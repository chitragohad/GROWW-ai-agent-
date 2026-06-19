"""SQLite run ledger for audit and idempotency (Phase 7)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pulse.ledger.models import DeliveryRecord, RunRecord

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    product TEXT NOT NULL,
    iso_week TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('pending', 'completed', 'failed')),
    review_count INTEGER,
    window_weeks INTEGER,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS deliveries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    channel TEXT NOT NULL CHECK(channel IN ('google_doc', 'gmail')),
    external_id TEXT NOT NULL,
    url TEXT,
    idempotency_key TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(run_id, channel)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_runs_completed_product_week
ON runs(product, iso_week)
WHERE status = 'completed';
"""


def default_ledger_path(data_dir: Path) -> Path:
    return data_dir / "ledger" / "pulse.db"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if value is None:
        return None
    return datetime.fromisoformat(value)


class LedgerStore:
    """Persistent run ledger backed by SQLite."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def _row_to_record(self, row: sqlite3.Row, deliveries: list[DeliveryRecord]) -> RunRecord:
        return RunRecord(
            run_id=row["run_id"],
            product=row["product"],
            iso_week=row["iso_week"],
            status=row["status"],  # type: ignore[arg-type]
            review_count=row["review_count"],
            window_weeks=row["window_weeks"],
            started_at=_parse_dt(row["started_at"]) or _utc_now(),
            completed_at=_parse_dt(row["completed_at"]),
            error_message=row["error_message"],
            deliveries=deliveries,
        )

    def _load_deliveries(self, conn: sqlite3.Connection, run_id: str) -> list[DeliveryRecord]:
        rows = conn.execute(
            "SELECT channel, external_id, url, idempotency_key FROM deliveries WHERE run_id = ? ORDER BY id",
            (run_id,),
        ).fetchall()
        return [
            DeliveryRecord(
                channel=row["channel"],  # type: ignore[arg-type]
                external_id=row["external_id"],
                url=row["url"],
                idempotency_key=row["idempotency_key"],
            )
            for row in rows
        ]

    def find_completed_run(self, product: str, iso_week: str) -> Optional[RunRecord]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM runs
                WHERE product = ? AND iso_week = ? AND status = 'completed'
                ORDER BY completed_at DESC
                LIMIT 1
                """,
                (product, iso_week),
            ).fetchone()
            if row is None:
                return None
            deliveries = self._load_deliveries(conn, row["run_id"])
            return self._row_to_record(row, deliveries)

    def find_latest_run(self, product: str, iso_week: str) -> Optional[RunRecord]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM runs
                WHERE product = ? AND iso_week = ?
                ORDER BY started_at DESC
                LIMIT 1
                """,
                (product, iso_week),
            ).fetchone()
            if row is None:
                return None
            deliveries = self._load_deliveries(conn, row["run_id"])
            return self._row_to_record(row, deliveries)

    def find_partial_delivery_run(self, product: str, iso_week: str) -> Optional[RunRecord]:
        """Return a failed run that delivered Doc but not Gmail (Gmail-only retry path)."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT r.* FROM runs r
                WHERE r.product = ? AND r.iso_week = ? AND r.status = 'failed'
                ORDER BY r.started_at DESC
                """,
                (product, iso_week),
            ).fetchall()
            for row in rows:
                deliveries = self._load_deliveries(conn, row["run_id"])
                channels = {d.channel for d in deliveries}
                if "google_doc" in channels and "gmail" not in channels:
                    return self._row_to_record(row, deliveries)
        return None

    def list_recent_runs(self, product: str, *, limit: int = 20) -> list[RunRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM runs
                WHERE product = ?
                ORDER BY started_at DESC
                LIMIT ?
                """,
                (product, limit),
            ).fetchall()
            records: list[RunRecord] = []
            for row in rows:
                deliveries = self._load_deliveries(conn, row["run_id"])
                records.append(self._row_to_record(row, deliveries))
            return records

    def find_failed_runs_since(
        self,
        product: str,
        *,
        since: datetime,
    ) -> list[RunRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM runs
                WHERE product = ? AND status = 'failed' AND started_at >= ?
                ORDER BY started_at DESC
                """,
                (product, _iso(since)),
            ).fetchall()
            records: list[RunRecord] = []
            for row in rows:
                deliveries = self._load_deliveries(conn, row["run_id"])
                records.append(self._row_to_record(row, deliveries))
            return records

    def create_run(
        self,
        run_id: str,
        product: str,
        iso_week: str,
        *,
        window_weeks: Optional[int] = None,
    ) -> RunRecord:
        started_at = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO runs (run_id, product, iso_week, status, window_weeks, started_at)
                VALUES (?, ?, ?, 'pending', ?, ?)
                """,
                (run_id, product, iso_week, window_weeks, _iso(started_at)),
            )
        return RunRecord(
            run_id=run_id,
            product=product,
            iso_week=iso_week,
            status="pending",
            window_weeks=window_weeks,
            started_at=started_at,
        )

    def reopen_run(self, run_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE runs SET status = 'pending', completed_at = NULL, error_message = NULL WHERE run_id = ?",
                (run_id,),
            )

    def update_run_metrics(self, run_id: str, *, review_count: int, window_weeks: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE runs SET review_count = ?, window_weeks = ? WHERE run_id = ?",
                (review_count, window_weeks, run_id),
            )

    def add_delivery(
        self,
        run_id: str,
        *,
        channel: str,
        external_id: str,
        url: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO deliveries (run_id, channel, external_id, url, idempotency_key, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id, channel) DO UPDATE SET
                    external_id = excluded.external_id,
                    url = excluded.url,
                    idempotency_key = excluded.idempotency_key,
                    created_at = excluded.created_at
                """,
                (run_id, channel, external_id, url, idempotency_key, _iso(_utc_now())),
            )

    def mark_completed(self, run_id: str) -> RunRecord:
        completed_at = _utc_now()
        with self._connect() as conn:
            conn.execute(
                "UPDATE runs SET status = 'completed', completed_at = ?, error_message = NULL WHERE run_id = ?",
                (_iso(completed_at), run_id),
            )
            row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            if row is None:
                raise KeyError(f"Run not found: {run_id}")
            deliveries = self._load_deliveries(conn, run_id)
            return self._row_to_record(row, deliveries)

    def mark_failed(self, run_id: str, error_message: str) -> RunRecord:
        completed_at = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE runs SET status = 'failed', completed_at = ?, error_message = ?
                WHERE run_id = ?
                """,
                (_iso(completed_at), error_message, run_id),
            )
            row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            if row is None:
                raise KeyError(f"Run not found: {run_id}")
            deliveries = self._load_deliveries(conn, run_id)
            return self._row_to_record(row, deliveries)

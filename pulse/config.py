"""Configuration loaders for product and pipeline YAML files."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, Field, field_validator


def project_root() -> Path:
    """Return repository root (directory containing config/)."""
    current = Path(__file__).resolve().parent
    for parent in [current, *current.parents]:
        if (parent / "config" / "pipeline.yaml").is_file():
            return parent
    raise FileNotFoundError("Could not locate project root (config/pipeline.yaml missing)")


def config_dir() -> Path:
    return project_root() / "config"


class PlayStoreConfig(BaseModel):
    app_id: str


class IngestionConfig(BaseModel):
    window_weeks: int = Field(ge=8, le=12)
    min_reviews: int = Field(ge=1)
    max_reviews: int = Field(ge=1)
    min_words: int = Field(ge=1)
    allowed_language: str = "en"


class EmailDeliveryConfig(BaseModel):
    recipients: list[str]
    default_mode: Literal["draft", "send"] = "draft"


class DeliveryConfig(BaseModel):
    google_doc_id: str
    email: EmailDeliveryConfig


class SchedulingConfig(BaseModel):
    timezone: str = "Asia/Kolkata"
    iso_week_policy: Literal["current", "previous_complete_before_monday_9am"] = (
        "previous_complete_before_monday_9am"
    )
    monday_cutoff_hour: int = Field(default=9, ge=0, le=23)


class ProductConfig(BaseModel):
    product: str
    display_name: str
    play_store: PlayStoreConfig
    ingestion: IngestionConfig
    delivery: DeliveryConfig
    scheduling: SchedulingConfig = Field(default_factory=SchedulingConfig)


class EmbeddingConfig(BaseModel):
    provider: str
    model: str
    batch_size: int = Field(ge=1)


class UmapConfig(BaseModel):
    n_neighbors: int = Field(ge=2)
    n_components: int = Field(ge=2)
    metric: str = "cosine"
    random_state: int = 42


class HdbscanConfig(BaseModel):
    min_cluster_size: int = Field(ge=2)
    min_samples: int = Field(ge=1)


class ClusteringConfig(BaseModel):
    umap: UmapConfig
    hdbscan: HdbscanConfig


class SummarizationConfig(BaseModel):
    provider: str
    model: str
    max_themes: int = Field(ge=1)
    max_tokens_per_run: int = Field(ge=1)
    max_samples_per_cluster: int = Field(ge=1)
    max_output_tokens_per_theme: int = Field(ge=1)
    request_interval_seconds: float = Field(ge=0)


class SafetyConfig(BaseModel):
    scrub_pii: bool = True
    max_review_chars: int = Field(ge=1)


class PipelineConfig(BaseModel):
    embedding: EmbeddingConfig
    clustering: ClusteringConfig
    summarization: SummarizationConfig
    safety: SafetyConfig


class AppSettings(BaseModel):
    """Runtime settings from environment variables."""

    pulse_env: Literal["development", "staging", "production"] = "development"
    pulse_data_dir: Path = Field(default_factory=lambda: project_root() / "data")
    mcp_config_path: Path = Field(default_factory=lambda: config_dir() / "mcp" / "servers.json")
    mcp_server_url: str = "https://web-production-bf583.up.railway.app"
    mcp_approval_key: Optional[str] = None
    pulse_email_mode: Optional[Literal["draft", "send"]] = None
    pulse_production_confirmed: bool = False
    pulse_alert_webhook_url: Optional[str] = None

    @classmethod
    def from_env(cls) -> AppSettings:
        import os

        env = os.environ.get("PULSE_ENV", "development")
        if env not in ("development", "staging", "production"):
            env = "development"

        data_dir = os.environ.get("PULSE_DATA_DIR")
        mcp_path = os.environ.get("MCP_CONFIG_PATH")
        mcp_url = os.environ.get("MCP_SERVER_URL")
        mcp_approval = os.environ.get("MCP_APPROVAL_KEY")
        email_mode = os.environ.get("PULSE_EMAIL_MODE")
        production_confirm = os.environ.get("PULSE_PRODUCTION_CONFIRM", "").strip().lower()
        alert_webhook = os.environ.get("PULSE_ALERT_WEBHOOK_URL", "").strip() or None

        if data_dir:
            os.makedirs(data_dir, exist_ok=True)
        hf_home = os.environ.get("HF_HOME")
        if hf_home:
            os.environ["HF_HOME"] = hf_home
            os.makedirs(hf_home, exist_ok=True)

        return cls(
            pulse_env=env,  # type: ignore[arg-type]
            pulse_data_dir=Path(data_dir) if data_dir else project_root() / "data",
            mcp_config_path=Path(mcp_path) if mcp_path else config_dir() / "mcp" / "servers.json",
            mcp_server_url=mcp_url or "https://web-production-bf583.up.railway.app",
            mcp_approval_key=mcp_approval or None,
            pulse_email_mode=email_mode if email_mode in ("draft", "send") else None,  # type: ignore[arg-type]
            pulse_production_confirmed=production_confirm in ("1", "true", "yes"),
            pulse_alert_webhook_url=alert_webhook,
        )


class PulseConfig(BaseModel):
    """Combined product + pipeline + app settings for a run."""

    product: ProductConfig
    pipeline: PipelineConfig
    settings: AppSettings

    @field_validator("settings", mode="before")
    @classmethod
    def _default_settings(cls, value: Optional[AppSettings]) -> AppSettings:
        return value or AppSettings.from_env()


def _load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}")
    return data


def load_product_config(product: str, *, root: Optional[Path] = None) -> ProductConfig:
    base = root or project_root()
    path = base / "config" / "products" / f"{product}.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"Product config not found: {path}")
    return ProductConfig.model_validate(_load_yaml(path))


def load_pipeline_config(*, root: Optional[Path] = None) -> PipelineConfig:
    base = root or project_root()
    path = base / "config" / "pipeline.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"Pipeline config not found: {path}")
    return PipelineConfig.model_validate(_load_yaml(path))


@lru_cache
def load_pulse_config(product: str = "groww") -> PulseConfig:
    return PulseConfig(
        product=load_product_config(product),
        pipeline=load_pipeline_config(),
        settings=AppSettings.from_env(),
    )

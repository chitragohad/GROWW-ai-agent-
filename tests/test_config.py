"""Configuration loader tests."""

from pulse.config import load_pipeline_config, load_product_config, load_pulse_config


def test_project_root_exists(project_root):
    assert (project_root / "config" / "pipeline.yaml").is_file()
    assert (project_root / "config" / "products" / "groww.yaml").is_file()


def test_load_groww_yaml(project_root):
    product = load_product_config("groww", root=project_root)
    assert product.product == "groww"
    assert product.display_name == "Groww"
    assert product.play_store.app_id == "com.nextbillion.groww"
    assert product.ingestion.window_weeks == 10
    assert product.ingestion.min_reviews == 20
    assert product.delivery.email.default_mode == "send"
    assert product.delivery.google_doc_id == "1ArysoTqwaheaUsz4QLHdm5HKOvkkAe_aDwbVnz43ZfA"
    assert product.scheduling.timezone == "Asia/Kolkata"
    assert product.scheduling.iso_week_policy == "previous_complete_before_monday_9am"


def test_load_pipeline_yaml(project_root):
    pipeline = load_pipeline_config(root=project_root)
    assert pipeline.embedding.provider == "sentence-transformers"
    assert pipeline.embedding.model == "BAAI/bge-small-en-v1.5"
    assert pipeline.clustering.umap.n_neighbors == 15
    assert pipeline.clustering.hdbscan.min_cluster_size == 5
    assert pipeline.summarization.model == "llama-3.3-70b-versatile"
    assert pipeline.safety.scrub_pii is True


def test_load_pulse_config_combined(project_root):
    config = load_pulse_config("groww")
    assert config.product.product == "groww"
    assert config.pipeline.summarization.max_tokens_per_run == 12000
    assert config.settings.pulse_env in ("development", "staging", "production")

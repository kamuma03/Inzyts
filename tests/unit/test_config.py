"""Tests for CloudConfig and APISourceConfig defaults."""

from src.config import CloudConfig, APISourceConfig


def test_cloud_config_defaults():
    cfg = CloudConfig()
    assert cfg.max_download_size_mb == 500
    assert "s3" in cfg.allowed_schemes
    assert "gs" in cfg.allowed_schemes
    assert "az" in cfg.allowed_schemes
    assert "abfs" in cfg.allowed_schemes
    assert "abfss" in cfg.allowed_schemes
    assert cfg.download_timeout_seconds == 300


def test_cloud_config_custom():
    cfg = CloudConfig(max_download_size_mb=1000, allowed_schemes=["s3"])
    assert cfg.max_download_size_mb == 1000
    assert cfg.allowed_schemes == ["s3"]


def test_api_source_config_defaults():
    cfg = APISourceConfig()
    assert cfg.max_pages == 10
    assert cfg.request_timeout_seconds == 30
    assert cfg.max_response_size_mb == 100
    assert cfg.require_https is True


def test_api_source_config_custom():
    cfg = APISourceConfig(max_pages=5, require_https=False)
    assert cfg.max_pages == 5
    assert cfg.require_https is False

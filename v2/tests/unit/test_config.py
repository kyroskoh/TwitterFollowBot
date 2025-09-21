"""
Tests for configuration management.
"""

import pytest
import tempfile
from pathlib import Path
import yaml

from x_follow_bot.core.config import Settings, create_sample_config, load_config


def test_settings_creation():
    """Test basic settings creation."""
    config_data = {
        "x_api": {
            "client_id": "test_id",
            "client_secret": "test_secret"
        }
    }
    
    settings = Settings(**config_data)
    assert settings.x_api.client_id == "test_id"
    assert settings.x_api.client_secret == "test_secret"


def test_settings_validation():
    """Test configuration validation."""
    # Valid configuration
    config_data = {
        "x_api": {
            "client_id": "test_id",
            "client_secret": "test_secret"
        },
        "bot": {
            "search_keywords": ["python", "test"]
        }
    }
    
    settings = Settings(**config_data)
    issues = settings.validate_configuration()
    assert len(issues) == 0


def test_settings_validation_missing_api_keys():
    """Test validation with missing API keys."""
    config_data = {
        "x_api": {
            "client_id": "",
            "client_secret": ""
        }
    }
    
    with pytest.raises(ValueError):
        Settings(**config_data)


def test_settings_validation_missing_keywords():
    """Test validation with missing search keywords."""
    config_data = {
        "x_api": {
            "client_id": "test_id",
            "client_secret": "test_secret"
        },
        "bot": {
            "search_keywords": []
        }
    }
    
    with pytest.raises(ValueError):
        Settings(**config_data)


def test_settings_from_yaml():
    """Test loading settings from YAML file."""
    config_data = {
        "x_api": {
            "client_id": "test_id",
            "client_secret": "test_secret"
        },
        "bot": {
            "search_keywords": ["python"]
        }
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(config_data, f)
        temp_path = f.name
    
    try:
        settings = Settings.from_yaml(temp_path)
        assert settings.x_api.client_id == "test_id"
        assert settings.bot.search_keywords == ["python"]
    finally:
        Path(temp_path).unlink()


def test_create_sample_config():
    """Test creating sample configuration file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        temp_path = f.name
    
    # Remove the empty file first
    Path(temp_path).unlink()
    
    try:
        create_sample_config(temp_path)
        assert Path(temp_path).exists()
        
        # Load and verify sample config
        with open(temp_path, 'r') as f:
            config_data = yaml.safe_load(f)
        
        assert "x_api" in config_data
        assert "bot" in config_data
        assert "client_id" in config_data["x_api"]
        assert "search_keywords" in config_data["bot"]
    finally:
        if Path(temp_path).exists():
            Path(temp_path).unlink()


def test_settings_to_yaml():
    """Test exporting settings to YAML."""
    config_data = {
        "x_api": {
            "client_id": "test_id",
            "client_secret": "test_secret"
        },
        "bot": {
            "search_keywords": ["python"]
        }
    }
    
    settings = Settings(**config_data)
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        temp_path = f.name
    
    # Remove the empty file first
    Path(temp_path).unlink()
    
    try:
        settings.to_yaml(temp_path)
        assert Path(temp_path).exists()
        
        # Load and verify exported config
        with open(temp_path, 'r') as f:
            exported_data = yaml.safe_load(f)
        
        # Should have redacted sensitive data
        assert exported_data["x_api"]["client_secret"] == "***REDACTED***"
        assert exported_data["bot"]["search_keywords"] == ["python"]
    finally:
        if Path(temp_path).exists():
            Path(temp_path).unlink()


def test_database_url_resolution():
    """Test database URL resolution for relative paths."""
    config_data = {
        "x_api": {
            "client_id": "test_id",
            "client_secret": "test_secret"
        },
        "database": {
            "url": "sqlite:///relative_path.db"
        }
    }
    
    settings = Settings(**config_data)
    db_url = settings.get_db_url()
    
    # Should convert relative path to absolute
    assert db_url.startswith("sqlite:///")
    assert "relative_path.db" in db_url
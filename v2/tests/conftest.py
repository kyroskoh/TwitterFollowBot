"""
Pytest configuration and fixtures for X Follow Bot tests.
"""

import pytest
import tempfile
import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from x_follow_bot.core.config import Settings
from x_follow_bot.storage.database import Base, DatabaseManager


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def test_config(temp_dir):
    """Create a test configuration."""
    config = {
        "x_api": {
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
            "bearer_token": "test_bearer_token",
            "redirect_uri": "http://localhost:8080/callback"
        },
        "bot": {
            "max_follows_per_hour": 10,
            "max_likes_per_hour": 20,
            "search_keywords": ["test", "python"],
            "min_followers": 5,
            "max_followers": 1000,
            "enable_safety_checks": True
        },
        "database": {
            "url": f"sqlite:///{temp_dir}/test.db",
            "echo": False
        },
        "redis": {
            "enabled": False
        },
        "logging": {
            "level": "DEBUG",
            "format": "text"
        }
    }
    
    return Settings(**config)


@pytest.fixture
def test_db(test_config):
    """Create a test database."""
    db_manager = DatabaseManager(test_config)
    db_manager.create_tables()
    yield db_manager
    # Cleanup is automatic with temporary directory


@pytest.fixture
def db_session(test_db):
    """Create a test database session."""
    session = test_db.get_session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def sample_user_data():
    """Sample user data for testing."""
    return {
        "id": 12345,
        "username": "testuser",
        "name": "Test User",
        "description": "A test user for testing",
        "verified": False,
        "protected": False,
        "public_metrics": {
            "followers_count": 100,
            "following_count": 50,
            "tweet_count": 200,
            "listed_count": 5
        }
    }


@pytest.fixture
def sample_tweet_data():
    """Sample tweet data for testing."""
    return {
        "id": 67890,
        "text": "This is a test tweet #python #testing",
        "author_id": 12345,
        "created_at": "2023-01-01T12:00:00Z",
        "public_metrics": {
            "retweet_count": 10,
            "like_count": 50,
            "reply_count": 5,
            "quote_count": 2
        }
    }
"""
Configuration management for X Follow Bot.
"""

import os
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import yaml


class DatabaseConfig(BaseModel):
    """Database configuration."""
    
    url: str = Field(default="sqlite:///x_follow_bot.db", description="Database URL")
    echo: bool = Field(default=False, description="Enable SQL logging")
    pool_size: int = Field(default=5, description="Connection pool size")
    max_overflow: int = Field(default=10, description="Max overflow connections")


class RedisConfig(BaseModel):
    """Redis configuration for caching."""
    
    url: str = Field(default="redis://localhost:6379/0", description="Redis URL")
    enabled: bool = Field(default=False, description="Enable Redis caching")
    ttl: int = Field(default=3600, description="Default TTL in seconds")


class XAPIConfig(BaseModel):
    """X API configuration."""
    
    client_id: str = Field(..., description="X API v2 Client ID")
    client_secret: str = Field(..., description="X API v2 Client Secret")
    bearer_token: Optional[str] = Field(default=None, description="Bearer token for app-only auth")
    redirect_uri: str = Field(default="http://localhost:8080/callback", description="OAuth redirect URI")
    
    # Rate limiting
    requests_per_window: int = Field(default=300, description="Requests per 15-minute window")
    window_size_minutes: int = Field(default=15, description="Rate limit window size")
    
    @validator('client_id', 'client_secret')
    def validate_required_fields(cls, v):
        if not v or not v.strip():
            raise ValueError("X API credentials are required")
        return v.strip()


class BotConfig(BaseModel):
    """Bot behavior configuration."""
    
    # Follow limits
    max_follows_per_hour: int = Field(default=50, description="Maximum follows per hour")
    max_follows_per_day: int = Field(default=400, description="Maximum follows per day")
    
    # Interaction limits
    max_likes_per_hour: int = Field(default=100, description="Maximum likes per hour")
    max_retweets_per_hour: int = Field(default=50, description="Maximum retweets per hour")
    
    # Search configuration
    search_keywords: List[str] = Field(default_factory=list, description="Keywords to search for")
    exclude_keywords: List[str] = Field(default_factory=list, description="Keywords to exclude")
    search_languages: List[str] = Field(default=["en"], description="Languages to search in")
    
    # User filtering
    min_followers: int = Field(default=10, description="Minimum followers required")
    max_followers: int = Field(default=100000, description="Maximum followers allowed")
    min_follower_ratio: float = Field(default=0.1, description="Minimum follower/following ratio")
    
    # Users to keep following (protected)
    users_keep_following: List[int] = Field(default_factory=list, description="User IDs to always keep following")
    users_keep_muted: List[int] = Field(default_factory=list, description="User IDs to keep muted")
    users_keep_unmuted: List[int] = Field(default_factory=list, description="User IDs to keep unmuted")
    
    # Blacklisted users
    blacklisted_users: List[int] = Field(default_factory=list, description="User IDs to never follow")
    blacklisted_keywords: List[str] = Field(default_factory=list, description="Keywords that trigger user blacklisting")
    
    # Timing
    follow_backoff_min_seconds: int = Field(default=30, description="Minimum wait between follows")
    follow_backoff_max_seconds: int = Field(default=120, description="Maximum wait between follows")
    
    # Safety features
    enable_safety_checks: bool = Field(default=True, description="Enable safety checks")
    enable_bot_detection: bool = Field(default=True, description="Enable bot detection")
    respect_rate_limits: bool = Field(default=True, description="Respect API rate limits")
    
    @validator('search_keywords')
    def validate_search_keywords(cls, v):
        if not v:
            raise ValueError("At least one search keyword is required")
        return [keyword.strip() for keyword in v if keyword.strip()]
    
    @validator('min_followers', 'max_followers')
    def validate_follower_counts(cls, v):
        if v < 0:
            raise ValueError("Follower counts must be non-negative")
        return v
    
    @validator('min_follower_ratio')
    def validate_follower_ratio(cls, v):
        if not 0 <= v <= 100:
            raise ValueError("Follower ratio must be between 0 and 100")
        return v


class LoggingConfig(BaseModel):
    """Logging configuration."""
    
    level: str = Field(default="INFO", description="Log level")
    format: str = Field(default="json", description="Log format (json or text)")
    file_path: Optional[str] = Field(default=None, description="Log file path")
    max_file_size: str = Field(default="10MB", description="Maximum log file size")
    backup_count: int = Field(default=5, description="Number of backup log files")
    
    @validator('level')
    def validate_log_level(cls, v):
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of: {valid_levels}")
        return v.upper()


class WebConfig(BaseModel):
    """Web interface configuration."""
    
    enabled: bool = Field(default=False, description="Enable web interface")
    host: str = Field(default="127.0.0.1", description="Web server host")
    port: int = Field(default=8000, description="Web server port")
    secret_key: str = Field(default="your-secret-key", description="Secret key for sessions")
    
    @validator('port')
    def validate_port(cls, v):
        if not 1 <= v <= 65535:
            raise ValueError("Port must be between 1 and 65535")
        return v


class Settings(BaseSettings):
    """Main application settings."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Core configurations
    x_api: XAPIConfig
    bot: BotConfig = Field(default_factory=BotConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    web: WebConfig = Field(default_factory=WebConfig)
    
    # Environment
    environment: str = Field(default="development", description="Runtime environment")
    debug: bool = Field(default=False, description="Enable debug mode")
    
    # File paths
    config_dir: Path = Field(default_factory=lambda: Path.home() / ".x-follow-bot")
    data_dir: Path = Field(default_factory=lambda: Path.home() / ".x-follow-bot" / "data")
    
    def __init__(self, **kwargs):
        """Initialize settings and create directories."""
        super().__init__(**kwargs)
        self.config_dir.mkdir(exist_ok=True)
        self.data_dir.mkdir(exist_ok=True)
    
    @classmethod
    def from_yaml(cls, config_path: Union[str, Path]) -> "Settings":
        """Load settings from YAML file."""
        config_path = Path(config_path)
        
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
        
        return cls(**config_data)
    
    @classmethod
    def from_env(cls) -> "Settings":
        """Load settings from environment variables."""
        return cls()
    
    def to_yaml(self, output_path: Union[str, Path]) -> None:
        """Save settings to YAML file."""
        output_path = Path(output_path)
        
        # Convert to dictionary and remove sensitive data
        config_dict = self.model_dump()
        
        # Remove sensitive fields
        if 'x_api' in config_dict:
            config_dict['x_api']['client_secret'] = "***REDACTED***"
            if config_dict['x_api'].get('bearer_token'):
                config_dict['x_api']['bearer_token'] = "***REDACTED***"
        
        with open(output_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)
    
    def get_cache_key(self, prefix: str, *args) -> str:
        """Generate cache key."""
        return f"x_follow_bot:{prefix}:{':'.join(str(arg) for arg in args)}"
    
    def get_db_url(self) -> str:
        """Get database URL with proper substitutions."""
        db_url = self.database.url
        
        # Handle SQLite relative paths
        if db_url.startswith("sqlite:///") and not db_url.startswith("sqlite:////"):
            db_path = db_url[10:]  # Remove "sqlite:///"
            if not os.path.isabs(db_path):
                db_path = self.data_dir / db_path
                db_url = f"sqlite:///{db_path}"
        
        return db_url
    
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() == "production"
    
    def validate_configuration(self) -> List[str]:
        """Validate configuration and return list of issues."""
        issues = []
        
        # Check X API configuration
        if not self.x_api.client_id:
            issues.append("X API Client ID is required")
        
        if not self.x_api.client_secret:
            issues.append("X API Client Secret is required")
        
        # Check bot configuration
        if not self.bot.search_keywords:
            issues.append("At least one search keyword is required")
        
        if self.bot.max_follows_per_hour > 100:
            issues.append("Max follows per hour should not exceed 100 for safety")
        
        # Check database
        if self.database.url.startswith("sqlite://") and self.is_production():
            issues.append("SQLite is not recommended for production use")
        
        return issues


def load_config(config_path: Optional[Union[str, Path]] = None) -> Settings:
    """Load configuration from file or environment."""
    if config_path:
        return Settings.from_yaml(config_path)
    
    # Try to load from default locations
    default_paths = [
        Path.cwd() / "config.yaml",
        Path.cwd() / "config.yml",
        Path.home() / ".x-follow-bot" / "config.yaml",
        Path.home() / ".x-follow-bot" / "config.yml",
    ]
    
    for path in default_paths:
        if path.exists():
            return Settings.from_yaml(path)
    
    # Fall back to environment variables
    return Settings.from_env()


def create_sample_config(output_path: Union[str, Path]) -> None:
    """Create a sample configuration file."""
    sample_config = {
        "x_api": {
            "client_id": "your_client_id_here",
            "client_secret": "your_client_secret_here",
            "bearer_token": "optional_bearer_token_here",
            "redirect_uri": "http://localhost:8080/callback"
        },
        "bot": {
            "max_follows_per_hour": 50,
            "max_likes_per_hour": 100,
            "search_keywords": ["python", "#programming", "#ai"],
            "exclude_keywords": ["spam", "scam"],
            "min_followers": 10,
            "max_followers": 50000,
            "follow_backoff_min_seconds": 30,
            "follow_backoff_max_seconds": 120,
            "enable_safety_checks": True
        },
        "database": {
            "url": "sqlite:///x_follow_bot.db",
            "echo": False
        },
        "logging": {
            "level": "INFO",
            "format": "json",
            "file_path": "logs/bot.log"
        }
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        yaml.dump(sample_config, f, default_flow_style=False, sort_keys=False)


# Global settings instance
_settings: Optional[Settings] = None


def get_settings(config_path: Optional[Union[str, Path]] = None) -> Settings:
    """Get global settings instance."""
    global _settings
    if _settings is None:
        _settings = load_config(config_path)
    return _settings


def reload_settings(config_path: Optional[Union[str, Path]] = None) -> Settings:
    """Reload global settings instance."""
    global _settings
    _settings = load_config(config_path)
    return _settings
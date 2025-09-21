"""
Database models and session management for X Follow Bot.
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, Float, JSON,
    ForeignKey, Index, UniqueConstraint, create_engine
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import structlog

from ..core.config import Settings

logger = structlog.get_logger(__name__)

Base = declarative_base()


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps."""
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class UserDB(Base, TimestampMixin):
    """Database model for X users."""
    
    __tablename__ = "users"
    
    # Primary key
    id = Column(Integer, primary_key=True, comment="X user ID")
    
    # User information
    username = Column(String(15), nullable=False, index=True, comment="X username (without @)")
    name = Column(String(50), nullable=False, comment="Display name")
    description = Column(Text, nullable=True, comment="Bio/description")
    verified = Column(Boolean, default=False, comment="Verified status")
    protected = Column(Boolean, default=False, comment="Protected account")
    
    # Metrics
    followers_count = Column(Integer, default=0, comment="Number of followers")
    following_count = Column(Integer, default=0, comment="Number of following")
    tweet_count = Column(Integer, default=0, comment="Number of tweets")
    listed_count = Column(Integer, default=0, comment="Number of lists")
    
    # Profile information
    profile_image_url = Column(Text, nullable=True, comment="Profile image URL")
    url = Column(Text, nullable=True, comment="Website URL")
    location = Column(String(100), nullable=True, comment="Location")
    
    # Bot tracking
    followed_at = Column(DateTime(timezone=True), nullable=True, comment="When bot followed this user")
    unfollowed_at = Column(DateTime(timezone=True), nullable=True, comment="When bot unfollowed this user")
    last_interaction = Column(DateTime(timezone=True), nullable=True, comment="Last interaction timestamp")
    interaction_count = Column(Integer, default=0, comment="Number of interactions")
    
    # Status flags
    is_following = Column(Boolean, default=False, comment="Currently following")
    is_follower = Column(Boolean, default=False, comment="User follows us")
    is_muted = Column(Boolean, default=False, comment="User is muted")
    is_blocked = Column(Boolean, default=False, comment="User is blocked")
    is_blacklisted = Column(Boolean, default=False, comment="User is blacklisted")
    
    # Bot analysis
    likely_bot = Column(Boolean, default=False, comment="Likely bot account")
    bot_score = Column(Float, nullable=True, comment="Bot likelihood score")
    
    # Relationships
    tweets = relationship("TweetDB", back_populates="author", cascade="all, delete-orphan")
    interactions = relationship("InteractionDB", back_populates="user", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index("idx_username", "username"),
        Index("idx_followed_at", "followed_at"),
        Index("idx_is_following", "is_following"),
        Index("idx_is_follower", "is_follower"),
        Index("idx_updated_at", "updated_at"),
        UniqueConstraint("id", name="uq_user_id"),
    )
    
    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', followers={self.followers_count})>"


class TweetDB(Base, TimestampMixin):
    """Database model for tweets."""
    
    __tablename__ = "tweets"
    
    # Primary key
    id = Column(Integer, primary_key=True, comment="Tweet ID")
    
    # Tweet content
    text = Column(Text, nullable=False, comment="Tweet text")
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="Author user ID")
    conversation_id = Column(Integer, nullable=True, comment="Conversation ID")
    in_reply_to_user_id = Column(Integer, nullable=True, comment="Reply to user ID")
    
    # Metadata
    lang = Column(String(10), nullable=True, comment="Language code")
    source = Column(String(100), nullable=True, comment="Tweet source")
    tweet_created_at = Column(DateTime(timezone=True), nullable=True, comment="Original tweet timestamp")
    
    # Metrics
    retweet_count = Column(Integer, default=0, comment="Retweet count")
    like_count = Column(Integer, default=0, comment="Like count")
    reply_count = Column(Integer, default=0, comment="Reply count")
    quote_count = Column(Integer, default=0, comment="Quote count")
    
    # Bot interactions
    liked_by_bot = Column(Boolean, default=False, comment="Liked by bot")
    retweeted_by_bot = Column(Boolean, default=False, comment="Retweeted by bot")
    replied_by_bot = Column(Boolean, default=False, comment="Replied by bot")
    processed_at = Column(DateTime(timezone=True), nullable=True, comment="Processing timestamp")
    
    # Analysis
    hashtags = Column(JSON, nullable=True, comment="Extracted hashtags")
    mentions = Column(JSON, nullable=True, comment="Extracted mentions")
    urls = Column(JSON, nullable=True, comment="Extracted URLs")
    
    # Relationships
    author = relationship("UserDB", back_populates="tweets")
    interactions = relationship("InteractionDB", back_populates="tweet", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index("idx_author_id", "author_id"),
        Index("idx_tweet_created_at", "tweet_created_at"),
        Index("idx_processed_at", "processed_at"),
        Index("idx_liked_by_bot", "liked_by_bot"),
        Index("idx_retweeted_by_bot", "retweeted_by_bot"),
        UniqueConstraint("id", name="uq_tweet_id"),
    )
    
    def __repr__(self):
        preview = self.text[:50] + "..." if len(self.text) > 50 else self.text
        return f"<Tweet(id={self.id}, author_id={self.author_id}, text='{preview}')>"


class InteractionDB(Base, TimestampMixin):
    """Database model for bot interactions."""
    
    __tablename__ = "interactions"
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Interaction details
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="Target user ID")
    tweet_id = Column(Integer, ForeignKey("tweets.id"), nullable=True, comment="Target tweet ID")
    
    # Interaction type
    interaction_type = Column(String(20), nullable=False, comment="Type of interaction")
    # Types: follow, unfollow, like, unlike, retweet, unretweet, mute, unmute, block, unblock
    
    # Status
    success = Column(Boolean, default=False, comment="Interaction was successful")
    error_message = Column(Text, nullable=True, comment="Error message if failed")
    
    # Context
    source_keyword = Column(String(100), nullable=True, comment="Keyword that triggered interaction")
    source_action = Column(String(50), nullable=True, comment="Action that triggered interaction")
    
    # Relationships
    user = relationship("UserDB", back_populates="interactions")
    tweet = relationship("TweetDB", back_populates="interactions")
    
    # Indexes
    __table_args__ = (
        Index("idx_user_id", "user_id"),
        Index("idx_tweet_id", "tweet_id"),
        Index("idx_interaction_type", "interaction_type"),
        Index("idx_created_at", "created_at"),
        Index("idx_success", "success"),
    )
    
    def __repr__(self):
        return f"<Interaction(id={self.id}, type={self.interaction_type}, user_id={self.user_id}, success={self.success})>"


class BotSessionDB(Base, TimestampMixin):
    """Database model for bot sessions."""
    
    __tablename__ = "bot_sessions"
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Session information
    session_id = Column(String(36), nullable=False, unique=True, comment="Unique session ID")
    status = Column(String(20), nullable=False, default="active", comment="Session status")
    # Status: active, paused, stopped, error
    
    # Configuration
    config_snapshot = Column(JSON, nullable=True, comment="Configuration at session start")
    keywords = Column(JSON, nullable=True, comment="Search keywords used")
    
    # Statistics
    users_followed = Column(Integer, default=0, comment="Users followed in session")
    users_unfollowed = Column(Integer, default=0, comment="Users unfollowed in session")
    tweets_liked = Column(Integer, default=0, comment="Tweets liked in session")
    tweets_retweeted = Column(Integer, default=0, comment="Tweets retweeted in session")
    
    # Timing
    started_at = Column(DateTime(timezone=True), server_default=func.now(), comment="Session start time")
    ended_at = Column(DateTime(timezone=True), nullable=True, comment="Session end time")
    
    # Error tracking
    error_count = Column(Integer, default=0, comment="Number of errors")
    last_error = Column(Text, nullable=True, comment="Last error message")
    
    # Indexes
    __table_args__ = (
        Index("idx_session_id", "session_id"),
        Index("idx_status", "status"),
        Index("idx_started_at", "started_at"),
    )
    
    def __repr__(self):
        return f"<BotSession(id={self.id}, session_id='{self.session_id}', status='{self.status}')>"


class AuthTokenDB(Base, TimestampMixin):
    """Database model for storing authentication tokens."""
    
    __tablename__ = "auth_tokens"
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Token information
    user_id = Column(Integer, nullable=True, comment="Associated user ID")
    token_type = Column(String(20), nullable=False, comment="Token type")
    # Types: access_token, refresh_token, bearer_token
    
    # Token data
    access_token = Column(Text, nullable=True, comment="Access token")
    refresh_token = Column(Text, nullable=True, comment="Refresh token")
    token_expires_at = Column(DateTime(timezone=True), nullable=True, comment="Token expiration")
    
    # Scopes and metadata
    scopes = Column(JSON, nullable=True, comment="OAuth scopes")
    metadata = Column(JSON, nullable=True, comment="Additional token metadata")
    
    # Status
    is_active = Column(Boolean, default=True, comment="Token is active")
    revoked_at = Column(DateTime(timezone=True), nullable=True, comment="Token revocation time")
    
    # Indexes
    __table_args__ = (
        Index("idx_user_id", "user_id"),
        Index("idx_token_type", "token_type"),
        Index("idx_is_active", "is_active"),
        Index("idx_expires_at", "token_expires_at"),
    )
    
    def __repr__(self):
        return f"<AuthToken(id={self.id}, user_id={self.user_id}, type='{self.token_type}')>"


class DatabaseManager:
    """Database manager for X Follow Bot."""
    
    def __init__(self, settings: Settings):
        """Initialize database manager."""
        self.settings = settings
        self.engine = None
        self.SessionLocal = None
        self._initialize_database()
    
    def _initialize_database(self):
        """Initialize database connection and create tables."""
        db_url = self.settings.get_db_url()
        
        self.engine = create_engine(
            db_url,
            echo=self.settings.database.echo,
            pool_size=self.settings.database.pool_size,
            max_overflow=self.settings.database.max_overflow,
        )
        
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )
        
        logger.info("Database initialized", db_url=db_url.split("://")[0] + "://***")
    
    def create_tables(self):
        """Create all database tables."""
        Base.metadata.create_all(bind=self.engine)
        logger.info("Database tables created")
    
    def drop_tables(self):
        """Drop all database tables."""
        Base.metadata.drop_all(bind=self.engine)
        logger.info("Database tables dropped")
    
    def get_session(self) -> Session:
        """Get a database session."""
        return self.SessionLocal()
    
    def health_check(self) -> bool:
        """Check database connectivity."""
        try:
            with self.get_session() as session:
                session.execute("SELECT 1")
                return True
        except Exception as e:
            logger.error("Database health check failed", error=str(e))
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        with self.get_session() as session:
            stats = {
                "users_count": session.query(UserDB).count(),
                "tweets_count": session.query(TweetDB).count(),
                "interactions_count": session.query(InteractionDB).count(),
                "sessions_count": session.query(BotSessionDB).count(),
                "following_count": session.query(UserDB).filter(UserDB.is_following == True).count(),
                "followers_count": session.query(UserDB).filter(UserDB.is_follower == True).count(),
            }
        
        return stats


# Global database manager instance
_db_manager: Optional[DatabaseManager] = None


def get_database_manager(settings: Optional[Settings] = None) -> DatabaseManager:
    """Get global database manager instance."""
    global _db_manager
    if _db_manager is None:
        if settings is None:
            from ..core.config import get_settings
            settings = get_settings()
        _db_manager = DatabaseManager(settings)
    return _db_manager


def get_db_session() -> Session:
    """Get database session."""
    return get_database_manager().get_session()
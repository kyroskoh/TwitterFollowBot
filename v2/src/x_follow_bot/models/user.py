"""
User data models for X Follow Bot.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class UserMetrics(BaseModel):
    """User public metrics."""
    
    followers_count: int = 0
    following_count: int = 0
    tweet_count: int = 0
    listed_count: int = 0


class User(BaseModel):
    """User model for X API v2."""
    
    id: int
    username: str
    name: str
    description: Optional[str] = None
    verified: bool = False
    protected: bool = False
    public_metrics: Optional[UserMetrics] = None
    profile_image_url: Optional[str] = None
    url: Optional[str] = None
    location: Optional[str] = None
    created_at: Optional[datetime] = None
    
    # Bot tracking fields
    followed_at: Optional[datetime] = None
    unfollowed_at: Optional[datetime] = None
    last_interaction: Optional[datetime] = None
    interaction_count: int = 0
    
    class Config:
        """Pydantic configuration."""
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }
    
    @classmethod
    def from_tweepy_user(cls, tweepy_user: Any) -> "User":
        """Create User from Tweepy user object."""
        metrics = None
        if hasattr(tweepy_user, 'public_metrics') and tweepy_user.public_metrics:
            metrics = UserMetrics(
                followers_count=tweepy_user.public_metrics.get('followers_count', 0),
                following_count=tweepy_user.public_metrics.get('following_count', 0),
                tweet_count=tweepy_user.public_metrics.get('tweet_count', 0),
                listed_count=tweepy_user.public_metrics.get('listed_count', 0)
            )
        
        return cls(
            id=int(tweepy_user.id),
            username=tweepy_user.username,
            name=tweepy_user.name,
            description=getattr(tweepy_user, 'description', None),
            verified=getattr(tweepy_user, 'verified', False),
            protected=getattr(tweepy_user, 'protected', False),
            public_metrics=metrics,
            profile_image_url=getattr(tweepy_user, 'profile_image_url', None),
            url=getattr(tweepy_user, 'url', None),
            location=getattr(tweepy_user, 'location', None),
            created_at=getattr(tweepy_user, 'created_at', None)
        )
    
    @property
    def is_verified(self) -> bool:
        """Check if user is verified."""
        return self.verified
    
    @property
    def follower_ratio(self) -> float:
        """Calculate follower to following ratio."""
        if not self.public_metrics or self.public_metrics.following_count == 0:
            return 0.0
        return self.public_metrics.followers_count / self.public_metrics.following_count
    
    @property
    def is_likely_bot(self) -> bool:
        """Simple heuristic to detect potential bots."""
        if not self.public_metrics:
            return False
        
        # Very high following to follower ratio
        if self.public_metrics.following_count > 5000 and self.follower_ratio < 0.1:
            return True
        
        # No description
        if not self.description or len(self.description.strip()) < 10:
            return True
        
        # Default profile image (simplified check)
        if not self.profile_image_url or 'default_profile' in self.profile_image_url:
            return True
        
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return self.model_dump()
    
    def __str__(self) -> str:
        """String representation."""
        return f"@{self.username} ({self.name})"
    
    def __repr__(self) -> str:
        """Detailed representation."""
        return f"User(id={self.id}, username='{self.username}', followers={self.public_metrics.followers_count if self.public_metrics else 0})"
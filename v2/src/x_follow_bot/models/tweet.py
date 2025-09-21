"""
Tweet data models for X Follow Bot.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class TweetMetrics(BaseModel):
    """Tweet public metrics."""
    
    retweet_count: int = 0
    like_count: int = 0
    reply_count: int = 0
    quote_count: int = 0


class Tweet(BaseModel):
    """Tweet model for X API v2."""
    
    id: int
    text: str
    author_id: int
    created_at: Optional[datetime] = None
    conversation_id: Optional[int] = None
    in_reply_to_user_id: Optional[int] = None
    referenced_tweets: Optional[List[Dict[str, Any]]] = None
    public_metrics: Optional[TweetMetrics] = None
    lang: Optional[str] = None
    source: Optional[str] = None
    
    # Bot interaction tracking
    liked_by_bot: bool = False
    retweeted_by_bot: bool = False
    replied_by_bot: bool = False
    processed_at: Optional[datetime] = None
    
    class Config:
        """Pydantic configuration."""
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }
    
    @classmethod
    def from_tweepy_tweet(cls, tweepy_tweet: Any) -> "Tweet":
        """Create Tweet from Tweepy tweet object."""
        metrics = None
        if hasattr(tweepy_tweet, 'public_metrics') and tweepy_tweet.public_metrics:
            metrics = TweetMetrics(
                retweet_count=tweepy_tweet.public_metrics.get('retweet_count', 0),
                like_count=tweepy_tweet.public_metrics.get('like_count', 0),
                reply_count=tweepy_tweet.public_metrics.get('reply_count', 0),
                quote_count=tweepy_tweet.public_metrics.get('quote_count', 0)
            )
        
        # Handle referenced tweets
        referenced_tweets = None
        if hasattr(tweepy_tweet, 'referenced_tweets') and tweepy_tweet.referenced_tweets:
            referenced_tweets = [
                {
                    'type': ref.type,
                    'id': ref.id
                }
                for ref in tweepy_tweet.referenced_tweets
            ]
        
        return cls(
            id=int(tweepy_tweet.id),
            text=tweepy_tweet.text,
            author_id=int(tweepy_tweet.author_id),
            created_at=getattr(tweepy_tweet, 'created_at', None),
            conversation_id=getattr(tweepy_tweet, 'conversation_id', None),
            in_reply_to_user_id=getattr(tweepy_tweet, 'in_reply_to_user_id', None),
            referenced_tweets=referenced_tweets,
            public_metrics=metrics,
            lang=getattr(tweepy_tweet, 'lang', None),
            source=getattr(tweepy_tweet, 'source', None)
        )
    
    @property
    def is_reply(self) -> bool:
        """Check if this tweet is a reply."""
        return self.in_reply_to_user_id is not None
    
    @property
    def is_retweet(self) -> bool:
        """Check if this tweet is a retweet."""
        return (self.referenced_tweets and 
                any(ref.get('type') == 'retweeted' for ref in self.referenced_tweets))
    
    @property
    def is_quote_tweet(self) -> bool:
        """Check if this tweet is a quote tweet."""
        return (self.referenced_tweets and 
                any(ref.get('type') == 'quoted' for ref in self.referenced_tweets))
    
    @property
    def engagement_rate(self) -> float:
        """Calculate simple engagement rate."""
        if not self.public_metrics:
            return 0.0
        
        total_engagement = (
            self.public_metrics.like_count +
            self.public_metrics.retweet_count +
            self.public_metrics.reply_count +
            self.public_metrics.quote_count
        )
        
        # This is a simplified calculation
        # In reality, you'd need follower count of the author
        return total_engagement
    
    @property
    def hashtags(self) -> List[str]:
        """Extract hashtags from tweet text."""
        import re
        return re.findall(r'#\w+', self.text)
    
    @property
    def mentions(self) -> List[str]:
        """Extract mentions from tweet text."""
        import re
        return re.findall(r'@\w+', self.text)
    
    @property
    def urls(self) -> List[str]:
        """Extract URLs from tweet text."""
        import re
        return re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', self.text)
    
    def contains_keywords(self, keywords: List[str]) -> bool:
        """Check if tweet contains any of the specified keywords."""
        text_lower = self.text.lower()
        return any(keyword.lower() in text_lower for keyword in keywords)
    
    def has_media(self) -> bool:
        """Check if tweet has media attachments."""
        # This would need to be enhanced with actual media detection
        # from the Twitter API response
        return 'pic.twitter.com' in self.text or 'media' in self.text.lower()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return self.model_dump()
    
    def __str__(self) -> str:
        """String representation."""
        preview = self.text[:50] + "..." if len(self.text) > 50 else self.text
        return f"Tweet({self.id}): {preview}"
    
    def __repr__(self) -> str:
        """Detailed representation."""
        return f"Tweet(id={self.id}, author_id={self.author_id}, likes={self.public_metrics.like_count if self.public_metrics else 0})"


class TweetSearchResult(BaseModel):
    """Container for tweet search results."""
    
    tweets: List[Tweet]
    meta: Dict[str, Any] = Field(default_factory=dict)
    users: Optional[List[Dict[str, Any]]] = None
    
    @property
    def count(self) -> int:
        """Number of tweets in result."""
        return len(self.tweets)
    
    def filter_by_keywords(self, keywords: List[str]) -> "TweetSearchResult":
        """Filter tweets by keywords."""
        filtered_tweets = [
            tweet for tweet in self.tweets
            if tweet.contains_keywords(keywords)
        ]
        
        return TweetSearchResult(
            tweets=filtered_tweets,
            meta=self.meta,
            users=self.users
        )
    
    def exclude_replies(self) -> "TweetSearchResult":
        """Exclude reply tweets."""
        filtered_tweets = [
            tweet for tweet in self.tweets
            if not tweet.is_reply
        ]
        
        return TweetSearchResult(
            tweets=filtered_tweets,
            meta=self.meta,
            users=self.users
        )
    
    def exclude_retweets(self) -> "TweetSearchResult":
        """Exclude retweets."""
        filtered_tweets = [
            tweet for tweet in self.tweets
            if not tweet.is_retweet
        ]
        
        return TweetSearchResult(
            tweets=filtered_tweets,
            meta=self.meta,
            users=self.users
        )
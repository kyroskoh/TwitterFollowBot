"""
X API v2 Client with rate limiting and error handling.
"""

import asyncio
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, timedelta
from dataclasses import dataclass

import tweepy
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import structlog

from .auth import XAuth, TokenResponse
from .exceptions import APIError, RateLimitError, AuthenticationError
from ..models.user import User
from ..models.tweet import Tweet

logger = structlog.get_logger(__name__)


@dataclass
class RateLimitInfo:
    """Rate limit information for an endpoint."""
    
    limit: int
    remaining: int
    reset_time: datetime
    
    @property
    def seconds_until_reset(self) -> int:
        """Seconds until rate limit resets."""
        return max(0, int((self.reset_time - datetime.utcnow()).total_seconds()))
    
    @property
    def is_exhausted(self) -> bool:
        """Check if rate limit is exhausted."""
        return self.remaining <= 0


class XClient:
    """
    Enhanced X API v2 client with rate limiting, retries, and async support.
    """
    
    def __init__(
        self,
        auth: XAuth,
        bearer_token: Optional[str] = None,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0
    ):
        """
        Initialize X API client.
        
        Args:
            auth: XAuth instance for authentication
            bearer_token: Optional bearer token for app-only auth
            max_retries: Maximum number of retries for failed requests
            base_delay: Base delay for exponential backoff
            max_delay: Maximum delay for exponential backoff
        """
        self.auth = auth
        self.bearer_token = bearer_token
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        
        # Initialize Tweepy client
        self._client: Optional[tweepy.Client] = None
        self._rate_limits: Dict[str, RateLimitInfo] = {}
        
        logger.info("X Client initialized", max_retries=max_retries)
    
    @property
    def client(self) -> tweepy.Client:
        """Get or create Tweepy client."""
        if not self._client:
            self._client = self.auth.get_tweepy_client(self.bearer_token)
        return self._client
    
    def _handle_rate_limit(self, response: Any) -> None:
        """Extract and store rate limit information from response."""
        if hasattr(response, 'headers'):
            headers = response.headers
            endpoint = self._get_endpoint_name(response)
            
            if 'x-rate-limit-limit' in headers:
                limit = int(headers['x-rate-limit-limit'])
                remaining = int(headers['x-rate-limit-remaining'])
                reset_timestamp = int(headers['x-rate-limit-reset'])
                reset_time = datetime.fromtimestamp(reset_timestamp)
                
                self._rate_limits[endpoint] = RateLimitInfo(
                    limit=limit,
                    remaining=remaining,
                    reset_time=reset_time
                )
                
                logger.debug("Rate limit updated",
                           endpoint=endpoint,
                           remaining=remaining,
                           limit=limit,
                           reset_time=reset_time.isoformat())
    
    def _get_endpoint_name(self, response: Any) -> str:
        """Extract endpoint name from response."""
        # This is a simplified implementation
        # In production, you'd want more sophisticated endpoint detection
        return "default"
    
    def _check_rate_limit(self, endpoint: str = "default") -> None:
        """Check if we're hitting rate limits for an endpoint."""
        if endpoint in self._rate_limits:
            rate_limit = self._rate_limits[endpoint]
            if rate_limit.is_exhausted:
                raise RateLimitError(
                    f"Rate limit exhausted for {endpoint}",
                    reset_time=int(rate_limit.reset_time.timestamp()),
                    limit=rate_limit.limit,
                    remaining=rate_limit.remaining
                )
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((tweepy.TooManyRequests, tweepy.ServiceUnavailable))
    )
    async def _make_request(self, func, *args, **kwargs):
        """Make API request with retry logic."""
        try:
            result = func(*args, **kwargs)
            return result
        except tweepy.TooManyRequests as e:
            logger.warning("Rate limit hit, retrying", error=str(e))
            raise RateLimitError("Rate limit exceeded")
        except tweepy.Unauthorized as e:
            logger.error("Authentication failed", error=str(e))
            raise AuthenticationError("Invalid credentials or expired token")
        except tweepy.HTTPException as e:
            logger.error("API error", status_code=e.response.status_code, error=str(e))
            raise APIError(
                f"API request failed: {e}",
                status_code=e.response.status_code if e.response else None
            )
    
    # User Management Methods
    async def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user information by username."""
        try:
            response = await self._make_request(
                self.client.get_user,
                username=username,
                user_fields=['id', 'username', 'name', 'description', 'public_metrics', 'verified']
            )
            
            if response.data:
                return User.from_tweepy_user(response.data)
            return None
            
        except Exception as e:
            logger.error("Failed to get user by username", username=username, error=str(e))
            raise
    
    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user information by ID."""
        try:
            response = await self._make_request(
                self.client.get_user,
                id=user_id,
                user_fields=['id', 'username', 'name', 'description', 'public_metrics', 'verified']
            )
            
            if response.data:
                return User.from_tweepy_user(response.data)
            return None
            
        except Exception as e:
            logger.error("Failed to get user by ID", user_id=user_id, error=str(e))
            raise
    
    async def get_followers(self, user_id: int, max_results: int = 100) -> List[User]:
        """Get followers of a user."""
        followers = []
        try:
            for response in tweepy.Paginator(
                self.client.get_users_followers,
                id=user_id,
                max_results=min(max_results, 1000),
                user_fields=['id', 'username', 'name', 'public_metrics']
            ).flatten(limit=max_results):
                followers.append(User.from_tweepy_user(response))
            
            return followers
            
        except Exception as e:
            logger.error("Failed to get followers", user_id=user_id, error=str(e))
            raise
    
    async def get_following(self, user_id: int, max_results: int = 100) -> List[User]:
        """Get users that a user is following."""
        following = []
        try:
            for response in tweepy.Paginator(
                self.client.get_users_following,
                id=user_id,
                max_results=min(max_results, 1000),
                user_fields=['id', 'username', 'name', 'public_metrics']
            ).flatten(limit=max_results):
                following.append(User.from_tweepy_user(response))
            
            return following
            
        except Exception as e:
            logger.error("Failed to get following", user_id=user_id, error=str(e))
            raise
    
    # Follow/Unfollow Methods
    async def follow_user(self, user_id: int) -> bool:
        """Follow a user."""
        try:
            response = await self._make_request(
                self.client.follow_user,
                target_user_id=user_id
            )
            
            success = response.data.get('following', False) if response.data else False
            logger.info("Follow user result", user_id=user_id, success=success)
            return success
            
        except Exception as e:
            logger.error("Failed to follow user", user_id=user_id, error=str(e))
            raise
    
    async def unfollow_user(self, user_id: int) -> bool:
        """Unfollow a user."""
        try:
            response = await self._make_request(
                self.client.unfollow_user,
                target_user_id=user_id
            )
            
            success = not response.data.get('following', True) if response.data else False
            logger.info("Unfollow user result", user_id=user_id, success=success)
            return success
            
        except Exception as e:
            logger.error("Failed to unfollow user", user_id=user_id, error=str(e))
            raise
    
    # Tweet Methods
    async def search_tweets(
        self,
        query: str,
        max_results: int = 100,
        tweet_fields: Optional[List[str]] = None
    ) -> List[Tweet]:
        """Search for tweets."""
        tweets = []
        tweet_fields = tweet_fields or ['id', 'text', 'author_id', 'created_at', 'public_metrics']
        
        try:
            for response in tweepy.Paginator(
                self.client.search_recent_tweets,
                query=query,
                max_results=min(max_results, 100),
                tweet_fields=tweet_fields,
                expansions=['author_id']
            ).flatten(limit=max_results):
                tweets.append(Tweet.from_tweepy_tweet(response))
            
            return tweets
            
        except Exception as e:
            logger.error("Failed to search tweets", query=query, error=str(e))
            raise
    
    async def like_tweet(self, tweet_id: int) -> bool:
        """Like a tweet."""
        try:
            response = await self._make_request(
                self.client.like,
                tweet_id=tweet_id
            )
            
            success = response.data.get('liked', False) if response.data else False
            logger.info("Like tweet result", tweet_id=tweet_id, success=success)
            return success
            
        except Exception as e:
            logger.error("Failed to like tweet", tweet_id=tweet_id, error=str(e))
            raise
    
    async def unlike_tweet(self, tweet_id: int) -> bool:
        """Unlike a tweet."""
        try:
            response = await self._make_request(
                self.client.unlike,
                tweet_id=tweet_id
            )
            
            success = not response.data.get('liked', True) if response.data else False
            logger.info("Unlike tweet result", tweet_id=tweet_id, success=success)
            return success
            
        except Exception as e:
            logger.error("Failed to unlike tweet", tweet_id=tweet_id, error=str(e))
            raise
    
    async def retweet(self, tweet_id: int) -> bool:
        """Retweet a tweet."""
        try:
            response = await self._make_request(
                self.client.retweet,
                tweet_id=tweet_id
            )
            
            success = response.data.get('retweeted', False) if response.data else False
            logger.info("Retweet result", tweet_id=tweet_id, success=success)
            return success
            
        except Exception as e:
            logger.error("Failed to retweet", tweet_id=tweet_id, error=str(e))
            raise
    
    async def unretweet(self, tweet_id: int) -> bool:
        """Remove retweet."""
        try:
            response = await self._make_request(
                self.client.unretweet,
                tweet_id=tweet_id
            )
            
            success = not response.data.get('retweeted', True) if response.data else False
            logger.info("Unretweet result", tweet_id=tweet_id, success=success)
            return success
            
        except Exception as e:
            logger.error("Failed to unretweet", tweet_id=tweet_id, error=str(e))
            raise
    
    async def create_tweet(self, text: str) -> Optional[Tweet]:
        """Create a new tweet."""
        try:
            response = await self._make_request(
                self.client.create_tweet,
                text=text
            )
            
            if response.data:
                # Get full tweet data
                full_tweet = await self._make_request(
                    self.client.get_tweet,
                    id=response.data['id'],
                    tweet_fields=['id', 'text', 'author_id', 'created_at', 'public_metrics']
                )
                
                if full_tweet.data:
                    tweet = Tweet.from_tweepy_tweet(full_tweet.data)
                    logger.info("Tweet created", tweet_id=tweet.id)
                    return tweet
            
            return None
            
        except Exception as e:
            logger.error("Failed to create tweet", text=text[:50], error=str(e))
            raise
    
    # Mute Methods
    async def mute_user(self, user_id: int) -> bool:
        """Mute a user."""
        try:
            response = await self._make_request(
                self.client.mute,
                target_user_id=user_id
            )
            
            success = response.data.get('muting', False) if response.data else False
            logger.info("Mute user result", user_id=user_id, success=success)
            return success
            
        except Exception as e:
            logger.error("Failed to mute user", user_id=user_id, error=str(e))
            raise
    
    async def unmute_user(self, user_id: int) -> bool:
        """Unmute a user."""
        try:
            response = await self._make_request(
                self.client.unmute,
                target_user_id=user_id
            )
            
            success = not response.data.get('muting', True) if response.data else False
            logger.info("Unmute user result", user_id=user_id, success=success)
            return success
            
        except Exception as e:
            logger.error("Failed to unmute user", user_id=user_id, error=str(e))
            raise
    
    # Utility Methods
    async def get_me(self) -> Optional[User]:
        """Get authenticated user information."""
        try:
            response = await self._make_request(
                self.client.get_me,
                user_fields=['id', 'username', 'name', 'description', 'public_metrics', 'verified']
            )
            
            if response.data:
                return User.from_tweepy_user(response.data)
            return None
            
        except Exception as e:
            logger.error("Failed to get authenticated user", error=str(e))
            raise
    
    def get_rate_limit_info(self, endpoint: str = "default") -> Optional[RateLimitInfo]:
        """Get rate limit information for an endpoint."""
        return self._rate_limits.get(endpoint)
    
    async def refresh_token_if_needed(self) -> bool:
        """Refresh access token if it's expired."""
        if not self.auth.is_token_valid() and self.auth.current_token and self.auth.current_token.refresh_token:
            try:
                await self.auth.refresh_access_token(self.auth.current_token.refresh_token)
                # Recreate client with new token
                self._client = None
                logger.info("Access token refreshed successfully")
                return True
            except Exception as e:
                logger.error("Failed to refresh access token", error=str(e))
                raise AuthenticationError("Failed to refresh access token")
        
        return False
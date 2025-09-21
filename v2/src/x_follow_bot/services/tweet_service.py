"""
Tweet interaction service for X Follow Bot.
"""

import asyncio
import random
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
import structlog

from ..core.client import XClient
from ..core.config import Settings
from ..core.exceptions import RateLimitError, APIError
from ..models.tweet import Tweet
from ..storage.database import TweetDB, UserDB, InteractionDB, get_db_session
from ..storage.cache import get_cache_manager, CacheKeys

logger = structlog.get_logger(__name__)


class TweetService:
    """Service for managing tweet interactions (likes, retweets, etc.)."""
    
    def __init__(self, client: XClient, settings: Settings):
        """Initialize tweet service."""
        self.client = client
        self.settings = settings
        self.cache = get_cache_manager(settings)
        
        # Rate limiting tracking
        self._like_count_hour = 0
        self._retweet_count_hour = 0
        self._last_reset = datetime.now(timezone.utc)
        
        logger.info("Tweet service initialized")
    
    async def _wait_between_actions(self) -> None:
        """Wait between tweet actions with random backoff."""
        min_wait = max(5, self.settings.bot.follow_backoff_min_seconds // 2)
        max_wait = max(10, self.settings.bot.follow_backoff_max_seconds // 2)
        
        wait_time = random.randint(min_wait, max_wait)
        
        logger.debug("Waiting between tweet actions", wait_time=wait_time)
        await asyncio.sleep(wait_time)
    
    def _check_rate_limits(self, action: str) -> bool:
        """Check if we're within rate limits for the action."""
        now = datetime.now(timezone.utc)
        
        # Reset hourly counters
        if (now - self._last_reset).total_seconds() >= 3600:
            self._like_count_hour = 0
            self._retweet_count_hour = 0
            self._last_reset = now
        
        # Check action-specific limits
        if action == "like":
            if self._like_count_hour >= self.settings.bot.max_likes_per_hour:
                logger.warning("Hourly like limit reached", 
                             count=self._like_count_hour,
                             limit=self.settings.bot.max_likes_per_hour)
                return False
        
        elif action == "retweet":
            if self._retweet_count_hour >= self.settings.bot.max_retweets_per_hour:
                logger.warning("Hourly retweet limit reached",
                             count=self._retweet_count_hour,
                             limit=self.settings.bot.max_retweets_per_hour)
                return False
        
        return True
    
    def _is_tweet_suitable_for_interaction(
        self,
        tweet: Tweet,
        action: str
    ) -> tuple[bool, str]:
        """Check if tweet is suitable for the given interaction."""
        
        # Don't interact with our own tweets
        me = self.client.auth.current_token
        if me and tweet.author_id == me:  # This would need proper user ID
            return False, "Cannot interact with own tweets"
        
        # Check if tweet contains excluded keywords
        if tweet.text:
            text_lower = tweet.text.lower()
            for keyword in self.settings.bot.exclude_keywords:
                if keyword.lower() in text_lower:
                    return False, f"Tweet contains excluded keyword: {keyword}"
        
        # Check if we've already interacted with this tweet
        with get_db_session() as session:
            existing_tweet = session.query(TweetDB).filter(TweetDB.id == tweet.id).first()
            
            if existing_tweet:
                if action == "like" and existing_tweet.liked_by_bot:
                    return False, "Already liked this tweet"
                elif action == "retweet" and existing_tweet.retweeted_by_bot:
                    return False, "Already retweeted this tweet"
        
        # Check tweet age (don't interact with very old tweets)
        if tweet.created_at:
            age_hours = (datetime.now(timezone.utc) - tweet.created_at).total_seconds() / 3600
            if age_hours > 24:  # Don't interact with tweets older than 24 hours
                return False, "Tweet is too old"
        
        # Don't interact with replies unless specifically configured
        if tweet.is_reply and not getattr(self.settings.bot, 'allow_reply_interactions', False):
            return False, "Tweet is a reply"
        
        return True, "Tweet is suitable for interaction"
    
    async def like_tweet(
        self,
        tweet: Tweet,
        source_keyword: Optional[str] = None,
        source_action: Optional[str] = None
    ) -> bool:
        """
        Like a tweet with safety checks and database tracking.
        
        Args:
            tweet: Tweet to like
            source_keyword: Keyword that triggered the like
            source_action: Action that triggered the like
            
        Returns:
            True if successfully liked, False otherwise
        """
        
        # Check rate limits
        if not self._check_rate_limits("like"):
            return False
        
        # Check if tweet is suitable for liking
        suitable, reason = self._is_tweet_suitable_for_interaction(tweet, "like")
        if not suitable:
            logger.debug("Tweet not suitable for liking",
                        tweet_id=tweet.id,
                        reason=reason)
            return False
        
        try:
            # Wait before action
            await self._wait_between_actions()
            
            # Attempt to like
            success = await self.client.like_tweet(tweet.id)
            
            # Update database
            with get_db_session() as session:
                # Update or create tweet record
                tweet_db = session.query(TweetDB).filter(TweetDB.id == tweet.id).first()
                if not tweet_db:
                    tweet_db = TweetDB(
                        id=tweet.id,
                        text=tweet.text,
                        author_id=tweet.author_id,
                        tweet_created_at=tweet.created_at,
                        lang=tweet.lang
                    )
                    session.add(tweet_db)
                
                if success:
                    tweet_db.liked_by_bot = True
                    tweet_db.processed_at = datetime.now(timezone.utc)
                    
                    # Update metrics if available
                    if tweet.public_metrics:
                        tweet_db.like_count = tweet.public_metrics.like_count
                        tweet_db.retweet_count = tweet.public_metrics.retweet_count
                        tweet_db.reply_count = tweet.public_metrics.reply_count
                        tweet_db.quote_count = tweet.public_metrics.quote_count
                
                # Record interaction
                interaction = InteractionDB(
                    user_id=tweet.author_id,
                    tweet_id=tweet.id,
                    interaction_type="like",
                    success=success,
                    source_keyword=source_keyword,
                    source_action=source_action
                )
                session.add(interaction)
                session.commit()
            
            if success:
                self._like_count_hour += 1
                
                # Update cache
                cache_key = CacheKeys.tweet_by_id(tweet.id)
                self.cache.delete(cache_key)
                
                logger.info("Successfully liked tweet",
                           tweet_id=tweet.id,
                           author_id=tweet.author_id,
                           source_keyword=source_keyword)
            else:
                logger.warning("Failed to like tweet", tweet_id=tweet.id)
            
            return success
            
        except RateLimitError as e:
            logger.warning("Rate limit hit while liking", tweet_id=tweet.id, error=str(e))
            self._record_failed_interaction(tweet, "like", str(e), source_keyword, source_action)
            return False
            
        except Exception as e:
            logger.error("Error liking tweet", tweet_id=tweet.id, error=str(e))
            self._record_failed_interaction(tweet, "like", str(e), source_keyword, source_action)
            return False
    
    async def retweet(
        self,
        tweet: Tweet,
        source_keyword: Optional[str] = None,
        source_action: Optional[str] = None
    ) -> bool:
        """
        Retweet a tweet with safety checks and database tracking.
        
        Args:
            tweet: Tweet to retweet
            source_keyword: Keyword that triggered the retweet
            source_action: Action that triggered the retweet
            
        Returns:
            True if successfully retweeted, False otherwise
        """
        
        # Check rate limits
        if not self._check_rate_limits("retweet"):
            return False
        
        # Check if tweet is suitable for retweeting
        suitable, reason = self._is_tweet_suitable_for_interaction(tweet, "retweet")
        if not suitable:
            logger.debug("Tweet not suitable for retweeting",
                        tweet_id=tweet.id,
                        reason=reason)
            return False
        
        # Additional check for retweets - don't retweet retweets
        if tweet.is_retweet:
            logger.debug("Skipping retweet of retweet", tweet_id=tweet.id)
            return False
        
        try:
            # Wait before action
            await self._wait_between_actions()
            
            # Attempt to retweet
            success = await self.client.retweet(tweet.id)
            
            # Update database
            with get_db_session() as session:
                # Update or create tweet record
                tweet_db = session.query(TweetDB).filter(TweetDB.id == tweet.id).first()
                if not tweet_db:
                    tweet_db = TweetDB(
                        id=tweet.id,
                        text=tweet.text,
                        author_id=tweet.author_id,
                        tweet_created_at=tweet.created_at,
                        lang=tweet.lang
                    )
                    session.add(tweet_db)
                
                if success:
                    tweet_db.retweeted_by_bot = True
                    tweet_db.processed_at = datetime.now(timezone.utc)
                
                # Record interaction
                interaction = InteractionDB(
                    user_id=tweet.author_id,
                    tweet_id=tweet.id,
                    interaction_type="retweet",
                    success=success,
                    source_keyword=source_keyword,
                    source_action=source_action
                )
                session.add(interaction)
                session.commit()
            
            if success:
                self._retweet_count_hour += 1
                
                # Update cache
                cache_key = CacheKeys.tweet_by_id(tweet.id)
                self.cache.delete(cache_key)
                
                logger.info("Successfully retweeted tweet",
                           tweet_id=tweet.id,
                           author_id=tweet.author_id,
                           source_keyword=source_keyword)
            else:
                logger.warning("Failed to retweet tweet", tweet_id=tweet.id)
            
            return success
            
        except Exception as e:
            logger.error("Error retweeting tweet", tweet_id=tweet.id, error=str(e))
            self._record_failed_interaction(tweet, "retweet", str(e), source_keyword, source_action)
            return False
    
    def _record_failed_interaction(
        self,
        tweet: Tweet,
        action: str,
        error_message: str,
        source_keyword: Optional[str] = None,
        source_action: Optional[str] = None
    ) -> None:
        """Record a failed interaction in the database."""
        try:
            with get_db_session() as session:
                interaction = InteractionDB(
                    user_id=tweet.author_id,
                    tweet_id=tweet.id,
                    interaction_type=action,
                    success=False,
                    error_message=error_message,
                    source_keyword=source_keyword,
                    source_action=source_action
                )
                session.add(interaction)
                session.commit()
        except Exception as e:
            logger.error("Failed to record failed interaction", error=str(e))
    
    async def auto_like_tweets(
        self,
        search_keywords: List[str],
        max_likes: int = 20
    ) -> Dict[str, Any]:
        """
        Automatically like tweets based on search keywords.
        
        Args:
            search_keywords: Keywords to search for
            max_likes: Maximum number of tweets to like
            
        Returns:
            Dictionary with results summary
        """
        
        results = {
            "total_searched": 0,
            "total_liked": 0,
            "total_skipped": 0,
            "errors": [],
            "liked_tweets": []
        }
        
        for keyword in search_keywords:
            if results["total_liked"] >= max_likes:
                break
            
            try:
                # Search for tweets with the keyword
                tweets = await self.client.search_tweets(
                    query=keyword,
                    max_results=min(100, max_likes * 2)
                )
                
                results["total_searched"] += len(tweets)
                
                # Like tweets
                for tweet in tweets:
                    if results["total_liked"] >= max_likes:
                        break
                    
                    success = await self.like_tweet(
                        tweet,
                        source_keyword=keyword,
                        source_action="auto_like"
                    )
                    
                    if success:
                        results["total_liked"] += 1
                        results["liked_tweets"].append({
                            "tweet_id": tweet.id,
                            "author_id": tweet.author_id,
                            "keyword": keyword,
                            "text_preview": tweet.text[:50] + "..." if len(tweet.text) > 50 else tweet.text
                        })
                    else:
                        results["total_skipped"] += 1
                
            except Exception as e:
                error_msg = f"Error searching/liking for keyword '{keyword}': {str(e)}"
                logger.error("Error in auto like", keyword=keyword, error=str(e))
                results["errors"].append(error_msg)
        
        logger.info("Auto like completed", results=results)
        return results
    
    async def auto_retweet_tweets(
        self,
        search_keywords: List[str],
        max_retweets: int = 10
    ) -> Dict[str, Any]:
        """
        Automatically retweet tweets based on search keywords.
        
        Args:
            search_keywords: Keywords to search for
            max_retweets: Maximum number of tweets to retweet
            
        Returns:
            Dictionary with results summary
        """
        
        results = {
            "total_searched": 0,
            "total_retweeted": 0,
            "total_skipped": 0,
            "errors": [],
            "retweeted_tweets": []
        }
        
        for keyword in search_keywords:
            if results["total_retweeted"] >= max_retweets:
                break
            
            try:
                # Search for tweets with the keyword
                tweets = await self.client.search_tweets(
                    query=keyword,
                    max_results=min(100, max_retweets * 2)
                )
                
                results["total_searched"] += len(tweets)
                
                # Retweet tweets
                for tweet in tweets:
                    if results["total_retweeted"] >= max_retweets:
                        break
                    
                    success = await self.retweet(
                        tweet,
                        source_keyword=keyword,
                        source_action="auto_retweet"
                    )
                    
                    if success:
                        results["total_retweeted"] += 1
                        results["retweeted_tweets"].append({
                            "tweet_id": tweet.id,
                            "author_id": tweet.author_id,
                            "keyword": keyword,
                            "text_preview": tweet.text[:50] + "..." if len(tweet.text) > 50 else tweet.text
                        })
                    else:
                        results["total_skipped"] += 1
                
            except Exception as e:
                error_msg = f"Error searching/retweeting for keyword '{keyword}': {str(e)}"
                logger.error("Error in auto retweet", keyword=keyword, error=str(e))
                results["errors"].append(error_msg)
        
        logger.info("Auto retweet completed", results=results)
        return results
    
    async def create_tweet(self, text: str) -> Optional[Tweet]:
        """
        Create a new tweet.
        
        Args:
            text: Tweet text
            
        Returns:
            Created tweet or None if failed
        """
        
        try:
            tweet = await self.client.create_tweet(text)
            
            if tweet:
                # Store in database
                with get_db_session() as session:
                    tweet_db = TweetDB(
                        id=tweet.id,
                        text=tweet.text,
                        author_id=tweet.author_id,
                        tweet_created_at=tweet.created_at,
                        lang=tweet.lang
                    )
                    session.add(tweet_db)
                    session.commit()
                
                logger.info("Successfully created tweet", tweet_id=tweet.id)
            
            return tweet
            
        except Exception as e:
            logger.error("Error creating tweet", text=text[:50], error=str(e))
            return None
    
    def get_tweet_stats(self) -> Dict[str, Any]:
        """Get tweet interaction statistics."""
        with get_db_session() as session:
            # Get counts
            total_tweets = session.query(TweetDB).count()
            liked_tweets = session.query(TweetDB).filter(TweetDB.liked_by_bot == True).count()
            retweeted_tweets = session.query(TweetDB).filter(TweetDB.retweeted_by_bot == True).count()
            
            # Get recent interactions
            recent_likes = session.query(InteractionDB).filter(
                InteractionDB.interaction_type == "like",
                InteractionDB.success == True,
                InteractionDB.created_at >= datetime.now(timezone.utc) - timedelta(days=1)
            ).count()
            
            recent_retweets = session.query(InteractionDB).filter(
                InteractionDB.interaction_type == "retweet",
                InteractionDB.success == True,
                InteractionDB.created_at >= datetime.now(timezone.utc) - timedelta(days=1)
            ).count()
            
            return {
                "total_tweets_processed": total_tweets,
                "total_liked": liked_tweets,
                "total_retweeted": retweeted_tweets,
                "recent_likes_24h": recent_likes,
                "recent_retweets_24h": recent_retweets,
                "hourly_like_count": self._like_count_hour,
                "hourly_retweet_count": self._retweet_count_hour,
                "hourly_like_limit": self.settings.bot.max_likes_per_hour,
                "hourly_retweet_limit": self.settings.bot.max_retweets_per_hour
            }
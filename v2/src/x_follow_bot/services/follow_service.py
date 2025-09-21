"""
Follow/Unfollow service for X Follow Bot.
"""

import asyncio
import random
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any, Set
from sqlalchemy.orm import Session
import structlog

from ..core.client import XClient
from ..core.config import Settings
from ..core.exceptions import RateLimitError, APIError
from ..models.user import User
from ..storage.database import UserDB, InteractionDB, get_db_session
from ..storage.cache import get_cache_manager, CacheKeys

logger = structlog.get_logger(__name__)


class FollowService:
    """Service for managing follow/unfollow operations."""
    
    def __init__(self, client: XClient, settings: Settings):
        """Initialize follow service."""
        self.client = client
        self.settings = settings
        self.cache = get_cache_manager(settings)
        
        # Rate limiting tracking
        self._follow_count_hour = 0
        self._follow_count_day = 0
        self._last_follow_reset = datetime.now(timezone.utc)
        
        logger.info("Follow service initialized")
    
    async def _wait_between_actions(self) -> None:
        """Wait between follow actions with random backoff."""
        min_wait = self.settings.bot.follow_backoff_min_seconds
        max_wait = self.settings.bot.follow_backoff_max_seconds
        
        wait_time = random.randint(min_wait, max_wait)
        
        logger.debug("Waiting between actions", wait_time=wait_time)
        await asyncio.sleep(wait_time)
    
    def _check_rate_limits(self) -> bool:
        """Check if we're within rate limits."""
        now = datetime.now(timezone.utc)
        
        # Reset hourly counter
        if (now - self._last_follow_reset).total_seconds() >= 3600:
            self._follow_count_hour = 0
            self._last_follow_reset = now
        
        # Reset daily counter
        if (now - self._last_follow_reset).total_seconds() >= 86400:
            self._follow_count_day = 0
        
        # Check limits
        if self._follow_count_hour >= self.settings.bot.max_follows_per_hour:
            logger.warning("Hourly follow limit reached", 
                         count=self._follow_count_hour,
                         limit=self.settings.bot.max_follows_per_hour)
            return False
        
        if self._follow_count_day >= self.settings.bot.max_follows_per_day:
            logger.warning("Daily follow limit reached",
                         count=self._follow_count_day,
                         limit=self.settings.bot.max_follows_per_day)
            return False
        
        return True
    
    def _is_user_suitable_for_following(self, user: User) -> tuple[bool, str]:
        """Check if user meets criteria for following."""
        
        # Check if user is blacklisted
        if user.id in self.settings.bot.blacklisted_users:
            return False, "User is blacklisted"
        
        # Check if user is protected
        if user.protected:
            return False, "User account is protected"
        
        # Check follower count limits
        if user.public_metrics:
            followers = user.public_metrics.followers_count
            following = user.public_metrics.following_count
            
            if followers < self.settings.bot.min_followers:
                return False, f"Too few followers ({followers} < {self.settings.bot.min_followers})"
            
            if followers > self.settings.bot.max_followers:
                return False, f"Too many followers ({followers} > {self.settings.bot.max_followers})"
            
            # Check follower ratio
            if following > 0:
                ratio = followers / following
                if ratio < self.settings.bot.min_follower_ratio:
                    return False, f"Poor follower ratio ({ratio:.2f} < {self.settings.bot.min_follower_ratio})"
        
        # Check for bot-like behavior
        if self.settings.bot.enable_bot_detection and user.is_likely_bot:
            return False, "User appears to be a bot"
        
        # Check for blacklisted keywords in description
        if user.description:
            description_lower = user.description.lower()
            for keyword in self.settings.bot.blacklisted_keywords:
                if keyword.lower() in description_lower:
                    return False, f"Description contains blacklisted keyword: {keyword}"
        
        return True, "User is suitable for following"
    
    async def follow_user(
        self,
        user: User,
        source_keyword: Optional[str] = None,
        source_action: Optional[str] = None
    ) -> bool:
        """
        Follow a user with safety checks and database tracking.
        
        Args:
            user: User to follow
            source_keyword: Keyword that triggered the follow
            source_action: Action that triggered the follow
            
        Returns:
            True if successfully followed, False otherwise
        """
        
        # Check rate limits
        if not self._check_rate_limits():
            return False
        
        # Check if user is suitable for following
        suitable, reason = self._is_user_suitable_for_following(user)
        if not suitable:
            logger.info("User not suitable for following", 
                       user_id=user.id, 
                       username=user.username,
                       reason=reason)
            return False
        
        # Check if already following
        with get_db_session() as session:
            existing_user = session.query(UserDB).filter(UserDB.id == user.id).first()
            if existing_user and existing_user.is_following:
                logger.info("Already following user", user_id=user.id, username=user.username)
                return False
        
        try:
            # Wait before action
            await self._wait_between_actions()
            
            # Attempt to follow
            success = await self.client.follow_user(user.id)
            
            # Update database
            with get_db_session() as session:
                # Update or create user record
                user_db = session.query(UserDB).filter(UserDB.id == user.id).first()
                if not user_db:
                    user_db = UserDB(
                        id=user.id,
                        username=user.username,
                        name=user.name,
                        description=user.description,
                        verified=user.verified,
                        protected=user.protected
                    )
                    session.add(user_db)
                
                if success:
                    user_db.is_following = True
                    user_db.followed_at = datetime.now(timezone.utc)
                    user_db.last_interaction = datetime.now(timezone.utc)
                    user_db.interaction_count += 1
                    
                    # Update metrics if available
                    if user.public_metrics:
                        user_db.followers_count = user.public_metrics.followers_count
                        user_db.following_count = user.public_metrics.following_count
                        user_db.tweet_count = user.public_metrics.tweet_count
                
                # Record interaction
                interaction = InteractionDB(
                    user_id=user.id,
                    interaction_type="follow",
                    success=success,
                    source_keyword=source_keyword,
                    source_action=source_action
                )
                session.add(interaction)
                session.commit()
            
            if success:
                self._follow_count_hour += 1
                self._follow_count_day += 1
                
                # Update cache
                cache_key = CacheKeys.user_by_id(user.id)
                self.cache.delete(cache_key)
                
                logger.info("Successfully followed user",
                           user_id=user.id,
                           username=user.username,
                           source_keyword=source_keyword)
            else:
                logger.warning("Failed to follow user",
                             user_id=user.id,
                             username=user.username)
            
            return success
            
        except RateLimitError as e:
            logger.warning("Rate limit hit while following", user_id=user.id, error=str(e))
            # Record failed interaction
            with get_db_session() as session:
                interaction = InteractionDB(
                    user_id=user.id,
                    interaction_type="follow",
                    success=False,
                    error_message=str(e),
                    source_keyword=source_keyword,
                    source_action=source_action
                )
                session.add(interaction)
                session.commit()
            return False
            
        except Exception as e:
            logger.error("Error following user", user_id=user.id, username=user.username, error=str(e))
            # Record failed interaction
            with get_db_session() as session:
                interaction = InteractionDB(
                    user_id=user.id,
                    interaction_type="follow",
                    success=False,
                    error_message=str(e),
                    source_keyword=source_keyword,
                    source_action=source_action
                )
                session.add(interaction)
                session.commit()
            return False
    
    async def unfollow_user(
        self,
        user_id: int,
        reason: Optional[str] = None
    ) -> bool:
        """
        Unfollow a user with database tracking.
        
        Args:
            user_id: ID of user to unfollow
            reason: Reason for unfollowing
            
        Returns:
            True if successfully unfollowed, False otherwise
        """
        
        # Check if user is protected
        if user_id in self.settings.bot.users_keep_following:
            logger.info("User is protected from unfollowing", user_id=user_id)
            return False
        
        try:
            # Wait before action
            await self._wait_between_actions()
            
            # Attempt to unfollow
            success = await self.client.unfollow_user(user_id)
            
            # Update database
            with get_db_session() as session:
                user_db = session.query(UserDB).filter(UserDB.id == user_id).first()
                if user_db:
                    if success:
                        user_db.is_following = False
                        user_db.unfollowed_at = datetime.now(timezone.utc)
                        user_db.last_interaction = datetime.now(timezone.utc)
                        user_db.interaction_count += 1
                
                # Record interaction
                interaction = InteractionDB(
                    user_id=user_id,
                    interaction_type="unfollow",
                    success=success,
                    source_action=reason
                )
                session.add(interaction)
                session.commit()
            
            if success:
                # Update cache
                cache_key = CacheKeys.user_by_id(user_id)
                self.cache.delete(cache_key)
                
                logger.info("Successfully unfollowed user", user_id=user_id, reason=reason)
            else:
                logger.warning("Failed to unfollow user", user_id=user_id)
            
            return success
            
        except Exception as e:
            logger.error("Error unfollowing user", user_id=user_id, error=str(e))
            # Record failed interaction
            with get_db_session() as session:
                interaction = InteractionDB(
                    user_id=user_id,
                    interaction_type="unfollow",
                    success=False,
                    error_message=str(e),
                    source_action=reason
                )
                session.add(interaction)
                session.commit()
            return False
    
    async def follow_users_from_search(
        self,
        search_keywords: List[str],
        max_follows: int = 10
    ) -> Dict[str, Any]:
        """
        Follow users based on search keywords.
        
        Args:
            search_keywords: Keywords to search for
            max_follows: Maximum number of users to follow
            
        Returns:
            Dictionary with results summary
        """
        
        results = {
            "total_searched": 0,
            "total_followed": 0,
            "total_skipped": 0,
            "errors": [],
            "followed_users": []
        }
        
        for keyword in search_keywords:
            if results["total_followed"] >= max_follows:
                break
            
            try:
                # Search for tweets with the keyword
                tweets = await self.client.search_tweets(
                    query=keyword,
                    max_results=min(100, max_follows * 2)  # Search more than we need
                )
                
                results["total_searched"] += len(tweets)
                
                # Get unique users from tweets
                user_ids = set()
                for tweet in tweets:
                    if tweet.author_id not in user_ids:
                        user_ids.add(tweet.author_id)
                        
                        if len(user_ids) >= max_follows - results["total_followed"]:
                            break
                
                # Follow users
                for tweet in tweets:
                    if results["total_followed"] >= max_follows:
                        break
                    
                    if tweet.author_id in user_ids:
                        user_ids.remove(tweet.author_id)
                        
                        # Get user details
                        user = await self.client.get_user_by_id(tweet.author_id)
                        if user:
                            success = await self.follow_user(
                                user,
                                source_keyword=keyword,
                                source_action="search_follow"
                            )
                            
                            if success:
                                results["total_followed"] += 1
                                results["followed_users"].append({
                                    "user_id": user.id,
                                    "username": user.username,
                                    "keyword": keyword
                                })
                            else:
                                results["total_skipped"] += 1
                        else:
                            results["total_skipped"] += 1
                
            except Exception as e:
                error_msg = f"Error searching for keyword '{keyword}': {str(e)}"
                logger.error("Error in search follow", keyword=keyword, error=str(e))
                results["errors"].append(error_msg)
        
        logger.info("Search follow completed", results=results)
        return results
    
    async def follow_followers_of_user(
        self,
        target_username: str,
        max_follows: int = 10
    ) -> Dict[str, Any]:
        """
        Follow followers of a specific user.
        
        Args:
            target_username: Username of the target user
            max_follows: Maximum number of followers to follow
            
        Returns:
            Dictionary with results summary
        """
        
        results = {
            "target_user": target_username,
            "total_followers": 0,
            "total_followed": 0,
            "total_skipped": 0,
            "errors": [],
            "followed_users": []
        }
        
        try:
            # Get target user
            target_user = await self.client.get_user_by_username(target_username)
            if not target_user:
                results["errors"].append(f"Target user '{target_username}' not found")
                return results
            
            # Get followers
            followers = await self.client.get_followers(target_user.id, max_results=max_follows * 2)
            results["total_followers"] = len(followers)
            
            # Follow followers
            for follower in followers:
                if results["total_followed"] >= max_follows:
                    break
                
                success = await self.follow_user(
                    follower,
                    source_action=f"follow_followers_of_{target_username}"
                )
                
                if success:
                    results["total_followed"] += 1
                    results["followed_users"].append({
                        "user_id": follower.id,
                        "username": follower.username
                    })
                else:
                    results["total_skipped"] += 1
            
        except Exception as e:
            error_msg = f"Error following followers of '{target_username}': {str(e)}"
            logger.error("Error in follow followers", target_username=target_username, error=str(e))
            results["errors"].append(error_msg)
        
        logger.info("Follow followers completed", results=results)
        return results
    
    async def unfollow_non_followers(self, max_unfollows: int = 50) -> Dict[str, Any]:
        """
        Unfollow users who don't follow back.
        
        Args:
            max_unfollows: Maximum number of users to unfollow
            
        Returns:
            Dictionary with results summary
        """
        
        results = {
            "total_checked": 0,
            "total_unfollowed": 0,
            "total_kept": 0,
            "errors": [],
            "unfollowed_users": []
        }
        
        try:
            with get_db_session() as session:
                # Get users we're following but who aren't following us back
                non_followers = session.query(UserDB).filter(
                    UserDB.is_following == True,
                    UserDB.is_follower == False,
                    ~UserDB.id.in_(self.settings.bot.users_keep_following)
                ).limit(max_unfollows * 2).all()
                
                results["total_checked"] = len(non_followers)
                
                for user_db in non_followers:
                    if results["total_unfollowed"] >= max_unfollows:
                        break
                    
                    # Check if user should be kept (recently followed)
                    if user_db.followed_at:
                        days_since_follow = (datetime.now(timezone.utc) - user_db.followed_at).days
                        if days_since_follow < 7:  # Keep for at least a week
                            results["total_kept"] += 1
                            continue
                    
                    success = await self.unfollow_user(
                        user_db.id,
                        reason="non_follower_cleanup"
                    )
                    
                    if success:
                        results["total_unfollowed"] += 1
                        results["unfollowed_users"].append({
                            "user_id": user_db.id,
                            "username": user_db.username
                        })
        
        except Exception as e:
            error_msg = f"Error in non-follower cleanup: {str(e)}"
            logger.error("Error in unfollow non-followers", error=str(e))
            results["errors"].append(error_msg)
        
        logger.info("Non-follower cleanup completed", results=results)
        return results
    
    def get_follow_stats(self) -> Dict[str, Any]:
        """Get follow/unfollow statistics."""
        with get_db_session() as session:
            # Get counts
            total_following = session.query(UserDB).filter(UserDB.is_following == True).count()
            total_followers = session.query(UserDB).filter(UserDB.is_follower == True).count()
            
            # Get recent interactions
            recent_follows = session.query(InteractionDB).filter(
                InteractionDB.interaction_type == "follow",
                InteractionDB.success == True,
                InteractionDB.created_at >= datetime.now(timezone.utc) - timedelta(days=1)
            ).count()
            
            recent_unfollows = session.query(InteractionDB).filter(
                InteractionDB.interaction_type == "unfollow",
                InteractionDB.success == True,
                InteractionDB.created_at >= datetime.now(timezone.utc) - timedelta(days=1)
            ).count()
            
            return {
                "total_following": total_following,
                "total_followers": total_followers,
                "follow_ratio": total_followers / max(total_following, 1),
                "recent_follows_24h": recent_follows,
                "recent_unfollows_24h": recent_unfollows,
                "hourly_follow_count": self._follow_count_hour,
                "daily_follow_count": self._follow_count_day,
                "hourly_limit": self.settings.bot.max_follows_per_hour,
                "daily_limit": self.settings.bot.max_follows_per_day
            }
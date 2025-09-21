"""
Main bot service that orchestrates all X Follow Bot operations.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
import structlog

from ..core.client import XClient
from ..core.auth import XAuth
from ..core.config import Settings
from ..core.exceptions import XFollowBotError, AuthenticationError
from ..storage.database import BotSessionDB, get_db_session, get_database_manager
from ..storage.cache import get_cache_manager
from .follow_service import FollowService
from .tweet_service import TweetService

logger = structlog.get_logger(__name__)


class BotService:
    """Main bot service that coordinates all operations."""
    
    def __init__(self, settings: Settings):
        """Initialize bot service."""
        self.settings = settings
        self.session_id = str(uuid.uuid4())
        self.status = "inactive"
        
        # Initialize components
        self.auth: Optional[XAuth] = None
        self.client: Optional[XClient] = None
        self.follow_service: Optional[FollowService] = None
        self.tweet_service: Optional[TweetService] = None
        
        # Initialize storage
        self.db_manager = get_database_manager(settings)
        self.cache = get_cache_manager(settings)
        
        # Session tracking
        self.session_db: Optional[BotSessionDB] = None
        
        logger.info("Bot service initialized", session_id=self.session_id)
    
    async def initialize(self) -> None:
        """Initialize bot components and authenticate."""
        try:
            # Initialize database
            self.db_manager.create_tables()
            
            # Initialize authentication
            self.auth = XAuth(
                client_id=self.settings.x_api.client_id,
                client_secret=self.settings.x_api.client_secret,
                redirect_uri=self.settings.x_api.redirect_uri
            )
            
            # Initialize API client
            self.client = XClient(
                auth=self.auth,
                bearer_token=self.settings.x_api.bearer_token
            )
            
            # Initialize services
            self.follow_service = FollowService(self.client, self.settings)
            self.tweet_service = TweetService(self.client, self.settings)
            
            # Validate configuration
            issues = self.settings.validate_configuration()
            if issues:
                logger.warning("Configuration issues found", issues=issues)
                for issue in issues:
                    logger.warning("Config issue", issue=issue)
            
            # Create session record
            await self._create_session_record()
            
            self.status = "initialized"
            logger.info("Bot service initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize bot service", error=str(e))
            self.status = "error"
            raise XFollowBotError(f"Bot initialization failed: {str(e)}")
    
    async def _create_session_record(self) -> None:
        """Create a session record in the database."""
        try:
            with get_db_session() as session:
                self.session_db = BotSessionDB(
                    session_id=self.session_id,
                    status="active",
                    config_snapshot=self.settings.model_dump(),
                    keywords=self.settings.bot.search_keywords,
                    started_at=datetime.now(timezone.utc)
                )
                session.add(self.session_db)
                session.commit()
                
            logger.info("Session record created", session_id=self.session_id)
            
        except Exception as e:
            logger.error("Failed to create session record", error=str(e))
    
    async def _update_session_stats(
        self,
        users_followed: int = 0,
        users_unfollowed: int = 0,
        tweets_liked: int = 0,
        tweets_retweeted: int = 0
    ) -> None:
        """Update session statistics."""
        try:
            with get_db_session() as session:
                session_record = session.query(BotSessionDB).filter(
                    BotSessionDB.session_id == self.session_id
                ).first()
                
                if session_record:
                    session_record.users_followed += users_followed
                    session_record.users_unfollowed += users_unfollowed
                    session_record.tweets_liked += tweets_liked
                    session_record.tweets_retweeted += tweets_retweeted
                    session.commit()
                    
        except Exception as e:
            logger.error("Failed to update session stats", error=str(e))
    
    async def start_automated_session(
        self,
        duration_minutes: Optional[int] = None,
        actions: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Start an automated bot session.
        
        Args:
            duration_minutes: How long to run (None for indefinite)
            actions: List of actions to perform (follow, like, retweet)
            
        Returns:
            Dictionary with session results
        """
        
        if self.status != "initialized":
            raise XFollowBotError("Bot must be initialized before starting session")
        
        # Default actions
        if actions is None:
            actions = ["follow", "like"]
        
        self.status = "running"
        start_time = datetime.now(timezone.utc)
        
        results = {
            "session_id": self.session_id,
            "start_time": start_time.isoformat(),
            "duration_minutes": duration_minutes,
            "actions_performed": {},
            "total_actions": 0,
            "errors": []
        }
        
        logger.info("Starting automated session",
                   session_id=self.session_id,
                   duration_minutes=duration_minutes,
                   actions=actions)
        
        try:
            # Run session loop
            cycle_count = 0
            
            while self.status == "running":
                cycle_count += 1
                cycle_start = datetime.now(timezone.utc)
                
                # Check if duration exceeded
                if duration_minutes:
                    elapsed_minutes = (cycle_start - start_time).total_seconds() / 60
                    if elapsed_minutes >= duration_minutes:
                        logger.info("Session duration reached", elapsed_minutes=elapsed_minutes)
                        break
                
                logger.info("Starting cycle", cycle=cycle_count)
                
                # Perform actions
                cycle_results = await self._run_action_cycle(actions)
                
                # Update results
                for action, count in cycle_results.items():
                    if action not in results["actions_performed"]:
                        results["actions_performed"][action] = 0
                    results["actions_performed"][action] += count
                    results["total_actions"] += count
                
                # Wait between cycles
                await asyncio.sleep(300)  # 5 minutes between cycles
                
                # Check health
                if not await self._health_check():
                    logger.warning("Health check failed, stopping session")
                    break
            
            self.status = "completed"
            end_time = datetime.now(timezone.utc)
            results["end_time"] = end_time.isoformat()
            results["total_duration_minutes"] = (end_time - start_time).total_seconds() / 60
            
            # Update session record
            await self._finalize_session_record()
            
            logger.info("Automated session completed", results=results)
            return results
            
        except Exception as e:
            self.status = "error"
            error_msg = f"Session error: {str(e)}"
            logger.error("Automated session failed", error=str(e))
            results["errors"].append(error_msg)
            
            # Update session record with error
            await self._finalize_session_record(error_msg)
            
            return results
    
    async def _run_action_cycle(self, actions: List[str]) -> Dict[str, int]:
        """Run one cycle of bot actions."""
        cycle_results = {}
        
        for action in actions:
            try:
                if action == "follow":
                    result = await self.follow_service.follow_users_from_search(
                        search_keywords=self.settings.bot.search_keywords,
                        max_follows=5  # Conservative per cycle
                    )
                    cycle_results["follow"] = result["total_followed"]
                    await self._update_session_stats(users_followed=result["total_followed"])
                
                elif action == "like":
                    result = await self.tweet_service.auto_like_tweets(
                        search_keywords=self.settings.bot.search_keywords,
                        max_likes=10  # Conservative per cycle
                    )
                    cycle_results["like"] = result["total_liked"]
                    await self._update_session_stats(tweets_liked=result["total_liked"])
                
                elif action == "retweet":
                    result = await self.tweet_service.auto_retweet_tweets(
                        search_keywords=self.settings.bot.search_keywords,
                        max_retweets=3  # Very conservative per cycle
                    )
                    cycle_results["retweet"] = result["total_retweeted"]
                    await self._update_session_stats(tweets_retweeted=result["total_retweeted"])
                
                elif action == "unfollow_cleanup":
                    result = await self.follow_service.unfollow_non_followers(
                        max_unfollows=5  # Conservative per cycle
                    )
                    cycle_results["unfollow"] = result["total_unfollowed"]
                    await self._update_session_stats(users_unfollowed=result["total_unfollowed"])
                
                # Small delay between action types
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error("Error in action cycle", action=action, error=str(e))
                cycle_results[action] = 0
        
        return cycle_results
    
    async def _health_check(self) -> bool:
        """Perform health checks on bot components."""
        try:
            # Check database connectivity
            if not self.db_manager.health_check():
                logger.error("Database health check failed")
                return False
            
            # Check cache connectivity (if enabled)
            if self.cache.enabled and not self.cache.health_check():
                logger.warning("Cache health check failed")
                # Not critical, continue
            
            # Check API client
            if self.client:
                # Try to refresh token if needed
                await self.client.refresh_token_if_needed()
                
                # Try a simple API call
                try:
                    me = await self.client.get_me()
                    if not me:
                        logger.error("Failed to get authenticated user info")
                        return False
                except Exception as e:
                    logger.error("API health check failed", error=str(e))
                    return False
            
            return True
            
        except Exception as e:
            logger.error("Health check failed", error=str(e))
            return False
    
    async def _finalize_session_record(self, error_message: Optional[str] = None) -> None:
        """Finalize the session record in the database."""
        try:
            with get_db_session() as session:
                session_record = session.query(BotSessionDB).filter(
                    BotSessionDB.session_id == self.session_id
                ).first()
                
                if session_record:
                    session_record.ended_at = datetime.now(timezone.utc)
                    session_record.status = "error" if error_message else "completed"
                    
                    if error_message:
                        session_record.error_count += 1
                        session_record.last_error = error_message
                    
                    session.commit()
                    
        except Exception as e:
            logger.error("Failed to finalize session record", error=str(e))
    
    def stop_session(self) -> None:
        """Stop the current session."""
        if self.status == "running":
            self.status = "stopping"
            logger.info("Session stop requested", session_id=self.session_id)
    
    def pause_session(self) -> None:
        """Pause the current session."""
        if self.status == "running":
            self.status = "paused"
            logger.info("Session paused", session_id=self.session_id)
    
    def resume_session(self) -> None:
        """Resume a paused session."""
        if self.status == "paused":
            self.status = "running"
            logger.info("Session resumed", session_id=self.session_id)
    
    async def follow_users_by_keyword(
        self,
        keywords: List[str],
        max_follows: int = 10
    ) -> Dict[str, Any]:
        """Follow users based on keywords."""
        if not self.follow_service:
            raise XFollowBotError("Follow service not initialized")
        
        return await self.follow_service.follow_users_from_search(keywords, max_follows)
    
    async def like_tweets_by_keyword(
        self,
        keywords: List[str],
        max_likes: int = 20
    ) -> Dict[str, Any]:
        """Like tweets based on keywords."""
        if not self.tweet_service:
            raise XFollowBotError("Tweet service not initialized")
        
        return await self.tweet_service.auto_like_tweets(keywords, max_likes)
    
    async def unfollow_non_followers(self, max_unfollows: int = 50) -> Dict[str, Any]:
        """Unfollow users who don't follow back."""
        if not self.follow_service:
            raise XFollowBotError("Follow service not initialized")
        
        return await self.follow_service.unfollow_non_followers(max_unfollows)
    
    def get_status(self) -> Dict[str, Any]:
        """Get current bot status and statistics."""
        status_info = {
            "session_id": self.session_id,
            "status": self.status,
            "initialized": self.auth is not None and self.client is not None,
            "database_connected": self.db_manager.health_check() if self.db_manager else False,
            "cache_enabled": self.cache.enabled if self.cache else False,
        }
        
        # Add service statistics if available
        if self.follow_service:
            status_info["follow_stats"] = self.follow_service.get_follow_stats()
        
        if self.tweet_service:
            status_info["tweet_stats"] = self.tweet_service.get_tweet_stats()
        
        # Add database statistics
        if self.db_manager:
            status_info["database_stats"] = self.db_manager.get_stats()
        
        return status_info
    
    async def cleanup(self) -> None:
        """Cleanup bot resources."""
        try:
            if self.status == "running":
                self.stop_session()
            
            # Finalize session record
            await self._finalize_session_record()
            
            self.status = "inactive"
            logger.info("Bot service cleanup completed")
            
        except Exception as e:
            logger.error("Error during cleanup", error=str(e))


# Global bot service instance
_bot_service: Optional[BotService] = None


def get_bot_service(settings: Optional[Settings] = None) -> BotService:
    """Get global bot service instance."""
    global _bot_service
    if _bot_service is None:
        if settings is None:
            from ..core.config import get_settings
            settings = get_settings()
        _bot_service = BotService(settings)
    return _bot_service
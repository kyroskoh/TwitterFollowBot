"""
Integration tests for database functionality.
"""

import pytest
from datetime import datetime, timezone

from x_follow_bot.storage.database import UserDB, TweetDB, InteractionDB, BotSessionDB


def test_database_connection(test_db):
    """Test database connection and health check."""
    assert test_db.health_check() is True


def test_create_user_record(db_session):
    """Test creating a user record."""
    user = UserDB(
        id=12345,
        username="testuser",
        name="Test User",
        description="A test user",
        verified=False,
        followers_count=100,
        following_count=50,
        is_following=True,
        followed_at=datetime.now(timezone.utc)
    )
    
    db_session.add(user)
    db_session.commit()
    
    # Retrieve and verify
    retrieved_user = db_session.query(UserDB).filter(UserDB.id == 12345).first()
    assert retrieved_user is not None
    assert retrieved_user.username == "testuser"
    assert retrieved_user.is_following is True


def test_create_tweet_record(db_session):
    """Test creating a tweet record."""
    # First create a user
    user = UserDB(
        id=12345,
        username="testuser",
        name="Test User"
    )
    db_session.add(user)
    db_session.commit()
    
    # Create tweet
    tweet = TweetDB(
        id=67890,
        text="This is a test tweet #python",
        author_id=12345,
        tweet_created_at=datetime.now(timezone.utc),
        like_count=10,
        retweet_count=5,
        liked_by_bot=True
    )
    
    db_session.add(tweet)
    db_session.commit()
    
    # Retrieve and verify
    retrieved_tweet = db_session.query(TweetDB).filter(TweetDB.id == 67890).first()
    assert retrieved_tweet is not None
    assert retrieved_tweet.text == "This is a test tweet #python"
    assert retrieved_tweet.liked_by_bot is True
    assert retrieved_tweet.author_id == 12345


def test_create_interaction_record(db_session):
    """Test creating an interaction record."""
    # Create user and tweet first
    user = UserDB(id=12345, username="testuser", name="Test User")
    tweet = TweetDB(id=67890, text="Test tweet", author_id=12345)
    
    db_session.add(user)
    db_session.add(tweet)
    db_session.commit()
    
    # Create interaction
    interaction = InteractionDB(
        user_id=12345,
        tweet_id=67890,
        interaction_type="like",
        success=True,
        source_keyword="python"
    )
    
    db_session.add(interaction)
    db_session.commit()
    
    # Retrieve and verify
    retrieved_interaction = db_session.query(InteractionDB).filter(
        InteractionDB.user_id == 12345,
        InteractionDB.interaction_type == "like"
    ).first()
    
    assert retrieved_interaction is not None
    assert retrieved_interaction.success is True
    assert retrieved_interaction.source_keyword == "python"


def test_create_bot_session_record(db_session):
    """Test creating a bot session record."""
    session = BotSessionDB(
        session_id="test-session-123",
        status="active",
        keywords=["python", "ai"],
        users_followed=10,
        tweets_liked=25,
        started_at=datetime.now(timezone.utc)
    )
    
    db_session.add(session)
    db_session.commit()
    
    # Retrieve and verify
    retrieved_session = db_session.query(BotSessionDB).filter(
        BotSessionDB.session_id == "test-session-123"
    ).first()
    
    assert retrieved_session is not None
    assert retrieved_session.status == "active"
    assert retrieved_session.users_followed == 10
    assert retrieved_session.tweets_liked == 25


def test_user_tweet_relationship(db_session):
    """Test relationship between users and tweets."""
    # Create user
    user = UserDB(
        id=12345,
        username="testuser",
        name="Test User"
    )
    db_session.add(user)
    db_session.commit()
    
    # Create tweets for the user
    tweet1 = TweetDB(id=67890, text="First tweet", author_id=12345)
    tweet2 = TweetDB(id=67891, text="Second tweet", author_id=12345)
    
    db_session.add(tweet1)
    db_session.add(tweet2)
    db_session.commit()
    
    # Verify relationship
    user_tweets = db_session.query(TweetDB).filter(TweetDB.author_id == 12345).all()
    assert len(user_tweets) == 2
    
    # Verify reverse relationship
    tweet = db_session.query(TweetDB).filter(TweetDB.id == 67890).first()
    assert tweet.author.username == "testuser"


def test_user_interaction_relationship(db_session):
    """Test relationship between users and interactions."""
    # Create user
    user = UserDB(id=12345, username="testuser", name="Test User")
    db_session.add(user)
    db_session.commit()
    
    # Create interactions
    interaction1 = InteractionDB(
        user_id=12345,
        interaction_type="follow",
        success=True
    )
    interaction2 = InteractionDB(
        user_id=12345,
        interaction_type="like",
        success=True
    )
    
    db_session.add(interaction1)
    db_session.add(interaction2)
    db_session.commit()
    
    # Verify relationship
    user_interactions = db_session.query(InteractionDB).filter(
        InteractionDB.user_id == 12345
    ).all()
    assert len(user_interactions) == 2


def test_database_stats(test_db, db_session):
    """Test database statistics retrieval."""
    # Add some test data
    user = UserDB(id=12345, username="testuser", name="Test User", is_following=True)
    tweet = TweetDB(id=67890, text="Test tweet", author_id=12345)
    interaction = InteractionDB(user_id=12345, interaction_type="follow", success=True)
    session = BotSessionDB(session_id="test-123", status="active")
    
    db_session.add(user)
    db_session.add(tweet)
    db_session.add(interaction)
    db_session.add(session)
    db_session.commit()
    
    # Get stats
    stats = test_db.get_stats()
    
    assert stats["users_count"] == 1
    assert stats["tweets_count"] == 1
    assert stats["interactions_count"] == 1
    assert stats["sessions_count"] == 1
    assert stats["following_count"] == 1
    assert stats["followers_count"] == 0


def test_database_indexes(db_session):
    """Test that database indexes work correctly."""
    # Add multiple users
    for i in range(100):
        user = UserDB(
            id=i,
            username=f"user{i}",
            name=f"User {i}",
            is_following=(i % 2 == 0)
        )
        db_session.add(user)
    
    db_session.commit()
    
    # Test indexed queries
    following_users = db_session.query(UserDB).filter(UserDB.is_following == True).all()
    assert len(following_users) == 50
    
    # Test username index
    specific_user = db_session.query(UserDB).filter(UserDB.username == "user50").first()
    assert specific_user is not None
    assert specific_user.id == 50
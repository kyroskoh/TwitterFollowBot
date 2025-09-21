"""
Tests for data models.
"""

import pytest
from datetime import datetime, timezone

from x_follow_bot.models.user import User, UserMetrics
from x_follow_bot.models.tweet import Tweet, TweetMetrics


class MockTweepyUser:
    """Mock Tweepy user object for testing."""
    
    def __init__(self, data):
        for key, value in data.items():
            setattr(self, key, value)


class MockTweepyTweet:
    """Mock Tweepy tweet object for testing."""
    
    def __init__(self, data):
        for key, value in data.items():
            setattr(self, key, value)


def test_user_metrics():
    """Test UserMetrics model."""
    metrics = UserMetrics(
        followers_count=1000,
        following_count=500,
        tweet_count=2000,
        listed_count=10
    )
    
    assert metrics.followers_count == 1000
    assert metrics.following_count == 500
    assert metrics.tweet_count == 2000
    assert metrics.listed_count == 10


def test_user_model():
    """Test User model."""
    metrics = UserMetrics(
        followers_count=1000,
        following_count=500,
        tweet_count=2000,
        listed_count=10
    )
    
    user = User(
        id=12345,
        username="testuser",
        name="Test User",
        description="A test user",
        verified=True,
        public_metrics=metrics
    )
    
    assert user.id == 12345
    assert user.username == "testuser"
    assert user.name == "Test User"
    assert user.is_verified is True
    assert user.follower_ratio == 2.0  # 1000/500


def test_user_from_tweepy():
    """Test creating User from Tweepy user object."""
    tweepy_data = {
        "id": 12345,
        "username": "testuser",
        "name": "Test User",
        "description": "A test user",
        "verified": True,
        "public_metrics": {
            "followers_count": 1000,
            "following_count": 500,
            "tweet_count": 2000,
            "listed_count": 10
        }
    }
    
    tweepy_user = MockTweepyUser(tweepy_data)
    user = User.from_tweepy_user(tweepy_user)
    
    assert user.id == 12345
    assert user.username == "testuser"
    assert user.is_verified is True
    assert user.public_metrics.followers_count == 1000


def test_user_bot_detection():
    """Test user bot detection heuristics."""
    # Bot-like user (high following, low followers)
    bot_metrics = UserMetrics(
        followers_count=10,
        following_count=5000,
        tweet_count=100,
        listed_count=0
    )
    
    bot_user = User(
        id=12345,
        username="botuser",
        name="Bot User",
        description="",  # No description
        public_metrics=bot_metrics
    )
    
    assert bot_user.is_likely_bot is True
    
    # Normal user
    normal_metrics = UserMetrics(
        followers_count=1000,
        following_count=500,
        tweet_count=2000,
        listed_count=10
    )
    
    normal_user = User(
        id=67890,
        username="normaluser",
        name="Normal User",
        description="I'm a real person who tweets about interesting things",
        public_metrics=normal_metrics,
        profile_image_url="https://example.com/real_image.jpg"
    )
    
    assert normal_user.is_likely_bot is False


def test_tweet_metrics():
    """Test TweetMetrics model."""
    metrics = TweetMetrics(
        retweet_count=10,
        like_count=50,
        reply_count=5,
        quote_count=2
    )
    
    assert metrics.retweet_count == 10
    assert metrics.like_count == 50
    assert metrics.reply_count == 5
    assert metrics.quote_count == 2


def test_tweet_model():
    """Test Tweet model."""
    metrics = TweetMetrics(
        retweet_count=10,
        like_count=50,
        reply_count=5,
        quote_count=2
    )
    
    tweet = Tweet(
        id=67890,
        text="This is a test tweet #python #testing",
        author_id=12345,
        created_at=datetime.now(timezone.utc),
        public_metrics=metrics
    )
    
    assert tweet.id == 67890
    assert tweet.author_id == 12345
    assert "python" in tweet.text
    assert tweet.engagement_rate == 67  # 10+50+5+2


def test_tweet_from_tweepy():
    """Test creating Tweet from Tweepy tweet object."""
    tweepy_data = {
        "id": 67890,
        "text": "This is a test tweet #python #testing",
        "author_id": 12345,
        "created_at": datetime.now(timezone.utc),
        "public_metrics": {
            "retweet_count": 10,
            "like_count": 50,
            "reply_count": 5,
            "quote_count": 2
        }
    }
    
    tweepy_tweet = MockTweepyTweet(tweepy_data)
    tweet = Tweet.from_tweepy_tweet(tweepy_tweet)
    
    assert tweet.id == 67890
    assert tweet.author_id == 12345
    assert tweet.public_metrics.like_count == 50


def test_tweet_hashtags_extraction():
    """Test hashtag extraction from tweet text."""
    tweet = Tweet(
        id=67890,
        text="This is a test tweet #python #testing #ai #machinelearning",
        author_id=12345
    )
    
    hashtags = tweet.hashtags
    assert "#python" in hashtags
    assert "#testing" in hashtags
    assert "#ai" in hashtags
    assert "#machinelearning" in hashtags
    assert len(hashtags) == 4


def test_tweet_mentions_extraction():
    """Test mention extraction from tweet text."""
    tweet = Tweet(
        id=67890,
        text="Hello @testuser and @anotheruser, this is a test tweet",
        author_id=12345
    )
    
    mentions = tweet.mentions
    assert "@testuser" in mentions
    assert "@anotheruser" in mentions
    assert len(mentions) == 2


def test_tweet_keyword_matching():
    """Test keyword matching in tweets."""
    tweet = Tweet(
        id=67890,
        text="This is a tweet about Python programming and machine learning",
        author_id=12345
    )
    
    # Should match keywords (case insensitive)
    assert tweet.contains_keywords(["python"]) is True
    assert tweet.contains_keywords(["Python"]) is True
    assert tweet.contains_keywords(["machine learning"]) is True
    assert tweet.contains_keywords(["javascript"]) is False
    assert tweet.contains_keywords(["python", "javascript"]) is True  # Any match


def test_tweet_type_detection():
    """Test tweet type detection."""
    # Regular tweet
    regular_tweet = Tweet(
        id=67890,
        text="This is a regular tweet",
        author_id=12345
    )
    assert regular_tweet.is_reply is False
    assert regular_tweet.is_retweet is False
    assert regular_tweet.is_quote_tweet is False
    
    # Reply tweet
    reply_tweet = Tweet(
        id=67891,
        text="@testuser This is a reply",
        author_id=12345,
        in_reply_to_user_id=54321
    )
    assert reply_tweet.is_reply is True
    
    # Retweet
    retweet = Tweet(
        id=67892,
        text="RT @original: This was retweeted",
        author_id=12345,
        referenced_tweets=[{"type": "retweeted", "id": "67893"}]
    )
    assert retweet.is_retweet is True
    
    # Quote tweet
    quote_tweet = Tweet(
        id=67894,
        text="Adding my thoughts to this: original tweet text",
        author_id=12345,
        referenced_tweets=[{"type": "quoted", "id": "67895"}]
    )
    assert quote_tweet.is_quote_tweet is True
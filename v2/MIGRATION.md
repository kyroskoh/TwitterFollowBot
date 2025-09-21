# Migration Guide: TwitterFollowBot v1 → v2.0

This guide helps you migrate from the original TwitterFollowBot (v1.x) to the new v2.0 version.

## 🚨 Important Changes

### API Changes
- **Twitter API v1.1** → **X API v2**
- **OAuth 1.0a** → **OAuth 2.0 with PKCE**
- **python-twitter library** → **tweepy 4.14+**

### Architecture Changes
- **Synchronous** → **Asynchronous (async/await)**
- **Text file storage** → **Database storage (SQLite/PostgreSQL)**
- **Python 2.7/3.3+** → **Python 3.11+**
- **Simple configuration** → **YAML/JSON configuration**

## 📋 Pre-Migration Checklist

### 1. Backup Your Data
```bash
# Backup your existing bot data
cp config.txt config_v1_backup.txt
cp already-followed.txt already-followed_backup.txt
cp followers.txt followers_backup.txt
cp following.txt following_backup.txt
```

### 2. Get X API v2 Credentials
You'll need new credentials from the X Developer Portal:

1. Go to [X Developer Portal](https://developer.twitter.com/)
2. Create a new Project (if you don't have one)
3. Create a new App within the Project
4. Enable OAuth 2.0
5. Generate Client ID and Client Secret
6. Set up redirect URI: `http://localhost:8080/callback`
7. Request these scopes:
   - `tweet.read`
   - `tweet.write` (optional)
   - `users.read`
   - `follows.read`
   - `follows.write`
   - `like.read`
   - `like.write`
   - `offline.access`

### 3. Check Access Tier
X API v2 has different access tiers:
- **Free**: 500 posts/month, 100 reads/month
- **Basic**: $200/month - 3K posts/month, 50K reads/month
- **Pro**: $5K/month - 1M reads/month, 300K posts/month

## 🔄 Migration Steps

### Step 1: Install v2.0

```bash
# Install from the v2 directory
cd TwitterFollowBot/v2
pip install -e .

# Or if available on PyPI
pip install x-follow-bot
```

### Step 2: Create New Configuration

```bash
# Create sample configuration
x-follow-bot config create

# This creates config.yaml - edit it with your credentials
```

**Map your old config.txt to new config.yaml:**

| v1 config.txt | v2 config.yaml |
|---------------|----------------|
| `OAUTH_TOKEN` | Not needed (OAuth 2.0 is different) |
| `OAUTH_SECRET` | Not needed |
| `CONSUMER_KEY` | `x_api.client_id` |
| `CONSUMER_SECRET` | `x_api.client_secret` |
| `TWITTER_HANDLE` | Auto-detected from API |
| `USERS_KEEP_FOLLOWING` | `bot.users_keep_following` |
| `FOLLOW_BACKOFF_*` | `bot.follow_backoff_*` |

### Step 3: Initialize Database

```bash
# Initialize the database
x-follow-bot database init
```

### Step 4: Import Existing Data (Optional)

Create a custom import script to migrate your text files:

```python
# import_v1_data.py
import asyncio
from pathlib import Path
from x_follow_bot.core.config import get_settings
from x_follow_bot.storage.database import get_db_session, UserDB
from x_follow_bot.services.bot_service import get_bot_service

async def import_v1_data():
    settings = get_settings()
    bot_service = get_bot_service(settings)
    await bot_service.initialize()
    
    # Import followers
    if Path("followers.txt").exists():
        with open("followers.txt", "r") as f:
            follower_ids = [int(line.strip()) for line in f if line.strip()]
        
        print(f"Importing {len(follower_ids)} followers...")
        
        with get_db_session() as session:
            for user_id in follower_ids:
                # Check if user already exists
                existing_user = session.query(UserDB).filter(UserDB.id == user_id).first()
                if not existing_user:
                    user = UserDB(
                        id=user_id,
                        username=f"imported_user_{user_id}",  # Will be updated when fetched
                        name="Imported User",
                        is_follower=True
                    )
                    session.add(user)
                else:
                    existing_user.is_follower = True
            
            session.commit()
    
    # Import following
    if Path("following.txt").exists():
        with open("following.txt", "r") as f:
            following_ids = [int(line.strip()) for line in f if line.strip()]
        
        print(f"Importing {len(following_ids)} following...")
        
        with get_db_session() as session:
            for user_id in following_ids:
                existing_user = session.query(UserDB).filter(UserDB.id == user_id).first()
                if not existing_user:
                    user = UserDB(
                        id=user_id,
                        username=f"imported_user_{user_id}",
                        name="Imported User",
                        is_following=True
                    )
                    session.add(user)
                else:
                    existing_user.is_following = True
            
            session.commit()
    
    # Import already followed
    if Path("already-followed.txt").exists():
        with open("already-followed.txt", "r") as f:
            already_followed_ids = [int(line.strip()) for line in f if line.strip()]
        
        print(f"Importing {len(already_followed_ids)} already followed...")
        
        with get_db_session() as session:
            for user_id in already_followed_ids:
                existing_user = session.query(UserDB).filter(UserDB.id == user_id).first()
                if not existing_user:
                    user = UserDB(
                        id=user_id,
                        username=f"imported_user_{user_id}",
                        name="Imported User",
                        is_blacklisted=True  # Mark as already processed
                    )
                    session.add(user)
                else:
                    existing_user.is_blacklisted = True
            
            session.commit()
    
    print("Import completed!")
    await bot_service.cleanup()

if __name__ == "__main__":
    asyncio.run(import_v1_data())
```

Run the import script:
```bash
python import_v1_data.py
```

### Step 5: Test the Migration

```bash
# Check bot status
x-follow-bot bot status

# Check database
x-follow-bot database status

# Test a small operation
x-follow-bot bot follow --keywords python --max-follows 1
```

## 🔧 Feature Mapping

### v1.x Methods → v2.0 Commands

| v1.x Method | v2.0 Command |
|-------------|--------------|
| `auto_follow("keyword")` | `x-follow-bot bot follow --keywords keyword` |
| `auto_fav("keyword")` | `x-follow-bot bot like --keywords keyword` |
| `auto_rt("keyword")` | `x-follow-bot bot retweet --keywords keyword` |
| `auto_follow_followers()` | `x-follow-bot bot follow-followers @username` |
| `auto_unfollow_nonfollowers()` | `x-follow-bot bot unfollow` |
| `sync_follows()` | Automatic with database |
| `send_tweet("message")` | `x-follow-bot bot tweet "message"` |

### v1.x Configuration → v2.0 Configuration

```yaml
# v1: config.txt
# CONSUMER_KEY:your_key
# CONSUMER_SECRET:your_secret
# USERS_KEEP_FOLLOWING:123,456

# v2: config.yaml
x_api:
  client_id: "your_key"
  client_secret: "your_secret"

bot:
  users_keep_following: [123, 456]
```

## 🚀 Running v2.0

### Basic Usage

```bash
# Follow users based on keywords
x-follow-bot bot follow --keywords "python,ai" --max-follows 10

# Like tweets
x-follow-bot bot like --keywords "#machinelearning" --max-likes 20

# Unfollow non-followers
x-follow-bot bot unfollow --max-unfollows 50

# Run automated session
x-follow-bot bot run --duration 60 --actions follow,like
```

### Programmatic Usage

```python
import asyncio
from x_follow_bot import BotService, Settings

async def main():
    settings = Settings.from_yaml("config.yaml")
    bot = BotService(settings)
    await bot.initialize()
    
    # Follow users (equivalent to v1's auto_follow)
    result = await bot.follow_users_by_keyword(["python"], max_follows=10)
    print(f"Followed {result['total_followed']} users")
    
    await bot.cleanup()

asyncio.run(main())
```

## ⚠️ Important Differences

### Rate Limits
- **v1.x**: Used Twitter API v1.1 rate limits
- **v2.0**: Uses X API v2 rate limits (much more restrictive on free tier)

### Data Storage
- **v1.x**: Text files (followers.txt, following.txt)
- **v2.0**: Database with full relationship tracking

### Error Handling
- **v1.x**: Basic error catching
- **v2.0**: Comprehensive error handling with retry logic

### Authentication
- **v1.x**: OAuth 1.0a (permanent tokens)
- **v2.0**: OAuth 2.0 (tokens expire, but refresh automatically)

## 🛠 Troubleshooting

### Common Issues

1. **"Invalid credentials" error**
   - Make sure you're using X API v2 credentials, not v1.1
   - Verify your Client ID and Client Secret

2. **"Rate limit exceeded" error**
   - v2.0 has stricter rate limits
   - Reduce `max_follows_per_hour` in config

3. **"Scope insufficient" error**
   - Make sure your app has the required OAuth 2.0 scopes
   - Regenerate tokens after adding scopes

4. **Database connection error**
   - Run `x-follow-bot database init` to create tables
   - Check database URL in config

### Getting Help

1. Check the [documentation](README.md)
2. Review [configuration examples](config.yaml.example)
3. Open an [issue](https://github.com/kyroskoh/TwitterFollowBot/issues)

## 📊 Performance Comparison

| Metric | v1.x | v2.0 |
|--------|------|------|
| API Version | Twitter v1.1 | X API v2 |
| Rate Limits | More generous | More restrictive |
| Data Storage | Text files | Database |
| Performance | Synchronous | Asynchronous |
| Error Recovery | Basic | Advanced |
| Monitoring | None | Built-in |
| Safety Features | Basic | Comprehensive |

## 🎯 Next Steps

After successful migration:

1. **Monitor Performance**: Use `x-follow-bot bot status` regularly
2. **Adjust Configuration**: Fine-tune rate limits based on your tier
3. **Set Up Monitoring**: Consider using the Docker setup with monitoring
4. **Backup Database**: Regular backups of your new database
5. **Stay Updated**: Watch for v2.0 updates and improvements

---

**Congratulations!** You've successfully migrated to TwitterFollowBot v2.0 🎉

The new version provides much better reliability, safety features, and monitoring capabilities while maintaining all the core functionality you're used to.
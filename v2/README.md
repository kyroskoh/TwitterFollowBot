# X Follow Bot v2.0

A modern, feature-rich Python bot for X (Twitter) automation with API v2 support.

## ✨ Features

- **X API v2 Support**: Built from the ground up for X API v2 with OAuth 2.0
- **Modern Architecture**: Async/await, type hints, comprehensive error handling
- **Database Storage**: SQLite/PostgreSQL support with SQLAlchemy ORM
- **Redis Caching**: Optional Redis integration for improved performance
- **Smart Rate Limiting**: Intelligent rate limiting with exponential backoff
- **Safety Features**: Bot detection, content filtering, user verification
- **CLI Interface**: Rich CLI with progress bars and colored output
- **Comprehensive Logging**: Structured logging with JSON output
- **Docker Support**: Ready-to-deploy Docker containers
- **Extensive Testing**: Unit and integration tests with high coverage

## 🚀 Quick Start

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/kyroskoh/TwitterFollowBot.git
cd TwitterFollowBot/v2

# Install dependencies
pip install -e .

# Or install from PyPI (when available)
pip install x-follow-bot
```

### 2. Configuration

Create a configuration file:

```bash
x-follow-bot config create
```

Edit the generated `config.yaml` with your X API credentials:

```yaml
x_api:
  client_id: "your_client_id_here"
  client_secret: "your_client_secret_here"
  bearer_token: "optional_bearer_token"
  redirect_uri: "http://localhost:8080/callback"

bot:
  max_follows_per_hour: 50
  max_likes_per_hour: 100
  search_keywords: ["python", "#programming", "#ai"]
  min_followers: 10
  max_followers: 50000
  enable_safety_checks: true

database:
  url: "sqlite:///x_follow_bot.db"

logging:
  level: "INFO"
  format: "json"
```

### 3. Initialize Database

```bash
x-follow-bot database init
```

### 4. Run the Bot

```bash
# Follow users based on keywords
x-follow-bot bot follow --keywords python ai --max-follows 10

# Like tweets
x-follow-bot bot like --keywords "machine learning" --max-likes 20

# Unfollow non-followers
x-follow-bot bot unfollow --max-unfollows 50

# Run automated session
x-follow-bot bot run --duration 60 --actions follow like
```

## 📋 Requirements

### X API v2 Credentials

You need X API v2 credentials from the [X Developer Portal](https://developer.twitter.com/):

1. Create a new App in your Project
2. Generate Client ID and Client Secret
3. Set up OAuth 2.0 with appropriate scopes
4. Optionally generate a Bearer Token for app-only authentication

### Required Scopes

- `tweet.read` - Read tweets
- `tweet.write` - Create tweets (optional)
- `users.read` - Read user profiles
- `follows.read` - Read following/followers
- `follows.write` - Follow/unfollow users
- `like.read` - Read likes
- `like.write` - Like/unlike tweets
- `offline.access` - Refresh tokens

## 🛠 Advanced Usage

### Environment Variables

You can configure the bot using environment variables:

```bash
export X_API_CLIENT_ID="your_client_id"
export X_API_CLIENT_SECRET="your_client_secret"
export BOT_SEARCH_KEYWORDS="python,#ai,#machinelearning"
export DATABASE_URL="postgresql://user:pass@localhost/xbot"
```

### Docker Deployment

```bash
# Build Docker image
docker build -t x-follow-bot .

# Run with environment variables
docker run -d \
  -e X_API_CLIENT_ID="your_client_id" \
  -e X_API_CLIENT_SECRET="your_client_secret" \
  -e DATABASE_URL="postgresql://user:pass@host/db" \
  x-follow-bot bot run --duration 1440  # Run for 24 hours
```

### Programmatic Usage

```python
import asyncio
from x_follow_bot import BotService, Settings

async def main():
    # Load configuration
    settings = Settings.from_yaml("config.yaml")
    
    # Initialize bot
    bot = BotService(settings)
    await bot.initialize()
    
    # Follow users
    result = await bot.follow_users_by_keyword(["python", "ai"], max_follows=10)
    print(f"Followed {result['total_followed']} users")
    
    # Like tweets
    result = await bot.like_tweets_by_keyword(["machine learning"], max_likes=20)
    print(f"Liked {result['total_liked']} tweets")
    
    # Cleanup
    await bot.cleanup()

asyncio.run(main())
```

## 📊 Monitoring and Analytics

### Status Dashboard

```bash
# Check bot status
x-follow-bot bot status

# Database statistics
x-follow-bot database status

# Validate configuration
x-follow-bot config validate
```

### Database Queries

The bot stores all interactions in a SQLite/PostgreSQL database:

```sql
-- Recent follows
SELECT u.username, i.created_at 
FROM interactions i 
JOIN users u ON i.user_id = u.id 
WHERE i.interaction_type = 'follow' 
ORDER BY i.created_at DESC 
LIMIT 10;

-- Follow success rate
SELECT 
    interaction_type,
    COUNT(*) as total,
    SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful,
    ROUND(AVG(CASE WHEN success THEN 1.0 ELSE 0.0 END) * 100, 2) as success_rate
FROM interactions 
GROUP BY interaction_type;
```

## ⚠️ Safety and Best Practices

### Rate Limiting

The bot automatically respects X API rate limits:

- **Free Tier**: 500 posts/month, 100 reads/month
- **Basic Tier**: 3K posts/month, 50K reads/month
- **Pro Tier**: 1M reads/month, 300K posts/month

### Safety Features

- **Bot Detection**: Automatically detects and skips likely bot accounts
- **Content Filtering**: Configurable keyword blacklists
- **User Protection**: Protected lists for important accounts
- **Conservative Limits**: Built-in limits to prevent aggressive behavior
- **Error Handling**: Graceful handling of API errors and rate limits

### Recommended Settings

```yaml
bot:
  max_follows_per_hour: 50        # Conservative follow rate
  max_likes_per_hour: 100         # Conservative like rate
  min_followers: 10               # Avoid empty accounts
  max_followers: 100000           # Avoid celebrity accounts
  min_follower_ratio: 0.1         # Avoid accounts with poor ratios
  enable_safety_checks: true      # Enable all safety features
  enable_bot_detection: true      # Skip likely bots
  respect_rate_limits: true       # Always respect API limits
```

## 🔧 Development

### Setup Development Environment

```bash
# Clone repository
git clone https://github.com/kyroskoh/TwitterFollowBot.git
cd TwitterFollowBot/v2

# Install development dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Run tests
pytest

# Run linting
black src tests
ruff check src tests
mypy src
```

### Architecture

```
src/x_follow_bot/
├── core/           # Core functionality
│   ├── auth.py     # OAuth 2.0 authentication
│   ├── client.py   # X API v2 client
│   ├── config.py   # Configuration management
│   └── exceptions.py
├── models/         # Data models
│   ├── user.py     # User model
│   └── tweet.py    # Tweet model
├── services/       # Business logic
│   ├── bot_service.py      # Main bot orchestration
│   ├── follow_service.py   # Follow/unfollow logic
│   └── tweet_service.py    # Tweet interactions
├── storage/        # Data persistence
│   ├── database.py # SQLAlchemy models
│   └── cache.py    # Redis caching
└── cli/           # Command-line interface
    └── main.py    # CLI commands
```

## 📜 Migration from v1

If you're migrating from the original TwitterFollowBot:

### Key Differences

| Feature | v1.x | v2.0 |
|---------|------|------|
| API | Twitter API v1.1 | X API v2 |
| Auth | OAuth 1.0a | OAuth 2.0 + PKCE |
| Storage | Text files | SQLite/PostgreSQL |
| Python | 2.7/3.3+ | 3.11+ |
| Dependencies | twitter==1.17.0 | tweepy>=4.14.0 |
| Architecture | Synchronous | Async/await |
| Configuration | config.txt | YAML/JSON |

### Migration Steps

1. **Export existing data** (optional):
   ```bash
   # Backup your existing files
   cp followers.txt followers_backup.txt
   cp following.txt following_backup.txt
   ```

2. **Install v2.0**:
   ```bash
   pip install x-follow-bot
   ```

3. **Create new configuration**:
   ```bash
   x-follow-bot config create
   ```

4. **Update credentials** to X API v2

5. **Initialize database**:
   ```bash
   x-follow-bot database init
   ```

6. **Import existing data** (if needed):
   ```python
   # Custom script to import old data
   # This would need to be implemented based on your needs
   ```

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Development Workflow

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes and add tests
4. Run tests and linting: `pytest && black . && ruff check .`
5. Commit your changes: `git commit -m 'Add amazing feature'`
6. Push to the branch: `git push origin feature/amazing-feature`
7. Open a Pull Request

## 📄 License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

## ⚖️ Disclaimer

This tool is for educational and automation purposes. Users are responsible for:

- Complying with X's Terms of Service
- Respecting rate limits and API guidelines
- Using the tool ethically and responsibly
- Any consequences of automated actions

The authors are not responsible for any misuse or consequences of using this tool.

## 🙏 Acknowledgments

- Original [TwitterFollowBot](https://github.com/rhiever/TwitterFollowBot) by Randal S. Olson
- [Tweepy](https://www.tweepy.org/) for X API integration
- The Python community for excellent libraries and tools

## 📞 Support

- 📖 **Documentation**: [Full documentation](https://github.com/kyroskoh/TwitterFollowBot/wiki)
- 🐛 **Bug Reports**: [GitHub Issues](https://github.com/kyroskoh/TwitterFollowBot/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/kyroskoh/TwitterFollowBot/discussions)
- ⭐ **Star the project** if you find it useful!

---

**X Follow Bot v2.0** - Modern X automation for the modern era 🚀
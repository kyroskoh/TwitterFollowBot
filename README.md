# TwitterFollowBot

A Python bot that automates several actions on X (Twitter), such as following users and favoriting tweets.

## 🚨 Important Update: v2.0 Available!

**TwitterFollowBot v2.0** is now available with full **X API v2 support**! The new version includes:

- ✅ **X API v2 Integration** with OAuth 2.0
- ✅ **Modern Python 3.11+** with async/await
- ✅ **Database Storage** (SQLite/PostgreSQL)
- ✅ **Rich CLI Interface** with progress bars
- ✅ **Docker Support** for easy deployment
- ✅ **Advanced Safety Features** and bot detection
- ✅ **Comprehensive Documentation** and migration guides

### 🚀 Get Started with v2.0

```bash
# Navigate to v2 directory
cd v2

# Install dependencies
pip install -e .

# Create configuration
x-follow-bot config create

# Initialize database
x-follow-bot database init

# Start using the bot
x-follow-bot bot follow --keywords python ai --max-follows 10
```

**📖 Full Documentation**: See [`v2/README.md`](v2/README.md) for complete v2.0 documentation.

**🔄 Migration Guide**: See [`v2/MIGRATION.md`](v2/MIGRATION.md) for migrating from v1.x to v2.0.

---

## v1.x (Legacy Version)

> **⚠️ Notice**: The v1.x version uses deprecated Twitter API v1.1 and is no longer actively maintained. We strongly recommend upgrading to v2.0 for continued functionality and support.

### Legacy Installation

You can still install the legacy version using `pip`:

```bash
pip install TwitterFollowBot
```

### Legacy Dependencies

The legacy version requires Python's [python-twitter](https://github.com/sixohsix/twitter/) library:

```bash
pip install twitter
```

**Note**: This library should be installed automatically if you used `pip` to install TwitterFollowBot.

### Legacy API Setup

You'll need to create an app account on the legacy Twitter Developer portal:

1. Sign in with your Twitter account
2. Create a new app account  
3. Modify the settings for that app account to allow read & write
4. Generate a new OAuth token with those permissions

This will create 4 tokens that you'll need for the legacy configuration.

### Legacy Configuration

Create a `config.txt` file with the following format:

```
OAUTH_TOKEN:your_oauth_token
OAUTH_SECRET:your_oauth_secret
CONSUMER_KEY:your_consumer_key
CONSUMER_SECRET:your_consumer_secret
TWITTER_HANDLE:your_twitter_handle
ALREADY_FOLLOWED_FILE:already-followed.txt
FOLLOWERS_FILE:followers.txt
FOLLOWS_FILE:following.txt
USERS_KEEP_FOLLOWING:
USERS_KEEP_UNMUTED:
USERS_KEEP_MUTED:
FOLLOW_BACKOFF_MIN_SECONDS:10
FOLLOW_BACKOFF_MAX_SECONDS:60
```

### Legacy Usage Examples

```python
from TwitterFollowBot import TwitterBot

# Create bot instance
my_bot = TwitterBot()

# Follow users based on keywords
my_bot.auto_follow("python")
my_bot.auto_follow("#machinelearning")

# Follow followers
my_bot.auto_follow_followers()

# Like tweets
my_bot.auto_fav("artificial intelligence", count=100)

# Retweet
my_bot.auto_rt("#python", count=50)

# Unfollow non-followers
my_bot.auto_unfollow_nonfollowers()

# Post a tweet
my_bot.send_tweet("Hello from TwitterFollowBot!")
```

### Legacy Features

The legacy version supports:

- ✅ Automatically follow users based on keywords/hashtags
- ✅ Follow users who follow you back
- ✅ Follow followers of specific users
- ✅ Automatically favorite/like tweets with specific phrases
- ✅ Automatically retweet tweets with specific phrases
- ✅ Unfollow users who don't follow back
- ✅ Mute/unmute functionality
- ✅ Post tweets
- ✅ Add users to lists
- ✅ Local caching of followers/following

## 🔄 Comparison: v1.x vs v2.0

| Feature | v1.x (Legacy) | v2.0 (Modern) |
|---------|---------------|---------------|
| **API** | Twitter v1.1 (deprecated) | X API v2 (current) |
| **Authentication** | OAuth 1.0a | OAuth 2.0 + PKCE |
| **Python Version** | 2.7/3.3+ | 3.11+ |
| **Performance** | Synchronous | Async/await |
| **Storage** | Text files | Database (SQLite/PostgreSQL) |
| **Configuration** | config.txt | YAML/JSON + validation |
| **CLI** | None | Rich CLI with progress bars |
| **Safety Features** | Basic | Advanced (bot detection, etc.) |
| **Error Handling** | Basic | Comprehensive with retries |
| **Rate Limiting** | Manual | Intelligent with backoff |
| **Monitoring** | None | Built-in analytics |
| **Testing** | None | Comprehensive test suite |
| **Deployment** | Manual setup | Docker ready |
| **Documentation** | Basic | Comprehensive |

## ⚠️ Disclaimer

I hold no liability for what you do with this bot or what happens to you by using this bot. Abusing this bot *can* get you banned from X/Twitter, so make sure to read up on [proper usage](https://help.twitter.com/en/rules-and-policies/twitter-automation) of the X API.

**Important**: Always respect X's Terms of Service and rate limits. Use the bot responsibly and ethically.

## 📋 Recommendations

### For New Users
- **Use v2.0**: Start with the modern v2.0 version for the best experience
- **X API v2**: Get X API v2 credentials from the [X Developer Portal](https://developer.twitter.com/)
- **Read Documentation**: Follow the comprehensive v2.0 documentation

### For Existing Users
- **Upgrade to v2.0**: The legacy version will eventually stop working
- **Migration Guide**: Follow the step-by-step migration guide
- **Backup Data**: Export your existing followers/following data before migrating

## 🆘 Getting Help

### For v2.0 Issues
- 📖 Read the [v2.0 Documentation](v2/README.md)
- 🔄 Check the [Migration Guide](v2/MIGRATION.md)
- 🐛 [File an Issue](https://github.com/kyroskoh/TwitterFollowBot/issues) with the `v2.0` label

### For Legacy v1.x Issues
- 🐛 [File an Issue](https://github.com/kyroskoh/TwitterFollowBot/issues) with the `v1.x` label
- ⚠️ Note: v1.x is in maintenance mode only

**Please check existing issues before creating new ones!**

## 📄 License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

## 🏗️ Project Status

- **v1.x**: Maintenance mode (bug fixes only)
- **v2.0**: Active development and support

## 🙏 Contributing

Contributions are welcome! Please focus on v2.0 development:

1. Fork the repository
2. Work in the `v2/` directory
3. Follow the development guidelines in `v2/README.md`
4. Submit a pull request

---

**TwitterFollowBot** - Automating X (Twitter) interactions since 2015, now modernized for 2025+ 🚀
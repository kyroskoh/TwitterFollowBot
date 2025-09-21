"""
Main CLI interface for X Follow Bot.
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt, Confirm
import structlog

from ..core.config import get_settings, create_sample_config, Settings
from ..services.bot_service import get_bot_service
from ..storage.database import get_database_manager

console = Console()
logger = structlog.get_logger(__name__)


def setup_logging():
    """Setup structured logging."""
    import logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


@click.group()
@click.option('--config', '-c', type=click.Path(exists=True), help='Configuration file path')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
@click.pass_context
def cli(ctx, config: Optional[str], verbose: bool):
    """X Follow Bot v2.0 - Modern X (Twitter) automation bot."""
    
    # Setup logging
    setup_logging()
    
    # Ensure context object exists
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    
    # Load configuration
    try:
        if config:
            settings = Settings.from_yaml(Path(config))
        else:
            settings = get_settings()
        
        ctx.obj['settings'] = settings
        
        if verbose:
            console.print(f"[green]Configuration loaded successfully[/green]")
            
    except Exception as e:
        console.print(f"[red]Error loading configuration: {e}[/red]")
        if not config:
            console.print("[yellow]Try creating a config file with: x-follow-bot config create[/yellow]")
        sys.exit(1)


@cli.group()
def config():
    """Configuration management commands."""
    pass


@config.command('create')
@click.option('--output', '-o', default='config.yaml', help='Output configuration file')
def create_config(output: str):
    """Create a sample configuration file."""
    try:
        create_sample_config(output)
        console.print(f"[green]Sample configuration created: {output}[/green]")
        console.print("[yellow]Please edit the configuration file with your X API credentials[/yellow]")
    except Exception as e:
        console.print(f"[red]Error creating config: {e}[/red]")
        sys.exit(1)


@config.command('validate')
@click.pass_context
def validate_config(ctx):
    """Validate the current configuration."""
    settings: Settings = ctx.obj['settings']
    
    issues = settings.validate_configuration()
    
    if not issues:
        console.print("[green]✓ Configuration is valid[/green]")
    else:
        console.print("[red]Configuration issues found:[/red]")
        for issue in issues:
            console.print(f"  [red]• {issue}[/red]")
        sys.exit(1)


@config.command('show')
@click.pass_context
def show_config(ctx):
    """Show current configuration (sanitized)."""
    settings: Settings = ctx.obj['settings']
    
    # Create a sanitized version
    config_dict = settings.model_dump()
    
    # Remove sensitive data
    if 'x_api' in config_dict:
        config_dict['x_api']['client_secret'] = "***HIDDEN***"
        if config_dict['x_api'].get('bearer_token'):
            config_dict['x_api']['bearer_token'] = "***HIDDEN***"
    
    console.print("[bold]Current Configuration:[/bold]")
    console.print_json(data=config_dict)


@cli.group()
def auth():
    """Authentication management commands."""
    pass


@auth.command('setup')
@click.pass_context
def setup_auth(ctx):
    """Setup OAuth 2.0 authentication."""
    settings: Settings = ctx.obj['settings']
    
    console.print("[bold]Setting up X API v2 Authentication[/bold]")
    console.print()
    console.print("You'll need your X API v2 credentials from https://developer.twitter.com/")
    console.print()
    
    # This would implement the OAuth flow
    # For now, show instructions
    console.print("[yellow]OAuth 2.0 setup would be implemented here[/yellow]")
    console.print("This would:")
    console.print("1. Generate authorization URL")
    console.print("2. Open browser for user authorization") 
    console.print("3. Capture authorization code")
    console.print("4. Exchange for access/refresh tokens")
    console.print("5. Save tokens securely")


@cli.group()
def database():
    """Database management commands."""
    pass


@database.command('init')
@click.pass_context
def init_database(ctx):
    """Initialize the database."""
    settings: Settings = ctx.obj['settings']
    
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Initializing database...", total=None)
            
            db_manager = get_database_manager(settings)
            db_manager.create_tables()
            
            progress.update(task, description="Database initialized successfully")
        
        console.print("[green]✓ Database initialized[/green]")
        
    except Exception as e:
        console.print(f"[red]Error initializing database: {e}[/red]")
        sys.exit(1)


@database.command('status')
@click.pass_context
def database_status(ctx):
    """Show database status and statistics."""
    settings: Settings = ctx.obj['settings']
    
    try:
        db_manager = get_database_manager(settings)
        
        if not db_manager.health_check():
            console.print("[red]✗ Database connection failed[/red]")
            sys.exit(1)
        
        stats = db_manager.get_stats()
        
        table = Table(title="Database Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Count", style="magenta")
        
        table.add_row("Users", str(stats['users_count']))
        table.add_row("Tweets", str(stats['tweets_count']))
        table.add_row("Interactions", str(stats['interactions_count']))
        table.add_row("Sessions", str(stats['sessions_count']))
        table.add_row("Following", str(stats['following_count']))
        table.add_row("Followers", str(stats['followers_count']))
        
        console.print(table)
        console.print("[green]✓ Database is healthy[/green]")
        
    except Exception as e:
        console.print(f"[red]Error checking database: {e}[/red]")
        sys.exit(1)


@cli.group()
def bot():
    """Bot operation commands."""
    pass


@bot.command('status')
@click.pass_context
def bot_status(ctx):
    """Show bot status and statistics."""
    settings: Settings = ctx.obj['settings']
    
    try:
        bot_service = get_bot_service(settings)
        status = bot_service.get_status()
        
        # Create status panel
        status_text = f"""
[bold]Session ID:[/bold] {status['session_id']}
[bold]Status:[/bold] {status['status']}
[bold]Initialized:[/bold] {'✓' if status['initialized'] else '✗'}
[bold]Database:[/bold] {'✓' if status['database_connected'] else '✗'}
[bold]Cache:[/bold] {'✓' if status['cache_enabled'] else '✗'}
"""
        
        console.print(Panel(status_text, title="Bot Status"))
        
        # Show follow stats if available
        if 'follow_stats' in status:
            follow_stats = status['follow_stats']
            
            table = Table(title="Follow Statistics")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="magenta")
            
            table.add_row("Following", str(follow_stats['total_following']))
            table.add_row("Followers", str(follow_stats['total_followers']))
            table.add_row("Follow Ratio", f"{follow_stats['follow_ratio']:.2f}")
            table.add_row("Follows (24h)", str(follow_stats['recent_follows_24h']))
            table.add_row("Unfollows (24h)", str(follow_stats['recent_unfollows_24h']))
            table.add_row("Hourly Limit", f"{follow_stats['hourly_follow_count']}/{follow_stats['hourly_limit']}")
            
            console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error getting bot status: {e}[/red]")
        sys.exit(1)


@bot.command('follow')
@click.option('--keywords', '-k', multiple=True, help='Keywords to search for')
@click.option('--max-follows', '-m', default=10, help='Maximum number of users to follow')
@click.pass_context
def follow_users(ctx, keywords, max_follows):
    """Follow users based on keywords."""
    settings: Settings = ctx.obj['settings']
    
    if not keywords:
        keywords = settings.bot.search_keywords
    
    if not keywords:
        console.print("[red]No keywords specified. Use --keywords or set search_keywords in config[/red]")
        sys.exit(1)
    
    async def run_follow():
        try:
            bot_service = get_bot_service(settings)
            await bot_service.initialize()
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("Following users...", total=None)
                
                result = await bot_service.follow_users_by_keyword(
                    list(keywords), max_follows
                )
                
                progress.update(task, description="Follow operation completed")
            
            # Show results
            console.print(f"[green]Followed {result['total_followed']} users[/green]")
            console.print(f"Skipped: {result['total_skipped']}")
            
            if result['errors']:
                console.print("[red]Errors occurred:[/red]")
                for error in result['errors']:
                    console.print(f"  [red]• {error}[/red]")
            
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            sys.exit(1)
        finally:
            await bot_service.cleanup()
    
    asyncio.run(run_follow())


@bot.command('like')
@click.option('--keywords', '-k', multiple=True, help='Keywords to search for')
@click.option('--max-likes', '-m', default=20, help='Maximum number of tweets to like')
@click.pass_context
def like_tweets(ctx, keywords, max_likes):
    """Like tweets based on keywords."""
    settings: Settings = ctx.obj['settings']
    
    if not keywords:
        keywords = settings.bot.search_keywords
    
    if not keywords:
        console.print("[red]No keywords specified. Use --keywords or set search_keywords in config[/red]")
        sys.exit(1)
    
    async def run_like():
        try:
            bot_service = get_bot_service(settings)
            await bot_service.initialize()
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("Liking tweets...", total=None)
                
                result = await bot_service.like_tweets_by_keyword(
                    list(keywords), max_likes
                )
                
                progress.update(task, description="Like operation completed")
            
            # Show results
            console.print(f"[green]Liked {result['total_liked']} tweets[/green]")
            console.print(f"Skipped: {result['total_skipped']}")
            
            if result['errors']:
                console.print("[red]Errors occurred:[/red]")
                for error in result['errors']:
                    console.print(f"  [red]• {error}[/red]")
            
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            sys.exit(1)
        finally:
            await bot_service.cleanup()
    
    asyncio.run(run_like())


@bot.command('unfollow')
@click.option('--max-unfollows', '-m', default=50, help='Maximum number of users to unfollow')
@click.pass_context
def unfollow_non_followers(ctx, max_unfollows):
    """Unfollow users who don't follow back."""
    settings: Settings = ctx.obj['settings']
    
    if not Confirm.ask("Are you sure you want to unfollow non-followers?"):
        console.print("Operation cancelled.")
        return
    
    async def run_unfollow():
        try:
            bot_service = get_bot_service(settings)
            await bot_service.initialize()
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("Unfollowing non-followers...", total=None)
                
                result = await bot_service.unfollow_non_followers(max_unfollows)
                
                progress.update(task, description="Unfollow operation completed")
            
            # Show results
            console.print(f"[green]Unfollowed {result['total_unfollowed']} users[/green]")
            console.print(f"Kept: {result['total_kept']}")
            
            if result['errors']:
                console.print("[red]Errors occurred:[/red]")
                for error in result['errors']:
                    console.print(f"  [red]• {error}[/red]")
            
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            sys.exit(1)
        finally:
            await bot_service.cleanup()
    
    asyncio.run(run_unfollow())


@bot.command('run')
@click.option('--duration', '-d', type=int, help='Duration in minutes')
@click.option('--actions', '-a', multiple=True, 
              type=click.Choice(['follow', 'like', 'retweet', 'unfollow_cleanup']),
              help='Actions to perform')
@click.pass_context
def run_automated(ctx, duration, actions):
    """Run automated bot session."""
    settings: Settings = ctx.obj['settings']
    
    if not actions:
        actions = ['follow', 'like']
    
    console.print(f"[bold]Starting automated session[/bold]")
    console.print(f"Duration: {duration or 'indefinite'} minutes")
    console.print(f"Actions: {', '.join(actions)}")
    console.print()
    
    if not Confirm.ask("Continue?"):
        console.print("Operation cancelled.")
        return
    
    async def run_session():
        try:
            bot_service = get_bot_service(settings)
            await bot_service.initialize()
            
            result = await bot_service.start_automated_session(
                duration_minutes=duration,
                actions=list(actions)
            )
            
            # Show results
            console.print("[bold]Session completed![/bold]")
            console.print(f"Total actions: {result['total_actions']}")
            console.print(f"Duration: {result.get('total_duration_minutes', 0):.1f} minutes")
            
            if result['actions_performed']:
                table = Table(title="Actions Performed")
                table.add_column("Action", style="cyan")
                table.add_column("Count", style="magenta")
                
                for action, count in result['actions_performed'].items():
                    table.add_row(action.capitalize(), str(count))
                
                console.print(table)
            
            if result['errors']:
                console.print("[red]Errors occurred:[/red]")
                for error in result['errors']:
                    console.print(f"  [red]• {error}[/red]")
            
        except KeyboardInterrupt:
            console.print("\n[yellow]Session interrupted by user[/yellow]")
            bot_service.stop_session()
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            sys.exit(1)
        finally:
            await bot_service.cleanup()
    
    asyncio.run(run_session())


@cli.command('version')
def version():
    """Show version information."""
    from .. import __version__
    console.print(f"X Follow Bot v{__version__}")


def main():
    """Main CLI entry point."""
    try:
        cli()
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation interrupted by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        sys.exit(1)


if __name__ == '__main__':
    main()
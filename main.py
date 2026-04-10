"""
Octobot - Enterprise-grade Discord bot for GitHub integration.
Entry point and bot initialization.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional

import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

from config import BotConfig
from database.manager import DatabaseManager
from utils.cache import CacheManager
from utils.github_client import GitHubClient

load_dotenv()

# ─── Logging Configuration ────────────────────────────────────────────────────

log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_dir / f"octobot_{datetime.utcnow().strftime('%Y%m%d')}.log"),
    ],
)
logger = logging.getLogger("octobot")

# Suppress noisy third-party loggers
logging.getLogger("discord").setLevel(logging.WARNING)
logging.getLogger("discord.http").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("matplotlib").setLevel(logging.WARNING)


# ─── Bot Class ────────────────────────────────────────────────────────────────

class Octobot(commands.Bot):
    """
    Octobot — The enterprise-grade GitHub companion for Discord.

    Provides comprehensive GitHub integration including repository management,
    issue tracking, pull requests, CI/CD monitoring, advanced analytics,
    and rich data visualizations.
    """

    def __init__(self, config: BotConfig) -> None:
        self.config = config
        self.start_time = datetime.utcnow()
        self.db: Optional[DatabaseManager] = None
        self.cache: Optional[CacheManager] = None
        self.github: Optional[GitHubClient] = None
        self._user_github_tokens: dict[int, str] = {}  # Discord user ID -> GitHub token

        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True

        super().__init__(
            command_prefix=commands.when_mentioned_or(*config.prefixes),
            intents=intents,
            help_command=None,
            description="Enterprise-grade GitHub bot for Discord",
            case_insensitive=True,
            strip_after_prefix=True,
            max_messages=10_000,
        )

    # ─── Cog Loading ──────────────────────────────────────────────────────────

    async def load_cogs(self) -> None:
        """Load all extension cogs."""
        cog_modules = [
            "cogs.repository",
            "cogs.issues",
            "cogs.pull_requests",
            "cogs.user",
            "cogs.organization",
            "cogs.gist",
            "cogs.search",
            "cogs.actions",
            "cogs.releases",
            "cogs.visualizations",
            "cogs.notifications",
            "cogs.admin",
            "cogs.help",
        ]
        for module in cog_modules:
            try:
                await self.load_extension(module)
                logger.info(f"Loaded extension: {module}")
            except Exception as exc:
                logger.error(f"Failed to load extension {module}: {exc}")
                traceback.print_exc()

    # ─── Bot Lifecycle ────────────────────────────────────────────────────────

    async def setup_hook(self) -> None:
        """Called when bot is setting up — before on_ready."""
        logger.info("Initializing Octobot services...")

        # Initialize database
        self.db = DatabaseManager(self.config.database_url)
        await self.db.initialize()
        logger.info("Database initialized.")

        # Initialize cache
        self.cache = CacheManager(
            ttl=self.config.cache_ttl,
            max_size=self.config.cache_max_size,
        )
        logger.info("Cache manager initialized.")

        # Initialize GitHub client
        self.github = GitHubClient(
            token=self.config.github_token,
            cache=self.cache,
        )
        logger.info("GitHub client initialized.")

        # Load all cogs
        await self.load_cogs()

        # Sync slash commands
        if self.config.sync_commands:
            logger.info("Syncing application commands...")
            try:
                synced = await self.tree.sync()
                logger.info(f"Synced {len(synced)} global application commands.")
            except Exception as exc:
                logger.error(f"Failed to sync commands: {exc}")

        # Start background tasks
        self.update_presence.start()
        self.cleanup_cache.start()
        logger.info("Background tasks started.")

    async def close(self) -> None:
        """Clean shutdown."""
        logger.info("Shutting down Octobot...")
        self.update_presence.cancel()
        self.cleanup_cache.cancel()

        if self.db:
            await self.db.close()

        if self.github:
            await self.github.close()

        await super().close()
        logger.info("Octobot shut down cleanly.")

    # ─── Events ───────────────────────────────────────────────────────────────

    async def on_ready(self) -> None:
        logger.info(
            f"Octobot ready! Logged in as {self.user} (ID: {self.user.id})\n"
            f"  Guilds: {len(self.guilds)}\n"
            f"  Prefix: {self.config.prefixes}\n"
            f"  Discord.py: {discord.__version__}"
        )

    async def on_guild_join(self, guild: discord.Guild) -> None:
        logger.info(f"Joined guild: {guild.name} (ID: {guild.id}, Members: {guild.member_count})")
        if self.db:
            await self.db.ensure_guild(guild.id, guild.name)

    async def on_guild_remove(self, guild: discord.Guild) -> None:
        logger.info(f"Left guild: {guild.name} (ID: {guild.id})")

    async def on_command(self, ctx: commands.Context) -> None:
        logger.info(
            f"Command: {ctx.command} | User: {ctx.author} ({ctx.author.id}) "
            f"| Guild: {ctx.guild} | Channel: {ctx.channel}"
        )

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        await self._handle_command_error(ctx, error)

    async def on_application_command_error(
        self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError
    ) -> None:
        await self._handle_app_error(interaction, error)

    # ─── Error Handling ───────────────────────────────────────────────────────

    async def _handle_command_error(
        self, ctx: commands.Context, error: commands.CommandError
    ) -> None:
        """Centralized prefix command error handler."""
        if isinstance(error, commands.CommandNotFound):
            return

        embed = discord.Embed(color=discord.Color.red())

        if isinstance(error, commands.MissingRequiredArgument):
            embed.title = "❌ Missing Argument"
            embed.description = (
                f"Required argument `{error.param.name}` is missing.\n"
                f"Use `{ctx.prefix}help {ctx.command}` for usage info."
            )
        elif isinstance(error, commands.BadArgument):
            embed.title = "❌ Invalid Argument"
            embed.description = str(error)
        elif isinstance(error, commands.MissingPermissions):
            embed.title = "🔒 Missing Permissions"
            embed.description = f"You need: `{'`, `'.join(error.missing_permissions)}`"
        elif isinstance(error, commands.BotMissingPermissions):
            embed.title = "🔒 Bot Missing Permissions"
            embed.description = f"I need: `{'`, `'.join(error.missing_permissions)}`"
        elif isinstance(error, commands.CommandOnCooldown):
            embed.title = "⏳ Command on Cooldown"
            embed.description = f"Retry in **{error.retry_after:.1f}s**."
        elif isinstance(error, commands.NotOwner):
            embed.title = "🔒 Owner Only"
            embed.description = "This command is restricted to the bot owner."
        elif isinstance(error, commands.CheckFailure):
            embed.title = "❌ Check Failed"
            embed.description = str(error)
        else:
            embed.title = "⚠️ Unexpected Error"
            embed.description = f"```{type(error).__name__}: {error}```"
            logger.exception(f"Unhandled command error in {ctx.command}:", exc_info=error)

        try:
            await ctx.reply(embed=embed, mention_author=False)
        except discord.HTTPException:
            pass

    async def _handle_app_error(
        self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError
    ) -> None:
        """Centralized slash command error handler."""
        embed = discord.Embed(color=discord.Color.red())

        if isinstance(error, discord.app_commands.CommandOnCooldown):
            embed.title = "⏳ Command on Cooldown"
            embed.description = f"Retry in **{error.retry_after:.1f}s**."
        elif isinstance(error, discord.app_commands.MissingPermissions):
            embed.title = "🔒 Missing Permissions"
            embed.description = f"You need: `{'`, `'.join(error.missing_permissions)}`"
        elif isinstance(error, discord.app_commands.CheckFailure):
            embed.title = "❌ Check Failed"
            embed.description = str(error)
        else:
            embed.title = "⚠️ Unexpected Error"
            embed.description = f"```{type(error).__name__}: {error}```"
            logger.exception(f"Unhandled app command error:", exc_info=error)

        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.HTTPException:
            pass

    # ─── Background Tasks ─────────────────────────────────────────────────────

    @tasks.loop(minutes=15)
    async def update_presence(self) -> None:
        """Cycle through rich presence statuses."""
        import random
        statuses = [
            discord.Activity(type=discord.ActivityType.watching, name="GitHub repositories"),
            discord.Activity(type=discord.ActivityType.listening, name="/help"),
            discord.Activity(type=discord.ActivityType.watching, name="pull requests merge"),
            discord.Activity(type=discord.ActivityType.playing, name="with GitHub API"),
            discord.Activity(type=discord.ActivityType.watching, name=f"{len(self.guilds)} servers"),
        ]
        await self.change_presence(activity=random.choice(statuses))

    @update_presence.before_loop
    async def before_update_presence(self) -> None:
        await self.wait_until_ready()

    @tasks.loop(hours=1)
    async def cleanup_cache(self) -> None:
        """Periodically purge expired cache entries."""
        if self.cache:
            removed = await self.cache.cleanup_expired()
            logger.debug(f"Cache cleanup: removed {removed} expired entries.")

    @cleanup_cache.before_loop
    async def before_cleanup_cache(self) -> None:
        await self.wait_until_ready()

    # ─── Utility Methods ──────────────────────────────────────────────────────

    def get_github_token_for_user(self, user_id: int) -> Optional[str]:
        """Get a user's personal GitHub token if linked."""
        return self._user_github_tokens.get(user_id)

    def set_github_token_for_user(self, user_id: int, token: str) -> None:
        """Link a personal GitHub token to a Discord user."""
        self._user_github_tokens[user_id] = token

    def remove_github_token_for_user(self, user_id: int) -> None:
        """Remove a user's linked GitHub token."""
        self._user_github_tokens.pop(user_id, None)

    def get_github_client_for(self, user_id: int) -> GitHubClient:
        """Return a GitHub client for a specific user (personal token if set)."""
        token = self.get_github_token_for_user(user_id)
        if token:
            return GitHubClient(token=token, cache=self.cache)
        return self.github

    @property
    def uptime(self) -> str:
        """Human-readable uptime string."""
        delta = datetime.utcnow() - self.start_time
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        days, hours = divmod(hours, 24)
        parts = []
        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
        parts.append(f"{seconds}s")
        return " ".join(parts)


# ─── Entry Point ──────────────────────────────────────────────────────────────

async def main() -> None:
    config = BotConfig.from_env()
    bot = Octobot(config)

    try:
        async with bot:
            await bot.start(config.discord_token)
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
    except discord.LoginFailure:
        logger.critical("Invalid Discord token. Check your .env file.")
        sys.exit(1)
    except Exception as exc:
        logger.critical(f"Fatal error: {exc}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

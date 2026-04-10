"""
Octobot Database Manager — Async SQLAlchemy with migration support.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, String, Text,
    BigInteger, JSON, Float, Index, UniqueConstraint, text,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

logger = logging.getLogger(__name__)
Base = declarative_base()


# ─── Models ───────────────────────────────────────────────────────────────────

class Guild(Base):
    __tablename__ = "guilds"

    id = Column(BigInteger, primary_key=True)
    name = Column(String(100))
    github_org = Column(String(100), nullable=True)
    default_repo = Column(String(200), nullable=True)
    notification_channel_id = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    subscriptions = relationship("Subscription", back_populates="guild", cascade="all, delete-orphan")
    user_links = relationship("UserLink", back_populates="guild", cascade="all, delete-orphan")


class UserLink(Base):
    """Maps Discord users to GitHub accounts."""
    __tablename__ = "user_links"
    __table_args__ = (UniqueConstraint("discord_user_id", "guild_id"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    discord_user_id = Column(BigInteger, nullable=False, index=True)
    github_username = Column(String(100), nullable=False)
    guild_id = Column(BigInteger, ForeignKey("guilds.id"), nullable=False)
    access_token_encrypted = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    guild = relationship("Guild", back_populates="user_links")


class Subscription(Base):
    """Tracks repository event subscriptions per guild."""
    __tablename__ = "subscriptions"
    __table_args__ = (UniqueConstraint("guild_id", "owner", "repo", "event_type"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, ForeignKey("guilds.id"), nullable=False)
    channel_id = Column(BigInteger, nullable=False)
    owner = Column(String(100), nullable=False)
    repo = Column(String(100), nullable=False)
    event_type = Column(String(50), nullable=False)  # push, issues, pull_request, release, etc.
    filter_json = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_notified_at = Column(DateTime, nullable=True)

    guild = relationship("Guild", back_populates="subscriptions")


class CachedRepoData(Base):
    """Persistent cache for expensive GitHub API calls."""
    __tablename__ = "cached_repo_data"
    __table_args__ = (Index("ix_cached_repo_key", "cache_key"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    cache_key = Column(String(500), unique=True, nullable=False)
    data_json = Column(JSON, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class CommandLog(Base):
    """Audit log for all commands."""
    __tablename__ = "command_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, nullable=True)
    user_id = Column(BigInteger, nullable=False)
    command_name = Column(String(100), nullable=False)
    args_json = Column(JSON, nullable=True)
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)
    duration_ms = Column(Float, nullable=True)
    executed_at = Column(DateTime, default=datetime.utcnow)


class RepoStat(Base):
    """Historical repository statistics for trend analysis."""
    __tablename__ = "repo_stats"
    __table_args__ = (
        UniqueConstraint("owner", "repo", "recorded_at"),
        Index("ix_repo_stats_owner_repo", "owner", "repo"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner = Column(String(100), nullable=False)
    repo = Column(String(100), nullable=False)
    stars = Column(Integer, default=0)
    forks = Column(Integer, default=0)
    watchers = Column(Integer, default=0)
    open_issues = Column(Integer, default=0)
    size_kb = Column(Integer, default=0)
    recorded_at = Column(DateTime, default=datetime.utcnow)


class GuildSetting(Base):
    """Key-value settings storage per guild."""
    __tablename__ = "guild_settings"
    __table_args__ = (UniqueConstraint("guild_id", "key"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, nullable=False)
    key = Column(String(100), nullable=False)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ─── Database Manager ─────────────────────────────────────────────────────────

class DatabaseManager:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self._engine = None
        self._session_factory: Optional[async_sessionmaker] = None

    async def initialize(self) -> None:
        import os
        os.makedirs("data", exist_ok=True)

        self._engine = create_async_engine(
            self.database_url,
            echo=False,
            pool_pre_ping=True,
        )
        self._session_factory = async_sessionmaker(
            self._engine, expire_on_commit=False, class_=AsyncSession
        )
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created/verified.")

    async def close(self) -> None:
        if self._engine:
            await self._engine.dispose()

    def session(self) -> AsyncSession:
        return self._session_factory()

    # ── Guilds ────────────────────────────────────────────────────────────

    async def ensure_guild(self, guild_id: int, name: str) -> Guild:
        async with self.session() as sess:
            from sqlalchemy import select
            result = await sess.execute(select(Guild).where(Guild.id == guild_id))
            guild = result.scalar_one_or_none()
            if guild is None:
                guild = Guild(id=guild_id, name=name)
                sess.add(guild)
                await sess.commit()
            return guild

    async def get_guild(self, guild_id: int) -> Optional[Guild]:
        async with self.session() as sess:
            from sqlalchemy import select
            result = await sess.execute(select(Guild).where(Guild.id == guild_id))
            return result.scalar_one_or_none()

    async def update_guild_setting(self, guild_id: int, key: str, value: str) -> None:
        async with self.session() as sess:
            from sqlalchemy import select
            result = await sess.execute(
                select(GuildSetting).where(
                    GuildSetting.guild_id == guild_id,
                    GuildSetting.key == key,
                )
            )
            setting = result.scalar_one_or_none()
            if setting:
                setting.value = value
                setting.updated_at = datetime.utcnow()
            else:
                setting = GuildSetting(guild_id=guild_id, key=key, value=value)
                sess.add(setting)
            await sess.commit()

    async def get_guild_setting(self, guild_id: int, key: str) -> Optional[str]:
        async with self.session() as sess:
            from sqlalchemy import select
            result = await sess.execute(
                select(GuildSetting).where(
                    GuildSetting.guild_id == guild_id,
                    GuildSetting.key == key,
                )
            )
            setting = result.scalar_one_or_none()
            return setting.value if setting else None

    # ── User Links ────────────────────────────────────────────────────────

    async def link_user(
        self,
        discord_user_id: int,
        github_username: str,
        guild_id: int,
        token: str = None,
    ) -> UserLink:
        async with self.session() as sess:
            from sqlalchemy import select
            result = await sess.execute(
                select(UserLink).where(
                    UserLink.discord_user_id == discord_user_id,
                    UserLink.guild_id == guild_id,
                )
            )
            link = result.scalar_one_or_none()
            if link:
                link.github_username = github_username
                if token:
                    link.access_token_encrypted = token
                link.updated_at = datetime.utcnow()
            else:
                link = UserLink(
                    discord_user_id=discord_user_id,
                    github_username=github_username,
                    guild_id=guild_id,
                    access_token_encrypted=token,
                )
                sess.add(link)
            await sess.commit()
            return link

    async def get_user_link(
        self, discord_user_id: int, guild_id: int
    ) -> Optional[UserLink]:
        async with self.session() as sess:
            from sqlalchemy import select
            result = await sess.execute(
                select(UserLink).where(
                    UserLink.discord_user_id == discord_user_id,
                    UserLink.guild_id == guild_id,
                )
            )
            return result.scalar_one_or_none()

    async def remove_user_link(self, discord_user_id: int, guild_id: int) -> bool:
        async with self.session() as sess:
            from sqlalchemy import select, delete
            result = await sess.execute(
                delete(UserLink).where(
                    UserLink.discord_user_id == discord_user_id,
                    UserLink.guild_id == guild_id,
                )
            )
            await sess.commit()
            return result.rowcount > 0

    # ── Subscriptions ─────────────────────────────────────────────────────

    async def add_subscription(
        self,
        guild_id: int,
        channel_id: int,
        owner: str,
        repo: str,
        event_type: str,
        filter_data: dict = None,
    ) -> Subscription:
        async with self.session() as sess:
            from sqlalchemy import select
            result = await sess.execute(
                select(Subscription).where(
                    Subscription.guild_id == guild_id,
                    Subscription.owner == owner,
                    Subscription.repo == repo,
                    Subscription.event_type == event_type,
                )
            )
            sub = result.scalar_one_or_none()
            if sub:
                sub.channel_id = channel_id
                sub.is_active = True
                sub.filter_json = filter_data
            else:
                sub = Subscription(
                    guild_id=guild_id,
                    channel_id=channel_id,
                    owner=owner,
                    repo=repo,
                    event_type=event_type,
                    filter_json=filter_data,
                )
                sess.add(sub)
            await sess.commit()
            return sub

    async def remove_subscription(
        self, guild_id: int, owner: str, repo: str, event_type: str
    ) -> bool:
        async with self.session() as sess:
            from sqlalchemy import delete
            result = await sess.execute(
                delete(Subscription).where(
                    Subscription.guild_id == guild_id,
                    Subscription.owner == owner,
                    Subscription.repo == repo,
                    Subscription.event_type == event_type,
                )
            )
            await sess.commit()
            return result.rowcount > 0

    async def get_guild_subscriptions(
        self, guild_id: int
    ) -> List[Subscription]:
        async with self.session() as sess:
            from sqlalchemy import select
            result = await sess.execute(
                select(Subscription).where(
                    Subscription.guild_id == guild_id,
                    Subscription.is_active == True,
                )
            )
            return list(result.scalars().all())

    async def get_all_active_subscriptions(self) -> List[Subscription]:
        async with self.session() as sess:
            from sqlalchemy import select
            result = await sess.execute(
                select(Subscription).where(Subscription.is_active == True)
            )
            return list(result.scalars().all())

    # ── Repo Stats ────────────────────────────────────────────────────────

    async def record_repo_stat(
        self, owner: str, repo: str, stars: int, forks: int,
        watchers: int, open_issues: int, size_kb: int
    ) -> None:
        async with self.session() as sess:
            stat = RepoStat(
                owner=owner, repo=repo, stars=stars, forks=forks,
                watchers=watchers, open_issues=open_issues, size_kb=size_kb,
            )
            sess.add(stat)
            await sess.commit()

    async def get_repo_stats_history(
        self, owner: str, repo: str, limit: int = 30
    ) -> List[RepoStat]:
        async with self.session() as sess:
            from sqlalchemy import select
            result = await sess.execute(
                select(RepoStat)
                .where(RepoStat.owner == owner, RepoStat.repo == repo)
                .order_by(RepoStat.recorded_at.desc())
                .limit(limit)
            )
            return list(reversed(list(result.scalars().all())))

    # ── Command Logging ───────────────────────────────────────────────────

    async def log_command(
        self,
        guild_id: Optional[int],
        user_id: int,
        command_name: str,
        args: dict = None,
        success: bool = True,
        error: str = None,
        duration_ms: float = None,
    ) -> None:
        async with self.session() as sess:
            log = CommandLog(
                guild_id=guild_id,
                user_id=user_id,
                command_name=command_name,
                args_json=args,
                success=success,
                error_message=error,
                duration_ms=duration_ms,
            )
            sess.add(log)
            await sess.commit()

    async def get_command_stats(self, limit: int = 20) -> List[dict]:
        async with self.session() as sess:
            result = await sess.execute(
                text("""
                    SELECT command_name,
                           COUNT(*) as total,
                           SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successes,
                           AVG(duration_ms) as avg_duration
                    FROM command_logs
                    GROUP BY command_name
                    ORDER BY total DESC
                    LIMIT :limit
                """),
                {"limit": limit},
            )
            return [dict(row._mapping) for row in result]

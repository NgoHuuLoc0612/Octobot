"""
Octobot Configuration — All settings sourced from environment variables.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class BotConfig:
    """Central configuration for Octobot."""

    # ── Discord ──────────────────────────────────────────────────────────────
    discord_token: str
    prefixes: List[str] = field(default_factory=lambda: ["!", "oct!"])
    owner_ids: List[int] = field(default_factory=list)
    sync_commands: bool = True
    error_channel_id: Optional[int] = None

    # ── GitHub ───────────────────────────────────────────────────────────────
    github_token: Optional[str] = None
    github_base_url: str = "https://api.github.com"
    github_graphql_url: str = "https://api.github.com/graphql"
    github_rate_limit_buffer: int = 50  # Reserve this many API calls

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///data/octobot.db"

    # ── Cache ────────────────────────────────────────────────────────────────
    cache_ttl: int = 300          # seconds
    cache_max_size: int = 5_000   # entries

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    command_cooldown_rate: int = 3
    command_cooldown_per: float = 10.0

    # ── Visualizations ───────────────────────────────────────────────────────
    viz_output_dir: str = "temp/visualizations"
    viz_dpi: int = 150
    viz_theme: str = "plotly_dark"
    viz_max_data_points: int = 500
    viz_color_scheme: str = "viridis"

    # ── Notifications ────────────────────────────────────────────────────────
    notification_poll_interval: int = 60   # seconds
    webhook_secret: Optional[str] = None
    webhook_port: int = 8080

    # ── Limits ───────────────────────────────────────────────────────────────
    max_results_per_page: int = 10
    max_embed_fields: int = 25
    max_code_preview_lines: int = 30
    max_search_results: int = 100

    # ── Logging ──────────────────────────────────────────────────────────────
    log_level: str = "INFO"
    log_commands: bool = True
    log_errors: bool = True

    @classmethod
    def from_env(cls) -> "BotConfig":
        """Construct configuration from environment variables."""
        discord_token = os.environ.get("DISCORD_TOKEN")
        if not discord_token:
            raise ValueError(
                "DISCORD_TOKEN is required. "
                "Copy .env.example to .env and fill in your credentials."
            )

        raw_owners = os.environ.get("OWNER_IDS", "")
        owner_ids = [
            int(uid.strip())
            for uid in raw_owners.split(",")
            if uid.strip().isdigit()
        ]

        raw_prefixes = os.environ.get("BOT_PREFIXES", "!,oct!")
        prefixes = [p.strip() for p in raw_prefixes.split(",") if p.strip()]

        return cls(
            discord_token=discord_token,
            prefixes=prefixes,
            owner_ids=owner_ids,
            sync_commands=os.environ.get("SYNC_COMMANDS", "true").lower() == "true",
            error_channel_id=_parse_int(os.environ.get("ERROR_CHANNEL_ID")),

            github_token=os.environ.get("GITHUB_TOKEN"),
            github_base_url=os.environ.get("GITHUB_BASE_URL", "https://api.github.com"),
            github_graphql_url=os.environ.get("GITHUB_GRAPHQL_URL", "https://api.github.com/graphql"),
            github_rate_limit_buffer=int(os.environ.get("GITHUB_RATE_LIMIT_BUFFER", "50")),

            database_url=os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///data/octobot.db"),

            cache_ttl=int(os.environ.get("CACHE_TTL", "300")),
            cache_max_size=int(os.environ.get("CACHE_MAX_SIZE", "5000")),

            command_cooldown_rate=int(os.environ.get("COOLDOWN_RATE", "3")),
            command_cooldown_per=float(os.environ.get("COOLDOWN_PER", "10.0")),

            viz_output_dir=os.environ.get("VIZ_OUTPUT_DIR", "temp/visualizations"),
            viz_dpi=int(os.environ.get("VIZ_DPI", "150")),
            viz_theme=os.environ.get("VIZ_THEME", "plotly_dark"),
            viz_max_data_points=int(os.environ.get("VIZ_MAX_DATA_POINTS", "500")),
            viz_color_scheme=os.environ.get("VIZ_COLOR_SCHEME", "viridis"),

            notification_poll_interval=int(os.environ.get("NOTIFICATION_POLL_INTERVAL", "60")),
            webhook_secret=os.environ.get("WEBHOOK_SECRET"),
            webhook_port=int(os.environ.get("WEBHOOK_PORT", "8080")),

            max_results_per_page=int(os.environ.get("MAX_RESULTS_PER_PAGE", "10")),
            max_embed_fields=int(os.environ.get("MAX_EMBED_FIELDS", "25")),
            max_code_preview_lines=int(os.environ.get("MAX_CODE_PREVIEW_LINES", "30")),
            max_search_results=int(os.environ.get("MAX_SEARCH_RESULTS", "100")),

            log_level=os.environ.get("LOG_LEVEL", "INFO"),
            log_commands=os.environ.get("LOG_COMMANDS", "true").lower() == "true",
            log_errors=os.environ.get("LOG_ERRORS", "true").lower() == "true",
        )


def _parse_int(value: Optional[str]) -> Optional[int]:
    if value and value.strip().isdigit():
        return int(value.strip())
    return None


# ── Color constants used across embeds ────────────────────────────────────────

class Colors:
    PRIMARY      = 0x238636   # GitHub green
    SECONDARY    = 0x1F6FEB   # GitHub blue
    SUCCESS      = 0x2EA44F   # Merge green
    DANGER       = 0xCF222E   # Error red
    WARNING      = 0xD29922   # Yellow/warning
    INFO         = 0x0D1117   # Dark background
    PURPLE       = 0x8957E5   # Purple accent
    PINK         = 0xDB61A2   # Pink accent
    ORANGE       = 0xE16F24   # Orange accent
    NEUTRAL      = 0x30363D   # Neutral gray

    OPEN         = 0x238636   # Open issue/PR
    CLOSED       = 0xCF222E   # Closed issue
    MERGED       = 0x8957E5   # Merged PR
    DRAFT        = 0x848D97   # Draft PR
    PENDING      = 0xD29922   # Pending check


# ── Emoji constants ────────────────────────────────────────────────────────────

class Emojis:
    GITHUB       = "🐙"
    REPO         = "📁"
    BRANCH       = "🌿"
    COMMIT       = "📝"
    ISSUE_OPEN   = "🟢"
    ISSUE_CLOSED = "🔴"
    PR_OPEN      = "🔵"
    PR_MERGED    = "🟣"
    PR_DRAFT     = "⚪"
    STAR         = "⭐"
    FORK         = "🍴"
    WATCH        = "👁️"
    TAG          = "🏷️"
    RELEASE      = "🚀"
    ACTION       = "⚡"
    WORKFLOW     = "🔄"
    SUCCESS      = "✅"
    FAILURE      = "❌"
    PENDING      = "⏳"
    WARNING      = "⚠️"
    INFO         = "ℹ️"
    USER         = "👤"
    ORG          = "🏢"
    GIST         = "📋"
    CODE         = "💻"
    SEARCH       = "🔍"
    CHART        = "📊"
    NETWORK      = "🌐"
    SHIELD       = "🛡️"
    KEY          = "🔑"
    LOCK         = "🔒"
    CLOCK        = "🕐"
    FIRE         = "🔥"
    TRENDING     = "📈"
    DOWN         = "📉"
    LANGUAGE     = "🗣️"
    LICENSE      = "📄"
    WEBHOOK      = "🔗"
    BOT          = "🤖"
    BELL         = "🔔"
    MUTE         = "🔕"
    LOADING      = "⌛"
    LINK         = "🔗"
    HOME         = "🏠"
    SETTINGS     = "⚙️"
    TRASH        = "🗑️"
    EDIT         = "✏️"
    PLUS         = "➕"
    MINUS        = "➖"
    CHECK        = "✔️"
    CROSS        = "✖️"
    ARROW_RIGHT  = "→"
    ARROW_UP     = "↑"
    ARROW_DOWN   = "↓"
    GRAPH        = "📈"
    PIE          = "🥧"
    MAP          = "🗺️"
    PALETTE      = "🎨"
    TREE         = "🌳"
    CLOUD        = "☁️"
    SANKEY       = "〰️"
    THREE_D      = "🧊"
    BUBBLE       = "🫧"
    SCATTER      = "✦"
    HEATMAP      = "🌡️"
    TIMELINE     = "📅"

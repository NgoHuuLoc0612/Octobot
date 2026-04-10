"""
Octobot Helpers & Formatters — Utility functions used across all cogs.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional, Tuple


# ─── Parsing ──────────────────────────────────────────────────────────────────

def parse_repo(repo_str: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse 'owner/repo' or just 'repo' (returns None owner).
    Returns (owner, repo) or (None, None) on invalid input.
    """
    repo_str = repo_str.strip()
    if "/" in repo_str:
        parts = repo_str.split("/", 1)
        if len(parts) == 2 and all(parts):
            return parts[0], parts[1]
    return None, None


def parse_owner_repo(value: str, default_owner: str = None) -> Tuple[str, str]:
    """
    Parse 'owner/repo' string. Raises ValueError on invalid input.
    """
    owner, repo = parse_repo(value)
    if not owner:
        if default_owner:
            return default_owner, value
        raise ValueError(
            f"Invalid repository format `{value}`. Use `owner/repo` format."
        )
    return owner, repo


def is_valid_repo_format(value: str) -> bool:
    """Check if string is a valid 'owner/repo' format."""
    pattern = r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$"
    return bool(re.match(pattern, value.strip()))


# ─── Formatting ───────────────────────────────────────────────────────────────

def fmt_bytes(n: int) -> str:
    """Format bytes to human-readable string."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def fmt_number(n: int) -> str:
    """Format large numbers with K/M suffixes."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def fmt_duration(seconds: float) -> str:
    """Format duration in seconds to human-readable string."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes, secs = divmod(int(seconds), 60)
    if minutes < 60:
        return f"{minutes}m {secs}s"
    hours, mins = divmod(minutes, 60)
    return f"{hours}h {mins}m {secs}s"


def fmt_timedelta(td: timedelta) -> str:
    total_seconds = int(td.total_seconds())
    periods = [
        ("year", 60 * 60 * 24 * 365),
        ("month", 60 * 60 * 24 * 30),
        ("day", 60 * 60 * 24),
        ("hour", 60 * 60),
        ("minute", 60),
        ("second", 1),
    ]
    for period_name, period_seconds in periods:
        if total_seconds >= period_seconds:
            period_value = total_seconds // period_seconds
            plural = "s" if period_value > 1 else ""
            return f"{period_value} {period_name}{plural} ago"
    return "just now"


def fmt_iso_date(iso_str: str, style: str = "R") -> str:
    """Format ISO date string as Discord timestamp."""
    if not iso_str:
        return "N/A"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return f"<t:{int(dt.timestamp())}:{style}>"
    except (ValueError, TypeError):
        return iso_str[:10]


def truncate(text: str, max_len: int = 200, suffix: str = "…") -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - len(suffix)] + suffix


def code_block(text: str, lang: str = "") -> str:
    return f"```{lang}\n{text}\n```"


def inline_code(text: str) -> str:
    return f"`{text}`"


def hyperlink(text: str, url: str) -> str:
    return f"[{text}]({url})"


def progress_bar(current: int, total: int, length: int = 10, filled: str = "█", empty: str = "░") -> str:
    if total == 0:
        return empty * length
    filled_count = round(current / total * length)
    return filled * filled_count + empty * (length - filled_count)


# ─── Language Colors ─────────────────────────────────────────────────────────

LANGUAGE_COLORS: dict[str, str] = {
    "Python": "#3572A5",
    "JavaScript": "#f1e05a",
    "TypeScript": "#2b7489",
    "Java": "#b07219",
    "Go": "#00ADD8",
    "Rust": "#dea584",
    "C++": "#f34b7d",
    "C#": "#178600",
    "C": "#555555",
    "PHP": "#4F5D95",
    "Ruby": "#701516",
    "Swift": "#F05138",
    "Kotlin": "#A97BFF",
    "Dart": "#00B4AB",
    "Scala": "#c22d40",
    "R": "#198CE7",
    "MATLAB": "#e16737",
    "Shell": "#89e051",
    "PowerShell": "#012456",
    "Haskell": "#5e5086",
    "Lua": "#000080",
    "Elixir": "#6e4a7e",
    "Erlang": "#B83998",
    "Clojure": "#db5855",
    "OCaml": "#3be133",
    "Julia": "#a270ba",
    "Perl": "#0298c3",
    "HTML": "#e34c26",
    "CSS": "#563d7c",
    "Vue": "#41b883",
    "Svelte": "#ff3e00",
}


def get_language_color(language: str) -> str:
    return LANGUAGE_COLORS.get(language, "#586069")


# ─── Repo/User Utilities ──────────────────────────────────────────────────────

def state_emoji(state: str, is_pr: bool = False, is_merged: bool = False) -> str:
    if is_merged:
        return "🟣"
    if state == "open":
        return "🟢" if not is_pr else "🔵"
    return "🔴"


def workflow_status_emoji(status: str, conclusion: str = None) -> str:
    key = conclusion or status
    return {
        "success": "✅",
        "failure": "❌",
        "cancelled": "⛔",
        "skipped": "⏭️",
        "timed_out": "⌛",
        "action_required": "⚠️",
        "in_progress": "🔄",
        "queued": "⏳",
        "waiting": "⏳",
        "neutral": "⬜",
    }.get(key, "❓")


def label_badge(label: dict) -> str:
    """Format a GitHub label as a badge string."""
    return f"`{label.get('name', 'label')}`"


# ─── Text Processing ─────────────────────────────────────────────────────────

def extract_mentions(text: str) -> List[str]:
    """Extract GitHub @mentions from text."""
    return re.findall(r"@([A-Za-z0-9\-]+)", text)


def extract_issue_refs(text: str) -> List[int]:
    """Extract issue/PR references from text."""
    return [int(n) for n in re.findall(r"#(\d+)", text)]


def sanitize_markdown(text: str) -> str:
    """Escape Discord markdown special characters."""
    chars = r"\*_`~|>"
    return re.sub(f"([{re.escape(chars)}])", r"\\\1", text)


def clean_body(text: Optional[str], max_len: int = 300) -> str:
    """Clean and truncate a GitHub body text."""
    if not text:
        return "*No description provided.*"
    # Remove HTML comments
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    # Collapse excessive newlines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return truncate(text.strip(), max_len)


# ─── Stats Helpers ────────────────────────────────────────────────────────────

def pct(part: int, total: int, decimals: int = 1) -> str:
    if total == 0:
        return "0%"
    return f"{part / total * 100:.{decimals}f}%"


def compute_language_percentages(languages: dict) -> List[Tuple[str, int, float]]:
    """Returns list of (language, bytes, percentage) sorted by bytes."""
    total = sum(languages.values())
    if total == 0:
        return []
    return sorted(
        [
            (lang, size, round(size / total * 100, 1))
            for lang, size in languages.items()
        ],
        key=lambda x: x[1],
        reverse=True,
    )


def aggregate_commit_activity(weeks: List[dict]) -> dict:
    """Aggregate weekly commit stats into monthly and yearly totals."""
    monthly: dict[str, int] = {}
    yearly_total = 0

    for week in weeks:
        ts = week.get("week", 0)
        count = week.get("total", 0)
        yearly_total += count
        if ts:
            dt = datetime.utcfromtimestamp(ts)
            month_key = dt.strftime("%Y-%m")
            monthly[month_key] = monthly.get(month_key, 0) + count

    return {"monthly": monthly, "total": yearly_total}

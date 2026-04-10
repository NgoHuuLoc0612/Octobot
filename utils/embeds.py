"""
Octobot Embed Builders — Rich Discord embeds for every GitHub entity type.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

import discord

from config import Colors, Emojis


def _fmt_date(iso_str: Optional[str]) -> str:
    if not iso_str:
        return "N/A"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return f"<t:{int(dt.timestamp())}:R>"
    except Exception:
        return iso_str[:10]


def _fmt_date_full(iso_str: Optional[str]) -> str:
    if not iso_str:
        return "N/A"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return f"<t:{int(dt.timestamp())}:F>"
    except Exception:
        return iso_str[:10]


def _num(n: Optional[int]) -> str:
    if n is None:
        return "0"
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}k"
    return str(n)


def _truncate(s: str, length: int = 200) -> str:
    return s[:length] + "…" if len(s) > length else s


def _yes_no(val: bool) -> str:
    return "Yes" if val else "No"


def _visibility(is_private: bool, is_fork: bool = False) -> str:
    parts = ["🔒 Private" if is_private else "🌍 Public"]
    if is_fork:
        parts.append("🍴 Fork")
    return " · ".join(parts)


# ─── Repository Embed ─────────────────────────────────────────────────────────

def build_repo_embed(data: dict) -> discord.Embed:
    owner = data.get("owner", {})
    name = data.get("full_name", "Unknown")
    desc = data.get("description") or "No description provided."
    url = data.get("html_url", "")

    embed = discord.Embed(
        title=f"{Emojis.REPO} {name}",
        url=url,
        description=_truncate(desc, 300),
        color=Colors.PRIMARY,
    )
    embed.set_thumbnail(url=owner.get("avatar_url", ""))

    # Main metrics
    embed.add_field(
        name="📊 Statistics",
        value=(
            f"{Emojis.STAR} **Stars:** {_num(data.get('stargazers_count', 0))}\n"
            f"{Emojis.FORK} **Forks:** {_num(data.get('forks_count', 0))}\n"
            f"{Emojis.WATCH} **Watchers:** {_num(data.get('watchers_count', 0))}\n"
            f"{Emojis.ISSUE_OPEN} **Open Issues:** {_num(data.get('open_issues_count', 0))}"
        ),
        inline=True,
    )

    # Details
    lang = data.get("language") or "None"
    size_kb = data.get("size", 0)
    size_str = f"{size_kb / 1024:.1f} MB" if size_kb >= 1024 else f"{size_kb} KB"
    embed.add_field(
        name="ℹ️ Details",
        value=(
            f"{Emojis.LANGUAGE} **Language:** {lang}\n"
            f"💾 **Size:** {size_str}\n"
            f"{Emojis.LICENSE} **License:** {data.get('license', {}).get('spdx_id', 'None') if data.get('license') else 'None'}\n"
            f"🔍 **Visibility:** {'Private' if data.get('is_private') or data.get('private') else 'Public'}"
        ),
        inline=True,
    )

    # Dates
    embed.add_field(
        name="📅 Timeline",
        value=(
            f"**Created:** {_fmt_date(data.get('created_at'))}\n"
            f"**Updated:** {_fmt_date(data.get('updated_at'))}\n"
            f"**Pushed:** {_fmt_date(data.get('pushed_at'))}"
        ),
        inline=True,
    )

    # Topics
    topics = data.get("topics", [])
    if topics:
        embed.add_field(
            name=f"{Emojis.TAG} Topics",
            value=" ".join(f"`{t}`" for t in topics[:15]),
            inline=False,
        )

    # Flags
    flags = []
    if data.get("fork"):
        flags.append("🍴 Fork")
    if data.get("archived"):
        flags.append("📦 Archived")
    if data.get("disabled"):
        flags.append("⛔ Disabled")
    if data.get("template_repository"):
        flags.append("📑 Template")
    if data.get("has_wiki"):
        flags.append("📖 Wiki")
    if data.get("has_pages"):
        flags.append("🌐 Pages")
    if data.get("has_discussions"):
        flags.append("💬 Discussions")
    if flags:
        embed.add_field(name="🏷️ Flags", value=" · ".join(flags), inline=False)

    embed.set_footer(text=f"ID: {data.get('id')} · Default branch: {data.get('default_branch', 'main')}")
    return embed


# ─── User Embed ───────────────────────────────────────────────────────────────

def build_user_embed(data: dict) -> discord.Embed:
    name = data.get("name") or data.get("login", "Unknown")
    login = data.get("login", "")
    bio = data.get("bio") or "No bio provided."
    url = data.get("html_url", "")

    embed = discord.Embed(
        title=f"{Emojis.USER} {name}",
        url=url,
        description=_truncate(bio, 300),
        color=Colors.SECONDARY,
    )
    embed.set_thumbnail(url=data.get("avatar_url", ""))

    embed.add_field(
        name="📊 Stats",
        value=(
            f"📁 **Repos:** {_num(data.get('public_repos', 0))}\n"
            f"👥 **Followers:** {_num(data.get('followers', 0))}\n"
            f"👤 **Following:** {_num(data.get('following', 0))}\n"
            f"{Emojis.GIST} **Public Gists:** {_num(data.get('public_gists', 0))}"
        ),
        inline=True,
    )

    details = []
    if data.get("company"):
        details.append(f"🏢 **Company:** {data['company']}")
    if data.get("location"):
        details.append(f"📍 **Location:** {data['location']}")
    if data.get("email"):
        details.append(f"📧 **Email:** {data['email']}")
    if data.get("blog"):
        blog = data["blog"]
        if not blog.startswith("http"):
            blog = f"https://{blog}"
        details.append(f"🔗 **Website:** [Link]({blog})")
    if data.get("twitter_username"):
        details.append(f"🐦 **Twitter:** @{data['twitter_username']}")

    if details:
        embed.add_field(name="ℹ️ Info", value="\n".join(details), inline=True)

    embed.add_field(
        name="📅 Timeline",
        value=(
            f"**Joined:** {_fmt_date(data.get('created_at'))}\n"
            f"**Updated:** {_fmt_date(data.get('updated_at'))}"
        ),
        inline=True,
    )

    type_str = "🤖 Bot" if data.get("type") == "Bot" else "👤 User"
    if data.get("site_admin"):
        type_str += " · 🛡️ Site Admin"
    if data.get("hireable"):
        type_str += " · 💼 Hireable"

    embed.set_footer(text=f"Login: @{login} · {type_str} · ID: {data.get('id')}")
    return embed


# ─── Organization Embed ───────────────────────────────────────────────────────

def build_org_embed(data: dict) -> discord.Embed:
    name = data.get("name") or data.get("login", "Unknown")
    desc = data.get("description") or "No description."
    url = data.get("html_url", "")

    embed = discord.Embed(
        title=f"{Emojis.ORG} {name}",
        url=url,
        description=_truncate(desc, 300),
        color=Colors.PURPLE,
    )
    embed.set_thumbnail(url=data.get("avatar_url", ""))

    embed.add_field(
        name="📊 Stats",
        value=(
            f"📁 **Public Repos:** {_num(data.get('public_repos', 0))}\n"
            f"👥 **Members:** {_num(data.get('members_count', 0))}\n"
            f"👥 **Followers:** {_num(data.get('followers', 0))}\n"
            f"📦 **Packages:** {_num(data.get('packages', 0))}"
        ),
        inline=True,
    )

    details = []
    if data.get("location"):
        details.append(f"📍 {data['location']}")
    if data.get("email"):
        details.append(f"📧 {data['email']}")
    if data.get("blog"):
        details.append(f"🔗 [Website]({data['blog']})")
    if data.get("twitter_username"):
        details.append(f"🐦 @{data['twitter_username']}")

    if details:
        embed.add_field(name="ℹ️ Info", value="\n".join(details), inline=True)

    embed.add_field(
        name="📅 Timeline",
        value=(
            f"**Created:** {_fmt_date(data.get('created_at'))}\n"
            f"**Updated:** {_fmt_date(data.get('updated_at'))}"
        ),
        inline=True,
    )

    embed.set_footer(text=f"Login: @{data.get('login')} · ID: {data.get('id')}")
    return embed


# ─── Issue Embed ──────────────────────────────────────────────────────────────

def build_issue_embed(data: dict, owner: str = None, repo: str = None) -> discord.Embed:
    state = data.get("state", "open")
    is_pr = "pull_request" in data
    title_prefix = f"{Emojis.PR_OPEN if is_pr else Emojis.ISSUE_OPEN} " if state == "open" else f"{Emojis.ISSUE_CLOSED} "
    color = Colors.OPEN if state == "open" else Colors.CLOSED

    embed = discord.Embed(
        title=f"{title_prefix}#{data.get('number')} {_truncate(data.get('title', 'No Title'), 200)}",
        url=data.get("html_url", ""),
        color=color,
    )

    body = data.get("body") or "No description."
    embed.description = _truncate(body, 400)

    user = data.get("user", {})
    embed.set_author(
        name=user.get("login", "Unknown"),
        url=user.get("html_url", ""),
        icon_url=user.get("avatar_url", ""),
    )

    # Labels
    labels = data.get("labels", [])
    if labels:
        label_str = " ".join(f"`{lbl['name']}`" for lbl in labels[:10])
        embed.add_field(name=f"{Emojis.TAG} Labels", value=label_str, inline=True)

    # Assignees
    assignees = data.get("assignees", [])
    if assignees:
        embed.add_field(
            name="👤 Assignees",
            value=", ".join(f"[@{a['login']}]({a['html_url']})" for a in assignees[:5]),
            inline=True,
        )

    # Milestone
    milestone = data.get("milestone")
    if milestone:
        embed.add_field(
            name="🏁 Milestone",
            value=f"[{milestone['title']}]({milestone['html_url']})",
            inline=True,
        )

    embed.add_field(
        name="📅 Timeline",
        value=(
            f"**Opened:** {_fmt_date(data.get('created_at'))}\n"
            f"**Updated:** {_fmt_date(data.get('updated_at'))}"
            + (f"\n**Closed:** {_fmt_date(data.get('closed_at'))}" if data.get("closed_at") else "")
        ),
        inline=True,
    )

    embed.add_field(
        name="💬 Activity",
        value=(
            f"**Comments:** {data.get('comments', 0)}\n"
            f"**Reactions:** {data.get('reactions', {}).get('total_count', 0)}"
        ),
        inline=True,
    )

    if owner and repo:
        embed.set_footer(text=f"{owner}/{repo} · State: {state.capitalize()}")
    return embed


# ─── Pull Request Embed ───────────────────────────────────────────────────────

def build_pr_embed(data: dict, owner: str = None, repo: str = None) -> discord.Embed:
    state = data.get("state", "open")
    is_merged = data.get("merged", False)
    is_draft = data.get("draft", False)

    if is_merged:
        color = Colors.MERGED
        state_emoji = Emojis.PR_MERGED
        state_label = "Merged"
    elif is_draft:
        color = Colors.DRAFT
        state_emoji = Emojis.PR_DRAFT
        state_label = "Draft"
    elif state == "open":
        color = Colors.OPEN
        state_emoji = Emojis.PR_OPEN
        state_label = "Open"
    else:
        color = Colors.CLOSED
        state_emoji = Emojis.ISSUE_CLOSED
        state_label = "Closed"

    embed = discord.Embed(
        title=f"{state_emoji} PR #{data.get('number')}: {_truncate(data.get('title', 'No Title'), 180)}",
        url=data.get("html_url", ""),
        description=_truncate(data.get("body") or "No description.", 400),
        color=color,
    )

    user = data.get("user", {})
    embed.set_author(
        name=user.get("login", "Unknown"),
        url=user.get("html_url", ""),
        icon_url=user.get("avatar_url", ""),
    )

    # Branch info
    head = data.get("head", {})
    base = data.get("base", {})
    embed.add_field(
        name=f"{Emojis.BRANCH} Branches",
        value=f"`{head.get('label', '?')}` → `{base.get('label', '?')}`",
        inline=True,
    )

    # Diff stats
    embed.add_field(
        name="📝 Changes",
        value=(
            f"📄 **Files:** {data.get('changed_files', 0)}\n"
            f"➕ **Additions:** {data.get('additions', 0)}\n"
            f"➖ **Deletions:** {data.get('deletions', 0)}\n"
            f"📝 **Commits:** {data.get('commits', 0)}"
        ),
        inline=True,
    )

    # Review state
    embed.add_field(
        name="👀 Review",
        value=(
            f"**Reviews:** {data.get('review_comments', 0)} comments\n"
            f"**Mergeable:** {data.get('mergeable_state', 'unknown').capitalize()}"
        ),
        inline=True,
    )

    # Assignees & reviewers
    assignees = data.get("assignees", [])
    if assignees:
        embed.add_field(
            name="👤 Assignees",
            value=", ".join(f"@{a['login']}" for a in assignees[:5]),
            inline=True,
        )

    reviewers = data.get("requested_reviewers", [])
    if reviewers:
        embed.add_field(
            name="🔍 Requested Reviewers",
            value=", ".join(f"@{r['login']}" for r in reviewers[:5]),
            inline=True,
        )

    labels = data.get("labels", [])
    if labels:
        embed.add_field(
            name=f"{Emojis.TAG} Labels",
            value=" ".join(f"`{lbl['name']}`" for lbl in labels[:10]),
            inline=False,
        )

    embed.add_field(
        name="📅 Timeline",
        value=(
            f"**Opened:** {_fmt_date(data.get('created_at'))}\n"
            f"**Updated:** {_fmt_date(data.get('updated_at'))}"
            + (f"\n**Merged:** {_fmt_date(data.get('merged_at'))}" if is_merged else "")
            + (f"\n**Closed:** {_fmt_date(data.get('closed_at'))}" if data.get("closed_at") and not is_merged else "")
        ),
        inline=True,
    )

    if owner and repo:
        embed.set_footer(text=f"{owner}/{repo} · {state_label}")
    return embed


# ─── Commit Embed ─────────────────────────────────────────────────────────────

def build_commit_embed(data: dict, owner: str = None, repo: str = None) -> discord.Embed:
    commit = data.get("commit", {})
    author = commit.get("author", {})
    committer = commit.get("committer", {})
    gh_author = data.get("author") or {}
    message = commit.get("message", "No message")
    title_line = message.split("\n")[0]

    embed = discord.Embed(
        title=f"{Emojis.COMMIT} {_truncate(title_line, 200)}",
        url=data.get("html_url", ""),
        color=Colors.NEUTRAL,
    )

    if gh_author.get("avatar_url"):
        embed.set_author(
            name=author.get("name", "Unknown"),
            url=gh_author.get("html_url", ""),
            icon_url=gh_author.get("avatar_url", ""),
        )
    else:
        embed.set_author(name=author.get("name", "Unknown"))

    sha = data.get("sha", "")[:7]
    embed.add_field(name="🔑 SHA", value=f"`{sha}`", inline=True)
    embed.add_field(
        name="📅 Date",
        value=_fmt_date(author.get("date")),
        inline=True,
    )

    stats = data.get("stats", {})
    if stats:
        embed.add_field(
            name="📊 Stats",
            value=(
                f"➕ +{stats.get('additions', 0)} "
                f"➖ -{stats.get('deletions', 0)} "
                f"📄 {stats.get('total', 0)} changes"
            ),
            inline=True,
        )

    files = data.get("files", [])
    if files:
        file_lines = [
            f"`{f.get('filename', 'N/A')}` (+{f.get('additions', 0)}/-{f.get('deletions', 0)})"
            for f in files[:8]
        ]
        embed.add_field(
            name=f"📄 Files Changed ({len(files)})",
            value="\n".join(file_lines),
            inline=False,
        )

    if owner and repo:
        embed.set_footer(text=f"{owner}/{repo}")
    return embed


# ─── Release Embed ────────────────────────────────────────────────────────────

def build_release_embed(data: dict, owner: str = None, repo: str = None) -> discord.Embed:
    is_prerelease = data.get("prerelease", False)
    is_draft = data.get("draft", False)
    color = Colors.WARNING if is_prerelease or is_draft else Colors.SUCCESS

    embed = discord.Embed(
        title=f"{Emojis.RELEASE} {data.get('name') or data.get('tag_name', 'Release')}",
        url=data.get("html_url", ""),
        description=_truncate(data.get("body") or "No release notes.", 800),
        color=color,
    )

    author = data.get("author", {})
    embed.set_author(
        name=author.get("login", "Unknown"),
        url=author.get("html_url", ""),
        icon_url=author.get("avatar_url", ""),
    )

    embed.add_field(name=f"{Emojis.TAG} Tag", value=f"`{data.get('tag_name')}`", inline=True)
    embed.add_field(
        name="📋 Type",
        value=(
            "📦 Draft" if is_draft else
            "🔶 Pre-release" if is_prerelease else
            "✅ Full Release"
        ),
        inline=True,
    )
    embed.add_field(
        name="📅 Published",
        value=_fmt_date(data.get("published_at")),
        inline=True,
    )

    assets = data.get("assets", [])
    if assets:
        asset_lines = [
            f"[{a['name']}]({a['browser_download_url']}) — {a.get('download_count', 0)} downloads"
            for a in assets[:6]
        ]
        embed.add_field(
            name=f"📦 Assets ({len(assets)})",
            value="\n".join(asset_lines),
            inline=False,
        )

    if owner and repo:
        embed.set_footer(text=f"{owner}/{repo}")
    return embed


# ─── Workflow Run Embed ───────────────────────────────────────────────────────

def build_workflow_run_embed(data: dict, owner: str = None, repo: str = None) -> discord.Embed:
    conclusion = data.get("conclusion")
    status = data.get("status", "queued")

    color_map = {
        "success": Colors.SUCCESS,
        "failure": Colors.DANGER,
        "cancelled": Colors.NEUTRAL,
        "skipped": Colors.NEUTRAL,
        "timed_out": Colors.WARNING,
        "action_required": Colors.WARNING,
        "neutral": Colors.NEUTRAL,
    }
    color = color_map.get(conclusion or status, Colors.INFO)

    emoji_map = {
        "success": "✅",
        "failure": "❌",
        "cancelled": "⛔",
        "skipped": "⏭️",
        "timed_out": "⌛",
        "action_required": "⚠️",
        "in_progress": "🔄",
        "queued": "⏳",
        "waiting": "⏳",
    }
    state_emoji = emoji_map.get(conclusion or status, "❓")

    embed = discord.Embed(
        title=f"{state_emoji} {data.get('display_title', data.get('name', 'Workflow Run'))}",
        url=data.get("html_url", ""),
        color=color,
    )

    embed.add_field(name="🔄 Workflow", value=data.get("name", "N/A"), inline=True)
    embed.add_field(
        name="📋 Status",
        value=f"{status.replace('_', ' ').title()}"
        + (f" → **{conclusion.title()}**" if conclusion else ""),
        inline=True,
    )
    embed.add_field(
        name=f"{Emojis.BRANCH} Branch",
        value=f"`{data.get('head_branch', 'N/A')}`",
        inline=True,
    )
    embed.add_field(
        name="🎯 Event",
        value=data.get("event", "N/A").replace("_", " ").title(),
        inline=True,
    )
    embed.add_field(
        name="🔑 Commit",
        value=f"`{(data.get('head_sha') or 'N/A')[:7]}`",
        inline=True,
    )
    embed.add_field(name="#️⃣ Run", value=f"#{data.get('run_number', '?')}", inline=True)
    embed.add_field(
        name="📅 Started",
        value=_fmt_date(data.get("created_at")),
        inline=True,
    )
    embed.add_field(
        name="🏁 Updated",
        value=_fmt_date(data.get("updated_at")),
        inline=True,
    )

    actor = data.get("actor", {})
    if actor:
        embed.set_author(
            name=actor.get("login", "Unknown"),
            url=actor.get("html_url", ""),
            icon_url=actor.get("avatar_url", ""),
        )

    if owner and repo:
        embed.set_footer(text=f"{owner}/{repo} · Run ID: {data.get('id')}")
    return embed


# ─── Gist Embed ───────────────────────────────────────────────────────────────

def build_gist_embed(data: dict) -> discord.Embed:
    desc = data.get("description") or "No description."
    url = data.get("html_url", "")
    files = data.get("files", {})

    embed = discord.Embed(
        title=f"{Emojis.GIST} {_truncate(desc, 120)}",
        url=url,
        color=Colors.SECONDARY,
    )

    owner = data.get("owner", {})
    embed.set_author(
        name=owner.get("login", "Unknown"),
        url=owner.get("html_url", ""),
        icon_url=owner.get("avatar_url", ""),
    )

    embed.add_field(
        name="📄 Files",
        value="\n".join(
            f"`{name}` ({meta.get('language') or 'Unknown'}) — {meta.get('size', 0)} bytes"
            for name, meta in list(files.items())[:8]
        ) or "None",
        inline=False,
    )

    embed.add_field(
        name="📊 Stats",
        value=(
            f"**Comments:** {data.get('comments', 0)}\n"
            f"**Forks:** {len(data.get('forks', []))}\n"
            f"**Files:** {len(files)}"
        ),
        inline=True,
    )

    embed.add_field(
        name="🔒 Visibility",
        value="🔒 Secret" if not data.get("public") else "🌍 Public",
        inline=True,
    )

    embed.add_field(
        name="📅 Timeline",
        value=(
            f"**Created:** {_fmt_date(data.get('created_at'))}\n"
            f"**Updated:** {_fmt_date(data.get('updated_at'))}"
        ),
        inline=True,
    )

    embed.set_footer(text=f"Gist ID: {data.get('id')}")
    return embed


# ─── Generic Error Embed ─────────────────────────────────────────────────────

def build_error_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(
        title=f"❌ {title}",
        description=description,
        color=Colors.DANGER,
    )


def build_success_embed(title: str, description: str = "") -> discord.Embed:
    return discord.Embed(
        title=f"✅ {title}",
        description=description,
        color=Colors.SUCCESS,
    )


def build_info_embed(title: str, description: str = "") -> discord.Embed:
    return discord.Embed(
        title=f"ℹ️ {title}",
        description=description,
        color=Colors.INFO,
    )


def build_loading_embed(message: str = "Fetching data from GitHub...") -> discord.Embed:
    return discord.Embed(
        description=f"{Emojis.LOADING} {message}",
        color=Colors.NEUTRAL,
    )

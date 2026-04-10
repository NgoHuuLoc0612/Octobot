"""
Octobot Issues Cog — Complete GitHub Issues management commands.
"""

from __future__ import annotations

from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from config import Colors, Emojis
from utils.embeds import build_error_embed, build_issue_embed, build_loading_embed
from utils.helpers import clean_body, fmt_iso_date, fmt_number, parse_owner_repo
from utils.pagination import PaginatorView, build_list_embeds, send_paginated
from utils.github_client import GitHubAPIError, NotFound


class IssuesCog(commands.Cog, name="Issues"):
    """Commands for managing and exploring GitHub Issues."""

    def __init__(self, bot) -> None:
        self.bot = bot

    def _gh(self, user_id: int):
        return self.bot.get_github_client_for(user_id)

    # ─── /issues ──────────────────────────────────────────────────────────

    @app_commands.command(name="issues", description="List issues in a repository")
    @app_commands.describe(
        repository="owner/repo",
        state="Filter by state",
        labels="Comma-separated label names",
        assignee="Filter by assignee username",
        sort="Sort field",
        direction="Sort direction",
    )
    @app_commands.choices(
        state=[
            app_commands.Choice(name="Open", value="open"),
            app_commands.Choice(name="Closed", value="closed"),
            app_commands.Choice(name="All", value="all"),
        ],
        sort=[
            app_commands.Choice(name="Created", value="created"),
            app_commands.Choice(name="Updated", value="updated"),
            app_commands.Choice(name="Comments", value="comments"),
        ],
        direction=[
            app_commands.Choice(name="Descending (newest first)", value="desc"),
            app_commands.Choice(name="Ascending (oldest first)", value="asc"),
        ],
    )
    async def issues_list(
        self,
        interaction: discord.Interaction,
        repository: str,
        state: str = "open",
        labels: str = None,
        assignee: str = None,
        sort: str = "created",
        direction: str = "desc",
    ) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))

        try:
            issues = await self._gh(interaction.user.id).get_issues(
                owner, repo,
                state=state,
                labels=labels,
                assignee=assignee,
                sort=sort,
                direction=direction,
                max_results=50,
            )
        except NotFound:
            return await interaction.followup.send(embed=build_error_embed("Not Found", f"`{repository}` not found."))
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        if not issues:
            state_text = state if state != "all" else "any state"
            return await interaction.followup.send(
                embed=discord.Embed(
                    description=f"No {state_text} issues found in `{repository}`.",
                    color=Colors.NEUTRAL,
                )
            )

        state_emoji = {"open": Emojis.ISSUE_OPEN, "closed": Emojis.ISSUE_CLOSED}.get(state, "🔵")

        def fmt_issue(issue: dict, idx: int) -> str:
            num = issue.get("number", 0)
            title = issue.get("title", "No title")[:70]
            s = issue.get("state", "open")
            emoji = Emojis.ISSUE_OPEN if s == "open" else Emojis.ISSUE_CLOSED
            comments = issue.get("comments", 0)
            date = fmt_iso_date(issue.get("created_at"), "d")
            url = issue.get("html_url", "")
            labels_str = " ".join(f"`{l['name']}`" for l in issue.get("labels", [])[:3])
            return (
                f"`{idx:>2}.` {emoji} [**#{num}**]({url}) {title}\n"
                f"       💬 {comments} · {date}"
                + (f"\n       {labels_str}" if labels_str else "")
            )

        title_parts = [f"{state_emoji} Issues — {owner}/{repo}"]
        if labels:
            title_parts.append(f"Labels: {labels}")
        if assignee:
            title_parts.append(f"Assignee: @{assignee}")

        embeds = build_list_embeds(
            title=" · ".join(title_parts),
            items=issues,
            formatter=fmt_issue,
            color=Colors.OPEN if state == "open" else Colors.CLOSED,
            per_page=8,
        )
        await send_paginated(interaction, embeds, interaction.user.id)

    # ─── /issue ───────────────────────────────────────────────────────────

    @app_commands.command(name="issue", description="Show detailed info about a specific issue")
    @app_commands.describe(repository="owner/repo", number="Issue number")
    async def issue_detail(
        self,
        interaction: discord.Interaction,
        repository: str,
        number: int,
    ) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))

        try:
            data = await self._gh(interaction.user.id).get_issue(owner, repo, number)
        except NotFound:
            return await interaction.followup.send(
                embed=build_error_embed("Not Found", f"Issue #{number} not found in `{repository}`.")
            )
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        embed = build_issue_embed(data, owner, repo)
        await interaction.followup.send(embed=embed)

    # ─── /issue-comments ──────────────────────────────────────────────────

    @app_commands.command(name="issue-comments", description="Browse comments on a GitHub issue")
    @app_commands.describe(repository="owner/repo", number="Issue number")
    async def issue_comments(
        self,
        interaction: discord.Interaction,
        repository: str,
        number: int,
    ) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))

        try:
            comments = await self._gh(interaction.user.id).get_issue_comments(owner, repo, number, max_results=30)
        except NotFound:
            return await interaction.followup.send(
                embed=build_error_embed("Not Found", f"Issue #{number} not found in `{repository}`.")
            )
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        if not comments:
            return await interaction.followup.send(
                embed=discord.Embed(description=f"No comments on issue #{number}.", color=Colors.NEUTRAL)
            )

        embeds = []
        for i, comment in enumerate(comments):
            user = comment.get("user", {})
            body = clean_body(comment.get("body", ""), 800)
            embed = discord.Embed(
                description=body,
                color=Colors.SECONDARY,
                url=comment.get("html_url", ""),
            )
            embed.set_author(
                name=f"@{user.get('login', 'unknown')}",
                url=user.get("html_url", ""),
                icon_url=user.get("avatar_url", ""),
            )
            embed.set_footer(
                text=(
                    f"Comment {i+1}/{len(comments)} · "
                    f"Issue #{number} · {owner}/{repo} · "
                    f"{fmt_iso_date(comment.get('created_at'), 'f')}"
                )
            )
            embeds.append(embed)

        await send_paginated(interaction, embeds, interaction.user.id)

    # ─── /labels ──────────────────────────────────────────────────────────

    @app_commands.command(name="labels", description="List all labels in a repository")
    @app_commands.describe(repository="owner/repo")
    async def labels(self, interaction: discord.Interaction, repository: str) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))

        try:
            data = await self._gh(interaction.user.id).get_labels(owner, repo)
        except NotFound:
            return await interaction.followup.send(embed=build_error_embed("Not Found", f"`{repository}` not found."))
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        if not data:
            return await interaction.followup.send(
                embed=discord.Embed(description="No labels found.", color=Colors.NEUTRAL)
            )

        def fmt_label(l: dict, idx: int) -> str:
            name = l.get("name", "?")
            color = l.get("color", "000000")
            desc = l.get("description") or ""
            return f"`{idx:>2}.` 🏷️ **{name}** `#{color}`" + (f"\n       _{desc[:60]}_" if desc else "")

        embeds = build_list_embeds(
            title=f"{Emojis.TAG} Labels — {owner}/{repo}",
            items=data,
            formatter=fmt_label,
            color=Colors.SECONDARY,
            per_page=12,
        )
        await send_paginated(interaction, embeds, interaction.user.id)

    # ─── /milestones ──────────────────────────────────────────────────────

    @app_commands.command(name="milestones", description="List milestones in a repository")
    @app_commands.describe(repository="owner/repo", state="open or closed")
    @app_commands.choices(state=[
        app_commands.Choice(name="Open", value="open"),
        app_commands.Choice(name="Closed", value="closed"),
    ])
    async def milestones(
        self,
        interaction: discord.Interaction,
        repository: str,
        state: str = "open",
    ) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))

        try:
            data = await self._gh(interaction.user.id).get_milestones(owner, repo, state=state)
        except NotFound:
            return await interaction.followup.send(embed=build_error_embed("Not Found", f"`{repository}` not found."))
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        if not data:
            return await interaction.followup.send(
                embed=discord.Embed(description=f"No {state} milestones.", color=Colors.NEUTRAL)
            )

        embeds = []
        for ms in data:
            open_issues = ms.get("open_issues", 0)
            closed_issues = ms.get("closed_issues", 0)
            total = open_issues + closed_issues
            pct = round(closed_issues / max(1, total) * 100)
            bar_fill = round(pct / 10)
            bar = "█" * bar_fill + "░" * (10 - bar_fill)

            embed = discord.Embed(
                title=f"🏁 Milestone #{ms.get('number')}: {ms.get('title', 'N/A')}",
                url=ms.get("html_url", ""),
                description=clean_body(ms.get("description"), 300),
                color=Colors.SUCCESS if state == "closed" else Colors.PRIMARY,
            )
            embed.add_field(
                name="📊 Progress",
                value=f"`{bar}` {pct}%\n{Emojis.ISSUE_OPEN} {open_issues} open · {Emojis.ISSUE_CLOSED} {closed_issues} closed",
                inline=True,
            )
            embed.add_field(
                name="📅 Due Date",
                value=fmt_iso_date(ms.get("due_on"), "D") if ms.get("due_on") else "No due date",
                inline=True,
            )
            embed.add_field(name="📋 State", value=ms.get("state", "?").title(), inline=True)
            embed.set_footer(text=f"{owner}/{repo}")
            embeds.append(embed)

        await send_paginated(interaction, embeds, interaction.user.id)

    # ─── /milestone ───────────────────────────────────────────────────────

    @app_commands.command(name="milestone", description="Show detailed info about a specific milestone")
    @app_commands.describe(repository="owner/repo", number="Milestone number")
    async def milestone_detail(
        self,
        interaction: discord.Interaction,
        repository: str,
        number: int,
    ) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))

        try:
            ms = await self._gh(interaction.user.id).get_milestone(owner, repo, number)
        except NotFound:
            return await interaction.followup.send(
                embed=build_error_embed("Not Found", f"Milestone #{number} not found in `{repository}`.")
            )
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        open_issues = ms.get("open_issues", 0)
        closed_issues = ms.get("closed_issues", 0)
        total = open_issues + closed_issues
        pct = round(closed_issues / max(1, total) * 100)
        bar_fill = round(pct / 5)
        bar = "█" * bar_fill + "░" * (20 - bar_fill)

        embed = discord.Embed(
            title=f"🏁 Milestone #{number}: {ms.get('title', 'N/A')}",
            url=ms.get("html_url", ""),
            description=clean_body(ms.get("description"), 500),
            color=Colors.SUCCESS if ms.get("state") == "closed" else Colors.PRIMARY,
        )
        embed.add_field(
            name="📊 Progress",
            value=(
                f"`{bar}` **{pct}%**\n"
                f"{Emojis.ISSUE_OPEN} **{open_issues}** open · "
                f"{Emojis.ISSUE_CLOSED} **{closed_issues}** closed · "
                f"**{total}** total"
            ),
            inline=False,
        )

        creator = ms.get("creator", {})
        if creator:
            embed.add_field(
                name="👤 Created By",
                value=f"[@{creator.get('login', '?')}]({creator.get('html_url', '')})",
                inline=True,
            )

        embed.add_field(
            name="📅 Due Date",
            value=fmt_iso_date(ms.get("due_on"), "D") if ms.get("due_on") else "No due date",
            inline=True,
        )
        embed.add_field(name="📋 State", value=ms.get("state", "?").title(), inline=True)
        embed.add_field(name="📅 Created", value=fmt_iso_date(ms.get("created_at"), "R"), inline=True)
        embed.add_field(name="🔄 Updated", value=fmt_iso_date(ms.get("updated_at"), "R"), inline=True)

        if ms.get("closed_at"):
            embed.add_field(name="✅ Closed", value=fmt_iso_date(ms.get("closed_at"), "R"), inline=True)

        embed.set_footer(text=f"{owner}/{repo}")
        await interaction.followup.send(embed=embed)

    # ─── /issue-timeline ──────────────────────────────────────────────────

    @app_commands.command(name="issue-timeline", description="Show the full timeline of an issue")
    @app_commands.describe(repository="owner/repo", number="Issue number")
    async def issue_timeline(
        self,
        interaction: discord.Interaction,
        repository: str,
        number: int,
    ) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))

        try:
            timeline = await self._gh(interaction.user.id).get_issue_timeline(owner, repo, number, max_results=30)
        except NotFound:
            return await interaction.followup.send(
                embed=build_error_embed("Not Found", f"Issue #{number} not found in `{repository}`.")
            )
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        if not timeline:
            return await interaction.followup.send(
                embed=discord.Embed(description="No timeline events found.", color=Colors.NEUTRAL)
            )

        event_emoji = {
            "commented": "💬", "labeled": "🏷️", "unlabeled": "🏷️",
            "assigned": "👤", "unassigned": "👤", "mentioned": "📢",
            "referenced": "🔗", "closed": "🔴", "reopened": "🟢",
            "committed": "📝", "reviewed": "👀", "review_requested": "🔍",
            "review_dismissed": "🚫", "merged": "🟣", "head_ref_deleted": "🗑️",
            "milestoned": "🏁", "demilestoned": "🏁", "renamed": "✏️",
            "locked": "🔒", "unlocked": "🔓", "pinned": "📌", "unpinned": "📌",
        }

        pages = []
        chunk_size = 8
        for i in range(0, len(timeline), chunk_size):
            chunk = timeline[i:i + chunk_size]
            lines = []
            for event in chunk:
                ev_type = event.get("event", "unknown")
                emoji = event_emoji.get(ev_type, "⚡")
                actor = event.get("actor", {}) or event.get("user", {}) or {}
                login = actor.get("login", "unknown")
                date = fmt_iso_date(event.get("created_at"), "R")

                extra = ""
                if ev_type in ("labeled", "unlabeled"):
                    label = event.get("label", {}).get("name", "?")
                    extra = f" `{label}`"
                elif ev_type in ("assigned", "unassigned"):
                    assignee = event.get("assignee", {}).get("login", "?")
                    extra = f" @{assignee}"
                elif ev_type == "renamed":
                    extra = f" → **{event.get('rename', {}).get('to', '?')}**"
                elif ev_type == "milestoned":
                    extra = f" **{event.get('milestone', {}).get('title', '?')}**"

                lines.append(f"{emoji} **{ev_type.replace('_', ' ').title()}**{extra} — @{login} {date}")

            embed = discord.Embed(
                title=f"📅 Timeline — #{number} ({owner}/{repo})",
                description="\n".join(lines),
                color=Colors.SECONDARY,
            )
            embed.set_footer(
                text=f"Events {i+1}–{min(i+chunk_size, len(timeline))} of {len(timeline)}"
            )
            pages.append(embed)

        await send_paginated(interaction, pages, interaction.user.id)


async def setup(bot) -> None:
    await bot.add_cog(IssuesCog(bot))

"""
Octobot Pull Requests Cog — Commands for exploring and analyzing pull requests.
"""
from __future__ import annotations
from typing import Optional
import discord
from discord import app_commands
from discord.ext import commands
from config import Colors, Emojis
from utils.embeds import build_error_embed, build_pr_embed
from utils.helpers import clean_body, fmt_iso_date, fmt_number, parse_owner_repo
from utils.pagination import build_list_embeds, send_paginated
from utils.github_client import GitHubAPIError, NotFound


class PullRequestsCog(commands.Cog, name="Pull Requests"):
    """Commands for managing and analyzing GitHub Pull Requests."""

    def __init__(self, bot) -> None:
        self.bot = bot

    def _gh(self, user_id: int):
        return self.bot.get_github_client_for(user_id)

    @app_commands.command(name="prs", description="List pull requests in a repository")
    @app_commands.describe(
        repository="owner/repo", state="Filter by PR state",
        base="Filter by base branch", sort="Sort field",
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
            app_commands.Choice(name="Popularity", value="popularity"),
            app_commands.Choice(name="Long-Running", value="long-running"),
        ],
    )
    async def prs_list(
        self, interaction: discord.Interaction, repository: str,
        state: str = "open", base: str = None, sort: str = "created",
    ) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))

        try:
            prs = await self._gh(interaction.user.id).get_pull_requests(
                owner, repo, state=state, base=base, sort=sort, max_results=50
            )
        except NotFound:
            return await interaction.followup.send(embed=build_error_embed("Not Found", f"`{repository}` not found."))
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        if not prs:
            return await interaction.followup.send(
                embed=discord.Embed(description=f"No {state} pull requests found.", color=Colors.NEUTRAL)
            )

        def fmt_pr(pr: dict, idx: int) -> str:
            num = pr.get("number", 0)
            title = pr.get("title", "No title")[:65]
            is_merged = pr.get("merged", False)
            is_draft = pr.get("draft", False)
            s = pr.get("state", "open")
            if is_merged: emoji = Emojis.PR_MERGED
            elif is_draft: emoji = Emojis.PR_DRAFT
            elif s == "open": emoji = Emojis.PR_OPEN
            else: emoji = Emojis.ISSUE_CLOSED
            comments = pr.get("comments", 0) + pr.get("review_comments", 0)
            changed = pr.get("changed_files", 0)
            date = fmt_iso_date(pr.get("created_at"), "d")
            url = pr.get("html_url", "")
            return (
                f"`{idx:>2}.` {emoji} [**#{num}**]({url}) {title}\n"
                f"       💬 {comments} reviews · 📄 {changed} files · {date}"
            )

        state_emoji = {
            "open": Emojis.PR_OPEN, "closed": Emojis.ISSUE_CLOSED, "all": "🔵"
        }.get(state, "🔵")

        embeds = build_list_embeds(
            title=f"{state_emoji} Pull Requests — {owner}/{repo}",
            items=prs,
            formatter=fmt_pr,
            color=Colors.OPEN if state == "open" else Colors.CLOSED,
            per_page=8,
        )
        await send_paginated(interaction, embeds, interaction.user.id)

    @app_commands.command(name="pr", description="Show detailed info about a specific pull request")
    @app_commands.describe(repository="owner/repo", number="PR number")
    async def pr_detail(
        self, interaction: discord.Interaction, repository: str, number: int
    ) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))

        try:
            data = await self._gh(interaction.user.id).get_pull_request(owner, repo, number)
        except NotFound:
            return await interaction.followup.send(
                embed=build_error_embed("Not Found", f"PR #{number} not found in `{repository}`.")
            )
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        embed = build_pr_embed(data, owner, repo)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="pr-files", description="List files changed in a pull request")
    @app_commands.describe(repository="owner/repo", number="PR number")
    async def pr_files(
        self, interaction: discord.Interaction, repository: str, number: int
    ) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))

        try:
            files = await self._gh(interaction.user.id).get_pr_files(owner, repo, number)
        except NotFound:
            return await interaction.followup.send(
                embed=build_error_embed("Not Found", f"PR #{number} not found in `{repository}`.")
            )
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        if not files:
            return await interaction.followup.send(
                embed=discord.Embed(description="No files changed.", color=Colors.NEUTRAL)
            )

        status_emoji = {
            "added": "➕", "removed": "➖", "modified": "✏️",
            "renamed": "📛", "copied": "📋", "changed": "🔄", "unchanged": "⬜",
        }

        def fmt_file(f: dict, idx: int) -> str:
            fname = f.get("filename", "?")
            status = f.get("status", "modified")
            emoji = status_emoji.get(status, "📄")
            additions = f.get("additions", 0)
            deletions = f.get("deletions", 0)
            changes = f.get("changes", 0)
            return (
                f"`{idx:>3}.` {emoji} `{fname}`\n"
                f"         ➕ +{additions} ➖ -{deletions} ({changes} changes)"
            )

        total_add = sum(f.get("additions", 0) for f in files)
        total_del = sum(f.get("deletions", 0) for f in files)

        embeds = build_list_embeds(
            title=f"📄 Changed Files — PR #{number} · {owner}/{repo}",
            items=files,
            formatter=fmt_file,
            color=Colors.SECONDARY,
            per_page=10,
        )
        for e in embeds:
            e.add_field(
                name="📊 Summary",
                value=f"**{len(files)}** files · ➕ **{total_add}** · ➖ **{total_del}**",
                inline=False,
            )

        await send_paginated(interaction, embeds, interaction.user.id)

    @app_commands.command(name="pr-reviews", description="Show reviews on a pull request")
    @app_commands.describe(repository="owner/repo", number="PR number")
    async def pr_reviews(
        self, interaction: discord.Interaction, repository: str, number: int
    ) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))

        try:
            reviews = await self._gh(interaction.user.id).get_pr_reviews(owner, repo, number)
        except NotFound:
            return await interaction.followup.send(
                embed=build_error_embed("Not Found", f"PR #{number} not found in `{repository}`.")
            )
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        if not reviews:
            return await interaction.followup.send(
                embed=discord.Embed(description=f"No reviews on PR #{number}.", color=Colors.NEUTRAL)
            )

        state_info = {
            "APPROVED": ("✅", Colors.SUCCESS, "Approved"),
            "CHANGES_REQUESTED": ("⚠️", Colors.WARNING, "Changes Requested"),
            "COMMENTED": ("💬", Colors.SECONDARY, "Commented"),
            "DISMISSED": ("🚫", Colors.NEUTRAL, "Dismissed"),
            "PENDING": ("⏳", Colors.NEUTRAL, "Pending"),
        }

        embeds = []
        for i, review in enumerate(reviews):
            state = review.get("state", "COMMENTED")
            emoji, color, label = state_info.get(state, ("❓", Colors.NEUTRAL, state.title()))
            user = review.get("user", {})
            body = clean_body(review.get("body", ""), 600)

            embed = discord.Embed(
                title=f"{emoji} {label} — PR #{number}",
                url=review.get("html_url", ""),
                description=body or "*No review comment.*",
                color=color,
            )
            embed.set_author(
                name=f"@{user.get('login', 'unknown')}",
                url=user.get("html_url", ""),
                icon_url=user.get("avatar_url", ""),
            )
            embed.set_footer(
                text=(
                    f"Review {i+1}/{len(reviews)} · {owner}/{repo} · "
                    f"{fmt_iso_date(review.get('submitted_at'), 'R')}"
                )
            )
            embeds.append(embed)

        await send_paginated(interaction, embeds, interaction.user.id)

    @app_commands.command(name="pr-commits", description="List commits in a pull request")
    @app_commands.describe(repository="owner/repo", number="PR number")
    async def pr_commits(
        self, interaction: discord.Interaction, repository: str, number: int
    ) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))

        try:
            commits = await self._gh(interaction.user.id).get_pr_commits(owner, repo, number)
        except NotFound:
            return await interaction.followup.send(
                embed=build_error_embed("Not Found", f"PR #{number} not found in `{repository}`.")
            )
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        if not commits:
            return await interaction.followup.send(
                embed=discord.Embed(description="No commits found.", color=Colors.NEUTRAL)
            )

        def fmt_commit(c: dict, idx: int) -> str:
            sha = (c.get("sha") or "")[:7]
            msg = (c.get("commit", {}).get("message") or "").split("\n")[0][:65]
            login = (c.get("author", {}) or {}).get("login", "unknown")
            date = fmt_iso_date(c.get("commit", {}).get("author", {}).get("date"), "d")
            url = c.get("html_url", "")
            return f"`{idx:>2}.` [`{sha}`]({url}) {msg}\n       👤 `{login}` · {date}"

        embeds = build_list_embeds(
            title=f"{Emojis.COMMIT} Commits in PR #{number} — {owner}/{repo}",
            items=commits,
            formatter=fmt_commit,
            color=Colors.MERGED,
            per_page=8,
        )
        await send_paginated(interaction, embeds, interaction.user.id)

    @app_commands.command(name="pr-status", description="Check if a pull request is merged")
    @app_commands.describe(repository="owner/repo", number="PR number")
    async def pr_status(
        self, interaction: discord.Interaction, repository: str, number: int
    ) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))

        try:
            is_merged = await self._gh(interaction.user.id).is_pr_merged(owner, repo, number)
            pr = await self._gh(interaction.user.id).get_pull_request(owner, repo, number)
        except NotFound:
            return await interaction.followup.send(
                embed=build_error_embed("Not Found", f"PR #{number} not found.")
            )
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        state = pr.get("state", "open")
        is_draft = pr.get("draft", False)

        if is_merged:
            color, emoji, label = Colors.MERGED, Emojis.PR_MERGED, "Merged"
        elif state == "closed":
            color, emoji, label = Colors.CLOSED, Emojis.ISSUE_CLOSED, "Closed (Not Merged)"
        elif is_draft:
            color, emoji, label = Colors.DRAFT, Emojis.PR_DRAFT, "Draft"
        else:
            color, emoji, label = Colors.OPEN, Emojis.PR_OPEN, "Open"

        embed = discord.Embed(
            title=f"{emoji} PR #{number}: {label}",
            url=pr.get("html_url", ""),
            description=pr.get("title", ""),
            color=color,
        )
        embed.add_field(
            name="🔀 Mergeable",
            value=str(pr.get("mergeable_state", "unknown")).replace("_", " ").title(),
            inline=True,
        )
        embed.add_field(
            name=f"{Emojis.BRANCH} Branch",
            value=f"`{pr.get('head', {}).get('ref', '?')}` → `{pr.get('base', {}).get('ref', '?')}`",
            inline=True,
        )

        if is_merged and pr.get("merged_at"):
            embed.add_field(name="✅ Merged At", value=fmt_iso_date(pr["merged_at"], "F"), inline=False)
            merged_by = pr.get("merged_by") or {}
            if merged_by.get("login"):
                embed.add_field(name="👤 Merged By", value=f"[@{merged_by['login']}]({merged_by.get('html_url','')})", inline=True)

        embed.set_footer(text=f"{owner}/{repo}")
        await interaction.followup.send(embed=embed)


async def setup(bot) -> None:
    await bot.add_cog(PullRequestsCog(bot))

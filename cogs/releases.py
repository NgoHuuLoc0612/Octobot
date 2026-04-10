"""
Octobot Releases Cog — GitHub releases and tag commands.
"""
from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands
from config import Colors, Emojis
from utils.embeds import build_error_embed, build_release_embed
from utils.helpers import fmt_iso_date, parse_owner_repo
from utils.pagination import build_list_embeds, send_paginated
from utils.github_client import GitHubAPIError, NotFound


class ReleasesCog(commands.Cog, name="Releases"):
    def __init__(self, bot) -> None:
        self.bot = bot

    def _gh(self, user_id: int):
        return self.bot.get_github_client_for(user_id)

    @app_commands.command(name="releases", description="List releases for a repository")
    @app_commands.describe(repository="owner/repo")
    async def releases(self, interaction: discord.Interaction, repository: str) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))
        try:
            data = await self._gh(interaction.user.id).get_releases(owner, repo, max_results=20)
        except NotFound:
            return await interaction.followup.send(embed=build_error_embed("Not Found", f"`{repository}` not found."))
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))
        if not data:
            return await interaction.followup.send(
                embed=discord.Embed(description="No releases found.", color=Colors.NEUTRAL)
            )

        def fmt_release(r: dict, idx: int) -> str:
            tag = r.get("tag_name", "?")
            name = r.get("name") or tag
            published = fmt_iso_date(r.get("published_at"), "d")
            pre = "🔶 Pre-release" if r.get("prerelease") else ("📦 Draft" if r.get("draft") else "🚀 Release")
            assets = len(r.get("assets", []))
            url = r.get("html_url", "")
            return f"`{idx:>2}.` {pre} [{name}]({url})\n       🏷️ `{tag}` · 📦 {assets} assets · {published}"

        embeds = build_list_embeds(
            title=f"{Emojis.RELEASE} Releases — {owner}/{repo}",
            items=data,
            formatter=fmt_release,
            color=Colors.SUCCESS,
            per_page=8,
        )
        await send_paginated(interaction, embeds, interaction.user.id)

    @app_commands.command(name="release", description="Show the latest or a specific release")
    @app_commands.describe(repository="owner/repo", tag="Tag name (default: latest release)")
    async def release(
        self, interaction: discord.Interaction, repository: str, tag: str = None
    ) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))
        try:
            if tag:
                data = await self._gh(interaction.user.id).get_release_by_tag(owner, repo, tag)
            else:
                data = await self._gh(interaction.user.id).get_latest_release(owner, repo)
        except NotFound:
            msg = f"Tag `{tag}` not found." if tag else "No releases found."
            return await interaction.followup.send(embed=build_error_embed("Not Found", msg))
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))
        embed = build_release_embed(data, owner, repo)
        await interaction.followup.send(embed=embed)


async def setup(bot) -> None:
    await bot.add_cog(ReleasesCog(bot))

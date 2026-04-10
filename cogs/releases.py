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


    @app_commands.command(name="release-assets", description="List download assets for a specific release")
    @app_commands.describe(repository="owner/repo", tag="Release tag name (default: latest)")
    async def release_assets(
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

        assets = data.get("assets", [])
        release_name = data.get("name") or data.get("tag_name", "?")
        release_url = data.get("html_url", "")

        embed = discord.Embed(
            title=f"📦 Assets — {release_name}",
            url=release_url,
            color=Colors.SUCCESS,
        )

        if not assets:
            embed.description = "No binary assets attached to this release.\n*(Source code archives are always available on the release page.)*"
        else:
            lines = []
            total_size = 0
            for a in assets:
                name = a.get("name", "?")
                size = a.get("size", 0)
                total_size += size
                downloads = a.get("download_count", 0)
                url = a.get("browser_download_url", "")
                from utils.helpers import fmt_bytes
                lines.append(
                    f"[📥 {name}]({url})\n"
                    f"  `{fmt_bytes(size)}` · ⬇️ {downloads:,} downloads"
                )
            embed.description = "\n\n".join(lines[:15])
            from utils.helpers import fmt_bytes
            embed.set_footer(text=f"{len(assets)} asset(s) · Total: {fmt_bytes(total_size)}")

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="release-notes", description="Show the changelog / body of a specific release")
    @app_commands.describe(repository="owner/repo", tag="Release tag (default: latest)")
    async def release_notes(
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

        release_name = data.get("name") or data.get("tag_name", "?")
        body = data.get("body") or "*No release notes provided.*"
        url = data.get("html_url", "")

        # Discord embed description limit is 4096 chars
        if len(body) > 3800:
            body = body[:3800] + f"\n\n*[…truncated — see full notes]({url})*"

        embed = discord.Embed(
            title=f"📋 Release Notes — {release_name}",
            url=url,
            description=body,
            color=Colors.SUCCESS,
        )
        pre = "🔶 Pre-release" if data.get("prerelease") else ("📦 Draft" if data.get("draft") else "🚀 Release")
        embed.add_field(name="Type", value=pre, inline=True)
        embed.add_field(name="Tag", value=f"`{data.get('tag_name', '?')}`", inline=True)
        embed.add_field(name="Published", value=fmt_iso_date(data.get("published_at"), "d"), inline=True)
        embed.set_footer(text=f"{owner}/{repo}")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="latest-release", description="Quick view of the latest release for a repository")
    @app_commands.describe(repository="owner/repo")
    async def latest_release(
        self, interaction: discord.Interaction, repository: str
    ) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))

        try:
            data = await self._gh(interaction.user.id).get_latest_release(owner, repo)
        except NotFound:
            return await interaction.followup.send(embed=build_error_embed("Not Found", "No releases found for this repository."))
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        from utils.embeds import build_release_embed
        embed = build_release_embed(data, owner, repo)
        await interaction.followup.send(embed=embed)


async def setup(bot) -> None:
    await bot.add_cog(ReleasesCog(bot))

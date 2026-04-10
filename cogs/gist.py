"""
Octobot Gist Cog.
"""
from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands
from config import Colors, Emojis
from utils.embeds import build_error_embed, build_gist_embed
from utils.helpers import clean_body, fmt_iso_date
from utils.pagination import build_list_embeds, send_paginated
from utils.github_client import GitHubAPIError, NotFound


class GistCog(commands.Cog, name="Gist"):
    def __init__(self, bot) -> None:
        self.bot = bot

    def _gh(self, user_id: int):
        return self.bot.get_github_client_for(user_id)

    @app_commands.command(name="gist", description="Show a GitHub Gist by ID")
    @app_commands.describe(gist_id="Gist ID (from the URL)")
    async def gist(self, interaction: discord.Interaction, gist_id: str) -> None:
        await interaction.response.defer()
        try:
            data = await self._gh(interaction.user.id).get_gist(gist_id)
        except NotFound:
            return await interaction.followup.send(embed=build_error_embed("Not Found", f"Gist `{gist_id}` not found."))
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))
        embed = build_gist_embed(data)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="user-gists", description="List public gists by a user")
    @app_commands.describe(username="GitHub username")
    async def user_gists(self, interaction: discord.Interaction, username: str) -> None:
        await interaction.response.defer()
        try:
            gists = await self._gh(interaction.user.id).get_user_gists(username, max_results=30)
        except NotFound:
            return await interaction.followup.send(embed=build_error_embed("Not Found", f"User `{username}` not found."))
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        if not gists:
            return await interaction.followup.send(
                embed=discord.Embed(description=f"@{username} has no public gists.", color=Colors.NEUTRAL)
            )

        def fmt_gist(g: dict, idx: int) -> str:
            desc = g.get("description") or "No description"
            gid = g.get("id", "")
            files = g.get("files", {})
            fcount = len(files)
            comments = g.get("comments", 0)
            visibility = "🌍" if g.get("public") else "🔒"
            url = g.get("html_url", "")
            updated = fmt_iso_date(g.get("updated_at"), "R")
            return (
                f"`{idx:>2}.` {visibility} [{desc[:60]}]({url})\n"
                f"       📄 {fcount} file(s) · 💬 {comments} comments · {updated}"
            )

        embeds = build_list_embeds(
            title=f"{Emojis.GIST} Gists — @{username}",
            items=gists,
            formatter=fmt_gist,
            color=Colors.SECONDARY,
            per_page=8,
        )
        await send_paginated(interaction, embeds, interaction.user.id)

    @app_commands.command(name="gist-file", description="Preview a file inside a Gist")
    @app_commands.describe(gist_id="Gist ID", filename="Filename to preview")
    async def gist_file(
        self, interaction: discord.Interaction, gist_id: str, filename: str
    ) -> None:
        await interaction.response.defer()
        try:
            data = await self._gh(interaction.user.id).get_gist(gist_id)
        except NotFound:
            return await interaction.followup.send(embed=build_error_embed("Not Found", f"Gist `{gist_id}` not found."))
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        files = data.get("files", {})
        file_info = files.get(filename) or next(
            (v for k, v in files.items() if k.lower() == filename.lower()), None
        )

        if not file_info:
            available = ", ".join(f"`{k}`" for k in list(files.keys())[:10])
            return await interaction.followup.send(
                embed=build_error_embed("File Not Found", f"Available files: {available}")
            )

        content = file_info.get("content", "") or ""
        lang_map = {
            "py": "python", "js": "javascript", "ts": "typescript", "go": "go",
            "rs": "rust", "rb": "ruby", "java": "java", "sh": "bash",
            "json": "json", "yaml": "yaml", "yml": "yaml", "md": "markdown",
        }
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        lang = lang_map.get(ext, file_info.get("language", "").lower())

        preview = content[:1900]
        if len(content) > 1900:
            preview += "\n..."

        embed = discord.Embed(
            title=f"{Emojis.CODE} {filename}",
            url=data.get("html_url", ""),
            description=f"```{lang}\n{preview}\n```",
            color=Colors.NEUTRAL,
        )
        embed.set_footer(
            text=f"Gist: {gist_id} · {file_info.get('size', 0)} bytes"
        )
        await interaction.followup.send(embed=embed)


async def setup(bot) -> None:
    await bot.add_cog(GistCog(bot))

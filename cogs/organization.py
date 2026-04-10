"""
Octobot Organization Cog — GitHub organization commands.
"""
from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands
from config import Colors, Emojis
from utils.embeds import build_error_embed, build_org_embed
from utils.helpers import fmt_iso_date, fmt_number, parse_owner_repo
from utils.pagination import build_list_embeds, send_paginated
from utils.github_client import GitHubAPIError, NotFound


class OrganizationCog(commands.Cog, name="Organization"):
    def __init__(self, bot) -> None:
        self.bot = bot

    def _gh(self, user_id: int):
        return self.bot.get_github_client_for(user_id)

    @app_commands.command(name="org", description="Show detailed info about a GitHub organization")
    @app_commands.describe(organization="Organization name")
    async def org_info(self, interaction: discord.Interaction, organization: str) -> None:
        await interaction.response.defer()
        try:
            data = await self._gh(interaction.user.id).get_org(organization)
        except NotFound:
            return await interaction.followup.send(embed=build_error_embed("Not Found", f"Org `{organization}` not found."))
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))
        embed = build_org_embed(data)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="org-repos", description="List repositories of a GitHub organization")
    @app_commands.describe(organization="Organization name", type="Repository type", sort="Sort field")
    @app_commands.choices(
        type=[
            app_commands.Choice(name="All", value="all"),
            app_commands.Choice(name="Public", value="public"),
            app_commands.Choice(name="Forks", value="forks"),
            app_commands.Choice(name="Sources", value="sources"),
        ],
        sort=[
            app_commands.Choice(name="Created", value="created"),
            app_commands.Choice(name="Updated", value="updated"),
            app_commands.Choice(name="Pushed", value="pushed"),
            app_commands.Choice(name="Full Name", value="full_name"),
        ],
    )
    async def org_repos(
        self, interaction: discord.Interaction, organization: str,
        type: str = "all", sort: str = "updated",
    ) -> None:
        await interaction.response.defer()
        try:
            repos = await self._gh(interaction.user.id).get_org_repos(
                organization, type=type, sort=sort, max_results=50
            )
        except NotFound:
            return await interaction.followup.send(embed=build_error_embed("Not Found", f"Org `{organization}` not found."))
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        if not repos:
            return await interaction.followup.send(
                embed=discord.Embed(description="No repositories found.", color=Colors.NEUTRAL)
            )

        def fmt_repo(r: dict, idx: int) -> str:
            name = r.get("name", "?")
            stars = r.get("stargazers_count", 0)
            forks = r.get("forks_count", 0)
            lang = r.get("language") or "N/A"
            url = r.get("html_url", "")
            desc = r.get("description") or ""
            updated = fmt_iso_date(r.get("updated_at"), "R")
            return (
                f"`{idx:>2}.` [{name}]({url})"
                + (f" — {desc[:45]}" if desc else "")
                + f"\n       {Emojis.STAR}{fmt_number(stars)} · {Emojis.FORK}{fmt_number(forks)} · {lang} · {updated}"
            )

        embeds = build_list_embeds(
            title=f"📁 Repositories — {organization}",
            items=repos,
            formatter=fmt_repo,
            color=Colors.PURPLE,
            per_page=8,
        )
        await send_paginated(interaction, embeds, interaction.user.id)

    @app_commands.command(name="org-members", description="List members of a GitHub organization")
    @app_commands.describe(organization="Organization name", role="Member role filter")
    @app_commands.choices(role=[
        app_commands.Choice(name="All", value="all"),
        app_commands.Choice(name="Admin/Owner", value="admin"),
        app_commands.Choice(name="Member", value="member"),
    ])
    async def org_members(
        self, interaction: discord.Interaction, organization: str, role: str = "all"
    ) -> None:
        await interaction.response.defer()
        try:
            members = await self._gh(interaction.user.id).get_org_members(
                organization, role=role, max_results=50
            )
        except NotFound:
            return await interaction.followup.send(embed=build_error_embed("Not Found", f"Org `{organization}` not found."))
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        if not members:
            return await interaction.followup.send(
                embed=discord.Embed(description="No members found.", color=Colors.NEUTRAL)
            )

        def fmt_member(m: dict, idx: int) -> str:
            login = m.get("login", "?")
            url = m.get("html_url", "")
            mtype = m.get("type", "User")
            return f"`{idx:>2}.` {Emojis.USER} [@{login}]({url}) ({mtype})"

        embeds = build_list_embeds(
            title=f"👥 Members — {organization}",
            items=members,
            formatter=fmt_member,
            color=Colors.PURPLE,
            per_page=15,
        )
        await send_paginated(interaction, embeds, interaction.user.id)

    @app_commands.command(name="org-teams", description="List teams in a GitHub organization")
    @app_commands.describe(organization="Organization name")
    async def org_teams(self, interaction: discord.Interaction, organization: str) -> None:
        await interaction.response.defer()
        try:
            teams = await self._gh(interaction.user.id).get_org_teams(organization)
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        if not teams:
            return await interaction.followup.send(
                embed=discord.Embed(description="No teams found (may require org membership).", color=Colors.NEUTRAL)
            )

        def fmt_team(t: dict, idx: int) -> str:
            name = t.get("name", "?")
            slug = t.get("slug", "?")
            members_count = t.get("members_count", 0)
            repos_count = t.get("repos_count", 0)
            privacy = "🔒" if t.get("privacy") == "secret" else "🌍"
            desc = t.get("description") or ""
            return (
                f"`{idx:>2}.` {privacy} **{name}** (`{slug}`)"
                + (f" — {desc[:40]}" if desc else "")
                + f"\n       👥 {members_count} members · 📁 {repos_count} repos"
            )

        embeds = build_list_embeds(
            title=f"🏢 Teams — {organization}",
            items=teams,
            formatter=fmt_team,
            color=Colors.PURPLE,
            per_page=8,
        )
        await send_paginated(interaction, embeds, interaction.user.id)


async def setup(bot) -> None:
    await bot.add_cog(OrganizationCog(bot))

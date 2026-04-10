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


    @app_commands.command(name="team", description="Show details of a specific team in an organization")
    @app_commands.describe(organization="Organization name", team="Team slug (from org-teams)")
    async def team_detail(
        self, interaction: discord.Interaction, organization: str, team: str
    ) -> None:
        await interaction.response.defer()
        try:
            data = await self._gh(interaction.user.id).get_team(organization, team)
        except NotFound:
            return await interaction.followup.send(embed=build_error_embed("Not Found", f"Team `{team}` not found in `{organization}`."))
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        privacy = "🔒 Secret" if data.get("privacy") == "secret" else "🌍 Visible"
        embed = discord.Embed(
            title=f"👥 {data.get('name', team)}",
            url=data.get("html_url", ""),
            description=data.get("description") or "*No description.*",
            color=Colors.PURPLE,
        )
        embed.add_field(name="🔖 Slug", value=f"`{data.get('slug', team)}`", inline=True)
        embed.add_field(name="👁️ Privacy", value=privacy, inline=True)
        embed.add_field(name="🆔 ID", value=f"`{data.get('id', 'N/A')}`", inline=True)
        embed.add_field(name="👥 Members", value=f"{data.get('members_count', 0):,}", inline=True)
        embed.add_field(name="📁 Repos", value=f"{data.get('repos_count', 0):,}", inline=True)
        if data.get("parent"):
            embed.add_field(name="⬆️ Parent Team", value=f"`{data['parent'].get('slug', 'N/A')}`", inline=True)
        embed.set_footer(text=organization)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="team-members", description="List members of a specific team")
    @app_commands.describe(organization="Organization name", team="Team slug")
    async def team_members(
        self, interaction: discord.Interaction, organization: str, team: str
    ) -> None:
        await interaction.response.defer()
        try:
            members = await self._gh(interaction.user.id).get_team_members(organization, team, max_results=50)
        except NotFound:
            return await interaction.followup.send(embed=build_error_embed("Not Found", f"Team `{team}` not found."))
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        if not members:
            return await interaction.followup.send(
                embed=discord.Embed(description="No members found (may require org membership).", color=Colors.NEUTRAL)
            )

        def fmt_member(m: dict, idx: int) -> str:
            login = m.get("login", "?")
            url = m.get("html_url", "")
            mtype = m.get("type", "User")
            return f"`{idx:>2}.` {Emojis.USER} [@{login}]({url}) ({mtype})"

        embeds = build_list_embeds(
            title=f"👥 Team Members — {team} · {organization}",
            items=members,
            formatter=fmt_member,
            color=Colors.PURPLE,
            per_page=15,
        )
        await send_paginated(interaction, embeds, interaction.user.id)

    @app_commands.command(name="team-repos", description="List repositories accessible to a team")
    @app_commands.describe(organization="Organization name", team="Team slug")
    async def team_repos(
        self, interaction: discord.Interaction, organization: str, team: str
    ) -> None:
        await interaction.response.defer()
        try:
            repos = await self._gh(interaction.user.id).get_team_repos(organization, team, max_results=50)
        except NotFound:
            return await interaction.followup.send(embed=build_error_embed("Not Found", f"Team `{team}` not found."))
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        if not repos:
            return await interaction.followup.send(
                embed=discord.Embed(description="No repositories found for this team.", color=Colors.NEUTRAL)
            )

        def fmt_repo(r: dict, idx: int) -> str:
            name = r.get("name", "?")
            stars = r.get("stargazers_count", 0)
            lang = r.get("language") or "N/A"
            url = r.get("html_url", "")
            perms = r.get("permissions", {})
            perm_str = "admin" if perms.get("admin") else ("push" if perms.get("push") else "pull")
            return (
                f"`{idx:>2}.` [{name}]({url})\n"
                f"       {Emojis.STAR}{fmt_number(stars)} · {lang} · 🔐 `{perm_str}`"
            )

        embeds = build_list_embeds(
            title=f"📁 Team Repos — {team} · {organization}",
            items=repos,
            formatter=fmt_repo,
            color=Colors.PURPLE,
            per_page=8,
        )
        await send_paginated(interaction, embeds, interaction.user.id)

    @app_commands.command(name="org-projects", description="List projects in a GitHub organization")
    @app_commands.describe(organization="Organization name", state="Project state filter")
    @app_commands.choices(state=[
        app_commands.Choice(name="Open", value="open"),
        app_commands.Choice(name="Closed", value="closed"),
        app_commands.Choice(name="All", value="all"),
    ])
    async def org_projects(
        self, interaction: discord.Interaction, organization: str, state: str = "open"
    ) -> None:
        await interaction.response.defer()
        try:
            projects = await self._gh(interaction.user.id).get_org_projects(organization, state=state)
        except NotFound:
            return await interaction.followup.send(embed=build_error_embed("Not Found", f"Org `{organization}` not found."))
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        if not projects:
            return await interaction.followup.send(
                embed=discord.Embed(description=f"No {state} projects found.", color=Colors.NEUTRAL)
            )

        def fmt_project(p: dict, idx: int) -> str:
            name = p.get("name", "?")
            number = p.get("number", "?")
            body = p.get("body") or ""
            url = p.get("html_url", "")
            updated = fmt_iso_date(p.get("updated_at"), "R")
            columns = p.get("columns_url", "")
            return (
                f"`{idx:>2}.` [**#{number} {name}**]({url})\n"
                + (f"       {body[:60]}…\n" if len(body) > 60 else (f"       {body}\n" if body else ""))
                + f"       🔄 {updated}"
            )

        embeds = build_list_embeds(
            title=f"📋 Projects — {organization}",
            items=projects,
            formatter=fmt_project,
            color=Colors.PURPLE,
            per_page=8,
        )
        await send_paginated(interaction, embeds, interaction.user.id)

    @app_commands.command(name="org-webhooks", description="List webhooks for an organization")
    @app_commands.describe(organization="Organization name")
    async def org_webhooks(
        self, interaction: discord.Interaction, organization: str
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            # Use raw request via the client's _request method
            gh = self._gh(interaction.user.id)
            hooks = await gh._paginate(f"/orgs/{organization}/hooks")
        except NotFound:
            return await interaction.followup.send(embed=build_error_embed("Not Found", f"Org `{organization}` not found."), ephemeral=True)
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)), ephemeral=True)

        embed = discord.Embed(
            title=f"🔗 Webhooks — {organization}",
            color=Colors.NEUTRAL,
        )
        if hooks:
            lines = []
            for i, h in enumerate(hooks[:20]):
                config = h.get("config", {})
                url_val = config.get("url", "N/A")
                active = "✅" if h.get("active") else "❌"
                events = ", ".join(h.get("events", [])[:4])
                lines.append(
                    f"`{i+1}.` {active} `{url_val[:50]}`\n       Events: `{events}`"
                )
            embed.description = "\n".join(lines)
        else:
            embed.description = "No webhooks configured (may require admin access)."
        embed.set_footer(text="Shown only to you • Requires org admin access")
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot) -> None:
    await bot.add_cog(OrganizationCog(bot))

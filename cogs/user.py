"""
Octobot User Cog — GitHub user profile and activity commands.
"""
from __future__ import annotations
from typing import Optional
import discord
from discord import app_commands
from discord.ext import commands
from config import Colors, Emojis
from utils.embeds import build_error_embed, build_user_embed
from utils.helpers import fmt_iso_date, fmt_number, parse_owner_repo
from utils.pagination import build_list_embeds, send_paginated
from utils.github_client import GitHubAPIError, NotFound


class UserCog(commands.Cog, name="User"):
    """Commands for exploring GitHub user profiles and activity."""

    def __init__(self, bot) -> None:
        self.bot = bot

    def _gh(self, user_id: int):
        return self.bot.get_github_client_for(user_id)

    @app_commands.command(name="user", description="Show a GitHub user's profile")
    @app_commands.describe(username="GitHub username")
    async def user_profile(self, interaction: discord.Interaction, username: str) -> None:
        await interaction.response.defer()
        try:
            data = await self._gh(interaction.user.id).get_user(username)
        except NotFound:
            return await interaction.followup.send(embed=build_error_embed("Not Found", f"User `{username}` not found."))
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))
        embed = build_user_embed(data)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="user-repos", description="List public repositories of a GitHub user")
    @app_commands.describe(username="GitHub username", sort="Sort field", type="Repository type")
    @app_commands.choices(
        sort=[
            app_commands.Choice(name="Updated", value="updated"),
            app_commands.Choice(name="Stars", value="stars"),
            app_commands.Choice(name="Forks", value="forks"),
            app_commands.Choice(name="Created", value="created"),
        ],
        type=[
            app_commands.Choice(name="All", value="all"),
            app_commands.Choice(name="Owner", value="owner"),
            app_commands.Choice(name="Forks", value="forks"),
            app_commands.Choice(name="Sources", value="sources"),
        ],
    )
    async def user_repos(
        self, interaction: discord.Interaction, username: str,
        sort: str = "updated", type: str = "all",
    ) -> None:
        await interaction.response.defer()
        try:
            repos = await self._gh(interaction.user.id).list_user_repos(
                username, type=type, sort=sort, max_results=50
            )
        except NotFound:
            return await interaction.followup.send(embed=build_error_embed("Not Found", f"User `{username}` not found."))
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        if not repos:
            return await interaction.followup.send(
                embed=discord.Embed(description=f"@{username} has no public repositories.", color=Colors.NEUTRAL)
            )

        def fmt_repo(r: dict, idx: int) -> str:
            name = r.get("name", "?")
            stars = r.get("stargazers_count", 0)
            forks = r.get("forks_count", 0)
            lang = r.get("language") or "N/A"
            desc = r.get("description") or ""
            url = r.get("html_url", "")
            fork_mark = "🍴 " if r.get("fork") else ""
            return (
                f"`{idx:>2}.` {fork_mark}[**{name}**]({url})"
                + (f" — {desc[:45]}" if desc else "")
                + f"\n       {Emojis.STAR}{fmt_number(stars)} · {Emojis.FORK}{fmt_number(forks)} · {lang}"
            )

        embeds = build_list_embeds(
            title=f"📁 Repositories — @{username}",
            items=repos,
            formatter=fmt_repo,
            color=Colors.SECONDARY,
            per_page=8,
        )
        await send_paginated(interaction, embeds, interaction.user.id)

    @app_commands.command(name="user-starred", description="Show repositories starred by a user")
    @app_commands.describe(username="GitHub username")
    async def user_starred(self, interaction: discord.Interaction, username: str) -> None:
        await interaction.response.defer()
        try:
            repos = await self._gh(interaction.user.id).get_user_starred(username, max_results=30)
        except NotFound:
            return await interaction.followup.send(embed=build_error_embed("Not Found", f"User `{username}` not found."))
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        if not repos:
            return await interaction.followup.send(
                embed=discord.Embed(description=f"@{username} hasn't starred any repos.", color=Colors.NEUTRAL)
            )

        def fmt_repo(r: dict, idx: int) -> str:
            name = r.get("full_name", "?")
            stars = r.get("stargazers_count", 0)
            lang = r.get("language") or "N/A"
            url = r.get("html_url", "")
            desc = r.get("description") or ""
            return (
                f"`{idx:>2}.` {Emojis.STAR} [{name}]({url})"
                + (f" — {desc[:50]}" if desc else "")
                + f"\n       ⭐{fmt_number(stars)} · {lang}"
            )

        embeds = build_list_embeds(
            title=f"⭐ Starred by @{username}",
            items=repos,
            formatter=fmt_repo,
            color=Colors.WARNING,
            per_page=8,
        )
        await send_paginated(interaction, embeds, interaction.user.id)

    @app_commands.command(name="user-followers", description="List followers of a GitHub user")
    @app_commands.describe(username="GitHub username")
    async def user_followers(self, interaction: discord.Interaction, username: str) -> None:
        await interaction.response.defer()
        try:
            followers = await self._gh(interaction.user.id).get_user_followers(username, max_results=50)
        except NotFound:
            return await interaction.followup.send(embed=build_error_embed("Not Found", f"User `{username}` not found."))
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        def fmt_user(u: dict, idx: int) -> str:
            login = u.get("login", "?")
            url = u.get("html_url", "")
            return f"`{idx:>2}.` {Emojis.USER} [@{login}]({url})"

        embeds = build_list_embeds(
            title=f"👥 Followers of @{username}",
            items=followers,
            formatter=fmt_user,
            color=Colors.SECONDARY,
            per_page=15,
        )
        await send_paginated(interaction, embeds, interaction.user.id)

    @app_commands.command(name="user-following", description="List users that a GitHub user is following")
    @app_commands.describe(username="GitHub username")
    async def user_following(self, interaction: discord.Interaction, username: str) -> None:
        await interaction.response.defer()
        try:
            following = await self._gh(interaction.user.id).get_user_following(username, max_results=50)
        except NotFound:
            return await interaction.followup.send(embed=build_error_embed("Not Found", f"User `{username}` not found."))
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        def fmt_user(u: dict, idx: int) -> str:
            login = u.get("login", "?")
            url = u.get("html_url", "")
            return f"`{idx:>2}.` {Emojis.USER} [@{login}]({url})"

        embeds = build_list_embeds(
            title=f"👤 @{username} is Following",
            items=following,
            formatter=fmt_user,
            color=Colors.SECONDARY,
            per_page=15,
        )
        await send_paginated(interaction, embeds, interaction.user.id)

    @app_commands.command(name="whoami", description="Show the currently linked GitHub account")
    async def whoami(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        link = None
        if interaction.guild and self.bot.db:
            link = await self.bot.db.get_user_link(interaction.user.id, interaction.guild.id)

        if link:
            try:
                data = await self._gh(interaction.user.id).get_user(link.github_username)
                embed = build_user_embed(data)
                embed.title = f"🔑 Linked as: {embed.title}"
                return await interaction.followup.send(embed=embed, ephemeral=True)
            except GitHubAPIError:
                pass

        embed = discord.Embed(
            title="🔑 No GitHub Account Linked",
            description=(
                "Use `/link-github <username>` to link your GitHub account.\n"
                "Use `/set-token` to add a personal access token for increased API limits."
            ),
            color=Colors.WARNING,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="link-github", description="Link your Discord to a GitHub username")
    @app_commands.describe(username="Your GitHub username")
    async def link_github(self, interaction: discord.Interaction, username: str) -> None:
        await interaction.response.defer(ephemeral=True)
        if not interaction.guild:
            return await interaction.followup.send("This command must be used in a server.", ephemeral=True)

        try:
            user_data = await self._gh(interaction.user.id).get_user(username)
        except NotFound:
            return await interaction.followup.send(
                embed=build_error_embed("Not Found", f"GitHub user `{username}` was not found."), ephemeral=True
            )
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)), ephemeral=True)

        await self.bot.db.ensure_guild(interaction.guild.id, interaction.guild.name)
        await self.bot.db.link_user(interaction.user.id, username, interaction.guild.id)

        embed = discord.Embed(
            title="✅ GitHub Account Linked",
            description=f"Your Discord account is now linked to [@{username}](https://github.com/{username}).",
            color=Colors.SUCCESS,
        )
        embed.set_thumbnail(url=user_data.get("avatar_url", ""))
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="unlink-github", description="Unlink your GitHub account from this server")
    async def unlink_github(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        if not interaction.guild:
            return await interaction.followup.send("This command must be used in a server.", ephemeral=True)

        removed = await self.bot.db.remove_user_link(interaction.user.id, interaction.guild.id)
        if removed:
            self.bot.remove_github_token_for_user(interaction.user.id)
            await interaction.followup.send(
                embed=discord.Embed(description="✅ GitHub account unlinked.", color=Colors.SUCCESS),
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                embed=discord.Embed(description="You don't have a linked GitHub account.", color=Colors.WARNING),
                ephemeral=True,
            )

    @app_commands.command(name="user-events", description="Show recent public GitHub events for a user")
    @app_commands.describe(username="GitHub username")
    async def user_events(self, interaction: discord.Interaction, username: str) -> None:
        await interaction.response.defer()
        try:
            events = await self._gh(interaction.user.id).get_user_events(username, max_results=30)
        except NotFound:
            return await interaction.followup.send(embed=build_error_embed("Not Found", f"User `{username}` not found."))
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        event_emoji = {
            "PushEvent": "📝", "PullRequestEvent": "🔵", "IssuesEvent": "🟢",
            "CreateEvent": "✨", "DeleteEvent": "🗑️", "ForkEvent": "🍴",
            "WatchEvent": "⭐", "ReleaseEvent": "🚀", "IssueCommentEvent": "💬",
            "PullRequestReviewEvent": "👀", "CommitCommentEvent": "💬",
            "MemberEvent": "👤", "PublicEvent": "🌍", "GollumEvent": "📖",
        }

        def fmt_event(e: dict, idx: int) -> str:
            etype = e.get("type", "Event")
            emoji = event_emoji.get(etype, "⚡")
            repo = e.get("repo", {}).get("name", "?")
            date = fmt_iso_date(e.get("created_at"), "R")
            label = etype.replace("Event", "").replace("PullRequest", "PR")
            return f"`{idx:>2}.` {emoji} **{label}** in `{repo}` {date}"

        embeds = build_list_embeds(
            title=f"⚡ Recent Events — @{username}",
            items=events,
            formatter=fmt_event,
            color=Colors.SECONDARY,
            per_page=10,
        )
        await send_paginated(interaction, embeds, interaction.user.id)

    @app_commands.command(name="user-orgs", description="Show organizations a GitHub user belongs to")
    @app_commands.describe(username="GitHub username")
    async def user_orgs(self, interaction: discord.Interaction, username: str) -> None:
        await interaction.response.defer()
        try:
            orgs = await self._gh(interaction.user.id).get_user_orgs(username)
        except NotFound:
            return await interaction.followup.send(embed=build_error_embed("Not Found", f"User `{username}` not found."))
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        embed = discord.Embed(
            title=f"🏢 Organizations — @{username}",
            color=Colors.PURPLE,
        )
        if orgs:
            lines = [
                f"`{i+1:>2}.` [{o.get('login', '?')}](https://github.com/{o.get('login', '?')})"
                for i, o in enumerate(orgs)
            ]
            embed.description = "\n".join(lines)
        else:
            embed.description = f"@{username} has no public organization memberships."

        embed.set_footer(text=f"Total: {len(orgs)} organization(s)")
        await interaction.followup.send(embed=embed)


async def setup(bot) -> None:
    await bot.add_cog(UserCog(bot))

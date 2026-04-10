"""
Octobot Notifications Cog — Subscribe to GitHub repository events.
"""
from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands
from config import Colors, Emojis
from utils.embeds import build_error_embed, build_success_embed
from utils.helpers import parse_owner_repo
from utils.pagination import build_list_embeds, send_paginated
from utils.github_client import GitHubAPIError, NotFound


EVENT_CHOICES = [
    app_commands.Choice(name="Push", value="push"),
    app_commands.Choice(name="Issues", value="issues"),
    app_commands.Choice(name="Pull Requests", value="pull_request"),
    app_commands.Choice(name="Releases", value="release"),
    app_commands.Choice(name="Stars", value="star"),
    app_commands.Choice(name="Forks", value="fork"),
    app_commands.Choice(name="Discussions", value="discussion"),
    app_commands.Choice(name="Workflows", value="workflow_run"),
]


class NotificationsCog(commands.Cog, name="Notifications"):
    """Subscribe to GitHub repository events and get Discord notifications."""

    def __init__(self, bot) -> None:
        self.bot = bot

    def _gh(self, user_id: int):
        return self.bot.get_github_client_for(user_id)

    @app_commands.command(name="subscribe", description="Subscribe a channel to GitHub repository events")
    @app_commands.describe(
        repository="owner/repo",
        event="Event type to subscribe to",
        channel="Channel to send notifications (default: current channel)",
    )
    @app_commands.choices(event=EVENT_CHOICES)
    @app_commands.default_permissions(manage_guild=True)
    async def subscribe(
        self,
        interaction: discord.Interaction,
        repository: str,
        event: str,
        channel: discord.TextChannel = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        if not interaction.guild:
            return await interaction.followup.send("This command must be used in a server.", ephemeral=True)

        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)), ephemeral=True)

        # Verify repo exists
        try:
            await self._gh(interaction.user.id).get_repo(owner, repo)
        except NotFound:
            return await interaction.followup.send(
                embed=build_error_embed("Not Found", f"Repository `{repository}` was not found."), ephemeral=True
            )
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)), ephemeral=True)

        target_channel = channel or interaction.channel
        await self.bot.db.ensure_guild(interaction.guild.id, interaction.guild.name)
        await self.bot.db.add_subscription(
            guild_id=interaction.guild.id,
            channel_id=target_channel.id,
            owner=owner,
            repo=repo,
            event_type=event,
        )

        embed = build_success_embed(
            "Subscription Added",
            (
                f"**{Emojis.BELL} {event.replace('_', ' ').title()}** events from "
                f"[`{owner}/{repo}`](https://github.com/{owner}/{repo}) "
                f"will be sent to {target_channel.mention}."
            ),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="unsubscribe", description="Remove a GitHub notification subscription")
    @app_commands.describe(repository="owner/repo", event="Event type to unsubscribe from")
    @app_commands.choices(event=EVENT_CHOICES)
    @app_commands.default_permissions(manage_guild=True)
    async def unsubscribe(
        self, interaction: discord.Interaction, repository: str, event: str
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        if not interaction.guild:
            return await interaction.followup.send("Must be used in a server.", ephemeral=True)

        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)), ephemeral=True)

        removed = await self.bot.db.remove_subscription(interaction.guild.id, owner, repo, event)
        if removed:
            await interaction.followup.send(
                embed=build_success_embed("Unsubscribed", f"Removed `{event}` subscription for `{owner}/{repo}`."),
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                embed=build_error_embed("Not Found", f"No `{event}` subscription found for `{owner}/{repo}`."),
                ephemeral=True,
            )

    @app_commands.command(name="subscriptions", description="List all notification subscriptions in this server")
    async def subscriptions(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        if not interaction.guild:
            return await interaction.followup.send("Must be used in a server.", ephemeral=True)

        subs = await self.bot.db.get_guild_subscriptions(interaction.guild.id)
        if not subs:
            return await interaction.followup.send(
                embed=discord.Embed(
                    description="No subscriptions set up. Use `/subscribe` to add one.",
                    color=Colors.NEUTRAL,
                ),
                ephemeral=True,
            )

        def fmt_sub(s, idx: int) -> str:
            repo = f"{s.owner}/{s.repo}"
            event = s.event_type.replace("_", " ").title()
            channel = f"<#{s.channel_id}>"
            status = "✅" if s.is_active else "⛔"
            return f"`{idx:>2}.` {status} **{event}** from `{repo}` → {channel}"

        embeds = build_list_embeds(
            title=f"{Emojis.BELL} Subscriptions — {interaction.guild.name}",
            items=subs,
            formatter=fmt_sub,
            color=Colors.PRIMARY,
            per_page=10,
        )
        await interaction.followup.send(embed=embeds[0], ephemeral=True)

    @app_commands.command(name="webhooks", description="List webhooks configured for a repository")
    @app_commands.describe(repository="owner/repo")
    async def webhooks(self, interaction: discord.Interaction, repository: str) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)), ephemeral=True)

        try:
            hooks = await self._gh(interaction.user.id).list_repo_webhooks(owner, repo)
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)), ephemeral=True)

        embed = discord.Embed(
            title=f"🔗 Webhooks — {owner}/{repo}",
            color=Colors.NEUTRAL,
        )
        if hooks:
            lines = []
            for i, h in enumerate(hooks):
                url_val = h.get("config", {}).get("url", "N/A")
                events = ", ".join(h.get("events", [])[:5])
                active = "✅" if h.get("active") else "⛔"
                lines.append(
                    f"`{i+1}.` {active} `{url_val[:50]}`\n       Events: {events or 'All'}"
                )
            embed.description = "\n".join(lines)
        else:
            embed.description = "No webhooks configured."
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot) -> None:
    await bot.add_cog(NotificationsCog(bot))

"""
Octobot Admin Cog — Bot administration and diagnostics.
"""
from __future__ import annotations
import platform
import sys
import discord
from discord import app_commands
from discord.ext import commands
from config import Colors, Emojis


class AdminCog(commands.Cog, name="Admin"):
    def __init__(self, bot) -> None:
        self.bot = bot

    async def cog_check(self, ctx: commands.Context) -> bool:
        return await self.bot.is_owner(ctx.author)

    @commands.command(name="reload", hidden=True)
    @commands.is_owner()
    async def reload_extension(self, ctx: commands.Context, extension: str) -> None:
        try:
            await self.bot.reload_extension(f"cogs.{extension}")
            await ctx.reply(f"✅ Reloaded `cogs.{extension}`")
        except Exception as e:
            await ctx.reply(f"❌ Failed: `{e}`")

    @commands.command(name="sync", hidden=True)
    @commands.is_owner()
    async def sync_commands(self, ctx: commands.Context) -> None:
        synced = await self.bot.tree.sync()
        await ctx.reply(f"✅ Synced {len(synced)} global application commands.")

    @commands.command(name="botstats", hidden=True)
    @commands.is_owner()
    async def show_stats(self, ctx: commands.Context) -> None:
        embed = discord.Embed(title=f"{Emojis.BOT} Octobot Diagnostics", color=Colors.PRIMARY)
        embed.add_field(name="⏱️ Uptime", value=self.bot.uptime, inline=True)
        embed.add_field(name="🏠 Guilds", value=str(len(self.bot.guilds)), inline=True)
        embed.add_field(name="👤 Users", value=str(sum(g.member_count or 0 for g in self.bot.guilds)), inline=True)
        embed.add_field(name="🏓 Latency", value=f"{self.bot.latency * 1000:.1f}ms", inline=True)
        embed.add_field(name="🐍 Python", value=sys.version.split()[0], inline=True)
        embed.add_field(name="📦 discord.py", value=discord.__version__, inline=True)

        if self.bot.cache:
            stats = self.bot.cache.stats
            embed.add_field(
                name="💾 Cache",
                value=(
                    f"Size: {stats['size']}/{stats['max_size']}\n"
                    f"Hit Rate: {stats['hit_rate']}%\n"
                    f"Evictions: {stats['evictions']}"
                ),
                inline=True,
            )

        if self.bot.github:
            embed.add_field(
                name="🐙 GitHub API",
                value=(
                    f"Remaining: {self.bot.github._rate_limit_remaining}\n"
                    f"Reset: {self.bot.github._rate_limit_reset or 'N/A'}"
                ),
                inline=True,
            )

        embed.set_footer(text=f"Platform: {platform.system()} {platform.machine()}")
        await ctx.reply(embed=embed)

    @app_commands.command(name="ping", description="Check bot latency")
    async def ping(self, interaction: discord.Interaction) -> None:
        latency_ms = round(self.bot.latency * 1000)
        color = Colors.SUCCESS if latency_ms < 100 else (Colors.WARNING if latency_ms < 300 else Colors.DANGER)
        embed = discord.Embed(
            description=f"🏓 **Pong!** `{latency_ms}ms`",
            color=color,
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="rate-limit", description="Check GitHub API rate limit status")
    async def rate_limit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            data = await self.bot.get_github_client_for(interaction.user.id).get_rate_limit()
        except Exception as e:
            return await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

        core = data.get("resources", {}).get("core", {})
        search = data.get("resources", {}).get("search", {})
        graphql = data.get("resources", {}).get("graphql", {})

        embed = discord.Embed(title="🔢 GitHub API Rate Limits", color=Colors.INFO)

        for name, resource in [("Core", core), ("Search", search), ("GraphQL", graphql)]:
            remaining = resource.get("remaining", 0)
            limit = resource.get("limit", 0)
            pct = remaining / max(1, limit) * 100
            bar_fill = round(pct / 10)
            bar = "█" * bar_fill + "░" * (10 - bar_fill)
            embed.add_field(
                name=f"📊 {name}",
                value=f"`{bar}` {remaining}/{limit} ({pct:.0f}%)",
                inline=False,
            )

        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="botinfo", description="Show Octobot information and statistics")
    async def botinfo(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title=f"{Emojis.BOT} Octobot — GitHub for Discord",
            description=(
                "Octobot is an enterprise-grade GitHub companion for Discord. "
                "It provides comprehensive GitHub integration with advanced analytics, "
                "real-time notifications, and stunning visualizations."
            ),
            color=Colors.PRIMARY,
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.add_field(name="⏱️ Uptime", value=self.bot.uptime, inline=True)
        embed.add_field(name="🏠 Servers", value=str(len(self.bot.guilds)), inline=True)
        embed.add_field(name="🏓 Latency", value=f"{self.bot.latency*1000:.0f}ms", inline=True)
        embed.add_field(
            name="📊 Features",
            value=(
                "• 80+ Slash Commands\n"
                "• 2D/3D Visualizations\n"
                "• Network & Sankey Graphs\n"
                "• Heatmaps & Treemaps\n"
                "• Real-time Notifications\n"
                "• GitHub API Integration"
            ),
            inline=True,
        )
        embed.add_field(
            name="🔗 Links",
            value=(
                "[GitHub](https://github.com) · "
                "[Discord](https://discord.com) · "
                "[Docs](https://docs.github.com)"
            ),
            inline=True,
        )
        embed.set_footer(text=f"Octobot v2.0 · discord.py {discord.__version__} · Python {sys.version.split()[0]}")
        await interaction.response.send_message(embed=embed)


async def setup(bot) -> None:
    await bot.add_cog(AdminCog(bot))

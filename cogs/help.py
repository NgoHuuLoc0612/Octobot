"""
Octobot Help Cog — Interactive help system with category browsing.
"""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands
from config import Colors, Emojis


COMMAND_CATEGORIES = {
    "🔍 Search": {
        "description": "Search across all of GitHub",
        "commands": [
            ("/search-repos", "Search repositories by keyword, language, stars"),
            ("/search-users", "Search GitHub users by name or criteria"),
            ("/search-issues", "Search issues and pull requests"),
            ("/search-code", "Full-text code search across GitHub"),
            ("/search-commits", "Search commit messages across repos"),
            ("/search-topics", "Search GitHub repository topics"),
        ],
    },
    "📁 Repository": {
        "description": "Explore repository details, files, and history",
        "commands": [
            ("/repo", "Complete repository info (stars, forks, topics, etc.)"),
            ("/branches", "List all branches with protection status"),
            ("/commits", "Browse commit history with filters"),
            ("/commit", "Detailed view of a single commit"),
            ("/contributors", "Top contributors ranked by commits"),
            ("/languages", "Language breakdown with size percentages"),
            ("/topics", "Repository topics and tags"),
            ("/readme", "Render repository README"),
            ("/forks", "List and sort repository forks"),
            ("/compare", "Diff two branches or commits"),
            ("/file", "Preview file content from any ref"),
            ("/stargazers", "Recent users who starred the repo"),
            ("/tags", "List all tags and versions"),
            ("/traffic", "Views, clones, and referrer stats"),
        ],
    },
    "🟢 Issues": {
        "description": "Manage and explore GitHub Issues",
        "commands": [
            ("/issues", "List issues with state, label, and assignee filters"),
            ("/issue", "Detailed issue view with timeline"),
            ("/issue-comments", "Browse all comments on an issue"),
            ("/issue-timeline", "Full chronological event timeline"),
            ("/labels", "All labels with colors and descriptions"),
            ("/milestones", "Milestones with progress bars"),
            ("/milestone", "Detailed milestone view"),
        ],
    },
    "🔵 Pull Requests": {
        "description": "Explore and analyze pull requests",
        "commands": [
            ("/prs", "List PRs with state, base, and sort filters"),
            ("/pr", "Detailed PR view with diff stats"),
            ("/pr-files", "All changed files in a PR"),
            ("/pr-reviews", "Review comments and approvals"),
            ("/pr-commits", "Commits included in a PR"),
            ("/pr-status", "Check merge status and mergability"),
        ],
    },
    "⚡ Actions": {
        "description": "GitHub Actions CI/CD monitoring",
        "commands": [
            ("/workflows", "List all workflows with state"),
            ("/workflow-runs", "Recent runs with status filters"),
            ("/workflow-run", "Detailed run with job breakdown"),
            ("/artifacts", "Download artifacts from runs"),
            ("/secrets", "List repository secret names"),
            ("/variables", "List and preview action variables"),
        ],
    },
    "🚀 Releases": {
        "description": "Repository releases and tags",
        "commands": [
            ("/releases", "Full release history"),
            ("/release", "Latest or specific tagged release"),
        ],
    },
    "👤 Users": {
        "description": "GitHub user profiles and activity",
        "commands": [
            ("/user", "Complete user profile"),
            ("/user-repos", "User's public repositories"),
            ("/user-starred", "Repos starred by user"),
            ("/user-followers", "User's followers list"),
            ("/user-following", "Users they follow"),
            ("/user-events", "Recent public GitHub activity"),
            ("/user-orgs", "Organization memberships"),
            ("/whoami", "Show your linked GitHub account"),
            ("/link-github", "Link your Discord to GitHub"),
            ("/unlink-github", "Remove GitHub account link"),
        ],
    },
    "🏢 Organizations": {
        "description": "GitHub organization commands",
        "commands": [
            ("/org", "Organization profile and stats"),
            ("/org-repos", "Organization repositories"),
            ("/org-members", "Member list with role filter"),
            ("/org-teams", "Teams with member counts"),
        ],
    },
    "📋 Gists": {
        "description": "GitHub Gist exploration",
        "commands": [
            ("/gist", "Show a gist by ID"),
            ("/user-gists", "All public gists by a user"),
            ("/gist-file", "Preview a file inside a gist"),
        ],
    },
    "🔔 Notifications": {
        "description": "Subscribe to repository events",
        "commands": [
            ("/subscribe", "Subscribe a channel to repo events"),
            ("/unsubscribe", "Remove a subscription"),
            ("/subscriptions", "List all active subscriptions"),
            ("/webhooks", "Show configured webhooks"),
        ],
    },
    "📊 Charts (2D)": {
        "description": "Standard charts and graphs",
        "commands": [
            ("/chart-commits", "Weekly commit activity bar chart"),
            ("/chart-languages", "Language distribution pie chart"),
            ("/chart-contributors", "Top contributors bar chart"),
            ("/chart-code-frequency", "Additions/deletions over time"),
            ("/chart-punch-card", "Commit heatmap by day and hour"),
            ("/chart-bubble", "Repo comparison bubble chart"),
            ("/chart-pr-cycle", "PR cycle time scatter plot"),
            ("/chart-label-dist", "Issue label distribution"),
            ("/chart-workflow-status", "CI/CD outcomes pie chart"),
            ("/chart-compare-repos", "Side-by-side repo comparison (up to 4)"),
        ],
    },
    "🧊 Charts (3D)": {
        "description": "Three-dimensional visualizations",
        "commands": [
            ("/chart-3d-commits", "3D commit activity scatter"),
            ("/chart-3d-contributors", "3D contributor activity bars"),
            ("/chart-3d-surface", "3D repository metrics surface"),
            ("/chart-3d-languages", "3D language distribution across repos"),
        ],
    },
    "🌐 Network Graphs": {
        "description": "Graph-based relationship visualizations",
        "commands": [
            ("/graph-forks", "Fork tree network graph"),
            ("/graph-pr-reviews", "PR review relationship network"),
        ],
    },
    "〰️ Sankey Diagrams": {
        "description": "Flow diagrams for GitHub workflows",
        "commands": [
            ("/sankey-prs", "Pull request lifecycle flow"),
            ("/sankey-cicd", "CI/CD pipeline flow"),
            ("/sankey-issues", "Issue triage flow"),
        ],
    },
    "🌡️ Heatmaps & Treemaps": {
        "description": "Density and hierarchical visualizations",
        "commands": [
            ("/heatmap-contributions", "GitHub contribution calendar"),
            ("/heatmap-activity", "Weekly activity heatmap"),
            ("/heatmap-correlation", "Contributor correlation heatmap"),
            ("/treemap-languages", "Language treemap across repos"),
            ("/treemap-topics", "Repository topic treemap"),
        ],
    },
    "⚙️ General": {
        "description": "Bot information and utilities",
        "commands": [
            ("/ping", "Check bot and API latency"),
            ("/botinfo", "Bot statistics and feature list"),
            ("/rate-limit", "View GitHub API rate limit status"),
            ("/help", "This help menu"),
        ],
    },
}


class HelpCategorySelect(discord.ui.Select):
    def __init__(self, categories: list) -> None:
        options = [
            discord.SelectOption(
                label=cat.split(" ", 1)[-1],
                emoji=cat.split(" ", 1)[0],
                value=cat,
                description=COMMAND_CATEGORIES[cat]["description"][:100],
            )
            for cat in categories[:25]
        ]
        super().__init__(
            placeholder="📚 Browse command categories...",
            options=options,
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        cat_name = self.values[0]
        cat_data = COMMAND_CATEGORIES.get(cat_name, {})
        commands_list = cat_data.get("commands", [])

        embed = discord.Embed(
            title=f"{cat_name}",
            description=f"*{cat_data.get('description', '')}*\n\u200b",
            color=Colors.PRIMARY,
        )

        lines = [
            f"`{cmd}` — {desc}"
            for cmd, desc in commands_list
        ]
        # Split into two columns
        mid = (len(lines) + 1) // 2
        if len(lines) > 6:
            embed.add_field(name="Commands", value="\n".join(lines[:mid]), inline=True)
            embed.add_field(name="\u200b", value="\n".join(lines[mid:]), inline=True)
        else:
            embed.add_field(name="Commands", value="\n".join(lines) or "None", inline=False)

        embed.set_footer(text=f"Octobot · {len(lines)} commands in this category")
        await interaction.response.edit_message(embed=embed)


class HelpView(discord.ui.View):
    def __init__(self, author_id: int) -> None:
        super().__init__(timeout=120)
        self.author_id = author_id
        self.add_item(HelpCategorySelect(list(COMMAND_CATEGORIES.keys())))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("Use `/help` yourself to browse.", ephemeral=True)
            return False
        return True

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True


def build_overview_embed(bot) -> discord.Embed:
    """Build the main help overview embed."""
    total_commands = sum(len(v["commands"]) for v in COMMAND_CATEGORIES.values())

    embed = discord.Embed(
        title=f"{Emojis.BOT} Octobot — GitHub for Discord",
        description=(
            "Octobot is your enterprise-grade GitHub companion. "
            "Use the dropdown below to explore all command categories.\n\u200b"
        ),
        color=Colors.PRIMARY,
    )
    embed.set_thumbnail(url=bot.user.display_avatar.url)

    # Quick overview fields
    embed.add_field(
        name="📁 Core Features",
        value=(
            "• Repositories, Issues, PRs\n"
            "• GitHub Actions & Releases\n"
            "• Users, Orgs & Gists\n"
            "• Full-text Code Search"
        ),
        inline=True,
    )
    embed.add_field(
        name="📊 Visualizations",
        value=(
            "• 2D/3D Charts & Graphs\n"
            "• Sankey Flow Diagrams\n"
            "• Network Graphs\n"
            "• Heatmaps & Treemaps"
        ),
        inline=True,
    )
    embed.add_field(
        name="🔔 Integrations",
        value=(
            "• Event Subscriptions\n"
            "• Webhook Management\n"
            "• GitHub Account Linking\n"
            "• Per-User API Tokens"
        ),
        inline=True,
    )

    embed.add_field(
        name="\u200b",
        value=(
            f"**{total_commands}+ commands** across **{len(COMMAND_CATEGORIES)} categories**\n"
            f"Use the dropdown below to explore each category."
        ),
        inline=False,
    )

    embed.set_footer(text="Octobot v2.0 · Use /botinfo for system stats")
    return embed


class HelpCog(commands.Cog, name="Help"):
    """Help and documentation commands."""

    def __init__(self, bot) -> None:
        self.bot = bot

    @app_commands.command(name="help", description="Browse all Octobot commands by category")
    async def help_command(self, interaction: discord.Interaction) -> None:
        embed = build_overview_embed(self.bot)
        view = HelpView(interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="quickstart", description="Quick guide to getting started with Octobot")
    async def quickstart(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title="🚀 Octobot Quickstart Guide",
            color=Colors.SUCCESS,
        )
        embed.add_field(
            name="1️⃣ Link Your Account",
            value=(
                "Use `/link-github <your-username>` to connect your GitHub account.\n"
                "This enables personalized results and higher API limits."
            ),
            inline=False,
        )
        embed.add_field(
            name="2️⃣ Explore a Repository",
            value=(
                "Try `/repo torvalds/linux` to see a repo overview.\n"
                "Then use `/commits`, `/issues`, or `/prs` to dive deeper."
            ),
            inline=False,
        )
        embed.add_field(
            name="3️⃣ Set Up Notifications",
            value=(
                "Use `/subscribe owner/repo push #channel` to get push notifications.\n"
                "Supports: push, issues, pull_request, release, star, fork, workflow_run."
            ),
            inline=False,
        )
        embed.add_field(
            name="4️⃣ Generate Visualizations",
            value=(
                "Try `/chart-commits owner/repo` for a commit activity chart.\n"
                "Or `/heatmap-contributions username` for a contribution calendar."
            ),
            inline=False,
        )
        embed.add_field(
            name="5️⃣ Search GitHub",
            value=(
                "Use `/search-repos query` to find repositories.\n"
                "Supports full GitHub search syntax: `language:python stars:>1000`"
            ),
            inline=False,
        )
        embed.set_footer(text="Use /help to see all available commands.")
        await interaction.response.send_message(embed=embed)


async def setup(bot) -> None:
    await bot.add_cog(HelpCog(bot))

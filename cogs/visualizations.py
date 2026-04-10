"""
Octobot Visualizations Cog — Rich chart and graph commands for GitHub data.
"""

from __future__ import annotations

import asyncio
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from config import Colors, Emojis
from utils.embeds import build_error_embed, build_loading_embed
from utils.helpers import parse_owner_repo
from utils.github_client import GitHubAPIError, NotFound
from visualizations.base import figure_to_discord_file
from visualizations.charts_2d import (
    CommitActivityChart,
    LanguagePieChart,
    ContributorBarChart,
    CodeFrequencyChart,
    StarsHistoryChart,
    RepoBubbleChart,
    PRCycleTimeScatter,
    LabelDistributionChart,
    MultiRepoComparisonChart,
    WorkflowStatusChart,
    PunchCardChart,
)
from visualizations.charts_3d import (
    CommitHistory3DChart,
    ContributorActivity3D,
    RepoMetricsSurface3D,
    LanguageEvolution3D,
)
from visualizations.network_graph import (
    ForkNetworkChart,
    ContributorNetworkChart,
    DependencyNetworkChart,
    PRReviewNetworkChart,
)
from visualizations.sankey import (
    PRFlowSankey,
    CICDPipelineSankey,
    ContributionFlowSankey,
    IssuetriageSankey,
)
from visualizations.heatmaps import (
    ContributionHeatmap,
    WeeklyActivityHeatmap,
    LanguageTreemap,
    RepoTopicTreemap,
    CommitCorrelationHeatmap,
)


class VisualizationsCog(commands.Cog, name="Visualizations"):
    """Comprehensive data visualization commands for GitHub analytics."""

    def __init__(self, bot) -> None:
        self.bot = bot

    def _gh(self, user_id: int):
        return self.bot.get_github_client_for(user_id)

    async def _send_chart(
        self,
        interaction: discord.Interaction,
        file: discord.File,
        title: str,
        description: str = "",
        color: int = Colors.PRIMARY,
    ) -> None:
        embed = discord.Embed(title=title, description=description, color=color)
        embed.set_image(url=f"attachment://{file.filename}")
        embed.set_footer(text="Octobot Analytics · Powered by Plotly")
        await interaction.followup.send(embed=embed, file=file)

    # ─── 2D Charts ────────────────────────────────────────────────────────

    @app_commands.command(name="chart-commits", description="Bar chart of weekly commit activity")
    @app_commands.describe(repository="owner/repo")
    async def chart_commits(self, interaction: discord.Interaction, repository: str) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))

        try:
            data = await self._gh(interaction.user.id).get_commit_activity(owner, repo)
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        chart = CommitActivityChart(
            title=f"📝 Weekly Commits — {owner}/{repo}", width=1000, height=450
        )
        file = await chart.to_discord_file(data or [], "commit_activity.png")
        await self._send_chart(
            interaction, file,
            title=f"📊 Commit Activity — {owner}/{repo}",
            description=f"Weekly commit history for the last 52 weeks.",
            color=Colors.PRIMARY,
        )

    @app_commands.command(name="chart-languages", description="Pie chart of repository language breakdown")
    @app_commands.describe(repository="owner/repo")
    async def chart_languages(self, interaction: discord.Interaction, repository: str) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))

        try:
            data = await self._gh(interaction.user.id).get_repo_languages(owner, repo)
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        chart = LanguagePieChart(title=f"🗣️ Languages — {owner}/{repo}", width=900, height=500)
        file = await chart.to_discord_file(data or {}, "language_pie.png")
        await self._send_chart(
            interaction, file,
            title=f"🗣️ Language Distribution — {owner}/{repo}",
            color=Colors.SECONDARY,
        )

    @app_commands.command(name="chart-contributors", description="Bar chart of top contributors")
    @app_commands.describe(repository="owner/repo")
    async def chart_contributors(self, interaction: discord.Interaction, repository: str) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))

        try:
            data = await self._gh(interaction.user.id).get_contributor_stats(owner, repo)
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        chart = ContributorBarChart(title=f"👥 Contributors — {owner}/{repo}", width=900, height=500)
        file = await chart.to_discord_file(data or [], "contributors.png")
        await self._send_chart(
            interaction, file,
            title=f"👥 Top Contributors — {owner}/{repo}",
            color=Colors.PRIMARY,
        )

    @app_commands.command(name="chart-code-frequency", description="Code additions/deletions over time")
    @app_commands.describe(repository="owner/repo")
    async def chart_code_freq(self, interaction: discord.Interaction, repository: str) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))

        try:
            data = await self._gh(interaction.user.id).get_code_frequency(owner, repo)
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        chart = CodeFrequencyChart(title=f"📊 Code Frequency — {owner}/{repo}", width=1000, height=450)
        file = await chart.to_discord_file(data or [], "code_freq.png")
        await self._send_chart(
            interaction, file,
            title=f"📊 Code Additions & Deletions — {owner}/{repo}",
            description="Weekly code changes over the last year.",
            color=Colors.SECONDARY,
        )

    @app_commands.command(name="chart-punch-card", description="Commit punch card by day and hour")
    @app_commands.describe(repository="owner/repo")
    async def chart_punch_card(self, interaction: discord.Interaction, repository: str) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))

        try:
            data = await self._gh(interaction.user.id).get_punch_card(owner, repo)
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        chart = PunchCardChart(title=f"🕐 Punch Card — {owner}/{repo}", width=1000, height=380)
        file = await chart.to_discord_file(data or [], "punch_card.png")
        await self._send_chart(
            interaction, file,
            title=f"🕐 Commit Punch Card — {owner}/{repo}",
            description="Commit frequency by day of week and hour (UTC).",
            color=Colors.INFO,
        )

    @app_commands.command(name="chart-bubble", description="Bubble chart comparing user repositories")
    @app_commands.describe(username="GitHub username to analyze")
    async def chart_bubble(self, interaction: discord.Interaction, username: str) -> None:
        await interaction.response.defer()
        try:
            repos = await self._gh(interaction.user.id).list_user_repos(
                username, sort="stars", max_results=30
            )
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        chart = RepoBubbleChart(title=f"🫧 Repository Comparison — @{username}", width=1000, height=550)
        file = await chart.to_discord_file(repos, "bubble_chart.png")
        await self._send_chart(
            interaction, file,
            title=f"🫧 Repository Bubble Chart — @{username}",
            description="X = Stars · Y = Forks · Size = Open Issues · Color = Language",
            color=Colors.SECONDARY,
        )

    @app_commands.command(name="chart-pr-cycle", description="Scatter: PR cycle time vs size")
    @app_commands.describe(repository="owner/repo")
    async def chart_pr_cycle(self, interaction: discord.Interaction, repository: str) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))

        try:
            prs = await self._gh(interaction.user.id).get_pull_requests(
                owner, repo, state="closed", max_results=100
            )
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        chart = PRCycleTimeScatter(title=f"🔵 PR Cycle Time — {owner}/{repo}", width=1000, height=520)
        file = await chart.to_discord_file(prs, "pr_cycle.png")
        await self._send_chart(
            interaction, file,
            title=f"🔵 PR Cycle Time vs Size — {owner}/{repo}",
            description="Each dot represents a closed PR. X = total lines changed, Y = days to close.",
            color=Colors.MERGED,
        )

    @app_commands.command(name="chart-label-dist", description="Bar chart of issue label distribution")
    @app_commands.describe(repository="owner/repo")
    async def chart_label_dist(self, interaction: discord.Interaction, repository: str) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))

        try:
            issues = await self._gh(interaction.user.id).get_issues(
                owner, repo, state="all", max_results=200
            )
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        chart = LabelDistributionChart(title=f"🏷️ Label Distribution — {owner}/{repo}", width=900, height=500)
        file = await chart.to_discord_file(issues, "label_dist.png")
        await self._send_chart(
            interaction, file,
            title=f"🏷️ Issue Label Distribution — {owner}/{repo}",
            color=Colors.SECONDARY,
        )

    @app_commands.command(name="chart-workflow-status", description="Pie chart of workflow run outcomes")
    @app_commands.describe(repository="owner/repo", workflow="Workflow name or ID (optional)")
    async def chart_workflow_status(
        self, interaction: discord.Interaction, repository: str, workflow: str = None
    ) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))

        try:
            runs = await self._gh(interaction.user.id).get_workflow_runs(
                owner, repo, workflow_id=workflow, max_results=100
            )
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        chart = WorkflowStatusChart(title=f"⚡ Workflow Outcomes — {owner}/{repo}", width=800, height=500)
        file = await chart.to_discord_file(runs, "workflow_status.png")
        await self._send_chart(
            interaction, file,
            title=f"⚡ CI/CD Run Outcomes — {owner}/{repo}",
            description=f"Based on last {len(runs)} workflow runs.",
            color=Colors.SUCCESS,
        )

    # ─── 3D Charts ────────────────────────────────────────────────────────

    @app_commands.command(name="chart-3d-commits", description="3D scatter of commit activity over time")
    @app_commands.describe(repository="owner/repo")
    async def chart_3d_commits(self, interaction: discord.Interaction, repository: str) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))

        try:
            data = await self._gh(interaction.user.id).get_commit_activity(owner, repo)
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        chart = CommitHistory3DChart(title=f"🧊 3D Commit History — {owner}/{repo}", width=1000, height=600)
        file = await chart.to_discord_file(data or [], "commits_3d.png")
        await self._send_chart(
            interaction, file,
            title=f"🧊 3D Commit Activity — {owner}/{repo}",
            description="X = Week · Y = Day · Z = Commits",
            color=Colors.PRIMARY,
        )

    @app_commands.command(name="chart-3d-contributors", description="3D bar chart of contributor activity")
    @app_commands.describe(repository="owner/repo")
    async def chart_3d_contributors(self, interaction: discord.Interaction, repository: str) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))

        try:
            data = await self._gh(interaction.user.id).get_contributor_stats(owner, repo)
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        chart = ContributorActivity3D(
            title=f"🧊 3D Contributor Activity — {owner}/{repo}", width=1000, height=600
        )
        file = await chart.to_discord_file(data or [], "contrib_3d.png")
        await self._send_chart(
            interaction, file,
            title=f"🧊 3D Contributor Activity — {owner}/{repo}",
            description="X = Contributor · Y = Week · Z = Commits",
            color=Colors.PURPLE,
        )

    @app_commands.command(name="chart-3d-surface", description="3D surface chart of repo metrics")
    @app_commands.describe(username="GitHub username to analyze")
    async def chart_3d_surface(self, interaction: discord.Interaction, username: str) -> None:
        await interaction.response.defer()
        try:
            repos = await self._gh(interaction.user.id).list_user_repos(
                username, sort="stars", max_results=50
            )
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        if len(repos) < 4:
            return await interaction.followup.send(
                embed=build_error_embed("Insufficient Data", f"@{username} needs at least 4 repositories.")
            )

        chart = RepoMetricsSurface3D(
            title=f"🧊 3D Repo Surface — @{username}", width=1000, height=620
        )
        file = await chart.to_discord_file(repos, "surface_3d.png")
        await self._send_chart(
            interaction, file,
            title=f"🧊 3D Repository Metrics Surface — @{username}",
            description="Stars × Forks × Open Issues interpolated surface.",
            color=Colors.SECONDARY,
        )

    @app_commands.command(name="chart-3d-languages", description="3D language evolution across repositories")
    @app_commands.describe(username="GitHub username")
    async def chart_3d_languages(self, interaction: discord.Interaction, username: str) -> None:
        await interaction.response.defer()
        try:
            repos = await self._gh(interaction.user.id).list_user_repos(
                username, sort="updated", max_results=15
            )
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        gh = self._gh(interaction.user.id)
        repo_languages = {}
        tasks = []
        for r in repos[:12]:
            owner_login = r.get("owner", {}).get("login", username)
            repo_name = r.get("name", "")
            tasks.append(gh.get_repo_languages(owner_login, repo_name))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r, result in zip(repos[:12], results):
            if isinstance(result, dict):
                repo_languages[r.get("name", "?")] = result

        chart = LanguageEvolution3D(
            title=f"🧊 3D Language Evolution — @{username}", width=1100, height=650
        )
        file = await chart.to_discord_file(repo_languages, "lang_3d.png")
        await self._send_chart(
            interaction, file,
            title=f"🧊 3D Language Distribution — @{username}",
            description="Languages across the top repositories.",
            color=Colors.ORANGE,
        )

    # ─── Network Graphs ───────────────────────────────────────────────────

    @app_commands.command(name="graph-forks", description="Network graph of repository forks")
    @app_commands.describe(repository="owner/repo")
    async def graph_forks(self, interaction: discord.Interaction, repository: str) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))

        try:
            repo_data = await self._gh(interaction.user.id).get_repo(owner, repo)
            forks = await self._gh(interaction.user.id).get_repo_forks(owner, repo, max_results=50)
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        data = {
            "root": {
                "name": repo_data.get("name"),
                "stars": repo_data.get("stargazers_count", 0),
            },
            "forks": forks,
        }

        chart = ForkNetworkChart(title=f"🍴 Fork Network — {owner}/{repo}", width=1100, height=700)
        file = await chart.to_discord_file(data, "fork_network.png")
        await self._send_chart(
            interaction, file,
            title=f"🌐 Fork Network — {owner}/{repo}",
            description=f"Network of {len(forks)} forks. Node size = stars.",
            color=Colors.SECONDARY,
        )

    @app_commands.command(name="graph-pr-reviews", description="Network graph of PR review relationships")
    @app_commands.describe(repository="owner/repo")
    async def graph_pr_reviews(self, interaction: discord.Interaction, repository: str) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))

        try:
            prs = await self._gh(interaction.user.id).get_pull_requests(
                owner, repo, state="closed", max_results=50
            )
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        # Fetch reviews for each PR
        gh = self._gh(interaction.user.id)
        tasks = [gh.get_pr_reviews(owner, repo, pr.get("number", 0)) for pr in prs[:20]]
        review_results = await asyncio.gather(*tasks, return_exceptions=True)

        enriched = []
        for pr, reviews in zip(prs[:20], review_results):
            p = dict(pr)
            p["reviews"] = reviews if isinstance(reviews, list) else []
            enriched.append(p)

        chart = PRReviewNetworkChart(title=f"🌐 PR Review Network — {owner}/{repo}", width=1000, height=700)
        file = await chart.to_discord_file(enriched, "pr_network.png")
        await self._send_chart(
            interaction, file,
            title=f"🌐 PR Review Network — {owner}/{repo}",
            description="Edges represent review relationships. Thicker = more reviews.",
            color=Colors.MERGED,
        )

    # ─── Sankey Diagrams ──────────────────────────────────────────────────

    @app_commands.command(name="sankey-prs", description="Sankey diagram of pull request lifecycle")
    @app_commands.describe(repository="owner/repo")
    async def sankey_prs(self, interaction: discord.Interaction, repository: str) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))

        try:
            all_prs = await self._gh(interaction.user.id).get_pull_requests(
                owner, repo, state="all", max_results=200
            )
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        open_count = sum(1 for p in all_prs if p.get("state") == "open")
        merged_count = sum(1 for p in all_prs if p.get("merged_at"))
        closed_count = sum(1 for p in all_prs if p.get("state") == "closed" and not p.get("merged_at"))

        data = {
            "total": len(all_prs),
            "open": open_count,
            "merged": merged_count,
            "closed": closed_count,
            "approved": int(merged_count * 0.9),
            "changes_requested": int(merged_count * 0.3),
        }

        chart = PRFlowSankey(title=f"〰️ PR Flow — {owner}/{repo}", width=1000, height=550)
        file = await chart.to_discord_file(data, "sankey_prs.png")
        await self._send_chart(
            interaction, file,
            title=f"〰️ Pull Request Lifecycle Flow — {owner}/{repo}",
            description=f"Based on {len(all_prs)} pull requests.",
            color=Colors.MERGED,
        )

    @app_commands.command(name="sankey-cicd", description="Sankey diagram of CI/CD pipeline flow")
    @app_commands.describe(repository="owner/repo")
    async def sankey_cicd(self, interaction: discord.Interaction, repository: str) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))

        try:
            runs = await self._gh(interaction.user.id).get_workflow_runs(owner, repo, max_results=100)
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        chart = CICDPipelineSankey(title=f"〰️ CI/CD Flow — {owner}/{repo}", width=1100, height=550)
        file = await chart.to_discord_file(runs, "sankey_cicd.png")
        await self._send_chart(
            interaction, file,
            title=f"〰️ CI/CD Pipeline Flow — {owner}/{repo}",
            description=f"Based on {len(runs)} workflow runs.",
            color=Colors.SUCCESS,
        )

    @app_commands.command(name="sankey-issues", description="Sankey diagram of issue triage flow")
    @app_commands.describe(repository="owner/repo")
    async def sankey_issues(self, interaction: discord.Interaction, repository: str) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))

        try:
            issues = await self._gh(interaction.user.id).get_issues(
                owner, repo, state="all", max_results=200
            )
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        chart = IssuetriageSankey(title=f"〰️ Issue Triage — {owner}/{repo}", width=1000, height=520)
        file = await chart.to_discord_file(issues, "sankey_issues.png")
        await self._send_chart(
            interaction, file,
            title=f"〰️ Issue Triage Flow — {owner}/{repo}",
            description=f"Based on {len(issues)} issues.",
            color=Colors.PRIMARY,
        )

    # ─── Heatmaps ─────────────────────────────────────────────────────────

    @app_commands.command(name="heatmap-contributions", description="GitHub-style contribution calendar heatmap")
    @app_commands.describe(username="GitHub username", year="Year to show (default: current year)")
    async def heatmap_contributions(
        self, interaction: discord.Interaction, username: str, year: int = None
    ) -> None:
        await interaction.response.defer()
        try:
            data = await self._gh(interaction.user.id).get_user_contributions(username, year)
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        chart = ContributionHeatmap(
            title=f"🌡️ Contributions — @{username} ({year or 'This Year'})",
            width=1100, height=320,
        )
        file = await chart.to_discord_file(data, "contribution_heatmap.png")

        calendar = (
            data.get("user", {})
            .get("contributionsCollection", {})
            .get("contributionCalendar", {})
        )
        total = calendar.get("totalContributions", "?")

        await self._send_chart(
            interaction, file,
            title=f"🌡️ Contribution Calendar — @{username}",
            description=f"**{total}** total contributions this year.",
            color=Colors.SUCCESS,
        )

    @app_commands.command(name="heatmap-activity", description="Weekly activity heatmap (events by day/hour)")
    @app_commands.describe(username="GitHub username")
    async def heatmap_activity(self, interaction: discord.Interaction, username: str) -> None:
        await interaction.response.defer()
        try:
            events = await self._gh(interaction.user.id).get_user_events(username, max_results=100)
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        chart = WeeklyActivityHeatmap(
            title=f"🌡️ Weekly Activity — @{username}", width=1000, height=380
        )
        file = await chart.to_discord_file(events, "activity_heatmap.png")
        await self._send_chart(
            interaction, file,
            title=f"🌡️ Activity Heatmap — @{username}",
            description="GitHub event frequency by day of week and hour (UTC).",
            color=Colors.SECONDARY,
        )

    @app_commands.command(name="treemap-languages", description="Treemap of language distribution across repos")
    @app_commands.describe(username="GitHub username")
    async def treemap_languages(self, interaction: discord.Interaction, username: str) -> None:
        await interaction.response.defer()
        try:
            repos = await self._gh(interaction.user.id).list_user_repos(username, max_results=20)
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        gh = self._gh(interaction.user.id)
        tasks = [
            gh.get_repo_languages(r.get("owner", {}).get("login", username), r.get("name", ""))
            for r in repos[:15]
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        repo_languages = {}
        for r, result in zip(repos[:15], results):
            if isinstance(result, dict):
                repo_languages[r.get("name", "?")] = result

        chart = LanguageTreemap(
            title=f"🗺️ Language Treemap — @{username}", width=1100, height=650
        )
        file = await chart.to_discord_file(repo_languages, "lang_treemap.png")
        await self._send_chart(
            interaction, file,
            title=f"🗺️ Language Distribution Treemap — @{username}",
            description="Hierarchical view: Language → Repository → Code size.",
            color=Colors.SECONDARY,
        )

    @app_commands.command(name="treemap-topics", description="Treemap of repos grouped by topic")
    @app_commands.describe(username="GitHub username")
    async def treemap_topics(self, interaction: discord.Interaction, username: str) -> None:
        await interaction.response.defer()
        try:
            repos = await self._gh(interaction.user.id).list_user_repos(
                username, sort="stars", max_results=50
            )
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        chart = RepoTopicTreemap(
            title=f"🗺️ Topic Treemap — @{username}", width=1100, height=650
        )
        file = await chart.to_discord_file(repos, "topic_treemap.png")
        await self._send_chart(
            interaction, file,
            title=f"🗺️ Repository Topic Treemap — @{username}",
            description="Repositories grouped by their GitHub topics.",
            color=Colors.PURPLE,
        )

    @app_commands.command(name="heatmap-correlation", description="Contributor commit pattern correlation heatmap")
    @app_commands.describe(repository="owner/repo")
    async def heatmap_correlation(self, interaction: discord.Interaction, repository: str) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))

        try:
            data = await self._gh(interaction.user.id).get_contributor_stats(owner, repo)
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        if not data or len(data) < 2:
            return await interaction.followup.send(
                embed=build_error_embed("Insufficient Data", "Need at least 2 contributors for correlation.")
            )

        chart = CommitCorrelationHeatmap(
            title=f"🌡️ Commit Correlation — {owner}/{repo}", width=900, height=600
        )
        file = await chart.to_discord_file(data, "correlation_heatmap.png")
        await self._send_chart(
            interaction, file,
            title=f"🌡️ Contributor Commit Pattern Correlation — {owner}/{repo}",
            description="Green = positive correlation, Red = negative correlation.",
            color=Colors.INFO,
        )

    @app_commands.command(name="chart-compare-repos", description="Compare multiple repos side by side")
    @app_commands.describe(
        repo1="First repo (owner/repo)",
        repo2="Second repo (owner/repo)",
        repo3="Third repo (optional)",
        repo4="Fourth repo (optional)",
    )
    async def chart_compare_repos(
        self,
        interaction: discord.Interaction,
        repo1: str,
        repo2: str,
        repo3: str = None,
        repo4: str = None,
    ) -> None:
        await interaction.response.defer()
        repo_strings = [r for r in [repo1, repo2, repo3, repo4] if r]
        repos_data = []
        gh = self._gh(interaction.user.id)

        for repo_str in repo_strings:
            try:
                owner, repo = parse_owner_repo(repo_str)
                data = await gh.get_repo(owner, repo)
                repos_data.append(data)
            except (ValueError, NotFound, GitHubAPIError) as e:
                return await interaction.followup.send(
                    embed=build_error_embed("Error", f"Failed to fetch `{repo_str}`: {e}")
                )

        chart = MultiRepoComparisonChart(
            title=f"📊 Repository Comparison",
            width=1000, height=500
        )
        file = await chart.to_discord_file(repos_data, "repo_compare.png")
        names = ", ".join(r.get("full_name", "?") for r in repos_data)
        await self._send_chart(
            interaction, file,
            title=f"📊 Repository Comparison",
            description=f"Comparing: {names}",
            color=Colors.PRIMARY,
        )


async def setup(bot) -> None:
    await bot.add_cog(VisualizationsCog(bot))

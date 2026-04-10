"""
Octobot Visualizations Cog — Rich chart and graph commands for GitHub data.

Commands are organized into 4 groups to stay within Discord's 100-command limit:
  /chart   — 2D charts
  /chart3d — 3D charts
  /graph   — Network graphs
  /visual  — Heatmaps, treemaps, sankeys
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


async def _send_chart(interaction, file, title, description="", color=Colors.PRIMARY):
    embed = discord.Embed(title=title, description=description, color=color)
    embed.set_image(url=f"attachment://{file.filename}")
    embed.set_footer(text="Octobot Analytics · Powered by Plotly")
    await interaction.followup.send(embed=embed, file=file)


class VisualizationsCog(commands.Cog, name="Visualizations"):
    """Comprehensive data visualization commands for GitHub analytics."""

    def __init__(self, bot) -> None:
        self.bot = bot

    def _gh(self, user_id: int):
        return self.bot.get_github_client_for(user_id)

    # ── /chart group ──────────────────────────────────────────────────────

    chart = app_commands.Group(name="chart", description="2D charts for GitHub analytics")

    @chart.command(name="commits", description="Bar chart of weekly commit activity")
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
        chart = CommitActivityChart(title=f"📝 Weekly Commits — {owner}/{repo}", width=1000, height=450)
        file = await chart.to_discord_file(data or [], "commit_activity.png")
        await _send_chart(interaction, file, f"📊 Commit Activity — {owner}/{repo}",
                          "Weekly commit history for the last 52 weeks.", Colors.PRIMARY)

    @chart.command(name="languages", description="Pie chart of repository language breakdown")
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
        await _send_chart(interaction, file, f"🗣️ Language Distribution — {owner}/{repo}", color=Colors.SECONDARY)

    @chart.command(name="contributors", description="Bar chart of top contributors")
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
        await _send_chart(interaction, file, f"👥 Top Contributors — {owner}/{repo}", color=Colors.PRIMARY)

    @chart.command(name="code-freq", description="Code additions/deletions over time")
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
        await _send_chart(interaction, file, f"📊 Code Additions & Deletions — {owner}/{repo}",
                          "Weekly code changes over the last year.", Colors.SECONDARY)

    @chart.command(name="punch-card", description="Commit punch card by day and hour")
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
        await _send_chart(interaction, file, f"🕐 Commit Punch Card — {owner}/{repo}",
                          "Commit frequency by day of week and hour (UTC).", Colors.INFO)

    @chart.command(name="bubble", description="Bubble chart comparing user repositories")
    @app_commands.describe(username="GitHub username to analyze")
    async def chart_bubble(self, interaction: discord.Interaction, username: str) -> None:
        await interaction.response.defer()
        try:
            repos = await self._gh(interaction.user.id).list_user_repos(username, sort="stars", max_results=30)
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))
        chart = RepoBubbleChart(title=f"🫧 Repository Comparison — @{username}", width=1000, height=550)
        file = await chart.to_discord_file(repos, "bubble_chart.png")
        await _send_chart(interaction, file, f"🫧 Repository Bubble Chart — @{username}",
                          "X = Stars · Y = Forks · Size = Open Issues · Color = Language", Colors.SECONDARY)

    @chart.command(name="pr-cycle", description="Scatter plot of PR cycle time vs size")
    @app_commands.describe(repository="owner/repo")
    async def chart_pr_cycle(self, interaction: discord.Interaction, repository: str) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))
        try:
            prs = await self._gh(interaction.user.id).get_pull_requests(owner, repo, state="closed", max_results=100)
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))
        chart = PRCycleTimeScatter(title=f"🔵 PR Cycle Time — {owner}/{repo}", width=1000, height=520)
        file = await chart.to_discord_file(prs, "pr_cycle.png")
        await _send_chart(interaction, file, f"🔵 PR Cycle Time vs Size — {owner}/{repo}",
                          "Each dot represents a closed PR. X = total lines changed, Y = days to close.",
                          Colors.MERGED)

    @chart.command(name="labels", description="Bar chart of issue label distribution")
    @app_commands.describe(repository="owner/repo")
    async def chart_label_dist(self, interaction: discord.Interaction, repository: str) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))
        try:
            issues = await self._gh(interaction.user.id).get_issues(owner, repo, state="all", max_results=200)
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))
        chart = LabelDistributionChart(title=f"🏷️ Label Distribution — {owner}/{repo}", width=900, height=500)
        file = await chart.to_discord_file(issues, "label_dist.png")
        await _send_chart(interaction, file, f"🏷️ Issue Label Distribution — {owner}/{repo}",
                          color=Colors.SECONDARY)

    @chart.command(name="workflows", description="Pie chart of workflow run outcomes")
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
                owner, repo, workflow_id=workflow, max_results=100)
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))
        chart = WorkflowStatusChart(title=f"⚡ Workflow Outcomes — {owner}/{repo}", width=800, height=500)
        file = await chart.to_discord_file(runs, "workflow_status.png")
        await _send_chart(interaction, file, f"⚡ CI/CD Run Outcomes — {owner}/{repo}",
                          f"Based on last {len(runs)} workflow runs.", Colors.SUCCESS)

    @chart.command(name="compare", description="Compare multiple repos side by side (up to 4)")
    @app_commands.describe(repo1="First repo (owner/repo)", repo2="Second repo (owner/repo)",
                           repo3="Third repo (optional)", repo4="Fourth repo (optional)")
    async def chart_compare_repos(
        self, interaction: discord.Interaction,
        repo1: str, repo2: str, repo3: str = None, repo4: str = None,
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
                    embed=build_error_embed("Error", f"Failed to fetch `{repo_str}`: {e}"))
        chart = MultiRepoComparisonChart(title="📊 Repository Comparison", width=1000, height=500)
        file = await chart.to_discord_file(repos_data, "repo_compare.png")
        names = ", ".join(r.get("full_name", "?") for r in repos_data)
        await _send_chart(interaction, file, "📊 Repository Comparison",
                          f"Comparing: {names}", Colors.PRIMARY)

    # ── /chart3d group ────────────────────────────────────────────────────

    chart3d = app_commands.Group(name="chart3d", description="3D visualization charts for GitHub analytics")

    @chart3d.command(name="commits", description="3D scatter of commit activity over time")
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
        await _send_chart(interaction, file, f"🧊 3D Commit Activity — {owner}/{repo}",
                          "X = Week · Y = Day · Z = Commits", Colors.PRIMARY)

    @chart3d.command(name="contributors", description="3D bar chart of contributor activity")
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
        chart = ContributorActivity3D(title=f"🧊 3D Contributor Activity — {owner}/{repo}", width=1000, height=600)
        file = await chart.to_discord_file(data or [], "contrib_3d.png")
        await _send_chart(interaction, file, f"🧊 3D Contributor Activity — {owner}/{repo}",
                          "X = Contributor · Y = Week · Z = Commits", Colors.PURPLE)

    @chart3d.command(name="surface", description="3D surface chart of repository metrics")
    @app_commands.describe(username="GitHub username to analyze")
    async def chart_3d_surface(self, interaction: discord.Interaction, username: str) -> None:
        await interaction.response.defer()
        try:
            repos = await self._gh(interaction.user.id).list_user_repos(username, sort="stars", max_results=50)
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))
        if len(repos) < 4:
            return await interaction.followup.send(
                embed=build_error_embed("Insufficient Data", f"@{username} needs at least 4 repositories."))
        chart = RepoMetricsSurface3D(title=f"🧊 3D Repo Surface — @{username}", width=1000, height=620)
        file = await chart.to_discord_file(repos, "surface_3d.png")
        await _send_chart(interaction, file, f"🧊 3D Repository Metrics Surface — @{username}",
                          "Stars × Forks × Open Issues interpolated surface.", Colors.SECONDARY)

    @chart3d.command(name="languages", description="3D language evolution across repositories")
    @app_commands.describe(username="GitHub username")
    async def chart_3d_languages(self, interaction: discord.Interaction, username: str) -> None:
        await interaction.response.defer()
        try:
            repos = await self._gh(interaction.user.id).list_user_repos(username, sort="updated", max_results=15)
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))
        gh = self._gh(interaction.user.id)
        tasks = [gh.get_repo_languages(
            r.get("owner", {}).get("login", username), r.get("name", "")) for r in repos[:12]]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        repo_languages = {}
        for r, result in zip(repos[:12], results):
            if isinstance(result, dict):
                repo_languages[r.get("name", "?")] = result
        chart = LanguageEvolution3D(title=f"🧊 3D Language Evolution — @{username}", width=1100, height=650)
        file = await chart.to_discord_file(repo_languages, "lang_3d.png")
        await _send_chart(interaction, file, f"🧊 3D Language Distribution — @{username}",
                          "Languages across the top repositories.", Colors.ORANGE)

    # ── /graph group ──────────────────────────────────────────────────────

    graph = app_commands.Group(name="graph", description="Network graphs for GitHub relationships")

    @graph.command(name="forks", description="Network graph of repository forks")
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
        data = {"root": {"name": repo_data.get("name"), "stars": repo_data.get("stargazers_count", 0)},
                "forks": forks}
        chart = ForkNetworkChart(title=f"🍴 Fork Network — {owner}/{repo}", width=1100, height=700)
        file = await chart.to_discord_file(data, "fork_network.png")
        await _send_chart(interaction, file, f"🌐 Fork Network — {owner}/{repo}",
                          f"Network of {len(forks)} forks. Node size = stars.", Colors.SECONDARY)

    @graph.command(name="pr-reviews", description="Network graph of PR review relationships")
    @app_commands.describe(repository="owner/repo")
    async def graph_pr_reviews(self, interaction: discord.Interaction, repository: str) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))
        try:
            prs = await self._gh(interaction.user.id).get_pull_requests(
                owner, repo, state="closed", max_results=50)
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))
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
        await _send_chart(interaction, file, f"🌐 PR Review Network — {owner}/{repo}",
                          "Edges represent review relationships. Thicker = more reviews.", Colors.MERGED)

    # ── /visual group (heatmaps, treemaps, sankeys) ───────────────────────

    visual = app_commands.Group(name="visual", description="Heatmaps, treemaps, and Sankey diagrams")

    @visual.command(name="contributions", description="GitHub-style contribution calendar heatmap")
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
            title=f"🌡️ Contributions — @{username} ({year or 'This Year'})", width=1100, height=320)
        file = await chart.to_discord_file(data, "contribution_heatmap.png")
        calendar = data.get("user", {}).get("contributionsCollection", {}).get("contributionCalendar", {})
        total = calendar.get("totalContributions", "?")
        await _send_chart(interaction, file, f"🌡️ Contribution Calendar — @{username}",
                          f"**{total}** total contributions this year.", Colors.SUCCESS)

    @visual.command(name="activity", description="Weekly activity heatmap (events by day/hour)")
    @app_commands.describe(username="GitHub username")
    async def heatmap_activity(self, interaction: discord.Interaction, username: str) -> None:
        await interaction.response.defer()
        try:
            events = await self._gh(interaction.user.id).get_user_events(username, max_results=100)
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))
        chart = WeeklyActivityHeatmap(title=f"🌡️ Weekly Activity — @{username}", width=1000, height=380)
        file = await chart.to_discord_file(events, "activity_heatmap.png")
        await _send_chart(interaction, file, f"🌡️ Activity Heatmap — @{username}",
                          "GitHub event frequency by day of week and hour (UTC).", Colors.SECONDARY)

    @visual.command(name="correlation", description="Contributor commit pattern correlation heatmap")
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
                embed=build_error_embed("Insufficient Data", "Need at least 2 contributors for correlation."))
        chart = CommitCorrelationHeatmap(title=f"🌡️ Commit Correlation — {owner}/{repo}", width=900, height=600)
        file = await chart.to_discord_file(data, "correlation_heatmap.png")
        await _send_chart(interaction, file, f"🌡️ Contributor Commit Pattern Correlation — {owner}/{repo}",
                          "Green = positive correlation, Red = negative correlation.", Colors.INFO)

    @visual.command(name="lang-treemap", description="Treemap of language distribution across repos")
    @app_commands.describe(username="GitHub username")
    async def treemap_languages(self, interaction: discord.Interaction, username: str) -> None:
        await interaction.response.defer()
        try:
            repos = await self._gh(interaction.user.id).list_user_repos(username, max_results=20)
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))
        gh = self._gh(interaction.user.id)
        tasks = [gh.get_repo_languages(
            r.get("owner", {}).get("login", username), r.get("name", "")) for r in repos[:15]]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        repo_languages = {}
        for r, result in zip(repos[:15], results):
            if isinstance(result, dict):
                repo_languages[r.get("name", "?")] = result
        chart = LanguageTreemap(title=f"🗺️ Language Treemap — @{username}", width=1100, height=650)
        file = await chart.to_discord_file(repo_languages, "lang_treemap.png")
        await _send_chart(interaction, file, f"🗺️ Language Distribution Treemap — @{username}",
                          "Hierarchical view: Language → Repository → Code size.", Colors.SECONDARY)

    @visual.command(name="topic-treemap", description="Treemap of repos grouped by topic")
    @app_commands.describe(username="GitHub username")
    async def treemap_topics(self, interaction: discord.Interaction, username: str) -> None:
        await interaction.response.defer()
        try:
            repos = await self._gh(interaction.user.id).list_user_repos(username, sort="stars", max_results=50)
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))
        chart = RepoTopicTreemap(title=f"🗺️ Topic Treemap — @{username}", width=1100, height=650)
        file = await chart.to_discord_file(repos, "topic_treemap.png")
        await _send_chart(interaction, file, f"🗺️ Repository Topic Treemap — @{username}",
                          "Repositories grouped by their GitHub topics.", Colors.PURPLE)

    @visual.command(name="sankey-prs", description="Sankey diagram of pull request lifecycle")
    @app_commands.describe(repository="owner/repo")
    async def sankey_prs(self, interaction: discord.Interaction, repository: str) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))
        try:
            all_prs = await self._gh(interaction.user.id).get_pull_requests(
                owner, repo, state="all", max_results=200)
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))
        open_c = sum(1 for p in all_prs if p.get("state") == "open")
        merged_c = sum(1 for p in all_prs if p.get("merged_at"))
        closed_c = sum(1 for p in all_prs if p.get("state") == "closed" and not p.get("merged_at"))
        data = {"total": len(all_prs), "open": open_c, "merged": merged_c, "closed": closed_c,
                "approved": int(merged_c * 0.9), "changes_requested": int(merged_c * 0.3)}
        chart = PRFlowSankey(title=f"〰️ PR Flow — {owner}/{repo}", width=1000, height=550)
        file = await chart.to_discord_file(data, "sankey_prs.png")
        await _send_chart(interaction, file, f"〰️ Pull Request Lifecycle Flow — {owner}/{repo}",
                          f"Based on {len(all_prs)} pull requests.", Colors.MERGED)

    @visual.command(name="sankey-cicd", description="Sankey diagram of CI/CD pipeline flow")
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
        await _send_chart(interaction, file, f"〰️ CI/CD Pipeline Flow — {owner}/{repo}",
                          f"Based on {len(runs)} workflow runs.", Colors.SUCCESS)

    @visual.command(name="sankey-issues", description="Sankey diagram of issue triage flow")
    @app_commands.describe(repository="owner/repo")
    async def sankey_issues(self, interaction: discord.Interaction, repository: str) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))
        try:
            issues = await self._gh(interaction.user.id).get_issues(owner, repo, state="all", max_results=200)
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))
        chart = IssuetriageSankey(title=f"〰️ Issue Triage — {owner}/{repo}", width=1000, height=520)
        file = await chart.to_discord_file(issues, "sankey_issues.png")
        await _send_chart(interaction, file, f"〰️ Issue Triage Flow — {owner}/{repo}",
                          f"Based on {len(issues)} issues.", Colors.PRIMARY)


async def setup(bot) -> None:
    await bot.add_cog(VisualizationsCog(bot))

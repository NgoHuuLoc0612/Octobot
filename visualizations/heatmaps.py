"""
Octobot Heatmaps & Treemaps — Contribution heatmaps, file treemaps, language treemaps.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import plotly.express as px
import plotly.graph_objects as go

from visualizations.base import (
    BaseChart,
    GITHUB_PALETTE,
    OCTOBOT_THEME,
    apply_octobot_style,
    create_base_layout,
)
from utils.helpers import get_language_color


# ─── GitHub Contribution Heatmap ─────────────────────────────────────────────

class ContributionHeatmap(BaseChart):
    """
    GitHub-style contribution calendar heatmap.
    Rows = days of week, columns = weeks.
    """

    def build(self, data: dict) -> go.Figure:
        """
        data = contribution calendar from GraphQL:
        {
            user: {
                contributionsCollection: {
                    contributionCalendar: {
                        weeks: [{contributionDays: [{date, contributionCount, color}]}]
                    }
                }
            }
        }
        """
        try:
            weeks = (
                data.get("user", {})
                .get("contributionsCollection", {})
                .get("contributionCalendar", {})
                .get("weeks", [])
            )
        except Exception:
            weeks = data.get("weeks", [])

        if not weeks:
            fig = go.Figure()
            fig.add_annotation(text="No contribution calendar data", showarrow=False)
            apply_octobot_style(fig)
            return fig

        # Build 7×N grid (rows=weekday, cols=week)
        day_names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
        num_weeks = len(weeks)

        z = np.zeros((7, num_weeks), dtype=int)
        hover = [['' for _ in range(num_weeks)] for _ in range(7)]
        dates_row = ['' for _ in range(num_weeks)]

        for w_idx, week in enumerate(weeks):
            days = week.get("contributionDays", [])
            for day in days:
                try:
                    dt = datetime.fromisoformat(day.get("date", "2000-01-01"))
                    d_idx = dt.weekday()  # 0=Mon...6=Sun
                    # Convert to Sun=0 Mon=1 ... Sat=6
                    d_idx = (d_idx + 1) % 7
                    count = day.get("contributionCount", 0)
                    z[d_idx, w_idx] = count
                    hover[d_idx][w_idx] = f"{day.get('date', '')}: {count} contributions"
                    if d_idx == 0:
                        dates_row[w_idx] = dt.strftime("%b %d")
                except Exception:
                    pass

        # X-axis labels: show month names at week boundaries
        month_labels = []
        last_month = None
        for w_idx, week in enumerate(weeks):
            days = week.get("contributionDays", [])
            if days:
                try:
                    dt = datetime.fromisoformat(days[0].get("date", "2000-01-01"))
                    month = dt.strftime("%b")
                    if month != last_month:
                        month_labels.append(month)
                        last_month = month
                    else:
                        month_labels.append("")
                except Exception:
                    month_labels.append("")
            else:
                month_labels.append("")

        colorscale = [
            [0.00, "#1a2a1a"],
            [0.01, "#0e4429"],
            [0.25, "#006d32"],
            [0.50, "#26a641"],
            [0.75, "#39d353"],
            [1.00, "#56d364"],
        ]

        fig = go.Figure(go.Heatmap(
            z=z,
            x=month_labels,
            y=day_names,
            colorscale=colorscale,
            showscale=True,
            colorbar=dict(
                title=dict(text="Contributions", font=dict(color=OCTOBOT_THEME["text_color"])),
                tickfont=dict(color=OCTOBOT_THEME["text_color"]),
            ),
            customdata=hover,
            hovertemplate="%{customdata}<extra></extra>",
            xgap=2,
            ygap=2,
        ))

        fig.update_layout(
            **create_base_layout(
                title=self.title or "🌡️ GitHub Contribution Calendar",
                height=self.height,
                width=self.width,
                show_legend=False,
            )
        )
        apply_octobot_style(fig)
        return fig


# ─── Weekly Activity Heatmap ──────────────────────────────────────────────────

class WeeklyActivityHeatmap(BaseChart):
    """
    Heatmap of repository activity by day-of-week × hour-of-day.
    """

    def build(self, events: List[dict]) -> go.Figure:
        """events = list of GitHub events with created_at timestamps."""
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        activity = np.zeros((7, 24), dtype=int)

        for event in events:
            created = event.get("created_at", "")
            if not created:
                continue
            try:
                dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                day_idx = dt.weekday()  # 0=Mon
                hour_idx = dt.hour
                activity[day_idx, hour_idx] += 1
            except Exception:
                pass

        if activity.sum() == 0:
            fig = go.Figure()
            fig.add_annotation(text="No activity data available", showarrow=False)
            apply_octobot_style(fig)
            return fig

        hours = [f"{h:02d}:00" for h in range(24)]

        fig = go.Figure(go.Heatmap(
            z=activity,
            x=hours,
            y=day_names,
            colorscale=[
                [0, OCTOBOT_THEME["bg_color"]],
                [0.2, "#1a3a4a"],
                [0.5, "#1F6FEB"],
                [0.8, "#58A6FF"],
                [1, "#79C0FF"],
            ],
            showscale=True,
            colorbar=dict(
                title=dict(text="Events", font=dict(color=OCTOBOT_THEME["text_color"])),
                tickfont=dict(color=OCTOBOT_THEME["text_color"]),
            ),
            hovertemplate="<b>%{y} at %{x}</b><br>Events: %{z}<extra></extra>",
            xgap=1,
            ygap=1,
        ))

        fig.update_layout(
            **create_base_layout(
                title=self.title or "🌡️ Weekly Repository Activity Heatmap",
                xaxis_title="Hour of Day (UTC)",
                height=self.height,
                width=self.width,
                show_legend=False,
            )
        )
        apply_octobot_style(fig)
        return fig


# ─── Language Treemap ─────────────────────────────────────────────────────────

class LanguageTreemap(BaseChart):
    """
    Treemap showing language distribution across all user repositories.
    Hierarchy: Language → Repository.
    """

    def build(self, repo_languages: Dict[str, Dict[str, int]]) -> go.Figure:
        """repo_languages = {repo_name: {language: bytes}}"""
        if not repo_languages:
            fig = go.Figure()
            fig.add_annotation(text="No language data", showarrow=False)
            apply_octobot_style(fig)
            return fig

        ids, labels, parents, values, colors_list, hover = [], [], [], [], [], []

        # Root node
        ids.append("root")
        labels.append("All Repositories")
        parents.append("")
        values.append(0)
        colors_list.append(OCTOBOT_THEME["paper_color"])
        hover.append("All Repositories")

        # Language aggregation
        lang_totals: Dict[str, int] = defaultdict(int)
        for repo_name, langs in repo_languages.items():
            for lang, size in langs.items():
                lang_totals[lang] += size

        for lang, total_size in sorted(lang_totals.items(), key=lambda x: -x[1])[:15]:
            lang_id = f"lang:{lang}"
            ids.append(lang_id)
            labels.append(lang)
            parents.append("root")
            values.append(total_size)
            colors_list.append(get_language_color(lang))
            hover.append(f"{lang}: {total_size / 1024:.1f} KB total")

            for repo_name, langs in repo_languages.items():
                if lang in langs:
                    repo_id = f"{lang_id}/{repo_name}"
                    ids.append(repo_id)
                    labels.append(repo_name)
                    parents.append(lang_id)
                    values.append(langs[lang])
                    colors_list.append(get_language_color(lang))
                    hover.append(f"{repo_name}/{lang}: {langs[lang] / 1024:.1f} KB")

        fig = go.Figure(go.Treemap(
            ids=ids,
            labels=labels,
            parents=parents,
            values=values,
            branchvalues="total",
            marker=dict(
                colors=colors_list,
                line=dict(width=1, color=OCTOBOT_THEME["bg_color"]),
            ),
            customdata=hover,
            hovertemplate="%{customdata}<extra></extra>",
            textinfo="label+percent parent",
            textfont=dict(color=OCTOBOT_THEME["text_color"]),
        ))

        fig.update_layout(
            title=dict(
                text=self.title or "🗺️ Language Distribution Treemap",
                font=dict(color=OCTOBOT_THEME["text_color"], size=18),
                x=0.5,
            ),
            paper_bgcolor=OCTOBOT_THEME["paper_color"],
            font=dict(color=OCTOBOT_THEME["text_color"]),
            height=self.height,
            width=self.width,
            margin=dict(l=10, r=10, t=60, b=10),
        )
        return fig


# ─── Repository Topic Treemap ─────────────────────────────────────────────────

class RepoTopicTreemap(BaseChart):
    """
    Treemap grouping repositories by their topics/tags.
    """

    def build(self, repos: List[dict]) -> go.Figure:
        if not repos:
            fig = go.Figure()
            fig.add_annotation(text="No repository data", showarrow=False)
            apply_octobot_style(fig)
            return fig

        topic_repos: Dict[str, List[str]] = defaultdict(list)
        topic_stars: Dict[str, int] = defaultdict(int)
        no_topic_repos = []

        for repo in repos:
            topics = repo.get("topics", [])
            stars = repo.get("stargazers_count", 0)
            name = repo.get("name", "unknown")
            if topics:
                for topic in topics[:3]:  # max 3 topics per repo
                    topic_repos[topic].append(name)
                    topic_stars[topic] += stars
            else:
                no_topic_repos.append(name)

        ids, labels, parents, values, colors_list = [], [], [], [], []

        ids.append("root")
        labels.append("Repositories")
        parents.append("")
        values.append(0)
        colors_list.append(OCTOBOT_THEME["paper_color"])

        for i, (topic, repo_names) in enumerate(
            sorted(topic_repos.items(), key=lambda x: -topic_stars[x[0]])[:20]
        ):
            topic_id = f"topic:{topic}"
            ids.append(topic_id)
            labels.append(f"#{topic}")
            parents.append("root")
            values.append(topic_stars[topic])
            colors_list.append(GITHUB_PALETTE[i % len(GITHUB_PALETTE)])

            for repo_name in repo_names:
                repo_id = f"{topic_id}/{repo_name}"
                ids.append(repo_id)
                labels.append(repo_name)
                parents.append(topic_id)
                star_count = next(
                    (r.get("stargazers_count", 1) for r in repos if r.get("name") == repo_name),
                    1,
                )
                values.append(max(1, star_count))
                colors_list.append(GITHUB_PALETTE[i % len(GITHUB_PALETTE)])

        if no_topic_repos:
            ids.append("topic:uncategorized")
            labels.append("Uncategorized")
            parents.append("root")
            values.append(len(no_topic_repos))
            colors_list.append(OCTOBOT_THEME["grid_color"])
            for repo_name in no_topic_repos[:10]:
                ids.append(f"topic:uncategorized/{repo_name}")
                labels.append(repo_name)
                parents.append("topic:uncategorized")
                values.append(1)
                colors_list.append(OCTOBOT_THEME["grid_color"])

        fig = go.Figure(go.Treemap(
            ids=ids,
            labels=labels,
            parents=parents,
            values=values,
            branchvalues="total",
            marker=dict(
                colors=colors_list,
                line=dict(width=1, color=OCTOBOT_THEME["bg_color"]),
            ),
            textinfo="label+percent parent",
            textfont=dict(color=OCTOBOT_THEME["text_color"]),
        ))

        fig.update_layout(
            title=dict(
                text=self.title or "🗺️ Repository Topic Treemap",
                font=dict(color=OCTOBOT_THEME["text_color"], size=18),
                x=0.5,
            ),
            paper_bgcolor=OCTOBOT_THEME["paper_color"],
            font=dict(color=OCTOBOT_THEME["text_color"]),
            height=self.height,
            width=self.width,
            margin=dict(l=10, r=10, t=60, b=10),
        )
        return fig


# ─── Commit Correlation Heatmap ───────────────────────────────────────────────

class CommitCorrelationHeatmap(BaseChart):
    """
    Heatmap showing correlation between contributor commit patterns.
    """

    def build(self, data: List[dict]) -> go.Figure:
        """data = contributor stats list with weekly data."""
        if len(data) < 2:
            fig = go.Figure()
            fig.add_annotation(text="Need at least 2 contributors for correlation", showarrow=False)
            apply_octobot_style(fig)
            return fig

        top = sorted(data, key=lambda x: x.get("total", 0), reverse=True)[:10]
        logins = [c.get("author", {}).get("login", f"User{i}") for i, c in enumerate(top)]

        # Build matrix of weekly commits
        series = []
        for contrib in top:
            weeks = contrib.get("weeks", [])
            series.append([w.get("c", 0) for w in weeks])

        max_len = max(len(s) for s in series)
        matrix = np.array([s + [0] * (max_len - len(s)) for s in series], dtype=float)

        # Correlation matrix
        if matrix.shape[1] > 1:
            corr = np.corrcoef(matrix)
        else:
            corr = np.eye(len(top))
        corr = np.nan_to_num(corr, nan=0.0)

        fig = go.Figure(go.Heatmap(
            z=corr,
            x=logins,
            y=logins,
            colorscale=[
                [0, "#CF222E"],
                [0.5, OCTOBOT_THEME["bg_color"]],
                [1, "#238636"],
            ],
            zmin=-1, zmax=1,
            colorbar=dict(
                title=dict(text="Correlation", font=dict(color=OCTOBOT_THEME["text_color"])),
                tickfont=dict(color=OCTOBOT_THEME["text_color"]),
            ),
            hovertemplate=(
                "<b>%{y} × %{x}</b><br>"
                "Correlation: %{z:.3f}<extra></extra>"
            ),
            xgap=2,
            ygap=2,
            text=[[f"{v:.2f}" for v in row] for row in corr],
            texttemplate="%{text}",
            textfont=dict(size=9, color=OCTOBOT_THEME["text_color"]),
        ))

        fig.update_layout(
            **create_base_layout(
                title=self.title or "🌡️ Contributor Commit Pattern Correlation",
                height=self.height,
                width=self.width,
                show_legend=False,
            )
        )
        apply_octobot_style(fig)
        return fig

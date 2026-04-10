"""
Octobot 2D Charts — Bar, line, scatter, bubble, pie, area, violin, box plots.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from visualizations.base import (
    BaseChart,
    GITHUB_PALETTE,
    OCTOBOT_THEME,
    apply_octobot_style,
    create_base_layout,
)
from utils.helpers import get_language_color


# ─── Commit Activity Chart ────────────────────────────────────────────────────

class CommitActivityChart(BaseChart):
    """Weekly commit activity bar chart for the last 52 weeks."""

    def build(self, data: List[dict]) -> go.Figure:
        """data = list of {week: unix_ts, total: int, days: [int*7]}"""
        if not data:
            fig = go.Figure()
            fig.add_annotation(text="No commit data available", showarrow=False)
            apply_octobot_style(fig)
            return fig

        labels, values = [], []
        for entry in data[-52:]:
            ts = entry.get("week", 0)
            total = entry.get("total", 0)
            dt = datetime.utcfromtimestamp(ts) if ts else datetime.utcnow()
            labels.append(dt.strftime("%b %d"))
            values.append(total)

        fig = go.Figure(
            go.Bar(
                x=labels,
                y=values,
                marker=dict(
                    color=values,
                    colorscale=[
                        [0, "#1a3a1a"],
                        [0.25, "#238636"],
                        [0.75, "#2ea44f"],
                        [1, "#56d364"],
                    ],
                    showscale=False,
                    line=dict(width=0),
                ),
                hovertemplate="<b>Week of %{x}</b><br>Commits: %{y}<extra></extra>",
            )
        )

        fig.update_layout(
            **create_base_layout(
                title=self.title or "📝 Weekly Commit Activity (Last 52 Weeks)",
                xaxis_title="Week",
                yaxis_title="Commits",
                height=self.height,
                width=self.width,
                show_legend=False,
            )
        )
        apply_octobot_style(fig)
        return fig


# ─── Language Distribution Chart ─────────────────────────────────────────────

class LanguagePieChart(BaseChart):
    """Donut chart showing repository language breakdown."""

    def build(self, data: dict) -> go.Figure:
        """data = {language: bytes}"""
        if not data:
            fig = go.Figure()
            fig.add_annotation(text="No language data available", showarrow=False)
            apply_octobot_style(fig)
            return fig

        total = sum(data.values())
        sorted_langs = sorted(data.items(), key=lambda x: x[1], reverse=True)

        labels = [lang for lang, _ in sorted_langs]
        values = [size for _, size in sorted_langs]
        colors = [get_language_color(lang) for lang in labels]
        percents = [f"{v/total*100:.1f}%" for v in values]

        fig = go.Figure(
            go.Pie(
                labels=labels,
                values=values,
                hole=0.45,
                marker=dict(colors=colors, line=dict(color=OCTOBOT_THEME["bg_color"], width=2)),
                textinfo="label+percent",
                textfont=dict(color=OCTOBOT_THEME["text_color"]),
                hovertemplate=(
                    "<b>%{label}</b><br>"
                    "Size: %{value:,} bytes<br>"
                    "Share: %{percent}<extra></extra>"
                ),
            )
        )

        fig.update_layout(
            **create_base_layout(
                title=self.title or "🗣️ Language Distribution",
                height=self.height,
                width=self.width,
            )
        )
        apply_octobot_style(fig)
        return fig


# ─── Contributor Bar Chart ────────────────────────────────────────────────────

class ContributorBarChart(BaseChart):
    """Horizontal bar chart for top contributors by commit count."""

    def build(self, data: List[dict]) -> go.Figure:
        """data = list of contributor stat dicts with author.login and total."""
        if not data:
            fig = go.Figure()
            fig.add_annotation(text="No contributor data available", showarrow=False)
            apply_octobot_style(fig)
            return fig

        sorted_data = sorted(data, key=lambda x: x.get("total", 0), reverse=True)[:20]
        logins = [d.get("author", {}).get("login", "Unknown") for d in sorted_data]
        totals = [d.get("total", 0) for d in sorted_data]
        additions = [sum(w.get("a", 0) for w in d.get("weeks", [])) for d in sorted_data]
        deletions = [sum(w.get("d", 0) for w in d.get("weeks", [])) for d in sorted_data]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            y=logins[::-1],
            x=totals[::-1],
            orientation="h",
            name="Commits",
            marker_color=GITHUB_PALETTE[0],
            hovertemplate="<b>%{y}</b><br>Commits: %{x}<extra></extra>",
        ))

        fig.update_layout(
            **create_base_layout(
                title=self.title or "👥 Top Contributors by Commits",
                xaxis_title="Commits",
                yaxis_title="Contributor",
                height=max(400, len(logins) * 28 + 100),
                width=self.width,
                show_legend=False,
            )
        )
        apply_octobot_style(fig)
        return fig


# ─── Issues Timeline Chart ────────────────────────────────────────────────────

class IssuesTimelineChart(BaseChart):
    """Line chart tracking open/closed issues over time."""

    def build(self, data: dict) -> go.Figure:
        """data = {dates: [str], open: [int], closed: [int]}"""
        dates = data.get("dates", [])
        open_counts = data.get("open", [])
        closed_counts = data.get("closed", [])

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=dates,
            y=open_counts,
            name="Open",
            mode="lines+markers",
            line=dict(color=GITHUB_PALETTE[0], width=2),
            marker=dict(size=4),
            fill="tozeroy",
            fillcolor=f"rgba(35, 134, 54, 0.15)",
            hovertemplate="<b>%{x}</b><br>Open: %{y}<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=dates,
            y=closed_counts,
            name="Closed",
            mode="lines+markers",
            line=dict(color=GITHUB_PALETTE[4], width=2, dash="dash"),
            marker=dict(size=4),
            hovertemplate="<b>%{x}</b><br>Closed: %{y}<extra></extra>",
        ))

        fig.update_layout(
            **create_base_layout(
                title=self.title or "🟢 Issues Over Time",
                xaxis_title="Date",
                yaxis_title="Count",
                height=self.height,
                width=self.width,
            )
        )
        apply_octobot_style(fig)
        return fig


# ─── Code Frequency Chart ────────────────────────────────────────────────────

class CodeFrequencyChart(BaseChart):
    """Stacked area chart for code additions and deletions per week."""

    def build(self, data: List[List[int]]) -> go.Figure:
        """data = list of [timestamp, additions, deletions]"""
        if not data:
            fig = go.Figure()
            fig.add_annotation(text="No code frequency data", showarrow=False)
            apply_octobot_style(fig)
            return fig

        dates = [datetime.utcfromtimestamp(row[0]).strftime("%b %d") for row in data[-52:]]
        additions = [row[1] for row in data[-52:]]
        deletions = [abs(row[2]) for row in data[-52:]]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=dates,
            y=additions,
            name="Additions",
            marker_color="#238636",
            hovertemplate="<b>%{x}</b><br>Additions: +%{y:,}<extra></extra>",
        ))
        fig.add_trace(go.Bar(
            x=dates,
            y=[-d for d in deletions],
            name="Deletions",
            marker_color="#CF222E",
            hovertemplate="<b>%{x}</b><br>Deletions: -%{y:,}<extra></extra>",
        ))

        fig.update_layout(
            **create_base_layout(
                title=self.title or "📊 Code Frequency (Additions / Deletions)",
                xaxis_title="Week",
                yaxis_title="Lines",
                height=self.height,
                width=self.width,
            ),
            barmode="relative",
        )
        apply_octobot_style(fig)
        return fig


# ─── Stars History Chart ──────────────────────────────────────────────────────

class StarsHistoryChart(BaseChart):
    """Cumulative stars over time line chart."""

    def build(self, data: dict) -> go.Figure:
        """data = {dates: [str], stars: [int]}"""
        dates = data.get("dates", [])
        stars = data.get("stars", [])

        if not dates:
            fig = go.Figure()
            fig.add_annotation(text="No star history data", showarrow=False)
            apply_octobot_style(fig)
            return fig

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=dates,
            y=stars,
            name="Stars",
            mode="lines",
            line=dict(color="#D29922", width=2),
            fill="tozeroy",
            fillcolor="rgba(210, 153, 34, 0.15)",
            hovertemplate="<b>%{x}</b><br>Stars: %{y:,}<extra></extra>",
        ))

        fig.update_layout(
            **create_base_layout(
                title=self.title or "⭐ Star History",
                xaxis_title="Date",
                yaxis_title="Cumulative Stars",
                height=self.height,
                width=self.width,
                show_legend=False,
            )
        )
        apply_octobot_style(fig)
        return fig


# ─── Repository Comparison Bubble Chart ──────────────────────────────────────

class RepoBubbleChart(BaseChart):
    """
    Bubble chart comparing repositories.
    X = stars, Y = forks, size = open issues, color = language.
    """

    def build(self, repos: List[dict]) -> go.Figure:
        if not repos:
            fig = go.Figure()
            fig.add_annotation(text="No repository data", showarrow=False)
            apply_octobot_style(fig)
            return fig

        import numpy as np

        names = [r.get("name", "?") for r in repos]
        stars = [r.get("stargazers_count", 0) for r in repos]
        forks = [r.get("forks_count", 0) for r in repos]
        issues = [max(1, r.get("open_issues_count", 1)) for r in repos]
        langs = [r.get("language") or "Unknown" for r in repos]
        urls = [r.get("html_url", "") for r in repos]

        # Normalize sizes
        max_issues = max(issues)
        sizes = [10 + (i / max_issues) * 50 for i in issues]

        unique_langs = list(set(langs))
        color_map = {
            lang: GITHUB_PALETTE[i % len(GITHUB_PALETTE)]
            for i, lang in enumerate(unique_langs)
        }

        fig = go.Figure()
        for lang in unique_langs:
            idx = [i for i, l in enumerate(langs) if l == lang]
            fig.add_trace(go.Scatter(
                x=[stars[i] for i in idx],
                y=[forks[i] for i in idx],
                mode="markers",
                name=lang,
                marker=dict(
                    size=[sizes[i] for i in idx],
                    color=color_map[lang],
                    line=dict(color=OCTOBOT_THEME["bg_color"], width=1),
                    opacity=0.85,
                ),
                text=[names[i] for i in idx],
                customdata=[[issues[i], urls[i]] for i in idx],
                hovertemplate=(
                    "<b>%{text}</b><br>"
                    "Stars: %{x:,}<br>"
                    "Forks: %{y:,}<br>"
                    "Open Issues: %{customdata[0]:,}<br>"
                    f"Language: {lang}<extra></extra>"
                ),
            ))

        fig.update_layout(
            **create_base_layout(
                title=self.title or "🫧 Repository Comparison (Bubble Chart)",
                xaxis_title="Stars",
                yaxis_title="Forks",
                height=self.height,
                width=self.width,
            )
        )
        apply_octobot_style(fig)
        return fig


# ─── PR Cycle Time Scatter Plot ───────────────────────────────────────────────

class PRCycleTimeScatter(BaseChart):
    """Scatter plot of PR cycle time vs size (additions + deletions)."""

    def build(self, prs: List[dict]) -> go.Figure:
        from datetime import timezone

        valid = []
        for pr in prs:
            created = pr.get("created_at")
            closed = pr.get("merged_at") or pr.get("closed_at")
            if not (created and closed):
                continue
            try:
                dt_created = datetime.fromisoformat(created.replace("Z", "+00:00"))
                dt_closed = datetime.fromisoformat(closed.replace("Z", "+00:00"))
                days = (dt_closed - dt_created).total_seconds() / 86400
                size = pr.get("additions", 0) + pr.get("deletions", 0)
                valid.append({
                    "number": pr.get("number", 0),
                    "title": pr.get("title", "")[:50],
                    "days": round(days, 1),
                    "size": size,
                    "state": pr.get("merged_at") and "merged" or "closed",
                })
            except Exception:
                continue

        if not valid:
            fig = go.Figure()
            fig.add_annotation(text="No closed PR data available", showarrow=False)
            apply_octobot_style(fig)
            return fig

        merged = [v for v in valid if v["state"] == "merged"]
        closed = [v for v in valid if v["state"] != "merged"]

        fig = go.Figure()
        for subset, color, name in [
            (merged, "#8957E5", "Merged"),
            (closed, "#CF222E", "Closed"),
        ]:
            if subset:
                fig.add_trace(go.Scatter(
                    x=[p["size"] for p in subset],
                    y=[p["days"] for p in subset],
                    mode="markers",
                    name=name,
                    marker=dict(color=color, size=8, opacity=0.75),
                    text=[f"#{p['number']} {p['title']}" for p in subset],
                    hovertemplate=(
                        "<b>%{text}</b><br>"
                        "Size: %{x:,} lines<br>"
                        "Cycle Time: %{y:.1f} days<extra></extra>"
                    ),
                ))

        fig.update_layout(
            **create_base_layout(
                title=self.title or "🔵 PR Cycle Time vs Size",
                xaxis_title="PR Size (Additions + Deletions)",
                yaxis_title="Cycle Time (Days)",
                height=self.height,
                width=self.width,
            )
        )
        fig.update_xaxes(type="log")
        apply_octobot_style(fig)
        return fig


# ─── Issue Label Distribution ─────────────────────────────────────────────────

class LabelDistributionChart(BaseChart):
    """Horizontal bar chart showing issue count per label."""

    def build(self, issues: List[dict]) -> go.Figure:
        label_counts: Dict[str, Tuple[int, str]] = {}

        for issue in issues:
            for label in issue.get("labels", []):
                name = label.get("name", "unknown")
                color = f"#{label.get('color', '586069')}"
                label_counts[name] = (
                    label_counts.get(name, (0, color))[0] + 1,
                    color,
                )

        if not label_counts:
            fig = go.Figure()
            fig.add_annotation(text="No label data available", showarrow=False)
            apply_octobot_style(fig)
            return fig

        sorted_labels = sorted(label_counts.items(), key=lambda x: x[1][0], reverse=True)[:20]
        names = [item[0] for item in sorted_labels]
        counts = [item[1][0] for item in sorted_labels]
        colors = [item[1][1] for item in sorted_labels]

        fig = go.Figure(go.Bar(
            y=names[::-1],
            x=counts[::-1],
            orientation="h",
            marker=dict(
                color=colors[::-1],
                line=dict(color=OCTOBOT_THEME["bg_color"], width=1),
            ),
            hovertemplate="<b>%{y}</b><br>Issues: %{x}<extra></extra>",
        ))

        fig.update_layout(
            **create_base_layout(
                title=self.title or "🏷️ Issue Label Distribution",
                xaxis_title="Issue Count",
                height=max(400, len(names) * 28 + 100),
                width=self.width,
                show_legend=False,
            )
        )
        apply_octobot_style(fig)
        return fig


# ─── Multi-Repo Comparison Bar Chart ─────────────────────────────────────────

class MultiRepoComparisonChart(BaseChart):
    """
    Grouped bar chart comparing multiple repositories across metrics:
    stars, forks, open issues, watchers.
    """

    def build(self, repos: List[dict]) -> go.Figure:
        if not repos:
            fig = go.Figure()
            fig.add_annotation(text="No repository data", showarrow=False)
            apply_octobot_style(fig)
            return fig

        names = [r.get("name", "?") for r in repos[:10]]
        metrics = {
            "Stars": [r.get("stargazers_count", 0) for r in repos[:10]],
            "Forks": [r.get("forks_count", 0) for r in repos[:10]],
            "Open Issues": [r.get("open_issues_count", 0) for r in repos[:10]],
            "Watchers": [r.get("watchers_count", 0) for r in repos[:10]],
        }
        colors = [GITHUB_PALETTE[i] for i in range(len(metrics))]

        fig = go.Figure()
        for (metric, values), color in zip(metrics.items(), colors):
            fig.add_trace(go.Bar(
                name=metric,
                x=names,
                y=values,
                marker_color=color,
                hovertemplate=f"<b>%{{x}}</b><br>{metric}: %{{y:,}}<extra></extra>",
            ))

        fig.update_layout(
            **create_base_layout(
                title=self.title or "📊 Repository Metrics Comparison",
                yaxis_title="Count",
                height=self.height,
                width=self.width,
            ),
            barmode="group",
        )
        apply_octobot_style(fig)
        return fig


# ─── Workflow Run Status Pie ───────────────────────────────────────────────────

class WorkflowStatusChart(BaseChart):
    """Pie chart of workflow run outcomes (success/failure/cancelled/etc)."""

    def build(self, runs: List[dict]) -> go.Figure:
        from collections import Counter

        if not runs:
            fig = go.Figure()
            fig.add_annotation(text="No workflow run data", showarrow=False)
            apply_octobot_style(fig)
            return fig

        conclusions = [
            r.get("conclusion") or r.get("status", "unknown")
            for r in runs
        ]
        counts = Counter(conclusions)

        color_map = {
            "success": "#238636",
            "failure": "#CF222E",
            "cancelled": "#848D97",
            "skipped": "#6E7681",
            "timed_out": "#D29922",
            "action_required": "#E16F24",
            "neutral": "#58A6FF",
            "in_progress": "#1F6FEB",
            "queued": "#8957E5",
            "unknown": "#484F58",
        }

        labels = list(counts.keys())
        values = list(counts.values())
        colors_list = [color_map.get(l, "#484F58") for l in labels]

        fig = go.Figure(go.Pie(
            labels=[l.replace("_", " ").title() for l in labels],
            values=values,
            hole=0.4,
            marker=dict(colors=colors_list, line=dict(color=OCTOBOT_THEME["bg_color"], width=2)),
            hovertemplate="<b>%{label}</b><br>Count: %{value}<br>%{percent}<extra></extra>",
        ))

        fig.update_layout(
            **create_base_layout(
                title=self.title or "⚡ Workflow Run Outcomes",
                height=self.height,
                width=self.width,
            )
        )
        apply_octobot_style(fig)
        return fig


# ─── Punch Card (Day-of-Week / Hour Heatmap) ──────────────────────────────────

class PunchCardChart(BaseChart):
    """
    Dot scatter chart showing commit frequency by day and hour.
    (GitHub-style commit punch card)
    """

    def build(self, data: List[List[int]]) -> go.Figure:
        """data = [[day, hour, count], ...] (0=Sun, 1=Mon, ... 6=Sat)"""
        if not data:
            fig = go.Figure()
            fig.add_annotation(text="No punch card data", showarrow=False)
            apply_octobot_style(fig)
            return fig

        days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
        day_nums = [row[0] for row in data]
        hours = [row[1] for row in data]
        counts = [row[2] for row in data]
        max_count = max(counts) if counts else 1

        sizes = [max(3, (c / max_count) * 40) for c in counts]

        fig = go.Figure(go.Scatter(
            x=hours,
            y=[days[d] for d in day_nums],
            mode="markers",
            marker=dict(
                size=sizes,
                color=counts,
                colorscale=[
                    [0, "#1a3a1a"],
                    [0.3, "#238636"],
                    [0.7, "#2ea44f"],
                    [1, "#56d364"],
                ],
                showscale=True,
                colorbar=dict(
                    title="Commits",
                    title_font_color=OCTOBOT_THEME["text_color"],
                    tickfont=dict(color=OCTOBOT_THEME["text_color"]),
                ),
                line=dict(width=0),
                opacity=0.9,
            ),
            hovertemplate=(
                "<b>%{y} at %{x}:00</b><br>"
                "Commits: %{marker.color}<extra></extra>"
            ),
        ))

        fig.update_layout(
            **create_base_layout(
                title=self.title or "🕐 Commit Punch Card",
                xaxis_title="Hour of Day (UTC)",
                yaxis_title="Day of Week",
                height=self.height,
                width=self.width,
                show_legend=False,
            )
        )
        fig.update_xaxes(
            tickmode="linear",
            tick0=0,
            dtick=1,
            range=[-0.5, 23.5],
        )
        apply_octobot_style(fig)
        return fig

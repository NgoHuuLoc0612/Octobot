"""
Octobot 3D Charts — Three-dimensional scatter, surface, and bar visualizations.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from visualizations.base import (
    BaseChart,
    GITHUB_PALETTE,
    OCTOBOT_THEME,
    apply_octobot_style,
)


def _apply_3d_style(fig: go.Figure) -> go.Figure:
    """Apply consistent 3D scene styling."""
    scene = dict(
        bgcolor=OCTOBOT_THEME["bg_color"],
        xaxis=dict(
            gridcolor=OCTOBOT_THEME["grid_color"],
            backgroundcolor=OCTOBOT_THEME["bg_color"],
            color=OCTOBOT_THEME["text_color"],
            showbackground=True,
            zerolinecolor=OCTOBOT_THEME["grid_color"],
        ),
        yaxis=dict(
            gridcolor=OCTOBOT_THEME["grid_color"],
            backgroundcolor=OCTOBOT_THEME["bg_color"],
            color=OCTOBOT_THEME["text_color"],
            showbackground=True,
            zerolinecolor=OCTOBOT_THEME["grid_color"],
        ),
        zaxis=dict(
            gridcolor=OCTOBOT_THEME["grid_color"],
            backgroundcolor=OCTOBOT_THEME["bg_color"],
            color=OCTOBOT_THEME["text_color"],
            showbackground=True,
            zerolinecolor=OCTOBOT_THEME["grid_color"],
        ),
    )
    fig.update_layout(
        scene=scene,
        paper_bgcolor=OCTOBOT_THEME["paper_color"],
        font=dict(color=OCTOBOT_THEME["text_color"], family="Inter, Arial, sans-serif"),
    )
    return fig


# ─── 3D Commit History ────────────────────────────────────────────────────────

class CommitHistory3DChart(BaseChart):
    """
    3D scatter plot of commits over time.
    X = week, Y = day of week, Z = commit count.
    """

    def build(self, data: List[dict]) -> go.Figure:
        """data = list of {week: ts, days: [int*7], total: int}"""
        x_weeks, y_days, z_counts = [], [], []

        for week_idx, entry in enumerate(data[-52:]):
            for day_idx, count in enumerate(entry.get("days", [0] * 7)):
                if count > 0:
                    x_weeks.append(week_idx)
                    y_days.append(day_idx)
                    z_counts.append(count)

        if not z_counts:
            fig = go.Figure()
            fig.add_annotation(text="No 3D commit data available", showarrow=False)
            _apply_3d_style(fig)
            return fig

        day_names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

        fig = go.Figure(
            go.Scatter3d(
                x=x_weeks,
                y=y_days,
                z=z_counts,
                mode="markers",
                marker=dict(
                    size=[max(3, min(12, c * 1.5)) for c in z_counts],
                    color=z_counts,
                    colorscale=[
                        [0, "#1a3a1a"],
                        [0.2, "#238636"],
                        [0.6, "#2ea44f"],
                        [1, "#56d364"],
                    ],
                    colorbar=dict(
                        title="Commits",
                        titlefont=dict(color=OCTOBOT_THEME["text_color"]),
                        tickfont=dict(color=OCTOBOT_THEME["text_color"]),
                    ),
                    opacity=0.9,
                    line=dict(width=0),
                ),
                hovertemplate=(
                    "Week: %{x}<br>"
                    "Day: %{y}<br>"
                    "Commits: %{z}<extra></extra>"
                ),
            )
        )

        fig.update_layout(
            title=dict(
                text=self.title or "🧊 3D Commit Activity",
                font=dict(color=OCTOBOT_THEME["text_color"], size=18),
                x=0.5,
            ),
            scene=dict(
                bgcolor=OCTOBOT_THEME["bg_color"],
                xaxis=dict(
                    title="Week",
                    gridcolor=OCTOBOT_THEME["grid_color"],
                    backgroundcolor=OCTOBOT_THEME["bg_color"],
                    color=OCTOBOT_THEME["text_color"],
                    showbackground=True,
                ),
                yaxis=dict(
                    title="Day",
                    ticktext=day_names,
                    tickvals=list(range(7)),
                    gridcolor=OCTOBOT_THEME["grid_color"],
                    backgroundcolor=OCTOBOT_THEME["bg_color"],
                    color=OCTOBOT_THEME["text_color"],
                    showbackground=True,
                ),
                zaxis=dict(
                    title="Commits",
                    gridcolor=OCTOBOT_THEME["grid_color"],
                    backgroundcolor=OCTOBOT_THEME["bg_color"],
                    color=OCTOBOT_THEME["text_color"],
                    showbackground=True,
                ),
            ),
            paper_bgcolor=OCTOBOT_THEME["paper_color"],
            font=dict(color=OCTOBOT_THEME["text_color"]),
            height=self.height,
            width=self.width,
            margin=dict(l=0, r=0, t=60, b=0),
        )
        return fig


# ─── 3D Contributor Activity ──────────────────────────────────────────────────

class ContributorActivity3D(BaseChart):
    """
    3D bar chart: X = contributor, Y = week, Z = commits.
    """

    def build(self, data: List[dict]) -> go.Figure:
        """data = list of contributor stats with author and weeks."""
        top_contribs = sorted(data, key=lambda x: x.get("total", 0), reverse=True)[:8]

        if not top_contribs:
            fig = go.Figure()
            fig.add_annotation(text="No contributor data", showarrow=False)
            _apply_3d_style(fig)
            return fig

        fig = go.Figure()

        for idx, contrib in enumerate(top_contribs):
            login = contrib.get("author", {}).get("login", f"User{idx}")
            weeks = contrib.get("weeks", [])[-26:]  # Last 26 weeks
            week_nums = list(range(len(weeks)))
            commit_counts = [w.get("c", 0) for w in weeks]
            color = GITHUB_PALETTE[idx % len(GITHUB_PALETTE)]

            # Create 3D bars using Mesh3d for each contributor
            for w_idx, count in enumerate(commit_counts):
                if count == 0:
                    continue
                x0, x1 = idx - 0.4, idx + 0.4
                y0, y1 = w_idx - 0.4, w_idx + 0.4
                z0, z1 = 0, count

                fig.add_trace(go.Mesh3d(
                    x=[x0, x1, x1, x0, x0, x1, x1, x0],
                    y=[y0, y0, y1, y1, y0, y0, y1, y1],
                    z=[z0, z0, z0, z0, z1, z1, z1, z1],
                    i=[7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2],
                    j=[3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3],
                    k=[0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6],
                    color=color,
                    opacity=0.8,
                    name=login if w_idx == 0 else None,
                    showlegend=w_idx == 0,
                    hovertemplate=f"<b>{login}</b><br>Week {w_idx}<br>Commits: {count}<extra></extra>",
                ))

        fig.update_layout(
            title=dict(
                text=self.title or "🧊 3D Contributor Activity",
                font=dict(color=OCTOBOT_THEME["text_color"], size=18),
                x=0.5,
            ),
            scene=dict(
                bgcolor=OCTOBOT_THEME["bg_color"],
                xaxis=dict(
                    title="Contributor",
                    ticktext=[c.get("author", {}).get("login", f"U{i}") for i, c in enumerate(top_contribs)],
                    tickvals=list(range(len(top_contribs))),
                    gridcolor=OCTOBOT_THEME["grid_color"],
                    backgroundcolor=OCTOBOT_THEME["bg_color"],
                    color=OCTOBOT_THEME["text_color"],
                    showbackground=True,
                ),
                yaxis=dict(
                    title="Week",
                    gridcolor=OCTOBOT_THEME["grid_color"],
                    backgroundcolor=OCTOBOT_THEME["bg_color"],
                    color=OCTOBOT_THEME["text_color"],
                    showbackground=True,
                ),
                zaxis=dict(
                    title="Commits",
                    gridcolor=OCTOBOT_THEME["grid_color"],
                    backgroundcolor=OCTOBOT_THEME["bg_color"],
                    color=OCTOBOT_THEME["text_color"],
                    showbackground=True,
                ),
            ),
            paper_bgcolor=OCTOBOT_THEME["paper_color"],
            font=dict(color=OCTOBOT_THEME["text_color"]),
            height=self.height,
            width=self.width,
        )
        return fig


# ─── 3D Repository Metrics Surface ───────────────────────────────────────────

class RepoMetricsSurface3D(BaseChart):
    """
    3D surface chart: user's repos mapped onto a quality surface.
    X = stars, Y = forks, Z = issues (interpolated surface).
    """

    def build(self, repos: List[dict]) -> go.Figure:
        if len(repos) < 4:
            fig = go.Figure()
            fig.add_annotation(text="Need at least 4 repositories for surface chart", showarrow=False)
            _apply_3d_style(fig)
            return fig

        stars = np.array([r.get("stargazers_count", 0) for r in repos], dtype=float)
        forks = np.array([r.get("forks_count", 0) for r in repos], dtype=float)
        issues = np.array([r.get("open_issues_count", 0) for r in repos], dtype=float)

        # Create grid and interpolate
        from scipy.interpolate import griddata

        x_range = np.linspace(stars.min(), stars.max(), 30)
        y_range = np.linspace(forks.min(), forks.max(), 30)
        xi, yi = np.meshgrid(x_range, y_range)

        points = np.column_stack([stars, forks])
        zi = griddata(points, issues, (xi, yi), method="cubic", fill_value=0)
        zi = np.nan_to_num(zi, nan=0.0)

        # Scatter points on top
        names = [r.get("name", "?") for r in repos]

        fig = go.Figure()

        fig.add_trace(go.Surface(
            x=xi,
            y=yi,
            z=zi,
            colorscale=[
                [0, "#1a2a3a"],
                [0.3, "#1F6FEB"],
                [0.6, "#8957E5"],
                [1, "#DB61A2"],
            ],
            opacity=0.8,
            showscale=True,
            colorbar=dict(
                title="Open Issues",
                titlefont=dict(color=OCTOBOT_THEME["text_color"]),
                tickfont=dict(color=OCTOBOT_THEME["text_color"]),
            ),
            hovertemplate=(
                "Stars: %{x:.0f}<br>"
                "Forks: %{y:.0f}<br>"
                "Issues: %{z:.0f}<extra></extra>"
            ),
        ))

        fig.add_trace(go.Scatter3d(
            x=stars,
            y=forks,
            z=issues,
            mode="markers+text",
            marker=dict(size=6, color="#D29922", line=dict(color="white", width=1)),
            text=names,
            textfont=dict(color=OCTOBOT_THEME["text_color"], size=10),
            hovertemplate=(
                "<b>%{text}</b><br>"
                "Stars: %{x:,}<br>"
                "Forks: %{y:,}<br>"
                "Issues: %{z:,}<extra></extra>"
            ),
        ))

        fig.update_layout(
            title=dict(
                text=self.title or "🧊 3D Repository Metrics Surface",
                font=dict(color=OCTOBOT_THEME["text_color"], size=18),
                x=0.5,
            ),
            scene=dict(
                bgcolor=OCTOBOT_THEME["bg_color"],
                xaxis=dict(
                    title="Stars",
                    gridcolor=OCTOBOT_THEME["grid_color"],
                    backgroundcolor=OCTOBOT_THEME["bg_color"],
                    color=OCTOBOT_THEME["text_color"],
                    showbackground=True,
                ),
                yaxis=dict(
                    title="Forks",
                    gridcolor=OCTOBOT_THEME["grid_color"],
                    backgroundcolor=OCTOBOT_THEME["bg_color"],
                    color=OCTOBOT_THEME["text_color"],
                    showbackground=True,
                ),
                zaxis=dict(
                    title="Open Issues",
                    gridcolor=OCTOBOT_THEME["grid_color"],
                    backgroundcolor=OCTOBOT_THEME["bg_color"],
                    color=OCTOBOT_THEME["text_color"],
                    showbackground=True,
                ),
            ),
            paper_bgcolor=OCTOBOT_THEME["paper_color"],
            font=dict(color=OCTOBOT_THEME["text_color"]),
            height=self.height,
            width=self.width,
        )
        return fig


# ─── 3D Language Evolution ────────────────────────────────────────────────────

class LanguageEvolution3D(BaseChart):
    """
    3D chart showing language usage across multiple repositories.
    X = repo, Y = language, Z = percentage of codebase.
    """

    def build(self, repo_languages: Dict[str, Dict[str, int]]) -> go.Figure:
        """repo_languages = {repo_name: {language: bytes}}"""
        if not repo_languages:
            fig = go.Figure()
            fig.add_annotation(text="No language data available", showarrow=False)
            _apply_3d_style(fig)
            return fig

        all_langs = set()
        for langs in repo_languages.values():
            all_langs.update(langs.keys())
        all_langs = sorted(all_langs)[:15]

        repo_names = list(repo_languages.keys())[:15]

        fig = go.Figure()

        for lang_idx, lang in enumerate(all_langs):
            from visualizations.base import GITHUB_PALETTE
            color = GITHUB_PALETTE[lang_idx % len(GITHUB_PALETTE)]

            for repo_idx, repo_name in enumerate(repo_names):
                langs = repo_languages[repo_name]
                total = sum(langs.values())
                count = langs.get(lang, 0)
                pct = (count / total * 100) if total > 0 else 0

                if pct < 1.0:
                    continue

                fig.add_trace(go.Scatter3d(
                    x=[repo_idx],
                    y=[lang_idx],
                    z=[pct],
                    mode="markers",
                    marker=dict(
                        size=max(4, pct / 3),
                        color=color,
                        opacity=0.85,
                        line=dict(width=0),
                    ),
                    name=lang if repo_idx == 0 else None,
                    showlegend=repo_idx == 0,
                    hovertemplate=(
                        f"<b>{lang}</b><br>"
                        f"Repo: {repo_name}<br>"
                        f"Usage: {pct:.1f}%<extra></extra>"
                    ),
                ))

        fig.update_layout(
            title=dict(
                text=self.title or "🧊 3D Language Distribution Across Repositories",
                font=dict(color=OCTOBOT_THEME["text_color"], size=16),
                x=0.5,
            ),
            scene=dict(
                bgcolor=OCTOBOT_THEME["bg_color"],
                xaxis=dict(
                    title="Repository",
                    ticktext=repo_names,
                    tickvals=list(range(len(repo_names))),
                    gridcolor=OCTOBOT_THEME["grid_color"],
                    backgroundcolor=OCTOBOT_THEME["bg_color"],
                    color=OCTOBOT_THEME["text_color"],
                    showbackground=True,
                ),
                yaxis=dict(
                    title="Language",
                    ticktext=all_langs,
                    tickvals=list(range(len(all_langs))),
                    gridcolor=OCTOBOT_THEME["grid_color"],
                    backgroundcolor=OCTOBOT_THEME["bg_color"],
                    color=OCTOBOT_THEME["text_color"],
                    showbackground=True,
                ),
                zaxis=dict(
                    title="Usage %",
                    range=[0, 100],
                    gridcolor=OCTOBOT_THEME["grid_color"],
                    backgroundcolor=OCTOBOT_THEME["bg_color"],
                    color=OCTOBOT_THEME["text_color"],
                    showbackground=True,
                ),
            ),
            paper_bgcolor=OCTOBOT_THEME["paper_color"],
            font=dict(color=OCTOBOT_THEME["text_color"]),
            height=self.height,
            width=self.width,
        )
        return fig

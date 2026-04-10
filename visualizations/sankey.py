"""
Octobot Sankey Diagrams — Flow diagrams for PRs, CI/CD, and contributions.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple

import plotly.graph_objects as go

from visualizations.base import (
    BaseChart,
    GITHUB_PALETTE,
    OCTOBOT_THEME,
    apply_octobot_style,
)


def _build_sankey(
    node_labels: List[str],
    source: List[int],
    target: List[int],
    value: List[float],
    node_colors: List[str] = None,
    link_colors: List[str] = None,
    title: str = "",
    height: int = 500,
    width: int = 900,
) -> go.Figure:
    """Build a styled Sankey figure."""
    if node_colors is None:
        n = len(node_labels)
        node_colors = [GITHUB_PALETTE[i % len(GITHUB_PALETTE)] for i in range(n)]

    if link_colors is None:
        link_colors = [
            node_colors[s].replace(")", ", 0.35)").replace("rgb(", "rgba(")
            if "rgb(" in (node_colors[s] if s < len(node_colors) else "")
            else "rgba(88, 96, 105, 0.3)"
            for s in source
        ]

    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(
            pad=15,
            thickness=20,
            line=dict(color=OCTOBOT_THEME["grid_color"], width=0.5),
            label=node_labels,
            color=node_colors,
            hovertemplate="%{label}<br>Flow: %{value:,.0f}<extra></extra>",
        ),
        link=dict(
            source=source,
            target=target,
            value=value,
            color=link_colors,
            hovertemplate=(
                "%{source.label} → %{target.label}<br>"
                "Value: %{value:,.0f}<extra></extra>"
            ),
        ),
    ))

    fig.update_layout(
        title=dict(
            text=title,
            font=dict(color=OCTOBOT_THEME["text_color"], size=18),
            x=0.5,
        ),
        paper_bgcolor=OCTOBOT_THEME["paper_color"],
        font=dict(color=OCTOBOT_THEME["text_color"], family="Inter, Arial, sans-serif"),
        height=height,
        width=width,
        margin=dict(l=40, r=40, t=80, b=40),
    )
    return fig


# ─── PR State Flow Sankey ─────────────────────────────────────────────────────

class PRFlowSankey(BaseChart):
    """
    Sankey diagram showing the lifecycle flow of pull requests:
    Author → Review State → Final State.
    """

    def build(self, data: dict) -> go.Figure:
        """
        data = {
            total: int,
            open: int,
            merged: int,
            closed: int,
            approved: int,
            changes_requested: int,
            commented_only: int,
        }
        """
        total = data.get("total", 1) or 1
        merged = data.get("merged", 0)
        closed_no_merge = data.get("closed", 0)
        open_prs = data.get("open", 0)
        approved = data.get("approved", 0)
        changes_req = data.get("changes_requested", 0)
        no_review = total - approved - changes_req

        node_labels = [
            "PRs Created",    # 0
            "Approved",       # 1
            "Changes Requested",  # 2
            "No Review",      # 3
            "Merged",         # 4
            "Closed (No Merge)", # 5
            "Open",           # 6
        ]

        node_colors = [
            "#1F6FEB",  # Created - blue
            "#238636",  # Approved - green
            "#D29922",  # Changes - yellow
            "#848D97",  # No review - gray
            "#8957E5",  # Merged - purple
            "#CF222E",  # Closed - red
            "#2EA44F",  # Open - lighter green
        ]

        source = [0, 0, 0,          # PRs Created → reviews
                  1, 1,              # Approved → merged/open
                  2, 2,              # Changes → merged/closed
                  3, 3]              # No review → closed/open

        target = [1, 2, 3,
                  4, 6,
                  4, 5,
                  5, 6]

        value = [
            max(1, approved), max(1, changes_req), max(1, no_review),
            max(1, int(approved * 0.8)), max(1, int(approved * 0.2)),
            max(1, int(changes_req * 0.5)), max(1, int(changes_req * 0.5)),
            max(1, int(no_review * 0.6)), max(1, int(no_review * 0.4)),
        ]

        return _build_sankey(
            node_labels=node_labels,
            source=source,
            target=target,
            value=value,
            node_colors=node_colors,
            title=self.title or "〰️ Pull Request Lifecycle Flow",
            height=self.height,
            width=self.width,
        )


# ─── CI/CD Pipeline Sankey ────────────────────────────────────────────────────

class CICDPipelineSankey(BaseChart):
    """
    Sankey showing CI/CD workflow run outcomes across stages.
    """

    def build(self, runs: List[dict]) -> go.Figure:
        if not runs:
            fig = go.Figure()
            fig.add_annotation(text="No workflow run data", showarrow=False)
            apply_octobot_style(fig)
            return fig

        # Collect event → status → conclusion flows
        event_counts: Counter = Counter()
        status_counts: Counter = Counter()
        conclusion_counts: Counter = Counter()
        event_to_status: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        status_to_conclusion: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

        for run in runs:
            event = run.get("event", "unknown").replace("_", " ").title()
            status = run.get("status", "unknown").replace("_", " ").title()
            conclusion = (run.get("conclusion") or "In Progress").replace("_", " ").title()

            event_counts[event] += 1
            status_counts[status] += 1
            conclusion_counts[conclusion] += 1
            event_to_status[event][status] += 1
            status_to_conclusion[status][conclusion] += 1

        events = list(event_counts.keys())
        statuses = list(status_counts.keys())
        conclusions = list(conclusion_counts.keys())

        node_labels = events + statuses + conclusions
        n_events = len(events)
        n_statuses = len(statuses)

        event_idx = {e: i for i, e in enumerate(events)}
        status_idx = {s: n_events + i for i, s in enumerate(statuses)}
        conclusion_idx = {c: n_events + n_statuses + i for i, c in enumerate(conclusions)}

        source, target, value = [], [], []

        for e, s_dict in event_to_status.items():
            for s, count in s_dict.items():
                source.append(event_idx[e])
                target.append(status_idx[s])
                value.append(count)

        for s, c_dict in status_to_conclusion.items():
            for c, count in c_dict.items():
                source.append(status_idx[s])
                target.append(conclusion_idx[c])
                value.append(count)

        if not value:
            fig = go.Figure()
            fig.add_annotation(text="Insufficient CI/CD data", showarrow=False)
            apply_octobot_style(fig)
            return fig

        conclusion_colors = {
            "Success": "#238636",
            "Failure": "#CF222E",
            "Cancelled": "#848D97",
            "In Progress": "#1F6FEB",
            "Skipped": "#6E7681",
            "Timed Out": "#D29922",
        }
        node_colors = (
            [GITHUB_PALETTE[1]] * n_events +
            [GITHUB_PALETTE[3]] * n_statuses +
            [conclusion_colors.get(c, GITHUB_PALETTE[4]) for c in conclusions]
        )

        return _build_sankey(
            node_labels=node_labels,
            source=source,
            target=target,
            value=value,
            node_colors=node_colors,
            title=self.title or "〰️ CI/CD Pipeline Flow",
            height=self.height,
            width=self.width,
        )


# ─── Contribution Flow Sankey ─────────────────────────────────────────────────

class ContributionFlowSankey(BaseChart):
    """
    Sankey diagram: Contributors → Repositories → Languages.
    Shows how code flows from people to projects to tech stacks.
    """

    def build(self, data: dict) -> go.Figure:
        """
        data = {
            contributions: [
                {login, repo, language, commits}
            ]
        }
        """
        contributions = data.get("contributions", [])
        if not contributions:
            fig = go.Figure()
            fig.add_annotation(text="No contribution data", showarrow=False)
            apply_octobot_style(fig)
            return fig

        # Aggregate: contributor → repo → language
        contrib_repo: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        repo_lang: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

        for entry in contributions:
            login = entry.get("login", "?")
            repo = entry.get("repo", "?")
            lang = entry.get("language") or "Unknown"
            commits = entry.get("commits", 1)
            contrib_repo[login][repo] += commits
            repo_lang[repo][lang] += commits

        # Top N to keep diagram readable
        top_contributors = sorted(
            contrib_repo.items(), key=lambda x: sum(x[1].values()), reverse=True
        )[:8]
        all_repos = set()
        for _, repos in top_contributors:
            all_repos.update(repos.keys())
        top_repos = sorted(all_repos)[:12]

        all_langs = set()
        for repo in top_repos:
            all_langs.update(repo_lang.get(repo, {}).keys())
        top_langs = sorted(all_langs)[:10]

        contrib_names = [c[0] for c in top_contributors]

        node_labels = contrib_names + top_repos + top_langs
        n_c = len(contrib_names)
        n_r = len(top_repos)

        contrib_idx = {c: i for i, c in enumerate(contrib_names)}
        repo_idx = {r: n_c + i for i, r in enumerate(top_repos)}
        lang_idx = {l: n_c + n_r + i for i, l in enumerate(top_langs)}

        source, target, value = [], [], []

        for login, repos in top_contributors:
            for repo, commits in repos.items():
                if repo in repo_idx:
                    source.append(contrib_idx[login])
                    target.append(repo_idx[repo])
                    value.append(commits)

        for repo in top_repos:
            langs = repo_lang.get(repo, {})
            for lang, commits in langs.items():
                if lang in lang_idx:
                    source.append(repo_idx[repo])
                    target.append(lang_idx[lang])
                    value.append(commits)

        if not value:
            fig = go.Figure()
            fig.add_annotation(text="Insufficient data for flow diagram", showarrow=False)
            apply_octobot_style(fig)
            return fig

        node_colors = (
            [GITHUB_PALETTE[0]] * n_c +    # Contributors = green
            [GITHUB_PALETTE[1]] * n_r +    # Repos = blue
            [GITHUB_PALETTE[2]] * len(top_langs)  # Languages = purple
        )

        return _build_sankey(
            node_labels=node_labels,
            source=source,
            target=target,
            value=value,
            node_colors=node_colors,
            title=self.title or "〰️ Contribution Flow: People → Repos → Languages",
            height=self.height,
            width=self.width,
        )


# ─── Issue Triage Sankey ─────────────────────────────────────────────────────

class IssuetriageSankey(BaseChart):
    """
    Sankey showing issue triage flow:
    Submitted → Labeled → Assigned → Resolved/Closed/Open.
    """

    def build(self, issues: List[dict]) -> go.Figure:
        if not issues:
            fig = go.Figure()
            fig.add_annotation(text="No issue data", showarrow=False)
            apply_octobot_style(fig)
            return fig

        total = len(issues)
        labeled = sum(1 for i in issues if i.get("labels"))
        assigned = sum(1 for i in issues if i.get("assignees"))
        with_milestone = sum(1 for i in issues if i.get("milestone"))
        open_issues = sum(1 for i in issues if i.get("state") == "open")
        closed_issues = sum(1 for i in issues if i.get("state") == "closed")
        unlabeled = total - labeled
        unassigned = total - assigned

        node_labels = [
            "Issues Created",    # 0
            "Labeled",           # 1
            "Unlabeled",         # 2
            "Assigned",          # 3
            "Unassigned",        # 4
            "With Milestone",    # 5
            "Open",              # 6
            "Closed",            # 7
        ]
        node_colors = [
            "#1F6FEB",  # Created
            "#238636",  # Labeled
            "#848D97",  # Unlabeled
            "#D29922",  # Assigned
            "#6E7681",  # Unassigned
            "#8957E5",  # Milestone
            "#2EA44F",  # Open
            "#CF222E",  # Closed
        ]

        source = [0, 0,        # Created → labeled/unlabeled
                  1, 1,        # Labeled → assigned/milestone
                  1, 2,        # Labeled/Unlabeled → open/closed
                  3, 3]
        target = [1, 2,
                  3, 5,
                  6, 7,
                  6, 7]
        value = [
            max(1, labeled), max(1, unlabeled),
            max(1, assigned), max(1, with_milestone),
            max(1, int(labeled * 0.4)), max(1, int(unlabeled * 0.7)),
            max(1, int(assigned * 0.5)), max(1, int(assigned * 0.5)),
        ]

        return _build_sankey(
            node_labels=node_labels,
            source=source,
            target=target,
            value=value,
            node_colors=node_colors,
            title=self.title or "〰️ Issue Triage Flow",
            height=self.height,
            width=self.width,
        )

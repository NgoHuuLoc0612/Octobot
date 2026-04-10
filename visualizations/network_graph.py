"""
Octobot Network Graphs — Dependency networks, fork trees, contributor graphs.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

import networkx as nx
import plotly.graph_objects as go

from visualizations.base import (
    BaseChart,
    GITHUB_PALETTE,
    OCTOBOT_THEME,
    apply_octobot_style,
)


def _spring_layout(G: nx.Graph, k: float = None, seed: int = 42) -> dict:
    """Compute spring layout positions."""
    if len(G.nodes()) == 0:
        return {}
    return nx.spring_layout(G, k=k, seed=seed)


def _build_network_traces(
    G: nx.Graph,
    pos: dict,
    node_colors: List[str],
    node_sizes: List[float],
    node_labels: List[str],
    edge_color: str = "#30363D",
    node_hover: List[str] = None,
) -> Tuple[go.Scatter, go.Scatter]:
    """Build edge and node traces for a network graph."""
    # Edge trace
    edge_x, edge_y = [], []
    for edge in G.edges():
        if edge[0] in pos and edge[1] in pos:
            x0, y0 = pos[edge[0]]
            x1, y1 = pos[edge[1]]
            edge_x += [x0, x1, None]
            edge_y += [y0, y1, None]

    edge_trace = go.Scatter(
        x=edge_x,
        y=edge_y,
        mode="lines",
        line=dict(width=0.8, color=edge_color),
        hoverinfo="none",
        showlegend=False,
    )

    # Node trace
    node_x = [pos[n][0] for n in G.nodes() if n in pos]
    node_y = [pos[n][1] for n in G.nodes() if n in pos]

    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        mode="markers+text",
        text=node_labels,
        textfont=dict(size=9, color=OCTOBOT_THEME["text_color"]),
        textposition="top center",
        marker=dict(
            size=node_sizes,
            color=node_colors,
            line=dict(width=1, color=OCTOBOT_THEME["bg_color"]),
            opacity=0.9,
        ),
        hovertext=node_hover or node_labels,
        hoverinfo="text",
        showlegend=False,
    )

    return edge_trace, node_trace


# ─── Fork Network Graph ───────────────────────────────────────────────────────

class ForkNetworkChart(BaseChart):
    """
    Network graph showing the fork tree of a repository.
    Root = original repo, nodes = forks, edges = parent→fork.
    """

    def build(self, data: dict) -> go.Figure:
        """
        data = {
            root: {name, stars, url},
            forks: [{name, owner, stars, forks, url, parent}]
        }
        """
        root_info = data.get("root", {})
        forks = data.get("forks", [])

        G = nx.DiGraph()
        root_name = root_info.get("name", "root")
        G.add_node(root_name, stars=root_info.get("stars", 0), is_root=True)

        for fork in forks[:80]:  # Cap for readability
            name = f"{fork.get('owner', {}).get('login', '?')}/{fork.get('name', '?')}"
            stars = fork.get("stargazers_count", 0)
            G.add_node(name, stars=stars, is_root=False)
            G.add_edge(root_name, name)

        if len(G.nodes()) < 2:
            fig = go.Figure()
            fig.add_annotation(text="Not enough fork data", showarrow=False)
            apply_octobot_style(fig)
            return fig

        pos = _spring_layout(G, k=2.0)

        stars_values = [G.nodes[n].get("stars", 0) for n in G.nodes()]
        max_stars = max(stars_values) if stars_values else 1
        node_sizes = [
            20 + (s / max(1, max_stars)) * 30
            if G.nodes[n].get("is_root") else
            8 + (s / max(1, max_stars)) * 20
            for n, s in zip(G.nodes(), stars_values)
        ]
        node_colors = [
            GITHUB_PALETTE[3] if G.nodes[n].get("is_root") else GITHUB_PALETTE[1]
            for n in G.nodes()
        ]

        labels = [n.split("/")[-1] if "/" in n else n for n in G.nodes()]
        hover = [f"{n}<br>⭐ {G.nodes[n].get('stars', 0):,}" for n in G.nodes()]

        edge_trace, node_trace = _build_network_traces(
            G, pos, node_colors, node_sizes, labels, node_hover=hover
        )

        fig = go.Figure(data=[edge_trace, node_trace])
        fig.update_layout(
            title=dict(
                text=self.title or f"🍴 Fork Network: {root_name}",
                font=dict(color=OCTOBOT_THEME["text_color"], size=18),
                x=0.5,
            ),
            paper_bgcolor=OCTOBOT_THEME["paper_color"],
            plot_bgcolor=OCTOBOT_THEME["bg_color"],
            font=dict(color=OCTOBOT_THEME["text_color"]),
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            height=self.height,
            width=self.width,
            margin=dict(l=20, r=20, t=70, b=20),
            showlegend=False,
        )
        return fig


# ─── Contributor Network ──────────────────────────────────────────────────────

class ContributorNetworkChart(BaseChart):
    """
    Bipartite network: contributors connected to repositories they've contributed to.
    """

    def build(self, data: dict) -> go.Figure:
        """
        data = {
            contributors: [{login, repos: [repo_name], commits: int}],
            repos: [{name, primary_language}]
        }
        """
        contributors = data.get("contributors", [])
        repos = data.get("repos", [])

        if not contributors:
            fig = go.Figure()
            fig.add_annotation(text="No contributor network data", showarrow=False)
            apply_octobot_style(fig)
            return fig

        G = nx.Graph()

        # Add contributor nodes
        for contrib in contributors[:30]:
            login = contrib.get("login", "?")
            G.add_node(login, type="contributor", commits=contrib.get("commits", 0))

        # Add repo nodes
        for repo in repos[:20]:
            name = repo.get("name", "?")
            G.add_node(name, type="repo", language=repo.get("primary_language", ""))

        # Add edges
        for contrib in contributors[:30]:
            login = contrib.get("login", "?")
            for repo_name in contrib.get("repos", [])[:5]:
                if G.has_node(repo_name):
                    G.add_edge(login, repo_name)

        pos = _spring_layout(G, k=1.5)

        node_colors, node_sizes, labels, hover = [], [], [], []
        for node in G.nodes():
            ntype = G.nodes[node].get("type", "contributor")
            if ntype == "contributor":
                commits = G.nodes[node].get("commits", 0)
                node_colors.append(GITHUB_PALETTE[0])
                node_sizes.append(10 + min(commits / 10, 25))
                hover.append(f"👤 {node}<br>Commits: {commits:,}")
            else:
                lang = G.nodes[node].get("language", "")
                node_colors.append(GITHUB_PALETTE[1])
                node_sizes.append(14)
                hover.append(f"📁 {node}<br>Language: {lang or 'Unknown'}")
            labels.append(node[:15])

        edge_trace, node_trace = _build_network_traces(
            G, pos, node_colors, node_sizes, labels, node_hover=hover
        )

        fig = go.Figure(data=[edge_trace, node_trace])
        fig.update_layout(
            title=dict(
                text=self.title or "🌐 Contributor–Repository Network",
                font=dict(color=OCTOBOT_THEME["text_color"], size=18),
                x=0.5,
            ),
            paper_bgcolor=OCTOBOT_THEME["paper_color"],
            plot_bgcolor=OCTOBOT_THEME["bg_color"],
            font=dict(color=OCTOBOT_THEME["text_color"]),
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            height=self.height,
            width=self.width,
            margin=dict(l=20, r=20, t=70, b=20),
            showlegend=False,
        )
        return fig


# ─── Dependency Graph ─────────────────────────────────────────────────────────

class DependencyNetworkChart(BaseChart):
    """
    Directed dependency network graph from package.json / requirements.txt parsing.
    """

    def build(self, data: dict) -> go.Figure:
        """
        data = {
            name: str,
            dependencies: {name: version},
            dev_dependencies: {name: version}
        }
        """
        pkg_name = data.get("name", "root")
        deps = data.get("dependencies", {})
        dev_deps = data.get("dev_dependencies", {})

        G = nx.DiGraph()
        G.add_node(pkg_name, category="root")

        for dep in list(deps.keys())[:40]:
            G.add_node(dep, category="prod")
            G.add_edge(pkg_name, dep)

        for dep in list(dev_deps.keys())[:25]:
            G.add_node(dep, category="dev")
            G.add_edge(pkg_name, dep)

        if len(G.nodes()) <= 1:
            fig = go.Figure()
            fig.add_annotation(text="No dependency data", showarrow=False)
            apply_octobot_style(fig)
            return fig

        # Hierarchical layout (manual)
        pos = {}
        pos[pkg_name] = (0, 0)
        prod_deps = [n for n in G.nodes() if G.nodes[n].get("category") == "prod"]
        dev_deps_nodes = [n for n in G.nodes() if G.nodes[n].get("category") == "dev"]

        for i, node in enumerate(prod_deps):
            angle = (2 * math.pi * i) / max(len(prod_deps), 1)
            pos[node] = (math.cos(angle) * 2, math.sin(angle) * 2)

        for i, node in enumerate(dev_deps_nodes):
            angle = (2 * math.pi * i) / max(len(dev_deps_nodes), 1) + math.pi / 8
            pos[node] = (math.cos(angle) * 3.5, math.sin(angle) * 3.5)

        color_map = {"root": GITHUB_PALETTE[3], "prod": GITHUB_PALETTE[0], "dev": GITHUB_PALETTE[2]}
        node_colors = [color_map.get(G.nodes[n].get("category", "prod"), GITHUB_PALETTE[0]) for n in G.nodes()]
        size_map = {"root": 25, "prod": 12, "dev": 10}
        node_sizes = [size_map.get(G.nodes[n].get("category", "prod"), 10) for n in G.nodes()]
        labels = [n[:12] for n in G.nodes()]

        cat_labels = {
            "root": f"📦 {pkg_name}",
            "prod": "Production dep",
            "dev": "Dev dependency",
        }
        hover = [f"{cat_labels.get(G.nodes[n].get('category', 'prod'), '')}: {n}" for n in G.nodes()]

        # Arrow annotations for edges
        annotations = []
        for u, v in G.edges():
            if u in pos and v in pos:
                annotations.append(dict(
                    ax=pos[u][0], ay=pos[u][1],
                    axref="x", ayref="y",
                    x=pos[v][0], y=pos[v][1],
                    xref="x", yref="y",
                    showarrow=True,
                    arrowhead=2,
                    arrowsize=0.7,
                    arrowwidth=1,
                    arrowcolor=OCTOBOT_THEME["grid_color"],
                ))

        edge_trace, node_trace = _build_network_traces(
            G, pos, node_colors, node_sizes, labels, node_hover=hover
        )

        fig = go.Figure(data=[edge_trace, node_trace])
        fig.update_layout(
            title=dict(
                text=self.title or f"🌐 Dependency Network: {pkg_name}",
                font=dict(color=OCTOBOT_THEME["text_color"], size=18),
                x=0.5,
            ),
            paper_bgcolor=OCTOBOT_THEME["paper_color"],
            plot_bgcolor=OCTOBOT_THEME["bg_color"],
            font=dict(color=OCTOBOT_THEME["text_color"]),
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            annotations=annotations,
            height=self.height,
            width=self.width,
            margin=dict(l=20, r=20, t=70, b=20),
            showlegend=False,
        )
        return fig


# ─── PR Review Network ────────────────────────────────────────────────────────

class PRReviewNetworkChart(BaseChart):
    """
    Network graph where nodes are contributors and edges represent code reviews.
    Directed edge: reviewer → PR author.
    """

    def build(self, data: List[dict]) -> go.Figure:
        """data = list of PR dicts with user and reviews sub-lists."""
        G = nx.DiGraph()
        review_counts: Dict[Tuple[str, str], int] = {}

        for pr in data:
            author = pr.get("user", {}).get("login", "unknown")
            G.add_node(author, type="author")
            for review in pr.get("reviews", []):
                reviewer = review.get("user", {}).get("login", "unknown")
                if reviewer and reviewer != author:
                    G.add_node(reviewer, type="reviewer")
                    key = (reviewer, author)
                    review_counts[key] = review_counts.get(key, 0) + 1

        for (reviewer, author), count in review_counts.items():
            G.add_edge(reviewer, author, weight=count)

        if len(G.nodes()) < 2:
            fig = go.Figure()
            fig.add_annotation(text="Not enough review data for network graph", showarrow=False)
            apply_octobot_style(fig)
            return fig

        pos = _spring_layout(G, k=1.8)

        degree_map = dict(G.degree())
        node_sizes = [8 + degree_map.get(n, 0) * 3 for n in G.nodes()]
        node_colors = [
            GITHUB_PALETTE[0] if G.nodes[n].get("type") == "author" else GITHUB_PALETTE[2]
            for n in G.nodes()
        ]
        labels = list(G.nodes())
        hover = [f"@{n}<br>Connections: {degree_map.get(n, 0)}" for n in G.nodes()]

        edge_trace, node_trace = _build_network_traces(
            G, pos, node_colors, node_sizes, labels, node_hover=hover
        )

        fig = go.Figure(data=[edge_trace, node_trace])
        fig.update_layout(
            title=dict(
                text=self.title or "🌐 PR Review Network",
                font=dict(color=OCTOBOT_THEME["text_color"], size=18),
                x=0.5,
            ),
            paper_bgcolor=OCTOBOT_THEME["paper_color"],
            plot_bgcolor=OCTOBOT_THEME["bg_color"],
            font=dict(color=OCTOBOT_THEME["text_color"]),
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            height=self.height,
            width=self.width,
            margin=dict(l=20, r=20, t=70, b=20),
            showlegend=False,
        )
        return fig

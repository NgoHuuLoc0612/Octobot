"""
Octobot Visualizations Base — Shared foundations for all chart/graph generators.
"""

from __future__ import annotations

import asyncio
import io
import os
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import plotly.graph_objects as go
import plotly.express as px
import plotly.io as pio

# Set default theme
pio.templates.default = "plotly_dark"

OCTOBOT_THEME = {
    "bg_color": "#0D1117",
    "paper_color": "#161B22",
    "grid_color": "#30363D",
    "text_color": "#C9D1D9",
    "accent_1": "#238636",   # Green
    "accent_2": "#1F6FEB",   # Blue
    "accent_3": "#8957E5",   # Purple
    "accent_4": "#D29922",   # Yellow
    "accent_5": "#CF222E",   # Red
    "accent_6": "#E16F24",   # Orange
    "font_family": "Inter, Arial, sans-serif",
}

GITHUB_PALETTE = [
    "#238636", "#1F6FEB", "#8957E5", "#D29922", "#CF222E",
    "#E16F24", "#0D94D4", "#2EA44F", "#DB61A2", "#F78166",
    "#79C0FF", "#C3E88D", "#FFA657", "#FF7B72", "#D2A8FF",
]


def create_base_layout(
    title: str = "",
    xaxis_title: str = "",
    yaxis_title: str = "",
    height: int = 500,
    width: int = 900,
    show_legend: bool = True,
) -> dict:
    """Build a consistent dark GitHub-themed layout dict."""
    return dict(
        title=dict(
            text=title,
            font=dict(color=OCTOBOT_THEME["text_color"], size=18, family=OCTOBOT_THEME["font_family"]),
            x=0.5,
            xanchor="center",
        ),
        paper_bgcolor=OCTOBOT_THEME["paper_color"],
        plot_bgcolor=OCTOBOT_THEME["bg_color"],
        font=dict(color=OCTOBOT_THEME["text_color"], family=OCTOBOT_THEME["font_family"]),
        xaxis=dict(
            title=xaxis_title,
            gridcolor=OCTOBOT_THEME["grid_color"],
            linecolor=OCTOBOT_THEME["grid_color"],
            tickcolor=OCTOBOT_THEME["grid_color"],
            tickfont=dict(color=OCTOBOT_THEME["text_color"]),
            title_font=dict(color=OCTOBOT_THEME["text_color"]),
            zerolinecolor=OCTOBOT_THEME["grid_color"],
        ),
        yaxis=dict(
            title=yaxis_title,
            gridcolor=OCTOBOT_THEME["grid_color"],
            linecolor=OCTOBOT_THEME["grid_color"],
            tickcolor=OCTOBOT_THEME["grid_color"],
            tickfont=dict(color=OCTOBOT_THEME["text_color"]),
            title_font=dict(color=OCTOBOT_THEME["text_color"]),
            zerolinecolor=OCTOBOT_THEME["grid_color"],
        ),
        legend=dict(
            bgcolor="rgba(22,27,34,0.8)",
            bordercolor=OCTOBOT_THEME["grid_color"],
            borderwidth=1,
            font=dict(color=OCTOBOT_THEME["text_color"]),
        ) if show_legend else dict(visible=False),
        height=height,
        width=width,
        margin=dict(l=60, r=40, t=80, b=60),
        showlegend=show_legend,
    )


async def figure_to_bytes(fig: go.Figure, scale: float = 2.0) -> io.BytesIO:
    """
    Render a Plotly figure to a PNG BytesIO buffer asynchronously.
    Uses kaleido engine if available, falls back to orca.
    """
    loop = asyncio.get_event_loop()
    buf = await loop.run_in_executor(None, _render_figure, fig, scale)
    return buf


def _render_figure(fig: go.Figure, scale: float = 2.0) -> io.BytesIO:
    img_bytes = pio.to_image(fig, format="png", scale=scale, engine="kaleido")
    buf = io.BytesIO(img_bytes)
    buf.seek(0)
    return buf


async def figure_to_discord_file(
    fig: go.Figure,
    filename: str = None,
    scale: float = 2.0,
) -> "discord.File":
    """Convert a Plotly figure directly to a discord.File object."""
    import discord
    buf = await figure_to_bytes(fig, scale)
    fname = filename or f"octobot_{uuid.uuid4().hex[:8]}.png"
    return discord.File(buf, filename=fname)


def apply_octobot_style(fig: go.Figure) -> go.Figure:
    """Apply Octobot's GitHub-themed styling to a figure."""
    fig.update_layout(
        paper_bgcolor=OCTOBOT_THEME["paper_color"],
        plot_bgcolor=OCTOBOT_THEME["bg_color"],
        font=dict(color=OCTOBOT_THEME["text_color"], family=OCTOBOT_THEME["font_family"]),
    )
    fig.update_xaxes(
        gridcolor=OCTOBOT_THEME["grid_color"],
        linecolor=OCTOBOT_THEME["grid_color"],
        tickfont=dict(color=OCTOBOT_THEME["text_color"]),
        zerolinecolor=OCTOBOT_THEME["grid_color"],
    )
    fig.update_yaxes(
        gridcolor=OCTOBOT_THEME["grid_color"],
        linecolor=OCTOBOT_THEME["grid_color"],
        tickfont=dict(color=OCTOBOT_THEME["text_color"]),
        zerolinecolor=OCTOBOT_THEME["grid_color"],
    )
    return fig


class BaseChart(ABC):
    """Abstract base class for all Octobot chart generators."""

    def __init__(self, title: str = "", width: int = 900, height: int = 500) -> None:
        self.title = title
        self.width = width
        self.height = height

    @abstractmethod
    def build(self, data: Any) -> go.Figure:
        """Build and return a Plotly Figure from the given data."""

    async def render(self, data: Any) -> io.BytesIO:
        """Build and render the figure to a PNG BytesIO."""
        fig = self.build(data)
        return await figure_to_bytes(fig)

    async def to_discord_file(self, data: Any, filename: str = None) -> "discord.File":
        """Build, render, and return a discord.File."""
        import discord
        buf = await self.render(data)
        fname = filename or f"{self.__class__.__name__.lower()}_{uuid.uuid4().hex[:8]}.png"
        return discord.File(buf, filename=fname)

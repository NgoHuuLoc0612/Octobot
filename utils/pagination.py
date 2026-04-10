"""
Octobot Pagination — Interactive paginated views for long result sets.
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable, List, Optional

import discord


class PaginatorView(discord.ui.View):
    """
    Discord UI View for paginating through multiple embeds.
    Supports navigation buttons and page indicator.
    """

    def __init__(
        self,
        embeds: List[discord.Embed],
        author_id: int,
        timeout: float = 120.0,
    ) -> None:
        super().__init__(timeout=timeout)
        self.embeds = embeds
        self.author_id = author_id
        self.current_page = 0
        self._update_buttons()

    def _update_buttons(self) -> None:
        """Update button states based on current page."""
        self.first_page.disabled = self.current_page == 0
        self.prev_page.disabled = self.current_page == 0
        self.next_page.disabled = self.current_page >= len(self.embeds) - 1
        self.last_page.disabled = self.current_page >= len(self.embeds) - 1
        self.page_counter.label = f"{self.current_page + 1}/{len(self.embeds)}"

        # Update footer on current embed
        embed = self.embeds[self.current_page]
        footer_text = embed.footer.text or ""
        if " | Page " not in footer_text:
            embed.set_footer(
                text=f"{footer_text} | Page {self.current_page + 1}/{len(self.embeds)}".strip(" |"),
                icon_url=embed.footer.icon_url,
            )

    async def _update_message(self, interaction: discord.Interaction) -> None:
        self._update_buttons()
        await interaction.response.edit_message(
            embed=self.embeds[self.current_page], view=self
        )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "❌ Only the command invoker can use these controls.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(emoji="⏮️", style=discord.ButtonStyle.secondary, row=0)
    async def first_page(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.current_page = 0
        await self._update_message(interaction)

    @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.primary, row=0)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.current_page = max(0, self.current_page - 1)
        await self._update_message(interaction)

    @discord.ui.button(label="1/1", style=discord.ButtonStyle.secondary, disabled=True, row=0)
    async def page_counter(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        pass

    @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.primary, row=0)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.current_page = min(len(self.embeds) - 1, self.current_page + 1)
        await self._update_message(interaction)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary, row=0)
    async def last_page(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.current_page = len(self.embeds) - 1
        await self._update_message(interaction)

    @discord.ui.button(label="🗑️ Close", style=discord.ButtonStyle.danger, row=1)
    async def close_paginator(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        self.stop()
        await interaction.response.edit_message(view=None)

    async def on_timeout(self) -> None:
        """Disable all buttons on timeout."""
        for item in self.children:
            item.disabled = True


class ConfirmView(discord.ui.View):
    """Simple yes/no confirmation view."""

    def __init__(self, author_id: int, timeout: float = 30.0) -> None:
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.confirmed: Optional[bool] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "❌ Only the command invoker can confirm.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="✅ Confirm", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.confirmed = True
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.confirmed = False
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()


class SelectMenuView(discord.ui.View):
    """A select menu view for choosing from options."""

    def __init__(
        self,
        options: List[discord.SelectOption],
        author_id: int,
        placeholder: str = "Select an option...",
        timeout: float = 60.0,
        min_values: int = 1,
        max_values: int = 1,
    ) -> None:
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.selected: Optional[List[str]] = None
        menu = discord.ui.Select(
            placeholder=placeholder,
            options=options[:25],
            min_values=min_values,
            max_values=min(max_values, len(options)),
        )
        menu.callback = self._callback
        self.add_item(menu)

    async def _callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "❌ Only the command invoker can use this.", ephemeral=True
            )
            return
        self.selected = interaction.data.get("values", [])
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()


def build_list_embeds(
    title: str,
    items: List[Any],
    formatter: Callable[[Any, int], str],
    color: int,
    per_page: int = 10,
    thumbnail: str = None,
) -> List[discord.Embed]:
    """Build paginated embeds from a list of items."""
    if not items:
        embed = discord.Embed(title=title, description="No items found.", color=color)
        return [embed]

    pages = []
    for i in range(0, len(items), per_page):
        chunk = items[i : i + per_page]
        description = "\n".join(
            formatter(item, i + idx + 1) for idx, item in enumerate(chunk)
        )
        embed = discord.Embed(title=title, description=description, color=color)
        if thumbnail:
            embed.set_thumbnail(url=thumbnail)
        pages.append(embed)

    return pages


async def send_paginated(
    ctx_or_interaction,
    embeds: List[discord.Embed],
    author_id: int,
    ephemeral: bool = False,
) -> None:
    """Send paginated embeds with navigation buttons."""
    if not embeds:
        return

    if len(embeds) == 1:
        view = None
        embed = embeds[0]
    else:
        view = PaginatorView(embeds, author_id)
        embed = embeds[0]
        view._update_buttons()

    if hasattr(ctx_or_interaction, "response"):
        # Slash command interaction
        if ctx_or_interaction.response.is_done():
            await ctx_or_interaction.followup.send(
                embed=embed, view=view, ephemeral=ephemeral
            )
        else:
            await ctx_or_interaction.response.send_message(
                embed=embed, view=view, ephemeral=ephemeral
            )
    else:
        # Prefix command context
        await ctx_or_interaction.send(embed=embed, view=view)

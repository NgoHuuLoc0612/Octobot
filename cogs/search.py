"""
Octobot Search Cog — Full-text search across GitHub.
"""
from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands
from config import Colors, Emojis
from utils.embeds import build_error_embed
from utils.helpers import fmt_iso_date, fmt_number
from utils.pagination import build_list_embeds, send_paginated
from utils.github_client import GitHubAPIError


class SearchCog(commands.Cog, name="Search"):
    """Full-text search commands across GitHub."""

    def __init__(self, bot) -> None:
        self.bot = bot

    def _gh(self, user_id: int):
        return self.bot.get_github_client_for(user_id)

    @app_commands.command(name="search-repos", description="Search GitHub repositories")
    @app_commands.describe(
        query="Search query (supports GitHub search syntax)",
        sort="Sort field",
        language="Filter by programming language",
        min_stars="Minimum star count",
    )
    @app_commands.choices(sort=[
        app_commands.Choice(name="Stars", value="stars"),
        app_commands.Choice(name="Forks", value="forks"),
        app_commands.Choice(name="Updated", value="updated"),
        app_commands.Choice(name="Relevance", value=""),
    ])
    async def search_repos(
        self, interaction: discord.Interaction, query: str,
        sort: str = "stars", language: str = None, min_stars: int = None,
    ) -> None:
        await interaction.response.defer()
        full_query = query
        if language:
            full_query += f" language:{language}"
        if min_stars:
            full_query += f" stars:>={min_stars}"

        try:
            total, results = await self._gh(interaction.user.id).search_repositories(
                full_query, sort=sort or "stars", max_results=30
            )
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        if not results:
            return await interaction.followup.send(
                embed=discord.Embed(description=f"No repositories found for `{query}`.", color=Colors.NEUTRAL)
            )

        def fmt_repo(r: dict, idx: int) -> str:
            name = r.get("full_name", "?")
            stars = r.get("stargazers_count", 0)
            forks = r.get("forks_count", 0)
            lang = r.get("language") or "N/A"
            desc = r.get("description") or ""
            url = r.get("html_url", "")
            updated = fmt_iso_date(r.get("updated_at"), "d")
            return (
                f"`{idx:>2}.` [{name}]({url})"
                + (f" — {desc[:50]}" if desc else "")
                + f"\n       {Emojis.STAR}{fmt_number(stars)} · {Emojis.FORK}{fmt_number(forks)} · {lang} · {updated}"
            )

        embeds = build_list_embeds(
            title=f"{Emojis.SEARCH} Repos: \"{query}\" — {total:,} results",
            items=results,
            formatter=fmt_repo,
            color=Colors.PRIMARY,
            per_page=8,
        )
        await send_paginated(interaction, embeds, interaction.user.id)

    @app_commands.command(name="search-users", description="Search GitHub users")
    @app_commands.describe(query="Search query", sort="Sort field")
    @app_commands.choices(sort=[
        app_commands.Choice(name="Followers", value="followers"),
        app_commands.Choice(name="Repositories", value="repositories"),
        app_commands.Choice(name="Joined", value="joined"),
    ])
    async def search_users(
        self, interaction: discord.Interaction, query: str, sort: str = "followers"
    ) -> None:
        await interaction.response.defer()
        try:
            total, results = await self._gh(interaction.user.id).search_users(
                query, sort=sort, max_results=30
            )
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        if not results:
            return await interaction.followup.send(
                embed=discord.Embed(description=f"No users found for `{query}`.", color=Colors.NEUTRAL)
            )

        def fmt_user(u: dict, idx: int) -> str:
            login = u.get("login", "?")
            u_type = u.get("type", "User")
            url = u.get("html_url", "")
            repos = u.get("public_repos", 0)
            followers = u.get("followers", 0)
            return (
                f"`{idx:>2}.` {Emojis.USER} [@{login}]({url}) ({u_type})"
                + (f"\n       👥 {fmt_number(followers)} followers · 📁 {repos} repos" if followers or repos else "")
            )

        embeds = build_list_embeds(
            title=f"{Emojis.SEARCH} Users: \"{query}\" — {total:,} results",
            items=results,
            formatter=fmt_user,
            color=Colors.SECONDARY,
            per_page=10,
        )
        await send_paginated(interaction, embeds, interaction.user.id)

    @app_commands.command(name="search-issues", description="Search GitHub issues and pull requests")
    @app_commands.describe(query="Search query (e.g. 'is:open label:bug')", sort="Sort field")
    @app_commands.choices(sort=[
        app_commands.Choice(name="Created", value="created"),
        app_commands.Choice(name="Updated", value="updated"),
        app_commands.Choice(name="Comments", value="comments"),
        app_commands.Choice(name="Reactions", value="reactions"),
    ])
    async def search_issues(
        self, interaction: discord.Interaction, query: str, sort: str = "created"
    ) -> None:
        await interaction.response.defer()
        try:
            total, results = await self._gh(interaction.user.id).search_issues(
                query, sort=sort, max_results=30
            )
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        if not results:
            return await interaction.followup.send(
                embed=discord.Embed(description=f"No issues found for `{query}`.", color=Colors.NEUTRAL)
            )

        def fmt_issue(item: dict, idx: int) -> str:
            num = item.get("number", 0)
            title = item.get("title", "")[:60]
            is_pr = "pull_request" in item
            state = item.get("state", "open")
            emoji = Emojis.PR_OPEN if is_pr else (Emojis.ISSUE_OPEN if state == "open" else Emojis.ISSUE_CLOSED)
            repo_url = item.get("repository_url", "").replace("https://api.github.com/repos/", "")
            url = item.get("html_url", "")
            date = fmt_iso_date(item.get("created_at"), "d")
            return f"`{idx:>2}.` {emoji} [**#{num}**]({url}) {title}\n       📂 `{repo_url}` · {date}"

        embeds = build_list_embeds(
            title=f"{Emojis.SEARCH} Issues: \"{query}\" — {total:,} results",
            items=results,
            formatter=fmt_issue,
            color=Colors.PRIMARY,
            per_page=8,
        )
        await send_paginated(interaction, embeds, interaction.user.id)

    @app_commands.command(name="search-code", description="Search code across GitHub")
    @app_commands.describe(query="Code search query (e.g. 'async def in:file language:python')")
    async def search_code(self, interaction: discord.Interaction, query: str) -> None:
        await interaction.response.defer()
        try:
            total, results = await self._gh(interaction.user.id).search_code(query, max_results=20)
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        if not results:
            return await interaction.followup.send(
                embed=discord.Embed(description=f"No code found for `{query}`.", color=Colors.NEUTRAL)
            )

        def fmt_code(c: dict, idx: int) -> str:
            name = c.get("name", "?")
            path = c.get("path", "?")
            repo = c.get("repository", {}).get("full_name", "?")
            url = c.get("html_url", "")
            lang = c.get("language") or ""
            return (
                f"`{idx:>2}.` {Emojis.CODE} [{name}]({url})\n"
                f"       📂 `{repo}/{path}`" + (f" · {lang}" if lang else "")
            )

        embeds = build_list_embeds(
            title=f"{Emojis.SEARCH} Code: \"{query}\" — {total:,} results",
            items=results,
            formatter=fmt_code,
            color=Colors.NEUTRAL,
            per_page=8,
        )
        await send_paginated(interaction, embeds, interaction.user.id)

    @app_commands.command(name="search-commits", description="Search commits across GitHub")
    @app_commands.describe(query="Commit search query (e.g. 'fix bug author:torvalds')")
    async def search_commits(self, interaction: discord.Interaction, query: str) -> None:
        await interaction.response.defer()
        try:
            total, results = await self._gh(interaction.user.id).search_commits(query, max_results=20)
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        if not results:
            return await interaction.followup.send(
                embed=discord.Embed(description=f"No commits found for `{query}`.", color=Colors.NEUTRAL)
            )

        def fmt_commit(c: dict, idx: int) -> str:
            sha = (c.get("sha") or "")[:7]
            msg = (c.get("commit", {}).get("message") or "").split("\n")[0][:60]
            author = c.get("commit", {}).get("author", {}).get("name", "?")
            repo = c.get("repository", {}).get("full_name", "?")
            url = c.get("html_url", "")
            date = fmt_iso_date(c.get("commit", {}).get("author", {}).get("date"), "d")
            return f"`{idx:>2}.` [`{sha}`]({url}) {msg}\n       👤 {author} · 📂 `{repo}` · {date}"

        embeds = build_list_embeds(
            title=f"{Emojis.SEARCH} Commits: \"{query}\" — {total:,} results",
            items=results,
            formatter=fmt_commit,
            color=Colors.NEUTRAL,
            per_page=8,
        )
        await send_paginated(interaction, embeds, interaction.user.id)

    @app_commands.command(name="search-topics", description="Search GitHub repository topics")
    @app_commands.describe(query="Topic search query")
    async def search_topics(self, interaction: discord.Interaction, query: str) -> None:
        await interaction.response.defer()
        try:
            total, results = await self._gh(interaction.user.id).search_topics(query, max_results=20)
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        embed = discord.Embed(
            title=f"{Emojis.SEARCH} Topics: \"{query}\" — {total:,} results",
            color=Colors.SECONDARY,
        )
        if results:
            lines = []
            for t in results[:20]:
                name = t.get("name", "?")
                short_desc = t.get("short_description") or t.get("description") or ""
                featured = "⭐ " if t.get("featured") else ""
                curated = "✅ " if t.get("curated") else ""
                lines.append(
                    f"{featured}{curated}**`{name}`**"
                    + (f" — {short_desc[:60]}" if short_desc else "")
                )
            embed.description = "\n".join(lines)
        else:
            embed.description = "No topics found."
        await interaction.followup.send(embed=embed)


async def setup(bot) -> None:
    await bot.add_cog(SearchCog(bot))

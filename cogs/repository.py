"""
Octobot Repository Cog — Commands for exploring GitHub repositories.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from config import Colors, Emojis
from utils.embeds import (
    build_commit_embed,
    build_error_embed,
    build_loading_embed,
    build_repo_embed,
    build_success_embed,
)
from utils.helpers import (
    clean_body,
    compute_language_percentages,
    fmt_bytes,
    fmt_iso_date,
    fmt_number,
    parse_owner_repo,
)
from utils.pagination import PaginatorView, build_list_embeds, send_paginated
from utils.github_client import GitHubAPIError, NotFound


class RepositoryCog(commands.Cog, name="Repository"):
    """Commands for exploring GitHub repositories in depth."""

    def __init__(self, bot) -> None:
        self.bot = bot

    def _gh(self, user_id: int):
        return self.bot.get_github_client_for(user_id)

    # ─── /repo info ───────────────────────────────────────────────────────

    @app_commands.command(name="repo", description="Show detailed info about a GitHub repository")
    @app_commands.describe(repository="Repository in owner/repo format")
    async def repo_info(self, interaction: discord.Interaction, repository: str) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))

        try:
            data = await self._gh(interaction.user.id).get_repo(owner, repo)
        except NotFound:
            return await interaction.followup.send(
                embed=build_error_embed("Not Found", f"Repository `{repository}` was not found.")
            )
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        embed = build_repo_embed(data)
        await interaction.followup.send(embed=embed)

    # ─── /branches ────────────────────────────────────────────────────────

    @app_commands.command(name="branches", description="List all branches in a repository")
    @app_commands.describe(repository="owner/repo", protected="Show only protected branches")
    async def branches(
        self,
        interaction: discord.Interaction,
        repository: str,
        protected: bool = False,
    ) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))

        try:
            branches = await self._gh(interaction.user.id).get_repo_branches(owner, repo, max_results=100)
        except NotFound:
            return await interaction.followup.send(embed=build_error_embed("Not Found", f"`{repository}` not found."))
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        if protected:
            branches = [b for b in branches if b.get("protected")]

        def fmt_branch(branch: dict, idx: int) -> str:
            name = branch.get("name", "?")
            sha = (branch.get("commit", {}).get("sha") or "")[:7]
            prot = "🔒" if branch.get("protected") else "🌿"
            return f"`{idx:>2}.` {prot} **{name}** — `{sha}`"

        embeds = build_list_embeds(
            title=f"{Emojis.BRANCH} Branches — {owner}/{repo}",
            items=branches,
            formatter=fmt_branch,
            color=Colors.SECONDARY,
            per_page=15,
        )
        for e in embeds:
            e.set_footer(text=f"Total: {len(branches)} branch{'es' if len(branches) != 1 else ''}")

        await send_paginated(interaction, embeds, interaction.user.id)

    # ─── /commits ─────────────────────────────────────────────────────────

    @app_commands.command(name="commits", description="Browse recent commits in a repository")
    @app_commands.describe(
        repository="owner/repo",
        branch="Branch or SHA to list commits from",
        author="Filter by author username",
        path="Filter commits touching a specific file path",
    )
    async def commits(
        self,
        interaction: discord.Interaction,
        repository: str,
        branch: str = None,
        author: str = None,
        path: str = None,
    ) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))

        try:
            commits_data = await self._gh(interaction.user.id).get_repo_commits(
                owner, repo, sha=branch, author=author, path=path, max_results=50
            )
        except NotFound:
            return await interaction.followup.send(embed=build_error_embed("Not Found", f"`{repository}` not found."))
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        if not commits_data:
            return await interaction.followup.send(
                embed=build_error_embed("No Commits", "No commits match your filters.")
            )

        def fmt_commit(c: dict, idx: int) -> str:
            sha = (c.get("sha") or "")[:7]
            msg = (c.get("commit", {}).get("message") or "").split("\n")[0]
            author_name = (
                c.get("author", {}).get("login")
                or c.get("commit", {}).get("author", {}).get("name")
                or "unknown"
            )
            date = fmt_iso_date(c.get("commit", {}).get("author", {}).get("date"), "d")
            url = c.get("html_url", "")
            return (
                f"`{idx:>2}.` [`{sha}`]({url}) {msg[:60]}{'…' if len(msg) > 60 else ''}\n"
                f"       👤 `{author_name}` · {date}"
            )

        embeds = build_list_embeds(
            title=f"{Emojis.COMMIT} Commits — {owner}/{repo}{f' ({branch})' if branch else ''}",
            items=commits_data,
            formatter=fmt_commit,
            color=Colors.NEUTRAL,
            per_page=8,
        )
        await send_paginated(interaction, embeds, interaction.user.id)

    # ─── /commit ──────────────────────────────────────────────────────────

    @app_commands.command(name="commit", description="Show detailed info about a specific commit")
    @app_commands.describe(repository="owner/repo", sha="Commit SHA (full or short)")
    async def commit_detail(
        self,
        interaction: discord.Interaction,
        repository: str,
        sha: str,
    ) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))

        try:
            data = await self._gh(interaction.user.id).get_commit(owner, repo, sha)
        except NotFound:
            return await interaction.followup.send(
                embed=build_error_embed("Not Found", f"Commit `{sha}` not found in `{repository}`.")
            )
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        embed = build_commit_embed(data, owner, repo)
        await interaction.followup.send(embed=embed)

    # ─── /contributors ────────────────────────────────────────────────────

    @app_commands.command(name="contributors", description="List top contributors to a repository")
    @app_commands.describe(repository="owner/repo", limit="Max contributors to show (1-50)")
    async def contributors(
        self,
        interaction: discord.Interaction,
        repository: str,
        limit: app_commands.Range[int, 1, 50] = 20,
    ) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))

        try:
            data = await self._gh(interaction.user.id).get_repo_contributors(owner, repo, max_results=limit)
        except NotFound:
            return await interaction.followup.send(embed=build_error_embed("Not Found", f"`{repository}` not found."))
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        if not data:
            return await interaction.followup.send(
                embed=build_error_embed("No Data", "No contributor statistics yet.")
            )

        total_commits = sum(c.get("contributions", 0) for c in data)

        def fmt_contrib(c: dict, idx: int) -> str:
            login = c.get("login", "unknown")
            contrib = c.get("contributions", 0)
            pct = f"{contrib/max(1,total_commits)*100:.1f}%"
            url = c.get("html_url", "")
            bar = "█" * round(contrib / max(1, data[0].get("contributions", 1)) * 10)
            return f"`{idx:>2}.` [@{login}]({url}) — **{contrib:,}** commits ({pct}) `{bar}`"

        embeds = build_list_embeds(
            title=f"👥 Top Contributors — {owner}/{repo}",
            items=data,
            formatter=fmt_contrib,
            color=Colors.PRIMARY,
            per_page=10,
        )
        for e in embeds:
            e.set_footer(text=f"Total commits analyzed: {total_commits:,}")

        await send_paginated(interaction, embeds, interaction.user.id)

    # ─── /languages ───────────────────────────────────────────────────────

    @app_commands.command(name="languages", description="Show language breakdown of a repository")
    @app_commands.describe(repository="owner/repo")
    async def languages(self, interaction: discord.Interaction, repository: str) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))

        try:
            data = await self._gh(interaction.user.id).get_repo_languages(owner, repo)
        except NotFound:
            return await interaction.followup.send(embed=build_error_embed("Not Found", f"`{repository}` not found."))
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        if not data:
            return await interaction.followup.send(
                embed=build_error_embed("No Data", "No language data found.")
            )

        langs = compute_language_percentages(data)
        total_bytes = sum(data.values())

        embed = discord.Embed(
            title=f"{Emojis.LANGUAGE} Language Breakdown — {owner}/{repo}",
            color=Colors.SECONDARY,
        )

        lang_lines = []
        for lang, size, pct in langs:
            bar_fill = round(pct / 100 * 20)
            bar = "█" * bar_fill + "░" * (20 - bar_fill)
            lang_lines.append(f"**{lang}** — {pct}%\n`{bar}` {fmt_bytes(size)}")

        # Split into chunks for embed fields
        chunk_size = 6
        for i in range(0, len(lang_lines), chunk_size):
            chunk = lang_lines[i:i + chunk_size]
            embed.add_field(
                name=f"Languages ({i+1}–{min(i+chunk_size, len(lang_lines))})",
                value="\n".join(chunk),
                inline=False,
            )

        embed.set_footer(text=f"Total: {fmt_bytes(total_bytes)} across {len(langs)} languages")
        await interaction.followup.send(embed=embed)

    # ─── /topics ──────────────────────────────────────────────────────────

    @app_commands.command(name="topics", description="Show topics/tags of a repository")
    @app_commands.describe(repository="owner/repo")
    async def topics(self, interaction: discord.Interaction, repository: str) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))

        try:
            topics = await self._gh(interaction.user.id).get_repo_topics(owner, repo)
        except NotFound:
            return await interaction.followup.send(embed=build_error_embed("Not Found", f"`{repository}` not found."))
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        embed = discord.Embed(
            title=f"{Emojis.TAG} Topics — {owner}/{repo}",
            color=Colors.PRIMARY,
        )
        if topics:
            embed.description = " ".join(f"`{t}`" for t in topics)
        else:
            embed.description = "*No topics set.*"

        embed.set_footer(text=f"{len(topics)} topic(s)")
        await interaction.followup.send(embed=embed)

    # ─── /readme ──────────────────────────────────────────────────────────

    @app_commands.command(name="readme", description="Fetch and display the README of a repository")
    @app_commands.describe(repository="owner/repo", ref="Branch or tag (default: default branch)")
    async def readme(
        self,
        interaction: discord.Interaction,
        repository: str,
        ref: str = None,
    ) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))

        try:
            content = await self._gh(interaction.user.id).get_readme(owner, repo, ref=ref)
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        if content is None:
            return await interaction.followup.send(
                embed=build_error_embed("Not Found", f"No README found in `{repository}`.")
            )

        lines = content.split("\n")
        chunks = []
        current = []
        current_len = 0

        for line in lines:
            if current_len + len(line) + 1 > 1800:
                chunks.append("\n".join(current))
                current = [line]
                current_len = len(line)
            else:
                current.append(line)
                current_len += len(line) + 1
        if current:
            chunks.append("\n".join(current))

        embeds = []
        for chunk in chunks[:5]:  # limit to 5 pages
            e = discord.Embed(
                title=f"📖 README — {owner}/{repo}",
                description=chunk[:2000],
                color=Colors.SECONDARY,
            )
            embeds.append(e)

        await send_paginated(interaction, embeds, interaction.user.id)

    # ─── /forks ───────────────────────────────────────────────────────────

    @app_commands.command(name="forks", description="List notable forks of a repository")
    @app_commands.describe(
        repository="owner/repo",
        sort="Sort order: newest, oldest, stargazers, watchers",
    )
    @app_commands.choices(sort=[
        app_commands.Choice(name="Newest", value="newest"),
        app_commands.Choice(name="Oldest", value="oldest"),
        app_commands.Choice(name="Most Stars", value="stargazers"),
        app_commands.Choice(name="Most Watchers", value="watchers"),
    ])
    async def forks(
        self,
        interaction: discord.Interaction,
        repository: str,
        sort: str = "newest",
    ) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))

        try:
            data = await self._gh(interaction.user.id).get_repo_forks(owner, repo, sort=sort, max_results=30)
        except NotFound:
            return await interaction.followup.send(embed=build_error_embed("Not Found", f"`{repository}` not found."))
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        if not data:
            return await interaction.followup.send(
                embed=build_success_embed("No Forks", f"`{repository}` has no forks yet.")
            )

        def fmt_fork(f: dict, idx: int) -> str:
            name = f.get("full_name", "?")
            stars = f.get("stargazers_count", 0)
            lang = f.get("language") or "N/A"
            updated = fmt_iso_date(f.get("updated_at"), "R")
            url = f.get("html_url", "")
            return (
                f"`{idx:>2}.` [{name}]({url})\n"
                f"       {Emojis.STAR} {fmt_number(stars)} · {Emojis.LANGUAGE} {lang} · Updated {updated}"
            )

        embeds = build_list_embeds(
            title=f"{Emojis.FORK} Forks — {owner}/{repo}",
            items=data,
            formatter=fmt_fork,
            color=Colors.SECONDARY,
            per_page=8,
        )
        await send_paginated(interaction, embeds, interaction.user.id)

    # ─── /compare ─────────────────────────────────────────────────────────

    @app_commands.command(name="compare", description="Compare two branches or commits")
    @app_commands.describe(
        repository="owner/repo",
        base="Base branch/commit",
        head="Head branch/commit",
    )
    async def compare(
        self,
        interaction: discord.Interaction,
        repository: str,
        base: str,
        head: str,
    ) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))

        try:
            data = await self._gh(interaction.user.id).compare_commits(owner, repo, base, head)
        except NotFound:
            return await interaction.followup.send(
                embed=build_error_embed("Not Found", f"One of the refs was not found in `{repository}`.")
            )
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        status = data.get("status", "unknown")
        status_emoji = {"ahead": "⬆️", "behind": "⬇️", "diverged": "🔀", "identical": "🟰"}.get(status, "❓")

        embed = discord.Embed(
            title=f"🔄 Compare: `{base}` vs `{head}`",
            url=data.get("html_url", ""),
            color=Colors.INFO,
        )
        embed.add_field(name="📊 Status", value=f"{status_emoji} **{status.title()}**", inline=True)
        embed.add_field(name="📝 Commits Ahead", value=str(data.get("ahead_by", 0)), inline=True)
        embed.add_field(name="📝 Commits Behind", value=str(data.get("behind_by", 0)), inline=True)

        files = data.get("files", [])
        embed.add_field(name="📄 Files Changed", value=str(len(files)), inline=True)
        total_add = sum(f.get("additions", 0) for f in files)
        total_del = sum(f.get("deletions", 0) for f in files)
        embed.add_field(name="➕ Additions", value=str(total_add), inline=True)
        embed.add_field(name="➖ Deletions", value=str(total_del), inline=True)

        commits = data.get("commits", [])[:6]
        if commits:
            commit_lines = []
            for c in commits:
                sha = (c.get("sha") or "")[:7]
                msg = (c.get("commit", {}).get("message") or "").split("\n")[0][:60]
                url = c.get("html_url", "")
                commit_lines.append(f"[`{sha}`]({url}) {msg}")
            embed.add_field(
                name=f"Recent Commits ({data.get('total_commits', 0)} total)",
                value="\n".join(commit_lines),
                inline=False,
            )

        embed.set_footer(text=f"{owner}/{repo}")
        await interaction.followup.send(embed=embed)

    # ─── /file ────────────────────────────────────────────────────────────

    @app_commands.command(name="file", description="Preview a file's content from a repository")
    @app_commands.describe(
        repository="owner/repo",
        path="File path (e.g., src/main.py)",
        ref="Branch or commit SHA",
    )
    async def file_preview(
        self,
        interaction: discord.Interaction,
        repository: str,
        path: str,
        ref: str = None,
    ) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))

        try:
            content = await self._gh(interaction.user.id).get_file_content(owner, repo, path, ref)
        except NotFound:
            return await interaction.followup.send(
                embed=build_error_embed("Not Found", f"`{path}` not found in `{repository}`.")
            )
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        lines = content.split("\n")
        ext = path.rsplit(".", 1)[-1] if "." in path else ""
        lang_map = {
            "py": "python", "js": "javascript", "ts": "typescript",
            "go": "go", "rs": "rust", "java": "java", "cs": "csharp",
            "cpp": "cpp", "c": "c", "sh": "bash", "yaml": "yaml",
            "yml": "yaml", "json": "json", "md": "markdown",
            "html": "html", "css": "css", "sql": "sql", "rb": "ruby",
            "php": "php", "swift": "swift", "kt": "kotlin",
        }
        lang = lang_map.get(ext, "")

        preview_lines = lines[:30]
        truncated = len(lines) > 30

        preview = "\n".join(preview_lines)
        if len(preview) > 1900:
            preview = preview[:1900] + "\n..."

        embed = discord.Embed(
            title=f"{Emojis.CODE} {path}",
            url=f"https://github.com/{owner}/{repo}/blob/{ref or 'HEAD'}/{path}",
            description=f"```{lang}\n{preview}\n```",
            color=Colors.NEUTRAL,
        )
        embed.add_field(name="📄 Total Lines", value=str(len(lines)), inline=True)
        embed.add_field(name="💾 Size", value=fmt_bytes(len(content.encode())), inline=True)
        if ref:
            embed.add_field(name=f"{Emojis.BRANCH} Ref", value=f"`{ref}`", inline=True)

        if truncated:
            embed.set_footer(text=f"Showing first 30/{len(lines)} lines · {owner}/{repo}")
        else:
            embed.set_footer(text=f"{owner}/{repo}")

        await interaction.followup.send(embed=embed)

    # ─── /stargazers ──────────────────────────────────────────────────────

    @app_commands.command(name="stargazers", description="Show recent users who starred a repository")
    @app_commands.describe(repository="owner/repo")
    async def stargazers(self, interaction: discord.Interaction, repository: str) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))

        try:
            data = await self._gh(interaction.user.id).get_repo_stargazers(owner, repo, max_results=50)
        except NotFound:
            return await interaction.followup.send(embed=build_error_embed("Not Found", f"`{repository}` not found."))
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        if not data:
            return await interaction.followup.send(
                embed=build_error_embed("No Stars", f"`{repository}` has no stargazers yet.")
            )

        def fmt_gazer(u: dict, idx: int) -> str:
            login = u.get("login", "?")
            url = u.get("html_url", "")
            return f"`{idx:>2}.` {Emojis.STAR} [@{login}]({url})"

        embeds = build_list_embeds(
            title=f"{Emojis.STAR} Recent Stargazers — {owner}/{repo}",
            items=data,
            formatter=fmt_gazer,
            color=Colors.WARNING,
            per_page=15,
        )
        await send_paginated(interaction, embeds, interaction.user.id)

    # ─── /tags ────────────────────────────────────────────────────────────

    @app_commands.command(name="tags", description="List tags/versions in a repository")
    @app_commands.describe(repository="owner/repo")
    async def tags(self, interaction: discord.Interaction, repository: str) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))

        try:
            data = await self._gh(interaction.user.id).get_tags(owner, repo, max_results=30)
        except NotFound:
            return await interaction.followup.send(embed=build_error_embed("Not Found", f"`{repository}` not found."))
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        if not data:
            return await interaction.followup.send(
                embed=build_success_embed("No Tags", f"`{repository}` has no tags.")
            )

        def fmt_tag(t: dict, idx: int) -> str:
            name = t.get("name", "?")
            sha = (t.get("commit", {}).get("sha") or "")[:7]
            url = f"https://github.com/{owner}/{repo}/releases/tag/{name}"
            return f"`{idx:>2}.` {Emojis.TAG} [{name}]({url}) — `{sha}`"

        embeds = build_list_embeds(
            title=f"{Emojis.TAG} Tags — {owner}/{repo}",
            items=data,
            formatter=fmt_tag,
            color=Colors.PRIMARY,
            per_page=15,
        )
        await send_paginated(interaction, embeds, interaction.user.id)

    # ─── /traffic ─────────────────────────────────────────────────────────

    @app_commands.command(name="traffic", description="Show repository traffic statistics (requires push access)")
    @app_commands.describe(repository="owner/repo")
    async def traffic(self, interaction: discord.Interaction, repository: str) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))

        gh = self._gh(interaction.user.id)
        try:
            views, clones, paths, referrers = await asyncio.gather(
                gh.get_repo_traffic_views(owner, repo),
                gh.get_repo_traffic_clones(owner, repo),
                gh.get_repo_traffic_paths(owner, repo),
                gh.get_repo_traffic_referrers(owner, repo),
            )
        except GitHubAPIError as e:
            return await interaction.followup.send(
                embed=build_error_embed(
                    "Traffic Unavailable",
                    f"{str(e)}\n\n*Traffic data requires push access to the repository.*",
                )
            )

        embed = discord.Embed(
            title=f"📈 Traffic — {owner}/{repo}",
            color=Colors.TRENDING,
            url=f"https://github.com/{owner}/{repo}/graphs/traffic",
        )
        embed.add_field(
            name="👁️ Views (14 days)",
            value=(
                f"**Unique:** {views.get('uniques', 0):,}\n"
                f"**Total:** {views.get('count', 0):,}"
            ),
            inline=True,
        )
        embed.add_field(
            name="📥 Clones (14 days)",
            value=(
                f"**Unique:** {clones.get('uniques', 0):,}\n"
                f"**Total:** {clones.get('count', 0):,}"
            ),
            inline=True,
        )

        if referrers:
            ref_lines = [
                f"`{r.get('referrer', '?')}` — {r.get('uniques', 0):,} uniques"
                for r in referrers[:5]
            ]
            embed.add_field(name="🔗 Top Referrers", value="\n".join(ref_lines), inline=False)

        if paths:
            path_lines = [
                f"`{p.get('path', '?')}` — {p.get('uniques', 0):,} uniques"
                for p in paths[:5]
            ]
            embed.add_field(name="📂 Popular Paths", value="\n".join(path_lines), inline=False)

        await interaction.followup.send(embed=embed)


async def setup(bot) -> None:
    await bot.add_cog(RepositoryCog(bot))

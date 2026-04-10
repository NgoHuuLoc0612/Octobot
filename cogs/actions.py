"""
Octobot Actions Cog — GitHub Actions workflow commands.
"""
from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands
from config import Colors, Emojis
from utils.embeds import build_error_embed, build_workflow_run_embed
from utils.helpers import fmt_iso_date, parse_owner_repo
from utils.pagination import build_list_embeds, send_paginated
from utils.github_client import GitHubAPIError, NotFound


class ActionsCog(commands.Cog, name="Actions"):
    """GitHub Actions workflow monitoring commands."""

    def __init__(self, bot) -> None:
        self.bot = bot

    def _gh(self, user_id: int):
        return self.bot.get_github_client_for(user_id)

    @app_commands.command(name="workflows", description="List workflows in a repository")
    @app_commands.describe(repository="owner/repo")
    async def workflows(self, interaction: discord.Interaction, repository: str) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))

        try:
            workflows = await self._gh(interaction.user.id).get_workflows(owner, repo)
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        if not workflows:
            return await interaction.followup.send(
                embed=discord.Embed(description="No workflows found.", color=Colors.NEUTRAL)
            )

        state_emoji = {"active": "✅", "deleted": "🗑️", "disabled_manually": "⛔", "disabled_inactivity": "💤"}

        def fmt_workflow(w: dict, idx: int) -> str:
            name = w.get("name", "?")
            state = w.get("state", "unknown")
            emoji = state_emoji.get(state, "❓")
            wid = w.get("id", 0)
            path = w.get("path", "?")
            url = w.get("html_url", "")
            return f"`{idx:>2}.` {emoji} [{name}]({url})\n       ID: `{wid}` · Path: `{path}`"

        embeds = build_list_embeds(
            title=f"{Emojis.WORKFLOW} Workflows — {owner}/{repo}",
            items=workflows,
            formatter=fmt_workflow,
            color=Colors.SUCCESS,
            per_page=8,
        )
        await send_paginated(interaction, embeds, interaction.user.id)

    @app_commands.command(name="workflow-runs", description="List recent workflow runs")
    @app_commands.describe(
        repository="owner/repo",
        workflow="Workflow name or ID (optional)",
        status="Filter by status",
        branch="Filter by branch",
    )
    @app_commands.choices(status=[
        app_commands.Choice(name="All", value=""),
        app_commands.Choice(name="Queued", value="queued"),
        app_commands.Choice(name="In Progress", value="in_progress"),
        app_commands.Choice(name="Completed", value="completed"),
        app_commands.Choice(name="Success", value="success"),
        app_commands.Choice(name="Failure", value="failure"),
    ])
    async def workflow_runs(
        self, interaction: discord.Interaction, repository: str,
        workflow: str = None, status: str = "", branch: str = None,
    ) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))

        try:
            runs = await self._gh(interaction.user.id).get_workflow_runs(
                owner, repo,
                workflow_id=workflow,
                status=status or None,
                branch=branch,
                max_results=20,
            )
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        if not runs:
            return await interaction.followup.send(
                embed=discord.Embed(description="No workflow runs found.", color=Colors.NEUTRAL)
            )

        from utils.helpers import workflow_status_emoji

        def fmt_run(r: dict, idx: int) -> str:
            name = r.get("name", "?")
            conclusion = r.get("conclusion")
            s = r.get("status", "unknown")
            emoji = workflow_status_emoji(s, conclusion)
            run_num = r.get("run_number", "?")
            branch_name = r.get("head_branch", "?")
            event = r.get("event", "?")
            date = fmt_iso_date(r.get("updated_at"), "R")
            url = r.get("html_url", "")
            return (
                f"`{idx:>2}.` {emoji} [Run #{run_num}]({url}) — **{name}**\n"
                f"       🌿 `{branch_name}` · {event} · {date}"
            )

        embeds = build_list_embeds(
            title=f"{Emojis.ACTION} Workflow Runs — {owner}/{repo}",
            items=runs,
            formatter=fmt_run,
            color=Colors.SECONDARY,
            per_page=8,
        )
        await send_paginated(interaction, embeds, interaction.user.id)

    @app_commands.command(name="workflow-run", description="Show details of a specific workflow run")
    @app_commands.describe(repository="owner/repo", run_id="Workflow run ID")
    async def workflow_run(
        self, interaction: discord.Interaction, repository: str, run_id: int
    ) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))

        try:
            run = await self._gh(interaction.user.id).get_workflow_run(owner, repo, run_id)
            jobs = await self._gh(interaction.user.id).get_workflow_run_jobs(owner, repo, run_id)
        except NotFound:
            return await interaction.followup.send(embed=build_error_embed("Not Found", f"Run {run_id} not found."))
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        embed = build_workflow_run_embed(run, owner, repo)

        if jobs:
            from utils.helpers import workflow_status_emoji
            job_lines = []
            for job in jobs[:8]:
                jname = job.get("name", "?")
                jconclusion = job.get("conclusion")
                jstatus = job.get("status", "unknown")
                jemoji = workflow_status_emoji(jstatus, jconclusion)
                jurl = job.get("html_url", "")
                job_lines.append(f"{jemoji} [{jname}]({jurl})")
            embed.add_field(
                name=f"🔧 Jobs ({len(jobs)})",
                value="\n".join(job_lines),
                inline=False,
            )

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="artifacts", description="List artifacts for a repository or run")
    @app_commands.describe(repository="owner/repo", run_id="Specific run ID (optional)")
    async def artifacts(
        self, interaction: discord.Interaction, repository: str, run_id: int = None
    ) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))

        try:
            if run_id:
                arts = await self._gh(interaction.user.id).get_workflow_run_artifacts(owner, repo, run_id)
            else:
                arts = await self._gh(interaction.user.id).get_artifacts(owner, repo, max_results=20)
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        if not arts:
            return await interaction.followup.send(
                embed=discord.Embed(description="No artifacts found.", color=Colors.NEUTRAL)
            )

        def fmt_art(a: dict, idx: int) -> str:
            name = a.get("name", "?")
            size = a.get("size_in_bytes", 0)
            from utils.helpers import fmt_bytes
            size_str = fmt_bytes(size)
            expired = "⚠️ Expired" if a.get("expired") else "✅ Available"
            expires = fmt_iso_date(a.get("expires_at"), "d")
            return f"`{idx:>2}.` 📦 **{name}**\n       {size_str} · {expired} · Expires {expires}"

        embeds = build_list_embeds(
            title=f"📦 Artifacts — {owner}/{repo}" + (f" · Run #{run_id}" if run_id else ""),
            items=arts,
            formatter=fmt_art,
            color=Colors.SECONDARY,
            per_page=8,
        )
        await send_paginated(interaction, embeds, interaction.user.id)

    @app_commands.command(name="secrets", description="List repository action secrets (names only)")
    @app_commands.describe(repository="owner/repo")
    async def secrets(self, interaction: discord.Interaction, repository: str) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)), ephemeral=True)

        try:
            secrets_list = await self._gh(interaction.user.id).list_repo_secrets(owner, repo)
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)), ephemeral=True)

        embed = discord.Embed(
            title=f"🔒 Action Secrets — {owner}/{repo}",
            color=Colors.NEUTRAL,
        )
        if secrets_list:
            lines = [
                f"`{i+1}.` 🔑 **{s.get('name', '?')}** — updated {fmt_iso_date(s.get('updated_at'), 'R')}"
                for i, s in enumerate(secrets_list)
            ]
            embed.description = "\n".join(lines)
        else:
            embed.description = "No secrets configured."

        embed.set_footer(text="Secret values are never revealed — names only.")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="variables", description="List repository action variables")
    @app_commands.describe(repository="owner/repo")
    async def variables(self, interaction: discord.Interaction, repository: str) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)), ephemeral=True)

        try:
            vars_list = await self._gh(interaction.user.id).list_repo_variables(owner, repo)
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)), ephemeral=True)

        embed = discord.Embed(
            title=f"⚙️ Action Variables — {owner}/{repo}",
            color=Colors.NEUTRAL,
        )
        if vars_list:
            lines = [
                f"`{i+1}.` **{v.get('name', '?')}** = `{str(v.get('value',''))[:40]}`"
                for i, v in enumerate(vars_list)
            ]
            embed.description = "\n".join(lines)
        else:
            embed.description = "No variables configured."
        await interaction.followup.send(embed=embed, ephemeral=True)


    @app_commands.command(name="workflow", description="Show details of a specific workflow by name or ID")
    @app_commands.describe(repository="owner/repo", workflow="Workflow file name or numeric ID")
    async def workflow_detail(
        self, interaction: discord.Interaction, repository: str, workflow: str
    ) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))

        try:
            # Try numeric ID first, then treat as filename
            wid: int | str = int(workflow) if workflow.isdigit() else workflow
            data = await self._gh(interaction.user.id).get_workflow(owner, repo, wid)
        except NotFound:
            return await interaction.followup.send(embed=build_error_embed("Not Found", f"Workflow `{workflow}` not found."))
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        state_map = {
            "active": ("✅", Colors.SUCCESS),
            "deleted": ("🗑️", Colors.DANGER),
            "disabled_manually": ("⛔", Colors.WARNING),
            "disabled_inactivity": ("💤", Colors.NEUTRAL),
        }
        state = data.get("state", "unknown")
        emoji, color = state_map.get(state, ("❓", Colors.NEUTRAL))

        embed = discord.Embed(
            title=f"{Emojis.WORKFLOW} {data.get('name', 'Workflow')}",
            url=data.get("html_url", ""),
            color=color,
        )
        embed.add_field(name="📄 File Path", value=f"`{data.get('path', 'N/A')}`", inline=True)
        embed.add_field(name="🆔 ID", value=f"`{data.get('id', 'N/A')}`", inline=True)
        embed.add_field(name="⚡ State", value=f"{emoji} {state.replace('_', ' ').title()}", inline=True)
        embed.add_field(name="📅 Created", value=fmt_iso_date(data.get("created_at"), "F"), inline=True)
        embed.add_field(name="🔄 Updated", value=fmt_iso_date(data.get("updated_at"), "R"), inline=True)
        embed.set_footer(text=f"{owner}/{repo}")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="workflow-jobs", description="List jobs in a specific workflow run")
    @app_commands.describe(repository="owner/repo", run_id="Workflow run ID")
    async def workflow_jobs(
        self, interaction: discord.Interaction, repository: str, run_id: int
    ) -> None:
        await interaction.response.defer()
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)))

        try:
            jobs = await self._gh(interaction.user.id).get_workflow_run_jobs(owner, repo, run_id)
        except NotFound:
            return await interaction.followup.send(embed=build_error_embed("Not Found", f"Run `{run_id}` not found."))
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)))

        if not jobs:
            return await interaction.followup.send(
                embed=discord.Embed(description="No jobs found for this run.", color=Colors.NEUTRAL)
            )

        from utils.helpers import fmt_duration, workflow_status_emoji

        def fmt_job(j: dict, idx: int) -> str:
            name = j.get("name", "?")
            conclusion = j.get("conclusion")
            status = j.get("status", "unknown")
            emoji = workflow_status_emoji(status, conclusion)
            started = j.get("started_at")
            completed = j.get("completed_at")
            duration = ""
            if started and completed:
                from datetime import datetime
                try:
                    s = datetime.fromisoformat(started.replace("Z", "+00:00"))
                    c = datetime.fromisoformat(completed.replace("Z", "+00:00"))
                    duration = f" · ⏱️ {fmt_duration((c - s).total_seconds())}"
                except Exception:
                    pass
            steps = j.get("steps", [])
            url = j.get("html_url", "")
            return (
                f"`{idx:>2}.` {emoji} [{name}]({url}){duration}\n"
                f"       🔩 {len(steps)} step(s) · Runner: `{j.get('runner_name') or 'N/A'}`"
            )

        embeds = build_list_embeds(
            title=f"🔧 Jobs — Run #{run_id} · {owner}/{repo}",
            items=jobs,
            formatter=fmt_job,
            color=Colors.SECONDARY,
            per_page=8,
        )
        await send_paginated(interaction, embeds, interaction.user.id)

    @app_commands.command(name="job-logs", description="Get the logs download URL for a workflow job")
    @app_commands.describe(repository="owner/repo", job_id="Job ID (from workflow-jobs command)")
    async def job_logs(
        self, interaction: discord.Interaction, repository: str, job_id: int
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            owner, repo = parse_owner_repo(repository)
        except ValueError as e:
            return await interaction.followup.send(embed=build_error_embed("Invalid Format", str(e)), ephemeral=True)

        try:
            url = await self._gh(interaction.user.id).get_job_logs_url(owner, repo, job_id)
        except NotFound:
            return await interaction.followup.send(embed=build_error_embed("Not Found", f"Job `{job_id}` not found."), ephemeral=True)
        except GitHubAPIError as e:
            return await interaction.followup.send(embed=build_error_embed("API Error", str(e)), ephemeral=True)

        embed = discord.Embed(
            title=f"📋 Job Logs — Job #{job_id}",
            color=Colors.NEUTRAL,
        )
        if url:
            embed.description = f"[📥 Download Logs]({url})\n\n*Link expires after a short time.*"
        else:
            embed.description = "Logs are not available (job may still be running or logs have expired)."
        embed.set_footer(text=f"{owner}/{repo}")
        await interaction.followup.send(embed=embed, ephemeral=True)



async def setup(bot) -> None:
    await bot.add_cog(ActionsCog(bot))

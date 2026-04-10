<p align="center">
  <img src="Ub5jT.jpg" width="120"/><br/>
  <b>Octobot</b>
</p>

# 🐙 Octobot — GitHub Bot for Discord

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://python.org)
[![discord.py 2.3+](https://img.shields.io/badge/discord.py-2.3%2B-5865F2)](https://discordpy.readthedocs.io)
[![GitHub API v3](https://img.shields.io/badge/GitHub%20API-v3%20%2B%20GraphQL-black)](https://docs.github.com/en/rest)

Octobot is a comprehensive, enterprise-grade Discord bot providing deep GitHub integration — from repository browsing and CI/CD monitoring to advanced data analytics with 3D charts, network graphs, Sankey diagrams, heatmaps, and treemaps.

---

## ✨ Feature Highlights

| Category | Features |
|---|---|
| **Repositories** | Info, branches, commits, file preview, traffic, compare, stargazers, forks |
| **Issues** | List, detail, comments, timeline, labels, milestones |
| **Pull Requests** | List, detail, files changed, reviews, commits, merge status |
| **GitHub Actions** | Workflows, runs, jobs, artifacts, secrets, variables |
| **Releases** | History, latest release, assets, pre-releases |
| **Users** | Profiles, repos, starred, followers, events, organizations |
| **Organizations** | Profile, repos, members, teams |
| **Gists** | View, list, file preview |
| **Search** | Repos, users, issues, code, commits, topics |
| **Notifications** | Subscribe to push, issues, PRs, releases, stars, forks |
| **2D Charts** | Commit activity, language pie, contributor bar, code frequency, punch card, bubble, scatter, PR cycle time, label distribution, workflow status |
| **3D Charts** | Commit history scatter, contributor bars, repo metrics surface, language evolution |
| **Network Graphs** | Fork networks, contributor–repo bipartite, dependency graphs, PR review networks |
| **Sankey Diagrams** | PR lifecycle flow, CI/CD pipeline flow, contribution flow, issue triage |
| **Heatmaps** | GitHub contribution calendar, weekly activity, commit correlation |
| **Treemaps** | Language distribution, repository topics |

---

## 🗂️ Project Structure

```
octobot/
├── main.py                    # Entry point, bot class, lifecycle
├── config.py                  # Configuration, Colors, Emojis constants
├── requirements.txt
├── .env.example
│
├── cogs/                      # Discord command extensions
│   ├── repository.py          # /repo, /branches, /commits, /file, /compare, ...
│   ├── issues.py              # /issues, /issue, /labels, /milestones, ...
│   ├── pull_requests.py       # /prs, /pr, /pr-files, /pr-reviews, ...
│   ├── actions.py             # /workflows, /workflow-runs, /artifacts, ...
│   ├── releases.py            # /releases, /release
│   ├── user.py                # /user, /user-repos, /link-github, /whoami, ...
│   ├── organization.py        # /org, /org-repos, /org-members, /org-teams
│   ├── gist.py                # /gist, /user-gists, /gist-file
│   ├── search.py              # /search-repos, /search-users, /search-code, ...
│   ├── visualizations.py      # All chart/graph/heatmap commands
│   ├── notifications.py       # /subscribe, /unsubscribe, /subscriptions
│   ├── admin.py               # /ping, /botinfo, /rate-limit, owner commands
│   └── help.py                # /help, /quickstart
│
├── utils/                     # Shared utilities
│   ├── github_client.py       # Async GitHub REST + GraphQL client
│   ├── cache.py               # In-memory LRU cache with TTL
│   ├── embeds.py              # Discord embed builders for all GitHub entities
│   ├── helpers.py             # Formatters, parsers, and utilities
│   └── pagination.py          # Interactive paginated embeds
│
├── visualizations/            # Chart generators
│   ├── base.py                # Base class, theme constants, helpers
│   ├── charts_2d.py           # Bar, line, scatter, bubble, pie, punch card
│   ├── charts_3d.py           # 3D scatter, surface, bar charts
│   ├── network_graph.py       # Fork tree, contributor, dependency, PR review networks
│   ├── sankey.py              # PR flow, CI/CD, contribution, issue triage
│   └── heatmaps.py            # Contribution calendar, activity, treemaps, correlation
│
└── database/
    └── manager.py             # SQLAlchemy async DB with all models and queries
```

---

## 🚀 Setup & Installation

### Prerequisites

- Python 3.11 or higher
- A [Discord bot token](https://discord.com/developers/applications)
- A [GitHub Personal Access Token](https://github.com/settings/tokens) with scopes:
  `repo`, `read:org`, `read:user`, `gist`, `notifications`

### 1. Clone and Install

```bash
git clone https://github.com/yourname/octobot.git
cd octobot
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env with your Discord token and GitHub token
```

### 3. Invite Bot to Discord

In the Discord Developer Portal, generate an OAuth2 URL with:
- **Scopes**: `bot`, `applications.commands`
- **Permissions**: `Send Messages`, `Embed Links`, `Attach Files`, `Read Message History`, `Use External Emojis`

### 4. Run

```bash
python main.py
```

On first run, slash commands are synced globally (may take up to 1 hour to propagate).

---

## 📊 Example Commands

```
/repo torvalds/linux
/issues microsoft/vscode state:open labels:bug
/pr microsoft/typescript 50000
/chart-commits nodejs/node
/heatmap-contributions torvalds
/sankey-cicd vercel/next.js
/graph-forks facebook/react
/chart-3d-commits rust-lang/rust
/treemap-languages google
/search-repos language:rust stars:>5000 sort:stars
/subscribe torvalds/linux push #dev-feed
```

---

## 🔑 GitHub Token Scopes

| Scope | Used For |
|---|---|
| `repo` | Private repo access, traffic stats, secrets |
| `read:org` | Organization members and teams |
| `read:user` | User profile details |
| `gist` | Gist access |
| `notifications` | Notification polling |

For public-only use, a token with no scopes works for all public data (5,000 req/hr authenticated vs. 60/hr unauthenticated).

---

## 🏗️ Architecture

- **`Octobot`** class extends `discord.ext.commands.Bot` with lifecycle management, per-user GitHub clients, and background tasks.
- **`GitHubClient`** wraps the REST v3 and GraphQL v4 APIs with transparent caching, rate limit awareness, and automatic retry with exponential backoff.
- **`CacheManager`** is an async LRU cache with per-entry TTL, used to reduce repeated API calls.
- **`DatabaseManager`** uses SQLAlchemy async with SQLite (default) or PostgreSQL, storing guild config, user links, subscriptions, and command logs.
- **Visualization pipeline**: Data fetched via `GitHubClient` → passed to chart class `.build()` → rendered to PNG via Plotly/Kaleido → sent as Discord embed with `discord.File`.

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

"""
Octobot GitHub Client — Async-first GitHub API wrapper with rate limiting,
caching, GraphQL support, and graceful error handling.
"""

from __future__ import annotations

import asyncio
import base64
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import quote

import aiohttp

from utils.cache import CacheManager

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
GITHUB_GRAPHQL = "https://api.github.com/graphql"


class GitHubAPIError(Exception):
    """Raised when GitHub API returns an error response."""
    def __init__(self, message: str, status: int = 0, response: dict = None):
        super().__init__(message)
        self.status = status
        self.response = response or {}


class RateLimitExceeded(GitHubAPIError):
    """Raised when GitHub rate limit is hit."""
    def __init__(self, reset_at: datetime):
        self.reset_at = reset_at
        super().__init__(
            f"GitHub rate limit exceeded. Resets at {reset_at.strftime('%H:%M UTC')}",
            status=429,
        )


class NotFound(GitHubAPIError):
    """Raised for 404 responses."""
    def __init__(self, resource: str = "Resource"):
        super().__init__(f"{resource} not found.", status=404)


class Forbidden(GitHubAPIError):
    """Raised for 403/401 responses."""
    pass


# ─── GitHub Client ────────────────────────────────────────────────────────────

class GitHubClient:
    """
    Async GitHub REST + GraphQL API client.

    Features:
    - Transparent caching with configurable TTL
    - Automatic rate limit handling with backoff
    - Pagination support (both cursor and page-based)
    - Full REST and GraphQL support
    - Per-request authentication
    """

    def __init__(
        self,
        token: Optional[str] = None,
        cache: Optional[CacheManager] = None,
        base_url: str = GITHUB_API,
        graphql_url: str = GITHUB_GRAPHQL,
    ) -> None:
        self.token = token
        self.cache = cache
        self.base_url = base_url.rstrip("/")
        self.graphql_url = graphql_url
        self._session: Optional[aiohttp.ClientSession] = None
        self._rate_limit_remaining: int = 5000
        self._rate_limit_reset: Optional[datetime] = None

    # ── Session Management ─────────────────────────────────────────────────

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            headers = {
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "Octobot/2.0 Discord-GitHub-Bot",
            }
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"

            self._session = aiohttp.ClientSession(
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            )
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    # ── Core Request ──────────────────────────────────────────────────────

    async def _request(
        self,
        method: str,
        endpoint: str,
        *,
        params: Optional[dict] = None,
        json: Optional[dict] = None,
        use_cache: bool = True,
        cache_ttl: Optional[int] = None,
    ) -> Any:
        """Execute an authenticated GitHub REST API request."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        cache_key = f"gh:{method}:{url}:{params}"

        # Check cache for GET requests
        if method == "GET" and use_cache and self.cache:
            cached = await self.cache.get(cache_key)
            if cached is not None:
                return cached

        # Rate limit pre-check
        if self._rate_limit_remaining <= 10 and self._rate_limit_reset:
            raise RateLimitExceeded(self._rate_limit_reset)

        session = await self._get_session()

        for attempt in range(3):
            try:
                async with session.request(
                    method, url, params=params, json=json
                ) as resp:
                    # Update rate limit headers
                    self._update_rate_limits(resp.headers)

                    if resp.status == 204:
                        return None

                    data = await resp.json(content_type=None)

                    if resp.status == 200 or resp.status == 201:
                        if method == "GET" and use_cache and self.cache:
                            await self.cache.set(cache_key, data, ttl=cache_ttl)
                        return data

                    elif resp.status == 304:
                        if self.cache:
                            return await self.cache.get(cache_key)
                        return None

                    elif resp.status == 401:
                        raise Forbidden("Authentication required or token invalid.")

                    elif resp.status == 403:
                        if "rate limit" in str(data.get("message", "")).lower():
                            raise RateLimitExceeded(self._rate_limit_reset or datetime.utcnow())
                        raise Forbidden(data.get("message", "Forbidden"))

                    elif resp.status == 404:
                        raise NotFound()

                    elif resp.status == 422:
                        raise GitHubAPIError(
                            data.get("message", "Validation failed"),
                            status=422,
                            response=data,
                        )

                    elif resp.status == 429:
                        raise RateLimitExceeded(self._rate_limit_reset or datetime.utcnow())

                    elif resp.status >= 500:
                        if attempt < 2:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        raise GitHubAPIError(f"GitHub server error: {resp.status}", status=resp.status)

                    else:
                        raise GitHubAPIError(
                            data.get("message", f"HTTP {resp.status}"),
                            status=resp.status,
                            response=data,
                        )

            except aiohttp.ClientError as exc:
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise GitHubAPIError(f"Network error: {exc}") from exc

        raise GitHubAPIError("Max retries exceeded.")

    def _update_rate_limits(self, headers: aiohttp.ClientResponse.headers) -> None:
        remaining = headers.get("X-RateLimit-Remaining")
        reset = headers.get("X-RateLimit-Reset")
        if remaining is not None:
            self._rate_limit_remaining = int(remaining)
        if reset is not None:
            self._rate_limit_reset = datetime.utcfromtimestamp(int(reset))

    async def _graphql(self, query: str, variables: dict = None) -> dict:
        """Execute a GitHub GraphQL query."""
        session = await self._get_session()
        payload = {"query": query, "variables": variables or {}}
        async with session.post(self.graphql_url, json=payload) as resp:
            data = await resp.json()
            if "errors" in data:
                raise GitHubAPIError(
                    "; ".join(e["message"] for e in data["errors"])
                )
            return data.get("data", {})

    async def get_rate_limit(self) -> dict:
        return await self._request("GET", "/rate_limit", use_cache=False)

    # ── Pagination ────────────────────────────────────────────────────────

    async def _paginate(
        self, endpoint: str, params: dict = None, max_results: int = 100
    ) -> List[dict]:
        """Fetch all pages from a paginated endpoint."""
        params = params or {}
        params["per_page"] = min(100, max_results)
        results = []
        page = 1

        while True:
            params["page"] = page
            data = await self._request("GET", endpoint, params=params)

            if not data:
                break

            if isinstance(data, dict):
                items = data.get("items", data.get("repositories", data.get("users", [])))
            else:
                items = data

            results.extend(items)

            if len(items) < params["per_page"] or len(results) >= max_results:
                break
            page += 1

        return results[:max_results]

    # ── Repository ────────────────────────────────────────────────────────

    async def get_repo(self, owner: str, repo: str) -> dict:
        return await self._request("GET", f"/repos/{owner}/{repo}")

    async def get_repo_topics(self, owner: str, repo: str) -> List[str]:
        data = await self._request("GET", f"/repos/{owner}/{repo}/topics")
        return data.get("names", [])

    async def get_repo_languages(self, owner: str, repo: str) -> dict:
        return await self._request("GET", f"/repos/{owner}/{repo}/languages")

    async def get_repo_contributors(
        self, owner: str, repo: str, anon: bool = False, max_results: int = 50
    ) -> List[dict]:
        params = {"anon": str(anon).lower()}
        return await self._paginate(
            f"/repos/{owner}/{repo}/contributors", params=params, max_results=max_results
        )

    async def get_repo_branches(
        self, owner: str, repo: str, max_results: int = 50
    ) -> List[dict]:
        return await self._paginate(
            f"/repos/{owner}/{repo}/branches", max_results=max_results
        )

    async def get_branch(self, owner: str, repo: str, branch: str) -> dict:
        return await self._request("GET", f"/repos/{owner}/{repo}/branches/{branch}")

    async def get_repo_commits(
        self,
        owner: str,
        repo: str,
        sha: str = None,
        path: str = None,
        author: str = None,
        since: str = None,
        until: str = None,
        max_results: int = 30,
    ) -> List[dict]:
        params = {}
        if sha: params["sha"] = sha
        if path: params["path"] = path
        if author: params["author"] = author
        if since: params["since"] = since
        if until: params["until"] = until
        return await self._paginate(
            f"/repos/{owner}/{repo}/commits", params=params, max_results=max_results
        )

    async def get_commit(self, owner: str, repo: str, sha: str) -> dict:
        return await self._request("GET", f"/repos/{owner}/{repo}/commits/{sha}")

    async def get_repo_forks(
        self, owner: str, repo: str, sort: str = "newest", max_results: int = 30
    ) -> List[dict]:
        return await self._paginate(
            f"/repos/{owner}/{repo}/forks",
            params={"sort": sort},
            max_results=max_results,
        )

    async def get_repo_stargazers(
        self, owner: str, repo: str, max_results: int = 50
    ) -> List[dict]:
        return await self._paginate(
            f"/repos/{owner}/{repo}/stargazers", max_results=max_results
        )

    async def get_repo_watchers(
        self, owner: str, repo: str, max_results: int = 50
    ) -> List[dict]:
        return await self._paginate(
            f"/repos/{owner}/{repo}/subscribers", max_results=max_results
        )

    async def get_readme(self, owner: str, repo: str, ref: str = None) -> Optional[str]:
        try:
            params = {}
            if ref:
                params["ref"] = ref
            data = await self._request("GET", f"/repos/{owner}/{repo}/readme", params=params)
            content = data.get("content", "")
            return base64.b64decode(content).decode("utf-8", errors="replace")
        except NotFound:
            return None

    async def get_repo_contents(
        self, owner: str, repo: str, path: str = "", ref: str = None
    ) -> Union[dict, List[dict]]:
        params = {}
        if ref:
            params["ref"] = ref
        return await self._request("GET", f"/repos/{owner}/{repo}/contents/{path}", params=params)

    async def get_file_content(self, owner: str, repo: str, path: str, ref: str = None) -> str:
        data = await self.get_repo_contents(owner, repo, path, ref)
        if isinstance(data, dict) and data.get("encoding") == "base64":
            return base64.b64decode(data["content"]).decode("utf-8", errors="replace")
        raise GitHubAPIError("Cannot decode file content.")

    async def get_commit_activity(self, owner: str, repo: str) -> List[dict]:
        """Get weekly commit activity for the last year."""
        return await self._request("GET", f"/repos/{owner}/{repo}/stats/commit_activity")

    async def get_code_frequency(self, owner: str, repo: str) -> List[List[int]]:
        """Get weekly code additions and deletions."""
        return await self._request("GET", f"/repos/{owner}/{repo}/stats/code_frequency")

    async def get_contributor_stats(self, owner: str, repo: str) -> List[dict]:
        """Get contributor commit statistics."""
        return await self._request("GET", f"/repos/{owner}/{repo}/stats/contributors")

    async def get_participation_stats(self, owner: str, repo: str) -> dict:
        """Get owner and all commit counts per week."""
        return await self._request("GET", f"/repos/{owner}/{repo}/stats/participation")

    async def get_punch_card(self, owner: str, repo: str) -> List[List[int]]:
        """Get hourly commit count for each day."""
        return await self._request("GET", f"/repos/{owner}/{repo}/stats/punch_card")

    async def get_repo_traffic_views(self, owner: str, repo: str) -> dict:
        return await self._request("GET", f"/repos/{owner}/{repo}/traffic/views")

    async def get_repo_traffic_clones(self, owner: str, repo: str) -> dict:
        return await self._request("GET", f"/repos/{owner}/{repo}/traffic/clones")

    async def get_repo_traffic_paths(self, owner: str, repo: str) -> List[dict]:
        return await self._request("GET", f"/repos/{owner}/{repo}/traffic/popular/paths")

    async def get_repo_traffic_referrers(self, owner: str, repo: str) -> List[dict]:
        return await self._request("GET", f"/repos/{owner}/{repo}/traffic/popular/referrers")

    async def compare_commits(
        self, owner: str, repo: str, base: str, head: str
    ) -> dict:
        return await self._request("GET", f"/repos/{owner}/{repo}/compare/{base}...{head}")

    async def list_user_repos(
        self,
        username: str,
        type: str = "all",
        sort: str = "updated",
        direction: str = "desc",
        max_results: int = 30,
    ) -> List[dict]:
        return await self._paginate(
            f"/users/{username}/repos",
            params={"type": type, "sort": sort, "direction": direction},
            max_results=max_results,
        )

    # ── Issues ────────────────────────────────────────────────────────────

    async def get_issues(
        self,
        owner: str,
        repo: str,
        state: str = "open",
        labels: str = None,
        assignee: str = None,
        milestone: str = None,
        sort: str = "created",
        direction: str = "desc",
        since: str = None,
        max_results: int = 30,
    ) -> List[dict]:
        params = {"state": state, "sort": sort, "direction": direction}
        if labels: params["labels"] = labels
        if assignee: params["assignee"] = assignee
        if milestone: params["milestone"] = milestone
        if since: params["since"] = since
        data = await self._paginate(
            f"/repos/{owner}/{repo}/issues", params=params, max_results=max_results
        )
        return [i for i in data if "pull_request" not in i]

    async def get_issue(self, owner: str, repo: str, number: int) -> dict:
        return await self._request("GET", f"/repos/{owner}/{repo}/issues/{number}")

    async def get_issue_comments(
        self, owner: str, repo: str, number: int, max_results: int = 20
    ) -> List[dict]:
        return await self._paginate(
            f"/repos/{owner}/{repo}/issues/{number}/comments", max_results=max_results
        )

    async def get_issue_timeline(
        self, owner: str, repo: str, number: int, max_results: int = 30
    ) -> List[dict]:
        return await self._paginate(
            f"/repos/{owner}/{repo}/issues/{number}/timeline", max_results=max_results
        )

    async def get_labels(self, owner: str, repo: str) -> List[dict]:
        return await self._paginate(f"/repos/{owner}/{repo}/labels")

    async def get_milestones(
        self, owner: str, repo: str, state: str = "open"
    ) -> List[dict]:
        return await self._paginate(
            f"/repos/{owner}/{repo}/milestones", params={"state": state}
        )

    async def get_milestone(self, owner: str, repo: str, number: int) -> dict:
        return await self._request("GET", f"/repos/{owner}/{repo}/milestones/{number}")

    # ── Pull Requests ─────────────────────────────────────────────────────

    async def get_pull_requests(
        self,
        owner: str,
        repo: str,
        state: str = "open",
        head: str = None,
        base: str = None,
        sort: str = "created",
        direction: str = "desc",
        max_results: int = 30,
    ) -> List[dict]:
        params = {"state": state, "sort": sort, "direction": direction}
        if head: params["head"] = head
        if base: params["base"] = base
        return await self._paginate(
            f"/repos/{owner}/{repo}/pulls", params=params, max_results=max_results
        )

    async def get_pull_request(self, owner: str, repo: str, number: int) -> dict:
        return await self._request("GET", f"/repos/{owner}/{repo}/pulls/{number}")

    async def get_pr_reviews(
        self, owner: str, repo: str, number: int
    ) -> List[dict]:
        return await self._paginate(f"/repos/{owner}/{repo}/pulls/{number}/reviews")

    async def get_pr_review_comments(
        self, owner: str, repo: str, number: int
    ) -> List[dict]:
        return await self._paginate(f"/repos/{owner}/{repo}/pulls/{number}/comments")

    async def get_pr_files(
        self, owner: str, repo: str, number: int
    ) -> List[dict]:
        return await self._paginate(f"/repos/{owner}/{repo}/pulls/{number}/files")

    async def get_pr_commits(
        self, owner: str, repo: str, number: int
    ) -> List[dict]:
        return await self._paginate(f"/repos/{owner}/{repo}/pulls/{number}/commits")

    async def is_pr_merged(self, owner: str, repo: str, number: int) -> bool:
        try:
            await self._request("GET", f"/repos/{owner}/{repo}/pulls/{number}/merge")
            return True
        except NotFound:
            return False

    # ── Users ─────────────────────────────────────────────────────────────

    async def get_user(self, username: str) -> dict:
        return await self._request("GET", f"/users/{username}")

    async def get_authenticated_user(self) -> dict:
        return await self._request("GET", "/user", use_cache=False)

    async def get_user_followers(
        self, username: str, max_results: int = 50
    ) -> List[dict]:
        return await self._paginate(
            f"/users/{username}/followers", max_results=max_results
        )

    async def get_user_following(
        self, username: str, max_results: int = 50
    ) -> List[dict]:
        return await self._paginate(
            f"/users/{username}/following", max_results=max_results
        )

    async def get_user_events(
        self, username: str, max_results: int = 30
    ) -> List[dict]:
        return await self._paginate(
            f"/users/{username}/events/public", max_results=max_results
        )

    async def get_user_starred(
        self, username: str, sort: str = "created", max_results: int = 30
    ) -> List[dict]:
        return await self._paginate(
            f"/users/{username}/starred",
            params={"sort": sort},
            max_results=max_results,
        )

    async def get_user_subscriptions(
        self, username: str, max_results: int = 30
    ) -> List[dict]:
        return await self._paginate(
            f"/users/{username}/subscriptions", max_results=max_results
        )

    async def get_user_orgs(self, username: str) -> List[dict]:
        return await self._paginate(f"/users/{username}/orgs")

    async def get_user_hovercard(self, username: str) -> dict:
        return await self._request("GET", f"/users/{username}/hovercard")

    # ── Organizations ─────────────────────────────────────────────────────

    async def get_org(self, org: str) -> dict:
        return await self._request("GET", f"/orgs/{org}")

    async def get_org_repos(
        self,
        org: str,
        type: str = "all",
        sort: str = "updated",
        max_results: int = 50,
    ) -> List[dict]:
        return await self._paginate(
            f"/orgs/{org}/repos",
            params={"type": type, "sort": sort},
            max_results=max_results,
        )

    async def get_org_members(
        self, org: str, role: str = "all", max_results: int = 50
    ) -> List[dict]:
        return await self._paginate(
            f"/orgs/{org}/members",
            params={"role": role},
            max_results=max_results,
        )

    async def get_org_teams(self, org: str) -> List[dict]:
        return await self._paginate(f"/orgs/{org}/teams")

    async def get_team(self, org: str, team_slug: str) -> dict:
        return await self._request("GET", f"/orgs/{org}/teams/{team_slug}")

    async def get_team_members(
        self, org: str, team_slug: str, max_results: int = 50
    ) -> List[dict]:
        return await self._paginate(
            f"/orgs/{org}/teams/{team_slug}/members", max_results=max_results
        )

    async def get_team_repos(
        self, org: str, team_slug: str, max_results: int = 50
    ) -> List[dict]:
        return await self._paginate(
            f"/orgs/{org}/teams/{team_slug}/repos", max_results=max_results
        )

    # ── Gists ─────────────────────────────────────────────────────────────

    async def get_gist(self, gist_id: str) -> dict:
        return await self._request("GET", f"/gists/{gist_id}")

    async def get_user_gists(self, username: str, max_results: int = 30) -> List[dict]:
        return await self._paginate(f"/users/{username}/gists", max_results=max_results)

    async def get_public_gists(self, max_results: int = 30) -> List[dict]:
        return await self._paginate("/gists/public", max_results=max_results)

    async def get_gist_commits(self, gist_id: str) -> List[dict]:
        return await self._paginate(f"/gists/{gist_id}/commits")

    async def get_gist_forks(self, gist_id: str) -> List[dict]:
        return await self._paginate(f"/gists/{gist_id}/forks")

    async def get_gist_comments(self, gist_id: str) -> List[dict]:
        return await self._paginate(f"/gists/{gist_id}/comments")

    # ── Search ────────────────────────────────────────────────────────────

    async def search_repositories(
        self,
        query: str,
        sort: str = "stars",
        order: str = "desc",
        max_results: int = 30,
    ) -> Tuple[int, List[dict]]:
        data = await self._request(
            "GET", "/search/repositories",
            params={"q": query, "sort": sort, "order": order, "per_page": min(max_results, 100)}
        )
        return data.get("total_count", 0), data.get("items", [])

    async def search_issues(
        self,
        query: str,
        sort: str = "created",
        order: str = "desc",
        max_results: int = 30,
    ) -> Tuple[int, List[dict]]:
        data = await self._request(
            "GET", "/search/issues",
            params={"q": query, "sort": sort, "order": order, "per_page": min(max_results, 100)}
        )
        return data.get("total_count", 0), data.get("items", [])

    async def search_users(
        self,
        query: str,
        sort: str = "followers",
        order: str = "desc",
        max_results: int = 30,
    ) -> Tuple[int, List[dict]]:
        data = await self._request(
            "GET", "/search/users",
            params={"q": query, "sort": sort, "order": order, "per_page": min(max_results, 100)}
        )
        return data.get("total_count", 0), data.get("items", [])

    async def search_code(
        self,
        query: str,
        sort: str = "indexed",
        order: str = "desc",
        max_results: int = 30,
    ) -> Tuple[int, List[dict]]:
        data = await self._request(
            "GET", "/search/code",
            params={"q": query, "sort": sort, "order": order, "per_page": min(max_results, 100)}
        )
        return data.get("total_count", 0), data.get("items", [])

    async def search_commits(
        self,
        query: str,
        sort: str = "author-date",
        order: str = "desc",
        max_results: int = 30,
    ) -> Tuple[int, List[dict]]:
        data = await self._request(
            "GET", "/search/commits",
            params={"q": query, "sort": sort, "order": order, "per_page": min(max_results, 100)}
        )
        return data.get("total_count", 0), data.get("items", [])

    async def search_topics(self, query: str, max_results: int = 20) -> Tuple[int, List[dict]]:
        data = await self._request(
            "GET", "/search/topics",
            params={"q": query, "per_page": min(max_results, 100)}
        )
        return data.get("total_count", 0), data.get("items", [])

    async def search_labels(
        self, repo_id: int, query: str, max_results: int = 20
    ) -> Tuple[int, List[dict]]:
        data = await self._request(
            "GET", "/search/labels",
            params={"repository_id": repo_id, "q": query, "per_page": min(max_results, 100)}
        )
        return data.get("total_count", 0), data.get("items", [])

    # ── GitHub Actions ────────────────────────────────────────────────────

    async def get_workflows(self, owner: str, repo: str) -> List[dict]:
        data = await self._request("GET", f"/repos/{owner}/{repo}/actions/workflows")
        return data.get("workflows", [])

    async def get_workflow(
        self, owner: str, repo: str, workflow_id: Union[int, str]
    ) -> dict:
        return await self._request(
            "GET", f"/repos/{owner}/{repo}/actions/workflows/{workflow_id}"
        )

    async def get_workflow_runs(
        self,
        owner: str,
        repo: str,
        workflow_id: Union[int, str] = None,
        status: str = None,
        branch: str = None,
        event: str = None,
        max_results: int = 20,
    ) -> List[dict]:
        if workflow_id:
            endpoint = f"/repos/{owner}/{repo}/actions/workflows/{workflow_id}/runs"
        else:
            endpoint = f"/repos/{owner}/{repo}/actions/runs"
        params = {}
        if status: params["status"] = status
        if branch: params["branch"] = branch
        if event: params["event"] = event
        data = await self._request("GET", endpoint, params={**params, "per_page": max_results})
        return data.get("workflow_runs", [])[:max_results]

    async def get_workflow_run(
        self, owner: str, repo: str, run_id: int
    ) -> dict:
        return await self._request("GET", f"/repos/{owner}/{repo}/actions/runs/{run_id}")

    async def get_workflow_run_jobs(
        self, owner: str, repo: str, run_id: int
    ) -> List[dict]:
        data = await self._request(
            "GET", f"/repos/{owner}/{repo}/actions/runs/{run_id}/jobs"
        )
        return data.get("jobs", [])

    async def get_workflow_run_artifacts(
        self, owner: str, repo: str, run_id: int
    ) -> List[dict]:
        data = await self._request(
            "GET", f"/repos/{owner}/{repo}/actions/runs/{run_id}/artifacts"
        )
        return data.get("artifacts", [])

    async def get_artifacts(self, owner: str, repo: str, max_results: int = 20) -> List[dict]:
        data = await self._request(
            "GET", f"/repos/{owner}/{repo}/actions/artifacts",
            params={"per_page": max_results}
        )
        return data.get("artifacts", [])

    async def list_repo_secrets(self, owner: str, repo: str) -> List[dict]:
        data = await self._request("GET", f"/repos/{owner}/{repo}/actions/secrets")
        return data.get("secrets", [])

    async def list_repo_variables(self, owner: str, repo: str) -> List[dict]:
        data = await self._request("GET", f"/repos/{owner}/{repo}/actions/variables")
        return data.get("variables", [])

    async def get_job_logs_url(
        self, owner: str, repo: str, job_id: int
    ) -> str:
        resp = await self._request("GET", f"/repos/{owner}/{repo}/actions/jobs/{job_id}/logs")
        return resp if isinstance(resp, str) else ""

    # ── Releases ──────────────────────────────────────────────────────────

    async def get_releases(
        self, owner: str, repo: str, max_results: int = 20
    ) -> List[dict]:
        return await self._paginate(
            f"/repos/{owner}/{repo}/releases", max_results=max_results
        )

    async def get_latest_release(self, owner: str, repo: str) -> dict:
        return await self._request("GET", f"/repos/{owner}/{repo}/releases/latest")

    async def get_release(self, owner: str, repo: str, release_id: int) -> dict:
        return await self._request(
            "GET", f"/repos/{owner}/{repo}/releases/{release_id}"
        )

    async def get_release_by_tag(self, owner: str, repo: str, tag: str) -> dict:
        return await self._request(
            "GET", f"/repos/{owner}/{repo}/releases/tags/{tag}"
        )

    async def get_tags(self, owner: str, repo: str, max_results: int = 30) -> List[dict]:
        return await self._paginate(
            f"/repos/{owner}/{repo}/tags", max_results=max_results
        )

    # ── Notifications ─────────────────────────────────────────────────────

    async def get_notifications(
        self,
        all: bool = False,
        participating: bool = False,
        since: str = None,
    ) -> List[dict]:
        params = {"all": str(all).lower(), "participating": str(participating).lower()}
        if since:
            params["since"] = since
        return await self._request("GET", "/notifications", params=params, use_cache=False)

    async def mark_all_notifications_read(self) -> None:
        await self._request("PUT", "/notifications", json={})

    async def get_thread(self, thread_id: int) -> dict:
        return await self._request("GET", f"/notifications/threads/{thread_id}")

    async def mark_thread_read(self, thread_id: int) -> None:
        await self._request("PATCH", f"/notifications/threads/{thread_id}")

    # ── Webhooks ──────────────────────────────────────────────────────────

    async def list_repo_webhooks(self, owner: str, repo: str) -> List[dict]:
        return await self._paginate(f"/repos/{owner}/{repo}/hooks")

    async def get_repo_webhook(
        self, owner: str, repo: str, hook_id: int
    ) -> dict:
        return await self._request("GET", f"/repos/{owner}/{repo}/hooks/{hook_id}")

    async def ping_repo_webhook(
        self, owner: str, repo: str, hook_id: int
    ) -> None:
        await self._request("POST", f"/repos/{owner}/{repo}/hooks/{hook_id}/pings")

    # ── Dependency Graph ──────────────────────────────────────────────────

    async def get_dependency_manifest(
        self, owner: str, repo: str
    ) -> dict:
        return await self._request(
            "GET", f"/repos/{owner}/{repo}/dependency-graph/sbom"
        )

    async def get_dependabot_alerts(
        self, owner: str, repo: str, state: str = "open"
    ) -> List[dict]:
        return await self._paginate(
            f"/repos/{owner}/{repo}/dependabot/alerts",
            params={"state": state},
        )

    # ── Code Scanning ─────────────────────────────────────────────────────

    async def get_code_scanning_alerts(
        self,
        owner: str,
        repo: str,
        state: str = "open",
        severity: str = None,
    ) -> List[dict]:
        params = {"state": state}
        if severity:
            params["severity"] = severity
        return await self._paginate(
            f"/repos/{owner}/{repo}/code-scanning/alerts", params=params
        )

    # ── Secret Scanning ───────────────────────────────────────────────────

    async def get_secret_scanning_alerts(
        self, owner: str, repo: str, state: str = "open"
    ) -> List[dict]:
        return await self._paginate(
            f"/repos/{owner}/{repo}/secret-scanning/alerts",
            params={"state": state},
        )

    # ── Projects ──────────────────────────────────────────────────────────

    async def get_repo_projects(
        self, owner: str, repo: str, state: str = "open"
    ) -> List[dict]:
        return await self._paginate(
            f"/repos/{owner}/{repo}/projects", params={"state": state}
        )

    async def get_org_projects(self, org: str, state: str = "open") -> List[dict]:
        return await self._paginate(
            f"/orgs/{org}/projects", params={"state": state}
        )

    # ── Repository Insights (GraphQL) ─────────────────────────────────────

    async def get_repo_insights(self, owner: str, repo: str) -> dict:
        """Fetch rich repository insights via GraphQL."""
        query = """
        query RepoInsights($owner: String!, $repo: String!) {
          repository(owner: $owner, name: $repo) {
            name
            description
            isPrivate
            isFork
            isArchived
            stargazerCount
            forkCount
            watchers { totalCount }
            issues(states: OPEN) { totalCount }
            pullRequests(states: OPEN) { totalCount }
            closedIssues: issues(states: CLOSED) { totalCount }
            mergedPRs: pullRequests(states: MERGED) { totalCount }
            defaultBranchRef {
              name
              target {
                ... on Commit {
                  committedDate
                  history { totalCount }
                }
              }
            }
            languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
              totalSize
              edges {
                size
                node { name color }
              }
            }
            releases(first: 1, orderBy: {field: CREATED_AT, direction: DESC}) {
              nodes {
                name
                tagName
                publishedAt
                isPrerelease
              }
            }
            repositoryTopics(first: 20) {
              nodes {
                topic { name }
              }
            }
            diskUsage
            createdAt
            updatedAt
            pushedAt
            licenseInfo { name spdxId url }
            primaryLanguage { name color }
            codeOfConduct { name }
            hasIssuesEnabled
            hasWikiEnabled
            hasDiscussionsEnabled
            securityPolicyUrl
          }
        }
        """
        return await self._graphql(query, {"owner": owner, "repo": repo})

    async def get_user_contributions(self, username: str, year: int = None) -> dict:
        """Fetch user contribution calendar via GraphQL."""
        from_date = f"{year or datetime.utcnow().year}-01-01T00:00:00Z"
        to_date = f"{year or datetime.utcnow().year}-12-31T23:59:59Z"
        query = """
        query UserContributions($login: String!, $from: DateTime!, $to: DateTime!) {
          user(login: $login) {
            name
            login
            contributionsCollection(from: $from, to: $to) {
              totalCommitContributions
              totalIssueContributions
              totalPullRequestContributions
              totalPullRequestReviewContributions
              totalRepositoryContributions
              contributionCalendar {
                totalContributions
                weeks {
                  contributionDays {
                    contributionCount
                    date
                    color
                  }
                }
              }
              commitContributionsByRepository(maxRepositories: 10) {
                repository { nameWithOwner url primaryLanguage { name color } }
                contributions { totalCount }
              }
            }
          }
        }
        """
        return await self._graphql(
            query, {"login": username, "from": from_date, "to": to_date}
        )

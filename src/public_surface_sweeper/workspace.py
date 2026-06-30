from __future__ import annotations

import os
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from .sweeper import Finding, scan, summarize_findings

WORKSPACE_SKIP_DIRS = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".superpowers",
    ".telos",
    ".tox",
    ".venv",
    ".vscode",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "target",
}
PUBLIC_DELIVERY_RULES = {
    "em-dash",
    "readme-public-delivery",
    "readme-visual-asset",
    "required-file",
}
DEVELOPER_DELIVERY_RULES = {"readme-developer-delivery"}
SECRET_RULE_PREFIXES = (
    "aws-access-key",
    "github-token",
    "openai-key",
    "private-key",
    "secret-assignment",
    "slack-token",
)


def discover_forward_facing_repos(roots: Iterable[Path]) -> list[Path]:
    repos: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        for repo in _iter_git_repos(Path(root)):
            resolved = repo.resolve()
            if resolved in seen or github_remote_slug(repo) is None:
                continue
            repos.append(repo)
            seen.add(resolved)
    return sorted(repos, key=lambda path: path.name.lower())


def build_delivery_matrix(roots: Iterable[Path]) -> dict[str, Any]:
    root_list = [Path(root).resolve() for root in roots]
    repositories = []
    counts = Counter({"MATCH": 0, "DRIFT": 0, "UNVERIFIABLE": 0})
    for repo in discover_forward_facing_repos(root_list):
        item = _repo_delivery_record(repo, root_list)
        repositories.append(item)
        counts[item["status"]] += 1
    return {
        "schema": "public-surface-sweeper.delivery-matrix/v1",
        "repository_count": len(repositories),
        "counts": dict(counts),
        "privacy_boundary": {
            "absolute_paths_included": False,
            "raw_secret_values_included": False,
            "network_calls_performed": False,
            "filesystem_writes_performed": False,
        },
        "repositories": repositories,
    }


def format_delivery_matrix(matrix: dict[str, Any]) -> str:
    counts = matrix["counts"]
    lines = [
        "workspace_delivery_matrix:",
        f"repositories: {matrix['repository_count']}",
        (
            "counts: "
            f"MATCH={counts['MATCH']} "
            f"DRIFT={counts['DRIFT']} "
            f"UNVERIFIABLE={counts['UNVERIFIABLE']}"
        ),
        "items:",
    ]
    if not matrix["repositories"]:
        return "\n".join(lines + ["- none"])
    for repo in matrix["repositories"]:
        lines.extend(_format_repo_lines(repo))
    return "\n".join(lines)


def github_remote_slug(repo: Path) -> str | None:
    for url in _remote_urls(repo):
        slug = _github_slug_from_url(url)
        if slug is not None:
            return slug
    return None


def _iter_git_repos(root: Path) -> Iterable[Path]:
    if not root.exists():
        return
    for current, dirnames, _ in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in WORKSPACE_SKIP_DIRS]
        current_path = Path(current)
        git_config = current_path / ".git" / "config"
        if git_config.is_file():
            yield current_path
            dirnames[:] = []


def _repo_delivery_record(repo: Path, roots: list[Path]) -> dict[str, Any]:
    try:
        findings = scan(repo)
    except OSError as exc:
        return _unverifiable_record(repo, roots, str(exc))
    summary = summarize_findings(findings)
    public_verdict = _rule_verdict(findings, PUBLIC_DELIVERY_RULES)
    developer_verdict = _rule_verdict(findings, DEVELOPER_DELIVERY_RULES)
    boundary_verdict = _boundary_verdict(findings)
    status = _overall_status(public_verdict, developer_verdict, boundary_verdict)
    return {
        "name": repo.name,
        "path": _display_path(repo, roots),
        "remote": github_remote_slug(repo),
        "status": status,
        "score": summary.score,
        "public_delivery": public_verdict,
        "developer_delivery": developer_verdict,
        "boundary": boundary_verdict,
        "findings": {
            "total": summary.total_findings,
            "errors": summary.errors,
            "warnings": summary.warnings,
            "rules": dict(Counter(item.rule for item in findings)),
            "action_items": summary.action_items,
        },
    }


def _unverifiable_record(repo: Path, roots: list[Path], reason: str) -> dict[str, Any]:
    return {
        "name": repo.name,
        "path": _display_path(repo, roots),
        "remote": github_remote_slug(repo),
        "status": "UNVERIFIABLE",
        "score": 0,
        "public_delivery": "UNVERIFIABLE",
        "developer_delivery": "UNVERIFIABLE",
        "boundary": "UNVERIFIABLE",
        "findings": {
            "total": 1,
            "errors": 1,
            "warnings": 0,
            "rules": {"scan-error": 1},
            "action_items": [f"scan-error: {reason}"],
        },
    }


def _rule_verdict(findings: list[Finding], rules: set[str]) -> str:
    return "DRIFT" if any(item.rule in rules for item in findings) else "MATCH"


def _boundary_verdict(findings: list[Finding]) -> str:
    for item in findings:
        if item.rule in SECRET_RULE_PREFIXES:
            return "DRIFT"
    return "MATCH"


def _overall_status(*verdicts: str) -> str:
    if "UNVERIFIABLE" in verdicts:
        return "UNVERIFIABLE"
    if "DRIFT" in verdicts:
        return "DRIFT"
    return "MATCH"


def _display_path(repo: Path, roots: list[Path]) -> str:
    resolved = repo.resolve()
    for root in roots:
        try:
            rel = resolved.relative_to(root)
        except ValueError:
            continue
        return rel.as_posix() or repo.name
    return repo.name


def _remote_urls(repo: Path) -> list[str]:
    config = repo / ".git" / "config"
    try:
        text = config.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return [
        match.group("url").strip()
        for match in re.finditer(r"^\s*url\s*=\s*(?P<url>\S+)\s*$", text, re.MULTILINE)
    ]


def _github_slug_from_url(url: str) -> str | None:
    patterns = (
        r"^git@github\.com:(?P<slug>[^/]+/[^/]+?)(?:\.git)?$",
        r"^https://github\.com/(?P<slug>[^/]+/[^/]+?)(?:\.git)?/?$",
        r"^ssh://git@github\.com/(?P<slug>[^/]+/[^/]+?)(?:\.git)?/?$",
    )
    for pattern in patterns:
        match = re.match(pattern, url)
        if match:
            return match.group("slug")
    return None


def _format_repo_lines(repo: dict[str, Any]) -> list[str]:
    lines = [
        (
            f"- {repo['name']} ({repo['remote']}): {repo['status']} "
            f"score={repo['score']} public={repo['public_delivery']} "
            f"developer={repo['developer_delivery']}"
        )
    ]
    for item in repo["findings"]["action_items"][:3]:
        lines.append(f"  action: {item}")
    return lines

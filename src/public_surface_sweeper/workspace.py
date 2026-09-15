from __future__ import annotations

import os
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .sweeper import Finding, scan_delivery_surface, summarize_findings

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
    "_deps",
    "build",
    "coverage",
    "dist",
    "external",
    "node_modules",
    "target",
    "third_party",
    "vendor",
    "vcpkg",
}
PUBLIC_DELIVERY_RULES = {
    "em-dash",
    "public-changelog",
    "public-funding",
    "readme-public-delivery",
    "readme-visual-asset",
    "required-file",
}
DEVELOPER_DELIVERY_RULES = {
    "developer-agent-instructions",
    "developer-ci-workflow",
    "developer-usage-doc",
    "readme-developer-delivery",
}
SECRET_RULE_PREFIXES = (
    "aws-access-key",
    "github-token",
    "openai-key",
    "private-key",
    "secret-assignment",
    "slack-token",
)
GIT_METADATA_READ_LIMIT_BYTES = 8192


@dataclass(frozen=True)
class _GitDirs:
    git_dir: Path
    common_dir: Path


@dataclass(frozen=True)
class _RepoCandidate:
    path: Path
    remote: str | None
    metadata_error: str | None = None


def discover_forward_facing_repos(roots: Iterable[Path]) -> list[Path]:
    repos_by_remote: dict[str, Path] = {}
    for root in roots:
        for candidate in _iter_git_repo_candidates(Path(root)):
            if candidate.metadata_error is not None or candidate.remote is None:
                continue
            current = repos_by_remote.get(candidate.remote)
            if current is None or _repo_rank(candidate.path) < _repo_rank(current):
                repos_by_remote[candidate.remote] = candidate.path
    return sorted(repos_by_remote.values(), key=lambda path: path.name.lower())


def build_delivery_matrix(roots: Iterable[Path]) -> dict[str, Any]:
    root_list = [Path(root).resolve() for root in roots]
    repositories = []
    counts = Counter({"MATCH": 0, "DRIFT": 0, "UNVERIFIABLE": 0})
    for candidate in _discover_delivery_candidates(root_list):
        if candidate.metadata_error is not None:
            item = _unverifiable_record(
                candidate.path,
                root_list,
                candidate.metadata_error,
                remote=candidate.remote,
                rule="git-metadata",
            )
        else:
            item = _repo_delivery_record(candidate.path, root_list, candidate.remote)
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
    urls, _ = _remote_urls_with_error(repo)
    for url in urls:
        slug = _github_slug_from_url(url)
        if slug is not None:
            return slug
    return None


def _iter_git_repos(root: Path) -> Iterable[Path]:
    for candidate in _iter_git_repo_candidates(root):
        if candidate.metadata_error is None and candidate.remote is not None:
            yield candidate.path


def _discover_delivery_candidates(roots: Iterable[Path]) -> list[_RepoCandidate]:
    repos_by_remote: dict[str, _RepoCandidate] = {}
    unverifiable_by_path: dict[Path, _RepoCandidate] = {}
    for root in roots:
        for candidate in _iter_git_repo_candidates(root):
            if candidate.metadata_error is not None:
                unverifiable_by_path[candidate.path.resolve()] = candidate
                continue
            if candidate.remote is None:
                continue
            current = repos_by_remote.get(candidate.remote)
            if current is None or _repo_rank(candidate.path) < _repo_rank(current.path):
                repos_by_remote[candidate.remote] = candidate
    candidates = list(repos_by_remote.values()) + list(unverifiable_by_path.values())
    return sorted(candidates, key=lambda candidate: candidate.path.name.lower())


def _iter_git_repo_candidates(root: Path) -> Iterable[_RepoCandidate]:
    if not root.exists():
        return
    for current, dirnames, _ in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in WORKSPACE_SKIP_DIRS]
        current_path = Path(current)
        if _has_git_metadata(current_path):
            urls, error = _remote_urls_with_error(current_path)
            slug = None
            for url in urls:
                slug = _github_slug_from_url(url)
                if slug is not None:
                    break
            yield _RepoCandidate(current_path, slug, error)
            if slug is not None or error is not None:
                dirnames[:] = []


def _repo_delivery_record(
    repo: Path, roots: list[Path], remote: str | None = None
) -> dict[str, Any]:
    try:
        findings = scan_delivery_surface(repo)
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
        "remote": remote if remote is not None else github_remote_slug(repo),
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


def _unverifiable_record(
    repo: Path,
    roots: list[Path],
    reason: str,
    remote: str | None = None,
    rule: str = "scan-error",
) -> dict[str, Any]:
    return {
        "name": repo.name,
        "path": _display_path(repo, roots),
        "remote": remote if remote is not None else github_remote_slug(repo),
        "status": "UNVERIFIABLE",
        "score": 0,
        "public_delivery": "UNVERIFIABLE",
        "developer_delivery": "UNVERIFIABLE",
        "boundary": "UNVERIFIABLE",
        "findings": {
            "total": 1,
            "errors": 1,
            "warnings": 0,
            "rules": {rule: 1},
            "action_items": [f"{rule}: {reason}"],
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


def _has_git_metadata(repo: Path) -> bool:
    git_entry = repo / ".git"
    return git_entry.is_dir() or git_entry.is_file()


def _remote_urls(repo: Path) -> list[str]:
    urls, _ = _remote_urls_with_error(repo)
    return urls


def _remote_urls_with_error(repo: Path) -> tuple[list[str], str | None]:
    dirs, error = _git_dirs(repo)
    if error is not None or dirs is None:
        return [], error
    text, error = _read_required_git_config(dirs.common_dir / "config")
    if error is not None:
        return [], error
    texts = [text]
    worktree_config = dirs.git_dir / "config.worktree"
    if worktree_config.is_file():
        worktree_text, error = _read_git_metadata_text(worktree_config, "worktree config")
        if error is not None:
            return [], error
        texts.append(worktree_text)
    return [
        match.group("url").strip()
        for config_text in texts
        for match in re.finditer(
            r"^\s*url\s*=\s*(?P<url>\S+)\s*$", config_text, re.MULTILINE
        )
    ], None


def _git_dirs(repo: Path) -> tuple[_GitDirs | None, str | None]:
    git_entry = repo / ".git"
    if git_entry.is_dir():
        return _GitDirs(git_entry, git_entry), None
    if not git_entry.is_file():
        return None, None
    text, error = _read_git_metadata_text(git_entry, ".git file")
    if error is not None:
        return None, error
    line = text.strip().splitlines()[0] if text.strip() else ""
    match = re.match(r"^gitdir:\s*(?P<path>.+?)\s*$", line)
    if not match:
        return None, ".git file is not a gitdir pointer"
    git_dir, error = _resolve_git_metadata_path(match.group("path"), repo, ".git file")
    if error is not None or git_dir is None:
        return None, error
    if not git_dir.is_dir():
        return None, ".git file points to a missing gitdir"
    common_dir = git_dir
    commondir_file = git_dir / "commondir"
    if commondir_file.is_file():
        commondir_text, error = _read_git_metadata_text(commondir_file, "commondir file")
        if error is not None:
            return None, error
        commondir_line = (
            commondir_text.strip().splitlines()[0] if commondir_text.strip() else ""
        )
        if not commondir_line:
            return None, "commondir file is empty"
        common_dir, error = _resolve_git_metadata_path(
            commondir_line, git_dir, "commondir file"
        )
        if error is not None or common_dir is None:
            return None, error
        if not common_dir.is_dir():
            return None, "commondir file points to a missing directory"
    return _GitDirs(git_dir, common_dir), None


def _resolve_git_metadata_path(
    raw_path: str, base: Path, label: str
) -> tuple[Path | None, str | None]:
    if any(ord(char) < 32 for char in raw_path):
        return None, f"{label} path is malformed"
    normalized = raw_path.strip().strip('"')
    if not normalized:
        return None, f"{label} path is missing"
    try:
        path = Path(normalized)
        if not path.is_absolute():
            path = base / path
        return path.resolve(), None
    except (OSError, ValueError):
        return None, f"{label} path is malformed"


def _read_required_git_config(config: Path) -> tuple[str, str | None]:
    if not config.is_file():
        return "", "git config is missing"
    return _read_git_metadata_text(config, "git config")


def _read_git_metadata_text(path: Path, label: str) -> tuple[str, str | None]:
    try:
        if path.stat().st_size > GIT_METADATA_READ_LIMIT_BYTES:
            return "", f"{label} exceeds {GIT_METADATA_READ_LIMIT_BYTES} byte limit"
        return path.read_text(encoding="utf-8", errors="replace"), None
    except OSError:
        return "", f"{label} could not be read"


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


def _repo_rank(path: Path) -> tuple[int, int, str]:
    parts = {part.lower() for part in path.parts}
    mirror_penalty = 1 if "pubscan" in parts else 0
    return (mirror_penalty, len(path.parts), path.as_posix().lower())


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

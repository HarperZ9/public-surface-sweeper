from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from public_surface_sweeper.workspace import (
    build_delivery_matrix,
    discover_forward_facing_repos,
)


def _write_git_config(repo: Path, remote: str) -> None:
    git_dir = repo / ".git"
    git_dir.mkdir(parents=True)
    (git_dir / "config").write_text(
        "[core]\n"
        "\trepositoryformatversion = 0\n"
        "[remote \"origin\"]\n"
        f"\turl = {remote}\n",
        encoding="utf-8",
    )


def _write_required_files(
    repo: Path, readme: str, include_delivery_contract: bool = True
) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    brand_dir = repo / "docs" / "brand"
    brand_dir.mkdir(parents=True)
    (brand_dir / "demo-hero.png").write_bytes(b"fake image")
    (repo / "README.md").write_text(readme, encoding="utf-8")
    for name in ("LICENSE", "AUTHORS.md", "CONTRIBUTING.md"):
        (repo / name).write_text("ok\n", encoding="utf-8")
    if include_delivery_contract:
        (repo / "AGENTS.md").write_text("# Agent Instructions\n\nRun tests first.\n", encoding="utf-8")
        (repo / "USAGE.md").write_text("# Usage\n\nInstall and run the CLI.\n", encoding="utf-8")
        (repo / "CHANGELOG.md").write_text("# Changelog\n\n## Unreleased\n\n- Current.\n", encoding="utf-8")
        workflow_dir = repo / ".github" / "workflows"
        workflow_dir.mkdir(parents=True)
        (repo / ".github" / "FUNDING.yml").write_text("github: HarperZ9\n", encoding="utf-8")
        (workflow_dir / "ci.yml").write_text(
            "name: CI\n\non: [push, pull_request]\n\njobs:\n"
            "  test:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - uses: actions/checkout@v5\n"
            "      - run: python -m pytest\n",
            encoding="utf-8",
        )


def _complete_readme() -> str:
    return (
        "# Demo\n\n"
        "![Demo hero](docs/brand/demo-hero.png)\n\n"
        "## Why it matters\n\n"
        "This explains the public value.\n\n"
        "## Try it\n\n"
        "```bash\npython -m demo\n```\n\n"
        "## For developers\n\n"
        "```bash\npython -m pytest\n```\n"
    )


def test_discovers_only_github_facing_repositories(tmp_path: Path) -> None:
    public_repo = tmp_path / "public-tool"
    local_repo = tmp_path / "local-tool"
    nested_repo = tmp_path / "node_modules" / "ignored-tool"
    _write_git_config(public_repo, "git@github.com:HarperZ9/public-tool.git")
    _write_git_config(local_repo, "file:///tmp/local-tool")
    _write_git_config(nested_repo, "https://github.com/HarperZ9/ignored-tool.git")

    repos = discover_forward_facing_repos([tmp_path])

    assert [repo.name for repo in repos] == ["public-tool"]


def test_discovery_deduplicates_multiple_clones_of_same_remote(tmp_path: Path) -> None:
    canonical_repo = tmp_path / "ready-tool"
    mirror_repo = tmp_path / "pubscan" / "ready-tool"
    _write_git_config(canonical_repo, "https://github.com/HarperZ9/ready-tool.git")
    _write_git_config(mirror_repo, "https://github.com/HarperZ9/ready-tool.git")

    repos = discover_forward_facing_repos([tmp_path])

    assert repos == [canonical_repo]


def test_discovery_continues_through_local_wrapper_repositories(tmp_path: Path) -> None:
    wrapper = tmp_path / "wrapper"
    nested_repo = wrapper / "nested-tool"
    _write_git_config(wrapper, "file:///tmp/wrapper")
    _write_git_config(nested_repo, "https://github.com/HarperZ9/nested-tool.git")

    repos = discover_forward_facing_repos([wrapper])

    assert repos == [nested_repo]


def test_delivery_matrix_splits_public_and_developer_verdicts(tmp_path: Path) -> None:
    ready_repo = tmp_path / "ready-tool"
    drift_repo = tmp_path / "drift-tool"
    _write_git_config(ready_repo, "https://github.com/HarperZ9/ready-tool.git")
    _write_required_files(ready_repo, _complete_readme())
    _write_git_config(drift_repo, "https://github.com/HarperZ9/drift-tool.git")
    _write_required_files(drift_repo, "# Drift\n\nA useful tool.\n")

    matrix = build_delivery_matrix([tmp_path])

    assert matrix["schema"] == "public-surface-sweeper.delivery-matrix/v1"
    assert matrix["privacy_boundary"]["absolute_paths_included"] is False
    by_name = {repo["name"]: repo for repo in matrix["repositories"]}
    assert by_name["ready-tool"]["public_delivery"] == "MATCH"
    assert by_name["ready-tool"]["developer_delivery"] == "MATCH"
    assert by_name["drift-tool"]["public_delivery"] == "DRIFT"
    assert by_name["drift-tool"]["developer_delivery"] == "DRIFT"
    assert by_name["drift-tool"]["findings"]["warnings"] == 3
    assert not any(str(tmp_path) in json.dumps(repo) for repo in matrix["repositories"])


def test_delivery_matrix_classifies_contract_gaps_by_audience(tmp_path: Path) -> None:
    repo = tmp_path / "contract-gap"
    _write_git_config(repo, "https://github.com/HarperZ9/contract-gap.git")
    _write_required_files(repo, _complete_readme(), include_delivery_contract=False)

    matrix = build_delivery_matrix([tmp_path])

    item = matrix["repositories"][0]
    assert item["status"] == "DRIFT"
    assert item["public_delivery"] == "DRIFT"
    assert item["developer_delivery"] == "DRIFT"
    assert item["boundary"] == "MATCH"
    assert item["findings"]["rules"] == {
        "developer-agent-instructions": 1,
        "developer-ci-workflow": 1,
        "developer-usage-doc": 1,
        "public-changelog": 1,
        "public-funding": 1,
    }


def test_cli_emits_workspace_matrix_json(tmp_path: Path) -> None:
    repo = tmp_path / "ready-tool"
    _write_git_config(repo, "https://github.com/HarperZ9/ready-tool.git")
    _write_required_files(repo, _complete_readme())
    env = os.environ.copy()
    local_src = str(Path(__file__).parents[1] / "src")
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = local_src + os.pathsep + existing if existing else local_src

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "public_surface_sweeper",
            str(tmp_path),
            "--workspace",
            "--json",
        ],
        check=False,
        capture_output=True,
        env=env,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["counts"] == {"MATCH": 1, "DRIFT": 0, "UNVERIFIABLE": 0}
    assert payload["repositories"][0]["remote"] == "HarperZ9/ready-tool"

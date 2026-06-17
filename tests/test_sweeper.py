from __future__ import annotations

from pathlib import Path

from proof_surface.packet import validate_packet
from public_surface_sweeper.sweeper import format_text, scan


def _write_required_files(root: Path) -> None:
    for name in ("README.md", "LICENSE", "AUTHORS.md", "CONTRIBUTING.md"):
        (root / name).write_text("ok\n", encoding="utf-8")


def test_scan_reports_missing_required_files(tmp_path: Path) -> None:
    findings = scan(tmp_path)
    rules = {item.rule for item in findings}
    assert "required-file" in rules
    assert len(findings) == 4


def test_scan_detects_public_surface_findings(tmp_path: Path) -> None:
    _write_required_files(tmp_path)
    token = "ghp_" + "ABCdef1234567890ABCdef1234567890zz"
    em_dash = chr(0x2014)
    (tmp_path / "README.md").write_text(
        f"title\nbad {em_dash} dash\n{token}\n",
        encoding="utf-8",
    )

    findings = scan(tmp_path)

    assert {item.rule for item in findings} == {"em-dash", "github-token"}
    assert "README.md:2" in format_text(findings)


def test_scan_detects_generic_secret_assignments(tmp_path: Path) -> None:
    _write_required_files(tmp_path)
    api_token = "q7R4m9T2" + "v8K1p6S3n5X0"
    client_secret = "s3C9pL2a" + "Q8zM5nR7tY4u"
    (tmp_path / "config.txt").write_text(
        f"api_token = {api_token}\n"
        f"client_secret: {client_secret}\n",
        encoding="utf-8",
    )

    findings = scan(tmp_path)

    assert [item.rule for item in findings] == ["secret-assignment", "secret-assignment"]
    assert "config.txt:1" in format_text(findings)
    assert "config.txt:2" in format_text(findings)


def test_scan_ignores_secret_labels_and_placeholders(tmp_path: Path) -> None:
    _write_required_files(tmp_path)
    (tmp_path / "README.md").write_text(
        "Document SECRET_TOKEN and API_KEY names.\n"
        "api_key: YOUR_" + "API_KEY_HERE\n"
        "token: example-" + "token-placeholder\n"
        "password: <redacted>\n",
        encoding="utf-8",
    )

    assert scan(tmp_path) == []


def test_scan_ignores_binary_files(tmp_path: Path) -> None:
    _write_required_files(tmp_path)
    (tmp_path / "artifact.bin").write_bytes(b"\x00\x01\x02")

    assert scan(tmp_path) == []


def test_scan_ignores_local_tool_state(tmp_path: Path) -> None:
    _write_required_files(tmp_path)
    token = "ghp_" + ("A" * 36)
    for dirname in (".claude", ".Codex", ".warden-safe-cache", "target"):
        local_dir = tmp_path / dirname
        local_dir.mkdir()
        (local_dir / "note.md").write_text(f"ignored - {token}\n", encoding="utf-8")

    assert scan(tmp_path) == []


def test_valid_proof_surface_packet_passes_validation() -> None:
    packet = {
        "proof_surface_version": "0.1",
        "packet_id": "public-surface-sweeper-clean-repo",
        "surface": "clean-repo public release surface",
        "status": "ready",
        "claims": [
            {
                "claim": "Required public release files are visible.",
                "evidence": "required-file findings=0",
            }
        ],
        "checks": [
            {
                "tool": "public-surface-sweeper",
                "status": "pass",
                "summary": "score=100, findings=0",
            }
        ],
        "action_items": [],
    }

    assert validate_packet(packet) == []


def test_cli_emits_proof_packet_for_clean_fixture() -> None:
    import os
    import subprocess
    import sys

    env = os.environ.copy()
    local_src = str(Path(__file__).parents[1] / "src")
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        local_src + os.pathsep + existing if existing else local_src
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "public_surface_sweeper",
            str(Path(__file__).parents[1] / "examples" / "clean-repo"),
            "--proof-packet",
        ],
        check=False,
        capture_output=True,
        env=env,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "proof_surface_version" in result.stdout

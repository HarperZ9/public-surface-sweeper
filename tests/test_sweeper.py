from __future__ import annotations

from pathlib import Path

from proof_surface.packet import validate_packet
from public_surface_sweeper.sweeper import format_text, scan


def _write_required_files(root: Path) -> None:
    brand_dir = root / "docs" / "brand"
    brand_dir.mkdir(parents=True)
    (brand_dir / "demo-hero.png").write_bytes(b"fake image")
    (root / "README.md").write_text(
        "# Demo\n\n"
        "![Demo hero](docs/brand/demo-hero.png)\n\n"
        "> A clear public description for a useful tool.\n\n"
        "## Why it matters\n\n"
        "This explains the public value.\n\n"
        "## Try it\n\n"
        "```bash\npython -m demo\n```\n\n"
        "## For developers\n\n"
        "Run the tests before changing behavior.\n\n"
        "```bash\npython -m pytest\n```\n",
        encoding="utf-8",
    )
    for name in ("LICENSE", "AUTHORS.md", "CONTRIBUTING.md"):
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
    readme = tmp_path / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8") + f"\nbad {em_dash} dash\n{token}\n",
        encoding="utf-8",
    )

    findings = scan(tmp_path)

    assert {item.rule for item in findings} == {"em-dash", "github-token"}
    assert "README.md:2" in format_text(findings)


def test_scan_warns_when_delivery_sections_are_missing(tmp_path: Path) -> None:
    _write_required_files(tmp_path)
    (tmp_path / "README.md").write_text("# Demo\n\nA useful tool.\n", encoding="utf-8")

    findings = scan(tmp_path)

    by_rule = {item.rule: item for item in findings}
    assert by_rule["readme-public-delivery"].severity == "warning"
    assert by_rule["readme-developer-delivery"].severity == "warning"
    assert by_rule["readme-visual-asset"].severity == "warning"


def test_scan_accepts_public_and_developer_delivery(tmp_path: Path) -> None:
    _write_required_files(tmp_path)

    assert scan(tmp_path) == []


def test_scan_accepts_html_readme_image(tmp_path: Path) -> None:
    _write_required_files(tmp_path)
    (tmp_path / "docs" / "brand" / "reconcile-hero.png").write_bytes(b"fake image")
    (tmp_path / "README.md").write_text(
        "# Demo\n\n"
        '<p align="center">\n'
        '  <img src="docs/brand/reconcile-hero.png" alt="Reconcile hero">\n'
        "</p>\n\n"
        "## Why it matters\n\n"
        "This explains the public value.\n\n"
        "## Try it\n\n"
        "```bash\npython -m demo\n```\n\n"
        "## For developers\n\n"
        "```bash\npython -m pytest\n```\n",
        encoding="utf-8",
    )

    assert scan(tmp_path) == []


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
    readme = tmp_path / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8")
        + "\nDocument SECRET_TOKEN and API_KEY names.\n"
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

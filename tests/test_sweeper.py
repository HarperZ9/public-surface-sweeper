from __future__ import annotations

from pathlib import Path

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
    token = "ghp_" + ("A" * 36)
    em_dash = chr(0x2014)
    (tmp_path / "README.md").write_text(
        f"title\nbad {em_dash} dash\n{token}\n",
        encoding="utf-8",
    )

    findings = scan(tmp_path)

    assert {item.rule for item in findings} == {"em-dash", "github-token"}
    assert "README.md:2" in format_text(findings)


def test_scan_ignores_binary_files(tmp_path: Path) -> None:
    _write_required_files(tmp_path)
    (tmp_path / "artifact.bin").write_bytes(b"\x00\x01\x02")

    assert scan(tmp_path) == []

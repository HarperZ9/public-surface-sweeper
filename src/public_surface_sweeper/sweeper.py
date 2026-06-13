from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

REQUIRED_FILES = ("README.md", "LICENSE", "AUTHORS.md", "CONTRIBUTING.md")
SKIP_DIRS = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
}
MAX_SCAN_BYTES = 1_000_000
SEVERITY_ORDER = {"info": 0, "warning": 1, "error": 2}

SECRET_PATTERNS = (
    (
        "private-key",
        re.compile(r"-----BEGIN (?:RSA |DSA |EC |OPENSSH |PGP )?PRIVATE KEY-----"),
        "private key block marker",
    ),
    (
        "github-token",
        re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{20,}\b"),
        "GitHub token shaped value",
    ),
    (
        "openai-key",
        re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
        "OpenAI key shaped value",
    ),
    (
        "aws-access-key",
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        "AWS access key shaped value",
    ),
    (
        "slack-token",
        re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
        "Slack token shaped value",
    ),
)


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    rule: str
    severity: str
    message: str


@dataclass(frozen=True)
class SweepSummary:
    score: int
    status: str
    total_findings: int
    errors: int
    warnings: int
    action_items: list[str]


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _iter_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.is_file():
            yield path


def _read_text(path: Path) -> str | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if len(data) > MAX_SCAN_BYTES or b"\0" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _required_file_findings(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for name in REQUIRED_FILES:
        if not (root / name).is_file():
            findings.append(
                Finding(
                    path=name,
                    line=0,
                    rule="required-file",
                    severity="error",
                    message=f"missing required file: {name}",
                )
            )
    return findings


def _text_findings(root: Path, path: Path, text: str) -> list[Finding]:
    rel_path = _relative(path, root)
    findings: list[Finding] = []

    for match in re.finditer("\u2014", text):
        findings.append(
            Finding(
                path=rel_path,
                line=_line_number(text, match.start()),
                rule="em-dash",
                severity="error",
                message="replace em dash with plain punctuation",
            )
        )

    for rule, pattern, message in SECRET_PATTERNS:
        for match in pattern.finditer(text):
            findings.append(
                Finding(
                    path=rel_path,
                    line=_line_number(text, match.start()),
                    rule=rule,
                    severity="error",
                    message=message,
                )
            )
    return findings


def scan(root: Path) -> list[Finding]:
    root = root.resolve()
    findings = _required_file_findings(root)
    for path in _iter_files(root):
        text = _read_text(path)
        if text is not None:
            findings.extend(_text_findings(root, path, text))
    return sorted(findings, key=lambda item: (item.severity, item.path, item.line, item.rule))


def format_text(findings: list[Finding]) -> str:
    if not findings:
        return "No findings."
    lines = []
    for item in findings:
        location = item.path if item.line == 0 else f"{item.path}:{item.line}"
        lines.append(f"{item.severity.upper()} {location} {item.rule}: {item.message}")
    return "\n".join(lines)


def summarize_findings(findings: list[Finding], action_limit: int = 8) -> SweepSummary:
    errors = sum(1 for item in findings if item.severity == "error")
    warnings = sum(1 for item in findings if item.severity == "warning")
    score = max(0, 100 - (errors * 25) - (warnings * 10))
    if errors:
        status = "blocked"
    elif warnings:
        status = "needs-polish"
    else:
        status = "ready"
    return SweepSummary(
        score=score,
        status=status,
        total_findings=len(findings),
        errors=errors,
        warnings=warnings,
        action_items=[_action_text(item) for item in findings[:action_limit]],
    )


def _action_text(item: Finding) -> str:
    location = item.path if item.line == 0 else f"{item.path}:{item.line}"
    return f"{location}: {item.message}"


def format_summary(summary: SweepSummary) -> str:
    lines = [
        f"score: {summary.score}",
        f"status: {summary.status}",
        f"total_findings: {summary.total_findings}",
        f"errors: {summary.errors}",
        f"warnings: {summary.warnings}",
        "action_items:",
    ]
    if summary.action_items:
        lines.extend(f"- {item}" for item in summary.action_items)
    else:
        lines.append("- none")
    return "\n".join(lines)


def proof_surface_packet(root: Path, findings: list[Finding]) -> dict[str, Any]:
    summary = summarize_findings(findings)
    required_gaps = sum(1 for item in findings if item.rule == "required-file")
    secret_hits = sum(1 for item in findings if item.rule in _secret_rules())
    punctuation_hits = sum(1 for item in findings if item.rule == "em-dash")
    return {
        "proof_surface_version": "0.1",
        "packet_id": f"public-surface-sweeper-{root.resolve().name}",
        "surface": f"{root.resolve().name} public release surface",
        "status": summary.status,
        "claims": [
            {
                "claim": "Required public release files are visible.",
                "evidence": f"required-file findings={required_gaps}",
            },
            {
                "claim": "Secret-shaped values are surfaced before publication.",
                "evidence": f"secret-shaped findings={secret_hits}",
            },
            {
                "claim": "Public text hygiene is checkable.",
                "evidence": f"em-dash findings={punctuation_hits}",
            },
        ],
        "checks": [
            {
                "tool": "public-surface-sweeper",
                "status": _packet_check_status(summary.status),
                "summary": f"score={summary.score}, findings={summary.total_findings}",
            }
        ],
        "action_items": summary.action_items,
    }


def _secret_rules() -> set[str]:
    return {rule for rule, _, _ in SECRET_PATTERNS}


def _packet_check_status(status: str) -> str:
    if status == "ready":
        return "pass"
    if status == "needs-polish":
        return "warn"
    if status == "blocked":
        return "fail"
    return "unknown"

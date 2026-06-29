from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

REQUIRED_FILES = ("README.md", "LICENSE", "AUTHORS.md", "CONTRIBUTING.md")
SKIP_DIRS = {
    ".git",
    ".Codex",
    ".claude",
    ".codex",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    ".vscode",
    ".warden-safe-cache",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "target",
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
SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"""
    (?<![A-Za-z0-9_])
    ["']?
    (?P<name>
        api[_-]?key|
        api[_-]?token|
        access[_-]?token|
        auth[_-]?token|
        client[_-]?secret|
        password|
        passwd|
        secret|
        token
    )
    ["']?
    \s*(?:=|:)\s*
    ["']?
    (?P<value>[A-Za-z0-9][A-Za-z0-9._~+/=-]{15,})
    ["']?
    """,
    re.IGNORECASE | re.VERBOSE,
)
PLACEHOLDER_MARKERS = (
    "changeme",
    "dummy",
    "example",
    "placeholder",
    "redacted",
    "sample",
    "test",
    "your",
)
PUBLIC_DELIVERY_HEADINGS = (
    "why it matters",
    "what it does",
    "overview",
    "use cases",
    "current status",
    "who it is for",
    "who it's for",
)
DEVELOPER_ENTRY_HEADINGS = (
    "install",
    "installation",
    "quickstart",
    "try it",
    "usage",
)
DEVELOPER_WORK_HEADINGS = (
    "api",
    "contributing",
    "development",
    "for developers",
    "testing",
)
SUBSTANTIVE_IMAGE_EXTENSIONS = (".gif", ".jpg", ".jpeg", ".png", ".svg", ".webp")
BADGE_IMAGE_MARKERS = (
    "badge",
    "badgen.net",
    "ci",
    "license",
    "shield",
    "shields.io",
    "version",
)
MARKDOWN_IMAGE_PATTERN = re.compile(
    r"!\[(?P<alt>[^\]]*)\]\((?P<target>[^)\s]+)(?:\s+\"[^\"]*\")?\)"
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


def _readme_delivery_findings(root: Path) -> list[Finding]:
    path = root / "README.md"
    text = _read_text(path)
    if text is None:
        return []

    findings: list[Finding] = []
    if not _has_any_heading(text, PUBLIC_DELIVERY_HEADINGS):
        findings.append(
            Finding(
                path="README.md",
                line=0,
                rule="readme-public-delivery",
                severity="warning",
                message="README should explain the public value, status, or use case",
            )
        )

    has_entry = _has_any_heading(text, DEVELOPER_ENTRY_HEADINGS)
    has_workflow = _has_any_heading(text, DEVELOPER_WORK_HEADINGS)
    has_command = "```" in text and _looks_like_command_block(text)
    if not (has_entry and has_workflow and has_command):
        findings.append(
            Finding(
                path="README.md",
                line=0,
                rule="readme-developer-delivery",
                severity="warning",
                message="README should include developer entry points, workflow notes, and runnable commands",
            )
        )

    if not _has_substantive_readme_image(root, text):
        findings.append(
            Finding(
                path="README.md",
                line=0,
                rule="readme-visual-asset",
                severity="warning",
                message="README should include a substantive non-badge visual asset",
            )
        )
    return findings


def _has_any_heading(text: str, terms: tuple[str, ...]) -> bool:
    headings = [
        match.group("heading").strip().lower()
        for match in re.finditer(r"^#{1,4}\s+(?P<heading>.+?)\s*$", text, re.MULTILINE)
    ]
    return any(any(term in heading for term in terms) for heading in headings)


def _looks_like_command_block(text: str) -> bool:
    command_block_pattern = (
        r"```(?:bash|console|powershell|ps1|shell|sh|text)?\s*\n(.*?)```"
    )
    command_word_pattern = (
        r"\b(python|pip|pytest|npm|pnpm|node|cargo|cmake|make|git|"
        r"public-surface-sweeper)\b"
    )
    for block in re.findall(command_block_pattern, text, re.DOTALL | re.IGNORECASE):
        if re.search(command_word_pattern, block):
            return True
    return False


def _has_substantive_readme_image(root: Path, text: str) -> bool:
    for match in MARKDOWN_IMAGE_PATTERN.finditer(text):
        alt = match.group("alt").lower()
        target = match.group("target").strip("<>").split("#", 1)[0].split("?", 1)[0]
        lowered_target = target.lower()
        if any(marker in alt or marker in lowered_target for marker in BADGE_IMAGE_MARKERS):
            continue
        if lowered_target.startswith(("http://", "https://")):
            if lowered_target.endswith(SUBSTANTIVE_IMAGE_EXTENSIONS):
                return True
            continue
        if not lowered_target.endswith(SUBSTANTIVE_IMAGE_EXTENSIONS):
            continue
        if (root / target).is_file():
            return True
    return False


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

    provider_spans: list[tuple[int, int]] = []
    for rule, pattern, message in SECRET_PATTERNS:
        for match in pattern.finditer(text):
            provider_spans.append(match.span())
            findings.append(
                Finding(
                    path=rel_path,
                    line=_line_number(text, match.start()),
                    rule=rule,
                    severity="error",
                    message=message,
                )
            )
    for match in SECRET_ASSIGNMENT_PATTERN.finditer(text):
        if _overlaps_any(match.span("value"), provider_spans):
            continue
        if _is_placeholder_value(match.group("value")):
            continue
        findings.append(
            Finding(
                path=rel_path,
                line=_line_number(text, match.start("value")),
                rule="secret-assignment",
                severity="error",
                message=f"{match.group('name')} appears to contain a credential-shaped value",
            )
        )
    return findings


def _overlaps_any(span: tuple[int, int], spans: list[tuple[int, int]]) -> bool:
    start, end = span
    return any(start < other_end and other_start < end for other_start, other_end in spans)


def _is_placeholder_value(value: str) -> bool:
    normalized = value.strip("\"'<>[](){}").strip()
    if len(normalized) < 16:
        return True
    lowered = normalized.lower()
    if any(marker in lowered for marker in PLACEHOLDER_MARKERS):
        return True
    variable_part = re.sub(r"[^A-Za-z0-9]", "", normalized)
    return len(set(variable_part)) <= 3


def scan(root: Path) -> list[Finding]:
    root = root.resolve()
    findings = _required_file_findings(root)
    findings.extend(_readme_delivery_findings(root))
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
    delivery_hits = sum(1 for item in findings if item.rule.startswith("readme-"))
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
            {
                "claim": "Public and developer delivery are inspectable.",
                "evidence": f"readme delivery findings={delivery_hits}",
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
    return {rule for rule, _, _ in SECRET_PATTERNS} | {"secret-assignment"}


def _packet_check_status(status: str) -> str:
    if status == "ready":
        return "pass"
    if status == "needs-polish":
        return "warn"
    if status == "blocked":
        return "fail"
    return "unknown"

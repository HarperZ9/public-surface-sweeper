from __future__ import annotations

from typing import Any

PACKET_STATUSES = {"ready", "needs-polish", "blocked", "unknown"}
CHECK_STATUSES = {"pass", "warn", "fail", "unknown"}
PACKET_FIELDS = {
    "proof_surface_version",
    "packet_id",
    "surface",
    "status",
    "claims",
    "checks",
    "action_items",
}
CLAIM_FIELDS = {"claim", "evidence"}
CHECK_FIELDS = {"tool", "status", "summary"}


def validate_proof_surface_packet(packet: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    _reject_unknown(packet, "$", PACKET_FIELDS, issues)
    _require_value(packet, "proof_surface_version", "0.1", issues)
    _require_text(packet, "packet_id", issues)
    _require_text(packet, "surface", issues)
    _require_enum(packet, "status", PACKET_STATUSES, issues)
    _validate_claims(packet.get("claims"), issues)
    _validate_checks(packet.get("checks"), issues)
    _validate_actions(packet.get("action_items"), issues)
    return issues


def _reject_unknown(
    data: dict[str, Any],
    path: str,
    allowed: set[str],
    issues: list[str],
) -> None:
    for field in sorted(set(data) - allowed):
        issues.append(f"{path}.{field}: unexpected field")


def _require_value(
    data: dict[str, Any],
    field: str,
    expected: str,
    issues: list[str],
) -> None:
    if data.get(field) != expected:
        issues.append(f"$.{field}: expected {expected!r}")


def _require_text(data: dict[str, Any], field: str, issues: list[str]) -> None:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        issues.append(f"$.{field}: expected non-empty string")


def _require_enum(
    data: dict[str, Any],
    field: str,
    allowed: set[str],
    issues: list[str],
) -> None:
    if data.get(field) not in allowed:
        issues.append(f"$.{field}: expected one of: {', '.join(sorted(allowed))}")


def _validate_claims(value: Any, issues: list[str]) -> None:
    if not isinstance(value, list):
        issues.append("$.claims: expected array")
        return
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            issues.append(f"$.claims[{index}]: expected object")
            continue
        _reject_unknown(item, f"$.claims[{index}]", CLAIM_FIELDS, issues)
        _require_text(item, f"claims[{index}].claim", issues)
        _require_text(item, f"claims[{index}].evidence", issues)


def _validate_checks(value: Any, issues: list[str]) -> None:
    if not isinstance(value, list):
        issues.append("$.checks: expected array")
        return
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            issues.append(f"$.checks[{index}]: expected object")
            continue
        _reject_unknown(item, f"$.checks[{index}]", CHECK_FIELDS, issues)
        _require_text(item, f"checks[{index}].tool", issues)
        _require_enum(item, f"checks[{index}].status", CHECK_STATUSES, issues)
        _require_text(item, f"checks[{index}].summary", issues)


def _validate_actions(value: Any, issues: list[str]) -> None:
    if not isinstance(value, list):
        issues.append("$.action_items: expected array")
        return
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            issues.append(f"$.action_items[{index}]: expected non-empty string")

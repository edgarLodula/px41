import logging
import re
import threading
from dataclasses import dataclass
from pathlib import Path

import yaml

from src.content_generation.schemas import Evaluation, Issue

logger = logging.getLogger(__name__)

_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2}
_SEVERITY_EMOJI = {"critical": "\U0001f534", "high": "⚠️", "medium": "ℹ️"}
_MAX_DIAGNOSIS_ISSUES = 20
_REGEX_TIMEOUT = 0.1  # segundos por regra/texto — proteção genérica contra backtracking


@dataclass
class CompiledRule:
    id: str
    pattern: str
    severity: str
    weight: int
    message: str
    fix: str | None
    context_window: int
    compiled: re.Pattern


def _compile_rules(rules_path: str) -> list[CompiledRule]:
    path = Path(rules_path)
    if not path.exists():
        logger.warning("rules_path nao encontrado: %s", rules_path)
        return []

    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not data or "rules" not in data or not data["rules"]:
        return []

    compiled: list[CompiledRule] = []
    for raw in data["rules"]:
        pattern_str = raw.get("pattern", "")
        try:
            compiled_re = re.compile(pattern_str, re.IGNORECASE | re.MULTILINE)
        except re.error as exc:
            logger.warning(
                "Regra '%s' ignorada — pattern invalido: %s", raw.get("id", "?"), exc
            )
            continue

        compiled.append(
            CompiledRule(
                id=raw["id"],
                pattern=pattern_str,
                severity=raw.get("severity", "medium"),
                weight=raw.get("weight", 3),
                message=raw.get("message", ""),
                fix=raw.get("fix"),
                context_window=raw.get("context_window", 80),
                compiled=compiled_re,
            )
        )
    return compiled


def _safe_finditer(
    compiled: re.Pattern, text: str, rule_id: str, timeout: float = _REGEX_TIMEOUT
) -> list[re.Match] | None:
    """Executa finditer em thread com daemon=True. Retorna None se exceder timeout."""
    results: list[re.Match] = []
    done = threading.Event()

    def _run() -> None:
        try:
            for m in compiled.finditer(text):
                results.append(m)
        finally:
            done.set()

    t = threading.Thread(target=_run, daemon=True)
    t.start()

    if not done.wait(timeout):
        logger.warning(
            "Regra '%s' excedeu timeout de %.1fs — ignorada para este texto",
            rule_id,
            timeout,
        )
        return None

    return results


def _extract_context(texto: str, start: int, end: int, window: int = 80) -> str:
    half = window // 2
    ctx_start = max(0, start - half)
    ctx_end = min(len(texto), end + half)

    snippet = texto[ctx_start:ctx_end]

    # Matches muito grandes ficam truncados ao dobro do window
    max_len = window * 2
    truncated = len(snippet) > max_len
    if truncated:
        snippet = snippet[:max_len]

    snippet = re.sub(r"\s*\n+\s*", " ", snippet).strip()

    prefix = "..." if ctx_start > 0 else ""
    suffix = "..." if (truncated or ctx_end < len(texto)) else ""
    return f'"{prefix}{snippet}{suffix}"'


def _calculate_score(issues: list[Issue]) -> int:
    score = 100
    for issue in issues:
        score -= issue.weight
    return max(0, score)


def _build_diagnosis(evaluation: Evaluation) -> str:
    status = "PASSOU" if evaluation.passed else "REPROVOU"

    if not evaluation.issues:
        return f"PASSOU (score: {evaluation.score}, 0 issues) — Nenhum problema encontrado."

    header = (
        f"{status} (score: {evaluation.score}, "
        f"critical: {evaluation.critical_count}, "
        f"high: {evaluation.high_count}, "
        f"medium: {evaluation.medium_count})"
    )

    sorted_issues = sorted(
        evaluation.issues,
        key=lambda i: (_SEVERITY_ORDER.get(i.severity, 99), i.line),
    )

    lines = [header]
    displayed = sorted_issues[:_MAX_DIAGNOSIS_ISSUES]
    for issue in displayed:
        emoji = _SEVERITY_EMOJI.get(issue.severity, "  ")
        sev_label = issue.severity.upper()
        lines.append(f"{emoji} {sev_label} (linha {issue.line}): {issue.message}")
        lines.append(f"   Contexto: {issue.context}")

    remainder = len(sorted_issues) - len(displayed)
    if remainder > 0:
        lines.append(f"... e mais {remainder} issues")

    return "\n".join(lines)


def avaliar(texto_md: str, rules_path: str) -> Evaluation:
    if not texto_md:
        return Evaluation(
            score=100,
            passed=True,
            total_issues=0,
            critical_count=0,
            high_count=0,
            medium_count=0,
            issues=[],
            diagnosis="PASSOU (score: 100, 0 issues) — Nenhum problema encontrado.",
        )

    rules = _compile_rules(rules_path)

    issues: list[Issue] = []
    for rule in rules:
        matches = _safe_finditer(rule.compiled, texto_md, rule.id)
        if matches is None:
            continue
        for match in matches:
            line = texto_md.count("\n", 0, match.start()) + 1
            context = _extract_context(
                texto_md, match.start(), match.end(), rule.context_window
            )
            issues.append(
                Issue(
                    rule_id=rule.id,
                    severity=rule.severity,
                    weight=rule.weight,
                    line=line,
                    context=context,
                    message=rule.message,
                    fix=rule.fix,
                    start=match.start(),
                    end=match.end(),
                )
            )

    score = _calculate_score(issues)
    critical_count = sum(1 for i in issues if i.severity == "critical")
    high_count = sum(1 for i in issues if i.severity == "high")
    medium_count = sum(1 for i in issues if i.severity == "medium")
    passed = (score >= 85) and (critical_count <= 1)

    evaluation = Evaluation(
        score=score,
        passed=passed,
        total_issues=len(issues),
        critical_count=critical_count,
        high_count=high_count,
        medium_count=medium_count,
        issues=issues,
        diagnosis="",
    )
    evaluation.diagnosis = _build_diagnosis(evaluation)
    return evaluation

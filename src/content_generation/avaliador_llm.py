import json
import logging
import os
import time

from openai import OpenAI

from src.content_generation.schemas import Evaluation, Issue

logger = logging.getLogger(__name__)

_OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
_WEIGHT_MAP = {"critical": 25, "high": 10, "medium": 3}
_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2}
_SEVERITY_EMOJI = {"critical": "\U0001f534", "high": "⚠️", "medium": "ℹ️"}
_MAX_DIAGNOSIS_ISSUES = 20
_MAX_RETRIES = 4
_TEXT_LIMIT = 12_000  # caracteres enviados ao LLM — equilibra cobertura e custo


def _bloco_contexto(profile: dict | None) -> str:
    if not profile:
        return ""
    partes = []
    area = profile.get("area", "")
    if area:
        partes.append(f"Área: {area}")
    normas = profile.get("normas_relevantes") or profile.get("normas") or []
    if normas:
        partes.append(f"Normas de referência: {', '.join(normas)}")
    return ("\n" + "\n".join(partes)) if partes else ""


def _build_prompt(texto_md: str, profile: dict | None) -> str:
    ctx = _bloco_contexto(profile)
    trecho = texto_md[:_TEXT_LIMIT]
    aviso_corte = (
        f"\n(Texto truncado em {_TEXT_LIMIT} caracteres para análise)"
        if len(texto_md) > _TEXT_LIMIT
        else ""
    )
    return f"""Você é especialista em Segurança e Saúde no Trabalho (SST) e avaliador crítico de material educacional.{ctx}

Analise o conteúdo abaixo e identifique APENAS problemas concretos, como:
- Terminologia obsoleta (PPRA→PGR, FISPQ→FDS, CIPA sem "e de Assédio", "ato inseguro")
- Referências normativas incorretas ou desatualizadas (NR com escopo errado, leis revogadas como Lei 8.666/1993)
- Conceitos técnicos errados (ex: IBUTG associado a agentes químicos/biológicos, NR-9 com riscos ergonômicos)
- CAT mencionada sem referência ao eSocial/S-2210
- Citações normativas sem número ou ano

Retorne SOMENTE um JSON válido nesta estrutura:
{{
  "issues": [
    {{
      "severity": "critical|high|medium",
      "message": "Descrição objetiva do problema",
      "excerpt": "Trecho literal do texto com o problema (até 150 caracteres)",
      "fix": "Como corrigir (ou null)"
    }}
  ]
}}

Critérios de severidade:
- critical (peso 25): terminologia abolida por lei, norma com escopo completamente errado
- high (peso 10): referência desatualizada relevante, ausência de informação obrigatória
- medium (peso 3): imprecisão menor, citação incompleta, lacuna recomendada

Se não houver problemas, retorne {{"issues": []}}.
Não repita o mesmo problema. Seja específico: use o trecho exato no campo "excerpt".{aviso_corte}

CONTEÚDO:
---
{trecho}
---"""


def _chamar_api(client: OpenAI, prompt: str) -> str:
    """Retry com backoff exponencial, igual ao padrão de generator.py."""
    ultimo_erro: Exception | None = None
    for tentativa in range(_MAX_RETRIES):
        try:
            resp = client.chat.completions.create(
                model=_OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0,
            )
            return resp.choices[0].message.content or "{}"
        except Exception as exc:
            ultimo_erro = exc
            if tentativa < _MAX_RETRIES - 1:
                espera = 2**tentativa
                logger.warning(
                    "avaliador_llm tentativa %d falhou: %s — aguardando %ds",
                    tentativa + 1,
                    exc,
                    espera,
                )
                time.sleep(espera)
    raise ultimo_erro  # type: ignore[misc]


def _find_line(texto: str, excerpt: str) -> int:
    if not excerpt:
        return 0
    pos = texto.lower().find(excerpt.strip().lower()[:80])
    if pos == -1:
        return 0
    return texto.count("\n", 0, pos) + 1


def _parse_issues(response_text: str, texto_md: str) -> list[Issue]:
    try:
        data = json.loads(response_text)
    except json.JSONDecodeError as exc:
        logger.warning("avaliador_llm: resposta não é JSON válido — %s", exc)
        return []

    raw_list = data.get("issues")
    if not isinstance(raw_list, list):
        return []

    issues: list[Issue] = []
    for i, raw in enumerate(raw_list):
        if not isinstance(raw, dict):
            continue
        severity = raw.get("severity", "medium")
        if severity not in _WEIGHT_MAP:
            severity = "medium"
        excerpt = (raw.get("excerpt") or "").strip()
        context = f'"{excerpt[:200]}"' if excerpt else ""
        issues.append(
            Issue(
                rule_id=f"llm_{severity}_{i+1:03d}",
                severity=severity,
                weight=_WEIGHT_MAP[severity],
                line=_find_line(texto_md, excerpt),
                context=context,
                message=(raw.get("message") or "").strip(),
                fix=raw.get("fix") or None,
                start=None,
                end=None,
            )
        )
    return issues


def _calculate_score(issues: list[Issue]) -> int:
    return max(0, 100 - sum(i.weight for i in issues))


def _build_diagnosis(issues: list[Issue], score: int, passed: bool) -> str:
    if not issues:
        return f"PASSOU (score: {score}, 0 issues) — Nenhum problema encontrado."

    critical = sum(1 for i in issues if i.severity == "critical")
    high = sum(1 for i in issues if i.severity == "high")
    medium = sum(1 for i in issues if i.severity == "medium")
    status = "PASSOU" if passed else "REPROVOU"
    header = f"{status} (score: {score}, critical: {critical}, high: {high}, medium: {medium})"

    sorted_issues = sorted(issues, key=lambda i: (_SEVERITY_ORDER.get(i.severity, 99), i.line))
    lines = [header]
    displayed = sorted_issues[:_MAX_DIAGNOSIS_ISSUES]
    for issue in displayed:
        emoji = _SEVERITY_EMOJI.get(issue.severity, "  ")
        lines.append(f"{emoji} {issue.severity.upper()} (linha {issue.line}): {issue.message}")
        if issue.context:
            lines.append(f"   Contexto: {issue.context}")

    remainder = len(sorted_issues) - len(displayed)
    if remainder > 0:
        lines.append(f"... e mais {remainder} issues")

    return "\n".join(lines)


def avaliar_llm(
    texto_md: str,
    client: OpenAI,
    profile: dict | None = None,
) -> Evaluation:
    """
    Avalia conteúdo markdown via LLM, detectando problemas contextuais
    (terminologia obsoleta, normas incorretas, erros técnicos) que o
    avaliador regex não consegue capturar.

    Retorna Evaluation no mesmo formato de avaliador.avaliar(), compatível
    com schemas.py — pode ser usado standalone ou em avaliar_combinado().
    """
    if not texto_md or not texto_md.strip():
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

    try:
        prompt = _build_prompt(texto_md, profile)
        raw = _chamar_api(client, prompt)
        issues = _parse_issues(raw, texto_md)
    except Exception as exc:
        logger.error("avaliador_llm: falha na chamada à API — %s", exc)
        return Evaluation(
            score=0,
            passed=False,
            total_issues=0,
            critical_count=0,
            high_count=0,
            medium_count=0,
            issues=[],
            diagnosis=f"ERRO na avaliação LLM: {exc}",
        )

    score = _calculate_score(issues)
    critical_count = sum(1 for i in issues if i.severity == "critical")
    high_count = sum(1 for i in issues if i.severity == "high")
    medium_count = sum(1 for i in issues if i.severity == "medium")
    passed = (score >= 85) and (critical_count == 0)

    return Evaluation(
        score=score,
        passed=passed,
        total_issues=len(issues),
        critical_count=critical_count,
        high_count=high_count,
        medium_count=medium_count,
        issues=issues,
        diagnosis=_build_diagnosis(issues, score, passed),
    )


def avaliar_combinado(
    texto_md: str,
    client: OpenAI,
    avaliacao_regex: Evaluation,
    profile: dict | None = None,
) -> Evaluation:
    """
    Mescla a avaliação regex (já executada externamente via avaliador.avaliar())
    com a avaliação LLM, recalculando score e diagnosis sobre o conjunto unificado.

    Uso típico:
        from src.content_generation.avaliador import avaliar
        from src.content_generation.avaliador_llm import avaliar_combinado

        ev_regex = avaliar(texto, rules_path)
        ev_final = avaliar_combinado(texto, client, ev_regex, profile)
    """
    ev_llm = avaliar_llm(texto_md, client, profile)

    issues = avaliacao_regex.issues + ev_llm.issues
    score = _calculate_score(issues)
    critical_count = sum(1 for i in issues if i.severity == "critical")
    high_count = sum(1 for i in issues if i.severity == "high")
    medium_count = sum(1 for i in issues if i.severity == "medium")
    passed = (score >= 85) and (critical_count == 0)

    return Evaluation(
        score=score,
        passed=passed,
        total_issues=len(issues),
        critical_count=critical_count,
        high_count=high_count,
        medium_count=medium_count,
        issues=issues,
        diagnosis=_build_diagnosis(issues, score, passed),
    )

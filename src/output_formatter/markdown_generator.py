"""
Gerador de arquivos Markdown de aluno e professor por disciplina.

Resolve o profile da área a partir dos registros agrupados.
Passa o profile explicitamente para todas as funções de geração.
Nunca consulta variáveis de ambiente para definir a área.
"""
import os
import re
import time
import logging
import traceback
import tempfile
import shutil
from dataclasses import dataclass, field

from src.content_generation.generator import gerar_topico, gerar_questoes_topico
from src.content_generation.area_profiles import get_profile

logger = logging.getLogger(__name__)

_DELAY_ENTRE_TOPICOS: float = float(os.getenv("DELAY_ENTRE_TOPICOS", "10"))
_DELAY_ENTRE_SECOES: float = float(os.getenv("DELAY_ENTRE_SECOES", "10"))
_DELAY_ENTRE_DISC: float = float(os.getenv("DELAY_ENTRE_DISCIPLINAS", "35"))


# ---------------------------------------------------------------------------
# ESTRUTURAS DE RESULTADO
# ---------------------------------------------------------------------------

@dataclass
class ResultadoDisciplina:
    disciplina: str
    area_key: str
    caminho_aluno: str = ""
    caminho_professor: str = ""
    pulada: bool = False
    erro: str = ""
    violacoes_vocab: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# VALIDAÇÃO DE VOCABULÁRIO PROIBIDO (Fase 6)
# ---------------------------------------------------------------------------

def _validar_vocabulario(texto: str, profile: dict) -> list[str]:
    """
    Verifica se o texto contém termos proibidos do profile.
    Retorna lista de strings descrevendo cada violação encontrada.
    """
    proibido = profile.get("vocabulario_proibido", [])
    if not proibido:
        return []

    violacoes: list[str] = []
    texto_low = texto.lower()

    for termo in proibido:
        termo_low = termo.lower()
        # Busca o termo como substring (não exige word boundary para suportar acentuação)
        pos = texto_low.find(termo_low)
        if pos >= 0:
            trecho = texto[max(0, pos - 30): pos + len(termo) + 30].replace("\n", " ")
            violacoes.append(
                f"Termo proibido '{termo}' encontrado em: '...{trecho}...'"
            )

    return violacoes


_POLITICA_VOCABULARIO: str = os.getenv("POLITICA_VOCABULARIO", "warn")


def _aplicar_politica_vocabulario(
    violacoes: list[str],
    disciplina: str,
    secao: str,
) -> None:
    """
    warn  — loga e continua
    fail  — lança ValueError
    retry — tratado no chamador; aqui apenas loga
    """
    if not violacoes:
        return
    for v in violacoes:
        logger.warning("[VOCAB] %s / %s: %s", disciplina, secao, v)

    if _POLITICA_VOCABULARIO == "fail":
        raise ValueError(
            f"Vocabulário proibido encontrado em '{disciplina}/{secao}': {violacoes}"
        )


# ---------------------------------------------------------------------------
# FORMATAÇÃO MARKDOWN
# ---------------------------------------------------------------------------

def texto_para_markdown(disciplina: str, texto_bruto: str) -> str:
    secoes = {
        "INTRODUCAO": "## Introdução",
        "OBJETIVOS": "## Objetivos de Aprendizagem",
        "TOPICOS": "## Explicação dos Tópicos",
        "EXEMPLOS": "## Exemplos Práticos",
        "RESUMO": "## Resumo",
        "QUESTOES": "## Questões",
    }
    md = f"# {disciplina}\n\n"
    for rotulo, titulo_md in secoes.items():
        chaves_str = "|".join(secoes.keys())
        padrao = rf"{rotulo}:(.*?)(?={chaves_str}:|$)"
        match = re.search(padrao, texto_bruto, re.DOTALL)
        conteudo = match.group(1).strip() if match else ""
        md += f"{titulo_md}\n\n{conteudo}\n\n"
    return md


def limpar_texto(texto: str) -> str:
    return "\n".join(ln.strip() for ln in texto.strip().splitlines() if ln.strip())


def _sanitizar_nome_arquivo(nome: str) -> str:
    nome = " ".join(nome.split())
    nome = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", nome)
    nome = re.sub(r"[^\w\s-]", "", nome)
    return nome.strip().replace(" ", "_")


def _controle_editorial_topico(i: int, nome: str) -> str:
    return (
        f"\n\n---\n\n"
        f"**Controle Editorial — Tópico {i}: {nome}**\n\n"
        "| Item | Status |\n"
        "|------|--------|\n"
        "| Fundamentação teórica | Sim |\n"
        "| Aplicação prática | Sim |\n"
        "| Casos práticos | Sim |\n"
        "| Erros comuns | Sim |\n"
        "| Glossário | Sim |\n"
        "| Página de perguntas | Sim |\n\n"
        "---\n"
    )


def juntar_topicos_formatado(
    introducao: str,
    objetivos: str,
    topicos_dict: dict,
    exemplos: str,
    resumo: str,
    questoes_aluno: str,
    questoes_professor: str,
) -> tuple[str, str]:
    """Retorna (doc_aluno, doc_professor)."""

    def _build(questoes_geral: str, chave_questoes_topico: str, titulo_questoes: str) -> str:
        partes: list[str] = []
        partes.append("INTRODUCAO:\n" + limpar_texto(introducao))
        partes.append("OBJETIVOS:\n" + limpar_texto(objetivos))

        topicos_texto = ["TOPICOS:"]
        for i, (nome, dados) in enumerate(topicos_dict.items(), 1):
            conteudo = dados["conteudo"] if isinstance(dados, dict) else dados
            questoes_topico = (
                dados.get(chave_questoes_topico, "") if isinstance(dados, dict) else ""
            )
            topicos_texto.append(f"\n### Tópico {i}: {nome}")
            topicos_texto.append(limpar_texto(conteudo))
            if questoes_topico:
                topicos_texto.append(
                    f"\n#### {titulo_questoes} — Tópico {i}: {nome}"
                )
                topicos_texto.append(limpar_texto(questoes_topico))
            topicos_texto.append(_controle_editorial_topico(i, nome))
        partes.append("\n\n".join(topicos_texto))

        partes.append("EXEMPLOS:\n" + limpar_texto(exemplos))
        partes.append("RESUMO:\n" + limpar_texto(resumo))
        partes.append("QUESTOES:\n" + limpar_texto(questoes_geral))
        return "\n\n".join(partes)

    doc_aluno = _build(questoes_aluno, "questoes_aluno", "Perguntas e Exercícios")
    doc_professor = _build(
        questoes_professor, "questoes_professor", "Perguntas, Exercícios e Gabarito"
    )
    return doc_aluno, doc_professor


# ---------------------------------------------------------------------------
# ESCRITA ATÔMICA
# ---------------------------------------------------------------------------

def _escrever_atomico(caminho: str, conteudo: str) -> None:
    """Escreve em arquivo temporário e só substitui o destino ao concluir."""
    dir_destino = os.path.dirname(caminho) or "."
    os.makedirs(dir_destino, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(dir=dir_destino, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(conteudo)
            f.flush()
            os.fsync(f.fileno())
        shutil.move(tmp_path, caminho)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# VERIFICAÇÃO DE PAR COMPLETO (retomada)
# ---------------------------------------------------------------------------

def _par_completo(caminho_aluno: str, caminho_professor: str) -> bool:
    for caminho in (caminho_aluno, caminho_professor):
        if not os.path.isfile(caminho):
            return False
        if os.path.getsize(caminho) < 100:  # arquivo claramente truncado
            return False
    return True


# ---------------------------------------------------------------------------
# GERAÇÃO PRINCIPAL
# ---------------------------------------------------------------------------

def gerar_markdowns(
    base_geral: list[dict],
    buscar_chunks,
    gerar_documento,
    model,
    index,
    gemini,
    pasta_saida: str = "data/output/markdown",
    force: bool = False,
    sleep_fn=None,
    instructions: str = "",
) -> list[ResultadoDisciplina]:
    """
    Gera arquivos Markdown de aluno e professor para cada disciplina.

    Retorna lista de ResultadoDisciplina com status de cada item.

    `sleep_fn` é injetável para testes (use `lambda s: None` para desativar espera).
    """
    if sleep_fn is None:
        sleep_fn = time.sleep

    os.makedirs(pasta_saida, exist_ok=True)

    # ---- Agrupa: arquivo (PDF) → disciplina → lista de aulas ----
    cursos: dict[str, dict[str, list[dict]]] = {}
    titulos_curso: dict[str, str] = {}

    for item in base_geral:
        arquivo = item.get("arquivo", "").strip() or "curso_desconhecido"
        disciplina = " ".join(item.get("disciplina", "").split()).strip()
        if not disciplina:
            continue
        cursos.setdefault(arquivo, {}).setdefault(disciplina, []).append(item)
        if arquivo not in titulos_curso:
            titulos_curso[arquivo] = item.get("curso", "") or arquivo

    total_disciplinas = sum(len(d) for d in cursos.values())
    logger.info("%d disciplinas únicas encontradas", total_disciplinas)
    print(f"\n📚 {total_disciplinas} disciplinas únicas encontradas\n")

    resultados: list[ResultadoDisciplina] = []
    contador = 0

    for arquivo_pdf, disciplinas in cursos.items():
        curso_slug = (
            re.sub(r"[^\w\s-]", "", arquivo_pdf)
            .replace(".pdf", "")
            .replace(".csv", "")
            .strip()
            .replace(" ", "_")
        )
        pasta_curso = os.path.join(pasta_saida, curso_slug)
        os.makedirs(pasta_curso, exist_ok=True)

        titulo_real = titulos_curso.get(arquivo_pdf, curso_slug)
        _escrever_atomico(os.path.join(pasta_curso, "_titulo.txt"), titulo_real)

        for disciplina, aulas in disciplinas.items():
            contador += 1
            print(f"[{contador}/{total_disciplinas}] {disciplina} ({len(aulas)} aulas)...")

            # ---- Resolve area_key a partir dos registros ----
            areas_encontradas = {
                a.get("area", "").strip() for a in aulas if a.get("area", "").strip()
            }
            if len(areas_encontradas) > 1:
                msg = (
                    f"Registros conflitantes de área para '{disciplina}': "
                    f"{areas_encontradas}. Pulando disciplina."
                )
                logger.error(msg)
                resultados.append(
                    ResultadoDisciplina(disciplina=disciplina, area_key="", erro=msg)
                )
                continue

            area_key = areas_encontradas.pop() if areas_encontradas else ""
            if not area_key:
                msg = f"Campo 'area' ausente nos registros de '{disciplina}'. Pulando."
                logger.error(msg)
                resultados.append(
                    ResultadoDisciplina(disciplina=disciplina, area_key="", erro=msg)
                )
                continue

            try:
                profile = get_profile(area_key)
            except ValueError as exc:
                msg = f"Profile inválido para '{disciplina}' (area='{area_key}'): {exc}"
                logger.error(msg)
                resultados.append(
                    ResultadoDisciplina(disciplina=disciplina, area_key=area_key, erro=msg)
                )
                continue

            nome_arquivo = _sanitizar_nome_arquivo(disciplina)
            caminho_aluno = os.path.join(pasta_curso, f"{nome_arquivo}.md")
            caminho_professor = os.path.join(pasta_curso, f"{nome_arquivo}_Professor.md")

            # ---- Modo retomada: pula se par completo existir ----
            if not force and _par_completo(caminho_aluno, caminho_professor):
                logger.info("  ↩ Pulando '%s' (par completo já existe)", disciplina)
                print(f"   ↩ Pulando (já gerado): {nome_arquivo}.md")
                resultados.append(
                    ResultadoDisciplina(
                        disciplina=disciplina,
                        area_key=area_key,
                        caminho_aluno=caminho_aluno,
                        caminho_professor=caminho_professor,
                        pulada=True,
                    )
                )
                continue

            try:
                # ---- Ementa e conteúdo consolidados ----
                ementa_consolidada = aulas[0].get("ementa", "")
                conteudo_consolidado = "\n\n".join(
                    f"Aula {a.get('aula', i+1)} — {a.get('titulo_aula', '')}\n"
                    f"Objetivo: {a.get('ementa', '')}\n"
                    f"Conteúdo: {a.get('conteudo', '')}"
                    for i, a in enumerate(aulas)
                )

                # ---- RAG: contexto filtrado pela mesma área ----
                query = f"{disciplina} {ementa_consolidada} {conteudo_consolidado[:500]}"
                chunks = buscar_chunks(
                    query, model, index, base_geral,
                    filtro_area=area_key,
                )
                contexto = "\n\n".join(
                    f"{c['disciplina']}\n{c['conteudo']}"
                    for c in chunks
                    if c["disciplina"].lower() != disciplina.lower()
                )[:3_000]

                if instructions:
                    contexto = (
                        f"{contexto}\n\n"
                        "Observações editoriais do solicitante (incorpore quando pertinente, "
                        "sem alterar a estrutura pedagógica nem reduzir a qualidade técnica):\n"
                        f"{instructions}"
                    )

                # ---- Gera tópico por aula ----
                topicos_dict: dict[str, dict] = {}
                for aula in aulas:
                    topico = aula.get("titulo_aula", "") or aula.get("conteudo", "")
                    print(f"      📝 Tópico: {topico[:60]}")
                    conteudo_topico = gerar_topico(
                        gemini, disciplina, topico, contexto, profile
                    )
                    viol_t = _validar_vocabulario(conteudo_topico, profile)
                    _aplicar_politica_vocabulario(viol_t, disciplina, f"topico:{topico}")
                    sleep_fn(_DELAY_ENTRE_TOPICOS)

                    print(f"      ❓ Questões: {topico[:60]}")
                    q_aluno, q_prof = gerar_questoes_topico(
                        gemini, disciplina, topico, contexto, profile
                    )
                    viol_q = _validar_vocabulario(q_aluno + q_prof, profile)
                    _aplicar_politica_vocabulario(viol_q, disciplina, f"questoes:{topico}")
                    sleep_fn(_DELAY_ENTRE_TOPICOS)

                    topicos_dict[topico] = {
                        "conteudo": conteudo_topico,
                        "questoes_aluno": q_aluno,
                        "questoes_professor": q_prof,
                    }

                # ---- Gera seções globais ----
                intro = gerar_documento(
                    gemini, disciplina, ementa_consolidada,
                    "Gere apenas a introdução.", contexto, profile
                )
                _aplicar_politica_vocabulario(
                    _validar_vocabulario(str(intro), profile), disciplina, "introducao"
                )
                sleep_fn(_DELAY_ENTRE_SECOES)

                objetivos = gerar_documento(
                    gemini, disciplina, ementa_consolidada,
                    "Gere apenas os objetivos.", contexto, profile
                )
                _aplicar_politica_vocabulario(
                    _validar_vocabulario(str(objetivos), profile), disciplina, "objetivos"
                )
                sleep_fn(_DELAY_ENTRE_SECOES)

                exemplos = gerar_documento(
                    gemini, disciplina, ementa_consolidada,
                    "Gere apenas exemplos práticos.", contexto, profile
                )
                _aplicar_politica_vocabulario(
                    _validar_vocabulario(str(exemplos), profile), disciplina, "exemplos"
                )
                sleep_fn(_DELAY_ENTRE_SECOES)

                resumo = gerar_documento(
                    gemini, disciplina, ementa_consolidada,
                    "Gere apenas o resumo.", contexto, profile
                )
                _aplicar_politica_vocabulario(
                    _validar_vocabulario(str(resumo), profile), disciplina, "resumo"
                )
                sleep_fn(_DELAY_ENTRE_SECOES)

                questoes_result = gerar_documento(
                    gemini, disciplina, ementa_consolidada,
                    "Gere a avaliação geral completa da disciplina com questões "
                    "objetivas, dissertativas e baseadas em casos práticos.",
                    contexto,
                    profile,
                )

                if isinstance(questoes_result, tuple):
                    questoes_aluno, questoes_professor = questoes_result
                else:
                    questoes_aluno = questoes_result
                    questoes_professor = questoes_result

                _aplicar_politica_vocabulario(
                    _validar_vocabulario(questoes_aluno + questoes_professor, profile),
                    disciplina, "questoes"
                )

                doc_aluno, doc_professor = juntar_topicos_formatado(
                    str(intro), str(objetivos), topicos_dict,
                    str(exemplos), str(resumo),
                    questoes_aluno, questoes_professor,
                )

                # ---- Escrita atômica ----
                _escrever_atomico(
                    caminho_aluno,
                    texto_para_markdown(disciplina, doc_aluno),
                )
                _escrever_atomico(
                    caminho_professor,
                    texto_para_markdown(disciplina, doc_professor),
                )

                # ---- Confirma existência dos arquivos ----
                if not _par_completo(caminho_aluno, caminho_professor):
                    raise RuntimeError(
                        f"Arquivos gerados ausentes ou inválidos após escrita: "
                        f"{caminho_aluno}, {caminho_professor}"
                    )

                print(
                    f"   ✅ Salvo — aluno: {nome_arquivo}.md "
                    f"| professor: {nome_arquivo}_Professor.md"
                )

                todas_violacoes = []
                for dados in topicos_dict.values():
                    todas_violacoes += _validar_vocabulario(
                        dados["conteudo"] + dados["questoes_aluno"] + dados["questoes_professor"],
                        profile,
                    )

                resultados.append(
                    ResultadoDisciplina(
                        disciplina=disciplina,
                        area_key=area_key,
                        caminho_aluno=caminho_aluno,
                        caminho_professor=caminho_professor,
                        violacoes_vocab=todas_violacoes,
                    )
                )

                sleep_fn(_DELAY_ENTRE_DISC)

            except (TypeError, NameError, AttributeError) as exc:
                # Bugs de programação — traceback completo, não silenciado
                tb = traceback.format_exc()
                msg = f"BUG em '{disciplina}': {type(exc).__name__}: {exc}\n{tb}"
                logger.error(msg)
                print(f"   🐛 BUG detectado em '{disciplina}': {type(exc).__name__}: {exc}")
                print(tb)
                resultados.append(
                    ResultadoDisciplina(
                        disciplina=disciplina, area_key=area_key, erro=msg
                    )
                )
                # Propaga — este é um bug de programação, não um erro de dado
                raise

            except Exception as exc:
                tb = traceback.format_exc()
                msg = f"Erro em '{disciplina}': {type(exc).__name__}: {exc}"
                logger.error("%s\n%s", msg, tb)
                print(f"   ❌ {msg}")
                resultados.append(
                    ResultadoDisciplina(
                        disciplina=disciplina, area_key=area_key, erro=msg
                    )
                )

    gerados = sum(1 for r in resultados if r.caminho_aluno and not r.pulada and not r.erro)
    pulados = sum(1 for r in resultados if r.pulada)
    erros = sum(1 for r in resultados if r.erro)
    print(f"\n✅ {gerados} geradas | ↩ {pulados} puladas | ❌ {erros} erros")

    return resultados

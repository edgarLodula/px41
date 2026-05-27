import os
import re
import time
from src.content_generation.generator import gerar_topico, gerar_questoes_topico
def texto_para_markdown(disciplina, texto_bruto):
    secoes = {
        "INTRODUCAO":  "## Introdução",
        "OBJETIVOS":   "## Objetivos de Aprendizagem",
        "TOPICOS":     "## Explicação dos Tópicos",
        "EXEMPLOS":    "## Exemplos Práticos",
        "RESUMO":      "## Resumo",
        "QUESTOES":    "## Questões Dissertativas",
        }
    md = f"# {disciplina}\n\n"

    for rotulo, titulo_md in secoes.items():
        # pega o conteúdo entre esse rótulo e o próximo
        padrao = rf"{rotulo}:(.*?)(?={'|'.join(secoes.keys())}:|$)"
        match = re.search(padrao, texto_bruto, re.DOTALL)
        conteudo = match.group(1).strip() if match else ""
        md += f"{titulo_md}\n\n{conteudo}\n\n"

    return md
def limpar_texto(texto):
    return "\n".join([linha.strip() for linha in texto.strip().splitlines() if linha.strip()])


def _sanitizar_nome_arquivo(nome: str) -> str:
    """Remove caracteres inválidos para nomes de arquivo no Windows."""
    nome = " ".join(nome.split())  # colapsa whitespace/newlines em espaço único
    nome = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', nome)  # caracteres proibidos no Windows
    nome = re.sub(r'[^\w\s-]', '', nome)
    return nome.strip().replace(" ", "_")


def _controle_editorial_topico(i: int, nome: str) -> str:
    return (
        f"\n\n---\n\n"
        f"**Controle Editorial — Tópico {i}: {nome}**\n\n"
        f"| Item | Status |\n"
        f"|------|--------|\n"
        f"| Páginas planejadas | 10–12 |\n"
        f"| Fundamentação teórica | Sim |\n"
        f"| Aplicação prática | Sim |\n"
        f"| Casos práticos | Sim |\n"
        f"| Erros comuns | Sim |\n"
        f"| Glossário | Sim |\n"
        f"| Página de perguntas | Sim |\n"
        f"| Gabarito | Sim |\n\n"
        f"---\n"
    )


def juntar_topicos_formatado(introducao, objetivos, topicos_dict, exemplos, resumo, questoes):
    partes = []
    partes.append("INTRODUCAO:\n" + limpar_texto(introducao))
    partes.append("OBJETIVOS:\n" + limpar_texto(objetivos))

    topicos_texto = ["TOPICOS:"]
    for i, (nome, dados) in enumerate(topicos_dict.items(), 1):
        conteudo = dados["conteudo"] if isinstance(dados, dict) else dados
        questoes_topico = dados.get("questoes", "") if isinstance(dados, dict) else ""
        topicos_texto.append(f"\n### Tópico {i}: {nome}")
        topicos_texto.append(limpar_texto(conteudo))
        if questoes_topico:
            topicos_texto.append(f"\n#### Perguntas, Exercícios e Gabarito — Tópico {i}: {nome}")
            topicos_texto.append(limpar_texto(questoes_topico))
        topicos_texto.append(_controle_editorial_topico(i, nome))
    partes.append("\n\n".join(topicos_texto))

    partes.append("EXEMPLOS:\n" + limpar_texto(exemplos))
    partes.append("RESUMO:\n" + limpar_texto(resumo))
    partes.append("QUESTOES:\n" + limpar_texto(questoes))

    return "\n\n".join(partes)

def gerar_markdowns(
    base_geral,
    buscar_chunks,
    gerar_documento,
    model,
    index,
    gemini,
    pasta_saida="data/output/markdown",
    on_disciplina=None,   # callback(nome, concluidas, total) — progresso por disciplina
    base_rag=None,        # base completa para RAG (se None usa base_geral)
):
    os.makedirs(pasta_saida, exist_ok=True)

    # base para RAG — usa a completa quando disponível, evita index out of range
    _base_rag = base_rag if base_rag is not None else base_geral

    # -------------------------
    # AGRUPA: arquivo (PDF) → disciplina → lista de aulas
    # Garante 1 PDF entrada = 1 pasta/apostila saída
    # -------------------------
    cursos = {}
    titulos_curso = {}
    for item in base_geral:
        arquivo = item.get("arquivo", "").strip()
        if not arquivo:
            arquivo = "curso_desconhecido"
        disciplina = " ".join(item.get("disciplina", "").split()).strip()
        if not disciplina:
            continue
        cursos.setdefault(arquivo, {}).setdefault(disciplina, []).append(item)
        if arquivo not in titulos_curso:
            titulos_curso[arquivo] = item.get("curso", "") or arquivo

    total_disciplinas = sum(len(discs) for discs in cursos.values())
    print(f"📚 {total_disciplinas} disciplinas únicas encontradas\n")

    erros = []
    gerados = 0
    contador = 0

    for arquivo_pdf, disciplinas in cursos.items():
        # -------------------------
        # PASTA DO ARQUIVO (1 pasta por PDF de entrada)
        # -------------------------
        curso_slug = re.sub(r'[^\w\s-]', '', arquivo_pdf) \
            .replace(".pdf", "").replace(".csv", "") \
            .strip().replace(" ", "_")

        pasta_curso = os.path.join(pasta_saida, curso_slug)
        os.makedirs(pasta_curso, exist_ok=True)

        # Salva título real do curso para a capa da apostila
        titulo_real = titulos_curso.get(arquivo_pdf, curso_slug)
        with open(os.path.join(pasta_curso, "_titulo.txt"), "w", encoding="utf-8") as _f:
            _f.write(titulo_real)

        nome_curso = titulo_real

        for disciplina, aulas in disciplinas.items():
            contador += 1
            print(f"[{contador}/{total_disciplinas}] Gerando: {disciplina} ({len(aulas)} aulas)...")
            if on_disciplina:
                on_disciplina(disciplina, contador - 1, total_disciplinas)

            try:
                # -------------------------
                # MONTA EMENTA E CONTEÚDO CONSOLIDADOS
                # -------------------------
                ementa_consolidada = aulas[0].get("ementa", "")

                conteudo_consolidado = "\n\n".join([
                    f"Aula {a.get('aula', i+1)} — {a.get('titulo_aula', '')}\n"
                    f"Objetivo: {a.get('ementa', '')}\n"
                    f"Conteúdo: {a.get('conteudo', '')}\n"
                    f"Conceitos-chave: {a.get('conceitos_chave', '')}\n"
                    f"Exemplos práticos: {a.get('exemplos', '')}\n"
                    f"Exercícios: {a.get('exercicios', '')}"
                    for i, a in enumerate(aulas)
                ])

                # -------------------------
                # RAG — contexto de outras disciplinas
                # -------------------------
                query = f"{disciplina} {ementa_consolidada} {conteudo_consolidado[:500]}"
                chunks = buscar_chunks(query, model, index, _base_rag)
                contexto = "\n\n".join([
                    f"{c['disciplina']}\n{c['conteudo']}"
                    for c in chunks
                    if c["disciplina"].lower() != disciplina.lower()
                ])
                contexto = contexto[:3000]

                # -------------------------
                # LLM — uma chamada por disciplina
                # -------------------------
                topicos_dict = {}
                for aula in aulas:
                    topico = aula.get("titulo_aula", "") or aula.get("conteudo", "")
                    print(f"      📝 Gerando explicação: {topico}")
                    conteudo_topico = gerar_topico(gemini, disciplina, topico, contexto)
                    time.sleep(10)
                    print(f"      ❓ Gerando questões: {topico}")
                    questoes_topico = gerar_questoes_topico(gemini, disciplina, topico, contexto)
                    topicos_dict[topico] = {"conteudo": conteudo_topico, "questoes": questoes_topico}
                    time.sleep(10)

                intro     = gerar_documento(gemini, disciplina, ementa_consolidada, "Gere apenas a introdução.", contexto)
                time.sleep(10)
                objetivos = gerar_documento(gemini, disciplina, ementa_consolidada, "Gere apenas os objetivos.", contexto)
                time.sleep(10)
                exemplos  = gerar_documento(gemini, disciplina, ementa_consolidada, "Gere apenas exemplos práticos.", contexto)
                time.sleep(10)
                resumo    = gerar_documento(gemini, disciplina, ementa_consolidada, "Gere apenas o resumo.", contexto)
                time.sleep(10)
                questoes  = gerar_documento(gemini, disciplina, ementa_consolidada, "Gere a avaliação geral completa da disciplina com questões objetivas, dissertativas e baseadas em casos práticos.", contexto)

                documento = juntar_topicos_formatado(intro, objetivos, topicos_dict, exemplos, resumo, questoes)
                
                
                # -------------------------
                # SALVA .md
                # -------------------------
                
                nome_arquivo = _sanitizar_nome_arquivo(disciplina)

                caminho_doc = os.path.join(pasta_curso, f"{nome_arquivo}.md")

                with open(caminho_doc, "w", encoding="utf-8") as f:
                    f.write(texto_para_markdown(disciplina, documento))

                print(f"   ✅ Salvo ({len(aulas)} aulas)")
                gerados += 1

                time.sleep(35)  # evita rate limit

            except Exception as e:
                print(f"   ❌ Erro: {e}")
                erros.append({"disciplina": disciplina, "erro": str(e)})

    print(f"\n✅ {gerados} documentos gerados.")
    if erros:
        print(f"⚠️ {len(erros)} erros: {[e['disciplina'] for e in erros]}")
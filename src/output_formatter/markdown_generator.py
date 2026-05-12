import os
import re
import time
from src.content_generation.generator import gerar_topico
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


def juntar_topicos_formatado(introducao, objetivos, topicos_dict, exemplos, resumo, questoes):
    partes = []
    partes.append("INTRODUCAO:\n" + limpar_texto(introducao))
    partes.append("OBJETIVOS:\n" + limpar_texto(objetivos))

    topicos_texto = ["TOPICOS:"]
    for i, (nome, conteudo) in enumerate(topicos_dict.items(), 1):
        topicos_texto.append(f"\nTópico {i}: {nome}")
        topicos_texto.append(limpar_texto(conteudo))
    partes.append("\n".join(topicos_texto))

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
    pasta_saida="data/output/markdown"
):
    os.makedirs(pasta_saida, exist_ok=True)

    # -------------------------
    # AGRUPA: curso → disciplina → lista de aulas
    # -------------------------
    cursos = {}
    for item in base_geral:
        curso = item.get("curso") or item.get("arquivo", "curso_desconhecido")
        disciplina = item.get("disciplina", "").strip()
        if not disciplina:
            continue
        cursos.setdefault(curso, {}).setdefault(disciplina, []).append(item)

    total_disciplinas = sum(len(discs) for discs in cursos.values())
    print(f"📚 {total_disciplinas} disciplinas únicas encontradas\n")

    erros = []
    gerados = 0
    contador = 0

    for nome_curso, disciplinas in cursos.items():
        # -------------------------
        # PASTA DO CURSO
        # -------------------------
        curso_slug = re.sub(r'[^\w\s-]', '', nome_curso) \
            .replace(".pdf", "").replace(".csv", "") \
            .strip().replace(" ", "_")

        pasta_curso = os.path.join(pasta_saida, curso_slug)
        os.makedirs(pasta_curso, exist_ok=True)

        for disciplina, aulas in disciplinas.items():
            contador += 1
            print(f"[{contador}/{total_disciplinas}] Gerando: {disciplina} ({len(aulas)} aulas)...")

            try:
                # -------------------------
                # MONTA EMENTA E CONTEÚDO CONSOLIDADOS
                # (passa todas as aulas de uma vez pro Gemini)
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
                chunks = buscar_chunks(query, model, index, base_geral)
                contexto = "\n\n".join([
                    f"{c['disciplina']}\n{c['conteudo']}"
                    for c in chunks
                    if c["disciplina"].lower() != disciplina.lower()
                ])
                contexto = contexto[:3000]

                # -------------------------
                # GEMINI — uma chamada por disciplina
                # -------------------------
                topicos_dict = {}
                for aula in aulas:
                    topico = aula.get("titulo_aula", "") or aula.get("conteudo", "")
                    print(f"      📝 Gerando tópico: {topico}")
                    topicos_dict[topico] = gerar_topico(gemini, disciplina, topico, contexto)
                    

                intro     = gerar_documento(gemini, disciplina, ementa_consolidada, "Gere apenas a introdução.", contexto)
                objetivos = gerar_documento(gemini, disciplina, ementa_consolidada, "Gere apenas os objetivos.", contexto)
                exemplos  = gerar_documento(gemini, disciplina, ementa_consolidada, "Gere apenas exemplos práticos.", contexto)
                resumo    = gerar_documento(gemini, disciplina, ementa_consolidada, "Gere apenas o resumo.", contexto)
                questoes  = gerar_documento(gemini, disciplina, ementa_consolidada, "Gere apenas 5 questões dissertativas.", contexto)

                documento = juntar_topicos_formatado(intro, objetivos, topicos_dict, exemplos, resumo, questoes)
                
                
                # -------------------------
                # SALVA .md
                # -------------------------
                
                nome_arquivo = re.sub(r'[^\w\s-]', '', disciplina) \
                    .strip().replace(" ", "_")

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
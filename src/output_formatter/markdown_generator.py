import os
import re
import time


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

    disciplinas_vistas = set()
    disciplinas_unicas = []

    # -------------------------
    # FILTRA DISCIPLINAS ÚNICAS (POR CURSO + DISCIPLINA)
    # -------------------------
    for item in base_geral:
        curso = item.get("arquivo", "curso_desconhecido")
        nome = item.get("disciplina", "").strip()

        chave = f"{curso}::{nome}".lower()

        if nome and chave not in disciplinas_vistas:
            disciplinas_vistas.add(chave)
            disciplinas_unicas.append(item)

    print(f"📚 {len(disciplinas_unicas)} disciplinas únicas encontradas\n")

    erros = []

    # -------------------------
    # LOOP DE GERAÇÃO
    # -------------------------
    for i, item in enumerate(disciplinas_unicas):
        disciplina = item.get("disciplina", "Sem_nome")
        curso = item.get("arquivo", "curso_desconhecido")

        print(f"[{i+1}/{len(disciplinas_unicas)}] Gerando: {disciplina}...")

        try:
            # -------------------------
            # QUERY RAG
            # -------------------------
            query = f"{disciplina} {item.get('ementa', '')} {item.get('conteudo', '')}"

            chunks = buscar_chunks(query, model, index, base_geral)
            contexto = ""
            contexto = "\n\n".join([
                f"{c['disciplina']}\n{c['conteudo']}"
                for c in chunks
                if c["disciplina"].lower() != disciplina.lower()
            ])
            contexto = contexto[:3000]

            # -------------------------
            # GERA DOCUMENTO
            # -------------------------
            documento = gerar_documento(
                gemini,
                disciplina,
                item.get("ementa", ""),
                item.get("conteudo", ""),
                contexto
            )
            
            # -------------------------
            # CRIA PASTA DO CURSO
            # -------------------------
            curso_nome = re.sub(r'[^\w\s-]', '', curso)\
                .replace(".pdf", "")\
                .strip()\
                .replace(" ", "_")

            pasta_curso = os.path.join(pasta_saida, curso_nome)
            os.makedirs(pasta_curso, exist_ok=True)

            # -------------------------
            # NOME DO ARQUIVO
            # -------------------------
            nome_arquivo = re.sub(r'[^\w\s-]', '', disciplina)\
                .strip()\
                .replace(" ", "_")

            caminho_doc = os.path.join(pasta_curso, f"{nome_arquivo}.md")

            # -------------------------
            # SALVA
            # -------------------------
            with open(caminho_doc, "w", encoding="utf-8") as f:
                f.write(f"# {disciplina}\n\n{documento}")

            print("   ✅ Salvo")

            time.sleep(35)  # evita rate limit

        except Exception as e:
            print(f"   ❌ Erro: {e}")
            erros.append({"disciplina": disciplina, "erro": str(e)})

    print(f"\n✅ {len(disciplinas_unicas) - len(erros)} documentos gerados.")

    if erros:
        print(f"⚠️ {len(erros)} erros: {[e['disciplina'] for e in erros]}")
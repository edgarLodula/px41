import os
import re

import requests

from src.video_generator.gerador_videos_direto import (
    aguardar_video,
    extrair_falas_do_roteiro,
    gerar_roteiro,
    gerar_video_heygen,
    parsear_cenas_do_roteiro,
)


def _slug(nome: str) -> str:
    slug = re.sub(r"[^\w.-]+", "_", nome.strip(), flags=re.UNICODE)
    return slug.strip("_") or "disciplina"


def _baixar_video(video_url: str, caminho_saida: str):
    resp = requests.get(video_url, timeout=60)
    resp.raise_for_status()
    with open(caminho_saida, "wb") as f:
        f.write(resp.content)


def gerar_videos_por_disciplina(pasta_markdown, pasta_saida, openai_token, heyGen_token):
    """
    Gera videos por disciplina a partir dos markdowns ja produzidos pela pipeline.

    Fluxo: markdown -> roteiro -> cenas -> falas -> HeyGen v3 -> download mp4
    """
    if not openai_token:
        raise ValueError("OPENAI_API_KEY nao configurada.")
    if not heyGen_token:
        raise ValueError("HEYGEN_API_KEY nao configurada.")

    os.makedirs(pasta_saida, exist_ok=True)

    for curso in os.listdir(pasta_markdown):
        caminho_curso = os.path.join(pasta_markdown, curso)

        if not os.path.isdir(caminho_curso):
            continue

        print(f"\nCurso: {curso}")

        pasta_curso_video = os.path.join(pasta_saida, curso)
        os.makedirs(pasta_curso_video, exist_ok=True)

        for arquivo in os.listdir(caminho_curso):
            if not arquivo.endswith(".md"):
                continue

            disciplina = arquivo.replace(".md", "").replace("_", " ")
            caminho_md = os.path.join(caminho_curso, arquivo)

            print(f"Gerando video: {disciplina}")

            try:
                pasta_disciplina = os.path.join(pasta_curso_video, _slug(disciplina))
                os.makedirs(pasta_disciplina, exist_ok=True)

                caminho_video = os.path.join(pasta_disciplina, "video.mp4")

                with open(caminho_md, "r", encoding="utf-8") as f:
                    markdown = f.read()

                roteiro = gerar_roteiro(markdown, disciplina, openai_token)
                cenas = parsear_cenas_do_roteiro(roteiro)
                falas = extrair_falas_do_roteiro(cenas)

                fala = falas.get(disciplina)
                if not fala and falas:
                    fala = next(iter(falas.values()))
                if not fala:
                    fala = " ".join(
                        cena.get("fala", "")
                        for grupo in cenas
                        for cena in grupo.get("cenas", [])
                        if cena.get("fala")
                    ).strip()
                if not fala:
                    raise ValueError("Nenhuma fala encontrada no roteiro gerado.")

                video_id = gerar_video_heygen(fala, disciplina, heyGen_token)
                info = aguardar_video(video_id, heyGen_token, max_min=10.0)

                video_url = info.get("video_url")
                if not video_url:
                    raise RuntimeError(f"HeyGen concluiu sem video_url: {info}")

                _baixar_video(video_url, caminho_video)

                print(f"   Finalizado: {caminho_video}")

            except Exception as e:
                print(f"   Erro em {disciplina}: {e}")

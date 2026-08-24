import os
import re

from src.video_generator.gerador_videos_direto import (
    gerar_roteiro,
    parsear_cenas_do_roteiro,
)
from src.video_generator.video_generator import gerar_video_com_slides


def _slug(nome: str) -> str:
    slug = re.sub(r"[^\w.-]+", "_", nome.strip(), flags=re.UNICODE)
    return slug.strip("_") or "disciplina"


def gerar_videos_por_disciplina(pasta_markdown, pasta_saida, openai_token, heyGen_token):
    """
    Gera videos por disciplina a partir dos markdowns ja produzidos pela pipeline.

    Fluxo: markdown -> roteiro -> cenas -> slides + avatar (recortado/posicionado
    no canto) + legenda queimada -> mp4 (mesmo pipeline usado em test_video_um.py).
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
                pasta_slides = os.path.join(pasta_disciplina, "slides")

                with open(caminho_md, "r", encoding="utf-8") as f:
                    markdown = f.read()

                roteiro = gerar_roteiro(markdown, disciplina, openai_token)
                disciplinas_parseadas = parsear_cenas_do_roteiro(roteiro)

                cenas = disciplinas_parseadas[0]["cenas"] if disciplinas_parseadas else []
                if not cenas:
                    raise ValueError("Nenhuma cena com fala encontrada no roteiro gerado.")

                gerar_video_com_slides(
                    cenas=cenas,
                    disciplina=disciplina,
                    caminho_saida=caminho_video,
                    pasta_slides=pasta_slides,
                    heygen_token=heyGen_token,
                    openai_token=openai_token,
                )

                print(f"   Finalizado: {caminho_video}")

            except Exception as e:
                print(f"   Erro em {disciplina}: {e}")

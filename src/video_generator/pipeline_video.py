import os
import re
import shutil

from src.video_generator.gerador_videos_direto import (
    gerar_roteiro,
    gerar_video_v3_multicena,
    parsear_cenas_do_roteiro,
)


def _slug(nome: str) -> str:
    slug = re.sub(r"[^\w.-]+", "_", nome.strip(), flags=re.UNICODE)
    return slug.strip("_") or "disciplina"


def gerar_videos_por_disciplina(pasta_markdown, pasta_saida, openai_token, heyGen_token):
    """
    Gera videos por disciplina a partir dos markdowns ja produzidos pela pipeline.

    Fluxo: markdown -> roteiro -> cenas -> HeyGen v3 (uma chamada por cena) -> concat -> mp4

    Cada cena do roteiro (abertura/desenvolvimento/encerramento) vira uma chamada
    HeyGen independente, com motion_prompt/expressiveness derivados da direção
    [PRODUCAO] daquela cena — em vez de concatenar todas as falas em um único
    bloco de texto e gerar um video "estático" com uma unica expressao do inicio
    ao fim, o que é a principal causa de o avatar parecer pouco natural.
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
                todas_cenas = parsear_cenas_do_roteiro(roteiro)

                disc_data = next(
                    (d for d in todas_cenas if d.get("disciplina") == disciplina),
                    None,
                )
                if not disc_data and todas_cenas:
                    disc_data = todas_cenas[0]

                cenas = disc_data.get("cenas", []) if disc_data else []
                cenas_com_fala = [
                    {"fala": c["fala"], "producao": c.get("producao", "")}
                    for c in cenas
                    if c.get("fala")
                ]
                if not cenas_com_fala:
                    raise ValueError("Nenhuma fala encontrada no roteiro gerado.")

                caminho_gerado = gerar_video_v3_multicena(
                    cenas_com_slides=cenas_com_fala,
                    disciplina=disciplina,
                    heygen_token=heyGen_token,
                    pasta_temp=pasta_disciplina,
                )

                if os.path.abspath(caminho_gerado) != os.path.abspath(caminho_video):
                    shutil.move(caminho_gerado, caminho_video)

                print(f"   Finalizado: {caminho_video}")

            except Exception as e:
                print(f"   Erro em {disciplina}: {e}")

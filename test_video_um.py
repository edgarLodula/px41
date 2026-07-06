"""
Gera 1 único vídeo HeyGen a partir de UM markdown, para teste rápido
(sem rodar o pipeline completo de PDF/apostila).

Uso:
    python test_video_um.py "data/output/markdown/curso_x/disciplina.md" [fem|masc]

Se nenhum caminho for passado, usa o primeiro .md encontrado em
data/output/markdown/ (busca recursiva).
O segundo argumento escolhe o avatar/voz (padrão: fem = Marina).
"""
import glob
import os
import sys

from dotenv import load_dotenv

from src.video_generator.roteiro_generator import gerar_roteiro
from src.video_generator.video_generator import gerar_video

PASTA_MARKDOWN = "data/output/markdown"
PASTA_SAIDA = "data/output/videos/teste_unico"


def _localizar_markdown() -> str:
    if len(sys.argv) > 1:
        caminho = sys.argv[1]
        if not os.path.isfile(caminho):
            print(f"ERRO: markdown não encontrado: {caminho}")
            sys.exit(1)
        return caminho

    candidatos = sorted(glob.glob(os.path.join(PASTA_MARKDOWN, "**", "*.md"), recursive=True))
    if not candidatos:
        print(f"ERRO: nenhum .md encontrado em '{PASTA_MARKDOWN}'. Passe o caminho como argumento.")
        sys.exit(1)
    print(f"[AVISO] Nenhum caminho informado — usando o primeiro .md encontrado: {candidatos[0]}")
    return candidatos[0]


def main():
    load_dotenv()

    voz = sys.argv[2] if len(sys.argv) > 2 else "fem"
    if voz not in ("fem", "masc"):
        print("ERRO: segundo argumento deve ser 'fem' ou 'masc'.")
        sys.exit(1)

    if voz == "fem":
        avatar_id, voice_id, nome_avatar = (
            os.getenv("AVATAR_FEM_ID"), os.getenv("VOZ_FEM_ID"), "Marina",
        )
    else:
        avatar_id, voice_id, nome_avatar = (
            os.getenv("AVATAR_MASC_ID"), os.getenv("VOZ_MASC_ID"), "Mário",
        )

    envs = {
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "HEYGEN_API_KEY": os.getenv("HEYGEN_API_KEY"),
        f"AVATAR_{'FEM' if voz == 'fem' else 'MASC'}_ID": avatar_id,
        f"VOZ_{'FEM' if voz == 'fem' else 'MASC'}_ID": voice_id,
    }
    faltando = [k for k, v in envs.items() if not v]
    if faltando:
        print(f"ERRO: variaveis ausentes no .env: {', '.join(faltando)}")
        sys.exit(1)

    os.environ["HEYGEN_AVATAR_ID"] = avatar_id
    os.environ["HEYGEN_VOICE_ID"] = voice_id
    os.environ["AVATAR_NOME"] = nome_avatar

    caminho_md = _localizar_markdown()
    disciplina = os.path.splitext(os.path.basename(caminho_md))[0].replace("_", " ")

    pasta_saida = os.path.join(PASTA_SAIDA, disciplina.replace(" ", "_"))
    pasta_roteiro = os.path.join(pasta_saida, "roteiro")
    pasta_slides = os.path.join(pasta_saida, "slides")
    caminho_roteiro = os.path.join(pasta_roteiro, "roteiro.txt")
    caminho_video = os.path.join(pasta_saida, "video.mp4")

    os.makedirs(pasta_roteiro, exist_ok=True)

    print(f"[{disciplina}] Lendo: {caminho_md}")
    with open(caminho_md, "r", encoding="utf-8") as f:
        markdown = f.read()

    # Exposto para slides_generator via env (limite Windows: 32767 chars)
    os.environ["SLIDES_MD_CONTEXT"] = markdown[:8000]

    if os.path.isfile(caminho_roteiro):
        print(f"[{disciplina}] Reusando roteiro existente: {caminho_roteiro}")
        with open(caminho_roteiro, "r", encoding="utf-8") as f:
            roteiro = f.read()
    else:
        print(f"[{disciplina}] Gerando roteiro via OpenAI...")
        roteiro = gerar_roteiro(markdown, disciplina, envs["OPENAI_API_KEY"])
        with open(caminho_roteiro, "w", encoding="utf-8") as f:
            f.write(roteiro)
        print(f"[{disciplina}] Roteiro salvo: {caminho_roteiro}")

    print(f"[{disciplina}] Gerando vídeo...")
    try:
        gerar_video(
            roteiro=roteiro,
            caminho_saida=caminho_video,
            pasta_slides=pasta_slides,
            disciplina=disciplina,
        )
        print(f"[{disciplina}] Concluído. Vídeo: {caminho_video}")
    except Exception as e:
        print(f"[{disciplina}] FALHOU: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

"""
Script de teste: gera roteiro + slides (1 por cena) + video sincronizado para
Anatomia e Fisiologia I.

Execute: python test_video.py
"""

import os
from dotenv import load_dotenv

from src.video_generator.roteiro_generator import gerar_roteiro
from src.video_generator.video_generator import gerar_video

load_dotenv()

# ── Configuracao ──────────────────────────────────────────────────────────────
CAMINHO_MD  = (
    r"data\output\markdown"
    r"\Tabela_Completa_Conteudo_Programatico_Tecnico_Enfermagemdocx"
    r"\Anatomia_e_Fisiologia_I.md"
)
PASTA_SAIDA  = r"data\output\videos\teste\Anatomia_e_Fisiologia_I"
DISCIPLINA   = "Anatomia e Fisiologia I"
# ─────────────────────────────────────────────────────────────────────────────


def main():
    openai_token = os.getenv("OPENAI_API_KEY")
    heygen_token = os.getenv("HEYGEN_API_KEY")
    avatar_id    = os.getenv("HEYGEN_AVATAR_ID")
    voice_id     = os.getenv("HEYGEN_VOICE_ID")

    faltando = [k for k, v in {
        "OPENAI_API_KEY":   openai_token,
        "HEYGEN_API_KEY":   heygen_token,
        "HEYGEN_AVATAR_ID": avatar_id,
        "HEYGEN_VOICE_ID":  voice_id,
    }.items() if not v]
    if faltando:
        print(f"ERRO: variaveis ausentes no .env: {', '.join(faltando)}")
        return

    pasta_roteiro = os.path.join(PASTA_SAIDA, "roteiro")
    pasta_slides  = os.path.join(PASTA_SAIDA, "slides")
    os.makedirs(pasta_roteiro, exist_ok=True)

    caminho_roteiro = os.path.join(pasta_roteiro, "roteiro.txt")
    caminho_video   = os.path.join(PASTA_SAIDA, "video.mp4")

    # 1. Le o markdown
    print(f"Lendo markdown: {CAMINHO_MD}")
    with open(CAMINHO_MD, "r", encoding="utf-8") as f:
        markdown = f.read()

    # 2. Gera roteiro via OpenAI (formato [AVATAR] / [VISUAL/B-ROLL] / [TEXTO NA TELA])
    print("Gerando roteiro via OpenAI...")
    roteiro = gerar_roteiro(markdown, DISCIPLINA, openai_token)
    with open(caminho_roteiro, "w", encoding="utf-8") as f:
        f.write(roteiro)
    print(f"Roteiro salvo em: {caminho_roteiro}")

    # 3. Gera slides (1 por cena) + upload HeyGen Assets + video sincronizado
    print("Iniciando geracao de slides, upload e video...")
    gerar_video(
        roteiro=roteiro,
        caminho_saida=caminho_video,
        pasta_slides=pasta_slides,
        disciplina=DISCIPLINA,
    )

    print(f"\nConcluido!")
    print(f"  Roteiro : {caminho_roteiro}")
    print(f"  Slides  : {pasta_slides}")
    print(f"  Video   : {caminho_video}")


if __name__ == "__main__":
    main()

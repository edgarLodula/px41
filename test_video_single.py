"""
Versao enxuta do test_video.py — gera APENAS 1 video (Anatomia e Fisiologia I,
avatar/voz feminino) para validar as melhorias de naturalidade do HeyGen
(motion_prompt/expressiveness dinamicos por cena) gastando o minimo de creditos.

Execute: python test_video_single.py
"""
import os
import sys

from dotenv import load_dotenv

from src.video_generator.roteiro_generator import gerar_roteiro
from src.video_generator.video_generator import gerar_video


_BASE_MD = (
    r"data\output\markdown"
    r"\Tabela_Completa_Conteudo_Programatico_Tecnico_Enfermagemdocx"
)


def main():
    load_dotenv()

    envs = {
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "HEYGEN_API_KEY": os.getenv("HEYGEN_API_KEY"),
        "AVATAR_FEM_ID":  os.getenv("AVATAR_FEM_ID"),
        "VOZ_FEM_ID":     os.getenv("VOZ_FEM_ID"),
    }
    faltando = [k for k, v in envs.items() if not v]
    if faltando:
        print(f"ERRO: variaveis ausentes no .env: {', '.join(faltando)}")
        sys.exit(1)

    openai_token = envs["OPENAI_API_KEY"]

    job = {
        "disciplina":  "Anatomia e Fisiologia I",
        "md_path":     _BASE_MD + r"\Anatomia_e_Fisiologia_I.md",
        "pasta_saida": r"data\output\videos\teste_single\Anatomia_e_Fisiologia_I",
        "avatar_id":   envs["AVATAR_FEM_ID"],
        "voice_id":    envs["VOZ_FEM_ID"],
        "nome_avatar": "Marina",
    }

    if not os.path.isfile(job["md_path"]):
        print(f"ERRO: arquivo markdown não encontrado: {job['md_path']}")
        sys.exit(1)

    os.environ["HEYGEN_AVATAR_ID"] = job["avatar_id"]
    os.environ["HEYGEN_VOICE_ID"]  = job["voice_id"]
    os.environ["AVATAR_NOME"]      = job["nome_avatar"]

    disc            = job["disciplina"]
    pasta_saida     = job["pasta_saida"]
    pasta_roteiro   = os.path.join(pasta_saida, "roteiro")
    pasta_slides    = os.path.join(pasta_saida, "slides")
    caminho_roteiro = os.path.join(pasta_roteiro, "roteiro.txt")
    caminho_video   = os.path.join(pasta_saida, "video.mp4")

    os.makedirs(pasta_roteiro, exist_ok=True)

    try:
        print(f"[{disc}] Lendo: {job['md_path']}")
        with open(job["md_path"], "r", encoding="utf-8") as f:
            markdown = f.read()

        os.environ["SLIDES_MD_CONTEXT"] = markdown[:8000]

        if os.path.isfile(caminho_roteiro):
            print(f"[{disc}] Reusando roteiro existente: {caminho_roteiro}")
            with open(caminho_roteiro, "r", encoding="utf-8") as f:
                roteiro = f.read()
        else:
            print(f"[{disc}] Gerando roteiro via OpenAI...")
            roteiro = gerar_roteiro(markdown, disc, openai_token)
            with open(caminho_roteiro, "w", encoding="utf-8") as f:
                f.write(roteiro)
            print(f"[{disc}] Roteiro salvo: {caminho_roteiro}")

        print(f"[{disc}] Gerando vídeo...")
        gerar_video(
            roteiro=roteiro,
            caminho_saida=caminho_video,
            pasta_slides=pasta_slides,
            disciplina=disc,
        )

        print(f"\n[{disc}] Concluído. Vídeo: {caminho_video}")

    except Exception as e:
        print(f"\n[{disc}] FALHOU: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

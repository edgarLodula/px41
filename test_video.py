"""
Gera 2 vídeos HeyGen em sequência:
  1. Anatomia e Fisiologia I  (avatar/voz feminino — Marina)
  2. Português                (avatar/voz masculino — Mário)

Execute: python test_video.py
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
        "AVATAR_MASC_ID": os.getenv("AVATAR_MASC_ID"),
        "VOZ_MASC_ID":    os.getenv("VOZ_MASC_ID"),
    }
    faltando = [k for k, v in envs.items() if not v]
    if faltando:
        print(f"ERRO: variaveis ausentes no .env: {', '.join(faltando)}")
        sys.exit(1)

    openai_token = envs["OPENAI_API_KEY"]

    jobs = [
        {
            "disciplina":  "Anatomia e Fisiologia I",
            "md_path":     _BASE_MD + r"\Anatomia_e_Fisiologia_I.md",
            "pasta_saida": r"data\output\videos\teste\Anatomia_e_Fisiologia_I",
            "avatar_id":   envs["AVATAR_FEM_ID"],
            "voice_id":    envs["VOZ_FEM_ID"],
            "nome_avatar": "Marina",
        },
        {
            "disciplina":  "Português",
            "md_path":     _BASE_MD + r"\Português.md",
            "pasta_saida": r"data\output\videos\teste\Português",
            "avatar_id":   envs["AVATAR_MASC_ID"],
            "voice_id":    envs["VOZ_MASC_ID"],
            "nome_avatar": "Mário",
        },
    ]

    # Resolver caminho do Português (fallback sem acento) e validar TODOS antes de gastar crédito
    for job in jobs:
        if not os.path.isfile(job["md_path"]):
            fallback = job["md_path"].replace("Português.md", "Portugues.md")
            if os.path.isfile(fallback):
                print(f"   [AVISO] Usando fallback de caminho: {fallback}")
                job["md_path"] = fallback
            else:
                print(f"ERRO: arquivo markdown não encontrado: {job['md_path']}")
                sys.exit(1)

    resultados = {}

    for job in jobs:
        disc = job["disciplina"]
        print(f"\n[{disc}] Iniciando...")

        os.environ["HEYGEN_AVATAR_ID"] = job["avatar_id"]
        os.environ["HEYGEN_VOICE_ID"]  = job["voice_id"]
        os.environ["AVATAR_NOME"]      = job["nome_avatar"]

        pasta_saida     = job["pasta_saida"]
        pasta_roteiro   = os.path.join(pasta_saida, "roteiro")
        pasta_slides    = os.path.join(pasta_saida, "slides")
        caminho_roteiro = os.path.join(pasta_roteiro, "roteiro.txt")
        caminho_video   = os.path.join(pasta_saida, "video.mp4")

        os.makedirs(pasta_roteiro, exist_ok=True)

        try:
            # 1. Ler markdown
            print(f"[{disc}] Lendo: {job['md_path']}")
            with open(job["md_path"], "r", encoding="utf-8") as f:
                markdown = f.read()

            # Expor markdown para slides_generator via env (limite Windows: 32767 chars)
            os.environ["SLIDES_MD_CONTEXT"] = markdown[:8000]

            # 2. Gerar ou reusar roteiro
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

            # 3. Gerar slides + upload + vídeo
            print(f"[{disc}] Gerando vídeo...")
            gerar_video(
                roteiro=roteiro,
                caminho_saida=caminho_video,
                pasta_slides=pasta_slides,
                disciplina=disc,
            )

            resultados[disc] = "OK"
            print(f"[{disc}] Concluído. Vídeo: {caminho_video}")

        except Exception as e:
            resultados[disc] = f"ERRO: {e}"
            print(f"[{disc}] FALHOU: {e}")

    print("\n" + "=" * 60)
    print("RESUMO FINAL")
    for disc, status in resultados.items():
        print(f"  {disc}: {status}")
    print("=" * 60)


if __name__ == "__main__":
    main()

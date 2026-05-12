import os

from src.video_generator.roteiro_generator import gerar_roteiro
from src.video_generator.video_generator import gerar_video


def gerar_videos_por_disciplina(pasta_markdown, pasta_saida, gemini_token, heyGen_token):
    if not heyGen_token:
        raise ValueError("❌ heyGen_token não encontrado. Configure no .env ou sistema.")

    os.makedirs(pasta_saida, exist_ok=True)

    for curso in os.listdir(pasta_markdown):
        caminho_curso = os.path.join(pasta_markdown, curso)

        if not os.path.isdir(caminho_curso):
            continue

        print(f"\n📚 Curso: {curso}")

        # pasta do curso
        pasta_curso_video = os.path.join(pasta_saida, curso)
        os.makedirs(pasta_curso_video, exist_ok=True)

        for arquivo in os.listdir(caminho_curso):
            if not arquivo.endswith(".md"):
                continue

            disciplina = arquivo.replace(".md", "")
            caminho_md = os.path.join(caminho_curso, arquivo)

            print(f"🎬 Gerando: {disciplina}")

            try:
                # pasta da disciplina
                pasta_disciplina = os.path.join(pasta_curso_video, disciplina)
                os.makedirs(pasta_disciplina, exist_ok=True)

                
                caminho_video = os.path.join(pasta_disciplina, "video.mp4")

                with open(caminho_md, "r", encoding="utf-8") as f:
                    texto = f.read()

                # 1. Roteiro
                roteiro = gerar_roteiro(texto, disciplina, gemini_token)


                # 4. Vídeo
                gerar_video(roteiro, caminho_video)

                print(f"   ✅ Finalizado: {disciplina}")

            except Exception as e:
                print(f"   ❌ Erro em {disciplina}: {e}")
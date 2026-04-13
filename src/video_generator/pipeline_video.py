import os

from src.video_generator.roteiro_generator import gerar_roteiro
from src.video_generator.audio_generator import gerar_audio
from src.video_generator.slides_generator import gerar_slides
from src.video_generator.video_generator import gerar_video


def gerar_videos_por_disciplina(pasta_markdown, pasta_saida, groq_token):
    if not groq_token:
        raise ValueError("❌ GROQ_TOKEN não encontrado. Configure no .env ou sistema.")

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

                caminho_audio = os.path.join(pasta_disciplina, "audio.mp3")
                pasta_slides = os.path.join(pasta_disciplina, "slides")
                os.makedirs(pasta_slides, exist_ok=True)
                caminho_video = os.path.join(pasta_disciplina, "video.mp4")

                with open(caminho_md, "r", encoding="utf-8") as f:
                    texto = f.read()

                # 1. Roteiro
                roteiro = gerar_roteiro(texto, disciplina, groq_token)

                # 2. Áudio
                gerar_audio(roteiro, caminho_audio)

                # 3. Slides
                gerar_slides(roteiro, pasta_slides, disciplina)

                # 4. Vídeo
                gerar_video(pasta_slides, caminho_audio, caminho_video)

                print(f"   ✅ Finalizado: {disciplina}")

            except Exception as e:
                print(f"   ❌ Erro em {disciplina}: {e}")
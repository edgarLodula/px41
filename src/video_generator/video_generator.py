import os
import glob
from PIL import Image, ImageDraw
import shutil
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips

# CONFIG
LARGURA, ALTURA = 1280, 720
W_AVATAR = 380
W_SLIDE = LARGURA - W_AVATAR

AVATAR_PATH = "assets/avatar_SanMarino.jpeg"


# -------------------------
# AVATAR (4 poses)
# -------------------------
def carregar_avatar(path_avatar):
    avatar = Image.open(path_avatar).convert("RGBA")

    largura, altura = avatar.size

    w = largura // 2
    h = altura // 2

    avatares = [
        avatar.crop((0, 0, w, h)),              # topo esquerdo
        avatar.crop((w, 0, largura, h)),        # topo direito
        avatar.crop((0, h, w, altura)),         # baixo esquerdo
        avatar.crop((w, h, largura, altura)),   # baixo direito
    ]

    return avatares


# -------------------------
# MONTA FRAME
# -------------------------
def montar_frame(caminho_slide, avatar_img):
    frame = Image.new("RGB", (LARGURA, ALTURA), (30, 58, 95))
    draw = ImageDraw.Draw(frame)

    # fundo esquerda (avatar)
    draw.rectangle([(0, 0), (W_AVATAR, ALTURA)], fill=(30, 58, 95))

    # redimensiona avatar
    avatar_img = avatar_img.copy()
    avatar_img.thumbnail((W_AVATAR - 40, ALTURA - 80))

    x = (W_AVATAR - avatar_img.width) // 2
    y = ALTURA - avatar_img.height - 20

    frame.paste(avatar_img, (x, y), avatar_img)

    # linha separadora
    draw.rectangle([(W_AVATAR, 0), (W_AVATAR + 4, ALTURA)], fill=(8, 145, 178))

    # slide (direita)
    slide = Image.open(caminho_slide).convert("RGB")
    slide = slide.resize((W_SLIDE, ALTURA))

    frame.paste(slide, (W_AVATAR + 4, 0))

    return frame


# -------------------------
# GERA VIDEO
# -------------------------
def gerar_video(pasta_slides, caminho_audio, caminho_saida):
    slides = sorted(glob.glob(os.path.join(pasta_slides, "slide_*.png")))

    if not slides:
        print("   ⚠️ Sem slides encontrados")
        return

    if not os.path.exists(caminho_audio):
        print("   ⚠️ Áudio não encontrado")
        return

    print(f"   🎞️ {len(slides)} slides encontrados")

    # carrega áudio
    audio = AudioFileClip(caminho_audio)
    duracao_total = audio.duration

    # duração por slide
    duracao_slide = duracao_total / len(slides)

    print(f"   ⏱️ {duracao_total/60:.1f} min | {duracao_slide:.1f}s por slide")

    # carrega avatares
    avatares = carregar_avatar(AVATAR_PATH)

    # pasta temporária
    pasta_tmp = "tmp_frames"
    os.makedirs(pasta_tmp, exist_ok=True)

    clips = []

    for idx, caminho_slide in enumerate(slides):
        avatar = avatares[idx % len(avatares)]

        frame = montar_frame(caminho_slide, avatar)

        caminho_frame = os.path.join(pasta_tmp, f"frame_{idx:03d}.png")
        frame.save(caminho_frame)

        clip = ImageClip(caminho_frame).set_duration(duracao_slide)
        clips.append(clip)

    # concatena
    video = concatenate_videoclips(clips)

    # adiciona áudio
    video = video.set_audio(audio)

    # exporta
    video.write_videofile(
        caminho_saida,
        fps=24,
        codec="libx264",
        audio_codec="aac"
    )

    print(f"   ✅ Vídeo salvo em: {caminho_saida}")

    shutil.rmtree(pasta_tmp, ignore_errors=True)
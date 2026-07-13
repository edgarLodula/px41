"""
Teste incremental do novo pipeline de vídeo (intro HeyGen + slides TTS + outro HeyGen).

MODOS DE TESTE (use --modo):

  parser   — Gera roteiro via OpenAI e valida se [TIPO] foi parseado corretamente.
             Não gera áudio nem vídeo. Rápido e barato (só OpenAI Chat).

  tts      — Além do parser, gera o áudio TTS de cada cena de conteúdo e combina
             com o slide PNG via ffmpeg. Não usa HeyGen. Barato e rápido.

  completo — Pipeline inteiro: intro HeyGen + slides TTS + outro HeyGen.
             Usa HeyGen (cobra créditos). Demora ~5–10 min por aula.

Uso:
    python test_novo_pipeline.py --modo parser
    python test_novo_pipeline.py --modo tts
    python test_novo_pipeline.py --modo completo
    python test_novo_pipeline.py --modo completo --md caminho/para/disciplina.md
"""
import argparse
import os
import sys
import textwrap

from dotenv import load_dotenv

load_dotenv()

# ── markdown de exemplo embutido (usado quando não é passado --md) ────────────
MARKDOWN_EXEMPLO = textwrap.dedent("""\
    # Introdução à Anatomia

    ## Ementa
    Conceitos básicos de anatomia humana para profissionais de saúde.

    ## Conteúdo Programático
    - Organização do corpo humano: células, tecidos, órgãos e sistemas
    - Planos anatômicos e termos de posição
    - Sistema esquelético: ossos axiais e apendiculares
    - Sistema muscular: tipos de músculos e principais grupos
    - Noções de fisiologia integrada
""")
# ─────────────────────────────────────────────────────────────────────────────


def _checar_env(*chaves: str):
    faltando = [k for k in chaves if not os.getenv(k)]
    if faltando:
        print(f"ERRO: variáveis ausentes no .env: {', '.join(faltando)}")
        sys.exit(1)


def _ler_markdown(caminho_md: str | None) -> tuple[str, str]:
    """Retorna (markdown, nome_disciplina)."""
    if caminho_md:
        if not os.path.isfile(caminho_md):
            print(f"ERRO: arquivo não encontrado: {caminho_md}")
            sys.exit(1)
        with open(caminho_md, "r", encoding="utf-8") as f:
            md = f.read()
        disciplina = os.path.splitext(os.path.basename(caminho_md))[0].replace("_", " ")
    else:
        print("[AVISO] Nenhum --md passado — usando markdown de exemplo embutido.")
        md = MARKDOWN_EXEMPLO
        disciplina = "Introdução à Anatomia"
    return md, disciplina


def _gerar_e_parsear_roteiro(md: str, disciplina: str) -> tuple[str, list[dict]]:
    from src.video_generator.gerador_videos_direto import (
        gerar_roteiro,
        parsear_cenas_do_roteiro,
    )

    openai_token = os.getenv("OPENAI_API_KEY")
    print(f"\n{'='*60}")
    print(f"ETAPA 1 — Gerando roteiro via OpenAI para: {disciplina}")
    print("="*60)
    roteiro = gerar_roteiro(md, disciplina, openai_token)
    print("\n--- ROTEIRO GERADO ---")
    print(roteiro[:2000], "..." if len(roteiro) > 2000 else "")
    print("---------------------")

    print("\nETAPA 2 — Parseando cenas e tipos...")
    disciplinas_parseadas = parsear_cenas_do_roteiro(roteiro)

    if not disciplinas_parseadas:
        print("ERRO: parser não extraiu nenhuma disciplina do roteiro.")
        sys.exit(1)

    disc = disciplinas_parseadas[0]
    cenas = disc.get("cenas", [])
    print(f"\nDisciplina: {disc['disciplina']}")
    print(f"Total de cenas: {len(cenas)}\n")

    tipos_ok = True
    for c in cenas:
        tipo = c.get("tipo", "N/A")
        fala_preview = (c.get("fala") or "")[:80].replace("\n", " ")
        status = "✅" if tipo in ("intro", "conteudo", "outro") else "⚠️ TIPO INVÁLIDO"
        print(f"  Cena {c['numero']:>2} [{tipo:>8}] {status}  → {fala_preview}...")
        if tipo not in ("intro", "conteudo", "outro"):
            tipos_ok = False

    if not tipos_ok:
        print("\n⚠️  Alguns tipos ficaram fora do esperado. Verifique o roteiro acima.")
    else:
        intros  = sum(1 for c in cenas if c.get("tipo") == "intro")
        outros  = sum(1 for c in cenas if c.get("tipo") == "outro")
        conteudo = sum(1 for c in cenas if c.get("tipo") == "conteudo")
        print(f"\n✅ Tipos OK — intro: {intros}  conteudo: {conteudo}  outro: {outros}")

    return roteiro, cenas


def modo_parser(caminho_md: str | None):
    _checar_env("OPENAI_API_KEY")
    md, disciplina = _ler_markdown(caminho_md)
    _gerar_e_parsear_roteiro(md, disciplina)
    print("\n✅ MODO PARSER concluído — nenhum áudio/vídeo gerado.")


def modo_tts(caminho_md: str | None):
    import tempfile

    from src.video_generator.slides_generator import gerar_slides
    from src.video_generator.compor_avatar_slides import _gerar_video_slide_com_audio
    from src.video_generator.audio_generator import gerar_audio_openai_tts

    _checar_env("OPENAI_API_KEY")
    md, disciplina = _ler_markdown(caminho_md)
    _, cenas = _gerar_e_parsear_roteiro(md, disciplina)

    cenas_conteudo = [c for c in cenas if c.get("tipo") == "conteudo"]
    if not cenas_conteudo:
        print("\n⚠️  Nenhuma cena de conteúdo encontrada para testar TTS+slides.")
        return

    pasta_temp = tempfile.mkdtemp(prefix="teste_tts_")
    pasta_slides = os.path.join(pasta_temp, "slides")
    print(f"\n{'='*60}")
    print(f"ETAPA 3 — Gerando {len(cenas_conteudo)} slide(s) de conteúdo...")
    print("="*60)

    cenas_para_slide = [
        {"fala": c["fala"], "visual": c.get("producao", ""), "texto": c.get("texto_na_tela", "")}
        for c in cenas_conteudo
    ]
    slides = gerar_slides(cenas_para_slide, pasta_slides, disciplina)
    print(f"✅ {len(slides)} slide(s) gerado(s) em: {pasta_slides}")

    openai_token = os.getenv("OPENAI_API_KEY")
    print(f"\n{'='*60}")
    print("ETAPA 4 — Gerando áudio TTS + combinando com slides...")
    print("="*60)

    videos_gerados = []
    for i, (cena, slide) in enumerate(zip(cenas_conteudo, slides), 1):
        fala = (cena.get("fala") or "").strip()
        if not fala:
            continue
        caminho_audio = os.path.join(pasta_temp, f"audio_{i:03d}.mp3")
        caminho_video = os.path.join(pasta_temp, f"cena_{i:03d}_conteudo.mp4")

        print(f"  Cena {i}/{len(cenas_conteudo)} — TTS ({len(fala)} chars)...")
        gerar_audio_openai_tts(fala, caminho_audio, openai_token)
        print(f"    ✅ áudio: {os.path.getsize(caminho_audio) // 1024} KB")

        _gerar_video_slide_com_audio(slide, caminho_audio, caminho_video)
        print(f"    ✅ vídeo: {os.path.getsize(caminho_video) // 1024} KB → {caminho_video}")
        videos_gerados.append(caminho_video)

    print(f"\n✅ MODO TTS concluído — {len(videos_gerados)} vídeo(s) de conteúdo gerado(s).")
    print(f"   Pasta de saída: {pasta_temp}")


def modo_completo(caminho_md: str | None, avatar: str = "fem"):
    import tempfile
    import shutil

    from src.video_generator.gerador_videos_direto import parsear_cenas_do_roteiro, gerar_roteiro
    from src.video_generator.video_generator import gerar_video_com_slides

    _checar_env("OPENAI_API_KEY", "HEYGEN_API_KEY")

    # Resolve avatar/voz igual ao test_video_um.py
    if avatar == "fem":
        _checar_env("AVATAR_FEM_ID", "VOZ_FEM_ID")
        avatar_id = os.getenv("AVATAR_FEM_ID")
        voice_id  = os.getenv("VOZ_FEM_ID")
        nome_avatar = "Marina"
    else:
        _checar_env("AVATAR_MASC_ID", "VOZ_MASC_ID")
        avatar_id = os.getenv("AVATAR_MASC_ID")
        voice_id  = os.getenv("VOZ_MASC_ID")
        nome_avatar = "Mário"

    os.environ["HEYGEN_AVATAR_ID"] = avatar_id
    os.environ["HEYGEN_VOICE_ID"]  = voice_id
    os.environ["AVATAR_NOME"]      = nome_avatar
    print(f"Avatar: {nome_avatar} ({avatar_id})")
    md, disciplina = _ler_markdown(caminho_md)

    openai_token = os.getenv("OPENAI_API_KEY")
    heygen_token = os.getenv("HEYGEN_API_KEY")

    os.environ["SLIDES_MD_CONTEXT"] = md[:8000]

    print(f"\n{'='*60}")
    print(f"ETAPA 1 — Gerando roteiro para: {disciplina}")
    print("="*60)
    roteiro = gerar_roteiro(md, disciplina, openai_token)
    disciplinas_parseadas = parsear_cenas_do_roteiro(roteiro)
    if not disciplinas_parseadas:
        print("ERRO: parser retornou vazio.")
        sys.exit(1)

    disc = disciplinas_parseadas[0]
    cenas = disc.get("cenas", [])
    print(f"✅ {len(cenas)} cena(s) parseada(s):")
    for c in cenas:
        print(f"   [{c.get('tipo', '?'):>8}] Cena {c['numero']} — {(c.get('fala') or '')[:60]}...")

    pasta_temp = tempfile.mkdtemp(prefix="teste_completo_")
    pasta_slides = os.path.join(pasta_temp, "slides")
    caminho_video = os.path.join(pasta_temp, "video_final.mp4")

    print(f"\n{'='*60}")
    print("ETAPA 2 — Gerando vídeo completo (intro HeyGen + slides TTS + outro HeyGen)...")
    print(f"Saída temporária: {pasta_temp}")
    print("="*60)

    gerar_video_com_slides(
        cenas=cenas,
        disciplina=disciplina,
        caminho_saida=caminho_video,
        pasta_slides=pasta_slides,
        heygen_token=heygen_token,
        openai_token=openai_token,
    )

    destino = os.path.join("data", "output", "videos", "teste_novo_pipeline", f"{disciplina.replace(' ', '_')}.mp4")
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    shutil.copy(caminho_video, destino)
    print(f"\n✅ MODO COMPLETO concluído!")
    print(f"   Vídeo final: {destino}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Testa o novo pipeline de vídeo (intro+tts+outro).")
    parser.add_argument(
        "--modo",
        choices=["parser", "tts", "completo"],
        default="parser",
        help="parser = só roteiro/tipos | tts = slides+TTS sem HeyGen | completo = pipeline inteiro",
    )
    parser.add_argument(
        "--md",
        default=None,
        help="Caminho para um arquivo .md de disciplina. Se omitido, usa exemplo embutido.",
    )
    parser.add_argument(
        "--avatar",
        choices=["fem", "masc"],
        default="fem",
        help="Avatar a usar no modo completo: fem (Marina, padrão) ou masc (Mário).",
    )
    args = parser.parse_args()

    if args.modo == "parser":
        modo_parser(args.md)
    elif args.modo == "tts":
        modo_tts(args.md)
    elif args.modo == "completo":
        modo_completo(args.md, args.avatar)

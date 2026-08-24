"""
Teste incremental do novo pipeline de vídeo (intro HeyGen + slides TTS + outro HeyGen).

MODOS DE TESTE (use --modo):

  parser   — Gera roteiro via OpenAI e valida se [TIPO] foi parseado corretamente.
             Não gera áudio nem vídeo. Rápido e barato (só OpenAI Chat).

  tts      — Além do parser, gera o áudio de cada cena de conteúdo com a voz do
             HeyGen (POST /v3/voices/speech — só áudio, sem avatar/vídeo) e
             combina com o slide PNG via ffmpeg, juntando tudo em 1 vídeo final.
             Usa HeyGen só para TTS (cobra bem menos que gerar avatar em vídeo).

  canto    — Cenas de conteúdo com slide + avatar HeyGen recortado (tronco pra
             cima) sobreposto no canto, via chroma key. Chama o HeyGen 1x por
             cena de conteúdo (mais caro que --modo tts, mas com avatar visível
             o tempo todo, não só no intro/outro).

  completo — Pipeline inteiro: intro HeyGen + slides TTS + outro HeyGen.
             Usa HeyGen com avatar em vídeo (cobra mais créditos). Demora ~5–10 min por aula.

Roteiros gerados são salvos em data/output/roteiros_teste/<disciplina>.txt e
reaproveitados automaticamente nas próximas execuções da mesma disciplina —
evita gastar chamada OpenAI de novo. Use --novo-roteiro pra forçar regeneração.

Uso:
    python test_novo_pipeline.py --modo parser
    python test_novo_pipeline.py --modo tts
    python test_novo_pipeline.py --modo tts --avatar masc
    python test_novo_pipeline.py --modo canto
    python test_novo_pipeline.py --modo completo
    python test_novo_pipeline.py --modo completo --md caminho/para/disciplina.md
    python test_novo_pipeline.py --modo tts --novo-roteiro
"""
import argparse
import os
import re
import sys
import textwrap

from dotenv import load_dotenv

load_dotenv()

# Onde os roteiros já gerados ficam salvos, pra não chamar a OpenAI de novo
# a cada teste — se já existe um roteiro pra disciplina, ele é reaproveitado.
PASTA_ROTEIROS = os.path.join("data", "output", "roteiros_teste")

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


def _slug(nome: str) -> str:
    slug = re.sub(r"[^\w.-]+", "_", nome.strip(), flags=re.UNICODE)
    return slug.strip("_") or "disciplina"


def _caminho_roteiro_cache(disciplina: str) -> str:
    return os.path.join(PASTA_ROTEIROS, f"{_slug(disciplina)}.txt")


def _gerar_e_parsear_roteiro(md: str, disciplina: str, forcar_novo: bool = False) -> tuple[str, list[dict]]:
    from src.video_generator.gerador_videos_direto import (
        gerar_roteiro,
        parsear_cenas_do_roteiro,
    )

    caminho_cache = _caminho_roteiro_cache(disciplina)

    print(f"\n{'='*60}")
    if os.path.isfile(caminho_cache) and not forcar_novo:
        print(f"ETAPA 1 — Roteiro já existe para '{disciplina}' — reaproveitando (sem chamar a OpenAI)")
        print(f"          {caminho_cache}")
        print("="*60)
        with open(caminho_cache, "r", encoding="utf-8") as f:
            roteiro = f.read()
    else:
        openai_token = os.getenv("OPENAI_API_KEY")
        print(f"ETAPA 1 — Gerando roteiro via OpenAI para: {disciplina}")
        print("="*60)
        roteiro = gerar_roteiro(md, disciplina, openai_token)
        os.makedirs(PASTA_ROTEIROS, exist_ok=True)
        with open(caminho_cache, "w", encoding="utf-8") as f:
            f.write(roteiro)
        print(f"          roteiro salvo em: {caminho_cache}")

    print("\n--- ROTEIRO ---")
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


def modo_parser(caminho_md: str | None, forcar_novo_roteiro: bool = False):
    _checar_env("OPENAI_API_KEY")
    md, disciplina = _ler_markdown(caminho_md)
    _gerar_e_parsear_roteiro(md, disciplina, forcar_novo_roteiro)
    print("\n✅ MODO PARSER concluído — nenhum áudio/vídeo gerado.")


def modo_tts(
    caminho_md: str | None,
    avatar: str = "fem",
    forcar_novo_roteiro: bool = False,
):
    import shutil
    import tempfile

    from src.video_generator.slides_generator import gerar_slides
    from src.video_generator.compor_avatar_slides import (
        _concatenar,
        _gerar_video_slide_com_audio,
    )
    from src.video_generator.audio_generator import gerar_audio_heygen_tts

    # Valida a chave da HeyGen.
    _checar_env("HEYGEN_API_KEY")
    heygen_token = os.getenv("HEYGEN_API_KEY")

    # Usa voz específica compatível com TTS Starfish.
    if avatar == "fem":
        _checar_env("TTS_VOZ_FEM_ID")
        voice_id = os.getenv("TTS_VOZ_FEM_ID")
    else:
        _checar_env("TTS_VOZ_MASC_ID")
        voice_id = os.getenv("TTS_VOZ_MASC_ID")

    md, disciplina = _ler_markdown(caminho_md)

    # Necessário pra gerar_slides() chamar a OpenAI e produzir conteúdo rico
    # (título/tópicos/imagem_prompt) em vez do fallback determinístico.
    os.environ["SLIDES_MD_CONTEXT"] = md[:8000]

    _, cenas = _gerar_e_parsear_roteiro(
        md,
        disciplina,
        forcar_novo_roteiro,
    )

    # Somente cenas de conteúdo viram slides com áudio.
    cenas_conteudo = [
        cena
        for cena in cenas
        if cena.get("tipo") == "conteudo"
    ]

    if not cenas_conteudo:
        print(
            "\n⚠️ Nenhuma cena de conteúdo encontrada "
            "para testar TTS + slides."
        )
        return

    pasta_temp = tempfile.mkdtemp(prefix="teste_tts_")
    pasta_slides = os.path.join(pasta_temp, "slides")

    print(f"\n{'=' * 60}")
    print(
        f"ETAPA 3 — Gerando "
        f"{len(cenas_conteudo)} slide(s) de conteúdo..."
    )
    print("=" * 60)

    cenas_para_slide = [
        {
            "fala": cena.get("fala", ""),
            "visual": cena.get("producao", ""),
            "texto": cena.get("texto_na_tela", ""),
            # Evita que a 1ª/última cena deste lote (só cenas de conteúdo,
            # sem intro/outro) sejam confundidas com abertura/encerramento
            # por posição — ver slides_generator._detectar_tipo.
            "tipo": "conteudo",
        }
        for cena in cenas_conteudo
    ]

    slides = gerar_slides(
        cenas_para_slide,
        pasta_slides,
        disciplina,
    )

    print(
        f"✅ {len(slides)} slide(s) gerado(s) em: "
        f"{pasta_slides}"
    )

    if len(slides) != len(cenas_conteudo):
        print(
            f"[AVISO] Foram gerados {len(slides)} slides "
            f"para {len(cenas_conteudo)} cenas."
        )

    print(f"\n{'=' * 60}")
    print(
        "ETAPA 4 — Gerando áudio "
        "(voz HeyGen, sem avatar) + combinando com slides..."
    )
    print("=" * 60)

    videos_gerados = []

    for indice, (cena, slide) in enumerate(
        zip(cenas_conteudo, slides),
        start=1,
    ):
        fala = (cena.get("fala") or "").strip()

        if not fala:
            print(
                f"  ⚠️ Cena {indice} sem fala — ignorando."
            )
            continue

        caminho_audio = os.path.join(
            pasta_temp,
            f"audio_{indice:03d}.mp3",
        )

        caminho_video = os.path.join(
            pasta_temp,
            f"cena_{indice:03d}_conteudo.mp4",
        )

        print(
            f"  Cena {indice}/{len(cenas_conteudo)} "
            f"— TTS HeyGen ({len(fala)} chars)..."
        )

        gerar_audio_heygen_tts(
            fala,
            caminho_audio,
            heygen_token,
            voice_id,
        )

        if not os.path.isfile(caminho_audio):
            raise RuntimeError(
                f"O áudio da cena {indice} não foi criado: "
                f"{caminho_audio}"
            )

        print(
            f"    ✅ áudio: "
            f"{os.path.getsize(caminho_audio) // 1024} KB"
        )

        _gerar_video_slide_com_audio(
            slide,
            caminho_audio,
            caminho_video,
        )

        if not os.path.isfile(caminho_video):
            raise RuntimeError(
                f"O vídeo da cena {indice} não foi criado: "
                f"{caminho_video}"
            )

        print(
            f"    ✅ vídeo: "
            f"{os.path.getsize(caminho_video) // 1024} KB "
            f"→ {caminho_video}"
        )

        videos_gerados.append(caminho_video)

    if not videos_gerados:
        print(
            "\n⚠️ Nenhum vídeo de conteúdo foi gerado."
        )
        return

    nome_arquivo = re.sub(
        r"[^\w.-]+",
        "_",
        disciplina.strip(),
        flags=re.UNICODE,
    ).strip("_")

    destino = os.path.join(
        "data",
        "output",
        "videos",
        "teste_novo_pipeline",
        f"{nome_arquivo}_tts.mp4",
    )

    os.makedirs(
        os.path.dirname(destino),
        exist_ok=True,
    )

    if len(videos_gerados) == 1:
        shutil.copy2(
            videos_gerados[0],
            destino,
        )
    else:
        print(f"\n{'=' * 60}")
        print(
            f"ETAPA 5 — Juntando "
            f"{len(videos_gerados)} cena(s)..."
        )
        print("=" * 60)

        caminho_final = os.path.join(
            pasta_temp,
            "video_final_tts.mp4",
        )

        _concatenar(
            videos_gerados,
            caminho_final,
            pasta_temp,
        )

        shutil.copy2(
            caminho_final,
            destino,
        )

    print(
        f"\n✅ MODO TTS concluído — "
        f"{len(videos_gerados)} cena(s) gerada(s)."
    )
    print(f"   Vídeo final: {destino}")


def modo_canto(caminho_md: str | None, avatar: str = "fem", forcar_novo_roteiro: bool = False):
    """
    Cenas de conteúdo com slide + avatar HeyGen recortado (tronco pra cima)
    sobreposto no canto do slide, via chroma key — a composição visual usada
    antes do pipeline atual (que só mostra avatar full-screen no intro/outro).

    Chama o HeyGen 1x por cena de conteúdo (gera o avatar sobre fundo verde),
    então compõe localmente com ffmpeg. Mais caro que --modo tts (que não usa
    HeyGen pra vídeo nenhum), mas o avatar fica visível durante todo o vídeo.
    """
    import shutil
    import tempfile

    from src.video_generator.compor_avatar_slides import (
        AVATAR_LARGURA_REL,
        AVATAR_MARGEM_PX,
        AVATAR_POSICAO,
        SAIDA_ALTURA,
        SAIDA_LARGURA,
        _baixar_video,
        _concatenar,
        _ffprobe_duracao,
        _gerar_video_do_slide,
        _zona_avatar_horizontal,
        compor_avatar_sobre_slide,
        gerar_avatar_chroma_key,
    )
    from src.video_generator.gerador_videos_direto import aguardar_video
    from src.video_generator.legendas import adicionar_legendas
    from src.video_generator.slides_generator import gerar_slides

    _checar_env("OPENAI_API_KEY", "HEYGEN_API_KEY")

    # Resolve avatar/voz igual ao modo completo (avatar em vídeo, não TTS puro).
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

    heygen_token = os.getenv("HEYGEN_API_KEY")
    print(f"Avatar: {nome_avatar} ({avatar_id})")

    md, disciplina = _ler_markdown(caminho_md)

    # Necessário pra gerar_slides() chamar a OpenAI e produzir conteúdo rico
    # (título/tópicos/imagem_prompt) em vez do fallback determinístico.
    os.environ["SLIDES_MD_CONTEXT"] = md[:8000]

    _, cenas = _gerar_e_parsear_roteiro(md, disciplina, forcar_novo_roteiro)

    cenas_conteudo = [c for c in cenas if c.get("tipo") == "conteudo"]
    if not cenas_conteudo:
        print("\n⚠️ Nenhuma cena de conteúdo encontrada para testar avatar no canto.")
        return

    pasta_temp = tempfile.mkdtemp(prefix="teste_canto_")
    pasta_slides = os.path.join(pasta_temp, "slides")

    print(f"\n{'=' * 60}")
    print(f"ETAPA 3 — Gerando {len(cenas_conteudo)} slide(s) de conteúdo...")
    print("=" * 60)

    cenas_para_slide = [
        {
            "fala": cena.get("fala", ""),
            "visual": cena.get("producao", ""),
            "texto": cena.get("texto_na_tela", ""),
            # Evita que a 1ª/última cena deste lote (só cenas de conteúdo,
            # sem intro/outro) sejam confundidas com abertura/encerramento
            # por posição — ver slides_generator._detectar_tipo.
            "tipo": "conteudo",
        }
        for cena in cenas_conteudo
    ]
    slides = gerar_slides(cenas_para_slide, pasta_slides, disciplina)
    print(f"✅ {len(slides)} slide(s) gerado(s) em: {pasta_slides}")

    print(f"\n{'=' * 60}")
    print("ETAPA 4 — Gerando avatar HeyGen (fundo verde) por cena e compondo no canto do slide...")
    print("=" * 60)

    videos_gerados = []
    falhas_cena = []
    for indice, (cena, slide) in enumerate(zip(cenas_conteudo, slides), start=1):
        fala = (cena.get("fala") or "").strip()
        if not fala:
            print(f"  ⚠️ Cena {indice} sem fala — ignorando.")
            continue

        # Cada cena é isolada num try/except: se UMA cena falhar (timeout,
        # erro de rede, HeyGen fora do ar), as cenas anteriores já geradas
        # nesta mesma aula NÃO são perdidas — seguimos pras próximas cenas
        # e no final juntamos o que deu certo, em vez de descartar tudo.
        # Além disso, cada cena tem direito a uma 2ª tentativa completa
        # (novo video_id do zero) antes de ser dada como falha definitiva —
        # timeouts no HeyGen costumam ser uma lentidão pontual da fila de
        # renderização, não um problema estrutural da cena em si.
        MAX_TENTATIVAS_CENA = 2
        video_id = None
        sucesso = False
        ultimo_erro = None
        for tentativa in range(1, MAX_TENTATIVAS_CENA + 1):
            try:
                n_palavras = len(fala.split())
                sufixo_tentativa = f" (tentativa {tentativa}/{MAX_TENTATIVAS_CENA})" if tentativa > 1 else ""
                print(f"  Cena {indice}/{len(cenas_conteudo)} — gerando avatar HeyGen "
                      f"(chroma key, {n_palavras} palavras de fala){sufixo_tentativa}...")
                video_id = gerar_avatar_chroma_key(
                    fala, f"{disciplina} — Conteúdo {indice}/{len(cenas_conteudo)}",
                    heygen_token, avatar_id, voice_id,
                )
                # Log imediato do video_id — se o polling abaixo estourar o
                # tempo limite, o render pode ter continuado no HeyGen mesmo
                # assim; com o ID em mãos dá pra checar depois via
                # /gerador-videos/heygen-status/{video_id} em vez de perder o
                # rastro do que foi gerado (e possivelmente cobrado).
                print(f"    video_id: {video_id}  (anote — permite checar status depois em caso de timeout)")

                # Timeout generoso: cenas de conteúdo mais longas (várias
                # dezenas de segundos de fala) podem legitimamente demorar mais
                # que os 5 min originais para renderizar no HeyGen.
                info = aguardar_video(video_id, heygen_token, max_min=20.0)
                if not info.get("video_url"):
                    raise RuntimeError("sem video_url na resposta")

                caminho_avatar = os.path.join(pasta_temp, f"avatar_{indice:03d}.mp4")
                _baixar_video(info["video_url"], caminho_avatar)
                print(f"    ✅ avatar baixado: {os.path.getsize(caminho_avatar) // 1024} KB")

                duracao = _ffprobe_duracao(caminho_avatar)
                caminho_slide_video = os.path.join(pasta_temp, f"slide_{indice:03d}.mp4")
                _gerar_video_do_slide(slide, duracao, caminho_slide_video)

                caminho_video = os.path.join(pasta_temp, f"cena_{indice:03d}_canto.mp4")
                compor_avatar_sobre_slide(caminho_avatar, caminho_slide_video, caminho_video)
                print(f"    ✅ cena composta: {caminho_video}")
                videos_gerados.append(caminho_video)
                sucesso = True
                break
            except Exception as e:
                ultimo_erro = e
                video_id_str = video_id or "desconhecido (falhou antes de gerar o ID)"
                if tentativa < MAX_TENTATIVAS_CENA:
                    print(f"    ⚠️ Cena {indice} falhou na tentativa {tentativa} ({e}) — "
                          f"video_id: {video_id_str}. Tentando de novo do zero...")
                    video_id = None
                else:
                    print(f"    ❌ Cena {indice} falhou após {MAX_TENTATIVAS_CENA} tentativas "
                          f"({e}) — video_id: {video_id_str}. Seguindo pras próximas cenas desta aula.")

        if not sucesso:
            video_id_str = video_id or "desconhecido (falhou antes de gerar o ID)"
            falhas_cena.append((indice, video_id_str, str(ultimo_erro)))
            continue

    if falhas_cena:
        print(f"\n⚠️ {len(falhas_cena)} cena(s) falharam nesta aula (video_id anotado acima pra cada uma):")
        for idx, vid, erro in falhas_cena:
            print(f"   - Cena {idx}: video_id={vid} | {erro}")

    if not videos_gerados:
        print("\n⚠️ Nenhum vídeo gerado — nada para juntar.")
        return

    nome_arquivo = re.sub(r"[^\w.-]+", "_", disciplina.strip(), flags=re.UNICODE).strip("_")
    destino = os.path.join("data", "output", "videos", "teste_novo_pipeline", f"{nome_arquivo}_canto.mp4")
    os.makedirs(os.path.dirname(destino), exist_ok=True)

    if len(videos_gerados) == 1:
        shutil.copy2(videos_gerados[0], destino)
    else:
        print(f"\n{'=' * 60}")
        print(f"ETAPA 5 — Juntando {len(videos_gerados)} cena(s) em um único vídeo...")
        print("=" * 60)
        caminho_final = os.path.join(pasta_temp, "video_final_canto.mp4")
        _concatenar(videos_gerados, caminho_final, pasta_temp)
        shutil.copy2(caminho_final, destino)

    print(f"\n{'=' * 60}")
    print("ETAPA 6 — Transcrevendo a fala (Whisper) e queimando legenda sincronizada...")
    print("=" * 60)

    openai_token = os.getenv("OPENAI_API_KEY")
    # Mesma zona reservada pro avatar na composição (compor_avatar_slides.py)
    # — a legenda evita esse lado pra nunca ficar por cima do avatar.
    lado_avatar, reservar_px = _zona_avatar_horizontal(AVATAR_POSICAO, AVATAR_LARGURA_REL, AVATAR_MARGEM_PX)
    try:
        caminho_legendado = os.path.join(pasta_temp, f"{nome_arquivo}_canto_legendado.mp4")
        adicionar_legendas(
            destino, caminho_legendado, openai_token, prompt_contexto=disciplina,
            evitar_lado=lado_avatar, reservar_px=reservar_px,
            largura_video=SAIDA_LARGURA, altura_video=SAIDA_ALTURA,
        )
        shutil.copy2(caminho_legendado, destino)
        print(f"   ✅ Legenda adicionada: {destino}")
    except Exception as e:
        print(f"   ⚠️ Falha ao gerar legenda ({e}) — mantendo vídeo sem legenda.")

    print(f"\n✅ MODO CANTO concluído — {len(videos_gerados)} cena(s) juntada(s) em 1 vídeo.")
    print(f"   Vídeo final: {destino}")


def modo_completo(caminho_md: str | None, avatar: str = "fem", forcar_novo_roteiro: bool = False):
    import tempfile
    import shutil

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

    _, cenas = _gerar_e_parsear_roteiro(md, disciplina, forcar_novo_roteiro)
    if not cenas:
        print("ERRO: parser retornou vazio.")
        sys.exit(1)

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
        choices=["parser", "tts", "canto", "completo"],
        default="parser",
        help=(
            "parser = só roteiro/tipos | tts = slides+TTS voz HeyGen sem avatar | "
            "canto = slides+avatar HeyGen no canto (chroma key) | completo = pipeline inteiro"
        ),
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
        help="Voz/avatar a usar nos modos tts e completo: fem (Marina, padrão) ou masc (Mário).",
    )
    parser.add_argument(
        "--novo-roteiro",
        action="store_true",
        help="Ignora o roteiro em cache (data/output/roteiros_teste/) e gera um novo via OpenAI.",
    )
    args = parser.parse_args()

    if args.modo == "parser":
        modo_parser(args.md, args.novo_roteiro)
    elif args.modo == "tts":
        modo_tts(args.md, args.avatar, args.novo_roteiro)
    elif args.modo == "canto":
        modo_canto(args.md, args.avatar, args.novo_roteiro)
    elif args.modo == "completo":
        modo_completo(args.md, args.avatar, args.novo_roteiro)

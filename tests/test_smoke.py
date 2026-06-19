"""
Smoke test offline (Fase 15): pipeline ponta-a-ponta sem API real.

Cobre: base_geral → embeddings → índice FAISS → markdown aluno + professor.
Todas as chamadas externas (LLM, modelo de embedding) são substituídas por fakes.
"""
import os
import tempfile
import numpy as np
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Fixtures e fakes reutilizáveis
# ---------------------------------------------------------------------------

_DIM = 8


def _fake_model():
    """Modelo de embedding fake: retorna vetores normalizados deterministicamente."""
    m = MagicMock()

    def encode(texts, normalize_embeddings=True, **kw):
        rng = np.random.default_rng(42)
        vecs = rng.random((len(texts), _DIM)).astype("float32")
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        return vecs / np.maximum(norms, 1e-9)

    m.encode.side_effect = encode
    return m


def _fake_client():
    """Client OpenAI fake que retorna strings curtas mas não-vazias."""
    c = MagicMock()
    c.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(
            content="Conteúdo gerado pelo fake LLM. " * 5
        ))]
    )
    return c


def _base_geral(area: str = "tecnico_enfermagem", n_disc: int = 2) -> list[dict]:
    registros = []
    for d in range(n_disc):
        for t in range(2):
            registros.append({
                "arquivo": f"curso_{area}",
                "curso": f"Curso {area}",
                "disciplina": f"Disciplina {d}",
                "ementa": f"Ementa da disciplina {d}",
                "aula": t + 1,
                "titulo_aula": f"Tópico {t} da disciplina {d}",
                "conteudo": f"Conteúdo do tópico {t}",
                "area": area,
                "texto_embedding": f"Disciplina {d} Tópico {t}",
            })
    return registros


# ---------------------------------------------------------------------------
# Smoke: embeddings + FAISS
# ---------------------------------------------------------------------------

def test_smoke_criar_indice_faiss():
    """Embeddings gerados por fake model são indexados sem erros."""
    from src.content_generation.embedding_model import gerar_embeddings
    from src.content_generation.faiss_index import criar_ou_carregar_index

    base = _base_geral(n_disc=2)
    model = _fake_model()

    with tempfile.TemporaryDirectory() as d:
        with patch("src.content_generation.embedding_model.SentenceTransformer",
                   return_value=model):
            embs = gerar_embeddings(model, base)

        assert embs.shape == (len(base), _DIM)

        caminho = os.path.join(d, "test.bin")
        index = criar_ou_carregar_index(caminho, embs, n_registros=len(base))
        assert index.ntotal == len(base)


# ---------------------------------------------------------------------------
# Smoke: buscar_chunks com base filtrada por área
# ---------------------------------------------------------------------------

def test_smoke_rag_nao_contamina_areas():
    """RAG retorna apenas chunks da área solicitada."""
    import faiss
    from src.content_generation.rag_pipeline import buscar_chunks

    base_enf = _base_geral("tecnico_enfermagem", n_disc=3)
    base_adm = _base_geral("tecnico_administracao", n_disc=3)
    base = base_enf + base_adm

    model = _fake_model()
    vecs = model.encode([r["texto_embedding"] for r in base])
    idx = faiss.IndexFlatIP(_DIM)
    idx.add(vecs)

    result = buscar_chunks(
        "higienização das mãos",
        model, idx, base,
        top_k=5,
        filtro_area="tecnico_enfermagem"
    )

    areas = {r["area"] for r in result}
    assert areas <= {"tecnico_enfermagem"}, f"Contaminação de área: {areas}"


# ---------------------------------------------------------------------------
# Smoke: gerar_markdowns ponta-a-ponta
# ---------------------------------------------------------------------------

def test_smoke_gerar_markdowns_cria_arquivos():
    """Geração completa de Markdown sem chamada real à API."""
    import faiss
    from src.content_generation.rag_pipeline import buscar_chunks
    from src.output_formatter.markdown_generator import gerar_markdowns

    base = _base_geral("tecnico_enfermagem", n_disc=1)
    model = _fake_model()
    client = _fake_client()

    vecs = model.encode([r["texto_embedding"] for r in base])
    idx = faiss.IndexFlatIP(_DIM)
    idx.add(vecs)

    def _gerar_topico_fake(client, disciplina, topico, contexto, profile):
        return f"Conteúdo: {topico}"

    def _gerar_questoes_fake(client, disciplina, topico, contexto, profile):
        return "Questão do aluno", "Gabarito do professor"

    def _gerar_documento_fake(client, disciplina, ementa, conteudo, contexto, profile):
        return "Documento gerado fake"

    with tempfile.TemporaryDirectory() as pasta:
        with (
            patch("src.output_formatter.markdown_generator.gerar_topico", _gerar_topico_fake),
            patch("src.output_formatter.markdown_generator.gerar_questoes_topico",
                  _gerar_questoes_fake),
        ):
            resultados = gerar_markdowns(
                base_geral=base,
                buscar_chunks=buscar_chunks,
                gerar_documento=_gerar_documento_fake,
                model=model,
                index=idx,
                gemini=client,
                pasta_saida=pasta,
                sleep_fn=lambda s: None,
            )

        erros = [r for r in resultados if r.erro]
        assert len(erros) == 0, f"Erros inesperados: {[e.erro for e in erros]}"

        for r in resultados:
            if not r.pulada:
                assert os.path.isfile(r.caminho_aluno), f"Arquivo aluno ausente: {r.caminho_aluno}"
                assert os.path.isfile(r.caminho_professor), f"Arquivo professor ausente: {r.caminho_professor}"
                assert os.path.getsize(r.caminho_aluno) > 100
                assert os.path.getsize(r.caminho_professor) > 100


def test_smoke_professor_contem_gabarito():
    """Arquivo do professor deve conter gabarito; aluno não."""
    import faiss
    from src.content_generation.rag_pipeline import buscar_chunks
    from src.output_formatter.markdown_generator import gerar_markdowns

    base = _base_geral("tecnico_enfermagem", n_disc=1)
    model = _fake_model()
    client = _fake_client()

    vecs = model.encode([r["texto_embedding"] for r in base])
    idx = faiss.IndexFlatIP(_DIM)
    idx.add(vecs)

    with tempfile.TemporaryDirectory() as pasta:
        with (
            patch("src.output_formatter.markdown_generator.gerar_topico",
                  lambda *a, **kw: "conteúdo"),
            patch("src.output_formatter.markdown_generator.gerar_questoes_topico",
                  lambda *a, **kw: ("pergunta", "GABARITO_SECRETO_PROFESSOR")),
        ):
            resultados = gerar_markdowns(
                base_geral=base,
                buscar_chunks=buscar_chunks,
                gerar_documento=lambda *a, **kw: "doc fake",
                model=model,
                index=idx,
                gemini=client,
                pasta_saida=pasta,
                sleep_fn=lambda s: None,
            )

        r = next(res for res in resultados if not res.pulada)
        with open(r.caminho_professor, "r", encoding="utf-8") as f:
            texto_prof = f.read()
        with open(r.caminho_aluno, "r", encoding="utf-8") as f:
            texto_aluno = f.read()

    assert "GABARITO_SECRETO_PROFESSOR" in texto_prof
    assert "GABARITO_SECRETO_PROFESSOR" not in texto_aluno


# ---------------------------------------------------------------------------
# Smoke: resume mode
# ---------------------------------------------------------------------------

def test_smoke_resume_pula_geracao_ja_concluida():
    """Segunda execução sem --force não regenera disciplinas completas."""
    import faiss
    from src.content_generation.rag_pipeline import buscar_chunks
    from src.output_formatter.markdown_generator import gerar_markdowns

    base = _base_geral("tecnico_enfermagem", n_disc=1)
    model = _fake_model()
    client = _fake_client()
    vecs = model.encode([r["texto_embedding"] for r in base])
    idx = faiss.IndexFlatIP(_DIM)
    idx.add(vecs)

    def _gerar_topico_fake(client, disciplina, topico, contexto, profile):
        return "conteúdo"

    def _gerar_questoes_fake(client, disciplina, topico, contexto, profile):
        return "qa", "qp"

    with tempfile.TemporaryDirectory() as pasta:
        run_args = dict(
            base_geral=base,
            buscar_chunks=buscar_chunks,
            gerar_documento=lambda *a, **kw: "doc",
            model=model,
            index=idx,
            gemini=client,
            pasta_saida=pasta,
            sleep_fn=lambda s: None,
        )

        with (
            patch("src.output_formatter.markdown_generator.gerar_topico", _gerar_topico_fake),
            patch("src.output_formatter.markdown_generator.gerar_questoes_topico", _gerar_questoes_fake),
        ):
            gerar_markdowns(**run_args)

        contador = [0]
        def conta_topico(*a, **kw):
            contador[0] += 1
            return "ok"

        with (
            patch("src.output_formatter.markdown_generator.gerar_topico", conta_topico),
            patch("src.output_formatter.markdown_generator.gerar_questoes_topico", _gerar_questoes_fake),
        ):
            resultados = gerar_markdowns(**{**run_args, "force": False})

    assert contador[0] == 0, "Resume não deveria chamar gerar_topico no segundo run"
    assert all(r.pulada for r in resultados)

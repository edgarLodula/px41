"""Testes da função main() e _parse_args()."""
import os
import tempfile
from unittest.mock import patch, MagicMock

from main import _parse_args, main


# ---------------------------------------------------------------------------
# _parse_args
# ---------------------------------------------------------------------------

def test_defaults():
    args = _parse_args([])
    assert args.force is False
    assert args.rebuild_index is False
    assert args.resume is True
    assert args.limit == 0
    assert args.validate_only is False
    assert args.skip_pdf is False
    assert args.log_level == "INFO"


def test_force_flag():
    args = _parse_args(["--force"])
    assert args.force is True


def test_limit_flag():
    args = _parse_args(["--limit", "3"])
    assert args.limit == 3


def test_validate_only_flag():
    args = _parse_args(["--validate-only"])
    assert args.validate_only is True


def test_log_level_flag():
    args = _parse_args(["--log-level", "DEBUG"])
    assert args.log_level == "DEBUG"


def test_skip_pdf_flag():
    args = _parse_args(["--skip-pdf"])
    assert args.skip_pdf is True


# ---------------------------------------------------------------------------
# --validate-only não inicializa client nem lê PDFs
# ---------------------------------------------------------------------------

def test_validate_only_nao_chama_openai():
    """--validate-only deve retornar sem criar um client OpenAI."""
    chamadas = []

    def configurar_spy(*a, **kw):
        chamadas.append(1)
        return MagicMock()

    with patch("main.configurar_openai", configurar_spy):
        resultado = main(["--validate-only"])

    assert len(chamadas) == 0, "--validate-only não deve chamar configurar_openai"
    assert resultado in (0, 1)  # pode falhar se dependências ausentes, mas não por API


def test_validate_only_retorna_inteiro():
    resultado = main(["--validate-only"])
    assert isinstance(resultado, int)


# ---------------------------------------------------------------------------
# Sem PDFs → retorna código != 0
# ---------------------------------------------------------------------------

def test_sem_pasta_input_retorna_1():
    """Se PASTA_PDFS não existir, main deve retornar 1."""
    with tempfile.TemporaryDirectory() as d:
        import main as m_module
        original = m_module.PASTA_PDFS
        m_module.PASTA_PDFS = os.path.join(d, "inexistente")
        try:
            with patch.dict(os.environ, {"OPENAI_API_KEY": "fake-key"}):
                with patch("main.configurar_openai", return_value=MagicMock()):
                    resultado = main([])
        finally:
            m_module.PASTA_PDFS = original

    assert resultado == 1


def test_pasta_input_vazia_retorna_1():
    """Pasta de PDFs vazia → main retorna 1."""
    with tempfile.TemporaryDirectory() as d:
        import main as m_module
        original = m_module.PASTA_PDFS
        m_module.PASTA_PDFS = d
        try:
            with patch.dict(os.environ, {"OPENAI_API_KEY": "fake-key"}):
                with patch("main.configurar_openai", return_value=MagicMock()):
                    resultado = main([])
        finally:
            m_module.PASTA_PDFS = original

    assert resultado == 1


# ---------------------------------------------------------------------------
# Falha crítica nos embeddings → retorna 1
# ---------------------------------------------------------------------------

def test_falha_em_embeddings_retorna_1():
    """Se carregar_modelo falhar, main deve retornar 1 (não propagar exceção)."""
    with tempfile.TemporaryDirectory() as d:
        pasta_pdf = os.path.join(d, "input")
        os.makedirs(pasta_pdf)
        # Cria um PDF falso (só para satisfazer a detecção de arquivos)
        with open(os.path.join(pasta_pdf, "teste.pdf"), "wb") as f:
            f.write(b"%PDF-1.4 fake content")

        import main as m_module
        original_pdfs = m_module.PASTA_PDFS
        original_csv = m_module.PASTA_CSV
        original_json = m_module.PASTA_JSON
        original_index = m_module.PASTA_INDEX
        m_module.PASTA_PDFS = pasta_pdf
        m_module.PASTA_CSV = os.path.join(d, "csv")
        m_module.PASTA_JSON = os.path.join(d, "json")
        m_module.PASTA_INDEX = os.path.join(d, "faiss")
        try:
            with patch.dict(os.environ, {"OPENAI_API_KEY": "fake-key"}):
                with patch("main.configurar_openai", return_value=MagicMock()):
                    with patch("main._resolver_area_pdf", return_value=("tecnico_enfermagem", "mock")):
                        with patch("main.extrair_pdf_para_csv"):
                            with patch("main.extrair_base_csv", return_value=[
                                {"arquivo": "teste", "disciplina": "D1", "ementa": "e",
                                 "aula": 1, "titulo_aula": "T1", "conteudo": "c",
                                 "texto_embedding": "D1"}
                            ]):
                                with patch("main.carregar_modelo",
                                           side_effect=RuntimeError("modelo indisponível")):
                                    resultado = main([])
        finally:
            m_module.PASTA_PDFS = original_pdfs
            m_module.PASTA_CSV = original_csv
            m_module.PASTA_JSON = original_json
            m_module.PASTA_INDEX = original_index

    assert resultado == 1


# ---------------------------------------------------------------------------
# --limit restringe disciplinas processadas
# ---------------------------------------------------------------------------

def test_limit_restringe_disciplinas():
    """--limit 1 deve limitar o número de disciplinas na base."""
    from main import main as run_main
    import main as m_module

    registros_expandidos = [
        {"arquivo": "a", "disciplina": f"D{i}", "ementa": "e",
         "aula": 1, "titulo_aula": f"T{i}", "conteudo": "c",
         "texto_embedding": f"D{i}", "curso": "Curso"}
        for i in range(10)
    ]

    base_limitada_ref = []

    def verificar_embeddings(model, base):
        base_limitada_ref.extend(base)
        raise RuntimeError("parar aqui")

    with tempfile.TemporaryDirectory() as d:
        pasta_pdf = os.path.join(d, "input")
        os.makedirs(pasta_pdf)
        with open(os.path.join(pasta_pdf, "teste.pdf"), "wb") as f:
            f.write(b"%PDF-1.4 fake")

        original_pdfs = m_module.PASTA_PDFS
        original_csv = m_module.PASTA_CSV
        original_json = m_module.PASTA_JSON
        original_index = m_module.PASTA_INDEX
        m_module.PASTA_PDFS = pasta_pdf
        m_module.PASTA_CSV = os.path.join(d, "csv")
        m_module.PASTA_JSON = os.path.join(d, "json")
        m_module.PASTA_INDEX = os.path.join(d, "faiss")
        try:
            with patch.dict(os.environ, {"OPENAI_API_KEY": "fake-key"}):
                with patch("main.configurar_openai", return_value=MagicMock()):
                    with patch("main._resolver_area_pdf",
                               return_value=("tecnico_enfermagem", "mock")):
                        with patch("main.extrair_pdf_para_csv"):
                            with patch("main.extrair_base_csv",
                                       return_value=registros_expandidos):
                                with patch("main.gerar_embeddings", verificar_embeddings):
                                    with patch("main.carregar_modelo", return_value=MagicMock()):
                                        run_main(["--limit", "1"])
        finally:
            m_module.PASTA_PDFS = original_pdfs
            m_module.PASTA_CSV = original_csv
            m_module.PASTA_JSON = original_json
            m_module.PASTA_INDEX = original_index

    disciplinas_na_base = {r["disciplina"] for r in base_limitada_ref}
    assert len(disciplinas_na_base) <= 1, (
        f"--limit 1 deveria limitar a 1 disciplina, obteve: {disciplinas_na_base}"
    )

"""Testa que todos os módulos principais importam sem erro."""
import importlib
import pytest


MODULOS = [
    "src.content_generation.area_profiles",
    "src.content_generation.area_detector",
    "src.content_generation.generator",
    "src.output_formatter.markdown_generator",
    "src.pdf_csv.pdf_csv",
    "src.syllabus_extractor.csv_processor",
    "src.content_generation.rag_pipeline",
    "src.content_generation.faiss_index",
    "src.content_generation.embedding_model",
]


@pytest.mark.parametrize("modulo", MODULOS)
def test_importa_modulo(modulo):
    mod = importlib.import_module(modulo)
    assert mod is not None


def test_importa_main():
    import main
    assert hasattr(main, "main")

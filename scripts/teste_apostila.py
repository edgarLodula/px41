import sys
sys.path.insert(0, "c:/Users/lizan/OneDrive/Documentos/Atria_Corp/SanMarino/px41")
from src.workbooks_generator.workbooks_generator import gerar_apostilas_por_curso
try:
    gerar_apostilas_por_curso()
    print("Apostila gerada com sucesso!")
except Exception as e:
    print(f"ERRO: {type(e).__name__}: {e}")

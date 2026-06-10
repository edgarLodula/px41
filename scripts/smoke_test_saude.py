"""Smoke test: gera UM tópico e valida que não vazou vocabulário industrial."""
import os, sys
os.environ["AREA_FORMACAO"] = "saude"

# garante que o projeto está no path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from src.content_generation.generator import configurar_openai, gerar_topico

client = configurar_openai()
texto = gerar_topico(
    client,
    disciplina="Fundamentos da Enfermagem II",
    topico="Prevenção de Lesão por Pressão (LPP)",
    contexto="Cuidados com paciente acamado em ambiente hospitalar",
)

print(texto[:3000])
print("\n" + "=" * 60)

PROIBIDAS = [
    "técnico industrial", "chão de fábrica", "fábrica", "linha de produção",
    "motor elétrico", "CLP", "NR-10", "NR-12", "NR-35",
    "CREA", "CFT", "LOTO", "TIA Portal", "Indústria 4.0",
    "úlcera de pressão", "úlcera por pressão", "escara",
]
OBRIGATORIAS = ["LPP", "técnico em enfermagem", "paciente"]

falhas = []
for termo in PROIBIDAS:
    if termo.lower() in texto.lower():
        falhas.append(f"  PROIBIDO encontrado: '{termo}'")
for termo in OBRIGATORIAS:
    if termo.lower() not in texto.lower():
        falhas.append(f"  OBRIGATORIO ausente: '{termo}'")

if falhas:
    print("FALHA NO SMOKE TEST:")
    print("\n".join(falhas))
    sys.exit(1)
else:
    print("Smoke test passou. Pode rodar o pipeline completo.")

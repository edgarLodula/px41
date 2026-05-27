import sys
sys.path.insert(0, "c:/Users/lizan/OneDrive/Documentos/Atria_Corp/SanMarino/px41")
import glob, os

# Localiza o PDF
caminhos = glob.glob("C:/Users/lizan/Downloads/*.pdf")
print("PDFs encontrados:")
for i, c in enumerate(caminhos):
    print(f"  [{i}] {os.path.basename(c)}")

escolha = input("Qual? [numero]: ").strip()
caminho = caminhos[int(escolha)]

from src.video_generator.gerador_videos_direto import _extrair_por_texto, _extrair_tabelas

print(f"\nTestando tabelas...")
tabelas = _extrair_tabelas(caminho)
print(f"  {len(tabelas)} disciplinas via tabela")

print(f"\nTestando texto...")
texto = _extrair_por_texto(caminho)
print(f"  {len(texto)} disciplinas via texto\n")

for i, d in enumerate(texto[:3]):
    print(f"  [{i+1}] {d['disciplina']}")
    print(f"       Ementa ({len(d['ementa'])} chars): {d['ementa'][:80]}...")
    print(f"       Conteudo ({len(d['conteudo'])} chars): {d['conteudo'][:80]}...")
    print()

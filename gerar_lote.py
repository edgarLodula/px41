"""
Gera vídeos em lote (modo canto) para todos os .md de uma pasta.

Processa um arquivo por vez chamando test_novo_pipeline.modo_canto — se algum
falhar (erro de API, roteiro inválido, etc.), registra o erro e segue pro
próximo em vez de travar o lote inteiro. No final imprime um resumo e salva
esse resumo em disco.

Uso:
    python gerar_lote.py
    python gerar_lote.py --pasta data/input --avatar masc
    python gerar_lote.py --pasta data/input --novo-roteiro
"""
import argparse
import glob
import os
import time
import traceback

from test_novo_pipeline import modo_canto

PASTA_RESUMO = os.path.join("data", "output", "videos", "teste_novo_pipeline")


def main():
    parser = argparse.ArgumentParser(
        description="Gera vídeos em lote (modo canto) a partir de vários arquivos .md."
    )
    parser.add_argument(
        "--pasta", default="data/input",
        help="Pasta com os arquivos .md a processar (padrão: data/input).",
    )
    parser.add_argument(
        "--avatar", choices=["fem", "masc"], default="fem",
        help="Avatar/voz pra todos os vídeos do lote: fem (Marina, padrão) ou masc (Mário).",
    )
    parser.add_argument(
        "--novo-roteiro", action="store_true",
        help="Ignora o roteiro em cache de cada disciplina e gera um novo via OpenAI.",
    )
    args = parser.parse_args()

    arquivos_md = sorted(glob.glob(os.path.join(args.pasta, "*.md")))
    if not arquivos_md:
        print(f"Nenhum .md encontrado em: {args.pasta}")
        return

    print(f"Encontrados {len(arquivos_md)} arquivo(s) .md em '{args.pasta}':")
    for a in arquivos_md:
        print(f"   - {os.path.basename(a)}")
    print(f"Avatar: {args.avatar}")

    sucesso: list[str] = []
    falha:   list[tuple[str, str]] = []
    inicio_lote = time.time()

    for i, caminho_md in enumerate(arquivos_md, 1):
        nome = os.path.basename(caminho_md)
        print(f"\n{'#' * 70}")
        print(f"# VIDEO {i}/{len(arquivos_md)} -- {nome}")
        print(f"{'#' * 70}")
        inicio = time.time()
        try:
            modo_canto(caminho_md, args.avatar, args.novo_roteiro)
            sucesso.append(nome)
        except Exception as e:
            falha.append((nome, str(e)))
            print(f"\n[FALHOU] {nome}: {e}")
            traceback.print_exc()
        print(f"   (levou {(time.time() - inicio) / 60:.1f} min)")

    duracao_total = (time.time() - inicio_lote) / 60

    linhas_resumo = [
        "=" * 70,
        f"LOTE CONCLUIDO em {duracao_total:.1f} min",
        f"Sucesso: {len(sucesso)}/{len(arquivos_md)}",
    ]
    linhas_resumo += [f"   OK  - {s}" for s in sucesso]
    if falha:
        linhas_resumo.append(f"Falhas: {len(falha)}/{len(arquivos_md)}")
        linhas_resumo += [f"   ERRO - {n}: {erro}" for n, erro in falha]
    linhas_resumo.append("=" * 70)

    resumo = "\n".join(linhas_resumo)
    print("\n" + resumo)

    os.makedirs(PASTA_RESUMO, exist_ok=True)
    caminho_resumo = os.path.join(PASTA_RESUMO, "lote_resumo.txt")
    with open(caminho_resumo, "w", encoding="utf-8") as f:
        f.write(resumo + "\n")
    print(f"\nResumo salvo em: {caminho_resumo}")


if __name__ == "__main__":
    main()

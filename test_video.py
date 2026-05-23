"""
test_video.py
Executa o fluxo completo de geração de vídeo usando um roteiro já existente no projeto.

Uso:
    python test_video.py                          # usa o primeiro roteiro encontrado
    python test_video.py caminho/para/roteiro.txt # usa o roteiro especificado
"""

import os
import sys
import glob
from pathlib import Path
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Configuração de paths — tudo relativo à raiz do projeto (onde este script está)
# ---------------------------------------------------------------------------
ROOT = Path(__file__).parent
PASTA_VIDEOS = ROOT / "data" / "output" / "videos"

load_dotenv(ROOT / ".env")

# ---------------------------------------------------------------------------
# Import da função de geração de vídeo já implementada no projeto
# ---------------------------------------------------------------------------
sys.path.insert(0, str(ROOT))
from src.video_generator.video_generator import gerar_video


# ---------------------------------------------------------------------------
# Localiza roteiros disponíveis
# ---------------------------------------------------------------------------
def localizar_roteiros() -> list[Path]:
    padrao = str(PASTA_VIDEOS / "**" / "roteiro" / "*.txt")
    return sorted(Path(p) for p in glob.glob(padrao, recursive=True))


def selecionar_roteiro(argumento: str | None) -> Path:
    if argumento:
        caminho = Path(argumento)
        if not caminho.is_absolute():
            caminho = ROOT / caminho
        if not caminho.exists():
            print(f"❌ Roteiro não encontrado: {caminho}")
            sys.exit(1)
        return caminho

    roteiros = localizar_roteiros()
    if not roteiros:
        print(f"❌ Nenhum roteiro .txt encontrado em: {PASTA_VIDEOS}")
        print("   Execute o pipeline principal primeiro para gerar roteiros.")
        sys.exit(1)

    print(f"📋 {len(roteiros)} roteiro(s) encontrado(s):")
    for i, r in enumerate(roteiros):
        disciplina = r.stem.replace("_", " ")
        curso      = r.parents[2].name.replace("_", " ")
        print(f"   [{i}] {curso} → {disciplina}")

    return roteiros[0]


def main():
    argumento = sys.argv[1] if len(sys.argv) > 1 else None

    print("\n" + "=" * 60)
    print("   TESTE DE GERAÇÃO DE VÍDEO — San Marino Booklet Creator")
    print("=" * 60)

    caminho_roteiro  = selecionar_roteiro(argumento)
    disciplina       = caminho_roteiro.stem.replace("_", " ")
    pasta_video      = ROOT / "data" / "videos" / caminho_roteiro.stem
    pasta_video.mkdir(parents=True, exist_ok=True)
    caminho_video    = pasta_video / "video.mp4"

    print(f"\n📄 Roteiro selecionado : {caminho_roteiro}")
    print(f"   Disciplina          : {disciplina}")
    print(f"   Saída do vídeo      : {caminho_video}")

   
    try:
        roteiro = caminho_roteiro.read_text(encoding="utf-8")
    except Exception as e:
        print(f"\n❌ Erro ao ler roteiro: {e}")
        sys.exit(1)

    print(f"\n📝 Roteiro lido ({len(roteiro)} caracteres, "
          f"{len(roteiro.splitlines())} linhas)")
    print(f"   Prévia: {roteiro[:120].strip()!r}...")

    
    print("\n🔑 Verificando variáveis de ambiente...")
    vars_obrigatorias = {
        "HEYGEN_API_KEY":   os.getenv("HEYGEN_API_KEY"),
        "HEYGEN_AVATAR_ID": os.getenv("HEYGEN_AVATAR_ID"),
        "HEYGEN_VOICE_ID":  os.getenv("HEYGEN_VOICE_ID"),
    }
    faltando = [k for k, v in vars_obrigatorias.items() if not v]
    if faltando:
        print(f"   ❌ Variáveis ausentes no .env: {', '.join(faltando)}")
        sys.exit(1)
    for k in vars_obrigatorias:
        print(f"   ✅ {k} configurado")

    # 4. Gera o vídeo
    print("\n🎬 Iniciando geração de vídeo via HeyGen...")
    print("   (Isso pode levar alguns minutos — polling a cada 10s por até 5min)")

    try:
        gerar_video(roteiro, str(caminho_video))
    except Exception as e:
        print(f"\n❌ Erro na geração de vídeo:")
        print(f"   {e}")
        sys.exit(1)

    # 5. Resultado
    print("\n" + "=" * 60)
    if caminho_video.exists():
        tamanho_mb = caminho_video.stat().st_size / (1024 * 1024)
        print(f"✅ Vídeo gerado com sucesso!")
        print(f"   Arquivo : {caminho_video}")
        print(f"   Tamanho : {tamanho_mb:.1f} MB")
    else:
        print("⚠️  gerar_video() concluiu sem erro, mas o arquivo não foi encontrado.")
        print(f"   Caminho esperado: {caminho_video}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()

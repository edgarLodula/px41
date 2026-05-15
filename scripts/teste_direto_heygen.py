"""
Teste direto do HeyGen — sem Gemini, sem pipeline completo.
Envia um roteiro pre-escrito diretamente para a API e aguarda o resultado.

Execute com: python scripts/teste_direto_heygen.py
"""

import os
import sys
import uuid
import time
import requests
from dotenv import load_dotenv

load_dotenv("c:/Users/lizan/OneDrive/Documentos/Atria_Corp/SanMarino/px41/.env")

# ─── Roteiros disponíveis (de scripts/roteiros_teste_heygen.md) ───────────────

ROTEIROS = {
    "1": {
        "nome":      "Curto e direto (~13s)",
        "disciplina": "Apresentacao San Marino",
        "texto": (
            "Ola! Seja bem-vindo a Escola Tecnica San Marino. "
            "Hoje comeca sua jornada rumo a uma carreira solida na area da saude. "
            "Estamos aqui para transformar seu futuro. Vamos comecar!"
        ),
    },
    "2": {
        "nome":      "Medio, tom acolhedor (~27s)",
        "disciplina": "Anatomia e Fisiologia",
        "texto": (
            "Ola, futuro profissional da saude! Meu nome e Marina, professora da Escola Tecnica San Marino, "
            "e estou muito feliz em receber voce na disciplina de Anatomia e Fisiologia. "
            "Aqui voce vai descobrir como o corpo humano funciona por dentro, cada osso, musculo e orgao tem uma historia fascinante. "
            "E entender essa historia e o primeiro passo para cuidar melhor de quem voce vai atender. Boas-vindas ao comeco de tudo!"
        ),
    },
    "3": {
        "nome":      "Energetico e motivacional (~33s)",
        "disciplina": "Administracao em Saude",
        "texto": (
            "Voce escolheu uma das areas mais importantes do mundo: a saude! "
            "E a Escola San Marino vai te preparar para fazer parte dela com excelencia. "
            "Nesta disciplina de Administracao em Saude, voce vai aprender a organizar, planejar e liderar equipes em ambientes hospitalares e clinicas. "
            "Gestao salva vidas, e voce vai entender exatamente como isso funciona na pratica. "
            "Eu acredito no seu potencial. Vamos juntos!"
        ),
    },
}

# ─── Configuração ─────────────────────────────────────────────────────────────

TOKEN      = os.getenv("HEYGEN_API_KEY")
AVATAR_ID  = os.getenv("HEYGEN_AVATAR_ID")
VOICE_ID   = os.getenv("HEYGEN_VOICE_ID")
BG_ASSET   = os.getenv("HEYGEN_BG_ASSET_ID", "")
BG_COLOR   = "#1a2744"
PASTA_SAIDA = "data/output/videos_teste"

os.makedirs(PASTA_SAIDA, exist_ok=True)

# ─── Validações ───────────────────────────────────────────────────────────────

def validar():
    erros = []
    if not TOKEN:
        erros.append("HEYGEN_API_KEY nao encontrada no .env")
    if not AVATAR_ID:
        erros.append("HEYGEN_AVATAR_ID nao encontrado no .env")
    if not VOICE_ID:
        erros.append("HEYGEN_VOICE_ID nao encontrado no .env")
    return erros

erros = validar()
if erros:
    for e in erros:
        print(f"ERRO: {e}")
    sys.exit(1)

# ─── Seleção do roteiro ───────────────────────────────────────────────────────

print("\n" + "=" * 55)
print("TESTE DIRETO HEYGEN")
print("=" * 55)
print("\nRoteiros disponíveis:")
for k, r in ROTEIROS.items():
    palavras = len(r["texto"].split())
    print(f"  [{k}] {r['nome']}  ({palavras} palavras)")

escolha = input("\nEscolha o roteiro [1/2/3] (Enter = 1): ").strip() or "1"
if escolha not in ROTEIROS:
    print(f"Opcao invalida. Usando roteiro 1.")
    escolha = "1"

roteiro = ROTEIROS[escolha]
palavras = len(roteiro["texto"].split())

print(f"\nRoteiro escolhido : {roteiro['nome']}")
print(f"Disciplina        : {roteiro['disciplina']}")
print(f"Palavras          : {palavras}")
print(f"Avatar            : {AVATAR_ID}")
print(f"Voz               : {VOICE_ID}")
print(f"Background        : {'asset ' + BG_ASSET[:12] + '...' if BG_ASSET else 'cor ' + BG_COLOR}")

confirmar = input("\nEnviar para HeyGen? [s/N]: ").strip().lower()
if confirmar not in ("s", "sim", "y", "yes"):
    print("Cancelado.")
    sys.exit(0)

modo_minimo = input("Usar payload MINIMO para diagnostico (sem bg/caption/motion)? [s/N]: ").strip().lower()
usar_minimo = modo_minimo in ("s", "sim", "y", "yes")

# ─── Envio para HeyGen ────────────────────────────────────────────────────────

print("\nEnviando para HeyGen...")

headers = {
    "X-Api-Key":       TOKEN,
    "Content-Type":    "application/json",
    "Idempotency-Key": str(uuid.uuid4()),
}

payload = {
    "type":           "avatar",
    "avatar_id":      AVATAR_ID,
    "voice_id":       VOICE_ID,
    "script":         roteiro["texto"],
    "title":          f"[TESTE] {roteiro['disciplina']}",
    "aspect_ratio":   "16:9",
}

if not usar_minimo:
    payload.update({
        "fit":            "contain",
        "engine":         {"type": "avatar_iv"},
        "voice_settings": {"speed": 1.0},
        "expressiveness": "medium",
        "motion_prompt":  "calm, professional, occasional hand gestures while teaching",
        "background": (
            {"type": "image", "asset_id": BG_ASSET}
            if BG_ASSET
            else {"type": "color", "value": BG_COLOR}
        ),
        "caption": {"style": "default"},
    })

print(f"\nModo: {'MINIMO (diagnostico)' if usar_minimo else 'COMPLETO'}")

resp = requests.post(
    "https://api.heygen.com/v3/videos",
    headers=headers,
    json=payload,
    timeout=30,
)

if not resp.ok:
    print(f"\nERRO HTTP {resp.status_code}:")
    print(resp.text[:400])
    sys.exit(1)

data     = resp.json().get("data", {})
video_id = data.get("video_id")

if not video_id:
    print(f"\nHeyGen nao retornou video_id: {resp.text[:300]}")
    sys.exit(1)

print(f"video_id: {video_id}")
print(f"status inicial: {data.get('status')}")

# ─── Polling ──────────────────────────────────────────────────────────────────

print("\nAguardando renderizacao (polling a cada 10s)...")
inicio = time.time()

for tentativa in range(60):
    time.sleep(10)
    decorrido = int(time.time() - inicio)

    status_resp = requests.get(
        f"https://api.heygen.com/v3/videos/{video_id}",
        headers={"X-Api-Key": TOKEN},
        timeout=15,
    )

    if not status_resp.ok:
        print(f"  Erro ao consultar status: {status_resp.status_code}")
        continue

    info   = status_resp.json().get("data", {})
    status = info.get("status", "unknown")
    print(f"  [{decorrido:3d}s] status: {status}")

    if status == "completed":
        video_url = info.get("video_url")
        duracao   = info.get("duration", 0)
        print(f"\nVideo pronto!")
        print(f"  Duracao  : {duracao:.1f}s")
        print(f"  URL      : {video_url}")

        # Download
        nome_arquivo = f"teste_roteiro_{escolha}_{video_id[:8]}.mp4"
        caminho      = os.path.join(PASTA_SAIDA, nome_arquivo)
        print(f"\nBaixando video para: {caminho}")
        video_bytes = requests.get(video_url, timeout=60).content
        with open(caminho, "wb") as f:
            f.write(video_bytes)
        print(f"Salvo! ({len(video_bytes) / 1024:.0f} KB)")

        # Registrar no log
        log_path = "docs/heygen-melhores-praticas.md"
        print(f"\nNao esqueca de registrar o resultado em: {log_path}")
        print("  - Qualidade da sincronizacao labial")
        print("  - Naturalidade do avatar")
        print("  - Se a legenda ficou correta")
        sys.exit(0)

    elif status == "failed":
        print(f"\nHeyGen reportou falha.")
        print(f"Resposta completa: {status_resp.json()}")
        print(f"\nDiagnostico:")
        print(f"  video_id : {video_id}")
        print(f"  Verifique em: https://app.heygen.com")
        print(f"\nProvaveis causas:")
        print(f"  1. avatar_id incompativel com v3 (tente sem motion_prompt/expressiveness)")
        print(f"  2. voice_id incompativel com este avatar")
        print(f"  3. background asset_id com problema")
        print(f"\nSugestao: rode com payload minimo (sem background, caption, motion_prompt)")
        sys.exit(1)

print("\nTimeout: video nao ficou pronto em 10 minutos.")
print(f"Verifique manualmente em: https://app.heygen.com")
print(f"video_id: {video_id}")
sys.exit(1)

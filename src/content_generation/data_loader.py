import json

def carregar_base(caminho_json: str) -> list:
    with open(caminho_json, "r", encoding="utf-8") as f:
        base_geral = json.load(f)

    print(f"✅ {len(base_geral)} chunks carregados")
    print("Exemplo de chunk:")
    print(json.dumps(base_geral[0], ensure_ascii=False, indent=2))

    return base_geral

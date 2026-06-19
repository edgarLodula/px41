import re

def limpar_texto(texto: str) -> str:
    if not texto:
        return ""
    texto = re.sub(r'Escola Técnica.*?página \d+', '', texto, flags=re.DOTALL)
    return texto.strip()

def normalizar_campo(texto: str) -> str:
    if not texto:
        return ""
    texto = texto.replace('\u200b', '').replace('\xa0', ' ')
    texto = re.sub(r'(?<!\n)\n(?!\n)', ' ', texto)
    texto = re.sub(r' +', ' ', texto)
    return texto.strip()

# HeyGen API — Melhores Práticas e Log de Testes

## Contexto

Documento vivo para registrar decisões de configuração da API HeyGen v3,
resultados dos testes e aprendizados. Atualizar a cada nova rodada de testes.

---

## Configuração Atual do Payload

```python
payload = {
    # Obrigatórios
    "type":       "avatar",
    "avatar_id":  HEYGEN_AVATAR_ID,
    "voice_id":   HEYGEN_VOICE_ID,
    "script":     roteiro,               # texto puro, sem marcações

    # Organização
    "title":      f"Introducao — {disciplina}",

    # Layout
    "aspect_ratio": "16:9",              # padrão para desktop/LMS

    # Engine
    "engine":     {"type": "avatar_iv"}, # padrão; testar avatar_v se elegível

    # Voz
    "voice_settings": {"speed": 1.0},    # range: 0.5–2.0

    # Fundo (sala de aula padronizada)
    "background": {
        "type":      "image",
        "image_url": "URL_DA_IMAGEM_SALA_DE_AULA",  # definir após validar imagem
    },

    # Avatar
    "fit":             "contain",        # evita corte nas bordas
    "motion_prompt":   "calm, professional, occasional hand gestures while teaching",
    "expressiveness":  "medium",         # low | medium | high

    # Legendas
    "caption": {
        "style": "default",  # valor aceito pela API v3 (não "standard" — validado em teste 2026-05-14)
    },
}

headers = {
    "X-Api-Key":       HEYGEN_API_KEY,
    "Content-Type":    "application/json",
    "Idempotency-Key": str(uuid.uuid4()), # evita cobranças duplicadas em retry
}
```

---

## Decisões Tomadas

### Sobre o script
- Enviar **texto puro** da fala, sem marcações de cena, colchetes ou stage directions
- O MOE (Mixture of Experts) separa: o Roteirista gera o texto completo com `[FALA]` marcado, o Especialista HeyGen extrai **só o texto de fala** antes de enviar
- Limite atual: **80 palavras** (~37 segundos). Ajustar conforme resultado dos testes

### Sobre o avatar
- `fit: "contain"` para não cortar o avatar em qualquer resolução
- `expressiveness: "medium"` para aulas — nem robótico nem teatral
- `motion_prompt` melhora naturalidade sem custo adicional (Avatar IV, Photo Avatar)

### Sobre o áudio
- `speed: 1.0` como base. Testar 0.9 se o avatar parecer acelerado
- Voz configurada via `HEYGEN_VOICE_ID` no `.env`

### Sobre legendas
- `caption.style: "standard"` ativa legenda gravada no vídeo
- A resposta também retorna `subtitle_url` com arquivo SRT separado
- **LIBRAS**: não disponível na plataforma HeyGen (2026-05). Feature futura a implementar externamente após entrega do fluxo base

### Sobre o fundo
- Padronizar com imagem de sala de aula profissional
- Usar `image_url` com URL estável (hospedar nos assets da San Marino)
- Alternativa: `{"type": "color", "value": "#1a2744"}` (azul escuro neutro) como fallback

### Sobre o webhook (callback_url)
- HeyGen precisa de URL pública para chamar de volta
- **Local (desenvolvimento):** usar ngrok → `ngrok http 8000` → pegar URL gerada
- **Produção:** URL do servidor de deploy
- Endpoint a criar: `POST /gerador-videos/heygen-webhook`
- Enquanto não houver URL pública: manter polling de 10s

### Sobre engine
- `avatar_iv`: padrão, funciona com todos os avatares
- `avatar_v`: qualidade superior, mas requer avatar elegível — verificar via `GET /v3/avatars/{id}`
- Testar `avatar_v` quando o fluxo base estiver validado

---

## Campos Descartados (e por quê)

| Campo | Motivo |
|-------|--------|
| `audio_url` | Mutuamente exclusivo com `script`. Usamos script |
| `remove_background` | Requer avatar treinado com matting. Verificar suporte |
| `output_format: "webm"` | Requer matting. MP4 padrão para compatibilidade com LMS |
| `watermark` | Feature Enterprise. Não necessário |

---

## Arquitetura MOE (Mixture of Experts)

### Contrato do Roteirista
**Recebe:** disciplina, ementa, conteúdo do markdown aprovado
**Entrega:** roteiro estruturado com seções `[FALA]` e `[CENA]` claramente separadas

```
[CENA 1 — Abertura]
[FALA] Olá, futuro profissional! Seja bem-vindo à disciplina de {disciplina}...
[VISUAL] Avatar centralizado, fundo sala de aula, logo San Marino

[CENA 2 — Desenvolvimento]
[FALA] Nesta jornada você vai aprender...
[VISUAL] Avatar explicando com gestos
```

### Contrato do Especialista HeyGen
**Recebe:** roteiro estruturado do Roteirista
**Entrega:** payload JSON pronto para `POST /v3/videos`
- Extrai apenas o texto de `[FALA]` (concatena em ordem)
- Descarta `[CENA]` e `[VISUAL]` (HeyGen não usa esses campos no v3)
- Aplica limites de palavras
- Monta o payload completo com todos os campos configurados

---

## Log de Testes

> Preencher após cada sessão de teste

### Template de registro

```
DATA: YYYY-MM-DD
ROTEIRO: Roteiro N (ver scripts/roteiros_teste_heygen.md)
AVATAR_ID: ...
VOICE_ID: ...
ENGINE: avatar_iv | avatar_v
EXPRESSIVENESS: low | medium | high
SPEED: 1.0
BACKGROUND: color #hex | image url

RESULTADO:
- video_id: ...
- duration: ...s
- Qualidade da sincronização labial: ruim | ok | boa | ótima
- Naturalidade do avatar: ruim | ok | boa | ótima
- Legenda (caption): sim | não | com erros
- Observações: ...

PRÓXIMOS AJUSTES: ...
```

---

### Teste 001
```
DATA: —
STATUS: aguardando liberação da chave Gemini/billing
```

---

## Features Futuras (pós-entrega base)

- [ ] LIBRAS: integrar serviço externo de intérprete após geração do vídeo
- [ ] Múltiplas cenas com múltiplos clips HeyGen concatenados via moviepy
- [ ] Background dinâmico por disciplina (ex: laboratório para Farmacologia)
- [ ] Background customizável pelo usuário: adicionar campo de upload de imagem na página `/gerador-videos` do frontend. O arquivo é enviado para `POST /v3/assets` do HeyGen, o `asset_id` retornado é usado no payload do vídeo. Permitir também cor sólida como alternativa simples.
- [ ] `avatar_v` quando elegibilidade do avatar for confirmada
- [ ] Webhook em produção (substituir polling)
- [ ] Download da legenda SRT separada para o LMS

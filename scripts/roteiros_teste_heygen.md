# Roteiros de Teste — HeyGen API
## Escola Técnica San Marino

Arquivo com 5 roteiros pré-escritos para testar a API HeyGen sem gastar tokens do Gemini.
Cada roteiro foi criado para testar um aspecto diferente: tamanho, tom e estrutura.

Use diretamente no endpoint `POST /gerador-videos/aprovar-roteiro/{job_id}`
ou no campo `script` do payload HeyGen.

---

## ROTEIRO 1 — Curto e direto (28 palavras ~13s)
**Objetivo:** baseline mínimo. Testa se a API funciona e o avatar sincroniza o lábio.
**Disciplina sugerida:** qualquer

```
Olá! Seja bem-vindo à Escola Técnica San Marino. Hoje começa sua jornada rumo a uma carreira sólida na área da saúde. Estamos aqui para transformar seu futuro. Vamos começar!
```

---

## ROTEIRO 2 — Médio, tom acolhedor (58 palavras ~27s)
**Objetivo:** testar o tamanho padrão do sistema atual (LIMITE_PALAVRAS = 80).
**Disciplina sugerida:** Anatomia e Fisiologia

```
Olá, futuro profissional da saúde! Meu nome é Marina, professora da Escola Técnica San Marino, e estou muito feliz em receber você na disciplina de Anatomia e Fisiologia.

Aqui você vai descobrir como o corpo humano funciona por dentro — cada osso, músculo e órgão tem uma história fascinante. E entender essa história é o primeiro passo para cuidar melhor de quem você vai atender. Boas-vindas ao começo de tudo!
```

---

## ROTEIRO 3 — Tom energético e motivacional (72 palavras ~33s)
**Objetivo:** testar expressividade — combinar com `expressiveness: "high"` e `motion_prompt` ativo.
**Disciplina sugerida:** Administração em Saúde

```
Você escolheu uma das áreas mais importantes do mundo: a saúde! E a Escola San Marino vai te preparar para fazer parte dela com excelência.

Nesta disciplina de Administração em Saúde, você vai aprender a organizar, planejar e liderar equipes em ambientes hospitalares e clínicas. Gestão salva vidas — e você vai entender exatamente como isso funciona na prática.

Eu acredito no seu potencial. Vamos juntos!
```

---

## ROTEIRO 4 — Tom formal e técnico (65 palavras ~30s)
**Objetivo:** testar se o avatar mantém credibilidade em tom mais acadêmico. Combinar com `expressiveness: "low"`.
**Disciplina sugerida:** Farmacologia

```
Bem-vindo à disciplina de Farmacologia Clínica da Escola Técnica San Marino.

Neste módulo, abordaremos os princípios fundamentais da ação medicamentosa, incluindo farmacocinética, farmacodinâmica e as principais classes terapêuticas utilizadas na prática clínica de enfermagem.

O domínio deste conteúdo é indispensável para a administração segura de medicamentos e para a prevenção de eventos adversos. Que seus estudos sejam produtivos.
```

---

## ROTEIRO 5 — Com pausa dramática e estrutura de cenas (78 palavras ~36s)
**Objetivo:** testar como o avatar lida com ritmo variado. Ideal para validar o plano de cenas antes da integração completa.
**Disciplina sugerida:** Primeiros Socorros

```
Imagine esta cena: alguém cai na sua frente. O coração para. Você tem menos de quatro minutos para agir.

Você saberia o que fazer?

Eu sou sua professora na Escola Técnica San Marino, e na disciplina de Primeiros Socorros você vai aprender exatamente isso — como salvar uma vida com suas próprias mãos.

Não é teoria. É habilidade. E ela começa agora.
```

---

## Como usar

### Via endpoint do sistema
```bash
# 1. Inicie um job com qualquer PDF
curl -X POST http://localhost:8000/gerador-videos/iniciar \
  -F "file=@data/input/seu_curriculo.pdf"

# 2. Aprove o markdown (pule a geração do Gemini)
curl -X POST http://localhost:8000/gerador-videos/aprovar-markdown/{job_id} \
  -H "Content-Type: application/json" \
  -d '{"markdown": "# Teste\n\nConteudo de teste."}'

# 3. Injete diretamente um roteiro deste arquivo
curl -X POST http://localhost:8000/gerador-videos/aprovar-roteiro/{job_id} \
  -H "Content-Type: application/json" \
  -d '{"script": "Cole aqui o roteiro escolhido"}'

# 4. Aprove as cenas (pode ser texto livre)
curl -X POST http://localhost:8000/gerador-videos/aprovar-cenas/{job_id} \
  -H "Content-Type: application/json" \
  -d '{"scenes": "CENA 1 — Abertura\n[AVATAR] Sorrindo\n[FALA] Roteiro completo"}'
```

### Direto no payload HeyGen (para testes isolados)
```python
payload = {
    "type":         "avatar",
    "avatar_id":    "SEU_AVATAR_ID",
    "voice_id":     "SEU_VOICE_ID",
    "script":       "Cole aqui o roteiro escolhido",
    "title":        "Teste Roteiro 2 — Acolhedor",
    "aspect_ratio": "16:9",
}
```

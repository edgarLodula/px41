import os
import time
from openai import OpenAI


def gerar_roteiro(texto, disciplina, token):
    client = OpenAI(api_key=token)
    modelo = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    nome_avatar = os.getenv("AVATAR_NOME", "Marina")

    prompt = f"""Você é um roteirista especialista em vídeo-aulas técnicas para a disciplina de {disciplina}.
O avatar que apresenta o vídeo se chama {nome_avatar}. Use esse nome nas falas de apresentação e despedida.
Seu objetivo é criar roteiros de vídeo-aula inaugurais altamente engajadores,
seguindo rigorosamente um formato padronizado com blocos, timecodes e marcações de produção.

Com base no conteúdo abaixo, crie um roteiro completo de vídeo-aula inaugural para a disciplina de {disciplina}.

**REGRAS DE NATURALIDADE (muito importantes — o roteiro alimenta um avatar de IA que fala o texto):**
- O texto dentro das aspas de [AVATAR] deve soar como uma pessoa falando de verdade, não como
  um texto escrito sendo lido: frases curtas, ritmo variado, conectivos do português falado
  ("olha", "repara", "então", "e sabe qual é a boa notícia?"). Evite orações longas e subordinadas.
- Use vírgulas e reticências para marcar pausas naturais de fala (onde a pessoa respiraria).
- A direção entre parênteses após [AVATAR] deve ser uma instrução CURTA e CONCRETA de expressão
  facial/corporal/gesto (ex.: "sorrindo, gesticulando com as mãos, olhar direto para a câmera"),
  não uma descrição abstrata — ela é usada literalmente para guiar a animação do avatar.
- Varie o tom entre os blocos: gancho/abertura mais energético, desenvolvimento mais didático e
  calmo, encerramento caloroso — cenas com o mesmo tom do início ao fim soam artificiais.

**SIGA EXATAMENTE este formato:**
---
Roteiro de Vídeo-Aula Inaugural: "Os Superpoderes de [NOME DA DISCIPLINA]"

Legenda de Execução:
● [AVATAR]: Direcionamento de emoção e postura para a IA geradora.
● [VISUAL/B-ROLL]: Imagens, vídeos curtos ou animações que sobrepõem a tela para quebrar a monotonia visual (essencial para retenção).
● [TEXTO NA TELA]: Palavras-chave que reforçam o aprendizado.

Bloco 1: O Gancho e a Promessa (0:00 - 1:00)

[AVATAR] (Sorriso confiante, contato visual direto com a câmera. Tom enérgico e intrigante)
"[Pergunta intrigante relacionada à disciplina que conecte com o cotidiano]"

[VISUAL/B-ROLL] ([Descrição de imagens impactantes relacionadas ao tema])

[AVATAR] (Expressão séria, mas acolhedora)
"[Apresentação: resposta à pergunta, identificação do avatar e boas-vindas em nome da Escola Técnica San Marino]"

[TEXTO NA TELA] (Animação elegante: Escola Técnica San Marino - {disciplina})

[AVATAR] (Movimento de mãos explicativo)
"[Desmistificação do preconceito sobre a disciplina + promessa de valor prático]"

Bloco 2: O Mapa da Jornada (A Ementa Traduzida para o Real) (1:00 - 3:30)

[AVATAR] (Tom empolgante, enumerando com os dedos)
"[Introdução dos 3 grandes módulos/superpoderes da disciplina, com o primeiro sendo nomeado]"

[TEXTO NA TELA] (Superpoder 1: [Nome do Módulo 1])

[AVATAR] (Tom professoral)
"[Descrição prática do que o aluno aprenderá no módulo 1, com exemplos do mundo real]"

[VISUAL/B-ROLL] ([Descrição de animação técnica relacionada ao módulo 1])

[AVATAR] (Sorriso empolgado)
"[Transição para o módulo 2]"

[TEXTO NA TELA] (Superpoder 2: [Nome do Módulo 2])

[AVATAR] (Fazendo gesto explicativo)
"[Descrição prática do que o aluno aprenderá no módulo 2, com exemplos do mundo real]"

[VISUAL/B-ROLL] ([Descrição de animação técnica relacionada ao módulo 2])

[AVATAR] (Expressão de alerta, tom mais grave e dramático)
"[Transição para o módulo 3, destacando o desafio ou complexidade do tema]"

[TEXTO NA TELA] (Superpoder 3: [Nome do Módulo 3])

[VISUAL/B-ROLL] ([Vídeo ou imagem impactante relacionada ao módulo 3])

[AVATAR] (Tom sério)
"[Descrição prática do que o aluno aprenderá no módulo 3, com exemplo dramático de consequência real]"

Bloco 3: O Modelo Híbrido San Marino (3:30 - 4:30)

[AVATAR] (Postura relaxada, tom de mentoria e proximidade)
"[Reconhecimento da preocupação do aluno + afirmação de capacidade + apresentação do modelo híbrido]"

[VISUAL/B-ROLL] (Tela dividida: De um lado o aluno assistindo ao vídeo no celular/notebook; do outro, alunos com EPIs operando equipamentos no laboratório)

[AVATAR] (Tom de explicação clara)
"[Explicação do modelo: teoria online + prática presencial no laboratório, destacando os benefícios para o aluno]"

Bloco 4: Call to Action (CTA) e Encerramento (4:30 - 5:00)

[AVATAR] (Sorriso encorajador)
"[Mensagem motivacional final conectando a disciplina com a transformação profissional do aluno]"

[TEXTO NA TELA] (Seu próximo passo)

[AVATAR] (Apontando para baixo ou para o lado, dependendo do LMS)
"[Instrução clara: abrir a Apostila 1 e avançar para o próximo vídeo. Despedida encorajadora.]"

[VISUAL/B-ROLL] (Logo da Escola Técnica San Marino brilhando com uma transição suave para o escuro. Fim do vídeo.)

Notas Estratégicas de {nome_avatar} para a Diretoria:
1. Redução de Carga Cognitiva: [Breve justificativa das escolhas pedagógicas do roteiro]
2. Alinhamento com o Interesse 2: [Como este roteiro apoia o engajamento com o formato híbrido]
3. Padronização Editorial: [Lembrete de que este roteiro serve de template para outras disciplinas]
---

**Conteúdo da disciplina para basear o roteiro:**

{texto[:8000]}
"""

    for tentativa in range(3):
        try:
            resposta = client.chat.completions.create(
                model=modelo,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=4000,
            )
            return resposta.choices[0].message.content
        except Exception as e:
            erro = str(e)
            if "401" in erro or "authentication" in erro.lower() or "invalid_api_key" in erro.lower():
                raise Exception(
                    f"❌ Chave OpenAI inválida. Verifique OPENAI_API_KEY. Detalhe: {erro}"
                )
            elif "429" in erro or "503" in erro or "500" in erro:
                espera = (2 ** tentativa) * 15
                print(f"⚠️ Rate limit/serviço indisponível. Aguardando {espera}s... (tentativa {tentativa + 1}/3)")
                time.sleep(espera)
            else:
                print(f"⚠️ Erro ao gerar roteiro (tentativa {tentativa + 1}/3): {e}")

    raise Exception(f"❌ Falha ao gerar roteiro para '{disciplina}' após 3 tentativas.")

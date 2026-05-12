import os
import requests
import time


def gerar_roteiro(texto, disciplina, token):
    for tentativa in range(3):
        try:
            headers = {"Content-Type": "application/json"}
            modelo = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

            payload = {
                "contents": [
                    {
                        "parts": [
                            {
                                "text": f"""Você é um roteirista especialista em vídeo-aulas técnicas para a disciplina de {disciplina}.
Seu objetivo é criar roteiros de vídeo-aula inaugurais altamente engajadores,
seguindo rigorosamente um formato padronizado com blocos, timecodes e marcações de produção.

Com base no conteúdo abaixo, crie um roteiro completo de vídeo-aula inaugural para a disciplina de {disciplina}.

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

Notas Estratégicas da Marina para a Diretoria:
1. Redução de Carga Cognitiva: [Breve justificativa das escolhas pedagógicas do roteiro]
2. Alinhamento com o Interesse 2: [Como este roteiro apoia o engajamento com o formato híbrido]
3. Padronização Editorial: [Lembrete de que este roteiro serve de template para outras disciplinas]
---

**Conteúdo da disciplina para basear o roteiro:**

{texto[:2000]}
"""
                            }
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 2000
                }
            }

            response = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={token}",
                headers=headers,
                json=payload
            )

            if response.status_code == 403:
                raise Exception(
                    f"❌ Acesso negado à Gemini API (403). Verifique se o projeto Google Cloud "
                    f"tem a API habilitada e se o token GEMINI é válido. Detalhe: {response.text}"
                )

            response.raise_for_status()

            return response.json()["candidates"][0]["content"]["parts"][0]["text"]

        except Exception as e:
            erro = str(e)
            if "403" in erro or "PERMISSION_DENIED" in erro:
                raise
            elif "429" in erro or "503" in erro:
                espera = (2 ** tentativa) * 15
                print(f"⚠️ Rate limit/serviço indisponível. Aguardando {espera}s... (tentativa {tentativa + 1}/3)")
                time.sleep(espera)
            else:
                print(f"⚠️ Erro ao gerar roteiro (tentativa {tentativa + 1}/3): {e}")

    raise Exception(f"❌ Falha ao gerar roteiro para '{disciplina}' após 3 tentativas.")

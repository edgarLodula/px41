"""
Profiles das áreas de formação técnica suportadas pelo pipeline.

Contém: AREA_PROFILES, _ALIASES, get_profile, validação estrutural.
NÃO contém lógica de detecção automática — isso está em area_detector.py.
"""
import copy

# ---------------------------------------------------------------------------
# PROFILES
# ---------------------------------------------------------------------------

AREA_PROFILES: dict[str, dict] = {
    "tecnico_enfermagem": {
        "nome_curso": "Técnico em Enfermagem",
        "nome_area": "saúde",
        "nome_profissional": "técnico em enfermagem",
        "ambientes_de_trabalho": [
            "enfermaria / unidade de internação hospitalar",
            "UTI (unidade de terapia intensiva)",
            "pronto-socorro / emergência",
            "centro cirúrgico",
            "UBS / atenção básica",
            "home care",
            "CME (central de material e esterilização)",
        ],
        "equipamentos_tipicos": [
            "esfigmomanômetro", "estetoscópio", "oxímetro",
            "monitor multiparamétrico", "bomba de infusão",
            "glicosímetro", "termômetro digital", "carro de emergência",
        ],
        "normas_regulamentadoras": ["NR-32", "NR-6"],
        "normas_tecnicas": ["COFEN", "ANVISA", "Ministério da Saúde"],
        "conselho_classe": "COFEN / COREN",
        "lei_exercicio": "Lei nº 7.498/1986 e Decreto nº 94.406/1987",
        "grandezas_tipicas": (
            "PA, FC, FR, temperatura, SpO2, dor (escalas), "
            "balanço hídrico, Glasgow, Braden"
        ),
        "tecnologias_emergentes": (
            "prontuário eletrônico (PEP), telemedicina, "
            "monitoramento remoto, SAE digital"
        ),
        "softwares_tipicos": "e-SUS APS, sistemas hospitalares, PNI SI-PNI",
        "epis_tipicos": (
            "luvas de procedimento, máscara cirúrgica, N95/PFF2, "
            "avental, óculos de proteção, gorro"
        ),
        "procedimentos_seguranca_chave": (
            "5 momentos da higienização das mãos, 9 certos da medicação, "
            "precauções padrão, segurança do paciente, descarte de perfurocortantes"
        ),
        "vocabulario_proibido": [
            "motor", "CLP", "inversor", "fábrica", "subestação",
            "compressor", "redutor", "curso industrial",
            "técnico em administração", "técnico em eletromecânica",
            "técnico em eletrotécnica", "curso técnico de administração",
            "curso técnico de gestão", "curso técnico industrial",
        ],
        "regras_terminologia_obrigatorias": [
            "Use SEMPRE 'LPP – Lesão por Pressão'. NUNCA use 'úlcera por pressão' ou 'escara'.",
            "Use 'paciente', 'cliente' ou 'usuário do serviço de saúde'. NUNCA use termos de ambiente fabril.",
            "Ao falar de medicamentos, sempre cite os '9 certos'.",
            "Ao falar de prevenção de infecção, sempre cite os '5 momentos da higienização das mãos' (OMS).",
            "Use a Lei nº 7.498/1986 ao falar de competências legais do técnico de enfermagem.",
        ],
        "referencias_oficiais_obrigatorias": [
            "Portal do Ministério da Saúde — https://www.gov.br/saude",
            "COFEN — https://www.cofen.gov.br",
            "ANVISA — https://www.gov.br/anvisa",
        ],
    },

    "tecnico_administracao": {
        "nome_curso": "Técnico em Administração",
        "nome_area": "administração",
        "nome_profissional": "técnico em administração",
        "ambientes_de_trabalho": [
            "escritórios corporativos",
            "setor financeiro e contábil",
            "departamento de recursos humanos",
            "setor de estoque e logística",
            "departamento comercial e de vendas",
            "controladoria",
        ],
        "equipamentos_tipicos": [
            "computador", "planilhas eletrônicas",
            "sistemas ERP", "impressora", "softwares de gestão",
        ],
        "normas_regulamentadoras": [],
        "normas_tecnicas": ["legislação empresarial", "normas contábeis"],
        "conselho_classe": "CRA (Conselho Regional de Administração)",
        "lei_exercicio": "Lei nº 4.769/1965",
        "grandezas_tipicas": (
            "fluxo de caixa, lucro, custo, receita, estoque, "
            "KPIs, margem de contribuição, ROI"
        ),
        "tecnologias_emergentes": (
            "ERP em nuvem, automação de processos (RPA), "
            "IA para gestão, Business Intelligence (BI)"
        ),
        "softwares_tipicos": "Excel, ERP (TOTVS, SAP, Oracle), CRM, PowerBI",
        "epis_tipicos": "não aplicável para ambiente administrativo",
        "procedimentos_seguranca_chave": (
            "organização de processos administrativos, "
            "controle financeiro e orçamentário, gestão de estoque, conformidade legal"
        ),
        "vocabulario_proibido": [
            "UTI", "paciente", "enfermagem", "enfermeiro",
            "saúde", "farmacologia", "anatomia", "fisiologia",
            "medicação", "prontuário", "curso técnico de saúde",
            "curso técnico de enfermagem", "técnico em enfermagem",
            "motor", "compressor", "CLP", "fábrica",
            "curso industrial", "técnico em eletromecânica",
        ],
        "regras_terminologia_obrigatorias": [],
        "referencias_oficiais_obrigatorias": [],
    },

    "tecnico_eletromecanica": {
        "nome_curso": "Técnico em Eletromecânica",
        "nome_area": "eletromecânica industrial",
        "nome_profissional": "técnico em eletromecânica",
        "ambientes_de_trabalho": [
            "manutenção industrial",
            "chão de fábrica / linha de produção",
            "oficinas mecânicas industriais",
            "plantas produtivas",
        ],
        "equipamentos_tipicos": [
            "motor elétrico", "redutor", "rolamento",
            "bomba centrífuga", "compressor", "esteira transportadora",
        ],
        "normas_regulamentadoras": ["NR-10", "NR-12", "NR-35"],
        "normas_tecnicas": ["ABNT/NBR"],
        "conselho_classe": "CREA/CFT",
        "lei_exercicio": "Lei nº 5.524/1968",
        "grandezas_tipicas": (
            "torque, vibração, rotação, potência mecânica, "
            "rendimento, temperatura de operação"
        ),
        "tecnologias_emergentes": (
            "manutenção preditiva, sensores industriais, "
            "IoT industrial, Indústria 4.0"
        ),
        "softwares_tipicos": (
            "CAD mecânico, simuladores industriais, "
            "sistemas de gestão de manutenção (CMMS)"
        ),
        "epis_tipicos": (
            "capacete, luvas, óculos de proteção, "
            "protetor auricular, calçado de segurança"
        ),
        "procedimentos_seguranca_chave": (
            "bloqueio e etiquetagem (LOTO), análise preliminar de risco (APR), "
            "permissão de trabalho (PT), manutenção preventiva"
        ),
        "vocabulario_proibido": [
            "paciente", "UTI", "medicação", "enfermagem", "saúde",
            "curso técnico de saúde", "curso técnico em enfermagem",
            "técnico em administração", "curso técnico de administração",
        ],
        "regras_terminologia_obrigatorias": [],
        "referencias_oficiais_obrigatorias": [],
    },

    "tecnico_eletrotecnica": {
        "nome_curso": "Técnico em Eletrotécnica",
        "nome_area": "energia elétrica",
        "nome_profissional": "técnico em eletrotécnica",
        "ambientes_de_trabalho": [
            "subestações elétricas",
            "instalações elétricas prediais e industriais",
            "painéis elétricos",
            "redes de distribuição",
        ],
        "equipamentos_tipicos": [
            "transformador", "disjuntor", "cabos elétricos",
            "painel elétrico", "SPDA", "multímetro",
        ],
        "normas_regulamentadoras": ["NR-10", "NR-35"],
        "normas_tecnicas": ["ABNT NBR 5410", "ABNT NBR 14039"],
        "conselho_classe": "CREA/CFT",
        "lei_exercicio": "Lei nº 5.524/1968",
        "grandezas_tipicas": (
            "tensão, corrente, potência, resistência, "
            "fator de potência, frequência"
        ),
        "tecnologias_emergentes": (
            "smart grid, energia solar fotovoltaica, "
            "automação elétrica, EV charging"
        ),
        "softwares_tipicos": "AutoCAD Electrical, ETAP, simulação elétrica",
        "epis_tipicos": (
            "luvas isolantes, capacete com aba frontal, "
            "óculos de proteção, calçado isolante"
        ),
        "procedimentos_seguranca_chave": (
            "desenergização, bloqueio e etiquetagem (LOTO), "
            "análise de risco elétrico, medição antes de tocar"
        ),
        "vocabulario_proibido": [
            "paciente", "medicação", "UTI", "enfermagem", "saúde",
            "curso técnico de saúde", "curso técnico em enfermagem",
            "técnico em administração",
        ],
        "regras_terminologia_obrigatorias": [],
        "referencias_oficiais_obrigatorias": [],
    },

    "curso_oratoria": {
        "nome_curso": "Curso de Oratória Profissional",
        "nome_area": "oratória e comunicação profissional",
        "nome_profissional": "orador / comunicador profissional",
        "ambientes_de_trabalho": [
            "palco / auditório / teatro",
            "sala de treinamento corporativo",
            "câmera (vídeos, lives, videoconferências)",
            "sala de reunião / boardroom",
            "evento social e cerimonial (MC, casamentos, formaturas)",
            "ambiente jurídico (tribunal, debate, júri simulado)",
            "ambiente acadêmico (defesa, aula, palestra científica)",
            "podcast / rádio / transmissão ao vivo",
        ],
        "equipamentos_tipicos": [
            "microfone de lapela (lavalier)",
            "microfone condensador de estúdio",
            "headset com microfone",
            "teleprompter (físico e digital)",
            "clicker / apresentador de slides remoto",
            "câmera (DSLR, mirrorless, webcam profissional)",
            "iluminação de palco e ring light",
            "fone de retorno (in-ear monitor)",
            "pódio e púlpito",
        ],
        "normas_regulamentadoras": [],
        "normas_tecnicas": [],
        "conselho_classe": "não há conselho regulamentador específico",
        "lei_exercicio": "não aplicável",
        "grandezas_tipicas": (
            "velocidade de fala (WPM — palavras por minuto), "
            "frequência vocal (Hz), volume (dB), pausas estratégicas (segundos), "
            "contato visual (distribuição por zona), "
            "dicção (escala GRBAS), gesticulação (amplitude/frequência)"
        ),
        "tecnologias_emergentes": (
            "apresentações interativas (Prezi, Canva Apresentações), "
            "videoconferência profissional (Zoom, Teams, Meet), "
            "live streaming (YouTube, Instagram, TikTok), "
            "teleprompter digital em smartphone/tablet, "
            "IA para criação de roteiros e síntese de voz, "
            "podcasts e audiogramas para distribuição de conteúdo"
        ),
        "softwares_tipicos": (
            "PowerPoint, Keynote, Prezi, Canva, Google Slides, "
            "OBS Studio (transmissão), Adobe Premiere Rush (edição), "
            "CapCut, Descript (edição de áudio/vídeo)"
        ),
        "epis_tipicos": (
            "higiene vocal (não EPIs industriais): hidratação adequada (>2 L/dia), "
            "repouso vocal após uso intenso, evitar irritantes (fumo, álcool, refluxo), "
            "uso de vaporizador em ambientes secos, pastilhas sem mentol"
        ),
        "procedimentos_seguranca_chave": (
            "aquecimento vocal antes da apresentação (10–15 min): vibração labial, "
            "escala de articulação, vocalises; "
            "resfriamento vocal após uso prolongado; "
            "respiração diafragmática como base técnica; "
            "postura corporal neutra para projeção de voz; "
            "hidratação contínua com água em temperatura ambiente"
        ),
        "vocabulario_proibido": [
            "ERP", "SAP", "TOTVS", "Oracle ERP", "PowerBI", "Power BI",
            "CRA", "Conselho Regional de Administração",
            "KPI", "ROI", "margem de contribuição", "fluxo de caixa",
            "estoque", "balanço patrimonial", "DRE", "controladoria",
            "RPA", "Business Intelligence", "BI empresarial",
            "técnico em administração", "curso técnico de administração",
            "técnico em enfermagem", "UTI", "paciente", "medicação",
            "CLP", "inversor", "motor elétrico", "fábrica", "subestação",
            "compressor de refrigeração", "PMOC", "NR-10", "NR-32",
        ],
        "regras_terminologia_obrigatorias": [
            "SEMPRE cite ao menos um autor de referência por seção: "
            "Dale Carnegie (Como Falar em Público e Influenciar Pessoas), "
            "Reinaldo Polito (Como Falar Corretamente e Bem), "
            "Robert Cialdini (Influência: A Psicologia da Persuasão), "
            "Carmine Gallo (Falar como TED), Bert Decker (You've Got to Be Believed to Be Heard).",
            "Exercícios práticos de voz/oratória DEVEM conter: nome do exercício, "
            "objetivo, duração/repetições, passo a passo numerado e critério de avaliação.",
            "Ao tratar de técnica vocal, inclua OBRIGATORIAMENTE exercícios de: "
            "respiração diafragmática, vibração labial (motorboat/dadá), "
            "trava-línguas para dicção, escalas de articulação e vocalises.",
            "Ao tratar de storytelling, cite OBRIGATORIAMENTE: "
            "Jornada do Herói (Joseph Campbell), Pixar Story Spine, "
            "estrutura do pitch (problema–solução–impacto), "
            "e ao menos uma das fórmulas: AIDA, PAS ou SPIN.",
            "Exemplos e estudos de caso DEVEM variar o contexto em cada tópico: "
            "NUNCA repita 'apresentação de resultados financeiros'. "
            "Use cenários como: defesa de TCC, pitch de startup, discurso de casamento, "
            "audiência em tribunal, aula universitária, live de produto, debate político, "
            "sermão/missa, recebimento de prêmio, toastmasters, vídeo tutorial.",
            "Ao citar persuasão, mencione os 6 princípios de Cialdini: "
            "reciprocidade, comprometimento, prova social, afinidade, autoridade, escassez.",
        ],
        "referencias_oficiais_obrigatorias": [
            "Dale Carnegie — Como Falar em Público e Influenciar Pessoas (1936/ed. revisada)",
            "Reinaldo Polito — Como Falar Corretamente e Bem (ed. Saraiva)",
            "Robert B. Cialdini — Influência: A Psicologia da Persuasão (ed. Harper Collins Brasil)",
            "Carmine Gallo — Falar como TED: Os 9 Segredos de Comunicação (ed. HSM)",
            "Bert Decker — You've Got to Be Believed to Be Heard (ed. St. Martin's Press)",
            "Toastmasters International — https://www.toastmasters.org / https://www.toastmasters.org.br",
        ],
    },

    "refrigeracao_climatizacao": {
        "nome_curso": "Técnico em Refrigeração e Climatização",
        "nome_area": "refrigeração e climatização (HVAC)",
        "nome_profissional": "técnico em refrigeração e climatização",
        "ambientes_de_trabalho": [
            "instalações de ar-condicionado residencial e comercial",
            "câmaras frigoríficas",
            "manutenção HVAC em edifícios",
            "centrais de processamento de ar (CPA)",
        ],
        "equipamentos_tipicos": [
            "compressor de refrigeração", "condensador", "evaporador",
            "válvula de expansão", "fluido refrigerante", "manômetro de carga",
        ],
        "normas_regulamentadoras": ["PMOC", "NR-10", "NR-35"],
        "normas_tecnicas": ["ABNT NBR 16401"],
        "conselho_classe": "CREA/CFT",
        "lei_exercicio": "não aplicável",
        "grandezas_tipicas": (
            "BTU/h, temperatura (°C), pressão (bar/psi), "
            "superaquecimento, sub-resfriamento, COP"
        ),
        "tecnologias_emergentes": (
            "HVAC inteligente, eficiência energética, "
            "IoT climático, refrigerantes sustentáveis (HFOs)"
        ),
        "softwares_tipicos": "simulação térmica, projeto HVAC, software de carga térmica",
        "epis_tipicos": (
            "luvas criogênicas, óculos de proteção, "
            "máscara de proteção química, calçado de segurança"
        ),
        "procedimentos_seguranca_chave": (
            "manipulação segura de gases refrigerantes, PMOC, "
            "controle de pressão, recuperação de gás refrigerante"
        ),
        "vocabulario_proibido": [
            "paciente", "UTI", "medicação", "CLP", "enfermagem", "saúde",
            "curso técnico de saúde", "técnico em administração",
        ],
        "regras_terminologia_obrigatorias": [],
        "referencias_oficiais_obrigatorias": [],
    },

    "curso_seguranca_no_trabalho": {
        "nome_curso": "Técnico em Segurança do Trabalho",
        "nome_area": "segurança do trabalho",
        "nome_profissional": "técnico em segurança do trabalho",
        "ambientes_de_trabalho": [
            "indústrias e plantas de manufatura",
            "canteiros de obras e construção civil",
            "mineração e extração",
            "SESMT (Serviço Especializado em Engenharia de Segurança e em Medicina do Trabalho)",
            "logística e armazéns",
            "setor elétrico e químico",
        ],
        "equipamentos_tipicos": [
            "medidor de nível de ruído (decibelímetro)",
            "detector de gases e vapores",
            "equipamentos de proteção individual (EPIs)",
            "extintor de incêndio",
            "detector de fumaça e alarme de incêndio",
            "cinto de segurança tipo paraquedista",
            "kit de primeiros socorros",
        ],
        "normas_regulamentadoras": [
            "NR-1 (Disposições Gerais e PGR)",
            "NR-5 (CIPA)",
            "NR-6 (EPIs)",
            "NR-7 (PCMSO)",
            "NR-9 (Avaliação e controle de riscos ocupacionais)",
            "NR-10 (Segurança em instalações elétricas)",
            "NR-12 (Segurança no trabalho em máquinas e equipamentos)",
            "NR-17 (Ergonomia)",
            "NR-23 (Proteção contra incêndios)",
            "NR-35 (Trabalho em altura)",
        ],
        "normas_tecnicas": ["ABNT NBR", "ISO 45001"],
        "conselho_classe": "CREA/CFT",
        "lei_exercicio": "Lei nº 7.410/1985",
        "grandezas_tipicas": (
            "nível de ruído (dB), concentração de agentes químicos (ppm/mg/m³), "
            "temperatura de bulbo seco e úmido (°C), IBUTG, "
            "taxa de frequência de acidentes (TFA), taxa de gravidade (TG), "
            "número de dias perdidos (NDP)"
        ),
        "tecnologias_emergentes": (
            "sistemas digitais de gestão de SST, "
            "wearables para monitoramento de condições ambientais, "
            "drones para inspeção de locais de risco, "
            "realidade aumentada para treinamentos de segurança, "
            "ISO 45001 para sistemas de gestão de SST"
        ),
        "softwares_tipicos": (
            "software de gestão de SST (eSocial, TOTVS SST, SAP EHS), "
            "sistemas de emissão de CAT, controle de EPIs, relatórios de acidentes"
        ),
        "epis_tipicos": (
            "capacete de segurança, luvas (nitrila, couro, isolantes), "
            "óculos de proteção, protetor auricular (concha e espuma), "
            "calçado de segurança (biqueira de aço), "
            "cinto de segurança tipo paraquedista, máscara respiratória (PFF1/PFF2)"
        ),
        "procedimentos_seguranca_chave": (
            "APR (Análise Preliminar de Risco), "
            "PT (Permissão de Trabalho), "
            "DDS (Diálogo Diário de Segurança), "
            "LOTO (bloqueio e etiquetagem), "
            "investigação e análise de acidentes (Árvore de Causas), "
            "inspeções de segurança periódicas, "
            "treinamentos de brigada de incêndio e primeiros socorros"
        ),
        "vocabulario_proibido": [
            "paciente", "UTI", "medicação", "enfermagem", "prontuário",
            "curso técnico de saúde", "técnico em enfermagem",
            "CLP", "inversor de frequência", "fator de potência",
            "picking", "packing", "WMS", "TMS", "lead time",
        ],
        "regras_terminologia_obrigatorias": [
            "Use 'trabalhador' ou 'colaborador', nunca 'paciente' ou 'operador de máquina' sem contexto.",
            "Ao citar riscos, classifique sempre por tipo: físico, químico, biológico, ergonômico ou de acidente.",
            "Ao mencionar EPI, sempre indique o CA (Certificado de Aprovação) como requisito legal (NR-6).",
            "Ao tratar de acidentes, utilize a terminologia da NR-1 e do eSocial (CAT — Comunicação de Acidente de Trabalho).",
            "Cite a Lei nº 7.410/1985 ao abordar as atribuições legais do técnico em segurança do trabalho.",
        ],
        "referencias_oficiais_obrigatorias": [
            "Ministério do Trabalho e Emprego — Normas Regulamentadoras: https://www.gov.br/trabalho-e-emprego/pt-br/acesso-a-informacao/participacao-social/conselhos-e-orgaos-colegiados/ctpp-nrs/portarias-do-orgao-gestor",
            "Fundacentro — https://www.fundacentro.gov.br",
            "ABNT — Normas Técnicas de Segurança: https://www.abnt.org.br",
        ],
    },

    "curso_logistica": {
        "nome_curso": "Técnico em Logística",
        "nome_area": "logística e supply chain",
        "nome_profissional": "técnico em logística",
        "ambientes_de_trabalho": [
            "centros de distribuição (CD) e armazéns",
            "portos, aeroportos e terminais de carga",
            "transportadoras e operadores logísticos",
            "setor de compras e suprimentos de empresas",
            "e-commerce e fulfillment centers",
            "indústrias (setor de supply chain interno)",
        ],
        "equipamentos_tipicos": [
            "empilhadeira (contrabalancada, retráctil, paleteira elétrica)",
            "leitor de código de barras e scanner RF",
            "leitor RFID",
            "palete PBR e rack de armazenagem",
            "coletor de dados (handheld)",
            "balança industrial",
            "sistema de esteiras e transportadores",
        ],
        "normas_regulamentadoras": [
            "NR-11 (Transporte, movimentação, armazenagem e manuseio de materiais)",
            "NR-12 (Máquinas e equipamentos — empilhadeiras)",
            "NR-17 (Ergonomia)",
        ],
        "normas_tecnicas": ["ABNT NBR", "legislação aduaneira e fiscal (NF-e, CT-e, SPED)"],
        "conselho_classe": "não há conselho regulamentador específico",
        "lei_exercicio": "não aplicável",
        "grandezas_tipicas": (
            "lead time, tempo de ciclo de pedido, giro de estoque, "
            "nível de serviço (fill rate), acuracidade de inventário (%), "
            "OTIF (On Time In Full), SKU, custo por pedido (CPP), "
            "capacidade de armazenagem (m²/posição palete)"
        ),
        "tecnologias_emergentes": (
            "WMS (Warehouse Management System), "
            "TMS (Transportation Management System), "
            "rastreamento em tempo real (GPS/IoT), "
            "automação de armazéns (AS/RS, AGV — veículos autônomos guiados), "
            "blockchain para rastreabilidade, "
            "drones para inventário aéreo, "
            "picking por voz e pick-to-light"
        ),
        "softwares_tipicos": (
            "WMS (SAP EWM, TOTVS, Manhattan), "
            "TMS (Oracle TMS, SAP TM), "
            "ERP (SAP, TOTVS, Oracle), "
            "Power BI para dashboards logísticos, "
            "Excel para gestão de estoque e KPIs"
        ),
        "epis_tipicos": (
            "colete refletivo, calçado de segurança com biqueira de aço, "
            "capacete (em áreas com movimentação de empilhadeira), "
            "luvas de proteção para manuseio de cargas"
        ),
        "procedimentos_seguranca_chave": (
            "FIFO (First In, First Out) e FEFO (First Expired, First Out) para gestão de validade, "
            "inventário rotativo e cíclico, "
            "picking (separação de pedidos) e packing (embalagem), "
            "recebimento e conferência de mercadorias, "
            "gestão de devoluções (logística reversa), "
            "auditoria de endereçamento e acuracidade de estoque"
        ),
        "vocabulario_proibido": [
            "paciente", "UTI", "medicação", "enfermagem", "prontuário",
            "curso técnico de saúde", "técnico em enfermagem",
            "CLP", "subestação elétrica", "disjuntor",
            "compressor de refrigeração", "BTU/h",
            "dicção", "vocalise", "oratória", "storytelling",
        ],
        "regras_terminologia_obrigatorias": [
            "Use termos técnicos em inglês consagrados sem tradução forçada quando amplamente adotados: SKU, WMS, TMS, OTIF, lead time, picking, packing.",
            "Ao citar indicadores, sempre inclua a fórmula de cálculo ou definição operacional (ex.: Giro de estoque = Custo das mercadorias vendidas / Estoque médio).",
            "Ao tratar de transporte, distinga modal rodoviário, ferroviário, aéreo, aquaviário e dutoviário.",
            "Ao falar de documentos fiscais, cite NF-e (Nota Fiscal Eletrônica) e CT-e (Conhecimento de Transporte Eletrônico).",
        ],
        "referencias_oficiais_obrigatorias": [
            "ABML (Associação Brasileira de Movimentação e Logística) — https://www.abml.org.br",
            "ILOS (Instituto de Logística e Supply Chain) — https://www.ilos.com.br",
            "Portal NF-e/CT-e — Secretaria da Fazenda: https://www.nfe.fazenda.gov.br",
        ],
    },
}

# ---------------------------------------------------------------------------
# CHAVES OBRIGATÓRIAS — validadas ao importar
# ---------------------------------------------------------------------------

_REQUIRED_KEYS: frozenset[str] = frozenset({
    "nome_curso", "nome_area", "nome_profissional", "ambientes_de_trabalho",
    "equipamentos_tipicos", "normas_regulamentadoras", "normas_tecnicas",
    "conselho_classe", "lei_exercicio", "grandezas_tipicas",
    "tecnologias_emergentes", "softwares_tipicos", "epis_tipicos",
    "procedimentos_seguranca_chave", "vocabulario_proibido",
    "regras_terminologia_obrigatorias", "referencias_oficiais_obrigatorias",
})


def validar_profiles() -> None:
    """Verifica que todos os profiles têm as chaves obrigatórias. Lança ValueError se não."""
    for key, profile in AREA_PROFILES.items():
        missing = _REQUIRED_KEYS - set(profile.keys())
        if missing:
            raise ValueError(
                f"Profile '{key}' está incompleto. Chaves ausentes: {sorted(missing)}"
            )


validar_profiles()


# ---------------------------------------------------------------------------
# ALIASES — mapeiam variantes de nome para a chave canônica
# ---------------------------------------------------------------------------

_ALIASES: dict[str, str] = {
    # enfermagem / saúde
    "enfermagem": "tecnico_enfermagem",
    "saúde": "tecnico_enfermagem",
    "saude": "tecnico_enfermagem",
    "tecnico em enfermagem": "tecnico_enfermagem",
    "técnico em enfermagem": "tecnico_enfermagem",
    "tecnico_em_enfermagem": "tecnico_enfermagem",
    # administração
    "administracao": "tecnico_administracao",
    "administração": "tecnico_administracao",
    "tecnico em administracao": "tecnico_administracao",
    "técnico em administração": "tecnico_administracao",
    "tecnico_em_administracao": "tecnico_administracao",
    # eletromecânica / industrial
    "eletromecanica": "tecnico_eletromecanica",
    "eletromecânica": "tecnico_eletromecanica",
    "industrial": "tecnico_eletromecanica",
    "tecnico em eletromecanica": "tecnico_eletromecanica",
    "técnico em eletromecânica": "tecnico_eletromecanica",
    "tecnico_em_eletromecanica": "tecnico_eletromecanica",
    # eletrotécnica
    "eletrotecnica": "tecnico_eletrotecnica",
    "eletrotécnica": "tecnico_eletrotecnica",
    "tecnico em eletrotecnica": "tecnico_eletrotecnica",
    "técnico em eletrotécnica": "tecnico_eletrotecnica",
    "tecnico_em_eletrotecnica": "tecnico_eletrotecnica",
    # oratória / comunicação
    "oratoria": "curso_oratoria",
    "oratória": "curso_oratoria",
    "oratória profissional": "curso_oratoria",
    "oratoria profissional": "curso_oratoria",
    "curso de oratoria": "curso_oratoria",
    "curso de oratória": "curso_oratoria",
    "comunicacao oral": "curso_oratoria",
    "comunicação oral": "curso_oratoria",
    "comunicacao profissional": "curso_oratoria",
    "comunicação profissional": "curso_oratoria",
    "curso_oratoria": "curso_oratoria",
    # refrigeração
    "hvac": "refrigeracao_climatizacao",
    "refrigeracao": "refrigeracao_climatizacao",
    "refrigeração": "refrigeracao_climatizacao",
    "climatizacao": "refrigeracao_climatizacao",
    "climatização": "refrigeracao_climatizacao",
    "refrigeracao_climatizacao": "refrigeracao_climatizacao",
    # segurança do trabalho
    "seguranca do trabalho": "curso_seguranca_no_trabalho",
    "segurança do trabalho": "curso_seguranca_no_trabalho",
    "seguranca_do_trabalho": "curso_seguranca_no_trabalho",
    "tecnico em seguranca do trabalho": "curso_seguranca_no_trabalho",
    "técnico em segurança do trabalho": "curso_seguranca_no_trabalho",
    "tecnico_em_seguranca_do_trabalho": "curso_seguranca_no_trabalho",
    "curso_seguranca_no_trabalho": "curso_seguranca_no_trabalho",
    "sst": "curso_seguranca_no_trabalho",
    "sesmt": "curso_seguranca_no_trabalho",
    # logística
    "logistica": "curso_logistica",
    "logística": "curso_logistica",
    "tecnico em logistica": "curso_logistica",
    "técnico em logística": "curso_logistica",
    "tecnico_em_logistica": "curso_logistica",
    "curso_logistica": "curso_logistica",
    "supply chain": "curso_logistica",
}


def get_profile(area: str) -> dict:
    """
    Retorna uma cópia profunda do profile da área solicitada.

    Aceita chave canônica ou alias. Normaliza caixa e espaços.
    Lança ValueError para área vazia ou desconhecida — sem fallback silencioso.
    """
    if not area or not str(area).strip():
        raise ValueError(
            "Área não informada. Passe explicitamente o nome da área "
            "(ex.: 'administracao', 'enfermagem', 'tecnico_eletrotecnica')."
        )

    raw = str(area).strip().lower()
    key = _ALIASES.get(raw, raw)

    if key not in AREA_PROFILES:
        raise ValueError(
            f"Área '{area}' (normalizada: '{raw}') não encontrada. "
            f"Áreas disponíveis: {sorted(AREA_PROFILES.keys())}. "
            f"Aliases disponíveis: {sorted(_ALIASES.keys())}"
        )

    return copy.deepcopy(AREA_PROFILES[key])

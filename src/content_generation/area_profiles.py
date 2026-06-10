AREA_PROFILES = {
    "industrial": {
        "nome_area": "industrial",
        "nome_profissional": "técnico industrial",
        "ambientes_de_trabalho": [
            "chão de fábrica / linha de produção",
            "planta industrial / utilidades",
            "laboratório técnico / bancada de testes",
            "sala de controle / painel elétrico",
            "manutenção de campo (corretiva ou preventiva)",
            "comissionamento / startup de equipamentos",
        ],
        "equipamentos_tipicos": [
            "motor elétrico", "inversor de frequência", "CLP",
            "esteira transportadora", "bomba centrífuga", "compressor",
            "quadro de distribuição", "sistema de automação",
        ],
        "normas_regulamentadoras": ["NR-10", "NR-12", "NR-35"],
        "normas_tecnicas": ["ABNT/NBR"],
        "conselho_classe": "CREA/CFT",
        "lei_exercicio": None,
        "grandezas_tipicas": "tensões, correntes, potências, torques, rendimentos",
        "tecnologias_emergentes": "automação industrial, Indústria 4.0, IoT industrial, manutenção preditiva, gêmeo digital",
        "softwares_tipicos": "TIA Portal, WEG CFW, FluidSIM, Factory I/O",
        "epis_tipicos": "capacete, óculos de segurança, luvas isolantes, calçado de segurança, protetor auricular",
        "procedimentos_seguranca_chave": "bloqueio e etiquetagem (LOTO), análise preliminar de risco (APR), permissão de trabalho (PT)",
        "vocabulario_proibido": [],
        "regras_terminologia_obrigatorias": [],
        "referencias_oficiais_obrigatorias": [],
    },

    "saude": {
        "nome_area": "saúde",
        "nome_profissional": "técnico em enfermagem",
        "ambientes_de_trabalho": [
            "enfermaria / unidade de internação hospitalar",
            "unidade de terapia intensiva (UTI)",
            "centro cirúrgico e sala de recuperação pós-anestésica (SRPA)",
            "pronto-socorro / unidade de emergência",
            "ambulatório e consultório",
            "unidade básica de saúde (UBS) e Estratégia Saúde da Família (ESF)",
            "centro de material e esterilização (CME)",
            "atenção domiciliar (home care)",
            "maternidade / alojamento conjunto / berçário",
        ],
        "equipamentos_tipicos": [
            "esfigmomanômetro e estetoscópio", "oxímetro de pulso",
            "monitor multiparamétrico", "bomba de infusão",
            "cama hospitalar e colchão de prevenção de LPP",
            "carro de emergência e desfibrilador (DEA)",
            "aspirador de secreções", "glicosímetro",
            "balança antropométrica", "termômetro digital",
            "material para punção venosa periférica",
            "material para curativo e sondagens",
        ],
        "normas_regulamentadoras": ["NR-32 (segurança em serviços de saúde)", "NR-6 (EPI)"],
        "normas_tecnicas": [
            "RDC ANVISA aplicáveis",
            "Resoluções do COFEN",
            "Manuais e Protocolos do Ministério da Saúde",
        ],
        "conselho_classe": "COFEN / COREN",
        "lei_exercicio": "Lei nº 7.498/1986 (Lei do Exercício Profissional da Enfermagem) e Decreto nº 94.406/1987",
        "grandezas_tipicas": "sinais vitais (PA, FC, FR, T, SpO2), dor (escalas), diurese, balanço hídrico, escala de Glasgow, escala de Braden",
        "tecnologias_emergentes": "prontuário eletrônico do paciente (PEP), telemedicina e teleconsulta de enfermagem, dispositivos vestíveis de monitoramento, SAE (Sistematização da Assistência de Enfermagem) digital",
        "softwares_tipicos": "sistemas de prontuário eletrônico hospitalar, e-SUS APS, sistema do PNI (SI-PNI)",
        "epis_tipicos": "luvas de procedimento e estéreis, máscara cirúrgica e N95/PFF2, óculos de proteção, avental/capote, gorro, propé",
        "procedimentos_seguranca_chave": "higienização das mãos (5 momentos da OMS), precauções padrão, precauções de contato/gotículas/aerossóis, descarte de perfurocortantes (caixa de descarte rígida), 9 certos da administração de medicamentos, prevenção de eventos adversos e cultura de segurança do paciente",
        "vocabulario_proibido": [
            "chão de fábrica", "fábrica", "linha de produção", "planta industrial",
            "técnico industrial", "operário", "máquina industrial",
            "inversor de frequência", "CLP", "motor elétrico",
            "NR-10", "NR-12", "NR-35", "torque", "escorregamento",
            "CREA", "CFT", "LOTO", "TIA Portal", "WEG CFW",
            "Indústria 4.0", "gêmeo digital",
        ],
        "regras_terminologia_obrigatorias": [
            "Use SEMPRE 'LPP – Lesão por Pressão' (termo NPUAP/EPUAP/PPPIA 2016). NUNCA use 'úlcera por pressão', 'úlcera de pressão' ou 'escara'.",
            "Use 'paciente', 'cliente' ou 'usuário do serviço de saúde'. NUNCA use 'cliente industrial', 'operário' ou termos de ambiente fabril.",
            "Use 'sinais vitais' (PA, FC, FR, T, SpO2) e não 'medições/leituras de instrumentos'.",
            "Ao falar de medicamentos, sempre cite os '9 certos' (paciente, medicamento, dose, via, hora, registro, ação esperada, forma e resposta).",
            "Ao falar de prevenção de infecção, sempre cite os '5 momentos da higienização das mãos' (OMS).",
            "Ao falar de feridas, classifique por estágios (I a IV, não classificável, tissular profunda) conforme NPUAP.",
            "Ao falar de PCR, siga as diretrizes da AHA vigente para SBV e suporte avançado de vida.",
            "Ao falar de calendário vacinal, mencione obrigatoriamente o portal do Ministério da Saúde como fonte atualizada.",
            "Use a Lei nº 7.498/1986 e o Decreto nº 94.406/1987 ao falar de competências legais do técnico de enfermagem.",
            "Use 'SAE — Sistematização da Assistência de Enfermagem' e 'Processo de Enfermagem' (Resolução COFEN 358/2009) ao falar de organização do cuidado.",
        ],
        "referencias_oficiais_obrigatorias": [
            "Portal do Ministério da Saúde — https://www.gov.br/saude/pt-br",
            "Calendário Nacional de Vacinação (PNI) — https://www.gov.br/saude/pt-br/assuntos/saude-de-a-a-z/c/calendario-nacional-de-vacinacao",
            "COFEN — https://www.cofen.gov.br",
            "ANVISA — https://www.gov.br/anvisa/pt-br",
            "DATASUS — https://datasus.saude.gov.br",
        ],
    },
}


def get_profile(area: str) -> dict:
    """Retorna o perfil da área. Faz fallback para 'industrial' se a área não for reconhecida."""
    key = (area or "industrial").strip().lower()
    aliases = {
        "enfermagem": "saude",
        "saúde": "saude",
        "tecnico em enfermagem": "saude",
        "técnico em enfermagem": "saude",
    }
    key = aliases.get(key, key)
    if key not in AREA_PROFILES:
        print(f"[area_profiles] Perfil '{area}' não encontrado, usando 'industrial' como padrão.")
        key = "industrial"
    return AREA_PROFILES[key]

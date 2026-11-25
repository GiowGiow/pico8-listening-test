"""The opening questionnaire: six questions, every one answered by picking an option.

The research package names the six fields but leaves the categories to the
app, so they are defined here under a version. An answer is stored as the
option's code; the export writes the code and VERSION, and the labels below
are the record of what each code meant.
"""

VERSION = "2026-11-25"

FIELDS = [
    {
        "name": "age_range",
        "label": "Qual é a sua faixa etária?",
        "options": [
            ("under_18", "Menos de 18 anos"),
            ("18_24", "18 a 24 anos"),
            ("25_34", "25 a 34 anos"),
            ("35_44", "35 a 44 anos"),
            ("45_54", "45 a 54 anos"),
            ("55_plus", "55 anos ou mais"),
        ],
    },
    {
        "name": "musical_experience",
        "label": "Qual é a sua experiência musical?",
        "options": [
            ("none", "Nenhuma"),
            ("hobby", "Toco ou canto por hobby, sem estudo formal"),
            ("formal", "Estudei ou estudo música (aulas, curso, conservatório)"),
            ("professional", "Trabalho com música"),
        ],
    },
    {
        "name": "gaming_frequency",
        "label": "Com que frequência você joga videogame?",
        "options": [
            ("never", "Nunca ou quase nunca"),
            ("monthly", "Algumas vezes por mês"),
            ("weekly", "Algumas vezes por semana"),
            ("daily", "Todos os dias ou quase"),
        ],
    },
    {
        "name": "retro_familiarity",
        "label": "Quanto você conhece de jogos retrô ou de 8 bits?",
        "options": [
            ("none", "Nada"),
            ("little", "Pouco"),
            ("some", "Razoavelmente"),
            ("much", "Muito"),
        ],
    },
    {
        "name": "region",
        "label": "Em que região você mora?",
        "options": [
            ("norte", "Norte"),
            ("nordeste", "Nordeste"),
            ("centro_oeste", "Centro-Oeste"),
            ("sudeste", "Sudeste"),
            ("sul", "Sul"),
            ("exterior", "Fora do Brasil"),
        ],
    },
    {
        "name": "headphones",
        "label": "Você está usando fones de ouvido agora?",
        "options": [
            ("yes", "Sim"),
            ("no", "Não"),
        ],
    },
]

CODES = {field["name"]: {code for code, _ in field["options"]} for field in FIELDS}
LABELS = {field["name"]: dict(field["options"]) for field in FIELDS}


def public():
    return {
        "version": VERSION,
        "fields": [
            {"name": f["name"], "label": f["label"],
             "options": [{"value": code, "label": label} for code, label in f["options"]]}
            for f in FIELDS
        ],
    }

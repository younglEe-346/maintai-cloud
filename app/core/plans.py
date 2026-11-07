"""Plans d'abonnement (tableau 2.3 du sujet)."""

PLANS = {
    "FREE": {
        "label": "Gratuit",
        "max_machines": 2,
        "max_measures_per_day": 10_000,
        "custom_model": False,  # modèle commun
        "export": False,
    },
    "PRO": {
        "label": "Pro",
        "max_machines": 50,
        "max_measures_per_day": 1_000_000,
        "custom_model": True,   # modèle réentraîné sur les données de l'usine
        "export": True,
    },
}


def plan_of(org) -> dict:
    return PLANS.get(org.plan, PLANS["FREE"])

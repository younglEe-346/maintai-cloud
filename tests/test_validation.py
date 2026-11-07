from app.services.validation import check_measure

OK = {"message_id": "m1", "air_temp": 298.1, "process_temp": 308.6,
      "rotational_speed": 1551, "torque": 42.8, "tool_wear": 0}


def test_mesure_valide():
    m, reasons = check_measure(OK)
    assert reasons == [] and m.message_id == "m1"


def test_valeur_physiquement_impossible():
    m, reasons = check_measure({**OK, "torque": -5})
    assert m is None and "torque = -5" in reasons[0] and "physiquement impossible" in reasons[0]


def test_plusieurs_raisons_en_meme_temps():
    _, reasons = check_measure({**OK, "air_temp": 900, "tool_wear": 5000})
    assert len(reasons) == 2


def test_champ_manquant_et_mauvais_type():
    _, reasons = check_measure({"message_id": "m", "air_temp": "chaud"})
    assert any("air_temp : doit être un nombre" in r for r in reasons)
    assert any("torque : champ obligatoire manquant" in r for r in reasons)


def test_message_id_obligatoire():
    _, reasons = check_measure({k: v for k, v in OK.items() if k != "message_id"})
    assert reasons == ["message_id : champ obligatoire manquant"]


def test_infini_refuse():
    _, reasons = check_measure({**OK, "torque": float("inf")})
    assert reasons and "nombre fini" in reasons[0]


def test_mesure_qui_n_est_pas_un_objet():
    assert check_measure([1, 2])[1] == ["la mesure doit être un objet JSON"]


def test_valeur_inhabituelle_mais_possible_acceptee():
    # couple très élevé : risque de panne, mais pas impossible -> c'est au modèle de juger
    m, reasons = check_measure({**OK, "torque": 95})
    assert reasons == []


def test_label_retour_terrain():
    m, _ = check_measure({**OK, "label": {"failure": True, "modes": ["HDF", "OSF"]}})
    assert m.label.failure and m.label.modes == ["HDF", "OSF"]
    _, reasons = check_measure({**OK, "label": {"failure": True, "modes": ["XYZ"]}})
    assert "mode inconnu" in reasons[0]

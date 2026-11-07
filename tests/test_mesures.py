"""Réception des mesures : validation, déduplication, quarantaine, calcul du risque."""
from helpers import API, ai4i_rows, create_machine, register, send


def setup(client):
    owner = register(client)
    machine = create_machine(client, owner)
    return owner, machine


def test_lot_valide_accepte_et_risque_calcule(client):
    owner, machine = setup(client)
    rows = ai4i_rows([0, 1, 50])  # 2 cycles normaux + 1 vraie panne (PWF)
    r = send(client, machine["api_key"], rows)
    assert r.status_code == 202
    assert r.json() == {"accepted": 3, "duplicates": [], "rejected": []}

    mesures = client.get(f"{API}/machines/{machine['id']}/mesures", headers=owner["headers"]).json()
    assert len(mesures) == 3
    assert all(m["prediction"] and m["prediction"]["model_version"] for m in mesures)
    panne = next(m for m in mesures if m["message_id"] == rows[2]["message_id"])
    assert panne["prediction"]["decision"] is True
    assert panne["prediction"]["probable_mode"] == "PWF"


def test_deduplication_par_message_id(client):
    _, machine = setup(client)
    rows = ai4i_rows([0, 1])
    assert send(client, machine["api_key"], rows).json()["accepted"] == 2
    again = send(client, machine["api_key"], rows).json()
    assert again["accepted"] == 0
    assert sorted(again["duplicates"]) == sorted(r["message_id"] for r in rows)


def test_doublon_dans_le_meme_lot(client):
    _, machine = setup(client)
    row = ai4i_rows([0])[0]
    r = send(client, machine["api_key"], [row, row]).json()
    assert r["accepted"] == 1 and r["duplicates"] == [row["message_id"]]


def test_meme_message_id_sur_deux_machines_est_accepte(client):
    owner, m1 = setup(client)
    m2 = create_machine(client, owner, "CNC-2")
    row = ai4i_rows([0])[0]
    assert send(client, m1["api_key"], [row]).json()["accepted"] == 1
    assert send(client, m2["api_key"], [row]).json()["accepted"] == 1


def test_quarantaine_avec_raisons(client):
    owner, machine = setup(client)
    good = ai4i_rows([0])[0]
    bad = {**ai4i_rows([1])[0], "torque": -3}
    broken = {"message_id": "casse", "air_temp": "chaud"}
    r = send(client, machine["api_key"], [good, bad, broken]).json()
    assert r["accepted"] == 1
    assert [x["index"] for x in r["rejected"]] == [1, 2]
    assert "physiquement impossible" in r["rejected"][0]["reasons"][0]

    q = client.get(f"{API}/quarantaine", headers=owner["headers"]).json()
    assert {x["message_id"] for x in q} == {bad["message_id"], "casse"}
    assert all(x["reasons"] for x in q)


def test_lot_vide_ou_trop_gros(client):
    _, machine = setup(client)
    assert send(client, machine["api_key"], []).status_code == 422
    assert send(client, machine["api_key"], [{}] * 1001).status_code == 413


def test_cle_invalide(client):
    assert send(client, "maint_fausse", ai4i_rows([0])).status_code == 401


def test_label_retour_terrain_enregistre(client):
    owner, machine = setup(client)
    rows = ai4i_rows([50], with_label=True)
    send(client, machine["api_key"], rows)
    m = client.get(f"{API}/machines/{machine['id']}/mesures", headers=owner["headers"]).json()[0]
    assert m["label_failure"] is True and m["label_modes"] == ["PWF"]

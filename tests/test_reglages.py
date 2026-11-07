"""Coûts réglables : le ratio de coût change le seuil optimal, appliqué par le worker."""
import pytest

from helpers import API, ai4i_rows, create_machine, invite_and_join, register, send

DEFAULTS = {"cost_ratio": 50, "alert_open_k": 1, "alert_close_k": 3, "alert_close_factor": 0.5}


def put(client, user, **changes):
    return client.put(f"{API}/org/settings", json={**DEFAULTS, **changes}, headers=user["headers"])


def test_reglages_par_defaut(client):
    owner = register(client)
    s = client.get(f"{API}/org/settings", headers=owner["headers"]).json()
    assert (s["cost_ratio"], s["alert_open_k"], s["alert_close_k"], s["alert_close_factor"]) == (50, 1, 3, 0.5)
    assert s["threshold_high"] == pytest.approx(0.022, abs=0.002)
    assert s["threshold_low"] == pytest.approx(s["threshold_high"] * 0.5)
    assert s["expected"]["evaluated_on"] == 10_000


def test_le_ratio_de_cout_change_le_seuil(client):
    owner = register(client)
    seuils = {}
    for ratio in (10, 50, 100):
        seuils[ratio] = put(client, owner, cost_ratio=ratio).json()["threshold_high"]
    # une panne manquée plus chère -> on alerte plus tôt -> seuil plus bas
    assert seuils[10] > seuils[50] > seuils[100]
    assert seuils[10] == pytest.approx(0.227, abs=0.002)


def test_apercu_sans_enregistrer(client):
    owner = register(client)
    p = client.get(f"{API}/org/settings/preview", params={"cost_ratio": 10}, headers=owner["headers"]).json()
    assert p["threshold"] == pytest.approx(0.227, abs=0.002)
    assert client.get(f"{API}/org/settings", headers=owner["headers"]).json()["cost_ratio"] == 50


def test_le_worker_applique_le_nouveau_seuil(client):
    owner = register(client)
    m = create_machine(client, owner)
    nouveau = put(client, owner, cost_ratio=10).json()["threshold_high"]
    send(client, m["api_key"], ai4i_rows([0]))
    mesure = client.get(f"{API}/machines/{m['id']}/mesures", headers=owner["headers"]).json()[0]
    assert mesure["prediction"]["threshold"] == pytest.approx(nouveau)


def test_seul_le_responsable_regle(client):
    owner = register(client)
    tech = invite_and_join(client, owner, "member")
    admin = invite_and_join(client, owner, "admin")
    assert put(client, tech, cost_ratio=10).status_code == 403
    assert put(client, admin, cost_ratio=10).status_code == 200
    assert client.get(f"{API}/org/settings", headers=tech["headers"]).status_code == 200


def test_ratio_extreme_ne_casse_pas_le_worker(client):
    owner = register(client)
    m = create_machine(client, owner)
    assert put(client, owner, cost_ratio=10_000).json()["threshold_high"] == 0
    assert send(client, m["api_key"], ai4i_rows([0])).status_code == 202
    mesure = client.get(f"{API}/machines/{m['id']}/mesures", headers=owner["headers"]).json()[0]
    assert mesure["prediction"]["decision"] is True  # seuil 0 : on alerte sur tout


@pytest.mark.parametrize("bad", [{"cost_ratio": 0}, {"cost_ratio": -5}, {"alert_open_k": 0},
                                 {"alert_close_factor": 1}, {"alert_close_factor": 0}])
def test_valeurs_invalides(client, bad):
    owner = register(client)
    assert put(client, owner, **bad).status_code == 422

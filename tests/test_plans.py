"""Plans d'abonnement : limite de machines, quota de mesures par jour, changement de plan."""
import pytest

from app.core.plans import PLANS
from helpers import API, ai4i_rows, create_machine, invite_and_join, register, send


def org(client, user):
    return client.get(f"{API}/org", headers=user["headers"]).json()


def test_gratuit_limite_a_2_machines(client):
    owner = register(client)
    m1 = create_machine(client, owner, "A")
    create_machine(client, owner, "B")
    r = client.post(f"{API}/machines", json={"name": "C"}, headers=owner["headers"])
    assert r.status_code == 402 and "Limite du plan Gratuit" in r.json()["detail"]
    # archiver une machine libère une place
    assert client.delete(f"{API}/machines/{m1['id']}", headers=owner["headers"]).status_code == 204
    create_machine(client, owner, "C")


def test_machine_archivee_n_envoie_plus(client):
    owner = register(client)
    m = create_machine(client, owner)
    client.delete(f"{API}/machines/{m['id']}", headers=owner["headers"])
    assert send(client, m["api_key"], ai4i_rows([0])).status_code == 401


def test_passage_au_plan_pro_par_le_proprietaire(client):
    owner = register(client)
    admin = invite_and_join(client, owner, "admin")
    assert client.put(f"{API}/org/plan", json={"plan": "PRO"}, headers=admin["headers"]).status_code == 403
    r = client.put(f"{API}/org/plan", json={"plan": "PRO"}, headers=owner["headers"])
    assert r.status_code == 200 and r.json()["limits"]["max_machines"] == 50
    for name in "ABC":
        create_machine(client, owner, name)
    # retour au Gratuit impossible avec 3 machines actives
    r = client.put(f"{API}/org/plan", json={"plan": "FREE"}, headers=owner["headers"])
    assert r.status_code == 409 and "Archivez" in r.json()["detail"]


def test_plan_inconnu_refuse(client):
    owner = register(client)
    assert client.put(f"{API}/org/plan", json={"plan": "GOLD"}, headers=owner["headers"]).status_code == 422


def test_quota_journalier_de_mesures(client, monkeypatch):
    monkeypatch.setitem(PLANS["FREE"], "max_measures_per_day", 5)
    owner = register(client)
    m = create_machine(client, owner)
    r = send(client, m["api_key"], ai4i_rows([0, 1, 2]))
    assert r.status_code == 202 and r.json()["quota"] == {"used_today": 3, "limit": 5}

    assert send(client, m["api_key"], ai4i_rows([3])).status_code == 202
    assert org(client, owner)["measures_today"] == 4

    over = send(client, m["api_key"], ai4i_rows([4, 5]))
    assert over.status_code == 429 and "Quota journalier" in over.json()["detail"]
    assert int(over.headers["Retry-After"]) > 0
    assert org(client, owner)["measures_today"] == 4  # le lot refusé n'est pas compté

    # le plan Pro a son propre plafond
    client.put(f"{API}/org/plan", json={"plan": "PRO"}, headers=owner["headers"])
    assert send(client, m["api_key"], ai4i_rows([4, 5])).status_code == 202


def test_doublons_hors_quota(client, monkeypatch):
    monkeypatch.setitem(PLANS["FREE"], "max_measures_per_day", 5)
    owner = register(client)
    m = create_machine(client, owner)
    rows = ai4i_rows([0, 1])
    send(client, m["api_key"], rows)
    again = send(client, m["api_key"], rows)
    assert again.json()["accepted"] == 0
    assert org(client, owner)["measures_today"] == 2


@pytest.mark.parametrize("plan,machines,measures", [("FREE", 2, 10_000), ("PRO", 50, 1_000_000)])
def test_limites_du_sujet(plan, machines, measures):
    assert PLANS[plan]["max_machines"] == machines
    assert PLANS[plan]["max_measures_per_day"] == measures
    assert PLANS[plan]["custom_model"] is (plan == "PRO") and PLANS[plan]["export"] is (plan == "PRO")

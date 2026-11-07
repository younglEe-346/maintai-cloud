"""Super-administrateur : suivi des usines et des workers, sans accès aux données privées."""
from app.cli import create_superadmin
from helpers import API, ai4i_rows, auth, create_machine, register, send, uid


def superadmin(client):
    email, password = f"{uid('sa')}@maintai.local", "motdepasse123"
    create_superadmin(email, password, "Équipe MaintAI")
    r = client.post(f"{API}/auth/login", data={"username": email, "password": password})
    return {"headers": auth(r.json()["access_token"])}


def test_liste_des_usines_avec_indicateurs(client):
    sa = superadmin(client)
    owner = register(client)
    m = create_machine(client, owner)
    send(client, m["api_key"], ai4i_rows([0, 1, 50]))
    org_id = client.get(f"{API}/auth/me", headers=owner["headers"]).json()["organization"]["id"]

    orgs = client.get(f"{API}/admin/organizations", headers=sa["headers"]).json()
    row = next(o for o in orgs if o["id"] == org_id)
    assert row["plan"] == "FREE" and row["members"] == 1 and row["machines"] == 1
    assert row["measures_today"] == 3 and row["active_alerts"] == 1 and row["last_measure_at"]
    assert row["model"].startswith("risk_model_v")
    assert "api_key" not in str(row)  # aucune donnée sensible


def test_changer_le_plan_d_une_usine(client):
    sa = superadmin(client)
    owner = register(client)
    org_id = client.get(f"{API}/auth/me", headers=owner["headers"]).json()["organization"]["id"]
    r = client.put(f"{API}/admin/organizations/{org_id}/plan", json={"plan": "PRO"}, headers=sa["headers"])
    assert r.status_code == 200 and r.json()["plan"] == "PRO"
    assert client.get(f"{API}/org", headers=owner["headers"]).json()["plan"] == "PRO"
    assert client.put(f"{API}/admin/organizations/inconnue/plan", json={"plan": "PRO"},
                      headers=sa["headers"]).status_code == 404


def test_etat_des_workers(client):
    sa = superadmin(client)
    r = client.get(f"{API}/admin/workers", headers=sa["headers"])
    assert r.status_code == 200 and isinstance(r.json()["workers"], list)


def test_reserve_au_super_administrateur(client):
    owner = register(client)
    assert client.get(f"{API}/admin/organizations", headers=owner["headers"]).status_code == 403
    assert client.get(f"{API}/admin/workers", headers=owner["headers"]).status_code == 403
    assert client.get(f"{API}/admin/organizations").status_code == 401


def test_le_super_administrateur_ne_voit_pas_les_donnees_des_usines(client):
    sa = superadmin(client)
    # il n'appartient à aucune usine : les routes des usines lui sont fermées
    assert client.get(f"{API}/machines", headers=sa["headers"]).status_code == 403
    assert client.get(f"{API}/alerts", headers=sa["headers"]).status_code == 403
    me = client.get(f"{API}/auth/me", headers=sa["headers"]).json()
    assert me["is_superadmin"] is True and me["organization"] is None


def test_creation_refusee_pour_un_compte_d_usine(client):
    import pytest
    owner = register(client)
    with pytest.raises(ValueError):
        create_superadmin(owner["email"], "motdepasse123", "X")

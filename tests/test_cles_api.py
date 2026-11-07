"""Clés d'API des machines : montrées une seule fois, hachées, révocables, remplaçables."""
from app.core.security import hash_token
from helpers import API, ai4i_rows, create_machine, invite_and_join, register, send


def test_cle_montree_une_seule_fois(client):
    owner = register(client)
    m = create_machine(client, owner)
    assert m["api_key"].startswith("maint_") and "plus jamais" in m["warning"]
    listed = client.get(f"{API}/machines", headers=owner["headers"]).json()[0]
    assert "api_key" not in listed
    assert listed["api_key_prefix"] == m["api_key"][:12]


def test_cle_stockee_hachee(client):
    from app.db.session import SessionLocal
    from app.models.models import Machine

    owner = register(client)
    m = create_machine(client, owner)
    db = SessionLocal()
    row = db.get(Machine, m["id"])
    assert row.api_key_hash == hash_token(m["api_key"]) and row.api_key_hash != m["api_key"]
    assert not hasattr(row, "api_key")
    db.close()


def test_revocation(client):
    owner = register(client)
    m = create_machine(client, owner)
    assert send(client, m["api_key"], ai4i_rows([0])).status_code == 202
    r = client.post(f"{API}/machines/{m['id']}/api-key/revoke", headers=owner["headers"])
    assert r.status_code == 200 and r.json()["api_key_revoked_at"]
    assert send(client, m["api_key"], ai4i_rows([1])).status_code == 401


def test_remplacement_de_cle(client):
    owner = register(client)
    m = create_machine(client, owner)
    r = client.post(f"{API}/machines/{m['id']}/api-key/rotate", headers=owner["headers"])
    assert r.status_code == 200
    new_key = r.json()["api_key"]
    assert new_key != m["api_key"]
    assert send(client, m["api_key"], ai4i_rows([0])).status_code == 401   # l'ancienne ne marche plus
    assert send(client, new_key, ai4i_rows([0])).status_code == 202        # la nouvelle oui


def test_remplacement_apres_revocation(client):
    owner = register(client)
    m = create_machine(client, owner)
    client.post(f"{API}/machines/{m['id']}/api-key/revoke", headers=owner["headers"])
    new_key = client.post(f"{API}/machines/{m['id']}/api-key/rotate", headers=owner["headers"]).json()["api_key"]
    assert send(client, new_key, ai4i_rows([0])).status_code == 202


def test_technicien_ne_gere_pas_les_cles(client):
    owner = register(client)
    m = create_machine(client, owner)
    tech = invite_and_join(client, owner, "member")
    assert client.post(f"{API}/machines/{m['id']}/api-key/revoke", headers=tech["headers"]).status_code == 403
    assert client.post(f"{API}/machines/{m['id']}/api-key/rotate", headers=tech["headers"]).status_code == 403


def test_autre_usine_ne_touche_pas_aux_cles(client):
    a, b = register(client), register(client)
    m = create_machine(client, a)
    assert client.post(f"{API}/machines/{m['id']}/api-key/revoke", headers=b["headers"]).status_code == 404
    assert send(client, m["api_key"], ai4i_rows([0])).status_code == 202

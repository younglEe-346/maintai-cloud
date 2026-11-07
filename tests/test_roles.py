"""Utilisateurs, rôles (propriétaire / administrateur / membre) et invitations."""
from datetime import datetime, timedelta

from app.services.email import OUTBOX
from helpers import API, auth, create_machine, invitation_token, invite_and_join, register, uid


def me(client, user):
    return client.get(f"{API}/auth/me", headers=user["headers"]).json()


def test_inscription_cree_usine_et_proprietaire(client):
    owner = register(client, full_name="Soulaimane Lbah")
    info = me(client, owner)
    assert info["role"] == "owner" and info["full_name"] == "Soulaimane Lbah"
    assert info["organization"]["plan"] == "FREE"


def test_connexion_et_mauvais_mot_de_passe(client):
    owner = register(client)
    ok = client.post(f"{API}/auth/login", data={"username": owner["email"].upper(), "password": owner["password"]})
    assert ok.status_code == 200  # l'e-mail n'est pas sensible à la casse
    bad = client.post(f"{API}/auth/login", data={"username": owner["email"], "password": "faux-mot-de-passe"})
    assert bad.status_code == 400


def test_email_deja_utilise_et_mot_de_passe_trop_court(client):
    owner = register(client)
    body = {"org_name": uid("U"), "full_name": "X", "email": owner["email"], "password": "motdepasse123"}
    assert client.post(f"{API}/auth/register", json=body).status_code == 400
    body = {"org_name": uid("U"), "full_name": "X", "email": f"{uid()}@x.ma", "password": "court"}
    assert client.post(f"{API}/auth/register", json=body).status_code == 422


def test_invitation_par_email_puis_acceptation(client):
    owner = register(client)
    email = f"{uid('tech')}@ensam.ma"
    r = client.post(f"{API}/org/invitations", json={"email": email, "role": "member"}, headers=owner["headers"])
    assert r.status_code == 201 and r.json()["email_sent"] is True
    mail = next(m for m in reversed(OUTBOX) if m["to"] == email)
    assert "Invitation" in mail["subject"] and "?invitation=" in mail["body"]
    token = invitation_token(OUTBOX, email)

    info = client.get(f"{API}/auth/invitations/{token}").json()
    assert info["email"] == email and info["role"] == "member"

    r = client.post(f"{API}/auth/accept-invitation",
                    json={"token": token, "full_name": "Jamal", "password": "motdepasse123"})
    assert r.status_code == 200
    tech = {"headers": auth(r.json()["access_token"])}
    assert me(client, tech)["role"] == "member"
    assert me(client, tech)["organization"]["id"] == me(client, owner)["organization"]["id"]

    # le lien ne sert qu'une fois
    again = client.post(f"{API}/auth/accept-invitation",
                        json={"token": token, "full_name": "X", "password": "motdepasse123"})
    assert again.status_code == 409


def test_invitation_annulee_ou_expiree(client):
    from app.db.session import SessionLocal
    from app.models.models import Invitation

    owner = register(client)
    email = f"{uid()}@ensam.ma"
    inv = client.post(f"{API}/org/invitations", json={"email": email}, headers=owner["headers"]).json()
    token = invitation_token(OUTBOX, email)
    assert client.delete(f"{API}/org/invitations/{inv['id']}", headers=owner["headers"]).status_code == 204
    assert client.get(f"{API}/auth/invitations/{token}").status_code == 404

    email2 = f"{uid()}@ensam.ma"
    inv2 = client.post(f"{API}/org/invitations", json={"email": email2}, headers=owner["headers"]).json()
    token2 = invitation_token(OUTBOX, email2)
    db = SessionLocal()
    db.get(Invitation, inv2["id"]).expires_at = datetime.utcnow() - timedelta(minutes=1)
    db.commit()
    db.close()
    assert client.get(f"{API}/auth/invitations/{token2}").status_code == 410


def test_le_jeton_d_invitation_n_est_pas_stocke_en_clair(client):
    from app.db.session import SessionLocal
    from app.models.models import Invitation

    owner = register(client)
    email = f"{uid()}@ensam.ma"
    inv = client.post(f"{API}/org/invitations", json={"email": email}, headers=owner["headers"]).json()
    token = invitation_token(OUTBOX, email)
    db = SessionLocal()
    assert db.get(Invitation, inv["id"]).token_hash != token
    db.close()


def test_droits_du_membre(client):
    owner = register(client)
    tech = invite_and_join(client, owner, "member")
    # un technicien consulte mais ne configure pas
    assert client.get(f"{API}/machines", headers=tech["headers"]).status_code == 200
    assert client.post(f"{API}/machines", json={"name": "X"}, headers=tech["headers"]).status_code == 403
    r = client.post(f"{API}/org/invitations", json={"email": f"{uid()}@x.ma"}, headers=tech["headers"])
    assert r.status_code == 403
    assert client.get(f"{API}/org/members", headers=tech["headers"]).status_code == 200


def test_droits_de_l_administrateur(client):
    owner = register(client)
    admin = invite_and_join(client, owner, "admin")
    assert client.post(f"{API}/machines", json={"name": "X"}, headers=admin["headers"]).status_code in (200, 201)
    # un administrateur invite des membres, mais pas des administrateurs
    ok = client.post(f"{API}/org/invitations", json={"email": f"{uid()}@x.ma", "role": "member"},
                     headers=admin["headers"])
    assert ok.status_code == 201
    no = client.post(f"{API}/org/invitations", json={"email": f"{uid()}@x.ma", "role": "admin"},
                     headers=admin["headers"])
    assert no.status_code == 403


def test_seul_le_proprietaire_change_les_roles(client):
    owner = register(client)
    admin = invite_and_join(client, owner, "admin")
    tech = invite_and_join(client, owner, "member")
    tech_id = me(client, tech)["id"]
    assert client.patch(f"{API}/org/members/{tech_id}", json={"role": "admin"},
                        headers=admin["headers"]).status_code == 403
    r = client.patch(f"{API}/org/members/{tech_id}", json={"role": "admin"}, headers=owner["headers"])
    assert r.status_code == 200 and r.json()["role"] == "admin"
    owner_id = me(client, owner)["id"]
    assert client.patch(f"{API}/org/members/{owner_id}", json={"role": "member"},
                        headers=owner["headers"]).status_code == 400


def test_membre_retire_ne_peut_plus_se_connecter(client):
    owner = register(client)
    tech = invite_and_join(client, owner, "member")
    tech_id = me(client, tech)["id"]
    assert client.delete(f"{API}/org/members/{tech_id}", headers=owner["headers"]).status_code == 204
    assert client.get(f"{API}/machines", headers=tech["headers"]).status_code == 401
    members = client.get(f"{API}/org/members", headers=owner["headers"]).json()
    assert tech_id not in [m["id"] for m in members]


def test_isolation_entre_usines(client):
    a, b = register(client), register(client)
    machine = create_machine(client, a)
    assert client.get(f"{API}/machines", headers=b["headers"]).json() == []
    assert client.get(f"{API}/machines/{machine['id']}/mesures", headers=b["headers"]).status_code == 404
    tech_a = invite_and_join(client, a, "member")
    tech_a_id = me(client, tech_a)["id"]
    # l'usine B ne peut ni voir ni retirer un membre de l'usine A
    assert tech_a_id not in [m["id"] for m in client.get(f"{API}/org/members", headers=b["headers"]).json()]
    assert client.delete(f"{API}/org/members/{tech_a_id}", headers=b["headers"]).status_code == 404


def test_sans_jeton_401(client):
    assert client.get(f"{API}/machines").status_code == 401
    assert client.get(f"{API}/machines", headers=auth("faux.jeton.jwt")).status_code == 401

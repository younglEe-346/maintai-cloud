"""Invitations : un seul lien valable par e-mail, et un ancien membre peut rejoindre une autre usine."""
from helpers import API, auth, invitation_token, invite_and_join, register, uid


def inviter(client, owner, email):
    r = client.post(f"{API}/org/invitations", json={"email": email, "role": "member"}, headers=owner["headers"])
    assert r.status_code == 201, r.text
    return r.json()


def test_deux_invitations_meme_email_seul_le_dernier_lien_marche(client):
    from app.services.email import OUTBOX
    owner = register(client)
    email = f"{uid('collegue')}@ensam.ma"
    inviter(client, owner, email)
    premier = invitation_token(OUTBOX, email)
    inviter(client, owner, email)
    dernier = invitation_token(OUTBOX, email)
    assert premier != dernier

    assert client.get(f"{API}/auth/invitations/{premier}").status_code == 404   # annulée
    assert client.get(f"{API}/auth/invitations/{dernier}").status_code == 200
    r = client.post(f"{API}/auth/accept-invitation",
                    json={"token": dernier, "full_name": "Jamal Lachguer", "password": "motdepasse123"})
    assert r.status_code == 200, r.text


def test_la_liste_montre_une_seule_invitation_en_attente(client):
    owner = register(client)
    email = f"{uid('collegue')}@ensam.ma"
    inviter(client, owner, email)
    inviter(client, owner, email)
    rows = [i for i in client.get(f"{API}/org/invitations", headers=owner["headers"]).json() if i["email"] == email]
    assert len(rows) == 2                                             # l'historique est gardé
    assert sum(1 for i in rows if not i.get("revoked_at") and not i.get("accepted_at")) == 1


def test_une_invitation_d_une_autre_usine_ou_email_n_est_pas_annulee(client):
    from app.services.email import OUTBOX
    a, b = register(client), register(client)
    email, autre = f"{uid('x')}@ensam.ma", f"{uid('y')}@ensam.ma"
    inviter(client, a, email)
    tok_a = invitation_token(OUTBOX, email)
    inviter(client, b, email)        # autre usine, même e-mail
    inviter(client, a, autre)        # même usine, autre e-mail
    assert client.get(f"{API}/auth/invitations/{tok_a}").status_code == 200


def test_ancien_membre_d_une_usine_peut_rejoindre_une_autre(client):
    from app.services.email import OUTBOX
    a, b = register(client), register(client)
    membre = invite_and_join(client, a, "member")
    membre_id = client.get(f"{API}/auth/me", headers=membre["headers"]).json()["id"]
    assert client.delete(f"{API}/org/members/{membre_id}", headers=a["headers"]).status_code == 204

    inviter(client, b, membre["email"])                    # l'usine B l'invite : accepté
    token = invitation_token(OUTBOX, membre["email"])
    r = client.post(f"{API}/auth/accept-invitation",
                    json={"token": token, "full_name": "Jamal Lachguer", "password": "nouveaumdp123"})
    assert r.status_code == 200, r.text                    # avant : 409 « compte existant »

    moi = client.get(f"{API}/auth/me", headers=auth(r.json()["access_token"])).json()
    assert moi["id"] == membre_id and moi["organization"]["name"] != ""
    ids_b = [m["id"] for m in client.get(f"{API}/org/members", headers=b["headers"]).json()]
    ids_a = [m["id"] for m in client.get(f"{API}/org/members", headers=a["headers"]).json()]
    assert membre_id in ids_b and membre_id not in ids_a   # il n'est plus dans l'usine A


def test_compte_actif_toujours_refuse(client):
    a, b = register(client), register(client)
    membre = invite_and_join(client, a, "member")
    r = client.post(f"{API}/org/invitations", json={"email": membre["email"]}, headers=b["headers"])
    assert r.status_code == 409                            # un compte actif ne peut pas être invité ailleurs

"""Limite de connexion : 5 échecs en 15 minutes pour un e-mail -> 429, même avec le bon mot de passe."""
from app.config import LOGIN_MAX_FAILURES
from app.services.usage import _redis
from helpers import API, register


def login(client, email, password):
    return client.post(f"{API}/auth/login", data={"username": email, "password": password})


def test_apres_5_echecs_meme_le_bon_mot_de_passe_est_bloque(client):
    owner = register(client)
    for _ in range(LOGIN_MAX_FAILURES):
        assert login(client, owner["email"], "faux-mot-de-passe").status_code == 400
    r = login(client, owner["email"], owner["password"])  # le bon mot de passe, mais trop tard
    assert r.status_code == 429
    assert "Trop de tentatives" in r.json()["detail"] and "minute" in r.json()["detail"]
    assert 0 < int(r.headers["Retry-After"]) <= 15 * 60


def test_un_succes_remet_le_compteur_a_zero(client):
    owner = register(client)
    for _ in range(2):
        assert login(client, owner["email"], "faux-mot-de-passe").status_code == 400
    assert login(client, owner["email"], owner["password"]).status_code == 200
    assert _redis().get(f"login_fail:{owner['email']}") is None  # compteur supprimé
    for _ in range(LOGIN_MAX_FAILURES - 1):                       # il repart de zéro : pas encore bloqué
        assert login(client, owner["email"], "faux-mot-de-passe").status_code == 400
    assert login(client, owner["email"], owner["password"]).status_code == 200


def test_le_blocage_d_un_e_mail_ne_touche_pas_les_autres(client):
    a, b = register(client), register(client)
    for _ in range(LOGIN_MAX_FAILURES):
        login(client, a["email"], "faux-mot-de-passe")
    assert login(client, a["email"], a["password"]).status_code == 429
    assert login(client, b["email"], b["password"]).status_code == 200


def test_majuscules_et_e_mail_inconnu(client):
    owner = register(client)
    for _ in range(LOGIN_MAX_FAILURES):  # « A@X.MA » et « a@x.ma » partagent le même compteur
        login(client, owner["email"].upper(), "faux-mot-de-passe")
    assert login(client, owner["email"], owner["password"]).status_code == 429
    inconnu = "personne-n-existe@ensam.ma"  # un e-mail inexistant est limité aussi (rien n'est révélé)
    _redis().delete(f"login_fail:{inconnu}")
    for _ in range(LOGIN_MAX_FAILURES):
        assert login(client, inconnu, "x" * 8).status_code == 400
    assert login(client, inconnu, "x" * 8).status_code == 429


def test_le_compteur_expire(client):
    owner = register(client)
    login(client, owner["email"], "faux-mot-de-passe")
    ttl = _redis().ttl(f"login_fail:{owner['email']}")
    assert 0 < ttl <= 15 * 60  # la clé s'efface toute seule : pas de ménage à faire

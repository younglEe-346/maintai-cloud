"""Sécurité et isolation des usines : tests transversaux.

Règle centrale du sujet : « une usine ne voit jamais les machines, les mesures ni le
modèle d'une autre usine ». On vérifie ici, route par route, qu'un responsable de
l'usine B n'obtient RIEN de l'usine A.
"""
from datetime import datetime, timedelta

from jose import jwt

from app.config import ALGORITHM, SECRET_KEY
from helpers import API, ai4i_rows, auth, create_machine, invite_and_join, register, send


def org_id(client, user):
    return client.get(f"{API}/auth/me", headers=user["headers"]).json()["organization"]["id"]


def test_isolation_complete_entre_deux_usines(client):
    a, b = register(client), register(client)
    for user in (a, b):
        client.put(f"{API}/org/plan", json={"plan": "PRO"}, headers=user["headers"])
    m = create_machine(client, a, "Machine secrète de A")
    send(client, m["api_key"], ai4i_rows([50]) + [{"message_id": "q", "torque": -1}])
    alert_id = client.get(f"{API}/alerts", headers=a["headers"]).json()[0]["id"]
    invite_and_join(client, a, "member")
    client.put(f"{API}/org/settings", json={"cost_ratio": 10, "alert_open_k": 2, "alert_close_k": 3,
                                            "alert_close_factor": 0.5}, headers=a["headers"])

    H = b["headers"]
    # listes : vides pour B
    assert client.get(f"{API}/machines", headers=H).json() == []
    assert client.get(f"{API}/alerts", headers=H).json() == []
    assert client.get(f"{API}/quarantaine", headers=H).json() == []
    assert len(client.get(f"{API}/org/members", headers=H).json()) == 1  # seulement son propriétaire
    assert client.get(f"{API}/org/models", headers=H).json()["history"] == []
    assert client.get(f"{API}/export/mesures.csv", headers=H).content.decode("utf-8-sig").count("\n") == 1
    # accès direct par identifiant : 404 (on ne révèle même pas l'existence)
    assert client.get(f"{API}/machines/{m['id']}/mesures", headers=H).status_code == 404
    assert client.get(f"{API}/alerts/{alert_id}", headers=H).status_code == 404
    assert client.post(f"{API}/alerts/{alert_id}/acknowledge", headers=H, json={}).status_code == 404
    assert client.post(f"{API}/machines/{m['id']}/api-key/revoke", headers=H).status_code == 404
    assert client.delete(f"{API}/machines/{m['id']}", headers=H).status_code == 404
    # les réglages de A n'ont pas touché B
    assert client.get(f"{API}/org/settings", headers=H).json()["cost_ratio"] == 50
    # A n'a rien perdu
    assert len(client.get(f"{API}/machines/{m['id']}/mesures", headers=a["headers"]).json()) == 1


def test_la_cle_d_une_machine_ne_donne_acces_qu_a_l_envoi(client):
    a = register(client)
    m = create_machine(client, a)
    # une clé de machine n'est pas un jeton de connexion
    assert client.get(f"{API}/machines", headers=auth(m["api_key"])).status_code == 401


def test_jeton_falsifie_ou_expire(client):
    a = register(client)
    me = client.get(f"{API}/auth/me", headers=a["headers"]).json()
    forged = jwt.encode({"sub": me["id"], "exp": datetime.utcnow() + timedelta(hours=1)},
                        "pas-la-bonne-cle", algorithm=ALGORITHM)
    assert client.get(f"{API}/machines", headers=auth(forged)).status_code == 401
    expired = jwt.encode({"sub": me["id"], "exp": datetime.utcnow() - timedelta(minutes=1)},
                         SECRET_KEY, algorithm=ALGORITHM)
    assert client.get(f"{API}/machines", headers=auth(expired)).status_code == 401


def test_mot_de_passe_hache_avec_bcrypt(client):
    from app.db.session import SessionLocal
    from app.models.models import User

    a = register(client)
    db = SessionLocal()
    user = db.query(User).filter(User.email == a["email"]).one()
    assert user.password_hash.startswith("$2") and a["password"] not in user.password_hash
    db.close()


def test_cors_limite_aux_sites_autorises(client):
    def preflight(origin):
        return client.options(f"{API}/machines", headers={"Origin": origin, "Access-Control-Request-Method": "GET"})
    assert preflight("http://localhost:8501").headers.get("access-control-allow-origin") == "http://localhost:8501"
    assert "access-control-allow-origin" not in preflight("https://site-malveillant.example").headers

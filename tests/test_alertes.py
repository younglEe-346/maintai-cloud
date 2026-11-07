"""Alertes de bout en bout : hystérésis réelle (worker), acquittement, isolation."""
from helpers import API, ai4i_rows, create_machine, invite_and_join, register, send

NORMAUX = [0, 1, 2, 3]  # cycles normaux AI4I : risque ~0


def alerts(client, owner, **params):
    r = client.get(f"{API}/alerts", headers=owner["headers"], params=params)
    assert r.status_code == 200, r.text
    return r.json()


def test_ouverture_puis_fermeture_avec_k_par_defaut(client):
    owner = register(client)
    m = create_machine(client, owner)
    send(client, m["api_key"], ai4i_rows([50]))           # K = 1 par défaut : ouverture
    active = alerts(client, owner, status="active")
    assert len(active) == 1 and active[0]["probable_mode"] == "PWF"

    send(client, m["api_key"], ai4i_rows([160, 3236]))    # toujours une seule alerte
    assert len(alerts(client, owner, status="active")) == 1

    send(client, m["api_key"], ai4i_rows(NORMAUX[:3]))    # 3 mesures basses : fermeture
    assert alerts(client, owner, status="active") == []
    closed = alerts(client, owner, status="CLOSED")
    assert len(closed) == 1 and closed[0]["closed_at"] and closed[0]["peak_risk_score"] > 0.9


def test_acquittement(client):
    owner = register(client)
    m = create_machine(client, owner)
    send(client, m["api_key"], ai4i_rows([50]))
    alert_id = alerts(client, owner, status="active")[0]["id"]

    tech = invite_and_join(client, owner, "member", full_name="Miloud Oujakka")
    r = client.post(f"{API}/alerts/{alert_id}/acknowledge", headers=tech["headers"],
                    json={"comment": "Couple anormal, outil changé"})
    assert r.status_code == 200
    a = r.json()
    assert a["status"] == "ACKNOWLEDGED" and a["acknowledged_by_name"] == "Miloud Oujakka"
    assert a["ack_comment"] == "Couple anormal, outil changé" and a["acknowledged_at"]

    # deuxième acquittement refusé
    again = client.post(f"{API}/alerts/{alert_id}/acknowledge", headers=owner["headers"], json={})
    assert again.status_code == 409

    # une alerte acquittée reste active : pas de nouvelle alerte si le risque reste haut
    send(client, m["api_key"], ai4i_rows([160]))
    assert [x["id"] for x in alerts(client, owner, status="active")] == [alert_id]

    # elle se ferme quand le risque redescend
    send(client, m["api_key"], ai4i_rows(NORMAUX[:3]))
    assert client.get(f"{API}/alerts/{alert_id}", headers=owner["headers"]).json()["status"] == "CLOSED"
    closed = client.post(f"{API}/alerts/{alert_id}/acknowledge", headers=owner["headers"], json={})
    assert closed.status_code == 409


def test_une_usine_ne_voit_pas_les_alertes_d_une_autre(client):
    a, b = register(client), register(client)
    m = create_machine(client, a)
    send(client, m["api_key"], ai4i_rows([50]))
    alert_id = alerts(client, a, status="active")[0]["id"]
    assert alerts(client, b) == []
    assert client.get(f"{API}/alerts/{alert_id}", headers=b["headers"]).status_code == 404
    r = client.post(f"{API}/alerts/{alert_id}/acknowledge", headers=b["headers"], json={})
    assert r.status_code == 404

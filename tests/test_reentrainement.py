"""Réentraînement Pro : modèle candidat entraîné sur les données de l'usine, promu s'il est meilleur."""
import pytest

from helpers import API, ai4i_rows, create_machine, invite_and_join, register, send


def pro_org_with_labeled_data(client, n_rows=1500):
    owner = register(client)
    client.put(f"{API}/org/plan", json={"plan": "PRO"}, headers=owner["headers"])
    m = create_machine(client, owner)
    rows = ai4i_rows(range(n_rows), with_label=True)   # vraies lignes AI4I + leur vraie étiquette
    for i in range(0, len(rows), 1000):
        assert send(client, m["api_key"], rows[i:i + 1000]).json()["accepted"] == len(rows[i:i + 1000])
    return owner, m


def retrain(client, owner):
    return client.post(f"{API}/org/models/retrain", headers=owner["headers"])


def overview(client, owner):
    return client.get(f"{API}/org/models", headers=owner["headers"]).json()


def test_reserve_au_plan_pro(client):
    owner = register(client)
    assert retrain(client, owner).status_code == 402


def test_reserve_au_responsable(client):
    owner = register(client)
    client.put(f"{API}/org/plan", json={"plan": "PRO"}, headers=owner["headers"])
    tech = invite_and_join(client, owner, "member")
    assert retrain(client, tech).status_code == 403


def test_pas_assez_de_donnees_etiquetees(client):
    owner, _ = pro_org_with_labeled_data(client, n_rows=50)
    assert retrain(client, owner).status_code == 202
    job = overview(client, owner)["history"][0]
    assert job["status"] == "failed" and "Pas assez de données étiquetées" in job["message"]
    assert overview(client, owner)["current_model"].startswith("risk_model_v")  # toujours le commun


def test_reentrainement_complet(client, monkeypatch):
    owner, m = pro_org_with_labeled_data(client)

    # 1. comparaison honnête : le candidat est promu seulement s'il coûte moins cher
    r = retrain(client, owner)
    assert r.status_code == 202 and r.json()["version"] == 1
    job = overview(client, owner)["history"][0]
    assert job["status"] in ("active", "rejected")
    metrics = job["metrics"]
    assert metrics["labeled_rows"] == 1500 and metrics["failures"] == 42
    assert metrics["promoted"] == (metrics["candidate"]["cost"] < metrics["current"]["cost"])

    # 2. on force le cas "le modèle actuel est mauvais" pour tester la promotion
    import app.ml.retraining as retraining
    real_evaluate = retraining.evaluate

    def current_is_bad(artifact, X, y, threshold, ratio):
        result = real_evaluate(artifact, X, y, threshold, ratio)
        if "name" in artifact:  # modèle actuel (le candidat n'a pas encore de nom)
            result["cost"] = 1e9  # il perd la comparaison
        return result

    monkeypatch.setattr(retraining, "evaluate", current_is_bad)
    assert retrain(client, owner).status_code == 202
    ov = overview(client, owner)
    job2 = ov["history"][0]
    assert job2["version"] == 2 and job2["status"] == "active", job2["message"]
    assert ov["current_model"] == job2["name"]

    # 3. les nouvelles mesures sont prédites avec le modèle de l'usine
    send(client, m["api_key"], ai4i_rows([5000]))
    last = client.get(f"{API}/machines/{m['id']}/mesures", params={"limit": 1}, headers=owner["headers"]).json()[0]
    assert last["prediction"]["model_version"] == job2["name"]
    assert client.get(f"{API}/org/settings", headers=owner["headers"]).json()["model_version"] == job2["name"]

    # 4. une autre usine Pro n'utilise jamais ce modèle
    other = register(client)
    client.put(f"{API}/org/plan", json={"plan": "PRO"}, headers=other["headers"])
    assert overview(client, other)["current_model"].startswith("risk_model_v")
    assert overview(client, other)["history"] == []

    # 5. repasser en Gratuit -> retour au modèle commun
    client.put(f"{API}/org/plan", json={"plan": "FREE"}, headers=owner["headers"])
    assert overview(client, owner)["current_model"].startswith("risk_model_v")


def test_un_seul_reentrainement_a_la_fois(client):
    from app.db.session import SessionLocal
    from app.models.models import Organization, OrgModel, User

    owner = register(client)
    client.put(f"{API}/org/plan", json={"plan": "PRO"}, headers=owner["headers"])
    me = client.get(f"{API}/auth/me", headers=owner["headers"]).json()
    db = SessionLocal()
    db.add(OrgModel(org_id=me["organization"]["id"], version=1, name="en-cours", status="training"))
    db.commit()
    db.close()
    assert retrain(client, owner).status_code == 409


@pytest.mark.parametrize("n", [0])
def test_aucune_donnee(client, n):
    owner = register(client)
    client.put(f"{API}/org/plan", json={"plan": "PRO"}, headers=owner["headers"])
    retrain(client, owner)
    assert overview(client, owner)["history"][0]["status"] == "failed"

"""Export CSV (plan Pro) : contenu, filtres, droits, isolation."""
import csv
import io

from helpers import API, ai4i_rows, create_machine, invite_and_join, register, send


def pro(client):
    owner = register(client)
    client.put(f"{API}/org/plan", json={"plan": "PRO"}, headers=owner["headers"])
    return owner


def read_csv(response):
    text = response.content.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text), delimiter=";"))


def test_reserve_au_plan_pro(client):
    owner = register(client)
    assert client.get(f"{API}/export/mesures.csv", headers=owner["headers"]).status_code == 402


def test_reserve_au_responsable(client):
    owner = pro(client)
    tech = invite_and_join(client, owner, "member")
    assert client.get(f"{API}/export/mesures.csv", headers=tech["headers"]).status_code == 403


def test_export_des_mesures_avec_predictions(client):
    owner = pro(client)
    m = create_machine(client, owner, "Tour CN")
    send(client, m["api_key"], ai4i_rows([0, 50], with_label=True))
    r = client.get(f"{API}/export/mesures.csv", headers=owner["headers"])
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    rows = read_csv(r)
    assert len(rows) == 2 and {row["machine"] for row in rows} == {"Tour CN"}
    panne = next(row for row in rows if row["label_failure"] == "True")
    assert panne["probable_mode"] == "PWF" and panne["decision"] == "True" and panne["model_version"]
    assert panne["label_modes"] == "PWF"


def test_filtre_par_machine(client):
    owner = pro(client)
    m1, m2 = create_machine(client, owner, "A"), create_machine(client, owner, "B")
    send(client, m1["api_key"], ai4i_rows([0]))
    send(client, m2["api_key"], ai4i_rows([1, 2]))
    r = client.get(f"{API}/export/mesures.csv", params={"machine_id": m2["id"]}, headers=owner["headers"])
    assert [row["machine"] for row in read_csv(r)] == ["B", "B"]


def test_export_des_alertes(client):
    owner = pro(client)
    m = create_machine(client, owner)
    send(client, m["api_key"], ai4i_rows([50]))
    rows = read_csv(client.get(f"{API}/export/alertes.csv", headers=owner["headers"]))
    assert len(rows) == 1 and rows[0]["status"] == "OPEN" and rows[0]["probable_mode"] == "PWF"


def test_une_usine_n_exporte_que_ses_donnees(client):
    a, b = pro(client), pro(client)
    ma = create_machine(client, a, "Machine A")
    send(client, ma["api_key"], ai4i_rows([0, 1]))
    assert read_csv(client.get(f"{API}/export/mesures.csv", headers=b["headers"])) == []
    r = client.get(f"{API}/export/mesures.csv", params={"machine_id": ma["id"]}, headers=b["headers"])
    assert read_csv(r) == []

"""Simulateur multi-usines : découpage d'AI4I, erreurs injectées, rejeu de bout en bout."""
import random

from helpers import API
from simulator.stream_simulator import inject_errors, load_ai4i, run, setup, split_rows, to_measure

SMALL = [("Usine A", "FREE", ["M1"]), ("Usine B", "PRO", ["M2", "M3"])]


def test_decoupage_couvre_tout_le_fichier_sans_recouvrement():
    df = load_ai4i()
    parts = split_rows(df, 7)
    assert len(parts) == 7 and sum(len(p) for p in parts) == len(df) == 10_000
    assert parts[0]["UDI"].iloc[-1] + 1 == parts[1]["UDI"].iloc[0]  # tranches consécutives


def test_mesure_construite_depuis_une_vraie_ligne():
    row = load_ai4i().iloc[50]
    m = to_measure(row, "Tour", with_label=True)
    assert m["message_id"] == "Tour-51" and m["torque"] == row["Torque [Nm]"]
    assert m["label"] == {"failure": True, "modes": ["PWF"]}


def test_erreurs_injectees():
    batch = [{"message_id": f"m{i}", "torque": 40.0, "air_temp": 300.0, "rotational_speed": 1500.0}
             for i in range(200)]
    out = inject_errors(batch, 0.1, random.Random(0))
    faux = [m for m in out if m["message_id"].endswith("-faux")]
    assert faux and all(m["torque"] < 0 or m["air_temp"] > 400 or m["rotational_speed"] < 0 for m in faux)
    assert len(out) > len(batch) + len(faux)  # il y a aussi des doublons


def test_rejeu_de_bout_en_bout_sur_plusieurs_usines(client):
    config = setup(client, base=API, factories=SMALL, tag="t" + random.choice("abcdef") + str(random.randint(0, 999)))
    assert [f["plan"] for f in config["factories"]] == ["FREE", "PRO"]
    df = load_ai4i().iloc[:90]
    stats = run(lambda: client, config, df, batch=15, delay=0, labels=True, errors=0.05,
                parallel=False, verbose=False)
    assert stats["acceptées"] == 90           # toutes les vraies lignes sont arrivées
    assert stats["quarantaine"] > 0           # les erreurs injectées sont en quarantaine
    assert stats["doublons"] > 0              # les doublons sont détectés
    # chaque usine ne voit que ses machines
    owner = config["factories"][1]
    tok = client.post(f"{API}/auth/login", data={"username": owner["email"], "password": owner["password"]})
    machines = client.get(f"{API}/machines", headers={"Authorization": f"Bearer {tok.json()['access_token']}"})
    assert sorted(m["name"] for m in machines.json()) == ["M2", "M3"]

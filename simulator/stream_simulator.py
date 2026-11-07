"""Simulateur : rejoue AI4I 2020 sur les machines de plusieurs usines en même temps.

1. Créer les usines de démonstration (comptes + machines), sauvegardés dans simulator/config.json :
       python -m simulator.stream_simulator setup
2. Rejouer AI4I (un thread par machine, toutes les usines en parallèle) :
       python -m simulator.stream_simulator run --labels --errors 0.02
3. Les deux d'un coup :
       python -m simulator.stream_simulator demo

Options utiles : --batch 25 (mesures par lot), --delay 1.0 (secondes entre deux lots),
--rows 2000 (ne rejouer qu'une partie), --labels (envoie le retour terrain AI4I, utile
au réentraînement Pro), --errors 0.02 (2 % de mesures impossibles + quelques doublons,
pour montrer la quarantaine et la déduplication).

Aucune donnée n'est inventée : les mesures sont les vraies lignes du fichier AI4I.
Les erreurs injectées (--errors) sont volontairement fausses et signalées comme telles.
"""
import argparse
import json
import os
import random
import secrets
import sys
import threading
import time
from collections import Counter
from pathlib import Path

import pandas as pd
import requests

API_URL = os.getenv("API_URL", "http://localhost:8000/api/v1")
DATA = Path(__file__).resolve().parents[1] / "data" / "ai4i2020.csv"
CONFIG = Path(__file__).resolve().parent / "config.json"

SENSORS = {"Air temperature [K]": "air_temp", "Process temperature [K]": "process_temp",
           "Rotational speed [rpm]": "rotational_speed", "Torque [Nm]": "torque",
           "Tool wear [min]": "tool_wear"}
MODES = ["TWF", "HDF", "PWF", "OSF", "RNF"]

# Usines de démonstration : (nom, plan, machines)
DEMO_FACTORIES = [
    ("Usine Casablanca", "PRO", ["Tour CN-01", "Fraiseuse-02", "Centre d'usinage-03"]),
    ("Usine Rabat", "FREE", ["Tour CN-R1", "Perceuse-R2"]),
    ("Usine Tanger", "FREE", ["Fraiseuse-T1", "Tour CN-T2"]),
]


# ---------------------------------------------------------------- données

def load_ai4i(path: Path = DATA) -> pd.DataFrame:
    if not path.exists():
        sys.exit(f"Fichier introuvable : {path}. Téléchargez AI4I 2020 depuis UCI (DOI 10.24432/C5HS5C).")
    return pd.read_csv(path, encoding="utf-8-sig")


def to_measure(row, machine_name: str, with_label: bool) -> dict:
    m = {"message_id": f"{machine_name}-{int(row['UDI'])}"}
    m.update({api: float(row[col]) for col, api in SENSORS.items()})
    if with_label:
        m["label"] = {"failure": bool(row["Machine failure"]), "modes": [x for x in MODES if row[x] == 1]}
    return m


def split_rows(df: pd.DataFrame, n_machines: int) -> list[pd.DataFrame]:
    """Découpe AI4I en tranches consécutives, une par machine (dans l'ordre du fichier)."""
    size = -(-len(df) // n_machines)  # division arrondie au-dessus
    return [df.iloc[i * size:(i + 1) * size] for i in range(n_machines)]


def inject_errors(batch: list[dict], rate: float, rng: random.Random) -> list[dict]:
    """Ajoute des erreurs VOLONTAIRES pour la démo : valeurs impossibles et doublons."""
    out = []
    for m in batch:
        if rng.random() < rate:
            bad = dict(m, message_id=m["message_id"] + "-faux")
            field, value = rng.choice([("torque", -12.0), ("air_temp", 900.0), ("rotational_speed", -50.0)])
            bad[field] = value
            out.append(bad)
        out.append(m)
        if rng.random() < rate:
            out.append(dict(m))  # doublon : même message_id renvoyé
    return out


# ---------------------------------------------------------------- mise en place

def setup(http, base: str = API_URL, factories=DEMO_FACTORIES, tag: str | None = None) -> dict:
    """Crée les usines, passe les usines Pro en Pro, déclare les machines. Renvoie la config."""
    tag = tag or secrets.token_hex(2)
    config = {"api_url": base, "tag": tag, "factories": []}
    for name, plan, machines in factories:
        slug = name.split()[-1].lower()
        email = f"responsable.{slug}.{tag}@maintai-demo.ma"
        password = f"demo-{secrets.token_hex(4)}"
        r = http.post(f"{base}/auth/register", json={"org_name": f"{name} ({tag})", "full_name": f"Responsable {name}",
                                                      "email": email, "password": password})
        r.raise_for_status()
        headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
        if plan == "PRO":
            http.put(f"{base}/org/plan", json={"plan": "PRO"}, headers=headers).raise_for_status()
        created = []
        for machine in machines:
            r = http.post(f"{base}/machines", json={"name": machine}, headers=headers)
            r.raise_for_status()
            created.append({"id": r.json()["id"], "name": machine, "api_key": r.json()["api_key"]})
        config["factories"].append({"name": f"{name} ({tag})", "plan": plan, "email": email,
                                    "password": password, "machines": created})
        print(f"  {name} ({tag}) [{plan}] : {len(created)} machines — connexion : {email} / {password}")
    return config


# ---------------------------------------------------------------- envoi

def replay_machine(http, base: str, machine: dict, rows: pd.DataFrame, batch: int, delay: float,
                   labels: bool, errors: float, seed: int, stats: Counter, lock: threading.Lock,
                   verbose: bool = True) -> None:
    rng = random.Random(seed)
    measures = [to_measure(r, machine["name"], labels) for _, r in rows.iterrows()]
    headers = {"x-api-key": machine["api_key"]}
    for i in range(0, len(measures), batch):
        lot = inject_errors(measures[i:i + batch], errors, rng) if errors else measures[i:i + batch]
        r = http.post(f"{base}/mesures", json=lot, headers=headers)
        with lock:
            if r.status_code == 202:
                body = r.json()
                stats["acceptées"] += body["accepted"]
                stats["doublons"] += len(body["duplicates"])
                stats["quarantaine"] += len(body["rejected"])
                if verbose:
                    print(f"  {machine['name']:<22} lot {i // batch + 1:>4} : {body['accepted']:>3} acceptées, "
                          f"{len(body['duplicates'])} doublons, {len(body['rejected'])} en quarantaine")
            else:
                stats[f"erreurs HTTP {r.status_code}"] += 1
                print(f"  {machine['name']:<22} lot {i // batch + 1:>4} : HTTP {r.status_code} {r.text[:120]}")
                if r.status_code in (401, 402, 429):
                    return  # clé révoquée ou quota atteint : cette machine s'arrête
        if delay:
            time.sleep(delay)


def run(http_factory, config: dict, df: pd.DataFrame, batch: int, delay: float, labels: bool,
        errors: float, parallel: bool = True, verbose: bool = True) -> Counter:
    base = config["api_url"]
    machines = [m for f in config["factories"] for m in f["machines"]]
    slices = split_rows(df, len(machines))
    stats, lock, threads = Counter(), threading.Lock(), []
    print(f"Rejeu de {len(df)} lignes AI4I sur {len(machines)} machines de {len(config['factories'])} usines "
          f"(lots de {batch}, {delay}s entre deux lots{', avec retour terrain' if labels else ''}"
          f"{f', {errors:.0%} d erreurs injectées' if errors else ''})")
    for k, (machine, rows) in enumerate(zip(machines, slices)):
        args = (http_factory(), base, machine, rows, batch, delay, labels, errors, k, stats, lock, verbose)
        if parallel:  # un thread par machine : toutes les usines envoient en même temps
            t = threading.Thread(target=replay_machine, args=args, daemon=True)
            t.start()
            threads.append(t)
        else:
            replay_machine(*args)
    for t in threads:
        t.join()
    print("Bilan :", dict(stats))
    return stats


# ---------------------------------------------------------------- ligne de commande

def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="python -m simulator.stream_simulator", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["setup", "run", "demo"])
    parser.add_argument("--batch", type=int, default=25)
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--rows", type=int, default=None, help="nombre de lignes AI4I à rejouer (défaut : toutes)")
    parser.add_argument("--labels", action="store_true", help="envoie le retour terrain (étiquettes AI4I)")
    parser.add_argument("--errors", type=float, default=0.0, help="taux d'erreurs injectées (ex. 0.02)")
    parser.add_argument("--quiet", action="store_true", help="n'affiche que le bilan")
    args = parser.parse_args(argv)

    if args.command in ("setup", "demo"):
        print(f"Création des usines de démonstration sur {API_URL} ...")
        config = setup(requests.Session())
        CONFIG.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Configuration (comptes et clés) enregistrée dans {CONFIG}")
    if args.command in ("run", "demo"):
        if not CONFIG.exists():
            sys.exit("Pas de configuration : lancez d'abord  python -m simulator.stream_simulator setup")
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        df = load_ai4i()
        if args.rows:
            df = df.iloc[:args.rows]
        run(requests.Session, config, df, args.batch, args.delay, args.labels, args.errors,
            verbose=not args.quiet)


if __name__ == "__main__":
    main()

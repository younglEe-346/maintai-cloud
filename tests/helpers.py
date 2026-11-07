"""Fonctions communes aux tests d'intégration."""
import uuid
from pathlib import Path

import pandas as pd

from app.ml.features import from_ai4i

API = "/api/v1"
DATA = next((p for p in (Path("data/ai4i2020.csv"), Path("/app/data/ai4i2020.csv")) if p.exists()), None)


def uid(prefix: str = "x") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def register(client, plan: str | None = None) -> dict:
    """Crée une usine ; renvoie {"headers", "email", "password"}."""
    email, password = f"{uid('owner')}@ensam.ma", "motdepasse123"
    body = {"org_name": uid("Usine"), "admin_email": email, "password": password}
    if plan:
        body["plan"] = plan
    r = client.post(f"{API}/auth/register", json=body)
    assert r.status_code == 200, r.text
    return {"headers": {"Authorization": f"Bearer {r.json()['access_token']}"},
            "email": email, "password": password}


def create_machine(client, owner: dict, name: str = "CNC") -> dict:
    r = client.post(f"{API}/machines", json={"name": name}, headers=owner["headers"])
    assert r.status_code in (200, 201), r.text
    return r.json()


def send(client, api_key: str, measures: list):
    return client.post(f"{API}/mesures", json=measures, headers={"x-api-key": api_key})


def ai4i_rows(indexes, with_label: bool = False, prefix: str | None = None) -> list[dict]:
    """Vraies lignes AI4I au format de l'API (jamais de données inventées)."""
    if DATA is None:
        raise RuntimeError("data/ai4i2020.csv introuvable")
    df = pd.read_csv(DATA, encoding="utf-8-sig")
    sub = df.loc[list(indexes)]
    prefix = prefix or uid("msg")
    out = []
    for (_, row), measure in zip(sub.iterrows(), from_ai4i(sub).to_dict("records")):
        measure["message_id"] = f"{prefix}-{int(row['UDI'])}"
        if with_label:
            measure["label"] = {"failure": bool(row["Machine failure"]),
                                "modes": [m for m in ("TWF", "HDF", "PWF", "OSF", "RNF") if row[m] == 1]}
        out.append(measure)
    return out

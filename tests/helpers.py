"""Fonctions communes aux tests d'intégration."""
import uuid
from pathlib import Path

import pandas as pd

from app.ml.features import from_ai4i

API = "/api/v1"
DATA = next((p for p in (Path("data/ai4i2020.csv"), Path("/app/data/ai4i2020.csv")) if p.exists()), None)


def uid(prefix: str = "x") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def register(client, full_name: str = "Soulaimane Lbah") -> dict:
    """Crée une usine et son propriétaire ; renvoie {"headers", "email", "password"}."""
    email, password = f"{uid('owner')}@ensam.ma", "motdepasse123"
    body = {"org_name": uid("Usine"), "full_name": full_name, "email": email, "password": password}
    r = client.post(f"{API}/auth/register", json=body)
    assert r.status_code == 200, r.text
    return {"headers": auth(r.json()["access_token"]), "email": email, "password": password}


def invite_and_join(client, inviter: dict, role: str = "member", full_name: str = "Jamal Lachguer") -> dict:
    """Invite un collègue, lit le lien dans l'e-mail envoyé, accepte. Renvoie {"headers", "email"}."""
    from app.services.email import OUTBOX
    email = f"{uid(role)}@ensam.ma"
    r = client.post(f"{API}/org/invitations", json={"email": email, "role": role}, headers=inviter["headers"])
    assert r.status_code == 201, r.text
    token = invitation_token(OUTBOX, email)
    r = client.post(f"{API}/auth/accept-invitation",
                    json={"token": token, "full_name": full_name, "password": "motdepasse123"})
    assert r.status_code == 200, r.text
    return {"headers": auth(r.json()["access_token"]), "email": email}


def invitation_token(outbox, email: str) -> str:
    mail = next(m for m in reversed(outbox) if m["to"] == email)
    return mail["body"].split("?invitation=")[1].split()[0]


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

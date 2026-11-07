"""Mon usine : membres, rôles, invitations de collègues par e-mail."""
import secrets
from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.config import FRONTEND_URL, INVITATION_DAYS
from app.core.deps import ROLE_LABELS, get_current_org, get_current_user, require_roles
from app.core.security import hash_token
from app.db.session import get_db
from app.core.plans import PLANS, plan_of
from app.models.models import Invitation, Machine, Organization, User
from app.services.usage import measures_today
from app.ml.predictor import threshold_info
from app.ml.selection import model_for_org
from app.services.email import send_email

router = APIRouter()


class InvitationIn(BaseModel):
    email: EmailStr
    role: Literal["admin", "member"] = "member"


class RoleIn(BaseModel):
    role: Literal["admin", "member"]


def member_out(u: User) -> dict:
    return {"id": u.id, "email": u.email, "full_name": u.full_name, "role": u.role,
            "created_at": u.created_at}


def invitation_out(i: Invitation) -> dict:
    return {"id": i.id, "email": i.email, "role": i.role, "created_at": i.created_at,
            "expires_at": i.expires_at, "accepted_at": i.accepted_at, "revoked_at": i.revoked_at}


def get_member(user_id: str, org: Organization, db: Session) -> User:
    u = db.query(User).filter(User.id == user_id, User.org_id == org.id, User.is_active.is_(True)).first()
    if u is None:
        raise HTTPException(status_code=404, detail="Membre introuvable")
    return u


# ---------- Membres ----------

@router.get("/members")
def list_members(org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    users = (db.query(User).filter(User.org_id == org.id, User.is_active.is_(True))
             .order_by(User.created_at).all())
    return [member_out(u) for u in users]


@router.patch("/members/{user_id}")
def change_role(user_id: str, body: RoleIn,
                me: User = Depends(require_roles("owner")),
                org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    """Seul le propriétaire change les rôles. Le rôle de propriétaire ne se change pas ici."""
    u = get_member(user_id, org, db)
    if u.role == "owner":
        raise HTTPException(status_code=400, detail="Le rôle du propriétaire ne peut pas être modifié")
    u.role = body.role
    db.commit()
    return member_out(u)


@router.delete("/members/{user_id}", status_code=204)
def remove_member(user_id: str, me: User = Depends(require_roles("owner", "admin")),
                  org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    """Retire un membre de l'usine (son compte est désactivé, l'historique est gardé)."""
    u = get_member(user_id, org, db)
    if u.role == "owner":
        raise HTTPException(status_code=400, detail="Le propriétaire ne peut pas être retiré")
    if u.role == "admin" and me.role != "owner":
        raise HTTPException(status_code=403, detail="Seul le propriétaire peut retirer un administrateur")
    u.is_active = False
    db.commit()


# ---------- Invitations ----------

@router.post("/invitations", status_code=201)
def invite(body: InvitationIn, me: User = Depends(require_roles("owner", "admin")),
           org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    if body.role == "admin" and me.role != "owner":
        raise HTTPException(status_code=403, detail="Seul le propriétaire peut inviter un administrateur")
    email = body.email.lower()
    existing = db.query(User).filter(User.email == email).first()
    if existing is not None and existing.is_active:
        raise HTTPException(status_code=409, detail="Un compte existe déjà avec cet e-mail")

    token = secrets.token_urlsafe(32)  # envoyé par e-mail, jamais stocké en clair
    inv = Invitation(org_id=org.id, email=email, role=body.role, token_hash=hash_token(token),
                     invited_by_user_id=me.id,
                     expires_at=datetime.utcnow() + timedelta(days=INVITATION_DAYS))
    db.add(inv)
    db.commit()

    link = f"{FRONTEND_URL}/?invitation={token}"
    sent = send_email(
        to=email,
        subject=f"Invitation à rejoindre {org.name} sur MaintAI Cloud",
        body=(f"Bonjour,\n\n{me.full_name} vous invite à rejoindre l'usine « {org.name} » sur "
              f"MaintAI Cloud en tant que {ROLE_LABELS[body.role]}.\n\n"
              f"Pour accepter, ouvrez ce lien (valable {INVITATION_DAYS} jours) :\n{link}\n\n"
              f"Si vous n'attendiez pas cette invitation, ignorez cet e-mail."),
    )
    return {**invitation_out(inv), "email_sent": sent}


@router.get("/invitations")
def list_invitations(me: User = Depends(require_roles("owner", "admin")),
                     org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    rows = db.query(Invitation).filter(Invitation.org_id == org.id).order_by(Invitation.created_at.desc())
    return [invitation_out(i) for i in rows]


@router.delete("/invitations/{invitation_id}", status_code=204)
def revoke_invitation(invitation_id: str, me: User = Depends(require_roles("owner", "admin")),
                      org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    inv = db.query(Invitation).filter(Invitation.id == invitation_id, Invitation.org_id == org.id).first()
    if inv is None:
        raise HTTPException(status_code=404, detail="Invitation introuvable")
    if inv.accepted_at is None and inv.revoked_at is None:
        inv.revoked_at = datetime.utcnow()
        db.commit()


# ---------- Plan et usage ----------

class PlanIn(BaseModel):
    plan: Literal["FREE", "PRO"]


def usage_out(org: Organization, db: Session) -> dict:
    plan = plan_of(org)
    machines = db.query(Machine).filter(Machine.org_id == org.id, Machine.status == "ACTIVE").count()
    return {"plan": org.plan, "plan_label": plan["label"], "limits": plan,
            "machines": machines, "measures_today": measures_today(org.id)}


@router.get("")
def my_organization(user: User = Depends(get_current_user), org: Organization = Depends(get_current_org),
                    db: Session = Depends(get_db)):
    return {"id": org.id, "name": org.name, "created_at": org.created_at, "my_role": user.role,
            **usage_out(org, db)}


@router.put("/plan")
def change_plan(body: PlanIn, _: User = Depends(require_roles("owner")),
                org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    """Changement de plan par le propriétaire (paiement simulé : pas de vrai paiement)."""
    apply_plan(org, body.plan, db)
    db.commit()
    return usage_out(org, db)


def apply_plan(org: Organization, new_plan: str, db: Session) -> None:
    """Règle commune (propriétaire et super-administrateur)."""
    machines = db.query(Machine).filter(Machine.org_id == org.id, Machine.status == "ACTIVE").count()
    limit = PLANS[new_plan]["max_machines"]
    if machines > limit:
        raise HTTPException(status_code=409, detail=(
            f"Impossible de passer au plan {PLANS[new_plan]['label']} : {machines} machines actives "
            f"pour {limit} autorisées. Archivez d'abord des machines."))
    org.plan = new_plan


# ---------- Réglages : coûts et seuils ----------

class SettingsIn(BaseModel):
    cost_ratio: float = Field(gt=0, le=10_000, description="Coût d'une panne manquée / coût d'une fausse alerte")
    alert_open_k: int = Field(ge=1, le=50, description="Mesures hautes d'affilée pour ouvrir une alerte")
    alert_close_k: int = Field(ge=1, le=50, description="Mesures basses d'affilée pour fermer une alerte")
    alert_close_factor: float = Field(gt=0, lt=1, description="Seuil bas = facteur × seuil haut")


def settings_out(org: Organization, db: Session) -> dict:
    model = model_for_org(org, db)
    info = threshold_info(model, org.cost_ratio)
    return {
        "cost_ratio": org.cost_ratio, "alert_open_k": org.alert_open_k,
        "alert_close_k": org.alert_close_k, "alert_close_factor": org.alert_close_factor,
        "model_version": model["name"],
        "threshold_high": info["threshold"],
        "threshold_low": info["threshold"] * org.alert_close_factor,
        # ce que ce seuil aurait donné sur les données hors-échantillon du modèle
        "expected": {"recall": info["recall"], "precision": info["precision"],
                     "missed_failures": info["fn"], "false_alarms": info["fp"],
                     "evaluated_on": info["evaluated_on"]},
    }


@router.get("/settings")
def get_settings(org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    return settings_out(org, db)


@router.put("/settings")
def update_settings(body: SettingsIn, _: User = Depends(require_roles("owner", "admin")),
                    org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    """Le seuil optimal est recalculé tout de suite pour le nouveau ratio de coût ;
    le worker l'applique aux mesures suivantes."""
    org.cost_ratio = body.cost_ratio
    org.alert_open_k, org.alert_close_k = body.alert_open_k, body.alert_close_k
    org.alert_close_factor = body.alert_close_factor
    db.commit()
    return settings_out(org, db)


@router.get("/settings/preview")
def preview_threshold(cost_ratio: float = Query(gt=0, le=10_000),
                      org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    """Aperçu sans enregistrer : quel seuil pour ce ratio de coût ?"""
    model = model_for_org(org, db)
    info = threshold_info(model, cost_ratio)
    return {"cost_ratio": cost_ratio, "threshold": info["threshold"], "recall": info["recall"],
            "precision": info["precision"], "missed_failures": info["fn"], "false_alarms": info["fp"]}

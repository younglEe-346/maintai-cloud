"""Inscription d'une usine, connexion, profil, acceptation d'une invitation."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_account
from app.core.security import create_access_token, get_password_hash, hash_token, verify_password
from app.db.session import get_db
from app.models.models import Invitation, Organization, User
from app.schemas.schemas import Token

router = APIRouter()


class RegisterIn(BaseModel):
    org_name: str = Field(min_length=2, max_length=100)
    full_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class AcceptInvitationIn(BaseModel):
    token: str
    full_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=128)


def token_for(user: User) -> dict:
    return {"access_token": create_access_token({"sub": user.id}), "token_type": "bearer"}


def find_valid_invitation(token: str, db: Session) -> Invitation:
    inv = db.query(Invitation).filter(Invitation.token_hash == hash_token(token)).first()
    if inv is None or inv.revoked_at is not None:
        raise HTTPException(status_code=404, detail="Invitation introuvable ou annulée")
    if inv.accepted_at is not None:
        raise HTTPException(status_code=409, detail="Invitation déjà utilisée")
    if inv.expires_at < datetime.utcnow():
        raise HTTPException(status_code=410, detail="Invitation expirée : demandez-en une nouvelle")
    return inv


@router.post("/register", response_model=Token)
def register_organization(body: RegisterIn, db: Session = Depends(get_db)):
    """Crée une usine (plan Gratuit) et son propriétaire."""
    email = body.email.lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="Cet e-mail est déjà utilisé")
    if db.query(Organization).filter(Organization.name == body.org_name).first():
        raise HTTPException(status_code=400, detail="Ce nom d'usine est déjà utilisé")
    org = Organization(name=body.org_name, plan="FREE")
    db.add(org)
    db.flush()
    owner = User(org_id=org.id, email=email, full_name=body.full_name,
                 password_hash=get_password_hash(body.password), role="owner")
    db.add(owner)
    db.commit()
    return token_for(owner)


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Connexion : username = e-mail."""
    user = db.query(User).filter(User.email == form_data.username.lower()).first()
    if not user or not user.is_active or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=400, detail="E-mail ou mot de passe incorrect")
    return token_for(user)


@router.get("/me")
def me(user: User = Depends(get_current_account), db: Session = Depends(get_db)):
    org = db.get(Organization, user.org_id) if user.org_id else None
    return {"id": user.id, "email": user.email, "full_name": user.full_name, "role": user.role,
            "is_superadmin": user.is_superadmin,
            "organization": {"id": org.id, "name": org.name, "plan": org.plan} if org else None}


@router.get("/invitations/{token}")
def invitation_info(token: str, db: Session = Depends(get_db)):
    """Informations affichées sur la page d'acceptation (sans être connecté)."""
    inv = find_valid_invitation(token, db)
    return {"organization": inv.organization.name, "email": inv.email, "role": inv.role,
            "expires_at": inv.expires_at}


@router.post("/accept-invitation", response_model=Token)
def accept_invitation(body: AcceptInvitationIn, db: Session = Depends(get_db)):
    inv = find_valid_invitation(body.token, db)
    user = db.query(User).filter(User.email == inv.email).first()
    if user is not None and (user.is_active or user.org_id != inv.org_id):
        raise HTTPException(status_code=409, detail="Un compte existe déjà avec cet e-mail")
    if user is None:  # cas normal : nouveau compte
        user = User(email=inv.email)
        db.add(user)
    # (sinon : ancien membre retiré de cette usine, qui revient)
    user.org_id, user.role, user.is_active = inv.org_id, inv.role, True
    user.full_name = body.full_name
    user.password_hash = get_password_hash(body.password)
    inv.accepted_at = datetime.utcnow()
    db.commit()
    return token_for(user)

"""Qui fait la requête ? Dépendances FastAPI d'authentification et de rôles.

Chaque route déclare ce qu'elle exige :
    user: User = Depends(get_current_user)                  # n'importe quel membre connecté
    user: User = Depends(require_roles("owner", "admin"))   # responsable seulement
    org: Organization = Depends(get_current_org)            # l'usine de l'utilisateur
Toutes les requêtes filtrent ensuite sur org.id : une usine ne voit jamais les données d'une autre.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import ALGORITHM, SECRET_KEY
from app.db.session import get_db
from app.models.models import Organization, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

ROLE_LABELS = {"owner": "propriétaire", "admin": "administrateur", "member": "membre"}


def get_current_account(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """Utilisateur connecté (y compris super-administrateur sans usine)."""
    invalid = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Identifiants invalides ou session expirée",
                            headers={"WWW-Authenticate": "Bearer"})
    try:
        user_id = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM]).get("sub")
    except JWTError:
        raise invalid
    user = db.get(User, user_id) if user_id else None
    if user is None or not user.is_active:
        raise invalid
    return user


def get_current_user(user: User = Depends(get_current_account)) -> User:
    """Utilisateur connecté qui appartient à une usine."""
    if user.org_id is None:
        raise HTTPException(status_code=403, detail="Ce compte n'appartient à aucune usine")
    return user


def get_current_org(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Organization:
    return db.get(Organization, user.org_id)


def require_roles(*roles: str):
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            allowed = ", ".join(ROLE_LABELS[r] for r in roles)
            raise HTTPException(status_code=403, detail=f"Action réservée aux rôles : {allowed}")
        return user
    return checker


def require_superadmin(user: User = Depends(get_current_account)) -> User:
    if not user.is_superadmin:
        raise HTTPException(status_code=403, detail="Action réservée au super-administrateur")
    return user

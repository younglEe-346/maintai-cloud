"""Commandes d'administration (à lancer sur le serveur, pas par l'API).

Créer le super-administrateur (équipe MaintAI) :
    docker compose exec api python -m app.cli create-superadmin --email admin@maintai.local --name "Équipe MaintAI"
(le mot de passe est demandé au clavier ; ou --password pour un script)
"""
import argparse
import getpass
import sys

from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models.models import User


def create_superadmin(email: str, password: str, name: str) -> User:
    if len(password) < 8:
        raise ValueError("Mot de passe trop court (8 caractères minimum)")
    db = SessionLocal()
    try:
        email = email.lower()
        user = db.query(User).filter(User.email == email).first()
        if user is not None and user.org_id is not None:
            raise ValueError("Cet e-mail appartient déjà à un compte d'usine")
        if user is None:
            user = User(email=email)
            db.add(user)
        user.full_name, user.password_hash = name, get_password_hash(password)
        user.is_superadmin, user.is_active, user.role, user.org_id = True, True, "member", None
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("create-superadmin", help="crée (ou met à jour) le super-administrateur")
    p.add_argument("--email", required=True)
    p.add_argument("--name", default="Équipe MaintAI")
    p.add_argument("--password", help="sinon demandé au clavier")
    args = parser.parse_args(argv)

    password = args.password or getpass.getpass("Mot de passe : ")
    try:
        user = create_superadmin(args.email, password, args.name)
    except ValueError as e:
        sys.exit(f"Erreur : {e}")
    print(f"Super-administrateur prêt : {user.email}")


if __name__ == "__main__":
    main()

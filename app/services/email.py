"""Envoi d'e-mails par SMTP.

En développement, le docker compose fournit Mailpit : un faux serveur mail qui reçoit
les e-mails et les affiche sur http://localhost:8025 (rien ne part sur Internet).
Sans SMTP_HOST, l'e-mail est seulement écrit dans les logs.
OUTBOX garde les derniers e-mails en mémoire : les tests y lisent le lien d'invitation.
"""
import logging
import smtplib
from collections import deque
from email.message import EmailMessage

from app.config import SMTP_FROM, SMTP_HOST, SMTP_PORT

log = logging.getLogger("maintai.email")
OUTBOX: deque = deque(maxlen=50)


def send_email(to: str, subject: str, body: str) -> bool:
    """Renvoie True si l'e-mail est parti (ou écrit dans les logs sans SMTP)."""
    OUTBOX.append({"to": to, "subject": subject, "body": body})
    if not SMTP_HOST:
        log.warning("E-mail (pas de SMTP configuré) à %s : %s\n%s", to, subject, body)
        return True
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = SMTP_FROM, to, subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=5) as smtp:
            smtp.send_message(msg)
        return True
    except OSError as e:
        log.error("Échec de l'envoi de l'e-mail à %s : %s", to, e)
        return False

import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/maintai_db")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
# Clé qui signe les jetons de connexion (JWT). À fournir par l'environnement (.env) en production :
#   python -c "import secrets; print(secrets.token_urlsafe(48))"
DEV_SECRET_KEY = "dev-only-change-me"
SECRET_KEY = os.getenv("SECRET_KEY") or DEV_SECRET_KEY
if SECRET_KEY == DEV_SECRET_KEY:
    import warnings
    warnings.warn("SECRET_KEY non définie : clé de développement utilisée (à changer en production)")

# Sites web autorisés à appeler l'API depuis un navigateur (CORS), séparés par des virgules
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:8501").split(",") if o.strip()]
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

# E-mails (invitations). Sans SMTP_HOST, les e-mails sont seulement écrits dans les logs.
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "1025"))
SMTP_FROM = os.getenv("SMTP_FROM", "MaintAI Cloud <noreply@maintai.local>")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:8501")
INVITATION_DAYS = int(os.getenv("INVITATION_DAYS", "7"))

# Modèles réentraînés par usine (plan Pro) : un sous-dossier par usine
ORG_MODELS_DIR = os.getenv("ORG_MODELS_DIR", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "org_models"))

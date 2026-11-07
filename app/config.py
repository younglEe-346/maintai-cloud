import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/maintai_db")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
SECRET_KEY = os.getenv("SECRET_KEY", "supersecretjwtkey_maintai_2026_ensam")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

# E-mails (invitations). Sans SMTP_HOST, les e-mails sont seulement écrits dans les logs.
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "1025"))
SMTP_FROM = os.getenv("SMTP_FROM", "MaintAI Cloud <noreply@maintai.local>")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:8501")
INVITATION_DAYS = int(os.getenv("INVITATION_DAYS", "7"))

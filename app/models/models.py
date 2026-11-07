import uuid
from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Integer, Text, Boolean, JSON, Index, text, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.session import Base

def generate_uuid():
    return str(uuid.uuid4())

class Organization(Base):
    __tablename__ = "organizations"
    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, unique=True, nullable=False)
    plan = Column(String, default="Standard")
    created_at = Column(DateTime, default=datetime.utcnow)
    # Réglages des alertes (modifiables par le responsable de l'usine)
    cost_ratio = Column(Float, nullable=False, server_default="50")          # panne manquée / fausse alerte
    alert_open_k = Column(Integer, nullable=False, server_default="1")       # K mesures hautes d'affilée pour ouvrir
    alert_close_k = Column(Integer, nullable=False, server_default="3")      # mesures basses d'affilée pour fermer
    alert_close_factor = Column(Float, nullable=False, server_default="0.5") # seuil bas = facteur x seuil haut

    machines = relationship("Machine", back_populates="organization")
    alerts = relationship("Alert", back_populates="organization")
    users = relationship("User", back_populates="organization")


ROLES = ("owner", "admin", "member")  # propriétaire, administrateur, membre (technicien)


class User(Base):
    """Personne qui se connecte. Appartient à une usine avec un rôle.
    Le super-administrateur (équipe MaintAI) n'appartient à aucune usine."""
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=generate_uuid)
    org_id = Column(String, ForeignKey("organizations.id"), nullable=True, index=True)
    email = Column(String, unique=True, nullable=False)  # toujours en minuscules
    full_name = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False, server_default="member")
    is_superadmin = Column(Boolean, nullable=False, server_default=text("false"))
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    created_at = Column(DateTime, default=datetime.utcnow)

    organization = relationship("Organization", back_populates="users")


class Invitation(Base):
    """Invitation d'un collègue par e-mail. Seule l'empreinte (SHA-256) du jeton est stockée."""
    __tablename__ = "invitations"
    id = Column(String, primary_key=True, default=generate_uuid)
    org_id = Column(String, ForeignKey("organizations.id"), nullable=False, index=True)
    email = Column(String, nullable=False)
    role = Column(String, nullable=False)
    token_hash = Column(String(64), unique=True, nullable=False)
    invited_by_user_id = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    accepted_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)

    organization = relationship("Organization")

class Machine(Base):
    __tablename__ = "machines"
    id = Column(String, primary_key=True, default=generate_uuid)
    org_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    name = Column(String, nullable=False)
    api_key = Column(String, unique=True, nullable=False)
    status = Column(String, default="ACTIVE")
    created_at = Column(DateTime, default=datetime.utcnow)
    # Compteurs de l'hystérésis (mesures consécutives au-dessus / en dessous des seuils)
    consecutive_high = Column(Integer, nullable=False, server_default="0")
    consecutive_low = Column(Integer, nullable=False, server_default="0")

    organization = relationship("Organization", back_populates="machines")
    telemetries = relationship("Telemetry", back_populates="machine")
    alerts = relationship("Alert", back_populates="machine")

class Telemetry(Base):
    __tablename__ = "telemetries"
    id = Column(String, primary_key=True, default=generate_uuid)
    machine_id = Column(String, ForeignKey("machines.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    air_temp = Column(Float, nullable=False)
    process_temp = Column(Float, nullable=False)
    rotational_speed = Column(Float, nullable=False)
    torque = Column(Float, nullable=False)
    tool_wear = Column(Float, nullable=False)
    # Identifiant donné par la machine : sert à ignorer un message reçu deux fois
    message_id = Column(String(128), nullable=True)
    received_at = Column(DateTime, default=datetime.utcnow)
    # Retour terrain optionnel (panne constatée + modes) : sert au réentraînement Pro
    label_failure = Column(Boolean, nullable=True)
    label_modes = Column(JSON, nullable=True)

    machine = relationship("Machine", back_populates="telemetries")

    __table_args__ = (
        UniqueConstraint("machine_id", "message_id", name="uq_telemetries_machine_message"),
        Index("ix_telemetries_machine_timestamp", "machine_id", "timestamp"),
    )


class QuarantinedMeasure(Base):
    """Mesure rejetée (invalide ou physiquement impossible), gardée avec les raisons du rejet."""
    __tablename__ = "quarantined_measures"
    id = Column(String, primary_key=True, default=generate_uuid)
    org_id = Column(String, ForeignKey("organizations.id"), nullable=False, index=True)
    machine_id = Column(String, ForeignKey("machines.id"), nullable=False)
    message_id = Column(String(128), nullable=True)
    payload = Column(JSON, nullable=False)   # la mesure telle que reçue
    reasons = Column(JSON, nullable=False)   # liste des raisons en français
    received_at = Column(DateTime, default=datetime.utcnow)

class Prediction(Base):
    """Résultat du modèle pour une mesure, avec la version du modèle qui l'a produit."""
    __tablename__ = "predictions"
    id = Column(String, primary_key=True, default=generate_uuid)
    telemetry_id = Column(String, ForeignKey("telemetries.id"), nullable=False, unique=True)
    machine_id = Column(String, ForeignKey("machines.id"), nullable=False, index=True)
    org_id = Column(String, ForeignKey("organizations.id"), nullable=False, index=True)
    risk_score = Column(Float, nullable=False)
    decision = Column(Boolean, nullable=False)
    threshold = Column(Float, nullable=False)
    model_version = Column(String, nullable=False)
    # remplis aux étapes suivantes (mode de panne, contributions)
    failure_modes = Column(JSON, nullable=True)
    contributions = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    telemetry = relationship("Telemetry")


class Alert(Base):
    __tablename__ = "alerts"
    id = Column(String, primary_key=True, default=generate_uuid)
    org_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    machine_id = Column(String, ForeignKey("machines.id"), nullable=False)
    risk_score = Column(Float, nullable=False)  # risque à l'ouverture
    status = Column(String, default="OPEN")  # OPEN, ACKNOWLEDGED (acquittée), CLOSED
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    peak_risk_score = Column(Float, nullable=True)   # risque maximal pendant l'alerte
    last_risk_score = Column(Float, nullable=True)   # dernier risque reçu
    probable_mode = Column(String, nullable=True)
    model_version = Column(String, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    # Acquittement par un technicien : "je l'ai vue, je m'en occupe"
    acknowledged_at = Column(DateTime, nullable=True)
    acknowledged_by_name = Column(String, nullable=True)
    acknowledged_by_user_id = Column(String, ForeignKey("users.id"), nullable=True)
    ack_comment = Column(Text, nullable=True)

    # Une seule alerte non fermée par machine, garantie par la base elle-même
    __table_args__ = (
        Index("uq_alerts_one_active_per_machine", "machine_id", unique=True,
              postgresql_where=text("status <> 'CLOSED'")),
    )

    organization = relationship("Organization", back_populates="alerts")
    machine = relationship("Machine", back_populates="alerts")

import uuid
from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Integer, Text, Boolean, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.session import Base

def generate_uuid():
    return str(uuid.uuid4())

class Organization(Base):
    __tablename__ = "organizations"
    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, unique=True, nullable=False)
    admin_email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    plan = Column(String, default="Standard")
    created_at = Column(DateTime, default=datetime.utcnow)

    machines = relationship("Machine", back_populates="organization")
    alerts = relationship("Alert", back_populates="organization")

class Machine(Base):
    __tablename__ = "machines"
    id = Column(String, primary_key=True, default=generate_uuid)
    org_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    name = Column(String, nullable=False)
    api_key = Column(String, unique=True, nullable=False)
    status = Column(String, default="ACTIVE")
    created_at = Column(DateTime, default=datetime.utcnow)

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

    machine = relationship("Machine", back_populates="telemetries")

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
    risk_score = Column(Float, nullable=False)
    status = Column(String, default="OPEN") # OPEN, CLOSED
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    organization = relationship("Organization", back_populates="alerts")
    machine = relationship("Machine", back_populates="alerts")

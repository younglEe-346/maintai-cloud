from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import auth, machines, telemetry, alerts, organization, models_api, export, admin

# Les tables sont créées et mises à jour par Alembic (service "migrate" : python -m app.db.migrate)

app = FastAPI(
    title="MaintAI Cloud API",
    description="Multi-Tenant Predictive Maintenance Platform API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(machines.router, prefix="/api/v1/machines", tags=["Machines"])
app.include_router(telemetry.router, prefix="/api/v1", tags=["Telemetry"])
app.include_router(alerts.router, prefix="/api/v1/alerts", tags=["Alerts"])
app.include_router(organization.router, prefix="/api/v1/org", tags=["Organisation"])
app.include_router(models_api.router, prefix="/api/v1/org/models", tags=["Modèle IA"])
app.include_router(export.router, prefix="/api/v1/export", tags=["Export"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Super-administrateur"])

@app.get("/")
def root():
    return {"message": "MaintAI Cloud Platform API is operational."}

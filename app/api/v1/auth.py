from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from jose import JWTError, jwt

from app.db.session import get_db
from app.models.models import Organization
from app.schemas.schemas import UserRegister, Token
from app.core.security import verify_password, get_password_hash, create_access_token
from app.config import SECRET_KEY, ALGORITHM

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

def get_current_org(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> Organization:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        org_id: str = payload.get("sub")
        if org_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    org = db.query(Organization).filter(Organization.id == org_id).first()
    if org is None:
        raise credentials_exception
    return org

@router.post("/register", response_model=Token)
def register_organization(user_in: UserRegister, db: Session = Depends(get_db)):
    existing_org = db.query(Organization).filter(
        (Organization.admin_email == user_in.admin_email) | (Organization.name == user_in.org_name)
    ).first()
    if existing_org:
        raise HTTPException(status_code=400, detail="Organization or Admin email already exists")

    org = Organization(
        name=user_in.org_name,
        admin_email=user_in.admin_email,
        password_hash=get_password_hash(user_in.password),
        plan=user_in.plan
    )
    db.add(org)
    db.commit()
    db.refresh(org)

    access_token = create_access_token(data={"sub": org.id})
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    org = db.query(Organization).filter(Organization.admin_email == form_data.username).first()
    if not org or not verify_password(form_data.password, org.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect email or password")

    access_token = create_access_token(data={"sub": org.id})
    return {"access_token": access_token, "token_type": "bearer"}

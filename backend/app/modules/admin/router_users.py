from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from ...core.database import get_db
from ..auth import schemas as auth_schemas
from ..auth import models as auth_models
from ..auth.security import require_admin_role, get_password_hash, verify_password

router = APIRouter(prefix="/api/admin/users", tags=["admin-users"])

@router.get("", response_model=List[auth_schemas.User])
def get_users(
    skip: int = 0, limit: int = 100, 
    db: Session = Depends(get_db), 
    current_admin=Depends(require_admin_role)
):
    return db.query(auth_models.User).offset(skip).limit(limit).all()

@router.post("", response_model=auth_schemas.User)
def create_user(
    user: auth_schemas.UserCreate, 
    db: Session = Depends(get_db), 
    current_admin=Depends(require_admin_role)
):
    # Check if username exists
    existing = db.query(auth_models.User).filter(auth_models.User.username == user.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already registered")
        
    db_user = auth_models.User(
        username=user.username,
        hashed_password=get_password_hash(user.password),
        role=user.role,
        is_active=True
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@router.put("/{user_id}", response_model=auth_schemas.User)
def update_user(
    user_id: int,
    user_update: auth_schemas.UserUpdate,
    db: Session = Depends(get_db),
    current_admin=Depends(require_admin_role)
):
    user = db.query(auth_models.User).filter(auth_models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if user_update.password:
        user.hashed_password = get_password_hash(user_update.password)
    
    if user_update.role is not None:
        user.role = user_update.role
        
    db.commit()
    db.refresh(user)
    return user

@router.put("/{user_id}/status", response_model=auth_schemas.User)
def update_user_status(
    user_id: int,
    status_update: auth_schemas.UserStatusUpdate,
    db: Session = Depends(get_db),
    current_admin=Depends(require_admin_role)
):
    if not verify_password(status_update.admin_password, current_admin.hashed_password):
        raise HTTPException(status_code=403, detail="Mật khẩu xác thực của Admin không chính xác")
        
    if not status_update.reason.strip():
        raise HTTPException(status_code=400, detail="Vui lòng cung cấp lý do")

    user = db.query(auth_models.User).filter(auth_models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    user.is_active = status_update.is_active
    # If activating, auto reset failed attempts
    if user.is_active:
        user.failed_login_attempts = 0
        user.lockout_until = None
        
    db.commit()
    db.refresh(user)
    return user

@router.delete("/{user_id}", response_model=auth_schemas.User)
def soft_delete_user(
    user_id: int, 
    db: Session = Depends(get_db), 
    current_admin=Depends(require_admin_role)
):
    user = db.query(auth_models.User).filter(auth_models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.username == "epi_scout_admin":
        raise HTTPException(status_code=400, detail="Cannot disable primary admin")
        
    user.is_active = False
    db.commit()
    db.refresh(user)
    return user

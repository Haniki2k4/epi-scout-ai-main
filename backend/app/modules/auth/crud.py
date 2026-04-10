from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional

from .models import User
from .schemas import UserCreate
from .security import get_password_hash

def get_user_by_username(db: Session, username: str) -> Optional[User]:
    return db.query(User).filter(User.username == username).first()

def create_user(db: Session, user: UserCreate) -> User:
    hashed_password = get_password_hash(user.password)
    db_user = User(
        username=user.username,
        hashed_password=hashed_password,
        role=user.role
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def increment_failed_login(db: Session, user: User):
    user.failed_login_attempts += 1
    db.commit()
    db.refresh(user)
    return user

def reset_failed_login(db: Session, user: User):
    if user.failed_login_attempts > 0 or user.lockout_until is not None:
        user.failed_login_attempts = 0
        user.lockout_until = None
        db.commit()
        db.refresh(user)
    return user

def lockout_user(db: Session, user: User, lockout_time: datetime):
    user.lockout_until = lockout_time
    db.commit()
    db.refresh(user)
    return user

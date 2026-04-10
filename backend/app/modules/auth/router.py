from datetime import timedelta, datetime
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import pytz

from ...core.database import get_db
from . import schemas, crud, security

router = APIRouter(prefix="/api/auth", tags=["auth"])

MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15

@router.post("/login", response_model=schemas.Token)
def login_for_access_token(
    db: Session = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()
):
    # Dùng form_data.username thay thế cho username logic
    user = crud.get_user_by_username(db, username=form_data.username)
    
    if not user:
        # User không tồn tại -> Lỗi ẩn (không báo rõ là user không có)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Đăng nhập không hợp lệ",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if locked out
    if user.lockout_until and user.lockout_until > datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản của bạn đã bị khóa tạm thời. Vui lòng thử lại sau.",
        )
    
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Tài khoản đã bị vô hiệu hoá")

    if not security.verify_password(form_data.password, user.hashed_password):
        # Mật khẩu sai
        user = crud.increment_failed_login(db, user)
        remaining = MAX_LOGIN_ATTEMPTS - user.failed_login_attempts
        
        if remaining <= 0:
            lockout_time = datetime.utcnow() + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
            crud.lockout_user(db, user, lockout_time)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Tài khoản bị khóa tạm thời do nhập sai quá {MAX_LOGIN_ATTEMPTS} lần.",
            )
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Sai mật khẩu. Bạn còn {remaining} lần thử",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Nếu thành công -> reset failed logic
    crud.reset_failed_login(db, user)
    
    access_token_expires = timedelta(minutes=security.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        subject=user.username, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=schemas.User)
def read_users_me(current_user: schemas.User = Depends(security.get_current_active_user)):
    return current_user

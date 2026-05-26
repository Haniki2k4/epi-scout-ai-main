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

@router.put("/me", response_model=schemas.User)
def update_user_me(
    user_in: schemas.UserUpdate,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(security.get_current_active_user)
):
    """Cập nhật thông tin cá nhân của người dùng hiện tại (email, tuỳ chọn nhận báo cáo)."""
    user_db = crud.get_user_by_username(db, current_user.username)
    if not user_db:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")
        
    # Check email uniqueness
    if user_in.email and user_in.email != user_db.email:
        from .models import User
        existing = db.query(User).filter(User.email == user_in.email).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email này đã được sử dụng")

    update_data = user_in.model_dump(exclude_unset=True)
    
    # Không cho phép tự đổi role hoặc is_active qua API này
    update_data.pop("role", None)
    update_data.pop("is_active", None)
    
    # Không cho phép đổi password qua API này (chỉ Admin)
    update_data.pop("password", None)

    for field, value in update_data.items():
        setattr(user_db, field, value)

    db.commit()
    db.refresh(user_db)

    # Cập nhật scheduler
    from ...scheduler import update_user_email_schedule
    update_user_email_schedule(
        user_id=user_db.id,
        schedule_type=user_db.report_schedule_type,
        schedule_time=user_db.report_schedule_time,
        schedule_day=user_db.report_schedule_day
    )

    return user_db

@router.post("/me/send-report-now")
async def send_report_now(
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(security.get_current_active_user)
):
    """Gửi ngay báo cáo vào email của user."""
    user = crud.get_user_by_username(db, current_user.username)
    if not user or not user.email:
        raise HTTPException(status_code=400, detail="Bạn chưa cấu hình địa chỉ email")

    from ...scheduler import send_personal_email_job

    result = await send_personal_email_job(user.id)
    if result and not result.get("success"):
        raise HTTPException(status_code=422, detail=result["message"])

    return {"success": True, "message": "Báo cáo đang được gửi đến email của bạn."}

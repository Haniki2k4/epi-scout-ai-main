from fastapi import Depends, HTTPException, status

from .models import User
from .security import get_optional_user, require_authenticated_user


def public_user(current_user: User | None = Depends(get_optional_user)) -> User | None:
    return current_user


def require_user(current_user: User = Depends(require_authenticated_user)) -> User:
    return current_user


def require_admin(current_user: User = Depends(require_authenticated_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return current_user

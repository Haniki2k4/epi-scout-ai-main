from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Unicode, UnicodeText
from datetime import datetime
from ...core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), default="user", nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=True)
    report_schedule_type = Column(String(50), default="none") # none, daily, weekly
    report_schedule_time = Column(String(10), nullable=True)  # VD: "08:00"
    report_schedule_day = Column(Integer, nullable=True)      # 0=Monday, 6=Sunday
    report_filter_id = Column(Integer, ForeignKey("user_alerts.id", ondelete="SET NULL"), nullable=True)
    is_active = Column(Boolean, default=True)
    failed_login_attempts = Column(Integer, default=0)
    lockout_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class UserBookmark(Base):
    __tablename__ = "user_bookmarks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    article_id = Column(Integer, ForeignKey("article_identity.id", ondelete="CASCADE"), index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class UserAlert(Base):
    """
    Bộ lọc bài báo cá nhân của từng cán bộ.
    User tự tạo tên + bộ từ khóa + địa bàn để lọc bài từ DB theo nhu cầu theo dõi cá nhân.
    Hệ thống vẫn quét bài theo keywords hệ thống (is_active keywords).
    """
    __tablename__ = "user_alerts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    name = Column(Unicode(255), nullable=False)          # Tên bộ cảnh báo, VD: "Theo dõi Sởi - Hà Nội"
    keywords = Column(UnicodeText, nullable=False)       # JSON list: ["Sởi", "Hà Nội"]
    location_filter = Column(Unicode(255), nullable=True) # VD: "Hà Nội" — lọc thêm theo vị trí
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

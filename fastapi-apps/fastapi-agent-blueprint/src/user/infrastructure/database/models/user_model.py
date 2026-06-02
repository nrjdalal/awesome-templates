from sqlalchemy import DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from src._core.infrastructure.persistence.rdb.database import Base


class UserModel(Base):
    __tablename__ = "user"
    __table_args__ = (
        UniqueConstraint("username", name="uq_user_username"),
        UniqueConstraint("email", name="uq_user_email"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(20), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime, server_default=func.now(), nullable=True
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=True
    )

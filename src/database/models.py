from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy import ForeignKey
from sqlalchemy.orm import mapped_column, Mapped
from datetime import datetime


class AbstractModel(DeclarativeBase):
    pass


class UserModel(AbstractModel):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(autoincrement=True, primary_key=True, unique=True)
    login: Mapped[str] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True)
    password: Mapped[str] = mapped_column()
    verify: Mapped[bool] = mapped_column()


    photos: Mapped[list["ProcessPhotoModel"]] = relationship(back_populates="user", lazy=False)

class ProcessPhotoModel(AbstractModel):
    __tablename__ = 'photos'
    id: Mapped[int] = mapped_column(autoincrement=True, primary_key=True, unique=True)
    timestamp: Mapped[datetime] = mapped_column()
    url: Mapped[str] = mapped_column()
    isProcessed: Mapped[bool] = mapped_column()
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))


    user: Mapped["UserModel"] = relationship(back_populates="photos", lazy=False)



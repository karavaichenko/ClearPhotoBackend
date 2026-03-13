from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy import ForeignKey
from sqlalchemy.orm import mapped_column, Mapped
from datetime import datetime
from src.schemas import PhotoSchema


class AbstractModel(DeclarativeBase):
    pass


class UserModel(AbstractModel):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(autoincrement=True, primary_key=True, unique=True)
    login: Mapped[str] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True)
    password: Mapped[str] = mapped_column()
    verify: Mapped[bool] = mapped_column()


    photos: Mapped[list["ProcessPhotoModel"]] = relationship(back_populates="user")

class ProcessPhotoModel(AbstractModel):
    __tablename__ = 'photos'
    id: Mapped[int] = mapped_column(autoincrement=True, primary_key=True, unique=True)
    timestamp: Mapped[datetime] = mapped_column()
    input_path: Mapped[str] = mapped_column()
    output_path: Mapped[str] = mapped_column()
    faces: Mapped[int] = mapped_column()
    plates: Mapped[int] = mapped_column()
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))

    user: Mapped["UserModel"] = relationship(back_populates="photos")

    def to_schema(self):
        return PhotoSchema(
            id=self.id, input_path=self.input_path,
            output_path=self.output_path, faces=self.faces,
            plates=self.plates, timestamp=self.timestamp
        )


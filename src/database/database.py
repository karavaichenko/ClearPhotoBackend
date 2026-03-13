import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, select, delete, desc, func
from sqlalchemy.orm import Session
from datetime import datetime

from src.database.models import AbstractModel, UserModel, ProcessPhotoModel
from src.utils.utils import hash_password

class Database:

    def __init__(self, URL):
        self.URL = URL
        self.engine = create_engine(
            self.URL,
            echo=False,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=300,
            pool_timeout=30,
        )
        with Session(self.engine) as session:
            AbstractModel.metadata.create_all(self.engine)

    def _get_session(self):
        """Создаёт новую сессию для каждого запроса"""
        return Session(self.engine)

    def add(self, obj):
        with self._get_session() as session:
            try:
                session.add(obj)
                session.commit()
            except Exception as e:
                session.rollback()
                print(f"Ошибка при добавлении: {e}")
                raise

    def create_user(self, login: str, password: str, email: str):
        with self._get_session() as session:
            try:
                print(password)
                res = session.execute(select(UserModel.login).where(UserModel.login == login))
                user = res.scalar()
                if user is not None:
                    return False
                else:
                    res = session.execute(select(UserModel.id).order_by(UserModel.id.desc()))
                    id = res.scalar()
                    if id:
                        user = UserModel(id=(id + 1), login=login, email=email, password=hash_password(password).hex(),
                                         verify=False)
                    else:
                        user = UserModel(id=1, login=login, email=email, password=hash_password(password).hex(),
                                         verify=False)
                    session.add(user)
                    session.commit()
                    return True
            except Exception as e:
                session.rollback()
                print(f"Ошибка в create_user: {e}")
                return False

    def change_user_password(self, user_id, old_password, new_password):
        from src.utils.utils import validate_password
        with self._get_session() as session:
            try:
                user = session.execute(select(UserModel).where(UserModel.id == user_id)).scalar()
                if not user:
                    return False
                if not validate_password(old_password, user.password):
                    return False
                user.password = hash_password(new_password).hex()
                session.commit()
                return True

            except Exception as e:
                print(f"Ошибка в change_user_password: {e}")
                return False

    def check_email(self, email):
        with self._get_session() as session:
            try:
                res = session.execute(select(UserModel).where(UserModel.email == email))
                user = res.scalar()
                return user is None
            except Exception as e:
                print(f"Ошибка в check_email: {e}")
                return False

    def verify_email(self, email):
        with self._get_session() as session:
            try:
                res = session.execute(select(UserModel).where(UserModel.email == email))
                user = res.scalar()
                if user:
                    user.verify = True
                    session.commit()
                    return True
                return False
            except Exception as e:
                session.rollback()
                print(f"Ошибка в verify_email: {e}")
                return False

    def get_user(self, login):
        with self._get_session() as session:
            try:
                res = session.execute(select(UserModel).where(UserModel.login == login))
                return res.scalar()
            except Exception as e:
                print(f"Ошибка при получении пользователя: {e}")
                return None

    def create_photo(self, input_path, output_path, timestamp, user_id, faces, plates):
        with self._get_session() as session:
            try:
                res = session.execute(select(ProcessPhotoModel.id).order_by(ProcessPhotoModel.id.desc()))
                photo_id = res.scalar()
                photo_id = photo_id + 1 if photo_id is not None else 0
                process_photo = ProcessPhotoModel(
                    id=photo_id, timestamp=timestamp,
                    input_path=input_path, output_path=output_path,
                    user_id=user_id, faces=faces,
                    plates=plates
                )
                session.add(process_photo)
                session.commit()
                return photo_id
            except Exception as e:
                session.rollback()
                print(f"Ошибка в create_photo: {e}")
                return None

    def get_photo(self, photo_id, user_id):
        with self._get_session() as session:
            try:
                res = session.execute(select(ProcessPhotoModel)
                                      .where(ProcessPhotoModel.user_id == user_id)
                                      .where(ProcessPhotoModel.id == photo_id))
                return res.scalars().first()
            except Exception as e:
                print(f"Ошибка в get_photo: {e}")
                return None

    def get_user_photos(self, user_id, limit, page):
        with self._get_session() as session:
            try:
                res = session.execute(select(ProcessPhotoModel).where(ProcessPhotoModel.user_id == user_id)
                                      .order_by(desc(ProcessPhotoModel.timestamp)).offset((page - 1) * limit).limit(limit))
                return res.scalars().all()
            except Exception as e:
                print(f"Ошибка в get_user_photos: {e}")
                return None

    def get_user_photos_count(self, user_id):
        with self._get_session() as session:
            try:
                res = session.execute(select(func.count(ProcessPhotoModel.id)).where(ProcessPhotoModel.user_id == user_id))
                return res.scalar()
            except Exception as e:
                print(f"Ошибка в get_user_photos_count: {e}")
                return None

    def delete_photo(self, photo_id, user_id):
        photo = self.get_photo(photo_id, user_id)
        if not photo:
            return None
        with self._get_session() as session:
            try:
                session.execute(delete(ProcessPhotoModel).where(ProcessPhotoModel.id == photo_id))
                session.commit()
                return True
            except Exception as e:
                session.rollback()
                print(f"Ошибка в delete_photo: {e}")
                return None




load_dotenv()
URL = os.getenv('DB_URL')
database = Database(URL)
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, select, delete
from sqlalchemy.orm import registry, Session
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
            pool_recycle=3600,
        )
        self.mapped_registry = registry()
        self._session = None
        with Session(self.engine) as session:
            AbstractModel.metadata.create_all(self.engine)

    @property
    def session(self):
        if self._session is None:
            self._session = Session(self.engine)
        return self._session

    def _ensure_session(self):
        try:
            self.session.execute(select(1)).scalar()
            return self.session
        except Exception as e:
            print(f"⚠️ Ошибка соединения: {e}, пересоздаю сессию...")
            # Создаем новую сессию
            if self._session:
                try:
                    self._session.close()
                except:
                    pass
            self._session = Session(self.engine)
            return self.session

    def add(self, obj):
        session = self._ensure_session()
        try:
            session.add(obj)
            session.commit()
        except Exception as e:
            print(f"⚠️ Ошибка при добавлении: {e}, пробую еще раз...")
            session.rollback()
            if self._session:
                try:
                    self._session.close()
                except:
                    pass
            self._session = Session(self.engine)
            self._session.add(obj)
            self._session.commit()

    def create_user(self, login: str, password: str, email: str):
        session = self._ensure_session()
        try:
            res = session.execute(select(UserModel.login).where(UserModel.login == login))
            user = res.scalar()
            if user is not None:
                return False
            else:
                res = session.execute(select(UserModel.id).order_by(UserModel.id.desc()))
                id = res.scalar()
                print(id)
                if id:
                    user = UserModel(id=(id + 1), login=login, email=email, password=hash_password(password).hex(),
                                     verify=False)
                else:
                    user = UserModel(id=1, login=login, email=email, password=hash_password(password).hex(),
                                     verify=False)
                self.add(user)
                return True
        except Exception as e:
            print(f"Ошибка в create_user: {e}")
            return False

    def check_email(self, email):
        session = self._ensure_session()
        try:
            res = session.execute(select(UserModel).where(UserModel.email == email))
            user = res.scalar()
            return user is None
        except Exception as e:
            print(f"Ошибка в check_email: {e}")
            return False

    def verify_email(self, email):
        session = self._ensure_session()
        try:
            res = session.execute(select(UserModel).where(UserModel.email == email))
            user = res.scalar()
            if user:
                user.verify = True
                session.commit()
                return True
            return False
        except Exception as e:
            print(f"Ошибка в verify_email: {e}")
            return False

    def get_user(self, login):
        session = self._ensure_session()
        try:
            res = session.execute(select(UserModel).where(UserModel.login == login))
            user = res.scalar()
            return user
        except Exception as e:
            print(f"Ошибка при получении пользователя: {e}")
            if self._session:
                try:
                    self._session.close()
                except:
                    pass
            self._session = Session(self.engine)
            try:
                res = self._session.execute(select(UserModel).where(UserModel.login == login))
                return res.scalar()
            except Exception as e2:
                print(f"Повторная ошибка: {e2}")
                return None

    def create_photo(self, user_id: int, url: str):
        session = self._ensure_session()
        try:
            res = session.execute(select(ProcessPhotoModel.id).order_by(ProcessPhotoModel.id.desc()))
            last_id = res.scalar()
            new_id = last_id + 1 if last_id else 1

            photo = ProcessPhotoModel(
                id=new_id, timestamp=datetime.now(),
                url=url, isProcessed=False, user_id=user_id
            )
            self.add(photo)
            return photo
        except Exception as e:
            print(f"Ошибка в create_photo: {e}")
            return None

    def get_photo(self, photo_id: int):
        session = self._ensure_session()
        try:
            res = session.execute(
                select(ProcessPhotoModel).where(ProcessPhotoModel.id == photo_id)
            )
            photo = res.scalar()
            return photo
        except Exception as e:
            print(f"Ошибка при получении фото {photo_id}: {e}")
            if self._session:
                try:
                    self._session.close()
                except:
                    pass
            self._session = Session(self.engine)
            try:
                res = self._session.execute(
                    select(ProcessPhotoModel).where(ProcessPhotoModel.id == photo_id)
                )
                return res.scalar()
            except Exception as e2:
                print(f"Повторная ошибка: {e2}")
                return None

    def get_user_photos(self, user_id: int, limit: int = 100, offset: int = 0):
        session = self._ensure_session()
        try:
            res = session.execute(
                select(ProcessPhotoModel)
                .where(ProcessPhotoModel.user_id == user_id)
                .order_by(ProcessPhotoModel.timestamp.desc())
                .limit(limit)
                .offset(offset)
            )
            photos = res.scalars().all()
            return photos
        except Exception as e:
            print(f"Ошибка при получении фото пользователя {user_id}: {e}")
            if self._session:
                try:
                    self._session.close()
                except:
                    pass
            self._session = Session(self.engine)
            try:
                res = self._session.execute(
                    select(ProcessPhotoModel)
                    .where(ProcessPhotoModel.user_id == user_id)
                    .order_by(ProcessPhotoModel.timestamp.desc())
                    .limit(limit)
                    .offset(offset)
                )
                return res.scalars().all()
            except Exception as e2:
                print(f"Повторная ошибка: {e2}")
                return []

    def get_unprocessed_photos(self, limit: int = 10):
        session = self._ensure_session()
        try:
            res = session.execute(
                select(ProcessPhotoModel)
                .where(ProcessPhotoModel.isProcessed == False)
                .order_by(ProcessPhotoModel.timestamp.asc())
                .limit(limit)
            )
            photos = res.scalars().all()
            return photos
        except Exception as e:
            print(f"Ошибка при получении необработанных фото: {e}")
            return []

    def update_photo_status(self, photo_id: int, isProcessed: bool = True):
        session = self._ensure_session()
        try:
            res = session.execute(
                select(ProcessPhotoModel).where(ProcessPhotoModel.id == photo_id)
            )
            photo = res.scalar()

            if photo:
                photo.isProcessed = isProcessed
                session.commit()
                return True
            return False
        except Exception as e:
            print(f"Ошибка при обновлении статуса фото {photo_id}: {e}")
            session.rollback()
            return False

    def delete_photo(self, photo_id: int):
        session = self._ensure_session()
        try:
            res = session.execute(
                select(ProcessPhotoModel).where(ProcessPhotoModel.id == photo_id)
            )
            photo = res.scalar()

            if photo:
                session.delete(photo)
                session.commit()
                return True
            return False
        except Exception as e:
            print(f"Ошибка при удалении фото {photo_id}: {e}")
            session.rollback()
            return False

    def get_photos_count(self, user_id: int = None):
        session = self._ensure_session()
        try:
            query = select(ProcessPhotoModel)
            if user_id:
                query = query.where(ProcessPhotoModel.user_id == user_id)

            res = session.execute(query)
            count = len(res.scalars().all())
            return count
        except Exception as e:
            print(f"Ошибка при подсчете фото: {e}")
            return 0

load_dotenv()
URL = os.getenv('DB_URL')
database = Database(URL)
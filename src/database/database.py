from sqlalchemy import create_engine, select, delete
from sqlalchemy.orm import registry, Session

from src.database.models import AbstractModel, UserModel
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
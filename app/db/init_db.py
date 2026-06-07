from app.db.session import Base, engine

# Import all models so SQLAlchemy registers them before create_all
from app.models import user, role, document  # noqa: F401


def init_db() -> None:
    Base.metadata.create_all(bind=engine)

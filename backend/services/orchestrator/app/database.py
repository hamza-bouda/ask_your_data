import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

if os.getenv("TESTING") == "1":
    DATABASE_URL = "sqlite:///./test.db"
    engine = create_engine(
        DATABASE_URL, connect_args={"check_same_thread": False}
    )
else:
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://askyourdata:askyourdata_dev@postgres:5432/askyourdata")
    engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_tables():
    Base.metadata.create_all(bind=engine)
    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE conversations ADD COLUMN IF NOT EXISTS source_id VARCHAR"))
            conn.execute(text("ALTER TABLE runs ADD COLUMN IF NOT EXISTS source_id VARCHAR"))

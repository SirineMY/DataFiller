import asyncio
from sqlalchemy import inspect
import pandas as pd
from io import StringIO
from arrow import now
from fastapi import Depends, HTTPException, Request
from sqlalchemy import Column, DateTime, Float, Integer, MetaData, String, Date, Table, create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_scoped_session
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy import ForeignKey
import threading
from sqlalchemy.dialects.mysql import VARCHAR, FLOAT, INTEGER, DATETIME


# Configuration de la base de données
DATABASE_URL = "mysql+aiomysql://root:@localhost/e1"
engine_e1 = create_async_engine(DATABASE_URL, echo=True)
SessionLocal_e1 = sessionmaker(autocommit=False, autoflush=False, bind=engine_e1, class_=AsyncSession)
Base_e1 = declarative_base()

engine_fichier_csv = create_engine('mysql+pymysql://root:@localhost/fichier_csv', echo=True)
SessionLocal_fichier_csv = sessionmaker(autocommit=False, autoflush=False, bind=engine_fichier_csv)

# Modèle utilisateur
class Utilisateur(Base_e1):
    __tablename__ = 'utilisateurs'
    id = Column(Integer, primary_key=True)
    nom = Column(String(50), unique=True, index=True)
    mot_de_passe = Column(String(80), nullable=False)

# Création des tables de manière asynchrone
async def create_tables():
    async with engine_e1.begin() as conn:
        await conn.run_sync(Base_e1.metadata.create_all)


# Dependency pour récupérer la session de la base de données
async def get_db():
    async_session = async_scoped_session(SessionLocal_e1, scopefunc=asyncio.current_task)
    try:
        yield async_session
    finally:
        await async_session.close()
        

class Operation(Base_e1):
    __tablename__ = 'operation'
    id = Column(Integer, primary_key=True)
    file_name = Column(String(255))  # Spécifiez une longueur pour VARCHAR
    num_rows = Column(Integer)
    num_columns = Column(Integer)
    percent_empty_cells = Column(Float)
    id_utilisateur = Column(Integer, ForeignKey('utilisateurs.id'))
    utilisateur = relationship("Utilisateur")
    date = Column(DateTime)

async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)):
    user_id = request.session.get('user_id')
    if user_id is None:
        raise HTTPException(status_code=404, detail="User not found")
    async with db() as session:
        user = await session.get(Utilisateur, user_id)
        if user:
            return user
        else:
            raise HTTPException(status_code=404, detail="User not found")


def insert_data_sync(df, table_name):
    """
    Fonction pour insérer des données dans une table de manière synchronique.
    Cette fonction est conçue pour être exécutée dans un thread séparé.
    """
    df.to_sql(table_name, engine_fichier_csv, if_exists='replace', index=False)
    
async def check_table_exists(engine, table_name):
    async with engine.connect() as conn:
        # Utilisez conn.run_sync pour exécuter une opération synchrone dans un contexte asynchrone
        result = await conn.run_sync(lambda sync_conn: inspect(sync_conn).has_table(table_name))
    return result

# Fonction pour créer une table à partir du nom du fichier et insérer les données
async def save_csv_data(file_name, content, utilisateur: Utilisateur):
    # Lecture du contenu CSV
    df = pd.read_csv(StringIO(content.decode("utf-8")))
    num_rows, num_columns = df.shape
    percent_empty_cells = 100 * (1 - df.count().sum() / (num_rows * num_columns))

    # Sauvegarde des informations dans la base de données e1
    AsyncSession_e1 = sessionmaker(engine_e1, expire_on_commit=False, class_=AsyncSession)
    async with AsyncSession_e1() as session:
        new_operation = Operation(
            file_name=file_name,
            num_rows=num_rows,
            date = now(),
            num_columns=num_columns,
            percent_empty_cells=percent_empty_cells,
            id_utilisateur=utilisateur.id  # Utilisez l'ID de l'utilisateur ici

        )
        session.add(new_operation)
        await session.commit()

    table_name = file_name.split('.')[0]

    

    # Exécutez l'insertion de manière synchronique dans un thread séparé
    thread = threading.Thread(target=insert_data_sync, args=(df, table_name))
    thread.start()
    thread.join()

def dtype_sqlalchemy(dtype):
    """
    Convertit un dtype pandas en dtype SQLAlchemy.
    """
    if pd.api.types.is_integer_dtype(dtype):
        return INTEGER
    elif pd.api.types.is_float_dtype(dtype):
        return FLOAT
    elif pd.api.types.is_datetime64_any_dtype(dtype):
        return DATETIME
    elif pd.api.types.is_string_dtype(dtype):
        return VARCHAR(255)
    else:
        return VARCHAR(255)  # Fallback type

async def create_table_from_df(engine, table_name, df):
    """
    Crée une table dans la base de données basée sur le schéma d'un DataFrame pandas.
    """
    metadata = MetaData(bind=engine)
    columns = [
        Column(name, dtype_sqlalchemy(dtype)) for name, dtype in df.dtypes.items()
    ]
    table = Table(table_name, metadata, *columns)
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    return table
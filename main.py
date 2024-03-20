from io import StringIO
import joblib 
from fastapi import FastAPI, Request, Form, Depends, HTTPException, File, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_scoped_session
from sqlalchemy.future import select
import pandas as pd
from starlette.middleware.sessions import SessionMiddleware
from aiofiles import open as aio_open
from security import hash_password, verify_password
from database import Utilisateur, get_db, create_tables, Operation, insert_data_sync, save_csv_data, get_current_user

app = FastAPI()

# Configurez la clé secrète et ajoutez le middleware de session
app.add_middleware(SessionMiddleware, secret_key="my_key")

@app.on_event("startup")
async def startup_event():
    await create_tables()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
    
# Routes
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/register", response_class=HTMLResponse)
async def register_user(request: Request, nom: str = Form(...), mot_de_passe: str = Form(...), db: AsyncSession = Depends(get_db)):
    hashed_password = hash_password(mot_de_passe)  # Utilisation de hash_password
    user = Utilisateur(nom=nom, mot_de_passe=hashed_password)
    async with db() as session:
        session.add(user)
        await session.commit()
    return templates.TemplateResponse("login.html", {"request": request, "message": "User created successfully"})

@app.post("/login", response_class=HTMLResponse)
async def login_user(request: Request, nom: str = Form(...), mot_de_passe: str = Form(...), db: AsyncSession = Depends(get_db)):
    async with db() as session:
        user = await session.execute(select(Utilisateur).filter(Utilisateur.nom == nom))
        user = user.scalars().first()
        if user and verify_password(mot_de_passe, user.mot_de_passe):
            # Stockez l'ID de l'utilisateur dans la session
            request.session['user_id'] = user.id
            return templates.TemplateResponse("index.html", {"request": request, "username": nom})
        else:
            return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid username or password"})

@app.get("/register", response_class=HTMLResponse)
async def get_register(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/upload-csv", response_class=HTMLResponse)
async def upload_csv(request: Request, file: UploadFile = File(...), utilisateur: Utilisateur = Depends(get_current_user)):
    content = await file.read()
    UPLOAD_DIR= "C:/Users/utilisateur/2024/E1/data"
    file_location = f"{UPLOAD_DIR}/{file.filename}"
    
    # Écriture du contenu dans un nouveau fichier dans le répertoire de téléchargement
    with open(file_location, "wb") as f:
        f.write(content)
    
    await save_csv_data(file.filename, content, utilisateur)
    # Utilisation de StringIO pour lire le contenu comme un fichier CSV
    df = pd.read_csv(StringIO(content.decode("utf-8")))
    
    # Préparation des informations à afficher
    file_name = file.filename
    num_rows = len(df)
    num_columns = len(df.columns)
    total_cells = num_rows * num_columns
    num_empty_cells = total_cells - df.count().sum()
    percent_empty_cells = (num_empty_cells / total_cells) * 100 if total_cells else 0
    column_types = df.dtypes.to_dict()
    
    # Convertir les 6 premières lignes du DataFrame en HTML
    df_html = df.head(6).to_html(classes="table table-striped", border=0)
    
    # Préparation du contexte pour le template
    context = {
        "request": request,
        "df_html": df_html,
        "file_name": file_name,
        "num_rows": num_rows,
        "num_columns": num_columns,
        "percent_empty_cells": percent_empty_cells,
        "column_types": {col: str(dtype) for col, dtype in column_types.items()},
    }
    # Renvoyer le template HTML avec les informations du CSV
    return templates.TemplateResponse("display_csv.html", context)

@app.post("/fill-csv", response_class=HTMLResponse)
async def fill_csv(request: Request, file_name: str = Form(...), utilisateur: Utilisateur = Depends(get_current_user)):
    # Chemin vers le modèle .pkl
    model_path = "C:/Users/utilisateur/2024/E1/model.pkl"
    
    # Charger le modèle
    model = joblib.load(model_path)
    UPLOAD_DIR= "C:/Users/utilisateur/2024/E1/data"
    file_location = f"{UPLOAD_DIR}/{file_name}"

    # Lire et retourner le contenu du fichier ou effectuer des opérations nécessaires
    df = pd.read_csv(file_location)
    
    # Suppression des colonnes non numériques
    df_numeriques = df.drop(columns=df.select_dtypes(exclude='number').columns)
    
    # Appliquer le modèle aux données
    df_transformed = model.fit_transform(df_numeriques)
    
    # Nom du fichier modifié pour inclure "_new" avant ".csv"
    new_file_name = file_name.rsplit('.', 1)[0] + "_new.csv"
    new_csv_path = f"C:/Users/utilisateur/2024/E1/data/{new_file_name}"
    
    # Enregistrer le DataFrame transformé dans un nouveau fichier CSV
    df_imputed = pd.DataFrame(df_transformed, columns=df_numeriques.columns)
    df_imputed.to_csv(new_csv_path, index=False)

    # Enregistrer également le fichier transformé dans la base de données
    insert_data_sync(df_imputed, new_file_name.rsplit('.', 1)[0])

    # Préparer le DataFrame transformé pour l'affichage
    df_html = df_imputed.head(6).to_html(classes="table table-striped", border=0)

    num_rows = len(df_imputed)
    num_columns = len(df_imputed.columns)
    total_cells = num_rows * num_columns
    num_empty_cells = total_cells - df_imputed.count().sum()
    percent_empty_cells = (num_empty_cells / total_cells) * 100 if total_cells else 0
    column_types = df_imputed.dtypes.to_dict()
    
    # Préparer et renvoyer le contexte avec les données modifiées
    context = {
        "request": request,
        "df_html": df_html,
        "file_name": new_file_name,
        "num_rows": num_rows,
        "num_columns": num_columns,
        "percent_empty_cells": percent_empty_cells,
        "column_types": {col: str(dtype) for col, dtype in column_types.items()},
    }
    
    # Afficher les informations de la nouvelle version des données
    return templates.TemplateResponse("display_csv_filled.html", context)

@app.get("/download/{file_name}", response_class=FileResponse)
async def download_csv(file_name: str):
    file_path = f"C:/Users/utilisateur/2024/E1/data/{file_name}"
    return FileResponse(path=file_path, filename=file_name, media_type='text/csv')

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
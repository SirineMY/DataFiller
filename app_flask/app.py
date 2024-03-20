from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
import os
import pandas as pd
from sqlalchemy import create_engine, MetaData
from werkzeug.utils import secure_filename



app = Flask(__name__)
app.secret_key = 'just_me'  

user = 'root'
password = ''
host = 'localhost'
database = 'e1'

app.config['SQLALCHEMY_DATABASE_URI'] = (f'mysql://{user}:{password}@{host}/{database}')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Utilisateur(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(50), nullable=False)
    mot_de_passe = db.Column(db.String(80), nullable=False)
    nombre_connexions = db.Column(db.Integer, default=0)



with app.app_context():
    db.create_all()

# from joblib import load

# model = load('C:/Users/utilisateur/2024/model/model.joblib')


UPLOAD_FOLDER = 'C:/Users/utilisateur/2024/E1/data'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Assurez-vous que l'engine SQL est bien configuré pour votre base de données fichier_csv
engine = create_engine('mysql+pymysql://root:@localhost/fichier_csv')
metadata = MetaData()
metadata.bind = engine

def create_table_from_csv(csv_file_path):
    # Lire le CSV pour déterminer la structure
    df = pd.read_csv(csv_file_path)
    table_name = os.path.splitext(os.path.basename(csv_file_path))[0]
    
    # Créer la table SQL dynamiquement
    df.to_sql(name=table_name, con=engine, if_exists='replace', index=False)


@app.route('/')
def home():
    if 'username' in session:
        return render_template('index.html')
    else:
        return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    erreur = None  # Assurez-vous que cette ligne existe
    if request.method == 'POST':
        nom = request.form['username']
        mot_de_passe = request.form['password']

        utilisateur = Utilisateur.query.filter_by(nom=nom).first()
        if utilisateur and utilisateur.mot_de_passe == mot_de_passe:
            session['username'] = nom
            return redirect(url_for('home'))
        else:
            erreur = "Nom d'utilisateur ou mot de passe incorrect."  # Message d'erreur
            print(erreur)

    return render_template('login.html', erreur=erreur)



@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))



@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        nom = request.form['username']
        mot_de_passe = request.form['password']
        # Ici,hacher le mot de passe avant de le stocker

        utilisateur_existant = Utilisateur.query.filter_by(nom=nom).first()
        if not utilisateur_existant:
            nouvel_utilisateur = Utilisateur(nom=nom, mot_de_passe=mot_de_passe)
            db.session.add(nouvel_utilisateur)
            db.session.commit()
            return redirect(url_for('home'))
        else:
            # Gérer le cas où l'utilisateur existe déjà
            pass

    return render_template('register.html')


from flask import flash

@app.route('/upload_csv', methods=['POST'])
def upload_csv():
    if 'fichier' not in request.files:
        flash("Aucun fichier sélectionné", "error")
        return redirect(url_for('home'))
    fichier = request.files['fichier']
    if fichier.filename == '':
        flash("Aucun fichier sélectionné", "error")
        return redirect(url_for('home'))
    if fichier:
        filename = secure_filename(fichier.filename)
        csv_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        fichier.save(csv_path)

        # Appeler la fonction pour créer une table à partir du fichier CSV
        create_table_from_csv(csv_path)

        # Analyse du fichier CSV
        df = pd.read_csv(csv_path)

        # Effectuer l'analyse requise
        nmb_colonnes = df.shape[1]
        nmb_lignes = df.shape[0]
        colonnes_numeriques = df.select_dtypes(include=['number']).columns.tolist()
        nmb_colonnes_numeriques = len(colonnes_numeriques)
        nmb_cellules_vides = df.isnull().sum().sum()
        total_cellules = nmb_colonnes * nmb_lignes
        pourcentage_vide = (nmb_cellules_vides / total_cellules) * 100 if total_cellules > 0 else 0

        # Passer les résultats à la page d'accueil
        flash(f"Nombre de colonnes : {nmb_colonnes}", "info")
        flash(f"Nombre de lignes : {nmb_lignes}", "info")
        flash(f"Nombre de colonnes numériques : {nmb_colonnes_numeriques}", "info")
        flash(f"Noms des colonnes numériques : {', '.join(colonnes_numeriques)}", "info")
        flash(f"Pourcentage de cellules vides dans les colonnes numériques : {pourcentage_vide:.2f}%", "info")

        return redirect(url_for('home'))
    else:
        flash("Erreur lors du téléchargement du fichier", "error")
        return redirect(url_for('home'))


@app.route('/remplir')
def remplir():
    

    flash('Les données ont été remplis avec succès.', 'success')
    return redirect(url_for('home'))


if __name__ == '__main__':
    app.run(debug=True)

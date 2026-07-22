import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import datetime, date
import io
import secrets
import smtplib
from email.mime.text import MIMEText

# Cartographie dynamique
import folium
from streamlit_folium import st_folium

# Exports PDF
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# ==========================================
# CONFIGURATION SMTP / MAIL ADMIN
# ==========================================
ADMIN_EMAIL = "issayoume2012@gmail.com"
SMTP_SENDER = "issayoume2012@gmail.com"
SMTP_PASSWORD = "qwhvzfvheaacdtsp"
APP_URL = "http://localhost:8501"

# ==========================================
# 0. BASE DE DONNÉES & FONCTIONS ESSENTIELLES
# ==========================================
UPLOAD_DIR = "uploads"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

DB_FILE = "agri_database.db"

def get_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def execute_db(query, params=()):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        last_id = cursor.lastrowid
    finally:
        conn.close()
    return last_id

def query_db(query, params=(), one=False):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rv = cursor.fetchall()
    finally:
        conn.close()
    return (rv[0] if rv else None) if one else rv

def query_df(query, params=()):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        data = cursor.fetchall()
        columns = [description[0] for description in cursor.description] if cursor.description else []
        df = pd.DataFrame(data, columns=columns)
    except Exception:
        df = pd.DataFrame()
    finally:
        conn.close()
    return df

def log_acces(email, action, statut, details=""):
    execute_db("""
        INSERT INTO me_logs_acces (user_email, action, date_evenement, statut, details)
        VALUES (?, ?, ?, ?, ?)
    """, (email, action, str(datetime.now()), statut, details))

# --- INITIALISATION FORCÉE DES TABLES SQL ---
def init_db():
    conn = get_db()
    try:
        cursor = conn.cursor()
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS me_tech (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT, prenom TEXT, gmail TEXT UNIQUE, phone TEXT, matricule TEXT, password TEXT, sync_gdocs INTEGER
        )""")

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS me_whitelist_emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            description TEXT,
            date_ajout TEXT
        )""")

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS me_autorisations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT,
            token TEXT UNIQUE,
            statut TEXT,
            date_demande TEXT,
            date_decision TEXT
        )""")

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS me_logs_acces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT,
            action TEXT,
            date_evenement TEXT,
            statut TEXT,
            details TEXT
        )""")

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS me_fil_discussion (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            auteur_nom TEXT,
            auteur_email TEXT,
            message TEXT,
            type_message TEXT,
            date_envoi TEXT
        )""")

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS me_notes_partagees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            auteur_email TEXT,
            auteur_nom TEXT,
            titre TEXT,
            categorie TEXT,
            contenu TEXT,
            date_creation TEXT
        )""")

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS me_champs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            nom TEXT, superficie_ha REAL, latitude REAL, longitude REAL, culture_actuelle TEXT, statut TEXT, icone_lieu TEXT
        )""")
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS me_historique_champs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, champ_id INTEGER,
            culture TEXT, date_debut TEXT, date_fin TEXT, rendement_kg REAL, remarques TEXT
        )""")

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS me_equipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            nom_groupe TEXT, chef_groupe TEXT, membres TEXT
        )""")
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS me_employes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            nom TEXT, role TEXT, groupe_id INTEGER, type_contrat TEXT, tarif_journalier REAL, salaire_mensuel REAL, photo_chemin TEXT, matricule_emp TEXT
        )""")

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS me_pointage (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            date TEXT, employe_nom TEXT, groupe_nom TEXT, champ_nom TEXT, statut_presence TEXT,
            heure_arrivee TEXT, heure_depart TEXT, heures_effectives REAL, remarque TEXT
        )""")

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS me_materiel (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            nom_materiel TEXT, categorie TEXT, etat TEXT, date_acquisition TEXT, remarques TEXT
        )""")

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS me_taches (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            champ_id INTEGER, groupe_id INTEGER, employe_id INTEGER, materiel_id INTEGER,
            type_travail TEXT, description TEXT, date_tache TEXT, heures_travaillees REAL, priorite TEXT, statut TEXT
        )""")

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS me_recoltes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            champ_id INTEGER, culture TEXT, date_recolte TEXT, quantite_kg REAL, prix_unitaire REAL
        )""")

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS me_depenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            champ_id INTEGER, type TEXT, montant REAL, date TEXT, facture_chemin TEXT
        )""")

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS me_intrants (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            nom TEXT, categorie TEXT, stock_actuel REAL, unite TEXT, seuil_alerte REAL, facture_chemin TEXT
        )""")

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS me_elevage (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            type_animaux TEXT, race TEXT, quantite INTEGER, date_arrivee TEXT, statut_sanitaire TEXT
        )""")

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS me_aquaculture (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            nom_bassin TEXT, espece_poisson TEXT, nombre_alvins INTEGER, aliment_kg REAL, ph_eau REAL
        )""")

        cursor.execute("INSERT OR IGNORE INTO me_whitelist_emails (email, description, date_ajout) VALUES (?, ?, ?)",
                       (ADMIN_EMAIL.lower(), "Administrateur Principal", str(datetime.now())))
        cursor.execute("INSERT OR IGNORE INTO me_tech (gmail, password, nom, prenom, sync_gdocs) VALUES (?, ?, ?, ?, 1)",
                       (ADMIN_EMAIL.lower(), "admin123", "Admin", "System"))

        conn.commit()
    finally:
        conn.close()

init_db()

# ==========================================
# VOTRE CODE MÉTIER / APPLICATION STREAMLIT
# ==========================================
st.title("Gestion Agricole - Application")
st.write("Base de données initialisée avec succès.")

# Exemple d'utilisation sécurisée :
USER_ID = 1 
champs_df = query_df("SELECT * FROM me_champs WHERE user_id = ?", (USER_ID,))

if not champs_df.empty:
    st.dataframe(champs_df)
else:
    st.info("Aucun champ enregistré pour le moment.")

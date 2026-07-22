import streamlit as st
import pandas as pd
import sqlite3
import os
import hashlib
import secrets
import smtplib
from datetime import datetime
from email.mime.text import MIMEText

# ==========================================
# CONFIGURATION SMTP / MAIL ADMIN
# ==========================================
ADMIN_EMAIL = "issayoume2012@gmail.com"      # Votre e-mail admin principal
SMTP_SENDER = "issayoume2012@gmail.com"      # Votre e-mail d'envoi
SMTP_PASSWORD = "qwhvzfvheaacdtsp"           # Mot de passe d'application Gmail
APP_URL = "http://localhost:8501"            # Remplacez par votre URL Streamlit Cloud

# ==========================================
# UTILITAIRES DE SÉCURITÉ (HASHING)
# ==========================================
def hash_secret(secret_str: str) -> str:
    """Hache un mot de passe ou un jeton avec SHA-256."""
    return hashlib.sha256(secret_str.encode('utf-8')).hexdigest()

# ==========================================
# 0. BASE DE DONNÉES & INITIALISATION SÉCURISÉE
# ==========================================
UPLOAD_DIR = "uploads"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

DB_FILE = "agri_database.db"

def get_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialise la base de données et crée toutes les tables si elles n'existent pas."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        # Table Techniciens
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS me_tech (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT, prenom TEXT, gmail TEXT UNIQUE, phone TEXT, matricule TEXT, password TEXT, sync_gdocs INTEGER
        )""")

        # Table Whitelist
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS me_whitelist_emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            description TEXT,
            date_ajout TEXT
        )""")

        # Table Autorisations
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS me_autorisations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT,
            token_hash TEXT UNIQUE,
            statut TEXT,
            date_demande TEXT,
            date_decision TEXT
        )""")

        # Table Logs d'accès
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS me_logs_acces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT,
            action TEXT,
            date_evenement TEXT,
            statut TEXT,
            details TEXT
        )""")

        # Table Discussion
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS me_fil_discussion (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            auteur_nom TEXT,
            auteur_email TEXT,
            message TEXT,
            type_message TEXT,
            date_envoi TEXT
        )""")

        # Table Notes Partagées
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

        # Tables Métiers Agronomie
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

        # Insertion de l'Admin principal par défaut
        cursor.execute("INSERT OR IGNORE INTO me_whitelist_emails (email, description, date_ajout) VALUES (?, ?, ?)",
                       (ADMIN_EMAIL.lower(), "Administrateur Principal", str(datetime.now())))
        
        admin_pwd_hash = hash_secret("admin123")
        cursor.execute("INSERT OR IGNORE INTO me_tech (gmail, password, nom, prenom, sync_gdocs) VALUES (?, ?, ?, ?, 1)",
                       (ADMIN_EMAIL.lower(), admin_pwd_hash, "Admin", "System"))

        conn.commit()
    finally:
        conn.close()

# Exécution de sécurité pour créer les tables
init_db()

def query_db(query, params=(), one=False):
    """Effectue une requête SQL classique de manière sécurisée."""
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rv = cursor.fetchall()
        return (rv[0] if rv else None) if one else rv
    except sqlite3.OperationalError:
        init_db()
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(query, params)
        rv = cursor.fetchall()
        return (rv[0] if rv else None) if one else rv
    finally:
        conn.close()

def query_df(query, params=()):
    """Lecture sécurisée d'un Dataframe Pandas (RÉSOLUTIF POUR L'ERREUR PANDAS)."""
    conn = get_db()
    try:
        return pd.read_sql_query(query, conn, params=params)
    except (pd.errors.DatabaseError, sqlite3.OperationalError):
        # Si la table n'existe pas ou la base est fermée, reconstruire et réessayer
        init_db()
        conn = get_db()
        return pd.read_sql_query(query, conn, params=params)
    except Exception:
        # Retourne un DataFrame vide au lieu de faire planter Streamlit
        return pd.DataFrame()
    finally:
        conn.close()

def execute_db(query, params=()):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()

# ==========================================
# FONCTIONS LOGS & ENVOI D'E-MAILS
# ==========================================
def log_acces(email, action, statut, details=""):
    execute_db("""
        INSERT INTO me_logs_acces (user_email, action, date_evenement, statut, details)
        VALUES (?, ?, ?, ?, ?)
    """, (email, action, str(datetime.now()), statut, details))

def envoyer_mail_demande_autorisation(user_email, raw_token):
    link_approve = f"{APP_URL}/?action=approve&token={raw_token}"
    link_reject = f"{APP_URL}/?action=reject&token={raw_token}"

    corps_html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <h2 style="color: #10B981;">🔐 Nouvelle demande d'accès - AgriGestion Pro</h2>
        <p>L'utilisateur <b>{user_email}</b> demande l'autorisation de se connecter au système.</p>
        <p><b>Date & Heure :</b> {datetime.now().strftime('%d/%m/%Y à %H:%M:%S')}</p>
        <hr style="border: none; border-top: 1px solid #ddd;">
        <p>Vous pouvez approuver ou refuser directement cette demande en cliquant ci-dessous :</p>
        <p style="margin-top: 20px;">
            <a href="{link_approve}" style="background-color: #10B981; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">🟢 APPROUVER L'ACCÈS</a>
            &nbsp;&nbsp;&nbsp;
            <a href="{link_reject}" style="background-color: #EF4444; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">🔴 REFUSER L'ACCÈS</a>
        </p>
      </body>
    </html>
    """
    
    msg = MIMEText(corps_html, 'html')
    msg['Subject'] = f"🔔 Demande d'accès en attente : {user_email}"
    msg['From'] = SMTP_SENDER
    msg['To'] = ADMIN_EMAIL

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SMTP_SENDER, SMTP_PASSWORD)
            server.sendmail(SMTP_SENDER, ADMIN_EMAIL, msg.as_string())
        return True
    except Exception:
        return False

# ==========================================
# 1. CONFIGURATION STYLES STREAMLIT
# ==========================================
st.set_page_config(
    page_title="AgriGestion Pro",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
    <style>
        .block-container { padding-top: 1rem; padding-bottom: 2rem; padding-left: 1rem; padding-right: 1rem; }
        .stButton>button { width: 100%; border-radius: 8px; height: 3em; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. TRAITEMENT DES LIENS D'APPROBATION E-MAIL
# ==========================================
params = st.query_params
if "action" in params and "token" in params:
    act = params["action"]
    tok_raw = params["token"]
    tok_hash = hash_secret(tok_raw)
    
    req = query_db("SELECT * FROM me_autorisations WHERE token_hash = ?", (tok_hash,), one=True)
    if req:
        if act == "approve":
            execute_db("UPDATE me_autorisations SET statut = 'APPROUVE', date_decision = ? WHERE token_hash = ?", (str(datetime.now()), tok_hash))
            log_acces(req['user_email'], "APPROVAL_EMAIL", "SUCCÈS", "Demande approuvée par e-mail.")
            st.success(f"✅ Accès ACCORDÉ pour l'utilisateur **{req['user_email']}**.")
        elif act == "reject":
            execute_db("UPDATE me_autorisations SET statut = 'REFUSE', date_decision = ? WHERE token_hash = ?", (str(datetime.now()), tok_hash))
            log_acces(req['user_email'], "APPROVAL_EMAIL", "REFUSÉ", "Demande refusée par e-mail.")
            st.error(f"❌ Accès REFUSÉ pour l'utilisateur **{req['user_email']}**.")
    else:
        st.warning("⚠️ Jeton de demande non valide ou expiré.")
    st.stop()

# ==========================================
# 3. AUTHENTIFICATION & SESSIONS
# ==========================================
if "user" not in st.session_state:
    st.session_state.user = None
if "pending_token_hash" not in st.session_state:
    st.session_state.pending_token_hash = None

def auth_system():
    if st.session_state.user is None:
        st.title("🌾 AgriGestion Pro")
        
        if st.session_state.pending_token_hash:
            st.info(f"⏳ **Votre demande d'accès a été enregistrée et transmise à l'administrateur ({ADMIN_EMAIL}).**")
            
            req = query_db("SELECT * FROM me_autorisations WHERE token_hash = ?", (st.session_state.pending_token_hash,), one=True)
            if req:
                if req['statut'] == 'APPROUVE':
                    user = query_db("SELECT * FROM me_tech WHERE gmail = ?", (req['user_email'],), one=True)
                    st.session_state.user = dict(user)
                    st.session_state.pending_token_hash = None
                    log_acces(req['user_email'], "LOGIN", "SUCCÈS", "Accès débloqué après validation.")
                    st.success("✅ Accès accordé ! Redirection...")
                    st.rerun()
                elif req['statut'] == 'REFUSE':
                    st.error("❌ Votre demande d'accès a été refusée par l'administrateur.")
                    if st.button("Nouvelle tentative"):
                        st.session_state.pending_token_hash = None
                        st.rerun()
                else:
                    st.warning("🔄 En attente de validation par l'administrateur...")
                    if st.button("🔄 Vérifier l'état de ma demande"):
                        st.rerun()
            return False

        tab_login, tab_register = st.tabs(["🔑 Connexion", "📝 Inscription"])

        with tab_login:
            gmail_in = st.text_input("Adresse Email", key="l_email").strip().lower()
            pwd_in = st.text_input("Mot de passe", type="password", key="l_pwd")
            
            if st.button("Se Connecter", type="primary"):
                if not gmail_in or not pwd_in:
                    st.warning("⚠️ Veuillez remplir tous les champs.")
                else:
                    in_whitelist = query_db("SELECT * FROM me_whitelist_emails WHERE email = ?", (gmail_in,), one=True)
                    if not in_whitelist:
                        st.error("❌ Accès Refusé : Cet e-mail n'est pas pré-autorisé sur la Liste Blanche.")
                        log_acces(gmail_in, "LOGIN_ATTEMPT", "BLOQUÉ_WHITELIST", "Adresse absente de la liste blanche.")
                    else:
                        pwd_hash = hash_secret(pwd_in)
                        user = query_db("SELECT * FROM me_tech WHERE gmail = ? AND password = ?", (gmail_in, pwd_hash), one=True)
                        if user:
                            if gmail_in == ADMIN_EMAIL.lower():
                                st.session_state.user = dict(user)
                                log_acces(gmail_in, "LOGIN_ADMIN", "SUCCÈS", "Accès admin direct.")
                                st.rerun()
                            else:
                                raw_token = secrets.token_hex(16)
                                tok_hash = hash_secret(raw_token)
                                execute_db("""
                                    INSERT INTO me_autorisations (user_email, token_hash, statut, date_demande)
                                    VALUES (?, ?, 'EN_ATTENTE', ?)
                                """, (gmail_in, tok_hash, str(datetime.now())))
                                
                                envoyer_mail_demande_autorisation(gmail_in, raw_token)
                                st.session_state.pending_token_hash = tok_hash
                                log_acces(gmail_in, "DEMANDE_AUTORISATION", "EN_ATTENTE", "Demande transmise à l'admin.")
                                st.rerun()
                        else:
                            st.error("❌ Identifiants incorrects.")

        with tab_register:
            with st.form("f_reg"):
                nom = st.text_input("Nom *")
                prenom = st.text_input("Prénom *")
                gmail = st.text_input("Email *").strip().lower()
                password = st.text_input("Mot de passe *", type="password")
                if st.form_submit_button("S'inscrire"):
                    if nom and prenom and gmail and password:
                        in_whitelist = query_db("SELECT * FROM me_whitelist_emails WHERE email = ?", (gmail,), one=True)
                        if not in_whitelist:
                            st.error("❌ Votre adresse doit être ajoutée à la Liste Blanche par l'administrateur.")
                        else:
                            try:
                                pwd_hash = hash_secret(password)
                                execute_db("INSERT INTO me_tech (nom, prenom, gmail, password, sync_gdocs) VALUES (?, ?, ?, ?, 1)", (nom, prenom, gmail, pwd_hash))
                                st.success("✅ Compte créé avec succès ! Connectez-vous maintenant.")
                            except sqlite3.IntegrityError:
                                st.error("❌ Un compte existe déjà pour cet e-mail.")
        return False
    return True

if not auth_system():
    st.stop()

USER_ID = st.session_state.user['id']
USER_DATA = st.session_state.user

# ==========================================
# 4. DASHBOARD & INTERFACE PRINCIPALE
# ==========================================
col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.markdown(f"### 🌾 Session : **{USER_DATA['prenom']} {USER_DATA['nom']}** ({USER_DATA['gmail']})")
with col_h2:
    if st.button("🚪 Déconnexion"):
        log_acces(USER_DATA['gmail'], "LOGOUT", "SUCCÈS", "Déconnexion.")
        st.session_state.user = None
        st.session_state.pending_token_hash = None
        st.rerun()

# --- LIGNE 433 SÉCURISÉE ---
champs_df = query_df("SELECT * FROM me_champs WHERE user_id = ?", (USER_ID,))

if not champs_df.empty:
    liste_champs = {row['nom']: (row['id'], row['latitude'], row['longitude']) for _, row in champs_df.iterrows()}
    if "selected_parcelle_name" not in st.session_state or st.session_state.selected_parcelle_name not in liste_champs:
        st.session_state.selected_parcelle_name = list(liste_champs.keys())[0]

    parcelle_active_nom = st.selectbox("📍 **Parcelle sélectionnée :**", list(liste_champs.keys()), index=list(liste_champs.keys()).index(st.session_state.selected_parcelle_name))
    st.session_state.selected_parcelle_name = parcelle_active_nom
    champ_id_actif, champ_lat_actif, champ_lon_actif = liste_champs[parcelle_active_nom]
else:
    champ_id_actif, champ_lat_actif, champ_lon_actif = None, 16.0300, -16.4800
    parcelle_active_nom = "Aucune parcelle"

tabs_titles = [
    "📊 TBD", "🤝 Espace Commun Techniciens", "🌱 Parcelles & Historique", "👥 Personnel & Équipes", "⏰ Pointages",
    "📅 Travaux & Matériel", "🐓 Élevage", "🐟 Pisciculture", "🌾 Récoltes", "💰 Finances", "📄 Rapports Automatisés"
]

if USER_DATA['gmail'].lower() == ADMIN_EMAIL.lower():
    tabs_titles.append("🛡️ Demandes d'Accès & Sécurité")

main_tabs = st.tabs(tabs_titles)

# --- TAB 1 : DASHBOARD ---
with main_tabs[0]:
    st.subheader("📊 Aperçu Général de l'Exploitation")
    k1, k2, k3, k4 = st.columns(4)

    surf_tot_req = query_db("SELECT SUM(superficie_ha) as total FROM me_champs WHERE user_id = ?", (USER_ID,), one=True)
    surf_tot = surf_tot_req['total'] if (surf_tot_req and surf_tot_req['total'] is not None) else 0.0

    emp_tot_req = query_db("SELECT COUNT(*) as total FROM me_employes WHERE user_id = ?", (USER_ID,), one=True)
    emp_tot = emp_tot_req['total'] if (emp_tot_req and emp_tot_req['total'] is not None) else 0

    anim_tot_req = query_db("SELECT SUM(quantite) as total FROM me_elevage WHERE user_id = ?", (USER_ID,), one=True)
    anim_tot = anim_tot_req['total'] if (anim_tot_req and anim_tot_req['total'] is not None) else 0

    rec_tot_req = query_db("SELECT SUM(quantite_kg) as total FROM me_recoltes WHERE user_id = ?", (USER_ID,), one=True)
    rec_tot = rec_tot_req['total'] if (rec_tot_req and rec_tot_req['total'] is not None) else 0.0
    
    k1.metric("Superficie Totale", f"{surf_tot:.1f} Ha")
    k2.metric("Personnel Actif", f"{emp_tot}")
    k3.metric("Bétail / Animaux", f"{anim_tot}")
    k4.metric("Récoltes Cumulées", f"{rec_tot/1000:.2f} T")
    
    if not champs_df.empty:
        st.dataframe(champs_df[["nom", "superficie_ha", "culture_actuelle", "statut"]], use_container_width=True)
    else:
        st.info("Aucune parcelle ajoutée pour le moment. Allez dans l'onglet 'Parcelles & Historique' pour en créer une.")

# --- TAB 2 : ESPACE COMMUN TECHNICIENS ---
with main_tabs[1]:
    st.subheader("🤝 Espace Commun de Collaboration entre Techniciens")
    comm_t1, comm_t2 = st.tabs(["💬 Fil d'Actualité", "📚 Base de Connaissances"])

    with comm_t1:
        with st.form("f_post_comm", clear_on_submit=True):
            type_m = st.selectbox("Type d'annonce", ["INFO", "ALERTE", "QUESTION"])
            msg_comm = st.text_area("Message pour l'équipe *")
            if st.form_submit_button("Publier"):
                if msg_comm:
                    nom_auteur = f"{USER_DATA['prenom']} {USER_DATA['nom']}"
                    execute_db("""
                        INSERT INTO me_fil_discussion (auteur_nom, auteur_email, message, type_message, date_envoi)
                        VALUES (?, ?, ?, ?, ?)
                    """, (nom_auteur, USER_DATA['gmail'], msg_comm, type_m, str(datetime.now().strftime('%d/%m/%Y %H:%M'))))
                    st.success("Publié !")
                    st.rerun()

        fil_df = query_df("SELECT * FROM me_fil_discussion ORDER BY id DESC LIMIT 30")
        if not fil_df.empty:
            for _, row in fil_df.iterrows():
                st.markdown(f"**{row['auteur_nom']}** (`{row['type_message']}`) - *{row['date_envoi']}*")
                st.write(row['message'])
                st.divider()

    with comm_t2:
        notes_df = query_df("SELECT * FROM me_notes_partagees ORDER BY id DESC")
        if not notes_df.empty:
            st.dataframe(notes_df, use_container_width=True)

# --- TAB 3 : PARCELLES ET HISTORIQUE ---
with main_tabs[2]:
    st.subheader("🌱 Parcelles & Terrains")
    with st.form("form_add_p", clear_on_submit=True):
        nom_p = st.text_input("Nom Parcelle *")
        surf_p = st.number_input("Superficie (Ha)", min_value=0.1, value=1.0)
        lat_p = st.number_input("Latitude", value=16.0300)
        lon_p = st.number_input("Longitude", value=-16.4800)
        cult_p = st.text_input("Culture")
        if st.form_submit_button("Ajouter Parcelle"):
            if nom_p:
                execute_db("INSERT INTO me_champs (user_id, nom, superficie_ha, latitude, longitude, culture_actuelle, statut) VALUES (?, ?, ?, ?, ?, ?, 'Actif')",
                           (USER_ID, nom_p, surf_p, lat_p, lon_p, cult_p))
                st.success("Parcelle ajoutée !")
                st.rerun()

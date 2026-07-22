import streamlit as st
import pandas as pd
import sqlite3
import os
import hashlib
import io
import secrets
import smtplib
from datetime import datetime, date
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
ADMIN_EMAIL = "issayoume2012@gmail.com"      # Votre e-mail admin principal
SMTP_SENDER = "issayoume2012@gmail.com"      # Votre e-mail d'envoi
SMTP_PASSWORD = "qwhvzfvheaacdtsp"           # Mot de passe d'application Gmail
APP_URL = "http://localhost:8501"            # Remplacez par votre URL de production

# ==========================================
# UTILITAIRES DE SÉCURITÉ (HASHING)
# ==========================================
def hash_secret(secret_str: str) -> str:
    """Hache un mot de passe ou un jeton avec SHA-256."""
    return hashlib.sha256(secret_str.encode('utf-8')).hexdigest()

# ==========================================
# 0. BASE DE DONNÉES & INITIALISATION
# ==========================================
UPLOAD_DIR = "uploads"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

DB_FILE = "agri_database.db"

def get_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Table des techniciens/utilisateurs
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS me_tech (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT, prenom TEXT, gmail TEXT UNIQUE, phone TEXT, matricule TEXT, password TEXT, sync_gdocs INTEGER
        )""")

        # Table Whitelist (E-mails pré-autorisés)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS me_whitelist_emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            description TEXT,
            date_ajout TEXT
        )""")

        # Table des demandes d'autorisation d'accès
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS me_autorisations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT,
            token_hash TEXT UNIQUE,
            statut TEXT, -- 'EN_ATTENTE', 'APPROUVE', 'REFUSE'
            date_demande TEXT,
            date_decision TEXT
        )""")

        # Table des logs d'accès
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS me_logs_acces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT,
            action TEXT,
            date_evenement TEXT,
            statut TEXT,
            details TEXT
        )""")

        # Table Fil de Discussion Commun
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS me_fil_discussion (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            auteur_nom TEXT,
            auteur_email TEXT,
            message TEXT,
            type_message TEXT,
            date_envoi TEXT
        )""")

        # Table Base de Connaissances
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

        # Tables Métiers de Gestion de Ferme
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

        # Inscription d'office de l'Admin dans la Whitelist et la table des comptes
        cursor.execute("INSERT OR IGNORE INTO me_whitelist_emails (email, description, date_ajout) VALUES (?, ?, ?)",
                       (ADMIN_EMAIL.lower(), "Administrateur Principal", str(datetime.now())))
        
        admin_pwd_hash = hash_secret("admin123")
        cursor.execute("INSERT OR IGNORE INTO me_tech (gmail, password, nom, prenom, sync_gdocs) VALUES (?, ?, ?, ?, 1)",
                       (ADMIN_EMAIL.lower(), admin_pwd_hash, "Admin", "System"))

        conn.commit()

init_db()

def query_db(query, params=(), one=False):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rv = cursor.fetchall()
        return (rv[0] if rv else None) if one else rv

def query_df(query, params=()):
    with get_db() as conn:
        try:
            df = pd.read_sql_query(query, conn, params=params)
        except Exception:
            init_db()
            try:
                df = pd.read_sql_query(query, conn, params=params)
            except Exception:
                df = pd.DataFrame()
        return df

def execute_db(query, params=()):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        return cursor.lastrowid

# ==========================================
# FONCTIONS DE LOGS & ENVOI D'E-MAILS D'ACCÈS
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
    msg['Subject'] = f"🔔 Demande d'accès en attente de validation : {user_email}"
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
        @media (max-width: 768px) {
            .stTabs [data-baseweb="tab-list"] { gap: 2px; }
            .stTabs [data-baseweb="tab"] { font-size: 11px; padding: 4px 6px; }
        }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. GESTION DES LIENS DE VALIDATION (CLIC EMAIL)
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
            log_acces(req['user_email'], "APPROVAL_EMAIL", "SUCCÈS", f"Demande approuvée par e-mail.")
            st.success(f"✅ Accès ACCORDÉ pour l'utilisateur **{req['user_email']}**.")
        elif act == "reject":
            execute_db("UPDATE me_autorisations SET statut = 'REFUSE', date_decision = ? WHERE token_hash = ?", (str(datetime.now()), tok_hash))
            log_acces(req['user_email'], "APPROVAL_EMAIL", "REFUSÉ", f"Demande refusée par e-mail.")
            st.error(f"❌ Accès REFUSÉ pour l'utilisateur **{req['user_email']}**.")
    else:
        st.warning("⚠️ Jeton de demande non valide ou expiré.")
    st.stop()

# ==========================================
# 3. AUTHENTIFICATION & PROCESSUS D'ACCÈS
# ==========================================
if "user" not in st.session_state:
    st.session_state.user = None
if "pending_token_hash" not in st.session_state:
    st.session_state.pending_token_hash = None

def auth_system():
    if st.session_state.user is None:
        st.title("🌾 AgriGestion Pro")
        
        # Écran d'attente lors d'une demande envoyée
        if st.session_state.pending_token_hash:
            st.info(f"⏳ **Votre demande d'accès a été enregistrée et transmise à l'administrateur ({ADMIN_EMAIL}).**")
            st.write("Veuillez patienter pendant la vérification. Dès que l'administrateur valide votre demande via l'e-mail ou son panneau d'administration, vous pourrez accéder à l'application.")
            
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
                    log_acces(req['user_email'], "LOGIN", "REFUSÉ", "Accès refusé.")
                    if st.button("Nouvelle tentative"):
                        st.session_state.pending_token_hash = None
                        st.rerun()
                else:
                    st.warning("🔄 En attente de validation par l'administrateur...")
                    if st.button("🔄 Vérifier l'état de ma demande"):
                        st.rerun()
            return False

        # Formulaires Connexion / Inscription
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
                                log_acces(gmail_in, "LOGIN_ADMIN", "SUCCÈS", "Accès administrateur direct.")
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
                                log_acces(gmail_in, "DEMANDE_AUTORISATION", "EN_ATTENTE", f"Demande transmise à l'admin.")
                                st.rerun()
                        else:
                            st.error("❌ Identifiants incorrects.")
                            log_acces(gmail_in, "LOGIN_ATTEMPT", "ÉCHEC", "Mot de passe erroné.")

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
                            st.error("❌ Inscription impossible : Votre adresse doit être ajoutée à la Liste Blanche par l'administrateur.")
                            log_acces(gmail, "REGISTRATION_ATTEMPT", "BLOQUÉ_WHITELIST", "Tentative d'inscription hors whitelist.")
                        else:
                            try:
                                pwd_hash = hash_secret(password)
                                execute_db("INSERT INTO me_tech (nom, prenom, gmail, password, sync_gdocs) VALUES (?, ?, ?, ?, 1)", (nom, prenom, gmail, pwd_hash))
                                log_acces(gmail, "REGISTRATION", "SUCCÈS", "Compte utilisateur créé.")
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
# 4. NAVIGATION & PARCELLE ACTIVE
# ==========================================
col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.markdown(f"### 🌾 Session : **{USER_DATA['prenom']} {USER_DATA['nom']}** ({USER_DATA['gmail']})")
with col_h2:
    if st.button("🚪 Déconnexion"):
        log_acces(USER_DATA['gmail'], "LOGOUT", "SUCCÈS", "Déconnexion de l'utilisateur.")
        st.session_state.user = None
        st.session_state.pending_token_hash = None
        st.rerun()

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

# ==========================================
# GENERATION RAPPORT PDF
# ==========================================
def generate_full_pdf_report(user_data, period_title, filter_month=None, filter_year=None):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
    elements = []
    
    styles = getSampleStyleSheet()
    subtitle_style = ParagraphStyle('CustomSub', parent=styles['Normal'], fontSize=11, leading=14, textColor=colors.HexColor('#4B5563'), spaceAfter=10)

    elements.append(Paragraph("<b>RAPPORT GLOBAL D'EXPLOITATION AUTOMATISÉ</b>", styles['Title']))
    elements.append(Paragraph(f"<b>Période / Titre : {period_title}</b>", subtitle_style))
    elements.append(Paragraph(f"Exploitant : {user_data['prenom']} {user_data['nom']} | Date : {date.today()}", styles['Normal']))
    elements.append(Spacer(1, 10))

    def add_section(title, df):
        elements.append(Paragraph(f"<b>{title}</b>", styles.get('Heading2', styles['Normal'])))
        if not df.empty:
            df_str = df.astype(str)
            data = [list(df_str.columns)] + df_str.values.tolist()
            t = Table(data)
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#10B981')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('FONTSIZE', (0,0), (-1,-1), 7),
                ('GRID', (0,0), (-1,-1), 0.5, colors.grey)
            ]))
            elements.append(t)
        else:
            elements.append(Paragraph("<i>Aucune donnée enregistrée pour cette période.</i>", styles['Normal']))
        elements.append(Spacer(1, 10))

    month_str = f"{filter_year:04d}-{filter_month:02d}" if (filter_month and filter_year) else None

    add_section("1. Parcelles & Terrains", query_df("SELECT nom, superficie_ha, culture_actuelle, statut FROM me_champs WHERE user_id = ?", (USER_ID,)))
    add_section("2. Personnel & Salaires", query_df("SELECT nom, role, type_contrat, tarif_journalier, salaire_mensuel FROM me_employes WHERE user_id = ?", (USER_ID,)))
    
    if month_str:
        add_section("3. Pointages du Mois", query_df("SELECT date, employe_nom, statut_presence, heures_effectives FROM me_pointage WHERE user_id = ? AND date LIKE ? ORDER BY date DESC", (USER_ID, f"{month_str}%")))
        add_section("4. Tâches du Mois", query_df("SELECT type_travail, description, date_tache, priorite, statut FROM me_taches WHERE user_id = ? AND date_tache LIKE ?", (USER_ID, f"{month_str}%")))
        add_section("5. Récoltes du Mois", query_df("SELECT culture, date_recolte, quantite_kg, prix_unitaire FROM me_recoltes WHERE user_id = ? AND date_recolte LIKE ?", (USER_ID, f"{month_str}%")))
        add_section("6. Dépenses Financières du Mois", query_df("SELECT type, montant, date FROM me_depenses WHERE user_id = ? AND date LIKE ?", (USER_ID, f"{month_str}%")))
    else:
        add_section("3. Derniers Pointages", query_df("SELECT date, employe_nom, statut_presence, heures_effectives FROM me_pointage WHERE user_id = ? ORDER BY date DESC LIMIT 15", (USER_ID,)))
        add_section("4. Tâches & Affectations", query_df("SELECT type_travail, description, date_tache, priorite, statut FROM me_taches WHERE user_id = ?", (USER_ID,)))
        add_section("5. Récoltes", query_df("SELECT culture, date_recolte, quantite_kg, prix_unitaire FROM me_recoltes WHERE user_id = ?", (USER_ID,)))
        add_section("6. Dépenses Financières", query_df("SELECT type, montant, date FROM me_depenses WHERE user_id = ?", (USER_ID,)))

    doc.build(elements)
    return buffer.getvalue()

# ==========================================
# MODULES APPLICATIFS
# ==========================================

# --- TAB 1 : DASHBOARD ---
with main_tabs[0]:
    st.subheader("📊 Aperçu Général de l'Exploitation")
    k1, k2, k3, k4 = st.columns(4)
    surf_tot_req = query_db("SELECT SUM(superficie_ha) as total FROM me_champs WHERE user_id = ?", (USER_ID,), one=True)
    surf_tot = surf_tot_req['total'] if surf_tot_req and surf_tot_req['total'] else 0

    emp_tot_req = query_db("SELECT COUNT(*) as total FROM me_employes WHERE user_id = ?", (USER_ID,), one=True)
    emp_tot = emp_tot_req['total'] if emp_tot_req and emp_tot_req['total'] else 0

    anim_tot_req = query_db("SELECT SUM(quantite) as total FROM me_elevage WHERE user_id = ?", (USER_ID,), one=True)
    anim_tot = anim_tot_req['total'] if anim_tot_req and anim_tot_req['total'] else 0

    rec_tot_req = query_db("SELECT SUM(quantite_kg) as total FROM me_recoltes WHERE user_id = ?", (USER_ID,), one=True)
    rec_tot = rec_tot_req['total'] if rec_tot_req and rec_tot_req['total'] else 0
    
    k1.metric("Superficie Totale", f"{surf_tot:.1f} Ha")
    k2.metric("Personnel Actif", f"{emp_tot}")
    k3.metric("Bétail / Animaux", f"{anim_tot}")
    k4.metric("Récoltes Cumulées", f"{rec_tot/1000:.2f} T")
    if not champs_df.empty:
        st.dataframe(champs_df[["nom", "superficie_ha", "culture_actuelle", "statut"]], use_container_width=True)

# --- TAB 2 : ESPACE COMMUN TECHNICIENS ---
with main_tabs[1]:
    st.subheader("🤝 Espace Commun de Collaboration entre Techniciens")
    st.info("💡 Cet espace interactif est accessible à l'ensemble des techniciens autorisés sur la plateforme.")
    
    comm_t1, comm_t2, comm_t3 = st.tabs([
        "💬 Fil d'Actualité & Messagerie", 
        "📚 Base de Connaissances & Fiches", 
        "👥 Annuaire des Techniciens"
    ])

    with comm_t1:
        st.write("#### 📢 Messages, Annonces & Alertes Partagées")
        
        with st.form("f_post_comm", clear_on_submit=True):
            type_m = st.selectbox("Type d'annonce", ["INFO (Information)", "ALERTE (Sanitaire/Météo)", "QUESTION (Besoin d'aide)"])
            msg_comm = st.text_area("Votre message pour l'équipe *", placeholder="Rédigez un message, une observation terrain ou une alerte...")
            if st.form_submit_button("Publier sur le réseau"):
                if msg_comm:
                    nom_auteur = f"{USER_DATA['prenom']} {USER_DATA['nom']}"
                    execute_db("""
                        INSERT INTO me_fil_discussion (auteur_nom, auteur_email, message, type_message, date_envoi)
                        VALUES (?, ?, ?, ?, ?)
                    """, (nom_auteur, USER_DATA['gmail'], msg_comm, type_m, str(datetime.now().strftime('%d/%m/%Y %H:%M'))))
                    st.success("Message publié !")
                    st.rerun()

        st.divider()
        st.write("##### 📜 Historique des Échanges")
        fil_df = query_df("SELECT * FROM me_fil_discussion ORDER BY id DESC LIMIT 50")
        if not fil_df.empty:
            for _, row in fil_df.iterrows():
                badge = "🔴" if "ALERTE" in str(row['type_message']) else ("🟡" if "QUESTION" in str(row['type_message']) else "🟢")
                with st.expander(f"{badge} **{row['auteur_nom']}** - *{row['date_envoi']}* [{row['type_message']}]"):
                    st.write(row['message'])
                    st.caption(f"Auteur : {row['auteur_email']}")
        else:
            st.info("Aucun message publié pour le moment.")

    with comm_t2:
        st.write("#### 📖 Centre de Documentation & Fiches Techniques")
        
        with st.expander("➕ Rédiger et Partager une nouvelle Fiche Technique"):
            with st.form("f_add_note_comm", clear_on_submit=True):
                t_note = st.text_input("Titre de la Fiche *", placeholder="Ex: Traitement bio contre le mildiou")
                cat_note = st.selectbox("Catégorie", ["Irrigation & Sol", "Protection des Cultures", "Élevage & Santé", "Machinisme", "Autre"])
                c_note = st.text_area("Description / Procédure *", height=180)
                if st.form_submit_button("Publier la Fiche Technique"):
                    if t_note and c_note:
                        nom_auteur = f"{USER_DATA['prenom']} {USER_DATA['nom']}"
                        execute_db("""
                            INSERT INTO me_notes_partagees (auteur_email, auteur_nom, titre, categorie, contenu, date_creation)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (USER_DATA['gmail'], nom_auteur, t_note, cat_note, c_note, str(datetime.now().strftime('%d/%m/%Y'))))
                        st.success("Fiche technique ajoutée !")
                        st.rerun()

        notes_df = query_df("SELECT * FROM me_notes_partagees ORDER BY id DESC")
        if not notes_df.empty:
            for _, r in notes_df.iterrows():
                st.markdown(f"### 📄 {r['titre']} `[{r['categorie']}]`")
                st.caption(f"Rédigé par **{r['auteur_nom']}** ({r['auteur_email']}) le {r['date_creation']}")
                st.markdown(r['contenu'])
                st.divider()
        else:
            st.info("Aucune fiche technique partagée.")

    with comm_t3:
        st.write("#### 👥 Répertoire des Techniciens Enregistrés")
        tech_df = query_df("SELECT prenom, nom, gmail, phone, matricule FROM me_tech")
        st.dataframe(tech_df, use_container_width=True)

# --- TAB 3 : PARCELLES ET HISTORIQUE ---
with main_tabs[2]:
    st.subheader("🌱 Gestion des Parcelles & Historique des Cultures")
    p_tab1, p_tab2 = st.tabs(["📍 Carte & Création", "📜 Historique"])

    with p_tab1:
        col_m, col_f = st.columns([2, 1])
        with col_m:
            m = folium.Map(location=[champ_lat_actif, champ_lon_actif], zoom_start=14)
            for _, r in champs_df.iterrows():
                folium.Marker([r['latitude'], r['longitude']], popup=f"{r['nom']} ({r['culture_actuelle']})").add_to(m)
            st_folium(m, width="100%", height=350, key="folium_map")
        with col_f:
            with st.form("form_p", clear_on_submit=True):
                nom_p = st.text_input("Nom de la Parcelle *")
                surf_p = st.number_input("Superficie (Ha)", min_value=0.1, value=1.0)
                lat_p = st.number_input("Latitude", value=float(champ_lat_actif), format="%.6f")
                lon_p = st.number_input("Longitude", value=float(champ_lon_actif), format="%.6f")
                cult_p = st.text_input("Culture Actuelle")
                stat_p = st.selectbox("Statut", ["Préparation", "Semé", "En Croissance", "En Récolte", "En Friche"])
                if st.form_submit_button("Créer la Parcelle"):
                    if nom_p:
                        execute_db("INSERT INTO me_champs (user_id, nom, superficie_ha, latitude, longitude, culture_actuelle, statut) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                   (USER_ID, nom_p, surf_p, lat_p, lon_p, cult_p, stat_p))
                        st.success("Parcelle enregistrée !")
                        st.rerun()

    with p_tab2:
        st.write(f"#### Historique pour : **{parcelle_active_nom}**")
        with st.expander("➕ Enregistrer une saison passée"):
            with st.form("f_hist_add"):
                c_hist = st.text_input("Culture passée", value="Maïs")
                d_dep = st.date_input("Date Début Plantation", value=date.today())
                d_fin = st.date_input("Date Récolte", value=date.today())
                rend_h = st.number_input("Rendement (Kg)", value=0.0)
                rem_h = st.text_area("Remarques & Bilan")
                if st.form_submit_button("Ajouter à l'Historique"):
                    if champ_id_actif:
                        execute_db("""
                            INSERT INTO me_historique_champs (user_id, champ_id, culture, date_debut, date_fin, rendement_kg, remarques)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (USER_ID, champ_id_actif, c_hist, str(d_dep), str(d_fin), rend_h, rem_h))
                        st.success("Historique ajouté !")
                        st.rerun()
                    else:
                        st.error("Aucune parcelle sélectionnée.")

        if champ_id_actif:
            hist_df = query_df("SELECT culture, date_debut, date_fin, rendement_kg, remarques FROM me_historique_champs WHERE user_id = ? AND champ_id = ?", (USER_ID, champ_id_actif))
            st.dataframe(hist_df, use_container_width=True)

# --- TAB RAPPORT AUTOMATISÉ ---
with main_tabs[10]:
    st.subheader("📄 Génération de Rapports PDF Automatisés")
    col_r1, col_r2 = st.columns(2)
    with col_r1:
        rep_type = st.radio("Portée du Rapport", ["Rapport Mensuel Spécifique", "Rapport Global Cumulé"])
    with col_r2:
        m_sel = st.selectbox("Mois", list(range(1, 13)), index=datetime.now().month - 1)
        y_sel = st.number_input("Année", value=datetime.now().year, step=1)

    if st.button("📥 Générer et Télécharger le Rapport PDF", type="primary"):
        if rep_type == "Rapport Mensuel Spécifique":
            pdf_data = generate_full_pdf_report(USER_DATA, f"Mois de {m_sel:02d}/{y_sel}", filter_month=m_sel, filter_year=y_sel)
            filename = f"Rapport_Agri_{m_sel:02d}_{y_sel}.pdf"
        else:
            pdf_data = generate_full_pdf_report(USER_DATA, "Bilan Global d'Exploitation")
            filename = "Rapport_Agri_Global.pdf"

        st.download_button("💾 Cliquer ici pour télécharger le PDF", data=pdf_data, file_name=filename, mime="application/pdf")

# --- TAB SÉCURITÉ ADMIN (Si applicable) ---
if USER_DATA['gmail'].lower() == ADMIN_EMAIL.lower() and len(main_tabs) > 11:
    with main_tabs[11]:
        st.subheader("🛡️ Panneau d'Administration & Gestion des Accès")
        
        st.write("#### 📜 Demandes d'Autorisation en Attente")
        req_df = query_df("SELECT id, user_email, statut, date_demande FROM me_autorisations WHERE statut = 'EN_ATTENTE'")
        if not req_df.empty:
            for _, r in req_df.iterrows():
                col_a, col_b, col_c = st.columns([3, 1, 1])
                col_a.write(f"👤 **{r['user_email']}** (Demande du {r['date_demande']})")
                if col_b.button("🟢 Valider", key=f"app_{r['id']}"):
                    execute_db("UPDATE me_autorisations SET statut = 'APPROUVE', date_decision = ? WHERE id = ?", (str(datetime.now()), r['id']))
                    log_acces(r['user_email'], "APPROVAL_PANEL", "SUCCÈS", "Accès approuvé depuis le panneau admin.")
                    st.success(f"Accès validé pour {r['user_email']}")
                    st.rerun()
                if col_c.button("🔴 Refuser", key=f"rej_{r['id']}"):
                    execute_db("UPDATE me_autorisations SET statut = 'REFUSE', date_decision = ? WHERE id = ?", (str(datetime.now()), r['id']))
                    log_acces(r['user_email'], "APPROVAL_PANEL", "REFUSÉ", "Accès refusé depuis le panneau admin.")
                    st.error(f"Accès refusé pour {r['user_email']}")
                    st.rerun()
        else:
            st.info("Aucune demande en attente.")

        st.divider()
        st.write("#### ⚪ Gestion de la Whitelist (Liste Blanche)")
        with st.form("f_add_whitelist"):
            w_email = st.text_input("Adresse Email à autoriser *").strip().lower()
            w_desc = st.text_input("Description / Role", value="Technicien Terrain")
            if st.form_submit_button("Ajouter à la Liste Blanche"):
                if w_email:
                    try:
                        execute_db("INSERT INTO me_whitelist_emails (email, description, date_ajout) VALUES (?, ?, ?)", (w_email, w_desc, str(datetime.now())))
                        st.success(f"{w_email} ajouté à la whitelist !")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.warning("Cet e-mail est déjà dans la liste blanche.")

        wl_df = query_df("SELECT email, description, date_ajout FROM me_whitelist_emails")
        st.dataframe(wl_df, use_container_width=True)

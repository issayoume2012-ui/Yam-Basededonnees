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
ADMIN_EMAIL = "issayoume2012@gmail.com"      # Votre e-mail admin principal
SMTP_SENDER = "issayoume2012@gmail.com"      # Votre e-mail d'envoi
SMTP_PASSWORD = "qwhvzfvheaacdtsp"           # Mot de passe d'application Gmail
APP_URL = "http://localhost:8501"            # Remplacez par votre URL de production

# ==========================================
# 0. BASE DE DONNÉES & INITIALISATION
# ==========================================
UPLOAD_DIR = "uploads"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

DB_FILE = "agri_database.db"

def get_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
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

    # Table des demandes d'autorisation d'accès (Demandes en attente)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS me_autorisations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_email TEXT,
        token TEXT UNIQUE,
        statut TEXT, -- 'EN_ATTENTE', 'APPROUVE', 'REFUSE'
        date_demande TEXT,
        date_decision TEXT
    )""")

    # Table des logs d'accès (Audit Trail / Traçabilité)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS me_logs_acces (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_email TEXT,
        action TEXT,
        date_evenement TEXT,
        statut TEXT,
        details TEXT
    )""")

    # Table Fil de Discussion Commun (Techniciens)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS me_fil_discussion (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        auteur_nom TEXT,
        auteur_email TEXT,
        message TEXT,
        type_message TEXT, -- 'INFO', 'ALERTE', 'QUESTION'
        date_envoi TEXT
    )""")

    # Table Base de Connaissances & Fiches Techniques Partagées
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
    cursor.execute("INSERT OR IGNORE INTO me_tech (gmail, password, nom, prenom, sync_gdocs) VALUES (?, ?, ?, ?, 1)",
                   (ADMIN_EMAIL.lower(), "admin123", "Admin", "System"))

    conn.commit()
    conn.close()

init_db()

def query_db(query, params=(), one=False):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(query, params)
    rv = cursor.fetchall()
    conn.close()
    return (rv[0] if rv else None) if one else rv

def query_df(query, params=()):
    conn = get_db()
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

def execute_db(query, params=()):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(query, params)
    conn.commit()
    last_id = cursor.lastrowid
    conn.close()
    return last_id

# ==========================================
# FONCTIONS DE LOGS & ENVOI D'E-MAILS D'ACCÈS
# ==========================================
def log_acces(email, action, statut, details=""):
    execute_db("""
        INSERT INTO me_logs_acces (user_email, action, date_evenement, statut, details)
        VALUES (?, ?, ?, ?, ?)
    """, (email, action, str(datetime.now()), statut, details))

def envoyer_mail_demande_autorisation(user_email, token):
    link_approve = f"{APP_URL}/?action=approve&token={token}"
    link_reject = f"{APP_URL}/?action=reject&token={token}"

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
    except Exception as e:
        # Si SMTP non configuré, le système enregistre tout de même la demande en BDD
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
    tok = params["token"]
    
    req = query_db("SELECT * FROM me_autorisations WHERE token = ?", (tok,), one=True)
    if req:
        if act == "approve":
            execute_db("UPDATE me_autorisations SET statut = 'APPROUVE', date_decision = ? WHERE token = ?", (str(datetime.now()), tok))
            log_acces(req['user_email'], "APPROVAL_EMAIL", "SUCCÈS", f"Demande approuvée par e-mail. Token: {tok}")
            st.success(f"✅ Accès ACCORDÉ pour l'utilisateur **{req['user_email']}**.")
        elif act == "reject":
            execute_db("UPDATE me_autorisations SET statut = 'REFUSE', date_decision = ? WHERE token = ?", (str(datetime.now()), tok))
            log_acces(req['user_email'], "APPROVAL_EMAIL", "REFUSÉ", f"Demande refusée par e-mail. Token: {tok}")
            st.error(f"❌ Accès REFUSÉ pour l'utilisateur **{req['user_email']}**.")
    else:
        st.warning("⚠️ Jeton de demande non valide ou expiré.")
    st.stop()

# ==========================================
# 3. AUTHENTIFICATION & PROCESSUS D'ACCÈS
# ==========================================
if "user" not in st.session_state:
    st.session_state.user = None
if "pending_token" not in st.session_state:
    st.session_state.pending_token = None

def auth_system():
    if st.session_state.user is None:
        st.title("🌾 AgriGestion Pro")
        
        # Écran d'attente lors d'une demande envoyée
        if st.session_state.pending_token:
            st.info("⏳ **Votre demande d'accès a été enregistrée et transmise à l'administrateur (issayoume2012@gmail.com).**")
            st.write("Veuillez patienter pendant la vérification. Dès que l'administrateur valide votre demande via l'e-mail ou son panneau d'administration, vous pourrez accéder à l'application.")
            
            req = query_db("SELECT * FROM me_autorisations WHERE token = ?", (st.session_state.pending_token,), one=True)
            
            if req:
                if req['statut'] == 'APPROUVE':
                    user = query_db("SELECT * FROM me_tech WHERE gmail = ?", (req['user_email'],), one=True)
                    st.session_state.user = dict(user)
                    st.session_state.pending_token = None
                    log_acces(req['user_email'], "LOGIN", "SUCCÈS", "Accès débloqué après validation.")
                    st.success("✅ Accès accordé ! Redirection...")
                    st.rerun()
                elif req['statut'] == 'REFUSE':
                    st.error("❌ Votre demande d'accès a été refusée par l'administrateur.")
                    log_acces(req['user_email'], "LOGIN", "REFUSÉ", "Accès refusé.")
                    if st.button("Nouvelle tentative"):
                        st.session_state.pending_token = None
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
                    # 1. Vérification dans la Whitelist
                    in_whitelist = query_db("SELECT * FROM me_whitelist_emails WHERE email = ?", (gmail_in,), one=True)
                    if not in_whitelist:
                        st.error("❌ Accès Refusé : Cet e-mail n'est pas pré-autorisé sur la Liste Blanche.")
                        log_acces(gmail_in, "LOGIN_ATTEMPT", "BLOQUÉ_WHITELIST", "Adresse absente de la liste blanche.")
                    else:
                        # 2. Vérification des identifiants
                        user = query_db("SELECT * FROM me_tech WHERE gmail = ? AND password = ?", (gmail_in, pwd_in), one=True)
                        if user:
                            # Si c'est l'administrateur principal, accès immédiat
                            if gmail_in == ADMIN_EMAIL.lower():
                                st.session_state.user = dict(user)
                                log_acces(gmail_in, "LOGIN_ADMIN", "SUCCÈS", "Accès administrateur direct.")
                                st.rerun()
                            else:
                                # 3. Création et transmission de la demande d'accès
                                token = secrets.token_hex(16)
                                execute_db("""
                                    INSERT INTO me_autorisations (user_email, token, statut, date_demande)
                                    VALUES (?, ?, 'EN_ATTENTE', ?)
                                """, (gmail_in, token, str(datetime.now())))
                                
                                envoyer_mail_demande_autorisation(gmail_in, token)
                                st.session_state.pending_token = token
                                log_acces(gmail_in, "DEMANDE_AUTORISATION", "EN_ATTENTE", f"Demande transmise à l'admin. Token: {token}")
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
                                execute_db("INSERT INTO me_tech (nom, prenom, gmail, password, sync_gdocs) VALUES (?, ?, ?, ?, 1)", (nom, prenom, gmail, password))
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
        st.session_state.pending_token = None
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

# Liste des onglets principaux
tabs_titles = [
    "📊 TBD", "🤝 Espace Commun Techniciens", "🌱 Parcelles & Historique", "👥 Personnel & Équipes", "⏰ Pointages",
    "📅 Travaux & Matériel", "🐓 Élevage", "🐟 Pisciculture", "🌾 Récoltes", "💰 Finances", "📄 Rapports Automatisés"
]

# Panneau Sécurité visible uniquement pour l'administrateur principal
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
    surf_tot = query_db("SELECT SUM(superficie_ha) as total FROM me_champs WHERE user_id = ?", (USER_ID,), one=True)['total'] or 0
    emp_tot = query_db("SELECT COUNT(*) as total FROM me_employes WHERE user_id = ?", (USER_ID,), one=True)['total'] or 0
    anim_tot = query_db("SELECT SUM(quantite) as total FROM me_elevage WHERE user_id = ?", (USER_ID,), one=True)['total'] or 0
    rec_tot = query_db("SELECT SUM(quantite_kg) as total FROM me_recoltes WHERE user_id = ?", (USER_ID,), one=True)['total'] or 0
    
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
    p_tab1, p_tab2, p_tab3 = st.tabs(["📍 Carte & Création", "📜 Historique", "🔄 Sélection Parcelle"])

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
                        st.success("Historique sauvegardé !")
                        st.rerun()

        hist_df = query_df("SELECT culture, date_debut, date_fin, rendement_kg, remarques FROM me_historique_champs WHERE champ_id = ? AND user_id = ?", (champ_id_actif, USER_ID))
        st.dataframe(hist_df, use_container_width=True)

    with p_tab3:
        st.write("#### 🔄 Basculer sur une autre Parcelle")
        if not champs_df.empty:
            p_target = st.selectbox("Sélectionner la parcelle active :", champs_df['nom'].tolist(), index=list(champs_df['nom']).index(parcelle_active_nom))
            if st.button("Activer cette Parcelle"):
                st.session_state.selected_parcelle_name = p_target
                st.success(f"Parcelle '{p_target}' chargée !")
                st.rerun()

# --- TAB 4 : PERSONNEL & ÉQUIPES ---
with main_tabs[3]:
    st.subheader("👥 Gestion du Personnel & Équipes")
    sub_t1, sub_t2, sub_t3 = st.tabs(["📋 Registre du Personnel", "➕ Nouvel Employé", "👨‍👩‍👧‍👦 Équipes"])

    with sub_t1:
        employes = query_df("SELECT e.*, g.nom_groupe FROM me_employes e LEFT JOIN me_equipes g ON e.groupe_id = g.id WHERE e.user_id = ?", (USER_ID,))
        if not employes.empty:
            st.dataframe(employes[["id", "nom", "role", "type_contrat", "tarif_journalier", "salaire_mensuel", "matricule_emp", "nom_groupe"]], use_container_width=True)
        else:
            st.info("Aucun employé enregistré.")

    with sub_t2:
        with st.form("f_emp", clear_on_submit=True):
            nom_e = st.text_input("Nom Complet *")
            role_e = st.text_input("Rôle / Poste", value="Ouvrier Agricole")
            contract_e = st.selectbox("Type de Contrat", ["Journalier", "Permanent / Mensuel", "Temporaire"])
            tarif_e = st.number_input("Tarif Journalier (FCFA)", value=0.0)
            sal_e = st.number_input("Salaire Mensuel (FCFA)", value=0.0)
            mat_e = st.text_input("Matricule", value=f"EMP-{secrets.token_hex(2).upper()}")
            
            equipes_list = query_df("SELECT id, nom_groupe FROM me_equipes WHERE user_id = ?", (USER_ID,))
            grp_opts = {"Aucune équipe": None}
            if not equipes_list.empty:
                for _, r in equipes_list.iterrows():
                    grp_opts[r['nom_groupe']] = r['id']
            sel_grp = st.selectbox("Équipe rattachée", list(grp_opts.keys()))

            if st.form_submit_button("Enregistrer l'Employé"):
                if nom_e:
                    execute_db("""
                        INSERT INTO me_employes (user_id, nom, role, groupe_id, type_contrat, tarif_journalier, salaire_mensuel, matricule_emp)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (USER_ID, nom_e, role_e, grp_opts[sel_grp], contract_e, tarif_e, sal_e, mat_e))
                    st.success("Employé enregistré avec succès !")
                    st.rerun()

    with sub_t3:
        st.write("#### Groupes & Équipes de Travail")
        with st.form("f_grp", clear_on_submit=True):
            nom_g = st.text_input("Nom de l'Équipe *")
            chef_g = st.text_input("Chef d'Équipe")
            if st.form_submit_button("Créer l'Équipe"):
                if nom_g:
                    execute_db("INSERT INTO me_equipes (user_id, nom_groupe, chef_groupe) VALUES (?, ?, ?)", (USER_ID, nom_g, chef_g))
                    st.success("Équipe créée !")
                    st.rerun()
        
        eq_df = query_df("SELECT * FROM me_equipes WHERE user_id = ?", (USER_ID,))
        st.dataframe(eq_df, use_container_width=True)

# --- TAB 5 : POINTAGES ---
with main_tabs[4]:
    st.subheader("⏰ Gestion des Pointages du Personnel")
    with st.form("f_pointage", clear_on_submit=True):
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            d_point = st.date_input("Date du Pointage", value=date.today())
            emp_list = query_df("SELECT nom FROM me_employes WHERE user_id = ?", (USER_ID,))['nom'].tolist()
            emp_p = st.selectbox("Employé", emp_list if emp_list else ["Aucun employé"])
            stat_p = st.selectbox("Statut de Présence", ["Présent", "Absent", "Demi-journée", "En Congé"])
        with col_p2:
            h_eff = st.number_input("Heures Effectives", value=8.0, step=0.5)
            rem_p = st.text_input("Remarques / Activité")

        if st.form_submit_button("Enregistrer le Pointage"):
            if emp_p and emp_p != "Aucun employé":
                execute_db("""
                    INSERT INTO me_pointage (user_id, date, employe_nom, champ_nom, statut_presence, heures_effectives, remarque)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (USER_ID, str(d_point), emp_p, parcelle_active_nom, stat_p, h_eff, rem_p))
                st.success("Pointage enregistré !")
                st.rerun()

    st.divider()
    st.write("#### 📜 Historique Récent des Pointages")
    p_df = query_df("SELECT date, employe_nom, champ_nom, statut_presence, heures_effectives, remarque FROM me_pointage WHERE user_id = ? ORDER BY date DESC LIMIT 30", (USER_ID,))
    st.dataframe(p_df, use_container_width=True)

# --- TAB 6 : TRAVAUX & MATÉRIEL ---
with main_tabs[5]:
    st.subheader("📅 Tâches, Travaux & Gestion du Matériel")
    t_tab1, t_tab2 = st.tabs(["📋 Suivi des Tâches", "🚜 Parc Matériel"])

    with t_tab1:
        with st.form("f_tache", clear_on_submit=True):
            col_t1, col_t2 = st.columns(2)
            with col_t1:
                type_t = st.text_input("Type de Travail *", placeholder="Ex: Labourage, Traitement Phytosanitaire")
                desc_t = st.text_area("Description des Travaux")
                d_tache = st.date_input("Date Prévue", value=date.today())
            with col_t2:
                prio_t = st.selectbox("Priorité", ["Normale", "Haute", "Urgente"])
                stat_t = st.selectbox("Statut Tâche", ["En Attente", "En Cours", "Terminé"])
                h_tache = st.number_input("Heures estimées / réalisées", value=4.0)

            if st.form_submit_button("Créer la Tâche"):
                if type_t:
                    execute_db("""
                        INSERT INTO me_taches (user_id, champ_id, type_travail, description, date_tache, heures_travaillees, priorite, statut)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (USER_ID, champ_id_actif, type_t, desc_t, str(d_tache), h_tache, prio_t, stat_t))
                    st.success("Tâche créée !")
                    st.rerun()

        taches_df = query_df("SELECT type_travail, description, date_tache, heures_travaillees, priorite, statut FROM me_taches WHERE user_id = ? ORDER BY id DESC", (USER_ID,))
        st.dataframe(taches_df, use_container_width=True)

    with t_tab2:
        with st.form("f_mat", clear_on_submit=True):
            nom_m = st.text_input("Nom du Matériel *", placeholder="Ex: Tracteur Massey Ferguson")
            cat_m = st.selectbox("Catégorie", ["Tracteur / Engin", "Outillage à Main", "Système Irrigation", "Pulvérisateur", "Autre"])
            etat_m = st.selectbox("État", ["Neuf", "Bon état", "En Panne / Réparation", "Hors d'usage"])
            d_acq = st.date_input("Date d'acquisition", value=date.today())
            if st.form_submit_button("Ajouter le Matériel"):
                if nom_m:
                    execute_db("INSERT INTO me_materiel (user_id, nom_materiel, categorie, etat, date_acquisition) VALUES (?, ?, ?, ?, ?)",
                               (USER_ID, nom_m, cat_m, etat_m, str(d_acq)))
                    st.success("Matériel enregistré !")
                    st.rerun()

        mat_df = query_df("SELECT nom_materiel, categorie, etat, date_acquisition FROM me_materiel WHERE user_id = ?", (USER_ID,))
        st.dataframe(mat_df, use_container_width=True)

# --- TAB 7 : ÉLEVAGE ---
with main_tabs[6]:
    st.subheader("🐓 Gestion de l'Élevage")
    with st.form("f_elevage", clear_on_submit=True):
        col_e1, col_e2 = st.columns(2)
        with col_e1:
            type_anim = st.selectbox("Type d'Animaux", ["Bovins (Vaches/Bœufs)", "Oovins (Moutons)", "Caprins (Chèvres)", "Volailles (Poulets)", "Porcins"])
            race_anim = st.text_input("Race / Variété")
            qte_anim = st.number_input("Nombre de Têtes", min_value=1, value=10)
        with col_e2:
            d_arriv = st.date_input("Date d'arrivée / Naissance", value=date.today())
            stat_san = st.selectbox("Statut Sanitaire", ["Sain / Vacciné", "Sous Traitement", "Quarantaine"])

        if st.form_submit_button("Enregistrer le Cheptel"):
            execute_db("INSERT INTO me_elevage (user_id, type_animaux, race, quantite, date_arrivee, statut_sanitaire) VALUES (?, ?, ?, ?, ?, ?)",
                       (USER_ID, type_anim, race_anim, qte_anim, str(d_arriv), stat_san))
            st.success("Bétail enregistré !")
            st.rerun()

    elev_df = query_df("SELECT type_animaux, race, quantite, date_arrivee, statut_sanitaire FROM me_elevage WHERE user_id = ?", (USER_ID,))
    st.dataframe(elev_df, use_container_width=True)

# --- TAB 8 : PISCICULTURE ---
with main_tabs[7]:
    st.subheader("🐟 Suivi Pisciculture & Aquaculture")
    with st.form("f_aqua", clear_on_submit=True):
        col_a1, col_a2 = st.columns(2)
        with col_a1:
            nom_bassin = st.text_input("Identifiant du Bassin *", value="Bassin #1")
            esp_poisson = st.selectbox("Espèce Élevée", ["Tilapia", "Poisson-Chat (Clarias)", "Carpe"])
            nb_alv = st.number_input("Nombre d'Alevins Introduits", value=500)
        with col_a2:
            alim_kg = st.number_input("Nourriture distribuée (Kg/jour)", value=5.0)
            ph_w = st.number_input("Mesure du pH de l'Eau", value=7.2, min_value=0.0, max_value=14.0)

        if st.form_submit_button("Enregistrer les données Pisciculture"):
            execute_db("INSERT INTO me_aquaculture (user_id, nom_bassin, espece_poisson, nombre_alvins, aliment_kg, ph_eau) VALUES (?, ?, ?, ?, ?, ?)",
                       (USER_ID, nom_bassin, esp_poisson, nb_alv, alim_kg, ph_w))
            st.success("Données de bassin sauvegardées !")
            st.rerun()

    aqua_df = query_df("SELECT nom_bassin, espece_poisson, nombre_alvins, aliment_kg, ph_eau FROM me_aquaculture WHERE user_id = ?", (USER_ID,))
    st.dataframe(aqua_df, use_container_width=True)

# --- TAB 9 : RÉCOLTES ---
with main_tabs[8]:
    st.subheader("🌾 Suivi des Récoltes & Production")
    with st.form("f_recolte", clear_on_submit=True):
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            cult_rec = st.text_input("Culture Récoltée *", value="Tomates")
            qte_rec = st.number_input("Quantité Récoltée (Kg)", value=100.0)
        with col_r2:
            d_rec = st.date_input("Date Récolte", value=date.today())
            pu_rec = st.number_input("Prix Vente Estimé / Kg (FCFA)", value=500.0)

        if st.form_submit_button("Enregistrer la Récolte"):
            if cult_rec:
                execute_db("""
                    INSERT INTO me_recoltes (user_id, champ_id, culture, date_recolte, quantite_kg, prix_unitaire)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (USER_ID, champ_id_actif, cult_rec, str(d_rec), qte_rec, pu_rec))
                st.success("Récolte enregistrée !")
                st.rerun()

    recoltes_df = query_df("SELECT culture, date_recolte, quantite_kg, prix_unitaire, (quantite_kg * prix_unitaire) as valeur_totale FROM me_recoltes WHERE user_id = ? ORDER BY date_recolte DESC", (USER_ID,))
    st.dataframe(recoltes_df, use_container_width=True)

# --- TAB 10 : FINANCES ---
with main_tabs[9]:
    st.subheader("💰 Gestion Financière & Dépenses")
    fin_t1, fin_t2 = st.tabs(["💸 Enregistrer une Dépense", "📦 Gestion des Intrants & Stock"])

    with fin_t1:
        with st.form("f_depense", clear_on_submit=True):
            type_d = st.selectbox("Type de Dépense", ["Achat Engrais/Semences", "Carburant", "Entretien Matériel", "Main d'œuvre / Salaires", "Autre"])
            montant_d = st.number_input("Montant (FCFA) *", min_value=100.0, value=5000.0)
            d_depense = st.date_input("Date Dépense", value=date.today())

            if st.form_submit_button("Enregistrer la Dépense"):
                execute_db("INSERT INTO me_depenses (user_id, champ_id, type, montant, date) VALUES (?, ?, ?, ?, ?)",
                           (USER_ID, champ_id_actif, type_d, montant_d, str(d_depense)))
                st.success("Dépense enregistrée !")
                st.rerun()

        dep_df = query_df("SELECT type, montant, date FROM me_depenses WHERE user_id = ? ORDER BY date DESC", (USER_ID,))
        st.dataframe(dep_df, use_container_width=True)

    with fin_t2:
        with st.form("f_intrant", clear_on_submit=True):
            nom_i = st.text_input("Nom de l'Intrant / Produit *", placeholder="Ex: Engrais NPK 15-15-15")
            cat_i = st.selectbox("Catégorie", ["Engrais / Fertilisant", "Semences", "Pesticide / Fongicide", "Aliment Bétail"])
            stock_i = st.number_input("Quantité en Stock", value=10.0)
            unite_i = st.selectbox("Unité", ["Kg", "Litres", "Sacs", "Tonnes"])
            seuil_i = st.number_input("Seuil d'Alerte Réapprovisionnement", value=2.0)

            if st.form_submit_button("Ajouter à l'Inventaire"):
                if nom_i:
                    execute_db("INSERT INTO me_intrants (user_id, nom, categorie, stock_actuel, unite, seuil_alerte) VALUES (?, ?, ?, ?, ?, ?)",
                               (USER_ID, nom_i, cat_i, stock_i, unite_i, seuil_i))
                    st.success("Stock mis à jour !")
                    st.rerun()

        int_df = query_df("SELECT nom, categorie, stock_actuel, unite, seuil_alerte FROM me_intrants WHERE user_id = ?", (USER_ID,))
        st.dataframe(int_df, use_container_width=True)

# --- TAB 11 : RAPPORTS AUTOMATISÉS ---
with main_tabs[10]:
    st.subheader("📄 Génération Automatisée de Rapports d'Exploitation PDF")
    st.write("Téléchargez des synthèses complètes prêtes à l'impression pour vos audits, partenaires ou gestion interne.")

    col_rep1, col_rep2 = st.columns(2)
    with col_rep1:
        st.markdown("#### 📆 Rapport Mensuel")
        m_rep = st.selectbox("Mois", list(range(1, 13)), index=datetime.now().month - 1)
        y_rep = st.number_input("Année", value=datetime.now().year, min_value=2020, max_value=2030)
        
        if st.button("🔄 Générer Rapport Mensuel (PDF)"):
            pdf_data = generate_full_pdf_report(USER_DATA, f"Rapport Mensuel {m_rep:02d}/{y_rep}", filter_month=m_rep, filter_year=y_rep)
            st.download_button(
                label="📥 Télécharger le PDF Mensuel",
                data=pdf_data,
                file_name=f"Rapport_Mensuel_{y_rep}_{m_rep:02d}.pdf",
                mime="application/pdf"
            )

    with col_rep2:
        st.markdown("#### 📋 Rapport Global Cumulative")
        st.write("Inclut l'ensemble de vos données historiques (Parcelles, Personnels, Tâches, Récoltes et Finances).")
        
        if st.button("🔄 Générer Rapport Global (PDF)"):
            pdf_data_global = generate_full_pdf_report(USER_DATA, "Rapport Global d'Exploitation")
            st.download_button(
                label="📥 Télécharger le PDF Global",
                data=pdf_data_global,
                file_name=f"Rapport_Global_Exploitation_{date.today()}.pdf",
                mime="application/pdf"
            )

# --- TAB 12 : SÉCURITÉ & DEMANDES D'ACCÈS (ADMIN UNIQUEMENT) ---
if USER_DATA['gmail'].lower() == ADMIN_EMAIL.lower():
    with main_tabs[11]:
        st.subheader("🛡️ Panneau d'Administration de la Sécurité & Autorisations")
        
        adm_sec1, adm_sec2, adm_sec3 = st.tabs([
            "📥 Demandes d'Autorisation", 
            "⚪ Liste Blanche (Whitelist)", 
            "📋 Log des Accès (Audit Trail)"
        ])

        # SECTION 1 : VALIDATION DES DEMANDES
        with adm_sec1:
            st.write("#### Validation des Demandes d'Accès")
            filtre_statut = st.radio("Filtrer les demandes :", ["EN_ATTENTE", "TOUS", "APPROUVE", "REFUSE"], horizontal=True)
            
            if filtre_statut == "TOUS":
                demandes_df = query_df("SELECT * FROM me_autorisations ORDER BY id DESC")
            else:
                demandes_df = query_df("SELECT * FROM me_autorisations WHERE statut = ? ORDER BY id DESC", (filtre_statut,))

            if not demandes_df.empty:
                for _, req in demandes_df.iterrows():
                    col_d1, col_d2, col_d3 = st.columns([3, 1, 1])
                    with col_d1:
                        st.write(f"👤 **{req['user_email']}** | Statut : `{req['statut']}` | Date : {req['date_demande']}")
                    
                    if req['statut'] == 'EN_ATTENTE':
                        with col_d2:
                            if st.button("🟢 Approuver", key=f"app_{req['id']}"):
                                execute_db("UPDATE me_autorisations SET statut = 'APPROUVE', date_decision = ? WHERE id = ?", 
                                           (str(datetime.now()), req['id']))
                                log_acces(req['user_email'], "APPROVAL_ADMIN", "SUCCÈS", "Accès validé depuis le panneau admin.")
                                st.success("Accès validé !")
                                st.rerun()
                        with col_d3:
                            if st.button("🔴 Refuser", key=f"rej_{req['id']}"):
                                execute_db("UPDATE me_autorisations SET statut = 'REFUSE', date_decision = ? WHERE id = ?", 
                                           (str(datetime.now()), req['id']))
                                log_acces(req['user_email'], "APPROVAL_ADMIN", "REFUSÉ", "Accès refusé depuis le panneau admin.")
                                st.error("Accès refusé !")
                                st.rerun()
                    else:
                        st.caption(f"Décision enregistrée le : {req['date_decision']}")
                    st.divider()
            else:
                st.info("Aucune demande d'accès répertoriée.")

        # SECTION 2 : WHITELIST
        with adm_sec2:
            st.write("#### Gestion de la Liste Blanche (Whitelist)")
            with st.form("f_add_whitelist", clear_on_submit=True):
                new_email = st.text_input("Adresse Email à pré-autoriser *").strip().lower()
                desc_email = st.text_input("Description / Rôle", placeholder="Ex: Technicien Zone Nord")
                if st.form_submit_button("Ajouter à la Liste Blanche"):
                    if new_email:
                        try:
                            execute_db("INSERT INTO me_whitelist_emails (email, description, date_ajout) VALUES (?, ?, ?)",
                                       (new_email, desc_email, str(datetime.now())))
                            log_acces(new_email, "WHITELIST_ADD", "SUCCÈS", f"Ajouté par {USER_DATA['gmail']}")
                            st.success(f"Adresse `{new_email}` ajoutée avec succès à la Whitelist !")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.warning("Cet e-mail figure déjà sur la Liste Blanche.")
                    else:
                        st.warning("Veuillez saisir un e-mail valide.")

            st.divider()
            st.write("##### Adresses Pré-autorisées actuelles")
            whitelist_df = query_df("SELECT * FROM me_whitelist_emails ORDER BY id DESC")
            st.dataframe(whitelist_df, use_container_width=True)

        # SECTION 3 : AUDIT TRAIL / LOGS
        with adm_sec3:
            st.write("#### Journal des Événements & Audit Trail")
            logs_df = query_df("SELECT * FROM me_logs_acces ORDER BY id DESC")
            st.dataframe(logs_df, use_container_width=True)

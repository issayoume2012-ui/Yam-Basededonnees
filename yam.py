import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import datetime, date
import io

# Cartographie dynamique interactive
import folium
from streamlit_folium import st_folium

# Exports PDF
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# ==========================================
# 0. INITIALISATION DOSSIER & BASE DE DONNÉES (SQLITE)
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
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS me_tech (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT, prenom TEXT, gmail TEXT, phone TEXT, matricule TEXT, password TEXT, sync_gdocs INTEGER
    )""")
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS me_champs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT, superficie_ha REAL, latitude REAL, longitude REAL, culture_actuelle TEXT, statut TEXT, icone_lieu TEXT
    )""")
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS me_equipes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom_groupe TEXT, chef_groupe TEXT, membres TEXT
    )""")
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS me_employes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT, role TEXT, groupe_id INTEGER, tarif_journalier REAL
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS me_pointage (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT, employe_nom TEXT, groupe_nom TEXT, champ_nom TEXT, statut_presence TEXT,
        heure_arrivee TEXT, heure_debut_pause TEXT, heure_fin_pause TEXT, heure_depart TEXT, 
        heures_effectives REAL, remarque TEXT
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS me_taches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        champ_id INTEGER, groupe_id INTEGER, type_travail TEXT, date_tache TEXT, heures_travaillees REAL, statut TEXT
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS me_recoltes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        champ_id INTEGER, culture TEXT, date_recolte TEXT, quantite_kg REAL, prix_unitaire REAL
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS me_depenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        champ_id INTEGER, type TEXT, montant REAL, date TEXT, facture_chemin TEXT
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS me_intrants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT, categorie TEXT, stock_actuel REAL, unite TEXT, seuil_alerte REAL, facture_chemin TEXT
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS me_pluviometrie (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        champ_id INTEGER, date TEXT, pluie_mm REAL
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS me_incidents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        champ_id INTEGER, date TEXT, description TEXT, gravite TEXT, action TEXT
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS me_materiel (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom_equipement TEXT, categorie TEXT, statut_marche TEXT, date_derniere_revision TEXT, prochaine_revision TEXT
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS me_tracabilite (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lot_code TEXT, champ_nom TEXT, culture TEXT, date_recolte TEXT, norme_certification TEXT, acheteur TEXT
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS me_irrigation (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        champ_nom TEXT, date TEXT, volume_eau_m3 REAL, methode TEXT, duree_heures REAL
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS me_alertes_meteo (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT, type_risque TEXT, niveau_alerte TEXT, recommandation_ts TEXT
    )""")

    conn.commit()
    conn.close()

init_db()

# Fonctions utilitaires SQL
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
# 1. CONFIGURATION DE LA PAGE STREAMLIT
# ==========================================
st.set_page_config(
    page_title="AgriGestion Pro - Technicien Supérieur",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
        .stApp { background-color: #f8f9fa; }
        .tech-badge { background-color: #10b981; color: white; padding: 4px 12px; border-radius: 12px; font-weight: bold; }
        .gdoc-badge { background-color: #4285F4; color: white; padding: 4px 10px; border-radius: 8px; font-size: 12px; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. AUTHENTIFICATION DYNAMIQUE (PERSISTANTE)
# ==========================================
def auth_system():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    tech_records = query_db("SELECT * FROM me_tech LIMIT 1")
    
    if not tech_records:
        st.title("👨‍🌾 Enregistrement Initial - Technicien Supérieur")
        st.info("Bienvenue ! Configurez votre compte professionnel (Stocké en Base de Données).")

        with st.form("form_registration"):
            col1, col2 = st.columns(2)
            with col1:
                nom = st.text_input("Nom de famille *")
                prenom = st.text_input("Prénom *")
                gmail = st.text_input("Adresse Gmail / Google Workspace *", placeholder="votre.email@gmail.com")
                phone = st.text_input("Numéro de Téléphone")
            with col2:
                matricule = st.text_input("Matricule / Code TS", value="TS-001")
                password_custom = st.text_input("Définissez votre Mot de Passe *", type="password")
                password_confirm = st.text_input("Confirmez votre Mot de Passe *", type="password")
                sync_gdocs = st.checkbox("Activer la synchronisation Google Drive / Docs", value=True)

            submit_reg = st.form_submit_button("Créer mon compte Technicien", use_container_width=True)

            if submit_reg:
                if not nom or not prenom or not gmail or not password_custom:
                    st.error("❌ Veuillez remplir tous les champs obligatoires (*).")
                elif password_custom != password_confirm:
                    st.error("❌ Les mots de passe ne correspondent pas.")
                else:
                    execute_db("""
                        INSERT INTO me_tech (nom, prenom, gmail, phone, matricule, password, sync_gdocs)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (nom, prenom, gmail, phone, matricule, password_custom, 1 if sync_gdocs else 0))
                    st.session_state.authenticated = True
                    st.success("✅ Compte créé avec succès !")
                    st.rerun()
        return False

    elif not st.session_state.authenticated:
        tech_data = tech_records[0]
        st.title("🔒 Connexion - Espace Technicien Supérieur")
        st.caption(f"Compte associé : **{tech_data['prenom']} {tech_data['nom']}** ({tech_data['gmail']})")

        pwd_input = st.text_input("Saisissez votre mot de passe :", type="password")
        
        col_b1, col_b2 = st.columns([1, 2])
        with col_b1:
            if st.button("Se Connecter", use_container_width=True):
                if pwd_input == tech_data['password']:
                    st.session_state.authenticated = True
                    st.success("✅ Connexion réussie !")
                    st.rerun()
                else:
                    st.error("❌ Mot de passe incorrect.")
        with col_b2:
            if st.button("Réinitialiser le profil / Réinitialiser la DB", use_container_width=True):
                execute_db("DELETE FROM me_tech")
                st.session_state.authenticated = False
                st.rerun()
        return False

    return True

if not auth_system():
    st.stop()

tech_row = query_db("SELECT * FROM me_tech LIMIT 1", one=True)

# ==========================================
# 3. EXPORTATIONS PDF & EXCEL
# ==========================================
def export_global_to_excel():
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        query_df("SELECT * FROM me_champs").to_excel(writer, index=False, sheet_name='Parcelles')
        query_df("SELECT * FROM me_equipes").to_excel(writer, index=False, sheet_name='Groupes')
        query_df("SELECT * FROM me_employes").to_excel(writer, index=False, sheet_name='Membres')
        query_df("SELECT * FROM me_pointage").to_excel(writer, index=False, sheet_name='Pointages')
        query_df("SELECT * FROM me_taches").to_excel(writer, index=False, sheet_name='Planning')
        query_df("SELECT * FROM me_recoltes").to_excel(writer, index=False, sheet_name='Recoltes')
        query_df("SELECT * FROM me_depenses").to_excel(writer, index=False, sheet_name='Depenses')
        query_df("SELECT * FROM me_intrants").to_excel(writer, index=False, sheet_name='Intrants')
        query_df("SELECT * FROM me_materiel").to_excel(writer, index=False, sheet_name='Materiel')
        query_df("SELECT * FROM me_tracabilite").to_excel(writer, index=False, sheet_name='Tracabilite')
        query_df("SELECT * FROM me_irrigation").to_excel(writer, index=False, sheet_name='Irrigation')
        query_df("SELECT * FROM me_alertes_meteo").to_excel(writer, index=False, sheet_name='Alertes_Meteo')
    return output.getvalue()

def export_global_pdf(date_rapport):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=25, leftMargin=25, topMargin=25, bottomMargin=25)
    elements = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=18, alignment=1, textColor=colors.HexColor('#1e3d59'))
    subtitle_style = ParagraphStyle('SubTitleStyle', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=12, textColor=colors.HexColor('#10b981'), spaceBefore=10, spaceAfter=5)
    normal_style = styles['Normal']
    
    elements.append(Paragraph("RAPPORT GÉNÉRAL D'EXPLOITATION AGRICOLE", title_style))
    elements.append(Spacer(1, 10))
    
    date_str = date_rapport.strftime('%d/%m/%Y')
    header_info = f"<b>JOURNÉE DU : {date_str}</b><br/>"
    header_info += f"<b>Technicien Supérieur Responsable :</b> {tech_row['prenom']} {tech_row['nom']} (Matricule: {tech_row['matricule']})<br/>"
    header_info += f"<b>Contact :</b> {tech_row['gmail']} | <b>Tél :</b> {tech_row['phone']}<br/>"
    header_info += f"<b>Date d'édition du document :</b> {datetime.now().strftime('%d/%m/%Y à %H:%M')}"
    
    elements.append(Paragraph(header_info, normal_style))
    elements.append(Spacer(1, 15))

    tables_dict = {
        "1. Pointages du Jour": query_df("SELECT * FROM me_pointage WHERE date = ?", (str(date_rapport),)),
        "2. Parcelles": query_df("SELECT * FROM me_champs"),
        "3. Récoltes": query_df("SELECT * FROM me_recoltes"),
        "4. Dépenses": query_df("SELECT * FROM me_depenses"),
        "5. Intrants en Stock": query_df("SELECT * FROM me_intrants")
    }

    for section_title, df_sec in tables_dict.items():
        elements.append(Paragraph(section_title, subtitle_style))
        if not df_sec.empty:
            data = [df_sec.columns.tolist()] + df_sec.astype(str).values.tolist()
            t = Table(data)
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#10b981')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ]))
            elements.append(t)
        else:
            elements.append(Paragraph("<i>Aucune donnée enregistrée pour cette section.</i>", normal_style))
        elements.append(Spacer(1, 10))

    elements.append(Spacer(1, 20))
    elements.append(Paragraph("<b><u>VALIDATION ET SIGNATURES OFFICIELLES</u></b>", subtitle_style))
    elements.append(Spacer(1, 10))

    signature_data = [
        ["Signature du Technicien Supérieur", "Signature du Chef d'Exploitation / Direction"],
        [f"\n\n\nNom: {tech_row['prenom']} {tech_row['nom']}\nDate: {date_str}", "\n\n\nNom: _____________________\nDate: ____/____/________"]
    ]
    
    sig_table = Table(signature_data, colWidths=[260, 260])
    sig_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#1e3d59')),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0f4f8')),
    ]))
    elements.append(sig_table)

    doc.build(elements)
    return buffer.getvalue()

# ==========================================
# 4. BARRE LATÉRALE & NAVIGATION
# ==========================================
with st.sidebar:
    st.markdown("### 👨‍🌾 Technicien Supérieur")
    st.markdown(f"**{tech_row['prenom']} {tech_row['nom']}**")
    st.caption(f"📧 {tech_row['gmail']}")
    st.caption(f"🆔 {tech_row['matricule']}")
    
    if tech_row['sync_gdocs']:
        st.markdown("<span class='gdoc-badge'>☁️ Drive Sync Actif</span>", unsafe_allow_html=True)
    
    st.divider()
    
    menu = st.radio("Navigation", [
        "📊 Tableau de Bord",
        "🌱 Cartographie & Parcelles",
        "👥 Groupes & Membres",
        "⏰ Pointage des Horaires",
        "📅 Planning & Travaux",
        "🌾 Récoltes & Rendements",
        "💰 Finances & Marges",
        "📦 Stocks d'Intrants",
        "🌧️ Pluviométrie",
        "⚠️ Incidents",
        "🚜 Maintenance Matériel",
        "🏷️ Traçabilité & Lots",
        "💧 Irrigation & Eau",
        "🌤️ Risques & Météo",
        "📈 Rentabilité & ROI",
        "📑 EXPORT COMPLET"
    ])
    
    st.divider()
    
    champs_df = query_df("SELECT * FROM me_champs")
    if not champs_df.empty:
        liste_champs = {row['nom']: (row['id'], row['latitude'], row['longitude']) for _, row in champs_df.iterrows()}
        
        # Gestion de l'état de la parcelle active via session_state
        if "selected_parcelle_name" not in st.session_state or st.session_state.selected_parcelle_name not in liste_champs:
            st.session_state.selected_parcelle_name = list(liste_champs.keys())[0]

        champ_selectionne = st.selectbox(
            "📍 Parcelle Active :", 
            list(liste_champs.keys()),
            index=list(liste_champs.keys()).index(st.session_state.selected_parcelle_name),
            key="parcelle_selector"
        )
        st.session_state.selected_parcelle_name = champ_selectionne
        champ_id_actif, champ_lat_actif, champ_lon_actif = liste_champs[champ_selectionne]
    else:
        champ_id_actif, champ_lat_actif, champ_lon_actif = None, 16.0300, -16.4800
        champ_selectionne = "Aucune parcelle"

    if st.button("🚪 Déconnexion"):
        st.session_state.authenticated = False
        st.rerun()

# ==========================================
# 5. MODULES APPLICATIFS
# ==========================================

# --- A. TABLEAU DE BORD ---
if menu == "📊 Tableau de Bord":
    st.title("📊 Tableau de Bord d'Exploitation")
    
    m1, m2, m3, m4 = st.columns(4)
    tot_surf = query_db("SELECT SUM(superficie_ha) as total FROM me_champs", one=True)['total'] or 0
    tot_ouv = query_db("SELECT COUNT(*) as total FROM me_employes", one=True)['total'] or 0
    tot_eq = query_db("SELECT COUNT(*) as total FROM me_equipes", one=True)['total'] or 0
    tot_rec = query_db("SELECT SUM(quantite_kg) as total FROM me_recoltes", one=True)['total'] or 0
    
    m1.metric("Superficie Totale", f"{tot_surf:.2f} Ha")
    m2.metric("Groupes", f"{tot_eq}")
    m3.metric("Effectif Total", f"{tot_ouv}")
    m4.metric("Récoltes Total", f"{tot_rec/1000:.2f} Tonnes")
    
    st.divider()
    
    champs_list = query_df("SELECT * FROM me_champs")
    if champs_list.empty:
        st.info("👋 Votre base de données est vide. Rendez-vous dans le menu **'🌱 Cartographie & Parcelles'** pour enregistrer vos premiers lieux.")
    else:
        st.subheader("📍 Aperçu des Parcelles")
        st.dataframe(champs_list[["nom", "superficie_ha", "culture_actuelle", "statut"]], use_container_width=True)

# --- B. CARTOGRAPHIE DYNAMIQUE ET HISTORIQUE (AVEC RÉSÉLECTION ET SAUVEGARDE) ---
elif menu == "🌱 Cartographie & Parcelles":
    st.title("🌱 Cartographie Dynamique & Historique des Parcelles")
    
    tab_map, tab_hist = st.tabs(["🗺️ Cartographie & Ajout", "📜 Historique & Sélection des Parcelles"])

    ICON_MAP = {
        "Feuille / Plant": ("leaf", "green"),
        "Eau / Irrigation": ("tint", "blue"),
        "Maison / Dépôt": ("home", "orange"),
        "Alerte / Repère": ("exclamation-sign", "red"),
        "Étoile": ("star", "purple")
    }

    with tab_map:
        col_map, col_form = st.columns([2, 1])
        
        center_lat = champ_lat_actif if champ_id_actif else 16.0300
        center_lon = champ_lon_actif if champ_id_actif else -16.4800

        with col_map:
            st.subheader("🗺️ Carte Interactive")
            
            m = folium.Map(location=[center_lat, center_lon], zoom_start=14, tiles="OpenStreetMap")
            
            champs_all = query_df("SELECT * FROM me_champs")
            for _, r in champs_all.iterrows():
                popup_content = f"<b>{r['nom']}</b><br>Culture: {r['culture_actuelle']}<br>Surface: {r['superficie_ha']} Ha"
                
                icon_key = r['icone_lieu'] if r['icone_lieu'] in ICON_MAP else "Feuille / Plant"
                icon_name, icon_color = ICON_MAP[icon_key]
                
                folium.Marker(
                    location=[r['latitude'], r['longitude']],
                    popup=popup_content,
                    tooltip=f"📍 {r['nom']} ({r['culture_actuelle']})",
                    icon=folium.Icon(color=icon_color, icon=icon_name)
                ).add_to(m)
                
            map_data = st_folium(m, width="100%", height=480, key="folium_map", returned_objects=["last_clicked"])
            
            if map_data and map_data.get("last_clicked"):
                click_lat = round(map_data["last_clicked"]["lat"], 6)
                click_lon = round(map_data["last_clicked"]["lng"], 6)
            else:
                click_lat, click_lon = center_lat, center_lon

        with col_form:
            st.subheader("➕ Enregistrer un Lieu")
            st.info(f"📍 **Position capturée :**\n- Lat : `{click_lat}`\n- Lon : `{click_lon}`")

            with st.form("form_champ", clear_on_submit=True):
                nom_p = st.text_input("Nom de la parcelle / Lieu *")
                surf_p = st.number_input("Superficie (Ha)", min_value=0.1, value=1.0, step=0.1)
                
                lat_p = st.number_input("Latitude GPS", value=float(click_lat), format="%.6f")
                lon_p = st.number_input("Longitude GPS", value=float(click_lon), format="%.6f")
                
                cult_p = st.text_input("Culture principale (ex: Riz, Maïs)")
                stat_p = st.selectbox("Statut de la parcelle", ["En préparation", "Semé", "En croissance", "Prêt à récolter"])
                logo_lieu = st.selectbox("Icône", list(ICON_MAP.keys()))

                submit_p = st.form_submit_button("💾 Enregistrer la parcelle", use_container_width=True)
                
                if submit_p:
                    if not nom_p:
                        st.error("❌ Le nom est obligatoire.")
                    else:
                        execute_db("""
                            INSERT INTO me_champs (nom, superficie_ha, latitude, longitude, culture_actuelle, statut, icone_lieu)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (nom_p, surf_p, round(lat_p, 6), round(lon_p, 6), cult_p, stat_p, logo_lieu))
                        st.session_state.selected_parcelle_name = nom_p
                        st.success(f"✅ Parcelle '{nom_p}' enregistrée !")
                        st.rerun()

    with tab_hist:
        st.subheader("📜 Historique Complet des Parcelles Enregistrées")
        champs_history = query_df("SELECT * FROM me_champs")
        
        if champs_history.empty:
            st.info("Aucune parcelle n'est encore enregistrée.")
        else:
            for idx, r in champs_history.iterrows():
                with st.expander(f"📍 {r['nom']} - Culture: {r['culture_actuelle']} ({r['superficie_ha']} Ha)", expanded=(r['id'] == champ_id_actif)):
                    c_h1, c_h2, c_h3 = st.columns([2, 2, 1])
                    with c_h1:
                        st.write(f"**Statut :** {r['statut']}")
                        st.write(f"**Coordonnées GPS :** Lat {r['latitude']}, Lon {r['longitude']}")
                    with c_h2:
                        nb_recoltes = query_db("SELECT COUNT(*) as cnt FROM me_recoltes WHERE champ_id = ?", (r['id'],), one=True)['cnt'] or 0
                        nb_taches = query_db("SELECT COUNT(*) as cnt FROM me_taches WHERE champ_id = ?", (r['id'],), one=True)['cnt'] or 0
                        st.write(f"**Tâches associées :** {nb_taches}")
                        st.write(f"**Récoltes enregistrées :** {nb_recoltes}")
                    with c_h3:
                        if st.button(f"📌 Sélectionner comme parcelle active", key=f"btn_select_{r['id']}"):
                            st.session_state.selected_parcelle_name = r['nom']
                            st.success(f"Parcelle active changée pour : {r['nom']}")
                            st.rerun()

# --- C. GROUPES & MEMBRES ---
elif menu == "👥 Groupes & Membres":
    st.title("👥 Gestion des Groupes & Membres")
    
    t1, t2 = st.tabs(["👥 Structure des Groupes", "👷 Répertoire des Membres"])
    
    with t1:
        st.subheader("Groupes Existants")
        st.dataframe(query_df("SELECT * FROM me_equipes"), use_container_width=True)
        
        with st.form("form_groupe", clear_on_submit=True):
            nom_g = st.text_input("Nom du Groupe")
            chef_g = st.text_input("Chef de Groupe *")
            membres_init = st.text_area("Membres (séparés par des virgules)", placeholder="Mamadou, Moussa, Fatou")
            
            if st.form_submit_button("Créer le Groupe"):
                if nom_g and chef_g:
                    grp_id = execute_db("INSERT INTO me_equipes (nom_groupe, chef_groupe, membres) VALUES (?, ?, ?)", (nom_g, chef_g, membres_init))
                    execute_db("INSERT INTO me_employes (nom, role, groupe_id, tarif_journalier) VALUES (?, ?, ?, ?)", (chef_g, "Chef de Groupe", grp_id, 5000))
                    
                    if membres_init:
                        m_list = [m.strip() for m in membres_init.split(",") if m.strip()]
                        for item in m_list:
                            execute_db("INSERT INTO me_employes (nom, role, groupe_id, tarif_journalier) VALUES (?, ?, ?, ?)", (item, "Membre Ouvrier", grp_id, 3000))
                    st.success("✅ Groupe créé !")
                    st.rerun()

    with t2:
        st.subheader("Liste de tous les ouvriers / membres")
        st.dataframe(query_df("SELECT * FROM me_employes"), use_container_width=True)

# --- D. POINTAGE DES HORAIRES ---
elif menu == "⏰ Pointage des Horaires":
    st.title("⏰ Registre de Pointage des Horaires")

    tab_masser, tab_hist = st.tabs(["⚡ Pointage Massif", "📋 Historique"])

    with tab_masser:
        st.subheader("⚡ Saisie Globale de la Journée")
        emp_df = query_df("SELECT * FROM me_employes")
        
        if emp_df.empty:
            st.warning("⚠️ Aucun employé enregistré dans la base.")
        else:
            col_p1, col_p2 = st.columns(2)
            with col_p1:
                date_p = st.date_input("Date", value=date.today())
                parc_p = st.selectbox("Parcelle", query_df("SELECT nom FROM me_champs")['nom'].tolist() if not champs_df.empty else ["Général"])
            
            df_grid = pd.DataFrame({
                "Employé": emp_df['nom'],
                "Présent": True,
                "Arrivée": "08:00",
                "Départ": "17:00",
                "Remarque": ""
            })

            grid_edited = st.data_editor(df_grid, use_container_width=True, key="editor_pointage")

            if st.button("💾 Valider et Enregistrer Tous les Pointages", type="primary", use_container_width=True):
                for _, row in grid_edited.iterrows():
                    is_p = row["Présent"]
                    stat = "Présent" if is_p else "Absent"
                    heures = 8.0 if is_p else 0.0
                    
                    emp_info = query_db("SELECT groupe_id FROM me_employes WHERE nom = ?", (row["Employé"],), one=True)
                    grp_nom = "N/A"
                    if emp_info and emp_info['groupe_id']:
                        g_rec = query_db("SELECT nom_groupe FROM me_equipes WHERE id = ?", (emp_info['groupe_id'],), one=True)
                        if g_rec: grp_nom = g_rec['nom_groupe']

                    execute_db("""
                        INSERT INTO me_pointage (date, employe_nom, groupe_nom, champ_nom, statut_presence, heure_arrivee, heure_depart, heures_effectives, remarque)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (str(date_p), row["Employé"], grp_nom, parc_p, stat, row["Arrivée"] if is_p else "-", row["Départ"] if is_p else "-", heures, row["Remarque"]))
                
                st.success("✅ Pointages enregistrés en base de données !")
                st.rerun()

    with tab_hist:
        st.dataframe(query_df("SELECT * FROM me_pointage"), use_container_width=True)

# --- E. PLANNING & TRAVAUX ---
elif menu == "📅 Planning & Travaux":
    st.title(f"📅 Attribution des Tâches : {champ_selectionne}")
    
    if not champ_id_actif:
        st.warning("⚠️ Aucune parcelle disponible. Veuillez d'abord ajouter une parcelle dans '🌱 Cartographie & Parcelles'.")
    else:
        st.dataframe(query_df("SELECT * FROM me_taches WHERE champ_id = ?", (champ_id_actif,)), use_container_width=True)
        
        st.subheader("➕ Planifier des Travaux & Déstocker des Intrants")
        with st.form("form_tache", clear_on_submit=True):
            groups = query_df("SELECT * FROM me_equipes")
            eq_t = st.selectbox("Groupe", groups['nom_groupe'].tolist() if not groups.empty else ["Aucun"])
            act_t = st.selectbox("Activité", ["Labour", "Semis", "Irrigation", "Désherbage", "Fertilisation / Epandage", "Traitement Phytosanitaire", "Récolte"])
            date_t = st.date_input("Date prévue", value=date.today())
            hrs_t = st.number_input("Heures", min_value=1.0, value=6.0)
            
            st.divider()
            st.caption("📦 Déstockage automatique (Si application d'intrants)")
            intrants_avail = query_df("SELECT * FROM me_intrants")
            use_intrant = st.checkbox("Consommer un intrant pour cette tâche ?")
            intrant_names = intrants_avail['nom'].tolist() if not intrants_avail.empty else ["Aucun"]
            selected_intrant = st.selectbox("Intrant utilisé", intrant_names)
            qty_used = st.number_input("Quantité consommée", min_value=0.0, value=0.0)

            if st.form_submit_button("Valider l'affectation"):
                grp_id = query_db("SELECT id FROM me_equipes WHERE nom_groupe = ?", (eq_t,), one=True)
                g_id = grp_id['id'] if grp_id else 0
                
                execute_db("""
                    INSERT INTO me_taches (champ_id, groupe_id, type_travail, date_tache, heures_travaillees, statut)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (champ_id_actif, g_id, act_t, str(date_t), hrs_t, "Planifié"))
                
                if use_intrant and qty_used > 0 and selected_intrant in intrant_names:
                    execute_db("UPDATE me_intrants SET stock_actuel = stock_actuel - ? WHERE nom = ?", (qty_used, selected_intrant))
                    st.info(f"📉 Stock de '{selected_intrant}' réduit de {qty_used} !")
                
                st.success("Tâche et déstockage enregistrés !")
                st.rerun()

# --- F. RÉCOLTES & RENDEMENTS ---
elif menu == "🌾 Récoltes & Rendements":
    st.title(f"🌾 Pesées : {champ_selectionne}")
    
    if not champ_id_actif:
        st.warning("⚠️ Aucune parcelle disponible. Créez au moins une parcelle.")
    else:
        st.dataframe(query_df("SELECT * FROM me_recoltes WHERE champ_id = ?", (champ_id_actif,)), use_container_width=True)
        
        with st.form("form_rec", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            cult = c1.text_input("Variété / Culture *")
            qte = c2.number_input("Quantité (Kg) *", min_value=0.0, step=10.0)
            pu = c3.number_input("Prix unitaire (FCFA)", min_value=0, value=350)
            d_rec = st.date_input("Date de récolte", value=date.today())
            
            if st.form_submit_button("Enregistrer la pesée"):
                if cult and qte > 0:
                    execute_db("INSERT INTO me_recoltes (champ_id, culture, date_recolte, quantite_kg, prix_unitaire) VALUES (?, ?, ?, ?, ?)",
                               (champ_id_actif, cult, str(d_rec), qte, pu))
                    st.success("Pesée enregistrée !")
                    st.rerun()
                else:
                    st.error("❌ Renseignez la variété et une quantité valide.")

# --- G. FINANCES & MARGES ---
elif menu == "💰 Finances & Marges":
    st.title(f"💰 Bilan Financier & Factures : {champ_selectionne}")
    
    if not champ_id_actif:
        st.warning("⚠️ Aucune parcelle disponible. Créez au moins une parcelle.")
    else:
        deps = query_df("SELECT * FROM me_depenses WHERE champ_id = ?", (champ_id_actif,))
        
        st.subheader("📋 Historique des dépense(s)")
        if not deps.empty:
            for idx, r in deps.iterrows():
                col_d1, col_d2, col_d3, col_d4 = st.columns([2, 2, 2, 2])
                col_d1.write(f"**{r['type']}**")
                col_d2.write(f"{r['montant']} FCFA")
                col_d3.write(f"{r['date']}")
                
                if r['facture_chemin'] and os.path.exists(r['facture_chemin']):
                    with open(r['facture_chemin'], "rb") as f:
                        col_d4.download_button("👁️ Voir Facture", f, file_name=os.path.basename(r['facture_chemin']), key=f"f_dep_{r['id']}")
                else:
                    col_d4.caption("Aucun fichier")
        else:
            st.info("Aucune dépense enregistrée sur cette parcelle.")

        st.subheader("➕ Ajouter une dépense / facture")
        with st.form("form_dep", clear_on_submit=True):
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                motif = st.text_input("Motif dépense *")
                mnt = st.number_input("Montant (FCFA) *", min_value=0, step=500)
                date_dep = st.date_input("Date", value=date.today())
            with col_f2:
                facture_file = st.file_uploader("📸 Joindre/Scanner Facture (Image ou PDF)", type=['jpg', 'jpeg', 'png', 'pdf'])
            
            if st.form_submit_button("💾 Enregistrer"):
                if motif and mnt > 0:
                    fact_path = ""
                    if facture_file:
                        fact_path = os.path.join(UPLOAD_DIR, f"dep_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{facture_file.name}")
                        with open(fact_path, "wb") as f:
                            f.write(facture_file.getbuffer())
                    
                    execute_db("""
                        INSERT INTO me_depenses (champ_id, type, montant, date, facture_chemin)
                        VALUES (?, ?, ?, ?, ?)
                    """, (champ_id_actif, motif, mnt, str(date_dep), fact_path))
                    
                    st.success("Dépense enregistrée !")
                    st.rerun()

# --- H. STOCKS D'INTRANTS ---
elif menu == "📦 Stocks d'Intrants":
    st.title("📦 Gestion du Magasin d'Intrants")
    
    st.dataframe(query_df("SELECT id, nom, categorie, stock_actuel, unite, seuil_alerte FROM me_intrants"), use_container_width=True)
    
    st.subheader("➕ Entrée en Stock / Approvisionnement")
    with st.form("form_intrant", clear_on_submit=True):
        col_i1, col_i2 = st.columns(2)
        with col_i1:
            nom_i = st.text_input("Intrant *")
            cat_i = st.selectbox("Catégorie", ["Engrais", "Herbicide", "Fongicide", "Insecticide", "Semences", "Carburant", "Autres"])
            stk_i = st.number_input("Quantité", min_value=0.0)
            unit_i = st.text_input("Unité (ex: Sacs, Litres)")
            seuil_i = st.number_input("Seuil Alerte", min_value=1.0, value=5.0)
        with col_i2:
            facture_i = st.file_uploader("📸 Bon de Commande / Facture", type=['jpg', 'jpeg', 'png', 'pdf'])

        if st.form_submit_button("💾 Enregistrer"):
            if nom_i:
                fact_path = ""
                if facture_i:
                    fact_path = os.path.join(UPLOAD_DIR, f"stk_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{facture_i.name}")
                    with open(fact_path, "wb") as f:
                        f.write(facture_i.getbuffer())

                execute_db("""
                    INSERT INTO me_intrants (nom, categorie, stock_actuel, unite, seuil_alerte, facture_chemin)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (nom_i, cat_i, stk_i, unit_i, seuil_i, fact_path))
                st.success("✅ Stock mis à jour !")
                st.rerun()

# --- I. PLUVIOMÉTRIE ---
elif menu == "🌧️ Pluviométrie":
    st.title(f"🌧️ Pluviométrie : {champ_selectionne}")
    if not champ_id_actif:
        st.warning("⚠️ Aucune parcelle disponible.")
    else:
        st.dataframe(query_df("SELECT * FROM me_pluviometrie WHERE champ_id = ?", (champ_id_actif,)), use_container_width=True)
        with st.form("form_pluie", clear_on_submit=True):
            d_pluie = st.date_input("Date", value=date.today())
            mm = st.number_input("Précipitations (mm)", min_value=0.0, step=0.5)
            if st.form_submit_button("Saisir"):
                if mm > 0:
                    execute_db("INSERT INTO me_pluviometrie (champ_id, date, pluie_mm) VALUES (?, ?, ?)", (champ_id_actif, str(d_pluie), mm))
                    st.success("Relevé pluviométrique ajouté !")
                    st.rerun()

# --- J. INCIDENTS ---
elif menu == "⚠️ Incidents":
    st.title(f"⚠️ Incidents : {champ_selectionne}")
    if not champ_id_actif:
        st.warning("⚠️ Aucune parcelle disponible.")
    else:
        st.dataframe(query_df("SELECT * FROM me_incidents WHERE champ_id = ?", (champ_id_actif,)), use_container_width=True)
        with st.form("form_inc", clear_on_submit=True):
            d_inc = st.date_input("Date", value=date.today())
            desc = st.text_area("Description")
            grav = st.selectbox("Gravité", ["Faible", "Moyenne", "Élevée"])
            act = st.text_input("Action entreprise")
            if st.form_submit_button("Déclarer"):
                if desc:
                    execute_db("INSERT INTO me_incidents (champ_id, date, description, gravite, action) VALUES (?, ?, ?, ?, ?)",
                               (champ_id_actif, str(d_inc), desc, grav, act))
                    st.success("Incident consigné !")
                    st.rerun()

# --- K. MAINTENANCE MATÉRIEL ---
elif menu == "🚜 Maintenance Matériel":
    st.title("🚜 Parc Matériel")
    st.dataframe(query_df("SELECT * FROM me_materiel"), use_container_width=True)
    with st.form("form_mat", clear_on_submit=True):
        nom_m = st.text_input("Équipement")
        cat_m = st.selectbox("Catégorie", ["Tracteur", "Motopompe", "Pulvérisateur", "Moissonneuse", "Autre"])
        stat_m = st.selectbox("Statut", ["Opérationnel", "En maintenance", "Hors service"])
        d_rev = st.date_input("Prochaine révision")
        if st.form_submit_button("Ajouter"):
            if nom_m:
                execute_db("INSERT INTO me_materiel (nom_equipement, categorie, statut_marche, date_derniere_revision, prochaine_revision) VALUES (?, ?, ?, ?, ?)",
                           (nom_m, cat_m, stat_m, str(date.today()), str(d_rev)))
                st.rerun()

# --- L. TRAÇABILITÉ & LOTS ---
elif menu == "🏷️ Traçabilité & Lots":
    st.title("🏷️ Traçabilité & Lots")
    st.dataframe(query_df("SELECT * FROM me_tracabilite"), use_container_width=True)
    with st.form("form_trac", clear_on_submit=True):
        code_l = st.text_input("Code Lot", value=f"LOT-{date.today().strftime('%Y%m%d')}-01")
        cult_l = st.text_input("Culture / Variété")
        certif = st.selectbox("Norme", ["Bio / GlobalGAP", "Conforme Norme Nationale", "Standard"])
        ach_l = st.text_input("Acheteur / Client")
        if st.form_submit_button("Créer le Lot"):
            execute_db("INSERT INTO me_tracabilite (lot_code, champ_nom, culture, date_recolte, norme_certification, acheteur) VALUES (?, ?, ?, ?, ?, ?)",
                       (code_l, champ_selectionne, cult_l, str(date.today()), certif, ach_l))
            st.rerun()

# --- M. IRRIGATION & EAU ---
elif menu == "💧 Irrigation & Eau":
    st.title("💧 Irrigation & Consommation d'Eau")
    st.dataframe(query_df("SELECT * FROM me_irrigation"), use_container_width=True)
    with st.form("form_irr", clear_on_submit=True):
        v_eau = st.number_input("Volume (m³)", min_value=0.0)
        m_irr = st.selectbox("Méthode", ["Goutte-à-goutte", "Aspersion", "Submersion", "Canon"])
        d_irr = st.number_input("Durée (Heures)", min_value=0.5, value=2.0)
        if st.form_submit_button("Enregistrer Session"):
            execute_db("INSERT INTO me_irrigation (champ_nom, date, volume_eau_m3, methode, duree_heures) VALUES (?, ?, ?, ?, ?)",
                       (champ_selectionne, str(date.today()), v_eau, m_irr, d_irr))
            st.rerun()

# --- N. RISQUES & MÉTÉO ---
elif menu == "🌤️ Risques & Météo":
    st.title("🌤️ Risques & Directives Météo")
    st.dataframe(query_df("SELECT * FROM me_alertes_meteo"), use_container_width=True)
    with st.form("form_meteo", clear_on_submit=True):
        t_r = st.selectbox("Risque", ["Vague de chaleur", "Inondation", "Vent fort", "Ravageurs"])
        n_a = st.selectbox("Niveau", ["🟢 Faible", "🟡 Modéré", "🔴 Élevé"])
        cons = st.text_area("Directives du Technicien")
        if st.form_submit_button("Publier l'Alerte"):
            execute_db("INSERT INTO me_alertes_meteo (date, type_risque, niveau_alerte, recommandation_ts) VALUES (?, ?, ?, ?)",
                       (str(date.today()), t_r, n_a, cons))
            st.rerun()

# --- O. RENTABILITÉ & ROI ---
elif menu == "📈 Rentabilité & ROI":
    st.title("📈 Calculateur de Rentabilité Réelle & ROI")
    st.caption("Prend en compte la masse salariale réelle issue des pointages et les factures de chaque parcelle.")

    champs_all = query_df("SELECT * FROM me_champs")
    if not champs_all.empty:
        res = []
        for _, c in champs_all.iterrows():
            cid = c['id']
            c_nom = c['nom']
            
            # Ventes (Récoltes)
            ca = query_db("SELECT SUM(quantite_kg * prix_unitaire) as val FROM me_recoltes WHERE champ_id = ?", (cid,), one=True)['val'] or 0
            
            # Dépenses directes (Factures)
            ch_dep = query_db("SELECT SUM(montant) as val FROM me_depenses WHERE champ_id = ?", (cid,), one=True)['val'] or 0
            
            # Masse Salariale calculée d'après le pointage
            pointages = query_df("SELECT employe_nom FROM me_pointage WHERE champ_nom = ? AND statut_presence = 'Présent'", (c_nom,))
            main_oeuvre = 0
            if not pointages.empty:
                for emp in pointages['employe_nom']:
                    e_rate = query_db("SELECT tarif_journalier FROM me_employes WHERE nom = ?", (emp,), one=True)
                    main_oeuvre += (e_rate['tarif_journalier'] if e_rate else 3000)
            
            total_charges = ch_dep + main_oeuvre
            marge = ca - total_charges
            roi = (marge / total_charges * 100) if total_charges > 0 else 0
            
            res.append({
                "Parcelle": c_nom,
                "Ventes Total (FCFA)": ca,
                "Factures & Intrants (FCFA)": ch_dep,
                "Masse Salariale (FCFA)": main_oeuvre,
                "Charges Totales (FCFA)": total_charges,
                "Marge Nette (FCFA)": marge,
                "ROI (%)": round(roi, 2)
            })
            
        st.dataframe(pd.DataFrame(res), use_container_width=True)

# --- P. EXPORT COMPLET ---
elif menu == "📑 EXPORT COMPLET":
    st.title("📑 Générateur de Rapport Synthétique d'Exploitation")
    date_export = st.date_input("Sélectionner la journée :", value=date.today())

    st.divider()
    col_dl1, col_dl2 = st.columns(2)
    
    with col_dl1:
        st.markdown("#### 📄 Rapport PDF Certifié")
        pdf_data = export_global_pdf(date_export)
        st.download_button("📥 Télécharger PDF", data=pdf_data, file_name=f"Rapport_{date_export}.pdf", mime="application/pdf", use_container_width=True)

    with col_dl2:
        st.markdown("#### 📊 Classeur Excel Global")
        excel_data = export_global_to_excel()
        st.download_button("📥 Télécharger Excel", data=excel_data, file_name=f"Base_{date_export}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
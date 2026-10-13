import streamlit as st
import sqlite3
import pandas as pd
import io
from datetime import datetime, date, timedelta
import base64
import time
import plotly.express as px
import calendar
import hashlib
from email_utils import notifier_user_valide, NOT_CONFIGURED
#--------------------------------     
# Confugarition de la mise en forme de la page 
#--------------------------------
st.set_page_config(
    page_title="SNAKE",
    page_icon="🐍",
    layout="wide"
)

# ── CSS ────────────────────────────────────────────────────────
st.markdown("""
    <style>
        #MainMenu {visibility: hidden;}
        header {visibility: hidden;}
        footer {visibility: hidden;}
        [data-testid="stSidebarNav"] {display: none;}
        [data-testid="stSidebar"] {
            min-width: 380px !important;
            max-width: 380px !important;
        }
        [data-testid="stSidebar"] > div:first-child {
            padding-top: 0 !important;
            padding-left: 0 !important;
            padding-right: 0 !important;
        }
    </style>
""", unsafe_allow_html=True)

# ── Logo sidebar ───────────────────────────────────────────────
def get_base64_image(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

img_b64 = get_base64_image("Logo_3_simplet.png")

st.sidebar.markdown(f"""
    <div style="text-align: center; padding: 0; margin: 0 -1rem;">
        <img src="data:image/png;base64,{img_b64}" 
             style="width: 100%; display: block;" />
    </div>
""", unsafe_allow_html=True)
st.sidebar.markdown("""
<div style="
    position: fixed;
    bottom: 10px;
    left: 20px;
    font-size: 12px;
    color: gray;
    opacity: 0.8;
">
   Powered by IAK
</div>
""", unsafe_allow_html=True)

st.sidebar.divider()

# ── Navigation ─────────────────────────────────────────────────
st.sidebar.page_link("app.py",                              label="🏠 Home")
st.sidebar.page_link("pages/1_Reservation-Annulation.py",   label="📅 Reservation / Cancellation")
st.sidebar.page_link("pages/2_Category_View.py",            label="🗂️ Category view")
st.sidebar.page_link("pages/3_Admin.py",                    label="⚙️ Admin")

#--------------------------------     
# Définition des fonctions utilitaires
#--------------------------------

def alerte_quota ( quota,nombre_heure): 
  # #  ------------------------------- 
  # Vérifie si le nombre d'heures de fonctionnement a dépassé le quota défini.: Retourne True si le quota est atteint ou dépassé, False sinon.

  
  verif=False
  if quota is None or nombre_heure is None: 
     verif =False
  else:   
   if quota<=nombre_heure:
    verif=True
   else:
    verif=False
  return(verif)  
def calcul_temps_fonctionnement(df_resa, date_value):
    # #  ------------------------------- 
    #   Calcule le nombre d'heures de fonctionnement d'un équipement  depuis la dernière date de maintenance.
    # Seules les réservations postérieures à date_value sont comptabilisées
    # #  ------------------------------- 

    heure_fct_maintenance = 0

   
    if pd.isna(date_value): # Si la date de maintenance est nulle, on retourne 0
        
        return 0


    date_maintenance = pd.to_datetime(date_value)
   
    for x, z in zip(df_resa["Début"], df_resa["Fin"]): #  Parcours de toutes les réservations

        debut = pd.to_datetime(x)
        fin = pd.to_datetime(z)

        # Cas 1 : la réservation est entièrement après la maintenance                          
        if debut > date_maintenance: 

            duree = (fin - debut).total_seconds() / 3600 # Conversion secondes → heures
            heure_fct_maintenance += duree
           # Cas 2 : la réservation chevauche la date de maintenance
        elif debut < date_maintenance < fin:
                # On ne compte que la partie après la maintenance
                duree_apres_maintenance = (fin - date_maintenance).total_seconds() / 3600
                heure_fct_maintenance += duree_apres_maintenance
  

    return heure_fct_maintenance
def temps_totale_fct (def_resa):
      # #  ------------------------------- 
      # Calcule le total brut des heures de fonctionnement à partir des réservations.
      # #  ------------------------------- 
    heure_fct=0
    for i,j in zip(df_resa["Début"],df_resa["Fin"]):
        debut = pd.to_datetime(i)
        fin=pd.to_datetime(j)
        duree= (fin - debut).total_seconds() / 3600 # Conversion secondes → heures
        heure_fct=heure_fct+ duree
    return(heure_fct) 
def calcul_tempsfctparmois(df_resa):
      # #  ------------------------------- 
      # Calcule le nombre total d'heures de fonctionnement par mois et par année à partir du DataFrame des réservations.
      #Retourne un DataFrame avec les colonnes : année, mois, duree (en heures)
      # #  ------------------------------- 
    heure_fct=0

    df_resa["Début"] = pd.to_datetime(df_resa["Début"])
    df_resa["Fin"] = pd.to_datetime(df_resa["Fin"])
    df_resa["année"]=df_resa["Début"].dt.year
    df_resa["mois"]=df_resa["Début"].dt.month
    df_resa["duree"]=(df_resa["Fin"]-df_resa["Début"]).dt.total_seconds() / 3600
    result=df_resa.groupby(["année","mois"])["duree"].sum().reset_index()

    return result  
def identification_admin(mp):
      # #  ------------------------------- 
      # Vérifie si le mot de passe saisi correspond au mot de passe admin stocké en base.
      #Le mot de passe est comparé sous forme de hash SHA-256 pour garantir la sécurité.
      #Retourne True si le mot de passe est correct, False sinon.
      # #  ------------------------------- 
    conn = sqlite3.connect("db/lab.db")
    c = conn.cursor()
    c.execute("SELECT code FROM admin_code")
    code=c.fetchone()# appel du code enregistré dans la base de donnée 
    conn.close()
    
    if hashlib.sha256(mp.encode()).hexdigest()==code[0]:# Comparaison du mot de passe saisi (haché) avec le mot de passe enregistré (haché)
        verif=True # vrai si les deux mot passe sont identiques
    else:
        verif=False 
    return verif      
#--------------------------------     
# Popup : demande d'enregistrement d'un nouveau profil administrateur
#--------------------------------
@st.dialog("Information")
def ask_dialog ():
 # #  ------------------------------- 
      # Dialogue affiché lorsqu'un utilisateur se connecte avec un email non enregistré.
      # Propose d'ajouter ce profil comme nouvel administrateur.
# #  ------------------------------- 
          name_admin = st.session_state.pending_name # Récupère le nom tapé
          email_admin = st.session_state.pending_email # Récupère l'email
                
          st.info("This profile is not registered yet. Would you like to add it as a new administrator?")# affichage du message , si profil non enregistré
                
          col1, col2 = st.columns(2)

          with col1:
            if st.button("Yes"): # Si le bouton "yes" est cliqué, le profil est enregistré dans la base de données
              conn = sqlite3.connect("db/lab.db")
              c = conn.cursor()     
              c.execute(
                "INSERT INTO admin (name_admin, email) VALUES (?, ?)",
                (name_admin, email_admin))
              st.success(("Administrator added "))
              conn.commit()
              conn.close()
              st.session_state.show_dialog = False  
              time.sleep(2)
              st.rerun ()
          with col2:
                  if st.button("No"):# Si "no" le profil ne sera pas enregistré
                   st.warning("Profile not registred")
                   st.session_state.show_dialog = False  
                   time.sleep(2)
                   st.rerun() 
               
  
#--------------------------------     
# Initialisation du mot de passe admin en base (une seule fois via INSERT OR IGNORE)
#--------------------------------
# Le mot de passe initial est lu dans .streamlit/secrets.toml (section [admin]),
# jamais ecrit en dur dans le code.
try:
    initial_admin_password = st.secrets["admin"]["password"]
except (KeyError, FileNotFoundError):
    initial_admin_password = None

if initial_admin_password:
    conn = sqlite3.connect("db/lab.db")
    c = conn.cursor()
    admin_code=hashlib.sha256(initial_admin_password.encode()).hexdigest() # Hash SHA-256 du mot de passe admin pour le stocker de façon sécurisée
    c.execute("""
    INSERT OR IGNORE INTO admin_code (id, code)
    VALUES (1, ?)
    """, (admin_code,)) # Le mot de passe n'est enregistré que si il n'existe pas dans la base de données
    conn.commit()
    conn.close()

#--------------------------------     
# Initialisation des variables de session utilisées dans la page
#--------------------------------

if "admin_conn" not in st.session_state:
      st.session_state.admin_conn = False # Statut de connexion admin (False par défaut)

if "show_dialog" not in st.session_state: # Contrôle l'affichage du popup d'ajout d'admin
    st.session_state.show_dialog = False

if "pending_name" not in st.session_state:  # Nom temporaire en attente de validation
    st.session_state.pending_name = None

if "pending_email" not in st.session_state: # Email temporaire en attente de validation

    st.session_state.pending_email = None   
#--------------------------------     
# Formulaire de connexion admin (affiché uniquement si non connecté)
#--------------------------------
if not st.session_state.admin_conn:    # Toujours False si pas de mot passe ou si le passe est incorrect 
  
# Affichage du carré pour les informations login
  st.subheader(" Admin Login ")
  with st.form("Admin login"):
   name_admin=st.text_input("Name")
   email_admin = st.text_input("Email")
   password = st.text_input("password", type="password")

   submit = st.form_submit_button("Login")

  if submit: # Devient vrai si la personne a cliqué sur le bouton "connexion"
  
   if email_admin: # Si le champ Email n'est pas vide 
  
    if password: # Si le champ password est non vide
    
   
     verif= identification_admin(password) # Appel de la fonction de vérification des mots passe ( plus haut)
   
     if verif: # Si le mot passe est correct
       
        st.session_state.admin_conn=True
        st.session_state.admin_name = name_admin
        # Vérification si l'email est déjà enregistré comme admin
        conn = sqlite3.connect("db/lab.db")
        c = conn.cursor()
        c.execute("SELECT email FROM admin WHERE email=?",(email_admin,)) # Vérifie si l'email tapé a été déja enregistré auparavant ( profil récent?)
       
        admin_mail=c.fetchone()
        if admin_mail is None:  # Nouvel email → déclenche le popup d'ajout
                    st.session_state.pending_name = name_admin
                    st.session_state.pending_email = email_admin
                    st.session_state.show_dialog = True # Ne devient True que si nouveau Email
        conn.commit()
        conn.close()
        st.rerun()
     else:
       st.error("incorrect password, try again")
   else:
       st.error("Please enter your email")  

if st.session_state.get("show_dialog"): # Affichage de la Popup car nouveau Email :profil non enregistré ( plus haut)

    ask_dialog()


#--------------------------------     
# Interface admin (visible uniquement après connexion réussie)
#--------------------------------

if st.session_state.admin_conn: # Devient True que si le mot de passe est correct ( plus haut)
 # En-tête : titre + nom de l'utilisateur connecté + bouton Log out
 col1, col2 = st.columns([7, 3], vertical_alignment="center") 
    
 with col1:
       st.markdown("<p style='font-size:28px; font-weight:600; margin:0;'>Interface administrateur</p>",unsafe_allow_html=True) # titre
    
 with col2:
        # Affichage du nom de la personne connectée
        admin_name = st.session_state.get('admin_name', '')
        col_name, col_btn = st.columns([1, 1])
        with col_name:
    
         st.markdown(
            f"""<div style="display:flex; align-items:center; justify-content:flex-end; height:38px;">
                <span style="background:var(--secondary-background-color);  color: var(--text-color); border-radius:8px; padding:6px 12px; border: 1px solid var(--border-color); font-size:16px; white-space:nowrap;">
                    👤 {admin_name}
                </span>
            </div>""",
            unsafe_allow_html=True
        )
         
     # Création du bouton Log out
        with col_btn: 
         if st.button("Déconnexion"): # Si le bouton log out est activé
             # Suppression de toutes les clés du session_state pour réinitialiser complètement la session
            # (admin_conn repasse à False → le formulaire de connexion réapparaît)  
            for key in list(st.session_state.keys()):
                del st.session_state[key] # Vide complètement la session utilisateur (suppression de toutes les variables)
            
            st.rerun()  # Recharge la page pour afficher le formulaire de connexion
          
    
 st.divider() # Ligne de séparation visuelle dans l'interface

#--------------------------------     
# Gestion  des utilisateurs
#--------------------------------

# Connexion DB
 conn = sqlite3.connect("db/lab.db")
 c = conn.cursor()
# 
    # Récupération de tous les utilisateurs enregistrés en base
 c.execute("SELECT nom,intiales,email,birthday,validation FROM users")
 user = c.fetchall()
 conn.close()
 df_user = pd.DataFrame(user, columns=["nom", "initiales BBF","email","anniversaire", "validation"]) # Créer une Data frame avec les donées récupéres

 df_user["statut"] = df_user["validation"].apply(lambda x: "validé" if x == 1 else "non validé") # Création d'une colonne 'statut' avec Validé et non validé


 st.subheader(" 👥 Gestion des utilisateurs") # Titre de la partie qui va s'afficher dans l'application
 st.markdown("<br>", unsafe_allow_html=True)# Faire un espace entre le titre et le reste
  # --- Initialisation des cases à cocher dans le session_state ---
 if not df_user.empty:# Si il y a des utilisateurs
    # Filtres de recherche par nom et par initiales-
    col_u1, col_u2 = st.columns(2)
    with col_u1:
        search_nom = st.text_input("🔍 Rechercher par nom", "")
    with col_u2:
        search_initiales = st.text_input("🔍 Rechercher par initiales", "")

    # Application des filtres sur une copie du DataFrame (l'original n'est pas modifié)
    df_filtered = df_user.copy()# Créeation d'une copie du tableau pour éviter de modifier l'original
    if search_nom:
        df_filtered = df_filtered[
            df_filtered["nom"].str.contains(search_nom, case=False, na=False)
        ]# Garde les lignes du tableau si le nom contient search_nom
    if search_initiales:
        df_filtered = df_filtered[
            df_filtered["initiales BBF"].str.contains(search_initiales, case=False, na=False)
        ]# Garde les lignes du tableau avec les initiaux recherchés

    st.caption(f"{len(df_filtered)} utilisateur(s) affiché(s)")# Affichage des nombres de lignes affichées

    
    # Préparation du tableau éditeur avec colonnes "validé" et "supprimer"
    df_editor = df_filtered.copy()
    df_editor["validé"]     = df_editor["validation"] == 1 # True si l'utilisateur est validé
    df_editor["supprimer"] = False     # Case à cocher pour suppression
    
    edited_users = st.data_editor(
        # st.data_editor affiche un tableau interactif modifiable directement dans l'interface
        # Les colonnes "nom", "initiales BBF", "email", "statut" sont en lecture seule (disabled=True)
        # Seules les colonnes "validé" et "supprimer" sont éditables (checkboxes)

        df_editor[["nom", "initiales BBF", "email","anniversaire", "statut", "validé", "supprimer"]],
        column_config={
            "nom":            st.column_config.TextColumn("Nom",             disabled=True, width="medium"),
            "initiales BBF":  st.column_config.TextColumn("Initiales BBF",   disabled=True, width="small"),
            "email":          st.column_config.TextColumn("Email",           disabled=True, width="large"),
            "anniversaire":   st.column_config.TextColumn("anniversaire",           disabled=True, width="large"),
            "statut":         st.column_config.TextColumn("Statut",          disabled=True, width="small"),
            "validé":      st.column_config.CheckboxColumn("✅ Validé",    width="small"),
            "supprimer":  st.column_config.CheckboxColumn("🗑️ Supprimer", width="small"),
        },
        hide_index=True,
        use_container_width=True,
        key="user_editor"
    ) 
  

    if st.button("Valider les changements"): # Si la personne clique sur le bouton valider les changements
        conn = sqlite3.connect("db/lab.db")
        c = conn.cursor()
        newly_validated = []  # (nom, email) des profils qui passent de "non validé" -> "validé"
        for i, row in edited_users.iterrows():# Parcours des lignes éditées pour appliquer les suppressions ou mises à jour à chaque ligne du tableau
            email_user = row["email"]
            if row["supprimer"]:# Suppression physique si la case supprimé est coché
                c.execute("DELETE FROM users WHERE email = ?", (email_user,))

            else:
                val = 1 if row["validé"] else 0 # Mise à jour du champ validation : 1 = validé, 0 = non validé
                c.execute(
                    "UPDATE users SET validation = ? WHERE email = ?",
                    (val, email_user)
                )
                # Transition non validé -> validé : on notera l'utilisateur par email.
                # (row["statut"] reflète l'état AVANT édition : "validé" / "non validé")
                if val == 1 and row["statut"] == "non validé":
                    newly_validated.append((row["nom"], email_user))
        conn.commit() # Sauvegarde toutes les modifications en une seule transaction
        conn.close()

        # Emails "votre profil est validé" (non bloquant : un échec n'annule rien)
        for nom_u, email_u in newly_validated:
            ok_mail, err_mail = notifier_user_valide(nom_u, email_u)
            if not ok_mail and err_mail != NOT_CONFIGURED:
                st.caption(f"ℹ️ Email de validation non envoyé à {email_u} ({err_mail})")

        st.success("Base de données mise à jour ✅")
        time.sleep(2)
        st.rerun()

 else:
    st.info("Aucun profil utilisateur enregistré")   # Si pas d'utilisateurs enregistrés dans la base

#--------------------------------     
# Gestion des permissions de réservation par utilisateur et par équipement
#--------------------------------
 # --- Chargement des donées ---
 st.markdown("<br><br>", unsafe_allow_html=True) 
 conn = sqlite3.connect("db/lab.db")
 c = conn.cursor()  
 # Récupération des utilisateurs validés uniquement  
 c.execute("SELECT id, nom,intiales FROM users WHERE validation = ?", (1,)) 
 personels = c.fetchall()
 df_personels=pd.DataFrame(personels,columns=["id","nom","intiales"])
 
# Récupération des équipements nécessitant une permission pour être réservés
 c.execute("SELECT id, Nom, Numero_salle, Nom_salle FROM equipements WHERE Demande_permission=?",("Oui",))# Récupération des equipements qui demandent une validation
 equipements = c.fetchall()  
 df_equipements=pd.DataFrame(equipements,columns=["id","nom","room number","room name"])

 # Récupération de la table des permissions (qui a le droit sur quel équipement)
 c.execute("SELECT id, user_id, equipment_id FROM user_equipment_write_permissions ") 
 permessions= c.fetchall()
 conn.commit()
 conn.close()
 df_permessions=pd.DataFrame(permessions,columns=["id permi","user_id","id_equipements"])
 # --- Affichage de la rubrique ---
 st.subheader(" 🔐 Gestion des droits de réservation des utilisateurs")
 st.markdown("<br>", unsafe_allow_html=True)
  # --- Code d'affichage du tableau et de la gestion des permissions--
 if not df_user.empty:
  # Filtres de recherche pour équipements et utilisateurs
  col_f1, col_f2 = st.columns(2)
  with col_f1:
        search_eq = st.text_input("🔍 Rechercher un équipement ou une salle", "")
  with col_f2:
        search_user = st.text_input("🔍 Rechercher un utilisateur", "")

    
   # Filtrage dynamique des équipements et utilisateurs
  df_eq_filtered = df_equipements[
        df_equipements["nom"].str.contains(search_eq, case=False, na=False) |
        df_equipements["room name"].str.contains(search_eq, case=False, na=False)
    ]
  df_users_filtered = df_personels[
        df_personels["intiales"].str.contains(search_user, case=False, na=False)
    ]
  def build_matrix(df_eq, df_users, df_perms):
         # #  ------------------------------- 
           #  Construit une matrice de permissions : lignes = équipements, colonnes = utilisateurs.
           #  Chaque cellule est True si l'utilisateur a la permission sur l'équipement, False sinon.
        # #  -------------------------------  
        
        matrix = {}
        for _, eq in df_eq.iterrows(): #  Pour chaque equipement
            label = f"{eq['room name']} — {eq['nom']}" # Construction d'un label affiché
            row = {"_eq_id": eq["id"], "Équipement / Salle": label} # Construction des lignes de la matrice avec deux colonnes : id :non affiché et les noms des Equipements et salle
            for _, user in df_users.iterrows(): #  Pour chaque utilisateur
                has_perm = not df_perms[
                    (df_perms["user_id"] == user["id"]) &
                    (df_perms["id_equipements"] == eq["id"])
                ].empty# # Cherche une ligne correspondant à cet utilisateur ET cet équipement dans la table des permissions. Si elle existe → True , sinon → False .
                row[user["intiales"]] = has_perm  # la case user["intiales"] reçoit le résultat de has_perm
            matrix[eq["id"]] = row # On stocke la ligne (row) dans le dictionnaire matrix en utilisant l'ID de l'équipement comme clé unique pour éviter les doublons
        return pd.DataFrame(matrix.values() )# retourne une Dataframe de la Matrix
  df_matrix = build_matrix(df_eq_filtered, df_users_filtered,  df_permessions)
  if df_matrix.empty or "_eq_id" not in df_matrix.columns:
    st.info("Aucun équipement trouvé.")
  else:  
   user_cols = df_users_filtered["intiales"].tolist() # Crée une liste avec tout  les initiaux des utilisateurs

   edited = st.data_editor(df_matrix,
      
               
        column_config={
            "_eq_id" :None,
            "Équipement / Salle": st.column_config.TextColumn(disabled=True, width="large"),
            **{
                col: st.column_config.CheckboxColumn(col, width="small")
                for col in user_cols # Crée une colonne par initiale
            }
        },
        hide_index=True,
        use_container_width=True,
        key="permission_editor"
    )
   if st.button("✅ Valider les permissions"):
        
       
        conn = sqlite3.connect("db/lab.db")
        c = conn.cursor()
        for _, row in edited.iterrows():  # Parcours chaque ligne du tableau = chaque équipement
            eq_id = row["_eq_id"]  # Récupère l'id de l'équipement de cette ligne
            for _, user in df_users_filtered.iterrows(): # Pour chaque utilisateur 
                user_id = user["id"]  # Récupére l'identifiant de l'utilisateur
                has_perm = row[user["intiales"]]  # Lit la valeur de la case [équipement × utilisateur] dans le tableau edited: True si cochée, False sinon
                
                if has_perm:  # Case cochée → l'utilisateur a la permission sur cet équipement
                    c.execute("""
                        INSERT OR IGNORE INTO user_equipment_write_permissions (user_id, equipment_id)
                        VALUES (?, ?)
                    """, (user_id, eq_id)) # INSERT OR IGNORE : si la permission existe déjà en base, on ne fait rien (pas de doublon)
                else: # Case décochée → l'utilisateur n'a pas (ou plus) la permission
                    c.execute("""
                        DELETE FROM user_equipment_write_permissions
                        WHERE user_id = ? AND equipment_id = ?
                    """, (user_id, eq_id)) # DELETE : si la permission n'existe pas en base, le DELETE ne fait rien (pas d'erreur)

        conn.commit()
        conn.close()
        st.success("Permissions mises à jour !")
        st.rerun()
 else:
    st.info("Aucun profil administrateur enregistré")  

 #--------------------------------     
  # Gestion des profils administrateurs enregistrés
#--------------------------------
 st.markdown("<br><br>", unsafe_allow_html=True)

 # --Affichage de la rubrique --            
 st.subheader(" 🧑‍💼 Gestion des profils administrateurs enregistrés")
 st.markdown("<br>", unsafe_allow_html=True)
  # --Récupération des données--  
 conn = sqlite3.connect("db/lab.db")
 c = conn.cursor()
 
 c.execute("""
SELECT id,
       name_admin,
       email,
       notification
FROM admin
""")

 admin=c.fetchall()# Récupération des résultats de la requête
 conn.commit()
 conn.close()
 df_admin=pd.DataFrame(admin, columns=["id","nom", "email", "notification"]) #  Conversion des données en DataFrame

 if not df_admin.empty: # Si le tableau est non vide ( Il y a des profils enregistrés)
  col1,col2,col3,col4=st.columns([3, 3, 2, 2])# Création de l'entete des colonnes du tableau
  col1.markdown("**Nom admin**")
  col2.markdown("**Email**")
  col3.markdown("**Notification activée**")
  col4.markdown("**Supprimer**")
  # Affichage de chaque ligne de la table des admins avec une checkbox de suppression
  for i, row in df_admin.iterrows(): # Parcours les lignes du DataFrame
    col1, col2,col3,col4= st.columns([3,3,2,2]) # Création des colonnes pour chaque ligne
    col1.write(row["nom"])
    col2.write(row["email"])
    if f"delete_{i}" not in st.session_state: # Initialisation de l'état de suppression si absent
        st.session_state[f"delete_{i}"] = False
    # Case "Notification activée" : cochée = cet admin reçoit les emails
    # "nouvel utilisateur à valider". Valeur initiale = état en base.
    checked_notif = col3.checkbox(
        "", key=f"notif_{i}", value=bool(row["notification"])
    )
    checked_del = col4.checkbox("", key=f"deletee_{i}") # Checkbox de suppression
  if st.button("Valider les changements",key="changement admin"):# Bouton de validation des suppressions
    conn = sqlite3.connect("db/lab.db")
    c = conn.cursor()
    for i, row in df_admin.iterrows(): # Parcours des administrateurs enregistrés
        email_admin = row["email"]
        if st.session_state[f"deletee_{i}"]: # Suppression si checkbox cochée
            c.execute("DELETE FROM admin WHERE email= ?", (email_admin,))
        else:
            # Mise à jour du réglage de notification (1 = coché, 0 = décoché)
            notif_val = 1 if st.session_state.get(f"notif_{i}") else 0
            c.execute(
                "UPDATE admin SET notification = ? WHERE email = ?",
                (notif_val, email_admin)
            )
    conn.commit()# Sauvegarde des modifications dans la base
    st.success("Base de données mise à jour ✅")
    conn.close() # Fermeture de la connexion à la base
    time.sleep(2)
    st.rerun()  # Actuallisation  de l'application
 else:
     st.info ("Aucun profil administrateur enregistré")    # Message si aucun administrateur n'est enregistré          

  #--------------------------------     
  # Gestion des equipements
#-------------------------------- 
 st.markdown("<br><br>", unsafe_allow_html=True)      
 st.subheader("🔬 Gestion des équipements")
 st.markdown("<br>", unsafe_allow_html=True)

 conn = sqlite3.connect("db/lab.db")
 c = conn.cursor()
 # --Filtres par nom de l'équipement et par salle--  
 filtre_col1, filtre_col2 = st.columns(2)
 with filtre_col1:
    search_nom = st.text_input("🔍 Rechercher un équipement", "", key="search_eq_nom")
 with filtre_col2:
    search_salle = st.text_input("🔍 Rechercher un nom de salle", "", key="search_eq_salle") 
 
# -- Récupération de toutes les colonnes de la table équipements.--   
 c.execute("""
SELECT id,
       Nom,
       Numero_salle,
       Nom_salle,
       Responsable,
       Coresponsable,
       Categorie,   
       Quota_fct_avant_maintenance,
       Quota_fct_par_mois,
       Date_maintenance,
       Date_installation,
       Nombre_heures_fct_depuis_maintenance,
       Nombre_heure_fct_depuis_installation,
       Etat,
       Besoin_maintenance,
       Date_prochain_arret,
       Compteur_d_arret_en_jours,
       Protocole,
       Demande_permission,
       Nb_jours_max_reservation
FROM equipements

""")

 eq = c.fetchall()


 df_eq = pd.DataFrame(
    eq,
    columns=[
        "id",
        "Nom",
        "Numero_salle",
        "Nom_salle",
        "Responsable",
        "Coresponsable",
        "Categorie",
        "Quota_fct_avant_maintenance",
        "Quota_fct_par_mois",
        "Date_maintenance",
        "Date_installation",
        "Nombre_heures_fct_depuis_maintenance",
        "Nombre_heure_fct_depuis_installation",
        "Etat",
        "Besoin_maintenance",
        "Date_prochain_arret",
        "Compteur_d_arret_en_jours",
        "Protocole",
        "Demande_permission",
        "Nb_jours_max_reservation"
    ]
)
 # -- Modification de la table selon le filtre.--   
 if search_nom:
    df_eq = df_eq[df_eq["Nom"].str.contains(search_nom, case=False, na=False)]

 if search_salle:
    df_eq = df_eq[df_eq["Nom_salle"].str.contains(search_salle, case=False, na=False)]
 df_eq = df_eq.reset_index(drop=True)   

 # -- Import depuis un fichier Excel préparé hors application ---------------
 st.markdown("<br>", unsafe_allow_html=True)
 with st.expander("📥 Import equipment from Excel"):
    st.caption(
        "Download the template below, edit it in Excel, then upload it here. "
        "Rows with an existing 'id' update that equipment; rows with an "
        "empty 'id' (or no 'id' column at all) are added as new equipment. "
        "Equipment not present in the file is left untouched — nothing is "
        "deleted automatically. 'Etat' should be 'Marche' or 'Panne', and "
        "'Demande_permission' should be 'Oui' or 'Non', to match the table's "
        "dropdowns."
    )
    st.caption(
        "⚠️ Don't use the ⬇️ download icon on the table below as your starting "
        "point — it hides the technical 'id' column needed to match rows for "
        "updates, so re-importing it would create duplicates instead of "
        "updating your equipment. Use this template instead:"
    )

    template_buffer = io.BytesIO()
    df_eq.to_excel(template_buffer, index=False, engine="openpyxl", sheet_name="equipements")
    st.download_button(
        "⬇️ Download current equipment as Excel template",
        data=template_buffer.getvalue(),
        file_name="equipements_template.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="eq_template_download"
    )

    imported_file = st.file_uploader("Choose an Excel file (.xlsx)", type=["xlsx"], key="eq_import_file")

    if imported_file is not None:
        try:
            df_import = pd.read_excel(imported_file)
        except Exception as e:
            st.error(f"Could not read this Excel file: {e}")
            df_import = None

        if df_import is not None:
            expected_cols = [
                "id", "Nom", "Numero_salle", "Nom_salle", "Responsable", "Coresponsable",
                "Categorie", "Quota_fct_avant_maintenance", "Quota_fct_par_mois",
                "Date_maintenance", "Date_installation", "Nombre_heures_fct_depuis_maintenance",
                "Nombre_heure_fct_depuis_installation", "Etat", "Besoin_maintenance",
                "Date_prochain_arret", "Compteur_d_arret_en_jours", "Protocole", "Demande_permission",
                "Nb_jours_max_reservation"
            ]
            required_cols = [col for col in expected_cols if col != "id"]  # "id" est optionnel à l'import
            missing_cols = [col for col in required_cols if col not in df_import.columns]
            extra_cols = [col for col in df_import.columns if col not in expected_cols]

            if "id" not in df_import.columns:
                st.warning("No 'id' column found — every row in this file will be added as new equipment.")
                df_import["id"] = None

            if missing_cols:
                st.error("This file is missing required column(s): " + ", ".join(missing_cols))
            else:
                if extra_cols:
                    st.warning("These columns aren't part of the equipment table and will be ignored: " + ", ".join(extra_cols))
                df_import = df_import[expected_cols]

                st.markdown(f"**Preview** — {len(df_import)} row(s) found")
                st.dataframe(df_import, use_container_width=True, hide_index=True)

                if st.button("✅ Apply import", key="apply_eq_import"):

                    def clean_import_value(col_name, value):
                        # Nettoie une valeur Excel avant écriture en base SQLite.
                        if pd.isna(value):
                            if col_name in ("Nombre_heures_fct_depuis_maintenance", "Nombre_heure_fct_depuis_installation"):
                                return 0
                            return None
                        if col_name in ("Date_maintenance", "Date_installation", "Date_prochain_arret"):
                            ts = pd.to_datetime(value, errors="coerce")
                            return ts.strftime("%Y-%m-%d") if pd.notna(ts) else None
                        if col_name == "Quota_fct_avant_maintenance":
                            try:
                                return int(value)
                            except (TypeError, ValueError):
                                return None
                        if isinstance(value, pd.Timestamp):
                            return value.strftime("%Y-%m-%d")
                        return value

                    conn_imp = sqlite3.connect("db/lab.db")
                    c_imp = conn_imp.cursor()
                    n_updated, n_inserted, n_skipped = 0, 0, 0

                    for _, row in df_import.iterrows():
                        eq_id = row["id"]
                        nom_value = row["Nom"]

                        if pd.isna(eq_id):
                            # Pas d'id -> nouvelle ligne, INSERT si le nom est renseigné.
                            if pd.isna(nom_value) or str(nom_value).strip() == "":
                                n_skipped += 1
                                continue
                            cols = [col for col in expected_cols if col != "id"]
                            col_names = ", ".join(f'"{col}"' for col in cols)
                            placeholders = ", ".join(["?"] * len(cols))
                            values = [clean_import_value(col, row[col]) for col in cols]
                            c_imp.execute(f'INSERT INTO equipements ({col_names}) VALUES ({placeholders})', values)
                            n_inserted += 1
                        else:
                            # Id présent -> UPDATE, seulement si cet id existe bien en base.
                            try:
                                eq_id_int = int(eq_id)
                            except (TypeError, ValueError):
                                n_skipped += 1
                                continue
                            c_imp.execute("SELECT 1 FROM equipements WHERE id = ?", (eq_id_int,))
                            if c_imp.fetchone() is None:
                                n_skipped += 1
                                continue
                            for col_name in expected_cols:
                                if col_name == "id":
                                    continue
                                value = clean_import_value(col_name, row[col_name])
                                c_imp.execute(f'UPDATE equipements SET "{col_name}" = ? WHERE id = ?', (value, eq_id_int))
                            n_updated += 1

                    conn_imp.commit()
                    conn_imp.close()

                    summary = f"Import complete — {n_updated} updated, {n_inserted} added"
                    if n_skipped:
                        summary += f", {n_skipped} skipped (unknown id or empty name)"
                    st.success(summary)
                    time.sleep(2)
                    st.rerun()

 def clean_value(value):
#------
# Nettoie une valeur avant insertion en base SQLite :
# Timestamp Pandas → chaîne format 'YYYY-MM-DD' (SQLite n'a pas de type DATE natif).
#------
    if pd.isna(value):
        if col in ("Nombre_heures_fct_depuis_maintenance", "Nombre_heure_fct_depuis_installation"):
            return 0
        return None
        

    # Timestamp -> string SQLite
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")

    return value
 def bytes_to_int(val):

    if isinstance(val, bytes):
        return int.from_bytes(val, byteorder='little')  # décoder le byte en int
    elif pd.notna(val):
        return float(val)
    else:
        return None

# Colonnes qui posent problème ou SQlite les enregistrés comme des bytes
 df_eq["Quota_fct_avant_maintenance"] = df_eq["Quota_fct_avant_maintenance"].apply(bytes_to_int)
 df_eq["Nombre_heures_fct_depuis_maintenance"] = df_eq["Nombre_heures_fct_depuis_maintenance"].apply(bytes_to_int)
 df_eq["Nb_jours_max_reservation"] = df_eq["Nb_jours_max_reservation"].apply(bytes_to_int)
# Mise à jour automatique du champ Besoin_maintenance selon le quota dépassé ou non.
 for i, j in df_eq.iterrows():
    eq_id = j["id"]
    verif = alerte_quota(j["Quota_fct_avant_maintenance"], j["Nombre_heures_fct_depuis_maintenance"])
    besoin = "Oui" if verif else "Non"
    df_eq.loc[i, "Besoin_maintenance"] = besoin
    c.execute("UPDATE equipements SET Besoin_maintenance=? WHERE id=?", (besoin, eq_id))
 conn.commit()
 conn.close()

 def make_badge(val):
#------
# Transforme la valeur textuelle "Oui"/"Non" en badge emoji lisible pour l'affichage dans le tableau des équipements.

#------
    if val == "Oui":
        return "🔴 Maintenance"
    elif val == "Non":
        return "🟢 OK"
    else:
        return val
# -- Tri explicite du tableau ------------------------------------------------
# Le tri natif par clic sur l'en-tête de colonne n'est pas disponible sur les
# st.data_editor en mode num_rows="dynamic" (nécessaire ici pour l'ajout de
# lignes). On propose donc un tri manuel équivalent, appliqué à df_eq
# lui-même (et non une copie) pour que les index restent alignés avec la
# comparaison "valeur modifiée ?" faite plus bas à la sauvegarde.
 sort_col1, sort_col2 = st.columns([2, 1])
 with sort_col1:
    sort_column = st.selectbox(
        "🔀 Sort by",
        df_eq.columns.drop("id"),
        index=list(df_eq.columns.drop("id")).index("Nom"),
        key="eq_sort_column"
    )
 with sort_col2:
    sort_order = st.selectbox(
        "Order",
        ["Ascending", "Descending"],
        key="eq_sort_order"
    )
 df_eq = df_eq.sort_values(
    by=sort_column,
    ascending=(sort_order == "Ascending"),
    na_position="last",
    kind="stable"
 ).reset_index(drop=True)

 # Sauvegarde dans le session state pour conserver l'état entre les interactions Streamlit. et ne pas modifier le tableau d'origine
 st.session_state.df = df_eq.copy()
 st.session_state.df["Besoin_maintenance"] = st.session_state.df["Besoin_maintenance"].apply(make_badge)
  
# Conversion des colonnes de dates en datetime pour l'affichage correct dans DateColumn.
 date_columns = [
    "Date_maintenance",
    "Date_installation",
    "Date_prochain_arret"
]

 for col in date_columns:

    st.session_state.df[col] = pd.to_datetime(
        st.session_state.df[col],
        errors="coerce"
    )


 st.caption(f"{len(df_eq)} equipement(s) affiché(s)")   
 
# Tableau éditable avec ajout de lignes possible (num_rows="dynamic").
# La colonne "id" est masquée (None) car elle est technique et ne doit pas être éditée.
 edited_df = st.data_editor(
 st.session_state.df,
    num_rows="dynamic",
    key="equipement_editor",
    hide_index=True,
    column_config={"id":None, "Etat": st.column_config.SelectboxColumn(
            "Etat",
            options=["Marche", "Panne"],
           
        ), "Date_maintenance": st.column_config.DateColumn(
            "Date_maintenance",
            format="DD/MM/YYYY",
            default=None
        ),
        "Date_installation": st.column_config.DateColumn(
            "Date_installation",
            format="DD/MM/YYYY",
            default=None
        ),
        "Date_prochain_arret": st.column_config.DateColumn(
            "Date_prochain_arret",
            format="DD/MM/YYYY",
            default=None
        ),
        "Demande_permission":st.column_config.SelectboxColumn(
            "Demande_permission",
            options=["Oui", "Non"],
            default="Non"

        ),
        "Nb_jours_max_reservation": st.column_config.NumberColumn(
            "Nb jours max reservation",
            help="Nombre de jours consecutifs maximum autorise pour une reservation de cet equipement (vide = pas de limite)",
            min_value=1,
            step=1,
            default=None
        ),
},
   
)      

#  Sauvegarde des modifications (UPDATE ou INSERT) 
 if st.button("Valider",key="Changement_eq"):

    conn = sqlite3.connect("db/lab.db")
    c = conn.cursor()
   

    for i, row in edited_df.iterrows():
        eq_id = row["id"]
     
        if pd.notna(eq_id): # Ligne existante (id connu) → UPDATE colonne par colonne si la valeur a changé.
          for col in edited_df.columns:
             if col != "id":   
                value = edited_df.loc[i, col]
                if    pd.isna(value):
                   if col in ("Nombre_heures_fct_depuis_maintenance", "Nombre_heure_fct_depuis_installation"):
                            value = 0
                   else :        
                            value = None                  
                if value != df_eq.loc[i, col]:
                    if col=="Quota_fct_avant_maintenance" or col=="Nb_jours_max_reservation":
                        if value is not None:
                         value=int(value)
                        
                    if (col=="Date_maintenance" ) or(col=="Date_installation") or (col=="Date_prochain_arret") :
                        value=clean_value(value) 
                    if col== "Date_maintenance":
                        # Cas spécial : quand la date de maintenance change, on recalcule automatiquement les heures de fonctionnement depuis cette nouvelle date
                        
                      c.execute(
                                              """
                                              SELECT start_time, end_time
                                              FROM reservations
                                              WHERE equipement_id = ?
                                              """,
                                                (eq_id,)
                                                                )
                      all_resa = c.fetchall()
                      date_str=value
                      df_all = pd.DataFrame(all_resa, columns=["Début", "Fin"])
                      temps_fct_maintenance = calcul_temps_fonctionnement(df_all,date_str)
                      st.session_state.df.loc[i, "Nombre_heures_fct_depuis_maintenance"] = temps_fct_maintenance
                      c.execute(
                                                 """
                                                 UPDATE equipements
                                                 SET Date_maintenance=?,Nombre_heures_fct_depuis_maintenance=?
                                                 WHERE id = ?
                                                 """,
                                                    (value,temps_fct_maintenance, eq_id))
                      
                    else: 
                     c.execute(
                        f'UPDATE equipements SET "{col}" = ? WHERE id = ?',
                        (value, eq_id)            )
                   
       
        else: # Nouvelle ligne (id = NaN) → INSERT uniquement si le champ Nom est renseigné.
                 cols = [col for col in edited_df.columns if col != "id" ] 
                 # Vérification que Nom n'est pas vide
                 nom_value = edited_df.loc[i, "Nom"]
                 if pd.isna(nom_value) or str(nom_value).strip() == "":
                   continue  # ← ignore les lignes vides  
                 col_names = ", ".join([f'"{col}"' for col in cols])
                 placeholders = ", ".join(["?"] * len(cols))
                 values = [clean_value(edited_df.loc[i, col])for col in cols]
                 c.execute(f'INSERT INTO equipements ({col_names}) VALUES ({placeholders})',
                 values)
    conn.commit()
    conn.close()         
    
                    
    
    st.success("Modifications enregistrées")
    time.sleep(2)
    st.rerun()
# ── Détection et suppression des équipements retirés du tableau ──────
# Les lignes supprimées dans st.data_editor disparaissent du DataFrame édité.
# On les détecte en comparant les sets ( liste sans duplicat) d'ids avant (df_intial) et après édition (edited_df).
 conn = sqlite3.connect("db/lab.db")
 c = conn.cursor()
 df_initial = st.session_state.df.copy()   
 ids_avant = set(df_initial["id"].dropna())
 ids_apres = set(edited_df["id"].dropna())
 ids_supprimes = ids_avant - ids_apres
 for id_del in ids_supprimes:
   c.execute("DELETE FROM equipements WHERE id = ?", (int(id_del),))
 conn.commit()
 conn.close()
 

 

 # --Rechargement et affichage des alertes de quota --
 conn = sqlite3.connect("db/lab.db")
 c = conn.cursor()

 eq = c.execute("SELECT * FROM equipements").fetchall()
  
 df_eq = pd.DataFrame(eq, columns=df_eq.columns)
 df_eq["Quota_fct_avant_maintenance"] = df_eq["Quota_fct_avant_maintenance"].apply(bytes_to_int)
 df_eq["Nombre_heures_fct_depuis_maintenance"] = df_eq["Nombre_heures_fct_depuis_maintenance"].apply(bytes_to_int)

 for i, j in df_eq.iterrows():
    eq_id = j["id"]
# Initialisation de l'état d'affichage de l'alerte pour cet équipement.
    if f"select_{i}" not in st.session_state:
        st.session_state[f"select_{i}"] = True
  # Mise à jour du champ Besoin_maintenance en base.
    verif = alerte_quota(j["Quota_fct_avant_maintenance"], j["Nombre_heures_fct_depuis_maintenance"])

    if verif: 
        c.execute("""UPDATE equipements SET Besoin_maintenance=? WHERE id=?""", ("Oui", eq_id))
    else:
        c.execute("""UPDATE equipements SET Besoin_maintenance=? WHERE id=?""", ("Non", eq_id))
   
        
 # Affichage de l'alerte si quota dépassé et si elle n'a pas été masquée ( lorsqu'il clique sur OK) par l'utilisateur.
    if verif and st.session_state[f"select_{i}"]: 
        col1, col2 = st.columns([8, 1])
        with col1: 
            st.warning(f"le quota pour la machine {j['Nom']} est dépassé, une maintenance est à envisager")
        with col2: 
            def ok_callback(idx=i):
                # Callback qui masque l'alerte quand l'utilisateur clique "OK".
                st.session_state[f"select_{idx}"] = False

            st.button("OK", key=f"ok_{i}", on_click=ok_callback)


 conn.commit()
 conn.close()
 # -----------------------------------
 # GESTION DES PROJETS
# ------------------------------------
 st.markdown("<br><br>", unsafe_allow_html=True)     
 st.subheader(" 📁 Gestion des projets") 
 st.markdown("<br>", unsafe_allow_html=True)
 
# Récupération des donées
 conn = sqlite3.connect("db/lab.db")
 c = conn.cursor()
 c.execute("SELECT id, Name_project, Name_Responsable FROM project ")
 project=c.fetchall()
 df_project=pd.DataFrame(project,columns=["id","Name_project","Name_Responsable"])
 
# Sauvegarde de l'état initial pour comparer avec les modifications et détecter les suppressions.
 st.session_state.df_project=df_project.copy()
# Tableau éditable avec ajout de lignes  possible (num_rows="dynamic").
 edited_df_project = st.data_editor(
    st.session_state.df_project,
    num_rows="dynamic",
    key="project_editor",
    column_config={"id":None} # Masquage de la colonne id technique.
)
 # Enregistrement des modifications
 if st.button("Valider",key="changement projet"):

    conn = sqlite3.connect("db/lab.db")
    c = conn.cursor()

    for i, row in edited_df_project.iterrows():
        pr_id = row["id"]
     
        if pd.notna(pr_id): # Ligne existante → UPDATE des colonnes modifiées.
          for col in edited_df_project.columns:
             if col != "id":   
                value = edited_df_project.loc[i, col]
                if    pd.isna(value):
                        value = None                  
                if value != df_project.loc[i, col]:
                    
                     c.execute(
                        f'UPDATE project SET "{col}" = ? WHERE id = ?',
                        (value, pr_id)            )
                   
       
        else: # Nouvelle ligne → INSERT.
                 cols = [col for col in edited_df_project.columns if col != "id" ]   
                 col_names = ", ".join([f'"{col}"' for col in cols])
                 placeholders = ", ".join(["?"] * len(cols))
                 values = [edited_df_project.loc[i, col] for col in cols]

                 c.execute(f'INSERT INTO project ({col_names}) VALUES ({placeholders})',
                 values)
                

                    
        conn.commit()
    st.rerun()
   
# Détection et suppression des projets retirés du tableau.
 conn = sqlite3.connect("db/lab.db")
 c = conn.cursor()
 df_project_initial = st.session_state.df_project.copy()
 
 ids_avant = set(df_project_initial["id"].dropna())
 
 ids_apres = set(edited_df_project["id"].dropna())
 ids_supprimes = ids_avant - ids_apres
 for id_del in ids_supprimes:
   c.execute("DELETE FROM project WHERE id = ?", (int(id_del),))
 conn.commit()
 conn.close()

 #---------------------------------
  # COMMUNICATION BOARD
 # ----------------------------------
 st.markdown("<br><br>", unsafe_allow_html=True)
 st.subheader(" 📢 Communication board")
 st.markdown("<br>", unsafe_allow_html=True)
# Récupération des donées
 conn = sqlite3.connect("db/lab.db")
 c = conn.cursor()

 c.execute("SELECT id, Comment, Name_admin, Bon, Mauvais, Warning, Info, Date_publication, Date_of_delete FROM admin_comment")
 comments = c.fetchall()

 df_comments = pd.DataFrame(comments, columns=["id", "Comment", "Name_admin", "Bon", "Mauvais", "Warning", "Info", "Date_publication", "Date_of_delete"])


 st.session_state.df_edit=df_comments.copy()# Sauvegarde dans le session state pour conserver l'état entre les interactions Streamlit. et ne pas modifier le tableau d'origine
 # Conversion explicite des états en bool pour que st.data_editor affiche correctement les checkboxes.
 st.session_state.df_edit["Bon"]= st.session_state.df_edit["Bon"].astype(bool)
 st.session_state.df_edit["Mauvais"]          = st.session_state.df_edit["Mauvais"].astype(bool)
 st.session_state.df_edit["Warning"]          = st.session_state.df_edit["Warning"].astype(bool)
 st.session_state.df_edit["Info"]             = st.session_state.df_edit["Info"].astype(bool)
  # Conversion des dates en objets date Python pour l'affichage dans DateColumn.
 st.session_state.df_edit["Date_publication"] = pd.to_datetime(st.session_state.df_edit["Date_publication"]).dt.date
 st.session_state.df_edit["Date_of_delete"]   = pd.to_datetime(st.session_state.df_edit["Date_of_delete"]).dt.date
 # Pré-remplissage du champ Name_admin avec le nom de l'admin connecté si la valeur est vide.
 default_name = st.session_state.get("admin_name", "")
 st.session_state.df_edit["Name_admin"] = st.session_state.df_edit["Name_admin"].replace("", default_name).fillna(default_name)
 # Tableau éditable des commentaires 
 edited_df = st.data_editor(
    st.session_state.df_edit,
    column_config={"id":None,
         
        "Comment":          st.column_config.TextColumn("Comment"),
        "Name_admin":       st.column_config.TextColumn("Name"),
        "Bon":              st.column_config.CheckboxColumn("😊 Good"),
        "Mauvais":          st.column_config.CheckboxColumn("😞 Bad"),
        "Warning":          st.column_config.CheckboxColumn("⚠️ Warning"),
        "Info":             st.column_config.CheckboxColumn("ℹ️ Info"),
        "Date_publication": st.column_config.DateColumn("Start", default=date.today()),
        "Date_of_delete":   st.column_config.DateColumn("End",   default=date.today() + timedelta(days=7)),
        
    },
    use_container_width=True,
    hide_index=True,
    num_rows="dynamic", 
    key="comments_editor",
)
 # Enregistrement des modifications 
 if st.button("Valider", key="save_comments"):
         conn = sqlite3.connect("db/lab.db")
         c = conn.cursor()
         has_error=False
         for _, row in edited_df.iterrows():
         # Validation 1 : le commentaire ne doit pas être vide.
         # On vérifie aussi les représentations textuelles de null générées par Pandas.
               if not str(row["Comment"]).strip() or str(row["Comment"]) in ["None", "nan", "NaN"]:
                        st.warning(f"Attention Commentaire vide ignoré")
                        has_error=True
                        break
               # Validation 2 : au moins un type de message doit être sélectionné.
               if not any([row["Bon"], row["Mauvais"], row["Warning"], row["Info"]]):
                          st.warning(f"Sélectionnez un type pour le commentaire '{row['Comment'][:30]}...'")
                          has_error=True
                          break
         # Validation 3 : un seul type autorisé par commentaire (règle métier).
         # sum() sur une liste de booléens compte les True.
               if sum([bool(row["Bon"]), bool(row["Mauvais"]), bool(row["Warning"]), bool(row["Info"])]) > 1:
                       st.warning(f"Un seul type autorisé pour le commentaire '{str(row['Comment'])[:30]}'")
                       has_error=True
                       break
               
               
         # Normalisation du nom admin (utilise le nom connecté si le champ est vide).
               name_to_save = str(row["Name_admin"]).strip() if pd.notna(row["Name_admin"]) and str(row["Name_admin"]).strip() else default_name
        
        
     # Normalisation des dates : le type retourné par st.data_editor peut varier
     # (objet date, datetime ou chaîne ISO). On garantit un objet date Python.
               date_pub = row["Date_publication"] if isinstance(row["Date_publication"], date) else date.fromisoformat(str(row["Date_publication"]))
               date_del = row["Date_of_delete"]   if isinstance(row["Date_of_delete"],   date) else date.fromisoformat(str(row["Date_of_delete"]))  
               if not has_error:  # Si aucune erreur n'a été détectée : Les 3 conditons sont validés
                  if pd.isna(row["id"]) or row["id"] == "" or row["id"] is None:  # ✅ nouvelle ligne → INSERT
                           
                           c.execute("""
                    INSERT INTO admin_comment (Comment, Name_admin, Bon, Mauvais, Warning, Info, Date_publication, Date_of_delete)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(row["Comment"]).strip(),
                    name_to_save,
                    1 if row["Bon"]     else 0,
                    1 if row["Mauvais"] else 0,
                    1 if row["Warning"] else 0,
                    1 if row["Info"]    else 0,
                    date_pub.isoformat(),
                    date_del.isoformat(),
                ))
                  else:  # ✅ ligne existante → UPDATE
                          c.execute("""
                    UPDATE admin_comment
                    SET Comment=?, Name_admin=?, Bon=?, Mauvais=?, Warning=?, Info=?, Date_publication=?, Date_of_delete=?
                    WHERE id=?
                """, (
                    str(row["Comment"]).strip(),
                    name_to_save,
                    1 if row["Bon"]     else 0,
                    1 if row["Mauvais"] else 0,
                    1 if row["Warning"] else 0,
                    1 if row["Info"]    else 0,
                    date_pub.isoformat(),
                    date_del.isoformat(),
                    int(row["id"]),
                ))
         # Si aucune erreur n'a été détectée : enregistrés validés la base et afficher le message de validation
         if not has_error:
           conn.commit()
           conn.close()     
           st.success("Modifications enregistrées")
           time.sleep(2)
           st.rerun()


# Suppression des commentaires retirés du tableau (même logique que pour les équipements et les projets).
 conn = sqlite3.connect("db/lab.db")
 c = conn.cursor()
 df_comments_initial = st.session_state.df_edit.copy()
 
 ids_avant = set(df_comments_initial["id"].dropna())
 
 ids_apres = set(edited_df["id"].dropna())
 ids_supprimes = ids_avant - ids_apres
 for id_del in ids_supprimes:
   c.execute("DELETE FROM admin_comment WHERE id = ?", (int(id_del),))
 conn.commit()
 conn.close()

    
# --------------------------------
# STATISTIQUES DE RÉSERVATIONS
# -------------------------------- 
  
 st.markdown("<br><br>", unsafe_allow_html=True)  
 st.subheader(" 📊 Satistiques des réservations")
 st.markdown("<br>", unsafe_allow_html=True) 

 conn = sqlite3.connect("db/lab.db")
 c = conn.cursor()
 
# Récupération des équipements
 c.execute("SELECT id, Nom, Numero_salle, Nom_salle FROM equipements")
 equipements = c.fetchall()
 conn.close()


 if equipements:
# Construction des filtres

  salles = list({(e[2], e[3]) for e in equipements})  # # Construction de la liste des salles.(Numero_salle, Nom_salle)
  options_salles = [""] + [f"{num}-{nom}" for num, nom in salles] # Format affiché dans le selectbox
  col1, col2 = st.columns(2)
  with col1:
    choice = st.selectbox(" 🚪 Sélectionner une salle", options_salles, index=0, key="room_select")  # Select de la salle
  
# Selection des equipements
  if choice: # Si il y un choix de la salle 
    num_salle_sel, nom_salle_sel = choice.split("-") # Séparation du numéro et du nom de salle depuis le format "num-nom".
    equipements_dispo = [e[1] for e in equipements if e[2] == num_salle_sel]
    with col2:
      equipement_nom = st.selectbox(
        f" 🔬 List of equipment in room {nom_salle_sel}", 
        equipements_dispo, 
        key="equipement_select"
    ) # Filtrer les équipements de cette salle
  else:
     with col2:  
              equipement_nom = st.selectbox(
        " 🔬 Sélectionner un équipement", 
        [e[1] for e in equipements], 
        key="equip_select"
    ) # Si aucune salle choisie → afficher tous les équipements

# Selection de la période  
  col3,col4=st.columns(2)
  current_year=datetime.now().year
  with col3:     
      date_début = st.date_input(
    " 📅 Date de début", 
    min_value=date(current_year-1,1,1), 
    max_value=date(current_year+1,12,31), 
    value=date(current_year,1,1)
)
  with col4:    
    date_fin = st.date_input(
    " 📅 Date de fin", 
    min_value=date(current_year-1,1,1), 
    max_value=date(current_year+1,12,31), 
    value= date(current_year,1,1)
)
  st.markdown("<br><br>", unsafe_allow_html=True)    
  dates = pd.date_range(start=date_début, end=date_fin, freq="D") # Génère toutes les dates entre la date de début et la date de fin : ( Fréq=D: Une date par jour)

# Génération d'une grille calendaire complète pour la période (une ligne par jour).
  df_dates = pd.DataFrame({"date": dates}) # Transformation de la liste de dates en DataFrame

  df_dates["année"] = df_dates["date"].dt.year # Extraction de l'année depuis la colonne date et création d'une colonne année avec les années existantes
  df_dates["mois"] = df_dates["date"].dt.month  # Extraction du mois depuis la colonne date et création d'une colonne mois avec les mois existantes
# Résumé des bornes min/max de date par année (pour les titres des graphiques).
  resume = df_dates.groupby("année").agg( # Grouper le tableau par année
    date_debut=("date", "min"), # Pour chaque année determination de la date minimale 
    date_fin=("date", "max"),# Pour chaque année determination de la date maximale
).reset_index()  
  
 


# Récupérer l'id de l'équipement sélectionné
  equipement_id = [e[0] for e in equipements if e[1] == equipement_nom][0] # Récupérer l'id de l'équipement sélectionné

 # Récupération de toutes les réservations pour cet équipement sélectionné depuis la liste.
  conn = sqlite3.connect("db/lab.db")
  c = conn.cursor()
  c.execute("SELECT user, user_id, start_time, end_time,project FROM reservations WHERE equipement_id = ?", 
    (equipement_id,)) # Récupération des réservations pour l'équipement choisi
  reservations = c.fetchall()
  conn.close()
  df_resa = pd.DataFrame(reservations, columns=["Nom", "id","Début", "Fin","projet"])

# Conversion en datetime
  df_resa["Début"] = pd.to_datetime(df_resa["Début"])
  df_resa["Fin"] = pd.to_datetime(df_resa["Fin"])




# Filtrage des réservations sur la période choisie.

  df_resa_courante = df_resa[(df_resa["Début"].dt.date >= date_début)  & (df_resa["Fin"].dt.date<=date_fin)] # Filtrer pour ne garder que les réservations de la période choisie
  
  
  # Calcul de la durée de chaque réservation en heures.
  for i,row in df_resa_courante.iterrows(): # calcul du nombre d'heures par réservation
     heures_fct=(row["Fin"]-row["Début"]).total_seconds() / 3600
     df_resa_courante.loc[i,"nombre heure"]=heures_fct
  
      
# -- Graphiques et tableaux --


  if  df_resa_courante.empty:
    st.info("Aucune donnée enregistrée pour la période sélectionnée.") # Affichage si pas de réservation pour la période
  else: 
      
      df_resa_courante["projet"] = (df_resa_courante["projet"] .fillna("others").replace("", "others"))  # Remplacer les projets vides
      df_resa_courante["Nom"] = (df_resa_courante["Nom"] .str.strip().str.upper())
      
      df_heures_fct_user = df_resa_courante.groupby(["Nom"])["nombre heure"].sum().reset_index().rename(columns={"Nom": "Nom", "nombre heure": "Nombres totale heures reservées"}) # Calcul du total des heures  reservées par utilisateur
     
      total_heures = df_heures_fct_user["Nombres totale heures reservées"].sum()# Calcul du total d'heures  de reservation pour l'équipement 
      df_heures_fct_projet = df_resa_courante.groupby("projet")["nombre heure"].sum().reset_index().rename(columns={"projet": "Nom du projet","nombre heure": "Nombres totale heures reservées"}) # Total par projet
     
      # Calcul des pourcentages
      df_heures_fct_projet["Pourcentage"] = (
      df_heures_fct_projet["Nombres totale heures reservées" ] / total_heures * 100)
      df_heures_fct_user["Pourcentage"] = (
      df_heures_fct_user["Nombres totale heures reservées"] / total_heures * 100)

      # Tri décroissant
      df_heures_fct_user = df_heures_fct_user.sort_values(by="Nombres totale heures reservées", ascending=False)
      df_heures_fct_projet = df_heures_fct_projet.sort_values(by="Nombres totale heures reservées", ascending=False)

      # GRAPHIQUE + Table  PAR UTILISATEUR
      st.write("*Répartition des réservations pour la période choisie par personne*")
      
      col1, col2 = st.columns([2, 1]) 
      with col1:
            fig = px.pie(
            df_heures_fct_user,
            names="Nom",
            values="Pourcentage",
            title="",  
            color_discrete_sequence=px.colors.qualitative.Pastel,
            hover_data=["Pourcentage"])
            fig.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True)
      with col2:
             st.dataframe(df_heures_fct_user[["Nom", "Nombres totale heures reservées", "Pourcentage"]], use_container_width=True,hide_index=True)

      # GRAPHIQUE PAR UTILISATEUR   
      st.markdown("<br><br>", unsafe_allow_html=True)      
      st.write("*Répartition des réservations pour la période choisie par projet*")

      col1, col2 = st.columns([2, 1]) 
      with col1:
            fig = px.pie(
            df_heures_fct_projet,
            names="Nom du projet",
            values="Pourcentage",
            title="",  
            color_discrete_sequence=px.colors.qualitative.Set3,
            hover_data=["Pourcentage"])
            fig.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True)
      with col2:
             st.dataframe(df_heures_fct_projet[["Nom du projet", "Nombres totale heures reservées", "Pourcentage"]], use_container_width=True,hide_index=True) 

      st.markdown("<br><br>", unsafe_allow_html=True)     
      st.write("*Pourcentage de fonctionnement par mois par rapport au quota*")
      st.markdown("<br><br>", unsafe_allow_html=True)   
      q= calcul_tempsfctparmois(df_resa_courante)
      
      # Création d’une table complète : toutes les combinaisons (année × mois)
     # Nécessaire pour que les mois sans réservation apparaissent à 0 dans le graphique.
      all_index = pd.MultiIndex.from_product(
       [q["année"].unique(), range(1, 13)], # Récupère toutes les années présentes dans le DataFrame + crée tout les mois pour cette année (2027:1,2027:2....)
      names=["année", "mois"] #appelle les deux niveaux ( année et mois )
      ).to_frame(index=False)    # conversion en DataFrame classique (colonnes)
      
    # Jointure gauche : les mois sans réservation reçoivent la valeur 0.
      q = all_index.merge(q,  # données de reservation
                          on=["année", "mois"], # clé de jointure (identifiant unique)
                          how="left" # on garde toutes les lignes de all_index ( touts les mois de l'année meme ceux où il n'y a pas de reservation)
                          ).fillna(0) # remplace les valeurs manquantes (mois ou pas de reservation) (NaN) par 0
      

      q["mois_nom"] = q["mois"].map(lambda x: calendar.month_name[x]) # Conversion du numéro de mois en nom de mois dans une nouvelle colonne nom_mois (1 → January, etc.) dans une nouvelle colonne (mois_nom)
    
      conn = sqlite3.connect("db/lab.db")
      c= conn.cursor()
      c.execute(
    "SELECT Quota_fct_par_mois FROM equipements WHERE id = ?", 
    (equipement_id,))
      quota=c.fetchall()
      conn.close()
      if quota[0][0]!=None:
          # Calcul du taux de fonctionnement en % par rapport au quota mensuel.
          quota = int(quota[0][0])
          q["percentage"] = (q["duree"] / quota) * 100
          # Un graphique par année présente dans la période sélectionnée.
          for e in set(q["année"])  : 
            data=q[q["année"]==e] # Récupére les données par année 
            df_e = resume.loc[resume["année"] == e] # Récupére dans le tableau resume (voir plus haut) la ligne pour l'année correspondante e 
            date_min = df_e["date_debut"].min().strftime('%d/%m/%Y') # Récupére la date minimale pour l'année correspondante (e) dans le tableau resume
            date_max = df_e["date_fin"].max().strftime('%d/%m/%Y') # Récupére la date maximale pour l'année correspondante (e) dans le tableau resume
            fig = px.bar(data, x="mois_nom", y="percentage", text="percentage",              color_discrete_sequence=["#1f77b4"],  
)
            fig.update_traces(
    texttemplate='%{text:.1f}%', 
    textposition='outside',
    showlegend=False
)

# Style axes et fond
            fig.update_layout(plot_bgcolor='white', paper_bgcolor='white',
         # fond du graphique paper_bgcolor='white',         # fond total xaxis=dict(title_text="month",
       xaxis=dict(
        title_text="month",showline=True,
        linecolor='gray',
        linewidth=1.5,
        showgrid=False,
        title_font=dict(color='black', size=14),
        tickfont=dict(color='black', size=12)
    ),
            yaxis=dict(
        range=[0, 100],             # axe Y jusqu'à 100 %
        showline=True,
        linecolor='gray',
        linewidth=1.5,
        showgrid=False,
        title_font=dict(color='black', size=14),
        tickfont=dict(color='black', size=12)
    ),
            title=dict(
          text=(f"Taux de fonctionnement mensuel par rapport au quota pour l'année {e} pour la période du {date_min} au {date_max} "),
        font=dict(size=14, color='black'),
        x=0))
            st.markdown("<br>", unsafe_allow_html=True)  
            st.plotly_chart(fig, use_container_width=True)
      else:
          st.warning("Veuillez renseigner un quota de fonctionnement par mois")  


 # ------------------------------------------
 # HISTORIQUE DES RÉSERVATIONS ET ANNULATIONS
 # ------------------------------------------
  st.markdown("<br><br>", unsafe_allow_html=True)      
  st.subheader("📝 Historique des réservations et annulations")
  st.markdown("<br>", unsafe_allow_html=True)

# Récupération des donées dans le tableau historique de la base
  conn = sqlite3.connect("db/lab.db")
  c = conn.cursor()
  c.execute("SELECT history,date FROM history ")
  hy=c.fetchall() 
  conn.commit()
  conn.close()
  hys = pd.DataFrame(hy, columns=["tâche", "date"])
  # Filtre par mot clé et par date 
  if not hys.empty:
    col_h1, col_h2 = st.columns(2)
    with col_h1:
        search_eq = st.text_input("🔍 Rechercher un mot clé", "")
    with col_h2:
        search_date = st.text_input("🔍 Rechercher une date", "")
  # Change les valeurs de la colonne Date en datetime
    hys["date"] = hys["date"].apply(pd.to_datetime)
    
 # Limite l'affichage aux 90 derniers jours pour faciliter l'affichage et la fluidité du tableau
    cutoff = datetime.now() - timedelta(days=90)
    hys_f = hys[hys["date"] > cutoff].sort_values("date", ascending=False).copy()
  
    if search_eq: # Filtrage par mot clé dans le texte de la tâche 
      
      hys_f = hys_f[
        hys_f["tâche"].str.contains(search_eq, case=False, na=False)
    ]

    if search_date: # Filtrage par date
      
       hys_f = hys_f[
        hys_f["date"].astype(str).str.contains(search_date, case=False, na=False)
    ]
            
 # Affichage du tableau filtré ou Non
    st.dataframe(hys_f,hide_index=True)
# --Suppression de toutes les entrées de l'historique (action irréversible)--. 
    if st.button("supprimer l'historique",key="delete_history"):
      conn = sqlite3.connect("db/lab.db")
      c = conn.cursor()
      c.execute("DELETE FROM history;")
      c.execute("DELETE FROM sqlite_sequence WHERE name='history';") # Réinitialisation de l'auto-incrément pour que les prochains ids repartent de 1.
      conn.commit()
      conn.close()
      st.success("✅ Tout l'hstorique a été supprimé.")
      time.sleep(2)
      st.rerun()
  else:
      st.info("Historique vide")    




      
  

 


           
            
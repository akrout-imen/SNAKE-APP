import streamlit as st
import sqlite3
import base64
import streamlit.components.v1 as components
from streamlit_modal import Modal
from streamlit_calendar import calendar
from db.database import init_db
from email_utils import notifier_admins_nouveau_user, NOT_CONFIGURED
from email_validator import validate_email, EmailNotValidError
import time
from datetime import datetime, timedelta,date
import pandas as pd
import hashlib
import shutil
import os 

# =============================================================================
# INITIALISATION DU SESSION STATE
# Ces variables persistent entre les rechargements de la page Streamlit

# =============================================================================

if "user_email" not in st.session_state: # Email saisi par l'utilisateur
    st.session_state.user_email = None

if "pending_email" not in st.session_state:
    st.session_state.pending_email = None # Email non reconnu, en attente d'inscription
if "user_conn" not in st.session_state:
      st.session_state.user_conn = False # True si l'utilisateur est connecté

if "user_idd" not in st.session_state:
      st.session_state.user_idd = None # ID de l'utilisateur connecté (clé primaire en BDD)
if "user_name" not in st.session_state:
      st.session_state.user_name = None # Nom affiché de l'utilisateur connecté
if "admin_verified" not in st.session_state:
    st.session_state.admin_verified = False        # True seulement apres validation du mot de passe admin

if "awaiting_admin_password" not in st.session_state:
    st.session_state.awaiting_admin_password = False  # Pilote l'affichage du formulaire mot de passe (persiste entre les reruns)

if "email_to_verify" not in st.session_state:
    st.session_state.email_to_verify = None  
               


# =============================================================================
# CONFIGURATION DE LA PAGE STREAMLIT
# =============================================================================

st.set_page_config(
    page_title="SNAKE",
    page_icon="🐍",
    layout="wide"
)
# =============================================================================
# CSS PERSONNALISÉ
# Masque les éléments par défaut de Streamlit (menu, header, footer, nav),
# et fixe la largeur de la sidebar à 380 px.
# =============================================================================

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

# =============================================================================
# LOGO DANS LA SIDEBAR
# Lit le logo au format PNG, l'encode en base64 et l'injecte en HTML.
# =============================================================================
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
""", unsafe_allow_html=True) # texte "Powered by IAK" fixé en bas de la sidebar

st.sidebar.divider()

# =============================================================================
# NAVIGATION DANS LA SIDEBAR
# Liens vers les différentes pages de l'application.
# ===========================================================================
st.sidebar.page_link("app.py",                              label="🏠 Home")
st.sidebar.page_link("pages/1_Reservation-Annulation.py",   label="📅 Reservation / Cancellation")
st.sidebar.page_link("pages/2_Category_View.py",            label="🗂️ Category view")
st.sidebar.page_link("pages/3_Admin.py",                    label="⚙️ Admin")






# =============================================================================
# FONCTIONS UTILITAIRES
# =============================================================================

def check_user(email):
 # ----------------------------- 
    # Vérifie si un email existe dans la table 'users'.

    #Paramètre
   # ---------
    #email : str

    #Retourne
    #--------
    #tuple | None  — la ligne de l'utilisateur, ou None s'il n'existe pas.
    #Colonne : (id, nom, email, birthday, validation, intiales) : si existe
  # -----------------------------   
   
    conn = sqlite3.connect("db/lab.db")
    c = conn.cursor()

    c.execute("SELECT * FROM users WHERE email=?", (email,))
    user = c.fetchone()

    conn.close()

    return user




def style_equipment_table(df):
    # ----------------------------- 
    # Génère et affiche un tableau HTML stylisé pour les équipements,
    # avec des badges colorés selon le statut (Operational / Out of order / Inconnu)
    #et des liens cliquables pour les protocoles.
  # -----------------------------   

    def style_status(val):
     # Retourne un badge HTML coloré selon la valeur du statut
        if "Operational" in str(val):
            return f"<span style='background:#dcfce7; color:#16a34a; font-weight:600; padding:3px 10px; border-radius:20px; font-size:13px;'>{val}</span>"
        elif "Out of order" in str(val):
            return f"<span style='background:#fee2e2; color:#dc2626; font-weight:600; padding:3px 10px; border-radius:20px; font-size:13px;'>{val}</span>"
        else:
            return f"<span style='background:#f3f4f6; color:#6b7280; font-weight:600; padding:3px 10px; border-radius:20px; font-size:13px;'>{val}</span>"
    # Construction de l'en-tête du tableau (une colonne <th> par colonne du DataFrame)
    headers = "".join([f"<th>{col}</th>" for col in df.columns]) 
    # Construction des lignes du tableau
    rows = ""
    for i, row in df.iterrows():
        cells = ""
        for col in df.columns:
            val = row[col]
            if col == "Equipment status":
                cells += f"<td>{style_status(val)}</td>"
            elif col == "Protocol" and str(val).startswith("http"):
               cells += f"<td><a href='{val}' target='_blank' style='color:#6366f1; text-decoration:none; font-weight:500;'>🔗 View</a></td>"
            else:
                cells += f"<td>{val}</td>"
        rows += f"<tr>{cells}</tr>"
    
    # Assemblage final : CSS du tableau + structure HTML complète
    html = f"""
    <style>
    .modern-table {{
        width: 100%;
        border-collapse: separate;
        border-spacing: 0;
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 4px 16px rgba(0,0,0,0.08);
        font-family: 'Segoe UI', sans-serif;
    }}
    .modern-table thead tr {{
        background: linear-gradient(90deg, #4f46e5, #6366f1);
    }}
    .modern-table thead th {{
        color: white !important;
        font-weight: 700;
        font-size: 13px;
        text-align: center;
        padding: 14px 12px;
        letter-spacing: 0.5px;
        text-transform: uppercase;
    }}
    .modern-table tbody tr {{
        transition: background 0.2s;
    }}
    .modern-table tbody tr:nth-child(even) {{
        background-color: #f8f9ff;
    }}
    .modern-table tbody tr:nth-child(odd) {{
        background-color: #ffffff;
    }}
    .modern-table tbody tr:hover {{
        background-color: #eef0fb !important;
    }}
    .modern-table tbody td {{
        text-align: center;
        font-size: 14px;
        padding: 12px 10px;
        color: #374151;
        border-bottom: 1px solid #f0f0f0;
    }}
    </style>
    <div style='overflow-x:auto; margin-top:10px;'>
        <table class='modern-table'>
            <thead><tr>{headers}</tr></thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)
def backup_db_daily():
# -----------------------------
    # Crée une copie de sauvegarde quotidienne de la base de données.
    #
    # Logique :
    #   1. Crée le dossier de backups s'il n'existe pas encore.
    #   2. Génère un nom de fichier basé sur la date du jour.
    #   3. Si aucun backup n'existe pour aujourd'hui, copie la base actuelle.
    #   4. Supprime les backups les plus anciens si plus de 30 sont stockés
    #      (conserve un historique glissant de 30 jours).
# -----------------------------    
    src = "db/lab.db"  # Chemin vers la base de données actuelle
    backup_dir = "db/backups" # Dossier de destination des sauvegardes
    os.makedirs(backup_dir, exist_ok=True)  #Création du dossier s'il n'existe pas (sans erreur sinon)

    today = datetime.now().strftime("%Y%m%d") # Date du jour au format AAAAMMJJ
    dst = f"{backup_dir}/lab_{today}.db"
    # Ne crée le backup que s'il n'existe pas déjà pour aujourd'hui
    # (évite de le recréer à chaque rechargement de la page Streamlit)
    if not os.path.exists(dst):   
        shutil.copy2(src, dst)

    # Garder seulement les 30 derniers backups
    backups = sorted(os.listdir(backup_dir)) # Liste les fichiers, triés par ordre chronologique (format de date trié = ordre naturel
    if len(backups) > 30:
        for old in backups[:-30]:  # Prend tout les élements sauf les 30 derniers
            os.remove(os.path.join(backup_dir, old))  
def test_email_valide(email):
    try:
        info = validate_email(email, check_deliverability=False)
        return True, info.normalized
    except EmailNotValidError as e:
        return False, str(e)
def test_nom_valide(prenom)  :
   test1=True
   test2=True
   if len(prenom) != 3 or not prenom.isalpha():
        test1= False
        
   else:    
        conn = sqlite3.connect("db/lab.db")
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE (intiales=?)",(prenom,))
        resultat = c.fetchone()
        if resultat:
          test2=False
   return test1,test2
def parse_birthday(raw):
    # -----------------------------
    # Valide et convertit une date de naissance saisie en texte libre (JJ/MM/AAAA).
    
    # Paramètre
    # ---------
    # raw : str — texte saisi par l'utilisateur (ex: "05/03/1990")
    #
    # Retourne
    # --------
    # (date | None, bool, str | None)
    #   - date convertie si valide, sinon None
    #   - True si la saisie est valide (ou vide), False sinon
    #   - message d'erreur si invalide, sinon None
    # -----------------------------

    if not raw or not raw.strip():
        # Champ laissé vide : la date de naissance est optionnelle,
        # on ne bloque pas l'inscription
        return None, True, None

    raw = raw.strip()

    try:
        # strptime construit un vrai objet date : si le jour ou le mois
        # est hors limites (ex: mois=13, jour=32, ou 30/02), Python lève
        # une ValueError au lieu de "corriger" silencieusement la date
        # (pas de rollover comme peuvent le faire certains widgets JS)
        d = datetime.strptime(raw, "%d/%m/%Y").date()
    except ValueError:
        return None, False, "Invalid date of birth"

    # Rejette les dates dans le futur (le bug initial remonté par le beta testeur)
    if d > date.today():
        return None, False, "Invalid date of birth: it cannot be in the future."

    # Rejette les dates trop anciennes pour être plausibles
    if d < date(1940, 1, 1):
        return None, False, "Invalid date of birth."

    # Date valide et cohérente
    return d, True, None
def  check_admin(email,):
 # -----------------------------
    # Vérifie si un email appartient à un administrateur enregistré.
    #
    # Paramètres
    # ----------
    # email : str — adresse email à vérifier
    #
    # Retourne
    # --------
    # tuple | None — la ligne admin si elle existe, None sinon.
 # -----------------------------
    conn = sqlite3.connect("db/lab.db")
    c = conn.cursor()
    c.execute("SELECT * FROM admin WHERE email=?", (email,))
    user_admin=c.fetchone()
    conn.close()
    return user_admin 
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


    
# =============================================================================
# Intialisation de la base de données 
# ===========================================================================
init_db()
backup_db_daily()

# =============================================================================
#  BLOC CONNEXION
# Affiché uniquement si l'utilisateur n'est pas encore connecté.
# =============================================================================

user = check_user(st.session_state.user_email) if st.session_state.user_email is not None else None
user_admin = st.session_state.get("admin_verified", False)
    # -------------------------------------------------------------------------
    # BLOC CONNEXION
    # Affiché uniquement si l'utilisateur n'est pas encore connecté.
    # -------------------------------------------------------------------------
if not st.session_state.get("user_conn", False):
      st.subheader("Login")
      if not st.session_state.awaiting_admin_password:



       with st.form("login_form"):
         
          email = st.text_input("Email", value=st.session_state.get("user_email", ""))
          submit = st.form_submit_button("Log in ")


       if submit:
           test_validation,e=test_email_valide(email) if email else None
           if not test_validation:
            st.error(f"{e}")
           if test_validation: 

                 user = check_user(email)          # Cet email est-il un utilisateur enregistre ?
                 admin_row = check_admin(email)     # Cet email est-il un administrateur ?
                 st.session_state.user_email = email

                 if admin_row is not None:
                     # Email admin detecte : on NE connecte PAS tout de suite.
                     # On memorise l'email et on active l'etape 2, puis on force
                     # un rerun immediat pour afficher le formulaire mot de passe.
                     st.session_state.awaiting_admin_password = True
                     st.session_state.email_to_verify = email
                     st.rerun()

                 elif user:
                     # Email non-admin, mais utilisateur connu -> connexion classique
                     if user[4] == 0:
                      st.error("Your profile is pending validation from the administrator.")
                      st.session_state.user_email = email
                     else:
                             st.session_state.user_idd = user[0]
                             st.session_state.user_email = email
                             st.session_state.user_conn = True
                             st.session_state.user_name = user[1]
                             st.session_state.pending_email = None
                             st.session_state.user_intiales = user[5]
                             st.rerun()
                 else:
                     # Email inconnu -> declenche le formulaire d'inscription plus bas
                          st.session_state.pending_email = email

      else:
          # --- ETAPE 2 : mot de passe admin ---
          # Ce bloc ne s'affiche QUE si awaiting_admin_password est True,
          # c'est-a-dire seulement pour un email reconnu comme admin a l'etape 1.
          st.info(f"Admin email detected ({st.session_state.email_to_verify}). Please enter the admin password.")
          with st.form("admin_password_form"):
              password = st.text_input("Admin password", type="password")
              submit_admin = st.form_submit_button("Login")

          if submit_admin:
              # Mot de passe non vide ET correct (hash compare a la table admin_code)
              if password and identification_admin(password):
                  email = st.session_state.email_to_verify   # On recupere l'email memorise a l'etape 1
                  user = check_user(email)
                  st.session_state.admin_verified = True     # Seul endroit du fichier ou ce flag passe a True

                  if user:
                      # L'admin a aussi un profil "utilisateur" classique
                      st.session_state.user_idd = user[0]
                      st.session_state.user_name = user[1]
                      st.session_state.user_intiales = user[5]
                  else:
                      # L'admin n'a pas de profil "utilisateur" -> on utilise son nom admin
                      admin_row = check_admin(email)
                      st.session_state.user_idd = None
                      st.session_state.user_name = admin_row[1] if admin_row else "Admin"
                      st.session_state.user_intiales = None

                  st.session_state.user_conn = True
                  st.session_state.user_email = email
                  st.session_state.awaiting_admin_password = False  # On referme l'etape 2
                  st.session_state.email_to_verify = None
                  st.rerun()
              else:
                  # Mot de passe incorrect : on reste sur l'etape 2 (awaiting_admin_password
                  # reste True), l'utilisateur peut reessayer sans retaper l'email.
                  st.error("Incorrect password")


  
# =============================================================================
#  BLOC INSCRIPTION
# Affiché uniquement si l'email n'est pas reconnu 
# =============================================================================
if st.session_state.pending_email:

        st.info(
        "Your email address is not registered. Please complete your registration details."
    )

        with st.form("signup_form"):
          name=st.text_input(" Please Enter your first name")
          In = st.text_input("Enter your three-letter initials as defined by BBF")
          birthday_raw = st.text_input("Birthday (DD/MM/YYYY)", placeholder="DD/MM/YYYY")
          
          signup = st.form_submit_button("Sign up")

          if signup:

           if name and In: # Vérification que les champs obligatoires sont remplis
               
               birthday,tb, msg = parse_birthday(birthday_raw)  # Validation de la date de naissance : renvoie la date convertie,
               
               t1,t2=test_nom_valide(In)  # t1 = format des initiales OK (3 lettres), t2 = initiales pas déjà prises

               # Conversion de la date en format ISO pour stockage en BDD
               if not tb:
                     st.error(msg)    # Date invalide (mauvais format, future, ou trop ancienne)
               elif t1 and t2 : 
               # Insertion du nouvel utilisateur en base
               # validation = 0 → en attente de validation par l'admin
                birthday_db = birthday.isoformat() if birthday is not None else None
                conn = sqlite3.connect("db/lab.db")
                c = conn.cursor()

                c.execute(
                """
                INSERT INTO users (nom, email, birthday, validation,intiales)
                VALUES (?, ?, ?, ?,?)
                """,
                (
                    name,
                    st.session_state.pending_email,
                    birthday_db,
                    0,
                    In.upper()
                )
            )

                conn.commit()
                conn.close()

                # Notifie les admins "notification activee" qu'un profil est a valider.
                # Non bloquant : un echec d'envoi n'empeche pas l'inscription.
                ok_mail, err_mail = notifier_admins_nouveau_user(
                    name, st.session_state.pending_email, In.upper()
                )
                if not ok_mail and err_mail != NOT_CONFIGURED:
                    st.caption(f"ℹ️ Admin notification email not sent ({err_mail})")

                st.success(
                "✅ Your email has been registered and is pending validation"
            )

                st.session_state.pending_email = None  # On réinitialise pending_email et on recharge la page

                time.sleep(2)
                st.rerun()
               elif t1==True and t2==False :
                  st.error("An account with these initials already exists. Please check your initials.") 
               elif t1==False and t2==True:  
                   st.error("The initials must consist of 3 letters.") 

            

           else:

             st.warning("Please enter your first name and your intiales")

# =============================================================================
# Interface princiaple (utilisateur connecté)
# =============================================================================
if st.session_state.user_conn: 
 
 col1, col2 = st.columns([7, 3], vertical_alignment="center") # Création de l'en-tête avec deux colonnes ( titre et infos personne connectée)
    
 with col1:
       st.markdown("<p style='font-size:28px; font-weight:600; margin:0;'>User interface</p>",unsafe_allow_html=True) # titre
    
 with col2:
        # Affichage du nom de la personne connectée
        user_name = st.session_state.get('user_name', '')
        col_name, col_btn = st.columns([1, 1])
        with col_name:
    
         st.markdown(
            f"""<div style="display:flex; align-items:center; justify-content:flex-end; height:38px;">
                <span style="background:var(--secondary-background-color); color: var(--text-color); border-radius:8px; padding:6px 12px; font-size:16px;border: 1px solid var(--border-color); white-space:nowrap;">
                    👤 {user_name}
                </span>
            </div>""",
            unsafe_allow_html=True
        )
         
     # Création du bouton Log out
        with col_btn: 
         if st.button("Log out"): # Si le bouton log out est activé
              
            for key in list(st.session_state.keys()):
                del st.session_state[key] # Vide complètement la session utilisateur (suppression de toutes les variables)
            
            st.rerun()  # Recharge immédiatement l'application pour revenir à l'écran initial
          
    
 st.divider() #
 # -------------------------------------------------------------------------
 #  Section "Actualités du jour"
 # Affiche les commentaires admin dont la date de publication est passée
 # et la date de suppression n'est pas encore atteinte
 # -------------------------------------------------------------------------
 st.subheader("📣Today's News")      
 conn = sqlite3.connect("db/lab.db")
 c = conn.cursor()

 c.execute("""
    SELECT 
        Comment ,
        Bon,
        Mauvais,
        Warning,
        Info,
        Date_publication,
        Date_of_delete   
    FROM admin_comment
""")
 comment=c.fetchall()
 df_comment=pd.DataFrame(comment,columns=["comment","bon","mauvais","warnig","info","date_publication","date_of_delete"])

 df_comment["date_publication"] = pd.to_datetime(
    df_comment["date_publication"]
)
 df_comment["date_of_delete"] = pd.to_datetime(
    df_comment["date_of_delete"]
)
 if not df_comment.empty:
  now = datetime.now()
  valid_news = df_comment[
    (df_comment["date_publication"] <= now) &
    (df_comment["date_of_delete"] >= now)] # On cherches le messages uniquement  dans la période de validité
  if not valid_news.empty:
   for index,row in valid_news.iterrows():
      # Le type de message (Bon/erreur/warning/info) dépend des colonnes booléennes
      if row["bon"]==1:
         st.success(row["comment"])
      elif row["mauvais"]==1:
          st.error(row["comment"])
      elif row["warnig"]==1:
          st.warning(row["comment"])
      elif row["info"]==1:
           st.info(row["comment"])
  else:
      st.write("No news today")
 else:
   st.write("No news for today") 
 # -------------------------------------------------------------------------
 #  Section "Mes prochaines reservations"
 #  Récupère toutes les réservations de l'utilisateur connecté,
 # avec les infos de l'équipement réservé 
 # -------------------------------------------------------------------------

 st.markdown("<br>", unsafe_allow_html=True)
       

 st.subheader("📅 My Next reservations")

 conn = sqlite3.connect("db/lab.db")
 c = conn.cursor()

 c.execute("""
    SELECT 
        r.start_time,
        r.end_time,
        e.Nom,
        e.Numero_salle,
        e.Nom_salle

    FROM reservations r

    JOIN equipements e
    ON r.equipement_id = e.id

    WHERE r.user_id = ?

    ORDER BY r.start_time ASC

""", (st.session_state.user_idd,))

 reservations = c.fetchall()

 conn.close()

 if reservations:

    df_reservation = pd.DataFrame(
        reservations,
        columns=[
            "Start",
            "End",
            "Equipment",
            "Room number",
            "Room name"
        ]
    )

    # Conversion des dates en objets datetime
    df_reservation["Start"] = pd.to_datetime(df_reservation["Start"])
    df_reservation["End"]=pd.to_datetime(df_reservation["End"])
    
    # On ne garde que les réservations qui n'ont pas encore commencé
    # (date de début >= aujourd'hui)
    df_reservation_copy=df_reservation[(df_reservation["Start"].dt.date >= datetime.now().date())]

    if not df_reservation_copy.empty: 
       for index, row in df_reservation_copy.iterrows():
        # Réservation sur une seule journée → affichage avec heures
           if row["Start"].date() == row["End"].date(): 
              st.info(
            f"You have a reservation of {row['Equipment']} "
            f"on {row['Start'].date()} "
            f"in room {row['Room name']} "
            f"from {row['Start'].strftime('%H:%M')} "
            f"to {row['End'].strftime('%H:%M')}"
        )
           else:
              # Réservation sur plusieurs jours → affichage avec dates uniquement
              st.info(
            f"You have a reservation of {row['Equipment']} "
            f"in room {row['Room name']} "
            f"from {row['Start'].date()} "
            f"to {row['End'].date()}"
        )
    else:

      st.warning("No upcoming reservation")

 else:
    st.warning("No upcoming reservation")


 st.markdown("<br>", unsafe_allow_html=True)
 
 # -------------------------------------------------------------------------
 #  Section "Anniversaires du jour "
 # Parcourt tous les utilisateurs et affiche un message + ballons
 # si la date du jour correspond à l'anniversaire de quelqu'un
 # -------------------------------------------------------------------------
 st.markdown("<br>", unsafe_allow_html=True)
 st.subheader("🎉 Today's Birthdays")  

 today_day = datetime.now().day
 today_month = datetime.now().month
 # Récupération des donées de la base de données
 conn = sqlite3.connect("db/lab.db")
 c = conn.cursor()

 c.execute("SELECT nom, birthday FROM users")
 birth=c.fetchall()
 # Conversion des donées en dataframe
 df_birth=pd.DataFrame(birth,columns=["Name","Date_birth"])
 df_birth["Date_birth"] = pd.to_datetime(
    df_birth["Date_birth"],
    errors="coerce"   # errors="coerce" → les dates invalides/manquantes deviennent NaT au lieu de planter
)
 # Affichage des anniversaires 
 if not df_birth.empty :
    birthday_today = False
    for i,row in df_birth.iterrows():
      if pd.notna(row["Date_birth"]):  
       if row["Date_birth"].day==today_day and row["Date_birth"].month==today_month:
          st.success(f"Happy birthday {row["Name"]}")
          birthday_today = True
    
    if birthday_today:
       st.balloons() # Affichage des ballons
    else : 
       st.markdown("No birthdays today") 

 else: 
    st.markdown("No birthdays today")
 
 # -------------------------------------------------------------------------
 #  Section "Equipements du jour " + FILTRES (salle/catégorie)
 # -------------------------------------------------------------------------
 st.subheader("🧪Equipement information")
# Récupération des donées de la base de donées
 conn = sqlite3.connect("db/lab.db")
 c = conn.cursor()

 c.execute("""
    SELECT 
        id,
        Nom,
        Numero_salle,
        Nom_salle,
        Categorie
    FROM equipements
""")

 eq = c.fetchall()


# Construction des listes uniques de salles / noms de salle / catégories
# pour alimenter les menus déroulants de filtre
 salles = {(e[2], e[3]) for e in eq}
 categorie = {e[4] for e in eq if e[4] is not None}  # On exclut None ici, géré séparément via "Uncategorized"
 options_salle = [""] + sorted(f"{i}-{j}" for i, j in salles) # Format "numéro-nom" pour chaque salle, avec une option vide en premier, triée par ordre alphanumérique
 options_categorie = [""] + sorted(categorie) + ["Uncategorized"] # Liste des catégories + option pour les équipements sans catégorie
# Affichage des filtres au-dessus du tableau (deux colonnes, comme dans la page Admin)
 filtre_col1, filtre_col2 = st.columns(2)
 with filtre_col1:
    choice_room = st.selectbox(
        "Filter by equipment room",
        options_salle,
        key="salle_select"
    ) # Filtre "Salle"
 with filtre_col2:
    choice_categorie = st.selectbox(
        "Filter by category",
        options_categorie,
        key="categorie_select"
    ) # Filtre "Catégorie"

# -- Contrôle de tri de la table "Equipment information" --------------------
# Appliqué quel que soit le filtre actif (salle / catégorie / les deux / aucun).
 eq_table_columns = [
    "Equipment name",
    "Room number",
    "Room name",
    "Equipment manager",
    "Equipment co-manager",
    "Equipment status",
    "Category",
    "Protocol"
]
 sort_col1, sort_col2 = st.columns([2, 1])
 with sort_col1:
    eq_sort_column = st.selectbox("🔀 Sort by", eq_table_columns, index=0, key="home_eq_sort_column")
 with sort_col2:
    eq_sort_order = st.selectbox("Order", ["Ascending", "Descending"], key="home_eq_sort_order")

 def sort_equipment_df(df):
    # Tri alphanumérique insensible à la casse (par défaut : Equipment name, croissant)
    return df.sort_values(
        by=eq_sort_column,
        ascending=(eq_sort_order == "Ascending"),
        key=lambda col: col.str.lower() if col.dtype == "object" else col,
        na_position="last",
        kind="stable"
    ).reset_index(drop=True)

# Construction des tableaux en focntion des choix des filtres
# -- Cas 1 : L'utilisateur à choisi une salle uniquement ---
 if choice_room and not choice_categorie:

    num = choice_room.split("-")[0]  # On extrait le numéro de salle à partir de "numéro-nom"
    # Récupération des equipements se trouvant dals salle choisie
    conn = sqlite3.connect("db/lab.db")
    c = conn.cursor()

    c.execute("""
        SELECT
            Nom,
            Numero_salle,
            Nom_salle,
            Responsable,
            Coresponsable,
            Etat,
            Categorie,
            Protocole

        FROM equipements

        WHERE Numero_salle = ?
    """, (num,))

    eq_salle = c.fetchall()
    if not eq_salle: 
        st.info("No equipment found in this room.")
    else:   
        # Transformation des donées en Datatframe
        df_eq_salle = pd.DataFrame(
            eq_salle,
            columns=[
                "Equipment name",
                "Room number",
                "Room name",
                "Equipment manager",
                "Equipment co-manager",
                "Equipment status",
                "Category",
                "Protocol"
            ]
        )

        df_eq_salle = df_eq_salle.fillna("No information") # Remplace les valeurs manquantes (NaN) par un texte explicite
        # Nettoyage et traduction des statuts (panne/marche) (FR → EN)
        df_eq_salle["Equipment status"] = (
            df_eq_salle["Equipment status"]
            .fillna("")
            .str.strip()
            .str.lower()
        )

        df_eq_salle["Equipment status"] = (
            df_eq_salle["Equipment status"]
            .replace({
                "marche": "Operational",
                "panne": "Out of order"
            })
        )

        df_eq_salle["Equipment status"] = (
            df_eq_salle["Equipment status"]
            .replace("", "No information")
        )

        # Gestion des protocoles manquants
        df_eq_salle["Protocol"] = (
            df_eq_salle["Protocol"]
            .fillna("No protocol")
        )
        df_eq_salle = sort_equipment_df(df_eq_salle)
        style_equipment_table(df_eq_salle)
# -- Cas 2 : L'utilisateur à choisi une catégorie uniquement ---   
 elif choice_categorie and not choice_room :

    conn = sqlite3.connect("db/lab.db")
    c = conn.cursor()

    if choice_categorie == "Uncategorized":
        c.execute("""
            SELECT
                Nom,
                Numero_salle,
                Nom_salle,
                Responsable,
                Coresponsable,
                Etat,
                Categorie,
                Protocole

            FROM equipements

            WHERE Categorie IS NULL
        """)
    else:
        c.execute("""
            SELECT
                Nom,
                Numero_salle,
                Nom_salle,
                Responsable,
                Coresponsable,
                Etat,
                Categorie,
                Protocole

            FROM equipements

            WHERE Categorie = ?
        """, (choice_categorie,))

    eq_categorie = c.fetchall()
    if not eq_categorie:
        st.info("No equipment found for this category.")
    else: 
        df_categorie = pd.DataFrame(
            eq_categorie,
            columns=[
                "Equipment name",
                "Room number",
                "Room name",
                "Equipment manager",
                "Equipment co-manager",
                "Equipment status",
                "Category",
                "Protocol"
            ]
        )
        df_categorie = df_categorie.fillna("No information")
        # Nettoyage et traduction des états
        df_categorie["Equipment status"] = (
            df_categorie["Equipment status"]
            .fillna("")
            .str.strip()
            .str.lower()
        )

        df_categorie["Equipment status"] = (
            df_categorie["Equipment status"]
            .replace({
                "marche": "Operational",
                "panne": "Out of order"
            })
        )

        df_categorie["Equipment status"] = (
            df_categorie["Equipment status"]
            .replace("", "No information")
        )

        # Gestion des protocoles manquants
        df_categorie["Protocol"] = (
            df_categorie["Protocol"]
            .fillna("No protocol")
        )

        df_categorie = sort_equipment_df(df_categorie)
        style_equipment_table(df_categorie)
# -- Cas 3 : L'utilisateur à choisi une catégorie + salle--
 elif choice_categorie and choice_room :
    num = choice_room.split("-")[0]
    conn = sqlite3.connect("db/lab.db")
    c = conn.cursor()

    if choice_categorie == "Uncategorized":
        c.execute("""
            SELECT
                Nom,
                Numero_salle,
                Nom_salle,
                Responsable,
                Coresponsable,
                Etat,
                Categorie,
                Protocole

            FROM equipements

            WHERE Categorie IS NULL AND Numero_salle = ?
        """, (num,))
    else:
        c.execute("""
            SELECT
                Nom,
                Numero_salle,
                Nom_salle,
                Responsable,
                Coresponsable,
                Etat,
                Categorie,
                Protocole

            FROM equipements

            WHERE Categorie = ? AND Numero_salle = ?
        """, (choice_categorie, num))

    eq_categorie_salle = c.fetchall()
    if not eq_categorie_salle:
        st.info("No equipment found for this room and category.")
    else:
        df_categorie_salle = pd.DataFrame(
            eq_categorie_salle,
            columns=[
                "Equipment name",
                "Room number",
                "Room name",
                "Equipment manager",
                "Equipment co-manager",
                "Equipment status",
                "Category",
                "Protocol"
            ]
        )
        df_categorie_salle = df_categorie_salle.fillna("No information")
        # Nettoyage et traduction des états
        df_categorie_salle["Equipment status"] = (
            df_categorie_salle["Equipment status"]
            .fillna("")
            .str.strip()
            .str.lower()
        )

        df_categorie_salle["Equipment status"] = (
            df_categorie_salle["Equipment status"]
            .replace({
                "marche": "Operational",
                "panne": "Out of order"
            })
        )

        df_categorie_salle["Equipment status"] = (
            df_categorie_salle["Equipment status"]
            .replace("", "No information")
        )

        # Gestion des protocoles manquants
        df_categorie_salle["Protocol"] = (
            df_categorie_salle["Protocol"]
            .fillna("No protocol")
        )

        df_categorie_salle = sort_equipment_df(df_categorie_salle)
        style_equipment_table(df_categorie_salle)

 else: 
    c.execute("""
        SELECT 
            Nom,
            Numero_salle,
            Nom_salle,
            Responsable,
            Coresponsable,
            Etat,
            Categorie,
            Protocole
            
        FROM equipements
    """)
    eq = c.fetchall()
    if not eq:
        st.info("No equipment found.")
    else:   

        df_eq = pd.DataFrame(
            eq,
            columns=[
                "Equipment name",
                "Room number",
                "Room name",
                "Equipment manager",
                "Equipment co-manager",
                "Equipment status",
                "Category",
                "Protocol"
            ]
        )
        df_eq = df_eq.fillna("No information")
        # Nettoyage et traduction des états
        df_eq["Equipment status"] = (
            df_eq["Equipment status"]
            .fillna("")
            .str.strip()
            .str.lower()
        )

        df_eq["Equipment status"] = (
            df_eq["Equipment status"]
            .replace({
                "marche": "Operational",
                "panne": "Out of order"
            })
        )

        df_eq["Equipment status"] = (
            df_eq["Equipment status"]
            .replace("", "No information")
        )

        # Gestion des protocoles manquants
        df_eq["Protocol"] = (
            df_eq["Protocol"]
            .fillna("No protocol")
        )

        df_eq = sort_equipment_df(df_eq)
        style_equipment_table(df_eq)
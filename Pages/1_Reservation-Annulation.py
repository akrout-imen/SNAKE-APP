import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta,date
import calendar
import base64
import time 
import hashlib
from email_validator import validate_email, EmailNotValidError
from email_utils import notifier_admins_nouveau_user, NOT_CONFIGURED
from streamlit_calendar import calendar as st_calendar
from streamlit_modal import Modal
# =============================================================================
# INITIALISATION DU SESSION STATE


# =============================================================================
if "user_email" not in st.session_state:
    st.session_state.user_email = None

if "pending_email" not in st.session_state:
    st.session_state.pending_email = None
if "user_conn" not in st.session_state:
      st.session_state.user_conn = False 

if "user_idd" not in st.session_state:
      st.session_state.user_idd = None
if "user_name" not in st.session_state:
      st.session_state.user_name = None
if "user_intiales" not in st.session_state:
      st.session_state.user_intiales = None
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
""", unsafe_allow_html=True)

st.sidebar.divider()

# =============================================================================
# NAVIGATION DANS LA SIDEBAR
# Liens vers les différentes pages de l'application.
# ===========================================================================
st.sidebar.page_link("app.py",                              label="🏠 Home")
st.sidebar.page_link("pages/1_Reservation-Annulation.py",   label="📅 Reservation / Cancellation")
st.sidebar.page_link("pages/2_Category_View.py",            label="🗂️ Category view")
st.sidebar.page_link("pages/3_Admin.py",                    label="⚙️ Admin")

st.sidebar.markdown("<br>", unsafe_allow_html=True) 

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
   
    conn = sqlite3.connect("db/lab.db")
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE email=?", (email,))
    user = c.fetchone()
    conn.close()
    
    return user

def check_permessions(eq_id,df_permessions):
 # ----------------------------- 
     # Vérifie si l'utilisateur courant a le droit de réserver un équipement.

     # Logique :
       # 1. Si l'équipement NE requiert PAS de permission explicite (Demande_permission != 'Oui'),
         #  l'accès est autorisé d'emblée.
      #  2. Sinon, l'accès n'est accordé que si l'équipement figure dans le DataFrame
          # des permissions de l'utilisateur.

     #  Paramètres
        # ----------
        # eq_id         : int   — identifiant de l'équipement
        # df_permessions: DataFrame — permissions accordées à l'utilisateur
                    #  (colonne 'equipement' = equipment_id)

     # Retourne
        # --------
        # bool — True si autorisé, False sinon.
        # -----------------------------  
    conn = sqlite3.connect("db/lab.db")
    c = conn.cursor()
    c.execute("SELECT id,Demande_permission FROM equipements WHERE  Demande_permission=?",("Oui",))
    perm=c.fetchall()
    df_perm= pd.DataFrame(perm,columns=["id","perm"])
    df_perm_f = df_perm[df_perm["id"] == eq_id]
    if df_perm_f.empty:
        found= True
        
    else:
      found = False
    for i in df_permessions["equipement"]:
        if i == eq_id:
            found = True
            break
    return(found)
def calcul_temps_fonctionnement(df_resa,date_str):
 # -----------------------------
    # Calcule le temps de fonctionnement total d'un équipement
    # depuis deux origines distinctes.
    #
    # Logique :
    #   1. Calcul du total depuis l'installation (toutes les réservations).
    #   2. Calcul depuis la dernière maintenance :
    #      - Cas 1 : réservation entièrement après la maintenance → comptée en totalité.
    #      - Cas 2 : réservation à cheval sur la date → seule la partie après est comptée.
    #      - Cas 3 : réservation entièrement avant → ignorée.
    #
    # Paramètres
    # ----------
    # df_resa   : DataFrame — colonnes 'Début' et 'Fin' (ISO 8601)
    # date_str  : str | None — date de la dernière maintenance (format ISO)
    #
    # Retourne
    # --------
    # tuple(float, float) — (heures depuis installation, heures depuis maintenance)
# -----------------------------
    if date_str!=None:
        date_maintenance = pd.to_datetime(date_str)
    else :
     date_maintenance=None  
    heure_fct=0
    heure_fct_maintenance=0
    for i,j in zip(df_resa["Début"],df_resa["Fin"]):
        début = pd.to_datetime(i)
        fin = pd.to_datetime(j)
        duree_heures=(fin - début).total_seconds() / 3600

        heure_fct=heure_fct+ duree_heures 
        
    if date_maintenance is not None:
        for x,z in zip(df_resa["Début"],df_resa["Fin"]):
            début = pd.to_datetime(x)
            fin = pd.to_datetime(z)
            duree_totale=(fin - début).total_seconds() / 3600

            if datetime.fromisoformat(x)> date_maintenance:
                heure_fct_maintenance=heure_fct_maintenance + duree_totale
               # Cas 1 : réservation entièrement après maintenance
            
            # Cas 2 : réservation chevauche la maintenance
            elif début < date_maintenance < fin:

                duree_apres_maintenance = (
                    fin - date_maintenance
                ).total_seconds() / 3600

                heure_fct_maintenance += duree_apres_maintenance
    

    return heure_fct, heure_fct_maintenance
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
def check_panne (eq_id) :
  # -----------------------------
    # Vérifie si un équipement est actuellement en panne.
    #
    # Paramètres
    # ----------
    # eq_id : int — identifiant de l'équipement
    #
    # Retourne
    # --------
    # bool — False si l'état est 'panne' (insensible à la casse), True sinon.
 # -----------------------------
    conn=sqlite3.connect("db/lab.db") 
    c=conn.cursor()
    c.execute ("SELECT Etat FROM equipements  WHERE id=?",(eq_id,) )
    etat=c.fetchone()
    verif = True
    if etat and etat[0]:
        if etat[0].strip().lower()== "panne":
            verif=False
        else:
            verif=True 
    return verif 
def get_maintenance_events(equipement_id, start_range, end_range):
 # -----------------------------
    # Génère les événements de maintenance périodique d'un équipement,
    # filtrés dans la plage de dates [start_range, end_range].
    #
    # Logique :
    #   1. Récupère la prochaine date d'arrêt et la périodicité depuis la base.
    #   2. Itère à partir de cette date par incréments de 'period' jours.
    #   3. N'ajoute que les occurrences comprises dans la plage visible.
    #
    # Paramètres
    # ----------
    # equipement_id : int      — identifiant de l'équipement
    # start_range   : datetime — borne inférieure de la plage visible
    # end_range     : datetime — borne supérieure de la plage visible
    #
    # Retourne
    # --------
    # list[dict] — liste d'événements au format FullCalendar,
    #              affichés en arrière-plan (eventDisplay: 'background').
 # -----------------------------
    conn = sqlite3.connect("db/lab.db")
    c = conn.cursor()

    c.execute("""
        SELECT Date_prochain_arret, Compteur_d_arret_en_jours
        FROM equipements
        WHERE id=?
    """, (equipement_id,))

    row = c.fetchone()
    conn.close()

    if not row or not row[0] or not row[1]:
        return []

    next_stop = datetime.strptime(row[0], "%Y-%m-%d")
    period = int(row[1])

    events = []
    current = next_stop

    # génération uniquement dans la plage visible
    while current <= end_range:

        if current >= start_range:

            events.append({
                "title": "UpKeep equipement",
                "start": current.isoformat(),
                "end": (current + timedelta(days=1)).isoformat(),
                "eventDisplay": "background",
                "color":"#d3d3d3"
            })

        current = current+ timedelta(days=period)

    return events
def is_maintenance_overlap(start_dt, end_dt, maintenance_events):
 # -----------------------------
    # Vérifie si un créneau [start_dt, end_dt] chevauche
    # un événement de maintenance planifié.
    #
    # Logique :
    #   Chevauchement si : start < m_end ET end > m_start
    #   (les intervalles ne sont pas disjoints).
    #
    # Paramètres
    # ----------
    # start_dt           : str ISO 8601 — début du créneau à tester
    # end_dt             : str ISO 8601 — fin du créneau à tester
    # maintenance_events : list[dict]   — événements de maintenance FullCalendar
    #
    # Retourne
    # --------
    # bool — True si chevauchement détecté, False sinon.
  # -----------------------------

    start = datetime.fromisoformat(start_dt)
    end = datetime.fromisoformat(end_dt)

    for ev in maintenance_events:

        m_start = datetime.fromisoformat(ev["start"])
        m_end = datetime.fromisoformat(ev["end"])

        # chevauchement
        if start < m_end and end > m_start:
            return True

    return False
def is_all_day(start, end):
 # -----------------------------
    # Détermine si un créneau correspond à une réservation 'toute la journée'.
    #
    # Logique :
    #   Critère : heures et minutes à 00:00 pour start ET end,
    #   et durée >= 1 jour.
    #
    # Paramètres
    # ----------
    # start : str | datetime — début du créneau
    # end   : str | datetime — fin du créneau
    #
    # Retourne
    # --------
    # bool — True si le créneau est une journée complète, False sinon.
 # -----------------------------
    start = pd.to_datetime(start)
    end = pd.to_datetime(end)

    duration = end - start

    return (
        start.hour == 0 and start.minute == 0 and
        end.hour == 0 and end.minute == 0 and
        duration.days >= 1
    )
def blocked_by_all_day (start,end,events):
 # -----------------------------
    # Vérifie si un créneau est bloqué par une réservation 'toute la journée'.
    #
    # Paramètres
    # ----------
    # start  : str | datetime — début du créneau à tester
    # end    : str | datetime — fin du créneau à tester
    # events : list[dict]     — événements FullCalendar déjà présents
    #
    # Retourne
    # --------
    # bool — True si le créneau chevauche une réservation all-day, False sinon.
 # -----------------------------
     start = pd.to_datetime(start)
     end = pd.to_datetime(end)
     for i in events :
            if not i.get("allDay"):
                continue
            ev_start = pd.to_datetime(i["start"])
            ev_end = pd.to_datetime(i["end"])

            if start < ev_end and end > ev_start:
                  return True
     return False       
def check_overlap(equipement_id, new_start_dt, new_end_dt, exclude_start=None, exclude_end=None):
 # -----------------------------
    # Vérifie si le nouveau créneau chevauche une réservation existante.
    #
    # Logique :
    #   1. Récupère toutes les réservations de l'équipement.
    #   2. Ignore la réservation en cours de modification
    #      (paramètres exclude_start / exclude_end).
    #   3. Détecte tout chevauchement avec les réservations restantes.
    #
    # Paramètres
    # ----------
    # equipement_id : int      — identifiant de l'équipement
    # new_start_dt  : datetime — début du nouveau créneau
    # new_end_dt    : datetime — fin du nouveau créneau
    # exclude_start : str | None — début de la réservation à ignorer (modification)
    # exclude_end   : str | None — fin de la réservation à ignorer (modification)
    #
    # Retourne
    # --------
    # bool — True si chevauchement détecté, False sinon.
 # -----------------------------
    new_start_dt = pd.to_datetime(new_start_dt)
    new_end_dt = pd.to_datetime(new_end_dt)
    conn = sqlite3.connect("db/lab.db")
    c = conn.cursor()
    c.execute("""
        SELECT start_time, end_time FROM reservations
        WHERE equipement_id = ?
    """, (equipement_id,))
    rows = c.fetchall()
    conn.close()

    for start_str, end_str in rows:
        existing_start = pd.to_datetime(start_str)
        existing_end   = pd.to_datetime(end_str)

        # Ignorer la réservation qu'on est en train de modifier
        if exclude_start and exclude_end:
            if (existing_start == pd.to_datetime(exclude_start) and
                existing_end   == pd.to_datetime(exclude_end)):
                continue

        # Vérification du chevauchement
        if new_start_dt < existing_end and new_end_dt > existing_start:
            return True  # chevauchement détecté

    return False  # pas de chevauchement


def get_max_jours_reservation(equipement_id):
    # -----------------------------
    # Retourne le nombre de jours consécutifs maximum autorisé pour une
    # réservation de cet équipement (renseigné par l'admin dans la page
    # "Gestion des équipements"), ou None si aucune limite n'est fixée
    # (colonne vide ou <= 0).
    # -----------------------------
    conn = sqlite3.connect("db/lab.db")
    c = conn.cursor()
    c.execute("SELECT Nb_jours_max_reservation FROM equipements WHERE id = ?", (equipement_id,))
    row = c.fetchone()
    conn.close()
    if not row or row[0] is None:
        return None
    try:
        val = int(row[0])
    except (TypeError, ValueError):
        return None
    return val if val > 0 else None


def compte_jours_consecutifs(start_dt, end_dt):
    # -----------------------------
    # Nombre de jours calendaires consécutifs couverts par une réservation.
    # Accepte des chaînes ISO ou des datetime. Gère le cas des fins "all-day"
    # exclusives (fin à minuit) pour ne pas compter un jour de trop.
    # -----------------------------
    s = pd.to_datetime(start_dt)
    e = pd.to_datetime(end_dt)
    nb = (e.date() - s.date()).days
    if e.hour or e.minute or e.second:
        nb += 1
    return max(nb, 1)


def check_jours_max(equipement_id, start_dt, end_dt):
    # -----------------------------
    # Retourne (depassement: bool, max_jours: int | None).
    #   depassement = True si la réservation dure plus de jours consécutifs
    #   que la limite fixée par l'admin.
    # -----------------------------
    max_jours = get_max_jours_reservation(equipement_id)
    if max_jours is None:
        return False, None
    return (compte_jours_consecutifs(start_dt, end_dt) > max_jours), max_jours


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
# SÉLECTION DU MODE (Reservation / Annulation)
# =============================================================================



if "mode" not in st.session_state:
    st.session_state.mode = None


col1, col2 = st.columns(2)
with col1:
    if st.button("📅 Reservation"):
        st.session_state.mode = "reservation"
with col2:
    if st.button("❌ Cancellation"):
        st.session_state.mode = "annulation"


# =============================================================================
# MODE RÉSERVATION
# =============================================================================
if st.session_state.mode == "reservation": 
    st.title("📅 Equipment Reservation")
    
     
    # Vérification du statut de connexion
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

    # -------------------------------------------------------------------------
    # BLOC INSCRIPTION
    # Affiché si l'email saisi n'est pas encore enregistré en base.
    # -------------------------------------------------------------------------
    if st.session_state.pending_email:

        st.info(
        "Your email is not registered. Please complete your registration details."
    )

        with st.form("signup_form"):
          name=st.text_input("Please enter your first name")
          In = st.text_input("Enter your three-letter initials as defined by BBF")
          birthday_raw = st.text_input("Birthday (DD/MM/YYYY)", placeholder="DD/MM/YYYY")
          signup = st.form_submit_button("Sign up")

          if signup:
              
                

           if name and In:# Vérification que les champs obligatoires sont remplis
            birthday,tb, msg = parse_birthday(birthday_raw)
            t1,t2=test_nom_valide(In)
            if not tb:
                     st.error(msg)
           
            elif t1 and t2 : 
             conn = sqlite3.connect("db/lab.db")
             c = conn.cursor()

             c.execute(
                "INSERT INTO users (nom, email, birthday, validation,intiales) VALUES (?, ?, ?,?,?)",
                (name, st.session_state.pending_email, birthday, 0,In.upper())
            )

             conn.commit()
             conn.close()

             # Notifie les admins "notification activee" (non bloquant).
             ok_mail, err_mail = notifier_admins_nouveau_user(
                 name, st.session_state.pending_email, In.upper()
             )
             if not ok_mail and err_mail != NOT_CONFIGURED:
                 st.caption(f"ℹ️ Admin notification email not sent ({err_mail})")

             st.success(
                "✅ Your email has been registered and is pending validation"
            )

             st.session_state.pending_email = None

             time.sleep(2)
             st.rerun()
            elif t1==True and t2==False :
                  st.error("An account with these initials already exists. Please check your initials.") 
            elif t1==False and t2==True:  
                   st.error("The initials must consist of 3 letters.") 
 
           else:

             st.warning("Please enter your first name and your intiales")
      
     # -------------------------------------------------------------------------
     # BLOC PRINCIPAL — accessible uniquement aux utilisateurs connectés
     # -------------------------------------------------------------------------
    if st.session_state.user_conn: 
           # ---------------------------------------------------------------
           # Récupéreration des données dans la base
           # ---------------------------------------------------------------

    
                st.divider()    
                
                # --Récupération des infos de session--
                user_idd = st.session_state.user_idd
                user_name= st.session_state.user_name
                user_intiales= st.session_state.get("user_intiales") or user[5]
                # --Chargement de tous les équipements depuis la base--
                conn = sqlite3.connect("db/lab.db")
                c = conn.cursor()
                c.execute("SELECT id, Nom, Numero_salle, Nom_salle, Categorie FROM equipements")
                equipements = c.fetchall()
               
                
                # --Construction des listes des salles et des catégories pour les sélecteurs--
                
                salles = {(e[2], e[3]) for e in equipements}
                categories = sorted({(e[4] if e[4] else "Uncategorized") for e in equipements})

                
                # --Sélecteurs de salle et de catégorie dans la sidebar -- 
                options = [""] + sorted(f"{i}-{j}" for i, j in salles)
                st.sidebar.divider()

                st.sidebar.markdown( ''' <div class="sidebar-section"     style="font-weight:bold; font-style:italic;">  EQUIPMENT</div>  ''',unsafe_allow_html=True)
                st.sidebar.markdown("<br>", unsafe_allow_html=True) 
                choice = st.sidebar.selectbox("Select the equipment room", options, index=0, key="room_select")
                choice_categorie = st.sidebar.selectbox("Filter by category", [""] + categories, index=0, key="categorie_select_resa")
                
                
                # --Sélecteur d'équipement filtré par salle et/ou catégorie--
                filtered_eq = equipements
                if choice:
                    num = choice.split("-")[0]
                    nom_salle = choice.split("-")[1]
                    filtered_eq = [e for e in filtered_eq if str(e[2]) == num]
                if choice_categorie:
                    if choice_categorie == "Uncategorized":
                        filtered_eq = [e for e in filtered_eq if not e[4]]
                    else:
                        filtered_eq = [e for e in filtered_eq if e[4] == choice_categorie]

                if choice and choice_categorie:
                    equip_label = f"Equipment in room {nom_salle} — {choice_categorie}"
                elif choice:
                    equip_label = f"List of equipment in room {nom_salle}"
                elif choice_categorie:
                    equip_label = f"Equipment in category {choice_categorie}"
                else:
                    equip_label = "Choose equipment:"

                op = sorted(e[1] for e in filtered_eq)
                if not op:
                    st.sidebar.warning("No equipment matches the selected filters.")
                equipement_nom = st.sidebar.selectbox(
                    equip_label,
                    op,
                    key="equip_select"
                )
                st.sidebar.divider()
                # --Affichage du nom de l'utilisateur et bouton de déconnexion dans la sidebar--
                col_name, col_btn = st.sidebar.columns([1, 1])
                with col_name:
                   user_name = st.session_state.get("user_name", "")
                   st.markdown(f"""<div style="display:flex; align-items:center; height:38px;">  <span style="background:var(--secondary-background-color); color: var(--text-color); border-radius:8px;border: 1px solid var(--border-color); padding:6px 12px; font-size:15px;">👤 {user_name}</span></div>""", unsafe_allow_html=True)
                with col_btn:
                   
                   if st.button(" Log out", use_container_width=True, key="logout_sidebar"):
                       # Effacement complet du session_state pour déconnecter l'utilisateur
                      for key in list(st.session_state.keys()):
                          del st.session_state[key]
                      st.rerun()
                
                if equipement_nom:
                  # Récupération de l'ID de l'équipement sélectionné
                  equipement_id = [e[0] for e in equipements if e[1] == equipement_nom][0]
                  # --Chargement des permissions de l'utilisateurs --
                  c.execute(
                    "SELECT equipment_id FROM user_equipment_write_permissions where  user_id =?",
                    (user_idd,)
                )   
                  permessions = c.fetchall()
                  df_permessions = pd.DataFrame(permessions, columns=["equipement"])
                  # Vérification que l'équipement n'est pas en panne
                  verif_panne=check_panne(equipement_id)

                 # ---------------------------------------------------------------
                 # CONSTRUCTION DES ÉVÉNEMENTS DU CALENDRIER
                 # ---------------------------------------------------------------

                  if verif_panne: # Si pas panne
                   # --1. Réservations existantes--
                    c.execute(
                    """
                    SELECT user, start_time, end_time,comment,project 
                    FROM reservations 
                    WHERE equipement_id = ?
                    """, 
                    (equipement_id,)
                )
                    reservations = c.fetchall()
                    df_resa = pd.DataFrame(reservations, columns=["Nom", "Début", "Fin","Commentaire","Projet"])
                    events =[]
                    for _, j in df_resa.iterrows():

                           start = pd.to_datetime(j["Début"])
                           end = pd.to_datetime(j["Fin"])

                           all_day = is_all_day(start, end)

                           events.append({
                                     "title": j["Nom"],
                                     "start": start.isoformat() ,
                                     "end": end.isoformat() ,
                                     "allDay": all_day,
                                     "comment":j["Commentaire"]
                                                })
                    #-- 2. Événements de maintenance périodique (fenêtre -30j / +6 mois)-- : N'affiche que les maintenance 30 jours avant et 6 mois après
                    maintenance_events = get_maintenance_events(equipement_id,datetime.now() - timedelta(days=30), datetime.now() + timedelta(days=180)
)

                    all_events= events+maintenance_events
                    
     
                    # ---------------------------------------------------------------
                    # CONFIGURATION ET AFFICHAGE DU CALENDRIER FULLCALENDAR
                    # ---------------------------------------------------------------           
                           
                    calendar_options = {
    "initialView": "dayGridMonth",  # par défaut on peut mettre "month"
    "headerToolbar": {
        "left": "prev,next today",
        "center": "title",
        "right": "dayGridMonth,timeGridWeek,timeGridDay"
        # Les boutons à droite permettent à l'utilisateur de basculer entre mois, semaine et jour
    },
    "firstDay": 1, 
    "slotMinTime": "00:00:00", 
    "slotMaxTime":"24:00:00",
    "locale":"en",
    "timeZone":"Europe/Paris",
    "height":800,
    "scrollTime": "07:00:00",
    "eventTimeFormat": {
    "hour": "2-digit",
    "minute": "2-digit",
    "hour12": False},
    "allDaySlot": True,
    "editable" :True,
     "selectable":True}  
               
                    st.markdown("<br><br>", unsafe_allow_html=True)
                    st.markdown(f"### Reservation schedule for {equipement_nom}")
                    st.markdown("<br>", unsafe_allow_html=True)
                
                
              
                    cal = st_calendar(events=all_events,options=calendar_options)
                    # ---------------------------------------------------------------
                    # DIALOG : Nouvelle réservation
                    # Ouvert lors d'une sélection multiple ou d'un clic sur un crénaux.
                    # ---------------------------------------------------------------               
                    @st.dialog("New reservation ")   
                    def reservation_dialog(start,end,maintenance_events,events,current_view,is_date_click=False):
                            # --------------------------
                              #  Dialog de création d'une réservation.
                              #  En vue mensuelle (dayGridMonth), l'utilisateur choisit entre : 'Toute la journée' et 'Choisir les heures'.
                              #En vue hebdomadaire/journalière, les heures sont directement issues de la sélection FullCalendar.

                               #Les contrôles effectués avant insertion :
                                        #- chevauchement avec une maintenance planifiée
                                        # - chevauchement avec une réservation all-day existante
                                         #  - vérification des initiales de l'utilisateur
                            # --------------------------  
                      if current_view == "dayGridMonth": # Si vu affiché: par mois

                             mode = st.radio( "Type de réservation",["All day", "Choose hours"],horizontal=True,key="mode_month" )
                             if mode == "All day":
                                 # En mode all-day, on utilise directement les dates de sélection
                                start_dt = start.replace("Z", "").replace(".000", "")
                                end_dt = end.replace("Z", "").replace(".000", "")
                               

                             else:
                                    # Saisie manuelle des heures par l'utilisateur
                                    start_time = st.time_input("Start time ", key="start_time",step=1800)
                                    end_time = st.time_input("End time", key="end_time", step=1800)
                                    start_dt = datetime.combine(  datetime.fromisoformat(start.split("T")[0]), start_time ).isoformat()
                                    if is_date_click: # Clic simple : start et end sont sur le même jour
                                        end_dt= datetime.combine(  datetime.fromisoformat(start.split("T")[0]), end_time ).isoformat()
                                       
                                    else:    
                                        # Sélection multi-jours : FullCalendar renvoie end exclusif,
                                        # on soustrait 1 jour pour obtenir la vraie date de fin
                                           end_date = datetime.fromisoformat(end.replace("Z", "")) - timedelta(days=1)
                                           end_dt= datetime.combine( end_date.date(), end_time).isoformat()                                               
                      else:
                             
                          # Vues semaine / jour : les heures sont déjà dans start/end
                           start_dt = start.replace("Z", "").replace(".000", "")
                           end_dt = end.replace("Z", "").replace(".000", "")
                    # --- Validations ---
                      has_error=False
                      trop_long_resa, max_jours_resa = check_jours_max(equipement_id, start_dt, end_dt)
                      if end_dt<start_dt:
                         st.error("Invalid dates: The end time must be after the start time. ") 
                         has_error =True
                      
                      elif is_maintenance_overlap(start_dt, end_dt, maintenance_events): #  Verification pas de maintenance 
                          st.error("You have selected hours during which machine maintenance is scheduled. Please check your reservation.")
                          has_error=True 
                      elif  blocked_by_all_day (start_dt,end_dt,events):  #  Verification pas bloqué allDay
                          st.error("You have selected hours during which the machine is booked all day. Please check your reservation.")
                          has_error=True  
                      elif check_overlap(equipement_id,start_dt,end_dt) :
                          st.error("The selected hours overlap with an existing reservation. Please check your reservation.")
                          has_error=True
                      elif trop_long_resa:
                          st.error(f"This equipment cannot be reserved for more than {max_jours_resa} consecutive day(s). Please shorten your reservation.")
                          has_error=True
                    # --Affichage du formulaire seulement si aucun conflit détecté   --
                      if not has_error :    
                           prénom = st.text_input("Enter your three-letter initials as defined by BBF")
                           commentaire = st.text_area("Comment")
                           # Chargement des projets disponibles
                           conn = sqlite3.connect("db/lab.db")
                           c = conn.cursor()
                           c.execute("SELECT Name_project FROM project")
                           projects=c.fetchall()
                           df_project=pd.DataFrame(projects,columns=["projet"])
                           liste_projet=[]
                           liste_projet = [""]+ [p[0] for p in projects]
                           projet = st.selectbox("Project", liste_projet)
                      
                           if st.button("validate"):
                             if prénom:

                                            
                                if (prénom.strip().lower()==user_intiales.strip().lower()) or user_admin: # Vérification des initiales (ou bypass admin)
                                   conn = sqlite3.connect("db/lab.db")
                                   c = conn.cursor()
                                   
                                  # Insertion de la réservation
                                   c.execute("""INSERT INTO reservations  (equipement_id, user_id, user, start_time, end_time,project,comment)VALUES (?, ?, ?, ?,?,?,?) """, (equipement_id, user_idd, prénom.upper(), start_dt,end_dt,projet,commentaire  ))
                                # --Recalcul des heures de fonctionnement après insertion --
                                   c.execute(
                                              """
                                              SELECT start_time, end_time
                                              FROM reservations
                                              WHERE equipement_id = ?
                                              """,
                                                (equipement_id,)
                                                                )
                                   all_resa = c.fetchall()
                                   c.execute(
                                              """
                                              SELECT Date_maintenance 
                                              FROM equipements
                                              WHERE id = ?
                                              """,
                                                (equipement_id,)
                                                                )
                                   date=c.fetchall()
                                
                                   date_str=date[0][0]
                                   df_all = pd.DataFrame(all_resa, columns=["Début", "Fin"])
                                   # --Construction du message d'historique (en français, côté admin)--
                                   no=datetime.now().isoformat()
                                   salle = [e[3] for e in equipements if e[0] == equipement_id][0]
                                   start = datetime.fromisoformat(start_dt)
                                   end = datetime.fromisoformat(end_dt)
                              

   
                                   h= f"Une réservation au nom de {prénom} pour l’équipement {equipement_nom}, du {start} au {end}, dans la salle {salle}, a été ajoutée par {user_name} ({user_intiales})."
                                    # --Mise à jour des compteurs de fonctionnement--
                                   temps_fonctionnement_installation,temps_fct_maintenance = calcul_temps_fonctionnement(df_all,date_str)
                                  
                                   c.execute(
                                                 """
                                                 UPDATE equipements
                                                 SET Nombre_heure_fct_depuis_installation = ?,Nombre_heures_fct_depuis_maintenance=?
                                                 WHERE id = ?
                                                 """,
                                                    (temps_fonctionnement_installation,temps_fct_maintenance, equipement_id)
                                                                                         )
                                   # Ajout dans l'historique global
                                   c.execute(
                                                 """
                                                 INSERT INTO history (history,date) VALUES(?,?)
                                                
                                                 """,
                                                    (h,no)
                                                                                         )
                                
                                   conn.commit()
                                   conn.close()

                                   st.success("✅ Reservation added")
                                   time.sleep(2)
                                   st.rerun()
                                if prénom.strip().lower() != user_intiales.strip().lower():
                                   st.error("Wrong name")
                                   time.sleep(2)
                                   st.rerun()  
                             else:
                                 st.warning("Please enter your three-letter initials")      
                                 
                    @st.dialog("error reservation")
                     #----------------
                     #Dialog d'erreur affiché quand l'utilisateur n'a pas les droits.
                     #----------------
                    def error_reservation_dialog():
                        st.warning("You are not authorized to reserve this equipment. Contact the admin.")
                # ---------------------------------------------------------------
                # GESTION DES INTERACTIONS AVEC LE CALENDRIER
                # ---------------------------------------------------------------
                
    
                    # ---Cas 1 : sélection par drag (plage de dates/heures)     ----         
                    if cal.get("select"):
                   
                     selection = cal["select"]
                     start = selection["start"]
                     
                     end = selection["end"]
                     current_view = selection.get("view", {}).get("type", "")
                     check = check_permessions(equipement_id, df_permessions)

                     if check or user_admin:
                       reservation_dialog(start,end,maintenance_events,events,current_view)      
                     
                     else :
                          error_reservation_dialog()  
                    # --Cas 2 : clic sur une date (sélection d'un seul créneau)---
                    if cal.get("dateClick"): 
                     selection = cal["dateClick"]
                     start = selection["date"]
                     start_dt = datetime.fromisoformat(start.replace("Z", "").replace(".000", ""))
                     current_view = selection.get("view", {}).get("type", "")
                     # Durée par défaut selon la vue
                     if current_view=="dayGridMonth":
                        end_dt = start_dt + timedelta(days=1)
                     else:
                        end_dt= start_dt + timedelta(minutes=30)

                     start_dt=start_dt.isoformat()
                     end_dt=end_dt.isoformat()
                     

                     check = check_permessions(equipement_id, df_permessions)
                     
                     if check or user_admin: 
                          reservation_dialog(start_dt,end_dt, maintenance_events,events,current_view,is_date_click=True) 
                                    
                     else :
                          error_reservation_dialog()  
                # ---------------------------------------------------------------
                # DIALOG : Détails d'un événement existant (clic sur un event)
                # ---------------------------------------------------------------
                    #-- Initialisation des états pour l'édition--
                    if "selected_event" not in st.session_state: 
                      st.session_state.selected_event = None
                    if "edit_mode" not in st.session_state:
                      st.session_state.edit_mode = False 
                    if "edit_reservation" not in st.session_state:
                        st.session_state.edit_reservation=False

                
                    @st.dialog("Details") # Définition du dialog (PoPup) qui  va afficher les détails de  l'événement sélectionné
                    def show_event_dialog(event):
                           # ---------------------------------------------------------------
                               # Dialog affichant les détails d'une réservation.
                               #Fonctionnalités :
                                    #- Affichage du commentaire associé
                                    #- Modification du commentaire (si propriétaire ou admin)
                                    #- Modification de la réservation (dates/heures/initiales)
                           # ---------------------------------------------------------------     
                   
                          conn = sqlite3.connect("db/lab.db")
                          c = conn.cursor()
                          start_dt = pd.to_datetime(event["start_full"])
                          end_dt   = pd.to_datetime(event["end_full"])
                          
                          #-- Récupération du commentaire depuis la base--
                          c.execute("""SELECT comment FROM reservations WHERE equipement_id = ? AND start_time = ? AND end_time = ?""", 
                           ( equipement_id,start_dt.isoformat(),end_dt.isoformat()))
                          result=c.fetchone()
                          #-- Affichage de l'evenement--
                          st.write(f"**{event['title']}**")
                          st.write(f"From {event['start']}h to {event['end']}h")
                          if result is not None and result[0] is not None:
                            st.markdown(f"<p style='color:  #1f77b4;'>{result[0]}</p>",unsafe_allow_html=True)
                          #-- Boutons de Modifications--
                          col_btn1, col_btn2 = st.columns(2)  
                          with col_btn1:
                           if st.button ("Modify comment") :
                             if (event["title"].strip().lower()== user_intiales.strip().lower()) or user_admin:
                                st.session_state.edit_mode = True
                             else: 
                                st.error("You cannot modify comments from other users")
                          with col_btn2:      
                           if st.button("Modify reservation") :
                              if (event["title"].strip().lower()== user_intiales.strip().lower()) or user_admin:
                                st.session_state.edit_reservation=True    
                              else:
                                  st.error("You cannot modify reservations of other users")
                         # --- Sous-formulaire : modification du commentaire ---          
                          if st.session_state.edit_mode:     
                            start_dt = pd.to_datetime(event["start_full"])
                            end_dt   = pd.to_datetime(event["end_full"])    
                            n_commentaire=st.text_area("New comment",key="new_comment")
                            if st.button("validate",key="validation_comment"):
                              c.execute("""UPDATE reservations SET comment =?  WHERE equipement_id = ? AND start_time = ? AND end_time = ?""", 
                             (n_commentaire, equipement_id,start_dt.isoformat(),end_dt.isoformat()))
                              st.success("comment modified")
                              conn.commit()
                              st.session_state.edit_mode=False
                              conn.close()
                              time.sleep(2)
                              st.rerun()
                        # --- Sous-formulaire : modification de la réservation ---         
                          if st.session_state.get("edit_reservation"):
                            
                             start_dt = pd.to_datetime(event["start_full"])
                             end_dt   = pd.to_datetime(event["end_full"])
                             st.divider()
                             st.subheader("New dates & times")
                             new_initiales = st.text_input( "Initials",  value=event["title"],   key="new_initiales"  )
                             
                             col1, col2 = st.columns(2)
                             with col1:
                                   new_start_date = st.date_input(
                                       "Start date",
                                        value=start_dt.date(),
                                        key="new_start_date"
                                                    )
                                   new_start_time = st.time_input(
                                                       "Start time",
                                                   value=start_dt.time(),
                                                    key="new_start_time",
                                                    step=1800        
                                                            )
                             with col2:
                                   new_end_date = st.date_input(
                                                "End date",
                                                 value=end_dt.date(),
                                                    key="new_end_date"
                                                       )
                                   new_end_time = st.time_input(
                                               "End time",
                                            value=end_dt.time(),
                                              key="new_end_time",
                                             step=1800
                                               )

        
                             new_start_dt = datetime.combine(new_start_date, new_start_time)
                             new_end_dt   = datetime.combine(new_end_date,   new_end_time)

                             trop_long_modif, max_jours_modif = check_jours_max(equipement_id, new_start_dt, new_end_dt)

                             if st.button("Validate reservation", key="validate_reservation"):
                                  #  --Vérifications ---
                                 if new_end_dt <= new_start_dt:
                                           st.error("Invalid dates: The end time must be after the start time. ")
                                 elif new_initiales.strip().lower() != user_intiales.strip().lower() and not user_admin:
                                        st.error("You can only do reservations for yourself.")


                                 elif check_overlap( equipement_id, new_start_dt, new_end_dt, exclude_start=start_dt.isoformat(), exclude_end=end_dt.isoformat()):  #  Vérification de pas de chevauchement de reservations

                                     st.error("⚠️ This time slot overlaps with an existing reservation. Please choose different dates.")
                                 elif is_maintenance_overlap(new_start_dt.isoformat(), new_end_dt.isoformat(), maintenance_events):#  Vérification pas de maintenance

                                           st.error("⚠️ This time slot overlaps with a scheduled maintenance.")
                                 elif trop_long_modif:
                                           st.error(f"⚠️ This equipment cannot be reserved for more than {max_jours_modif} consecutive day(s). Please shorten your reservation.")
                                 else:
                                        # Mise à jour de la réservation en base
                                       c.execute(
                    """UPDATE reservations
                       SET start_time = ?, end_time = ?,user=?
                       WHERE equipement_id = ? AND start_time = ? AND end_time = ?""",
                    (
                        new_start_dt.isoformat(),
                        new_end_dt.isoformat(),
                        new_initiales.strip(),
                        equipement_id,
                        start_dt.isoformat(),
                        end_dt.isoformat(),
                        
                    )
                )
                                       conn.commit()
                                       st.success("✅ Reservation updated!")
                                       st.session_state.edit_reservation = False
                                       conn.close()
                                       time.sleep(2)
                                       st.rerun()
                          
                          conn.close()
                          
                        
                                
                          


                       

                    # --Cas 3 : clic sur un événement existant --               
                         
                    if cal.get("eventClick"):# Si la personne a cliqué sur un évènement
                        st.session_state.edit_mode = False # Réinitialisation du mode édition
                        st.session_state.edit_reservation=False
                        selection = cal["eventClick"]["event"] # Récupère les détails de lévenement
                        st.session_state.selected_event = {
            "title": selection["title"],
            "start": pd.to_datetime(selection["start"]).strftime("%d/%m/%Y %H:%M"),
            "end": pd.to_datetime(selection["end"]).strftime("%d/%m/%Y %H:%M"),
            "start_full":selection["start"],
            "end_full": selection["end"],} 
                  
                   
                   
                #-- Ouverture du dialog si un événement est sélectionné--
                # --(on exclut les événements de maintenance "UpKeep equipement")--

                    if st.session_state.selected_event and st.session_state.selected_event["title"].strip().lower() != "upkeep equipement": # Si la variable est non vide ouvre le dialog

                      show_event_dialog(st.session_state.selected_event)
                      st.session_state.selected_event=None # Remet à None après affichage 
                      st.session_state.edit_mode=False

                  else: 
                    # L'équipement est en panne : on bloque toute réservation
                    st.error("This equipment is currently out of service.")     


                  

# =============================================================================
# MODE ANNULATION
# =============================================================================
if st.session_state.mode == "annulation":
    st.title("❌ Cancel Reservation")

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


           
    # -------------------------------------------------------------------------
    # BLOC INSCRIPTION (identique au mode réservation)
    # -------------------------------------------------------------------------            
    if st.session_state.pending_email:

        st.info(
        "Your email address is not registered. Please complete your registration details."
    )

        with st.form("signup_form"):

          name = st.text_input("Please enter your first name")
          In = st.text_input("Enter your three-letter initials as defined by BBF")

          birthday_raw = st.text_input("Birthday (DD/MM/YYYY)", placeholder="DD/MM/YYYY")
          signup = st.form_submit_button("Sign up")

          if signup:

           if name and In:
            t1,t2=test_nom_valide(In)
            birthday, tb, birthday_msg = parse_birthday(birthday_raw)
            if not tb: # Date invalide (mauvais format, future, ou trop ancienne)
           
             st.error(birthday_msg)

            elif t1 and t2 :
             conn = sqlite3.connect("db/lab.db")
             c = conn.cursor()

             c.execute(
                "INSERT INTO users (nom, email,birthday, validation,intiales) VALUES (?, ?, ?,?,?)",
                (name, st.session_state.pending_email,birthday, 0,In.upper())
            )

             conn.commit()
             conn.close()

             # Notifie les admins "notification activee" (non bloquant).
             ok_mail, err_mail = notifier_admins_nouveau_user(
                 name, st.session_state.pending_email, In.upper()
             )
             if not ok_mail and err_mail != NOT_CONFIGURED:
                 st.caption(f"ℹ️ Admin notification email not sent ({err_mail})")

             st.success(
                "✅ Your email has been registered and is pending validation"
            )

             st.session_state.pending_email = None

             time.sleep(2)
             st.rerun()

            elif t1==True and t2==False :
                  st.error("An account with these initials already exists. Please check your initials.") 
            elif t1==False and t2==True:  
                   st.error("The initials must consist of 3 letters.") 
           else:

             st.warning("Please enter your first name and your initales")    
   # -------------------------------------------------------------------------
   # BLOC PRINCIPAL — Annulation
   # -------------------------------------------------------------------------
    if st.session_state.user_conn: 

    
                st.divider() #                 
                user_idd = st.session_state.user_idd
                user_name= st.session_state.user_name
                user_intiales = st.session_state.get("user_intiales") or user[5]
                
               
                conn = sqlite3.connect("db/lab.db")
                c = conn.cursor()

                c.execute("SELECT id, Nom, Numero_salle, Nom_salle, Categorie FROM equipements")
                equipements = c.fetchall()
                # --Sélecteurs de salle et de catégorie ---
                salles = {(e[2], e[3]) for e in equipements}
                categories = sorted({(e[4] if e[4] else "Uncategorized") for e in equipements})

                
                # --Sélecteurs de salle et de catégorie dans la sidebar -- 
                options = [""] + sorted(f"{i}-{j}" for i, j in salles)
                st.sidebar.divider()

                st.sidebar.markdown( ''' <div class="sidebar-section"     style="font-weight:bold; font-style:italic;">  EQUIPMENT</div>  ''',unsafe_allow_html=True)
                st.sidebar.markdown("<br>", unsafe_allow_html=True) 
                choice = st.sidebar.selectbox("Select the equipment room", options, index=0, key="room_select")
                choice_categorie = st.sidebar.selectbox("Filter by category", [""] + categories, index=0, key="categorie_select_cancel")
                # --Sélecteur d'équipement filtré par salle et/ou catégorie--
                filtered_eq = equipements
                if choice:
                    num = choice.split("-")[0]
                    nom_salle = choice.split("-")[1]
                    filtered_eq = [e for e in filtered_eq if str(e[2]) == num]
                if choice_categorie:
                    if choice_categorie == "Uncategorized":
                        filtered_eq = [e for e in filtered_eq if not e[4]]
                    else:
                        filtered_eq = [e for e in filtered_eq if e[4] == choice_categorie]

                if choice and choice_categorie:
                    equip_label = f"Equipment in room {nom_salle} — {choice_categorie}"
                elif choice:
                    equip_label = f"List of equipment in room {nom_salle}"
                elif choice_categorie:
                    equip_label = f"Equipment in category {choice_categorie}"
                else:
                    equip_label = "Choose equipment:"

                op = sorted(e[1] for e in filtered_eq)
                if not op:
                    st.sidebar.warning("No equipment matches the selected filters.")
                equipement_nom = st.sidebar.selectbox(
                    equip_label,
                    op,
                    key="equip_select_cancel"
                )
                # --Récupération de l'id de l'équipement choisie --
                st.sidebar.divider()
                # -- Nom du user + Bouton de déconnexion--
                col_name, col_btn = st.sidebar.columns([1, 1])
                with col_name:
                   user_name = st.session_state.get("user_name", "")
                   st.markdown(f"""<div style="display:flex; align-items:center; height:38px;">  <span style="background:var(--secondary-background-color);  color: var(--text-color); border-radius:8px; border: 1px solid var(--border-color); padding:6px 12px; font-size:15px;">👤 {user_name}</span></div>""", unsafe_allow_html=True)
                with col_btn:
                   
                   if st.button(" Log out", use_container_width=True, key="logout_sidebar"):
                      for key in list(st.session_state.keys()):
                          del st.session_state[key]
                      st.rerun()

                if not equipement_nom:
                    st.stop()
                equipement_id = [e[0] for e in equipements if e[1] == equipement_nom][0]
                # ---------------------------------------------------------------
                # CONSTRUCTION DES ÉVÉNEMENTS DU CALENDRIER (lecture seule)
                # ---------------------------------------------------------------
                c.execute("""
                    SELECT user, start_time, end_time
                    FROM reservations
                    WHERE equipement_id = ?
                """, (equipement_id,))

                reservations = c.fetchall()
                df_resa = pd.DataFrame(reservations, columns=["Nom", "Début", "Fin"])

                # --- BUILD EVENTS (comme réservation) ---
            
                events =[]
                for _, j in df_resa.iterrows():

                           start = pd.to_datetime(j["Début"])
                           end = pd.to_datetime(j["Fin"])

                           all_day = is_all_day(start, end)
                           

                           events.append({
                                     "title": j["Nom"],
                                     "start": start.isoformat() ,
                                     "end": end.isoformat() ,
                                     "allDay": all_day,
                                     
                                                })
                maintenance_events = get_maintenance_events(equipement_id,datetime.now() - timedelta(days=30), datetime.now() + timedelta(days=180)
)

                all_events= events+maintenance_events
                    

                
                        
                # Calendrier en lecture seule (editable et selectable à False)
                calendar_options = {
                    "initialView": "dayGridMonth",
                    "headerToolbar": {
                        "left": "prev,next today",
                        "center": "title",
                        "right": "dayGridMonth,timeGridWeek,timeGridDay"
                    },
                    "slotMinTime": "00:00:00",
                    "slotMaxTime": "24:00:00",
                    "locale": "en",
                    "timeZone": "Europe/Paris",
                    "height": 800,
                    "scrollTime": "07:00:00",
                    "eventTimeFormat": { "hour": "2-digit","minute": "2-digit","hour12": False},
                    "editable": False,
                    "selectable": False,
                    "allDaySlot": True,
                }

                st.markdown(f"### Schedule for {equipement_nom}")

                cal = st_calendar(events=all_events, options=calendar_options)

                 # ---------------------------------------------------------------
                 # DIALOG : Confirmation d'annulation
                 # ---------------------------------------------------------------
                if "to_delete" not in st.session_state: #Initialisation de la variable de l'evenement sélectinné si elle n'exite pas encore dans la session
                 st.session_state.to_delete = None
                
                @st.dialog("❌ Confirm cancellation")
                def show_cancel_event(ev):    
                   # ---------------------------------------------------------------
                   # Dialog de confirmation avant suppression d'une réservation.
                   # Contrôles :
                      #- Seul le propriétaire (ou un admin) peut annuler une réservation.
                      # -Après suppression, les compteurs de fonctionnement sont mis à jour.
                      #-Un message est ajouté dans l'historique.
                   # ---------------------------------------------------------------   


                 st.warning(f"""
                    You selected:
                    - User: {ev['title']}
                    - From: {ev['start']}
                    - To: {ev['end']}
                    """)
                

                 if st.button("🗑️ Confirm cancellation", key=f"delete_{equipement_id}_{ev['start']}"):
                        #-- Normalisation du format datetime pour la requête SQL--
                        start_db = ev["start"] if "T" in ev["start"] else ev["start"] + "T00:00:00"
                        end_db = ev["end"] if "T" in ev["end"] else ev["end"] + "T00:00:00"
                       
                        if (ev["title"].strip().lower() == user_intiales.strip().lower()) or user_admin: # Controle de qui supprime la réservation

                            conn = sqlite3.connect("db/lab.db")
                            c = conn.cursor()

                            # Suppression de la réservation
                            c.execute("""
                                DELETE FROM reservations
                                WHERE equipement_id = ?
                                AND user = ?
                                AND start_time = ?
                                AND end_time = ?
                            """, (
                                equipement_id,
                                ev["title"],
                                start_db,
                                end_db
                            ))
                           #-- Recalcul des heures de fonctionnement après suppression--
                            c.execute(
                                              """
                                              SELECT start_time, end_time
                                              FROM reservations 
                                              WHERE equipement_id = ?
                                              """,
                                                (equipement_id,)
                                                                )
                            all_resa = c.fetchall()
                            c.execute(
                                              """
                                              SELECT Date_maintenance 
                                              FROM equipements
                                              WHERE id = ?
                                              """,
                                                (equipement_id,)
                                                                )
                            date=c.fetchall()
                                
                            date_str=date[0][0]
                            df_all = pd.DataFrame(all_resa, columns=["Début", "Fin"])
                            # --Historique de l'annulation--
                            no=datetime.now().isoformat()
                            salle = [e[3] for e in equipements if e[0] == equipement_id][0]
                            start = datetime.fromisoformat(start_db)
                            end = datetime.fromisoformat(end_db)
                            prénom=ev["title"]
                              

   
                            h= f"Une réservation au nom de {prénom} pour l’équipement {equipement_nom}, du {start} au {end}, dans la salle {salle}, a été annulée par {user_name} ({user_intiales})."
                            c.execute(
                                                 """
                                                 INSERT INTO history (history,date) VALUES(?,?)
                                                
                                                 """,
                                                    (h,no)
                                                                                         )
                             #-- Mise à jour des compteurs de fonctionnement --
                            temps_fonctionnement_installation,temps_fct_maintenance = calcul_temps_fonctionnement(df_all,date_str)
                            c.execute(
                                                 """
                                                 UPDATE equipements
                                                 SET Nombre_heure_fct_depuis_installation = ?,Nombre_heures_fct_depuis_maintenance=?
                                                 WHERE id = ?
                                                 """,
                                                    (temps_fonctionnement_installation,temps_fct_maintenance, equipement_id)
                                                                                     )
                            conn.commit()
                            conn.close()
                            st.success("✅ Reservation cancelled")
                            st.session_state.to_delete = None
                            time.sleep(2)
                            st.rerun()

                        else:
                            st.error("You can only delete your own reservations.")
                # -- Capture du clic sur un événement pour déclencher le dialog d'annulation --           
                if cal.get("eventClick"):
                    event = cal["eventClick"]["event"]

                    st.session_state.to_delete = {
                        "title": event["title"],
                        "start": event["start"],
                        "end":event["end"],
                    }
                # --Ouverture du dialog (on exclut les événements de maintenance)--   
                if st.session_state.to_delete and st.session_state.to_delete["title"].strip().lower() != "upkeep equipement":
                     show_cancel_event(st.session_state.to_delete)
                     st.session_state.to_delete=None
                    

                
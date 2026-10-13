import streamlit as st
import sqlite3
import pandas as pd
import base64
from datetime import datetime, timedelta
from streamlit_calendar import calendar as st_calendar

# =============================================================================
# INITIALISATION DU SESSION STATE
# (mêmes clés que les autres pages, pour rester cohérent si l'utilisateur
# arrive directement sur cette page avant d'avoir visité les autres)
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
    st.session_state.admin_verified = False
if "awaiting_admin_password" not in st.session_state:
    st.session_state.awaiting_admin_password = False
if "email_to_verify" not in st.session_state:
    st.session_state.email_to_verify = None
if "cat_view_selected_event" not in st.session_state:
    st.session_state.cat_view_selected_event = None
if "cat_view_last_click_sig" not in st.session_state:
    st.session_state.cat_view_last_click_sig = None

# =============================================================================
# CONFIGURATION DE LA PAGE STREAMLIT
# =============================================================================
st.set_page_config(
    page_title="SNAKE",
    page_icon="🐍",
    layout="wide"
)

# =============================================================================
# CSS PERSONNALISÉ (identique aux autres pages)
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
# =============================================================================
st.sidebar.page_link("app.py",                              label="🏠 Home")
st.sidebar.page_link("pages/1_Reservation-Annulation.py",   label="📅 Reservation / Cancellation")
st.sidebar.page_link("pages/2_Category_View.py",            label="🗂️ Category view")
st.sidebar.page_link("pages/3_Admin.py",                    label="⚙️ Admin")

# =============================================================================
# FONCTIONS UTILITAIRES
# (dupliquées depuis 1_Reservation-Annulation.py pour rester indépendant :
#  importer cette page comme module réexécuterait tout son code Streamlit)
# =============================================================================

def is_all_day(start, end):
    # Détermine si un créneau correspond à une réservation "toute la journée".
    start = pd.to_datetime(start)
    end = pd.to_datetime(end)
    duration = end - start
    return (
        start.hour == 0 and start.minute == 0 and
        end.hour == 0 and end.minute == 0 and
        duration.days >= 1
    )

def get_maintenance_events(equipement_id, start_range, end_range):
    # Génère les événements de maintenance périodique d'un équipement,
    # filtrés dans la plage de dates [start_range, end_range].
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
    while current <= end_range:
        if current >= start_range:
            events.append({
                "title": "Upkeep equipement",
                "start": current.isoformat(),
                "end": (current + timedelta(days=1)).isoformat(),
                "eventDisplay": "background",
                "color": "#d3d3d3",
            })
        current = current + timedelta(days=period)

    return events

# =============================================================================
# ACCÈS RÉSERVÉ AUX UTILISATEURS CONNECTÉS
# (on ne redemande pas de login ici : le session_state est partagé entre
#  toutes les pages d'une même session Streamlit)
# =============================================================================
if not st.session_state.user_conn:
    st.info("👋 Please log in from the **Reservation / Cancellation** page first.")
    st.stop()

st.divider()

# --Nom du user + Bouton de déconnexion dans la sidebar (identique aux autres pages)--
col_name, col_btn = st.sidebar.columns([1, 1])
with col_name:
    user_name = st.session_state.get("user_name", "")
    st.markdown(f"""<div style="display:flex; align-items:center; height:38px;">  <span style="background:var(--secondary-background-color); color: var(--text-color); border-radius:8px; border: 1px solid var(--border-color); padding:6px 12px; font-size:15px;">👤 {user_name}</span></div>""", unsafe_allow_html=True)
with col_btn:
    if st.button(" Log out", use_container_width=True, key="logout_sidebar_cat"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

st.title("🗂️ Category view")
st.caption("See every piece of equipment in a category on the same calendar. This view is read-only — book a slot from the Reservation page.")
st.markdown(
    """
    <div style="display:flex; gap:24px; align-items:center; margin-top:-4px; margin-bottom:10px; font-size:13px; color:gray;">
        <span>🟢 In service</span>
        <span>🔴 Out of service</span>
    </div>
    """,
    unsafe_allow_html=True
)

# =============================================================================
# SÉLECTEURS : catégorie (obligatoire) + salle (filtre optionnel)
# =============================================================================
conn = sqlite3.connect("db/lab.db")
c = conn.cursor()

c.execute("SELECT DISTINCT Categorie FROM equipements")
cats_raw = [r[0] for r in c.fetchall()]
categories = sorted({(cat if cat else "Uncategorized") for cat in cats_raw})

st.sidebar.divider()
st.sidebar.markdown('''<div class="sidebar-section" style="font-weight:bold; font-style:italic;">CATEGORY VIEW</div>''', unsafe_allow_html=True)
st.sidebar.markdown("<br>", unsafe_allow_html=True)

choice_categorie = st.sidebar.selectbox("Select a category", [""] + categories, index=0, key="cat_view_select")

if not choice_categorie:
    conn.close()
    st.info("Select a category in the sidebar to see all of its equipment on one calendar.")
    st.stop()

if choice_categorie == "Uncategorized":
    c.execute("SELECT id, Nom, Numero_salle, Nom_salle, Etat FROM equipements WHERE Categorie IS NULL")
else:
    c.execute("SELECT id, Nom, Numero_salle, Nom_salle, Etat FROM equipements WHERE Categorie = ?", (choice_categorie,))

eq_in_cat = sorted(c.fetchall(), key=lambda e: e[1].lower())

if not eq_in_cat:
    conn.close()
    st.info("No equipment found for this category.")
    st.stop()

# --Filtre optionnel par salle, limité aux salles présentes dans la catégorie--
rooms_in_cat = sorted({(e[2], e[3]) for e in eq_in_cat if e[2]})
room_options = ["All rooms"] + [f"{num}-{name}" for num, name in rooms_in_cat]
choice_room = st.sidebar.selectbox("Filter by room (optional)", room_options, index=0, key="cat_view_room")

if choice_room != "All rooms":
    num_filter = choice_room.split("-")[0]
    eq_in_cat = [e for e in eq_in_cat if str(e[2]) == num_filter]

if not eq_in_cat:
    conn.close()
    st.info("No equipment found for this category and room.")
    st.stop()

# =============================================================================
# CONSTRUCTION DES RESSOURCES ET DES ÉVÉNEMENTS
# ressource FullCalendar = un équipement -> une ligne du calendrier
# =============================================================================
resources = []
events = []

for eq_id, eq_nom, num_salle, nom_salle, etat in eq_in_cat:
    label = eq_nom
    if etat and etat.strip().lower() == "panne":
        label = f"{eq_nom} 🔴"  # signale visuellement un équipement en panne, en suffixe pour ne pas casser le tri alphabétique
    elif etat and etat.strip().lower() == "marche":
        label = f"{eq_nom} 🟢"  # signale visuellement un équipement en service
    resources.append({"id": str(eq_id), "title": label})

    c.execute("""
        SELECT user, start_time, end_time, comment, project
        FROM reservations
        WHERE equipement_id = ?
    """, (eq_id,))

    for user_i, start_s, end_s, comment, project in c.fetchall():
        start = pd.to_datetime(start_s)
        end = pd.to_datetime(end_s)
        events.append({
            "resourceId": str(eq_id),
            "title": user_i,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "allDay": is_all_day(start, end),
            "color": "#6366f1",
            "extendedProps": {
                "kind": "reservation",
                "equipment": eq_nom,
                "comment": comment,
                "project": project,
            },
        })

    maintenance_events = get_maintenance_events(
        eq_id, datetime.now() - timedelta(days=30), datetime.now() + timedelta(days=180)
    )
    for m in maintenance_events:
        m["resourceId"] = str(eq_id)
        m["extendedProps"] = {"kind": "maintenance", "equipment": eq_nom}
        events.append(m)

conn.close()

# =============================================================================
# CONFIGURATION ET AFFICHAGE DU CALENDRIER RESSOURCES (lecture seule)
# =============================================================================
calendar_options = {
    # Nécessaire pour activer les vues "resource*" de FullCalendar Scheduler.
    # Cette clé supprime le bandeau d'essai pour un usage interne/non-commercial.
    # Voir https://fullcalendar.io/license si l'appli est un jour distribuée
    # commercialement.
    "schedulerLicenseKey": "CC-Attribution-NonCommercial-NoDerivatives",
    "initialView": "resourceTimelineWeek",
    "headerToolbar": {
        "left": "prev,next today",
        "center": "title",
        "right": "resourceTimelineDay,resourceTimelineWeek,resourceTimelineMonth"
    },
    "resourceAreaHeaderContent": "Equipment",
    "resourceAreaWidth": "260px",
    "resources": resources,
    "resourceOrder": "title",  # tri alphanumérique forcé sur le nom affiché, quel que soit l'ordre du tableau "resources"
    "slotMinTime": "00:00:00",
    "slotMaxTime": "24:00:00",
    "locale": "en",
    "timeZone": "Europe/Paris",
    "firstDay":1,
    "height": 800,
    "scrollTime": "07:00:00",
    "eventTimeFormat": {"hour": "2-digit", "minute": "2-digit", "hour12": False},
    "editable": False,
    "selectable": False,
    "allDaySlot": True,
    # Vue "week" en créneaux de demi-journée plutôt qu'heure par heure.
    # (Day garde sa granularité horaire habituelle ; Month affiche un jour par colonne.)
    "views": {
        "resourceTimelineWeek": {
            "slotDuration": "12:00:00",
            "slotLabelFormat": [
                {"weekday": "short", "day": "numeric", "month": "short"},
                {"hour": "numeric", "hour12": True, "meridiem": "short"},
            ],
        }
    },
}

st.markdown(f"### {choice_categorie} — {len(resources)} equipment item(s)")

# Remplace le texte généré "12 AM" / "12 PM" par "Morning" / "Afternoon"
# dans l'en-tête de la vue semaine. FullCalendar ne permet pas de texte
# personnalisé via ses options JSON (seulement via un callback JS), donc
# on masque le texte d'origine et on le remplace en CSS via ::after,
# repéré sur l'horodatage exact du créneau (00:00 / 12:00).
category_view_css = """
/* Les noms d'équipement longs passent à la ligne plutôt que d'être tronqués. */
.fc-datagrid-cell-cushion {
    white-space: normal !important;
    overflow-wrap: break-word;
    line-height: 1.25;
}
.fc-datagrid-cell-frame {
    height: auto !important;
}
/* data-date vaut ici "2026-08-25T00:00:00" (FullCalendar force omitTimeZoneOffset),
   donc on teste "contient" (*=) et pas "se termine par" ($=). Le scope
   .fc-timeline-header-row-chrono évite de toucher la ligne "Mon 25 Aug" du haut. */
.fc-resourceTimelineWeek-view .fc-timeline-header-row-chrono .fc-timeline-slot[data-date*="T00:00:00"] .fc-timeline-slot-cushion,
.fc-resourceTimelineWeek-view .fc-timeline-header-row-chrono .fc-timeline-slot[data-date*="T12:00:00"] .fc-timeline-slot-cushion {
    font-size: 0;
}
.fc-resourceTimelineWeek-view .fc-timeline-header-row-chrono .fc-timeline-slot[data-date*="T00:00:00"] .fc-timeline-slot-cushion::after {
    content: "Morning";
    font-size: 11px;
}
.fc-resourceTimelineWeek-view .fc-timeline-header-row-chrono .fc-timeline-slot[data-date*="T12:00:00"] .fc-timeline-slot-cushion::after {
    content: "Afternoon";
    font-size: 11px;
}
"""

cal = st_calendar(events=events, options=calendar_options, custom_css=category_view_css, key="cat_calendar")

# =============================================================================
# DIALOG : détails d'un événement (lecture seule, pas d'annulation possible ici)
# =============================================================================
@st.dialog("📋 Booking details")
def show_event_details(ev):
    props = ev.get("extendedProps", {}) or {}
    start_fmt = pd.to_datetime(ev["start"]).strftime("%d/%m/%Y - %H:%M")
    end_fmt = pd.to_datetime(ev["end"]).strftime("%d/%m/%Y - %H:%M")
    if props.get("kind") == "maintenance":
        st.warning(f"""
**Scheduled maintenance**
- Equipment: {props.get('equipment', '—')}
- From: {start_fmt}
- To: {end_fmt}
""")
    else:
        st.info(f"""
- Equipment: {props.get('equipment', '—')}
- Booked by: {ev['title']}
- From: {start_fmt}
- To: {end_fmt}
- Project: {props.get('project') or '—'}
- Comment: {props.get('comment') or '—'}
""")
    st.caption("This view is read-only. To cancel a reservation, use the Reservation / Cancellation page.")
    
# --Détection d'un NOUVEAU clic-------------------------------------------
# streamlit-calendar continue de renvoyer le dernier "eventClick" tant qu'aucun
# nouveau clic n'a eu lieu côté frontend. Sans cette vérification, fermer la
# pop-up (bouton "Close" -> st.rerun()) relit ce même clic "périmé" et
# rouvre aussitôt la pop-up : le bouton "Close" semble ne rien faire.
# On ne réagit donc qu'aux clics dont la signature diffère du dernier traité.
event_click = cal.get("eventClick")
if event_click:
    ev = event_click["event"]
    click_sig = (ev.get("start"), ev.get("end"), ev.get("title"))
    st.session_state.cat_view_selected_event = ev

if st.session_state.cat_view_selected_event:
    show_event_details(st.session_state.cat_view_selected_event)
    st.session_state.cat_view_selected_event = None

import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from streamlit_calendar import calendar as st_calendar

# =============================================================================
# PAGE PUBLIQUE, LECTURE SEULE — pensée pour être consultée depuis un téléphone
# (via un tunnel Tailscale) séparément de l'application interne, qui reste
# sur le réseau du laboratoire.
#
# Différences volontaires avec pages/2_Category_View.py :
#   - Aucune authentification, aucune donnée de session utilisateur.
#   - Connexion SQLite en mode "ro" (read-only) : ce process ne peut
#     physiquement pas écrire dans la base, même en cas de bug.
#   - Pas de projet affiché dans les détails d'une réservation (uniquement
#     l'utilisateur, l'équipement et le créneau). Le commentaire est
#     également masqué par précaution, puisque ce champ est du texte libre
#     qui peut contenir autre chose que prévu — à réactiver si besoin.
#   - Mise en page pensée mobile d'abord : layout centré, filtres dans la
#     page plutôt que dans une sidebar (masquée sur mobile par défaut),
#     vue "jour" par défaut pour limiter le défilement horizontal initial.
#
# Lancement (depuis le même dossier que app.py, pour que "db/lab.db" et
# le logo soient trouvés) :
#   streamlit run public_schedule.py --server.port 8502
# =============================================================================

if "pub_selected_event" not in st.session_state:
    st.session_state.pub_selected_event = None
if "pub_last_click_sig" not in st.session_state:
    st.session_state.pub_last_click_sig = None

# =============================================================================
# CONFIGURATION DE LA PAGE STREAMLIT (centrée : plus adaptée aux écrans étroits)
# =============================================================================
st.set_page_config(
    page_title="SNAKE — Schedule",
    page_icon="🐍",
    layout="centered"
)

st.markdown("""
    <style>
        #MainMenu {visibility: hidden;}
        header {visibility: hidden;}
        footer {visibility: hidden;}
        [data-testid="stSidebarNav"] {display: none;}
        [data-testid="stSidebar"] {display: none;}
        .block-container {
            padding-top: 1.2rem !important;
            padding-left: 0.8rem !important;
            padding-right: 0.8rem !important;
        }
    </style>
""", unsafe_allow_html=True)

# =============================================================================
# LOGO (facultatif : ne bloque pas la page si le fichier est absent)
# =============================================================================
import base64
import os

if os.path.exists("Logo_3_simplet.png"):
    with open("Logo_3_simplet.png", "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()
    st.markdown(f"""
        <div style="text-align:center; margin-bottom:8px;">
            <img src="data:image/png;base64,{img_b64}" style="max-width:420px; width:90%; display:inline-block;" />
        </div>
    """, unsafe_allow_html=True)

st.title("📅 Equipment schedule")
st.caption("Read-only view, for information only — to book equipment, use the internal app from the lab network.")
st.markdown(
    """
    <div style="display:flex; gap:20px; align-items:center; margin-top:-4px; margin-bottom:10px; font-size:13px; color:gray;">
        <span>🟢 In service</span>
        <span>🔴 Out of service</span>
    </div>
    """,
    unsafe_allow_html=True
)

# =============================================================================
# FONCTIONS UTILITAIRES (connexion en lecture seule uniquement)
# =============================================================================

def get_ro_connection():
    # mode=ro : la connexion ne peut pas écrire dans le fichier, même par erreur.
    return sqlite3.connect("file:db/lab.db?mode=ro", uri=True)

def is_all_day(start, end):
    start = pd.to_datetime(start)
    end = pd.to_datetime(end)
    duration = end - start
    return (
        start.hour == 0 and start.minute == 0 and
        end.hour == 0 and end.minute == 0 and
        duration.days >= 1
    )

def get_maintenance_events(equipement_id, start_range, end_range):
    conn = get_ro_connection()
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
# SÉLECTEUR : catégorie (obligatoire), affiché dans la page (pas la sidebar,
# masquée par défaut sur mobile)
# =============================================================================
conn = get_ro_connection()
c = conn.cursor()

c.execute("SELECT DISTINCT Categorie FROM equipements")
cats_raw = [r[0] for r in c.fetchall()]
categories = sorted({(cat if cat else "Uncategorized") for cat in cats_raw})

choice_categorie = st.selectbox("Filter by category", [""] + categories, index=0, key="pub_cat_select")

if not choice_categorie:
    conn.close()
    st.info("Select a category above to see its equipment schedule.")
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

# =============================================================================
# CONSTRUCTION DES RESSOURCES ET DES ÉVÉNEMENTS
# =============================================================================
resources = []
events = []

for eq_id, eq_nom, num_salle, nom_salle, etat in eq_in_cat:
    label = eq_nom
    if etat and etat.strip().lower() == "panne":
        label = f"{eq_nom} 🔴"
    elif etat and etat.strip().lower() == "marche":
        label = f"{eq_nom} 🟢"
    resources.append({"id": str(eq_id), "title": label})

    c.execute("""
        SELECT user, start_time, end_time
        FROM reservations
        WHERE equipement_id = ?
    """, (eq_id,))

    for user_i, start_s, end_s in c.fetchall():
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
# CONFIGURATION ET AFFICHAGE DU CALENDRIER (lecture seule, pensé mobile)
# =============================================================================
calendar_options = {
    "schedulerLicenseKey": "CC-Attribution-NonCommercial-NoDerivatives",
    "initialView": "resourceTimelineDay",  # vue la plus lisible au premier chargement sur téléphone
    "headerToolbar": {
        "left": "prev,next today",
        "center": "title",
        "right": "resourceTimelineDay,resourceTimelineWeek,resourceTimelineMonth"
    },
    "resourceAreaHeaderContent": "Equipment",
    "resourceAreaWidth": "150px",  # largeur fixe, un peu plus large pour éviter la troncature des noms
    "resources": resources,
    "resourceOrder": "title",
    "slotMinTime": "00:00:00",
    "slotMaxTime": "24:00:00",
    "firstDay":1,
    "locale": "en",
    "timeZone": "Europe/Paris",
    "height": 650,
    "scrollTime": "07:00:00",
    "eventTimeFormat": {"hour": "2-digit", "minute": "2-digit", "hour12": False},
    "editable": False,
    "selectable": False,
    "allDaySlot": True,
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

st.markdown(f"#### {choice_categorie} — {len(resources)} equipment item(s)")

# Police plus petite dans l'ensemble du calendrier (écran de téléphone étroit) :
# FullCalendar utilise des unités "em" en cascade, donc réduire la taille sur
# ".fc" réduit aussi proportionnellement les noms d'équipement, les titres
# d'événement, et le texte "Morning"/"Afternoon" défini plus bas.
public_schedule_css = """
/* Les noms d'équipement longs passent à la ligne plutôt que d'être tronqués. */
.fc-datagrid-cell-cushion {
    white-space: normal !important;
    overflow-wrap: break-word;
    line-height: 1.25;
}
.fc-datagrid-cell-frame {
    height: auto !important;
}
.fc {
    font-size: 0.78em;
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

cal = st_calendar(events=events, options=calendar_options, custom_css=public_schedule_css, key="public_calendar")

# =============================================================================
# DIALOG : détails d'un événement (utilisateur + équipement + créneau uniquement)
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
""")
   
# Même garde-fou anti-clic périmé que sur Category View (cf. ce fichier).
event_click = cal.get("eventClick")
if event_click:
    ev = event_click["event"]
    click_sig = (ev.get("start"), ev.get("end"), ev.get("title"))
    
       
    st.session_state.pub_selected_event = ev

if st.session_state.pub_selected_event:
    show_event_details(st.session_state.pub_selected_event)
    st.session_state.pub_selected_event = None

# =============================================================================
# email_utils.py
# -----------------------------------------------------------------------------
# Envoi d'emails de notification (SMTP, gratuit) :
#   - notifier_admins_nouveau_user(...) : previent les admins qu'un nouveau
#     profil est en attente de validation.
#   - notifier_user_valide(...)         : previent l'utilisateur qu'il vient
#     d'etre valide par un admin.
#
# Conception : AUCUNE de ces fonctions ne leve d'exception. En cas de probleme
# (config absente, SMTP injoignable, etc.) elles renvoient (False, "message")
# et l'application continue normalement (inscription / validation non bloquees).
#
# Configuration attendue dans .streamlit/secrets.toml :
#
#   [email]
#   smtp_host   = "smtp.gmail.com"
#   smtp_port   = 587
#   sender      = "mon.adresse@gmail.com"
#   password    = "xxxx xxxx xxxx xxxx"     # mot de passe d'application Google
#   sender_name = "SNAKE - Reservation Lab" # optionnel
#   app_url     = "https://mon-app.streamlit.app"  # optionnel (lien dans le mail)
# =============================================================================

import smtplib
import ssl
import sqlite3
from email.message import EmailMessage

try:
    import streamlit as st
except Exception:  # pragma: no cover - streamlit est toujours present ici
    st = None

DB_PATH = "db/lab.db"

# Code renvoye quand la section [email] de secrets.toml est absente/incomplete.
# Les appelants s'en servent pour rester SILENCIEUX tant que rien n'est configure.
NOT_CONFIGURED = "not_configured"


def _get_config():
    """
    Lit la section [email] de st.secrets.

    Retourne
    --------
    dict | None : la config si elle est complete, None sinon.
    """
    if st is None:
        return None
    try:
        raw = st.secrets["email"]
    except Exception:
        # Pas de fichier secrets, ou pas de section [email]
        return None

    try:
        cfg = {
            "smtp_host": str(raw["smtp_host"]).strip(),
            "smtp_port": int(raw["smtp_port"]),
            "sender": str(raw["sender"]).strip(),
            "password": str(raw["password"]),
        }
    except Exception:
        return None

    if not cfg["smtp_host"] or not cfg["sender"] or not cfg["password"]:
        return None

    cfg["sender_name"] = str(raw["sender_name"]).strip() if "sender_name" in raw else "SNAKE"
    cfg["app_url"] = str(raw["app_url"]).strip() if "app_url" in raw else ""
    return cfg


def _send(to_addr, subject, body, cfg=None):
    """
    Envoie un email texte simple a une adresse.

    Retourne
    --------
    (bool, str) : (True, "") si envoye, (False, "raison") sinon.
    Ne leve jamais d'exception.
    """
    cfg = cfg or _get_config()
    if cfg is None:
        return False, NOT_CONFIGURED
    if not to_addr:
        return False, "Adresse destinataire vide."

    msg = EmailMessage()
    msg["From"] = f"{cfg['sender_name']} <{cfg['sender']}>"
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(cfg["smtp_host"], cfg["smtp_port"], timeout=15) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(cfg["sender"], cfg["password"])
            server.send_message(msg)
        return True, ""
    except Exception as e:
        return False, f"Echec envoi SMTP : {e}"


def _admins_a_notifier():
    """
    Retourne la liste (nom, email) des admins dont notification = 1.
    Tolerant : si la colonne n'existe pas encore, renvoie [].
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT name_admin, email FROM admin WHERE notification = 1 AND email IS NOT NULL")
        rows = c.fetchall()
        conn.close()
    except Exception:
        return []
    return [(r[0], r[1]) for r in rows if r[1]]


def notifier_admins_nouveau_user(nom, email, initiales=""):
    """
    Previent tous les admins "notification activee" qu'un nouveau profil
    utilisateur est en attente de validation.

    Retourne
    --------
    (bool, str) : (True, "") si au moins un email est parti,
                  (False, "raison") sinon.
    """
    cfg = _get_config()
    if cfg is None:
        return False, NOT_CONFIGURED

    destinataires = _admins_a_notifier()
    if not destinataires:
        return False, "Aucun admin avec la notification activee."

    lien = f"\n\nValidation : {cfg['app_url']}" if cfg["app_url"] else ""
    subject = "Nouveau profil a valider - SNAKE"
    body = (
        "Bonjour,\n\n"
        "Un nouvel utilisateur vient de s'inscrire et attend votre validation :\n\n"
        f"  Nom      : {nom}\n"
        f"  Email    : {email}\n"
        f"  Initiales: {initiales}\n\n"
        "Rendez-vous dans la page Admin > Gestion des utilisateurs pour le valider."
        f"{lien}\n\n"
        "-- Notification automatique SNAKE"
    )

    envoyes = 0
    dernier_err = ""
    for _, adr in destinataires:
        ok, err = _send(adr, subject, body, cfg=cfg)
        if ok:
            envoyes += 1
        else:
            dernier_err = err

    if envoyes:
        return True, ""
    return False, dernier_err or "Aucun email envoye."


def notifier_user_valide(nom, email):
    """
    Previent l'utilisateur que son profil vient d'etre valide.

    Retourne
    --------
    (bool, str)
    """
    cfg = _get_config()
    if cfg is None:
        return False, NOT_CONFIGURED

    lien = f"\n\nAcces a l'application : {cfg['app_url']}" if cfg["app_url"] else ""
    subject = "Your profil has been validated - SNAKE"
    body = (
        f"Hello {nom},\n\n"
        "Your profile has been validated by an administrator.\n"
        "You can now log in and make your reservations."
        f"{lien}\n\n"
        "-- Automatic notification from SNAKE"
    )
    return _send(email, subject, body, cfg=cfg)

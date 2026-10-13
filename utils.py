import qrcode
import os
import json
import tomllib



# =============================================================================
# QR code de la page publique (public_schedule.py)
# -----------------------------------------------------------------------------
# L'URL Tailscale de la page publique est lue dans .streamlit/secrets.toml
# (section [public_schedule], cle "url") pour ne pas apparaitre dans le code
# publie. On peut aussi la passer en argument. Le QR code est regenere
# automatiquement au prochain appel si l'URL a change ; sinon rien n'est reecrit.
# =============================================================================
SECRETS_PATH = ".streamlit/secrets.toml"


def read_public_schedule_url(secrets_path=SECRETS_PATH):
    """Renvoie l'URL de la page publique lue dans secrets.toml, ou None."""
    try:
        with open(secrets_path, "rb") as f:
            return tomllib.load(f).get("public_schedule", {}).get("url") or None
    except (OSError, tomllib.TOMLDecodeError):
        return None


def generate_public_schedule_qr(url=None, out_path="assets/qr_public_schedule.png"):
    """
    Genere le QR code pointant vers la page publique, UNIQUEMENT si l'URL a
    change depuis la derniere generation (ou si l'image n'existe pas encore).

    La derniere URL encodee est memorisee dans un fichier JSON place a cote de
    l'image (ex : assets/qr_public_schedule.json).

    Parametres
    ----------
    url : str | None
        URL a encoder. Si None, utilise l'URL de secrets.toml.
    out_path : str
        Chemin du PNG a ecrire.

    Retourne
    --------
    (str, bool) : (chemin du PNG, True si (re)genere / False si deja a jour)
    """
    url = url or read_public_schedule_url()
    if not url:
        raise ValueError(
            "URL de la page publique introuvable : renseigner [public_schedule] url "
            "dans .streamlit/secrets.toml ou la passer en argument."
        )
    url = url.strip()
    record_path = os.path.splitext(out_path)[0] + ".json"

    last_url = None
    if os.path.exists(record_path):
        try:
            with open(record_path, "r", encoding="utf-8") as f:
                last_url = json.load(f).get("url")
        except (OSError, ValueError):
            last_url = None

    # URL inchangee et image deja presente -> on ne regenere pas
    if last_url == url and os.path.exists(out_path):
        return out_path, False

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    img = qrcode.make(url)
    img.save(out_path)
    with open(record_path, "w", encoding="utf-8") as f:
        json.dump({"url": url}, f)

    return out_path, True

import qrcode
import os
import json

    

# =============================================================================
# QR code de la page publique (public_schedule.py)
# -----------------------------------------------------------------------------
# Coller la nouvelle valeur de L'url dans
# PUBLIC_SCHEDULE_URL ci-dessous (ou la passer en argument) : le QR code sera
# regenere automatiquement au prochain appel. Tant que l'URL est identique,
# la fonction ne reecrit rien.
# =============================================================================
PUBLIC_SCHEDULE_URL = "https://enforcement-art-badge-announces.trycloudflare.com/"


def generate_public_schedule_qr(url=None, out_path="assets/qr_public_schedule.png"):
    """
    Genere le QR code pointant vers la page publique, UNIQUEMENT si l'URL a
    change depuis la derniere generation (ou si l'image n'existe pas encore).

    La derniere URL encodee est memorisee dans un fichier JSON place a cote de
    l'image (ex : assets/qr_public_schedule.json).

    Parametres
    ----------
    url : str | None
        URL a encoder. Si None, utilise PUBLIC_SCHEDULE_URL.
    out_path : str
        Chemin du PNG a ecrire.

    Retourne
    --------
    (str, bool) : (chemin du PNG, True si (re)genere / False si deja a jour)
    """
    url = (url or PUBLIC_SCHEDULE_URL).strip()
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

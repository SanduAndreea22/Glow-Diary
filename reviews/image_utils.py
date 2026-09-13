import io
import logging

from django.core.files.base import ContentFile
from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

MAX_DIMENSIUNE_IMPLICITA = 1600


def optimizeaza_poza(camp_fisier, max_dimensiune=MAX_DIMENSIUNE_IMPLICITA):
    """Redimensionează o poză abia încărcată (nu una deja salvată — vezi
    `_committed`) dacă depășește `max_dimensiune` pe latura lungă. O poză
    de telefon de câțiva MB nu are rost servită la rezoluție completă doar
    pentru un thumbnail de 140px; no-op ieftin dacă e deja suficient de
    mică. Mutăm doar conținutul din memorie — Django își salvează singur
    fișierul (deja redimensionat) în storage, la finalul save()-ului
    modelului, deci nu riscăm fișiere orfane duplicate."""
    if not camp_fisier or getattr(camp_fisier, "_committed", True):
        return
    try:
        camp_fisier.seek(0)
        imagine = Image.open(camp_fisier)
        format_imagine = (imagine.format or "JPEG").upper()
        if max(imagine.size) <= max_dimensiune:
            camp_fisier.seek(0)
            return

        # exif_transpose ABIA aici (nu și pe calea "deja mică") — Pillow nu
        # păstrează automat orientarea EXIF la un nou save(), așa că fără
        # asta o poză de telefon ținută pe verticală ar ieși rotită greșit.
        imagine = ImageOps.exif_transpose(imagine)
        raport = max_dimensiune / float(max(imagine.size))
        dimensiune_noua = (round(imagine.width * raport), round(imagine.height * raport))
        imagine = imagine.resize(dimensiune_noua, Image.LANCZOS)

        opțiuni_salvare = {}
        if format_imagine == "JPEG":
            if imagine.mode in ("RGBA", "P"):
                imagine = imagine.convert("RGB")
            opțiuni_salvare = {"quality": 85, "optimize": True}
        elif format_imagine == "PNG":
            opțiuni_salvare = {"optimize": True}

        buffer = io.BytesIO()
        imagine.save(buffer, format=format_imagine, **opțiuni_salvare)
        camp_fisier.file = ContentFile(buffer.getvalue())
    except Exception:
        # O poză care nu poate fi procesată (fișier corupt, format neașteptat)
        # nu trebuie să blocheze salvarea produsului — mai bine poza
        # originală, nedimensionată, decât un 500 la adăugarea unui produs.
        logger.warning(
            "Nu am putut redimensiona poza %s.",
            getattr(camp_fisier, "name", "?"), exc_info=True,
        )
        try:
            camp_fisier.seek(0)
        except Exception:
            pass

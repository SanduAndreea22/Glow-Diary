import io
import logging

from django.core.files.base import ContentFile
from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

MAX_DIMENSIUNE_IMPLICITA = 1600

# Prag de pixeli decodați, verificat explicit înainte de resize — nu ne
# bazăm doar pe DecompressionBombError-ul implicit din Pillow (care doar
# avertizează, fără să oprească nimic, sub dublul MAX_IMAGE_PIXELS). 40MP
# acoperă orice poză reală de telefon/aparat foto; peste asta tratăm
# fișierul ca pe o posibilă decompression bomb și refuzăm să-l procesăm.
MAX_PIXELI_ACCEPTATI = 40_000_000


class PozaPreaMareError(ValueError):
    """Rezoluție decodată peste `MAX_PIXELI_ACCEPTATI` — ridicată explicit
    (nu înghițită de `except Exception` de mai jos) ca poza să NU fie
    salvată netratată, spre deosebire de o eroare normală de decodare."""


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

        if imagine.width * imagine.height > MAX_PIXELI_ACCEPTATI:
            camp_fisier.seek(0)
            raise PozaPreaMareError(
                f"Poză cu rezoluție neobișnuit de mare "
                f"({imagine.width}x{imagine.height}px) — refuzată."
            )

        # exif_transpose mereu, chiar dacă poza e deja destul de mică pentru
        # a nu necesita redimensionare — corectează orientarea ȘI, prin
        # reîncodarea de mai jos (fără exif= la save), scapă de orice
        # metadată EXIF (inclusiv coordonate GPS, dacă telefonul le-a scris)
        # din fișierul original. Fără asta, o poză mică trecea nemodificată
        # prin `return`-ul de mai devreme, cu EXIF-ul original intact —
        # relevant mai ales la Comment.imagine, unde orice vizitatoare
        # anonimă poate încărca o poză făcută pe loc cu telefonul.
        imagine = ImageOps.exif_transpose(imagine)

        if max(imagine.size) > max_dimensiune:
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
    except PozaPreaMareError:
        # Propagă mai departe — spre deosebire de erorile de mai jos, asta
        # nu trebuie „înghițită" cu poza originală salvată netratată.
        raise
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

from django.http import HttpResponse

# Peste MAX_UPLOAD_IMAGINE_BYTES (5MB, verificat în CommentForm.clean_imagine)
# + marjă pentru restul câmpurilor multipart (nume/comentariu/CSRF/boundary).
# Fără plafonul ăsta, verificarea din formular vine PREA TÂRZIU — Django
# citește deja tot corpul cererii (request.FILES) înainte ca view-ul să
# apuce să respingă ceva, deci un vizitator anonim ar putea trimite fișiere
# oricât de mari, repetat, către formularul public de comentarii, epuizând
# memoria/discul serverului înainte de orice validare de nivel aplicație.
MAX_REQUEST_BODY_BYTES = 8 * 1024 * 1024


class MaxUploadSizeMiddleware:
    """Respinge cererile cu Content-Length peste plafon INAINTE ca Django
    să înceapă să parseze corpul (request.POST/request.FILES) — trebuie
    plasat cât mai devreme în MIDDLEWARE, ca niciun middleware/view de după
    să nu atingă request.body/POST/FILES pe o cerere deja prea mare."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        content_length = request.META.get("CONTENT_LENGTH")
        if content_length:
            try:
                if int(content_length) > MAX_REQUEST_BODY_BYTES:
                    return HttpResponse(
                        "Cererea este prea mare.", status=413, content_type="text/plain"
                    )
            except (TypeError, ValueError):
                pass
        return self.get_response(request)

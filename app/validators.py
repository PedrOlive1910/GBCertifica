import re

from wtforms.validators import ValidationError


EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def validar_email(_form, campo):
    if not EMAIL_RE.fullmatch((campo.data or "").strip()):
        raise ValidationError("Informe um endereço de e-mail válido.")


def senha_forte(valor):
    return bool(
        valor
        and len(valor) >= 8
        and re.search(r"[A-ZÁÉÍÓÚÂÊÔÃÕÇ]", valor)
        and re.search(r"[a-záéíóúâêôãõç]", valor)
        and re.search(r"\d", valor)
    )


def validar_senha_forte(_form, campo):
    if not campo.data:
        return
    if not senha_forte(campo.data):
        raise ValidationError(
            "Use ao menos 8 caracteres, incluindo letra maiúscula, minúscula e número."
        )

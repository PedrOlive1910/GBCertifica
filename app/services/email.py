from email.message import EmailMessage
import smtplib

from flask import current_app


class ErroEnvioEmail(RuntimeError):
    pass


def enviar_email(destinatario: str, assunto: str, texto: str) -> None:
    host = current_app.config.get("SMTP_HOST")
    remetente = current_app.config.get("MAIL_FROM")
    if not host or not remetente:
        raise ErroEnvioEmail("SMTP não configurado no arquivo .env.")

    mensagem = EmailMessage()
    mensagem["Subject"] = assunto
    mensagem["From"] = remetente
    mensagem["To"] = destinatario
    mensagem.set_content(texto)

    try:
        with smtplib.SMTP(host, current_app.config["SMTP_PORT"], timeout=20) as smtp:
            smtp.ehlo()
            if current_app.config.get("SMTP_USE_TLS"):
                smtp.starttls()
                smtp.ehlo()
            usuario = current_app.config.get("SMTP_USER")
            senha = current_app.config.get("SMTP_PASSWORD")
            if usuario:
                smtp.login(usuario, senha)
            smtp.send_message(mensagem)
    except (OSError, smtplib.SMTPException) as erro:
        raise ErroEnvioEmail("Falha ao enviar o e-mail de recuperação.") from erro

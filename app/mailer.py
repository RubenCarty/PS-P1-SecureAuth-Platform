"""
Envío de correo por SMTP con cifrado en tránsito.

Nivel 1 (transporte) aplicado también al canal del segundo
factor: la conexión al servidor SMTP usa STARTTLS o SMTPS,
nunca texto plano.

Si no hay servidor configurado, la aplicación degrada a modo
consola: registra el mensaje en el log en vez de enviarlo.
Esto permite desarrollar y ejecutar las pruebas sin
credenciales de correo, pero en producción es obligatorio
configurar SMTP (ver comprobación en app/__init__.py).
"""

import smtplib
import ssl
from email.message import EmailMessage

from flask import current_app


def mail_is_configured() -> bool:
    cfg = current_app.config
    return bool(
        cfg.get("SMTP_HOST")
        and cfg.get("SMTP_USER")
        and cfg.get("SMTP_PASSWORD")
        and cfg.get("MAIL_FROM")
    )


def send_email(
    to_address: str,
    subject: str,
    body: str,
) -> bool:
    """
    Envía un correo de texto plano.

    Devuelve True si se entregó al servidor SMTP.
    Nunca propaga excepciones al flujo de autenticación:
    un fallo de correo no debe filtrar información ni
    romper la respuesta al usuario.
    """
    cfg = current_app.config

    if not mail_is_configured():
        current_app.logger.warning(
            "[SMTP NO CONFIGURADO] Para %s | %s\n%s",
            to_address,
            subject,
            body,
        )
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = cfg["MAIL_FROM"]
    message["To"] = to_address
    message.set_content(body)

    context = ssl.create_default_context()

    try:
        if cfg["SMTP_USE_SSL"]:
            with smtplib.SMTP_SSL(
                cfg["SMTP_HOST"],
                cfg["SMTP_PORT"],
                context=context,
                timeout=10,
            ) as server:
                server.login(
                    cfg["SMTP_USER"],
                    cfg["SMTP_PASSWORD"],
                )
                server.send_message(message)
        else:
            with smtplib.SMTP(
                cfg["SMTP_HOST"],
                cfg["SMTP_PORT"],
                timeout=10,
            ) as server:
                server.starttls(context=context)
                server.login(
                    cfg["SMTP_USER"],
                    cfg["SMTP_PASSWORD"],
                )
                server.send_message(message)

        return True

    except Exception:
        # Se registra sin incluir el cuerpo (contiene el código).
        current_app.logger.exception(
            "Fallo al enviar correo a un destinatario."
        )

        # En desarrollo, si el SMTP falla el usuario quedaría
        # sin forma de continuar. Se vuelca el mensaje al log
        # para no bloquear la demostración. En producción NO
        # se hace: el código nunca debe quedar en los logs de
        # un servidor accesible.
        if current_app.config["ENVIRONMENT"] != "production":
            current_app.logger.warning(
                "[SMTP FALLÓ — MODO DESARROLLO] Para %s | %s\n%s",
                to_address,
                subject,
                body,
            )

        return False

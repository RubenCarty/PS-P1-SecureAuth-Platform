"""
Diagnóstico de la configuración de correo.

Uso:
    python check_smtp.py                  # solo verifica el login
    python check_smtp.py destino@gmail.com  # además envía una prueba

Comprueba la conexión y las credenciales SMTP sin pasar por
el flujo de la aplicación, para aislar problemas de correo.
"""

import sys

from app import create_app
from app.mailer import send_email

app = create_app()

with app.app_context():
    cfg = app.config

    print("=" * 55)
    print("CONFIGURACIÓN SMTP")
    print("=" * 55)
    print(f"  SMTP_HOST     : {cfg['SMTP_HOST'] or '(vacío)'}")
    print(f"  SMTP_PORT     : {cfg['SMTP_PORT']}")
    print(f"  SMTP_USE_SSL  : {cfg['SMTP_USE_SSL']}")
    print(f"  SMTP_USER     : {cfg['SMTP_USER'] or '(vacío)'}")

    pwd = cfg["SMTP_PASSWORD"]
    if pwd:
        print(f"  SMTP_PASSWORD : {len(pwd)} caracteres "
              f"(termina en '{pwd[-2:]}')")
        if len(pwd) != 16:
            print("     AVISO: una contraseña de aplicación de "
                  "Google tiene exactamente 16 caracteres.")
    else:
        print("  SMTP_PASSWORD : (vacío)")

    print(f"  MAIL_FROM     : {cfg['MAIL_FROM']}")
    print()

    if not all((cfg["SMTP_HOST"], cfg["SMTP_USER"], pwd)):
        print("Falta configuración. Completa el .env.")
        sys.exit(1)

    # Prueba de login aislada
    import smtplib
    import ssl

    print("Conectando al servidor...")
    try:
        context = ssl.create_default_context()
        if cfg["SMTP_USE_SSL"]:
            server = smtplib.SMTP_SSL(
                cfg["SMTP_HOST"], cfg["SMTP_PORT"],
                context=context, timeout=10,
            )
        else:
            server = smtplib.SMTP(
                cfg["SMTP_HOST"], cfg["SMTP_PORT"], timeout=10,
            )
            server.starttls(context=context)

        server.login(cfg["SMTP_USER"], pwd)
        server.quit()
        print("Autenticación correcta.\n")

    except smtplib.SMTPAuthenticationError as exc:
        print(f"Credenciales rechazadas: {exc.smtp_code}\n")
        print("Causas habituales:")
        print("  1. Se usó la contraseña personal en vez de una")
        print("     contraseña de aplicación.")
        print("  2. La verificación en 2 pasos no está activa en")
        print("     la cuenta de Google.")
        print("  3. La contraseña se pegó con espacios o comillas.")
        print("  4. SMTP_USER no es el correo completo.")
        print("  5. Es una cuenta de Workspace con SMTP bloqueado")
        print("     por el administrador.")
        sys.exit(1)

    except Exception as exc:
        print(f"Error de conexión: {exc}")
        sys.exit(1)

    # Envío de prueba
    if len(sys.argv) > 1:
        destino = sys.argv[1]
        print(f"Enviando correo de prueba a {destino}...")
        ok = send_email(
            destino,
            "Prueba de configuración · SecureAuth Store",
            "Si recibes este mensaje, el segundo factor "
            "puede entregarse correctamente.",
        )
        print("Enviado. Revisa la bandeja (y spam)."
              if ok else "El envío falló.")
    else:
        print("Para enviar una prueba real:")
        print("  python check_smtp.py tu-correo@gmail.com")

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

def enviar_correo_contacto(nombre, email, telefono, asunto, mensaje):
    EMAIL_ADDRESS = os.getenv('EMAIL_ADDRESS')
    EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')

    # Crear el cuerpo del mensaje en HTML
    cuerpo_mensaje = f"""
    <html>
        <body>
            <h2 style="color: #2d8feb;">Nuevo mensaje del formulario de contacto:</h2>
            <ul style="list-style-type: none;">
                <li><strong>Nombre completo:</strong> {nombre}</li>
                <li><strong>Email:</strong> {email}</li>
                <li><strong>Teléfono:</strong> {telefono}</li>
                <li><strong>Asunto:</strong> {asunto}</li>
            </ul>
            <h3 style="color: #2d8feb;">Mensaje:</h3>
            <p>{mensaje}</p>
        </body>
    </html>
    """

    msg = MIMEMultipart()
    msg['Subject'] = 'Formulario de contacto - Sitio Web'
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = 'it.tartuski@gmail.com'  # Cambia esto a la dirección de destino deseada

    msg.attach(MIMEText(cuerpo_mensaje, 'html'))

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)
    except Exception as e:
        raise Exception(f"Error al enviar el correo: {e}")

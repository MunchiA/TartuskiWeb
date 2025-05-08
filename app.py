from flask import Flask, redirect, url_for, render_template, session, request, jsonify, g, flash
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv
import os
import secrets
import MySQLdb
from datetime import datetime
from email.mime.text import MIMEText
import smtplib

load_dotenv()

app = Flask(__name__)

# Usar la clave secreta desde el archivo .env
app.secret_key = os.getenv('FLASK_SECRET_KEY')

if not app.secret_key:
    raise ValueError("SECRET_KEY is not set in .env file")

# Cargar variables de entorno
load_dotenv()
client_id = os.getenv('AZURE_AD_CLIENT_ID')
tenant_id = os.getenv('AZURE_AD_TENANT_ID')
client_secret = os.getenv('AZURE_AD_CLIENT_SECRET')

# Verificar que las variables de entorno están cargadas
if not all([client_id, tenant_id, client_secret]):
    raise ValueError("Faltan variables de entorno: AZURE_AD_CLIENT_ID, AZURE_AD_TENANT_ID o AZURE_AD_CLIENT_SECRET")

# Configurar OAuth con Azure AD
oauth = OAuth(app)
azure = oauth.register(
    name='azure',
    client_id=client_id,
    client_secret=client_secret,
    api_base_url='https://graph.microsoft.com/v1.0/',
    authorize_url=f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize",
    access_token_url=f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
    jwks_uri=f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys",
    client_kwargs={'scope': 'openid profile email User.Read'},
)

# Configuración de la base de datos MySQL desde .env
db = MySQLdb.connect(
    host=os.getenv('DB_HOST'),
    user=os.getenv('DB_USER'),
    passwd=os.getenv('DB_PASS'),
    db=os.getenv('DB_NAME')
)

# Función para obtener la conexión a la base de datos
def get_db():
    if not hasattr(g, 'db'):
        g.db = db
    return g.db

# Cerrar la conexión a la base de datos después de cada solicitud
@app.teardown_appcontext
def close_db(error):
    db = getattr(g, 'db', None)
    if db is not None:
        db.close()

# Ruta para el calendario
@app.route('/calendario')
def calendario():
    if not session.get('user'):
        return redirect(url_for('login'))
    return render_template('calendario.html')

# Ruta para obtener eventos
@app.route('/obtener-eventos', methods=['GET'])
def obtener_eventos():
    if not session.get('user'):
        return jsonify({'status': 'error', 'message': 'No autenticado'}), 401
    cursor = get_db().cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("""
        SELECT e.id, e.titulo, e.descripcion, e.fecha_inicio, e.fecha_fin, u.nombre as creator
        FROM eventos e
        JOIN usuarios u ON e.azure_user_id = u.azure_user_id
    """)
    events = cursor.fetchall()
    cursor.close()
    
    # Formatear los eventos para FullCalendar
    formatted_events = []
    for event in events:
        start = event['fecha_inicio'] if event['fecha_inicio'] else None
        end = event['fecha_fin'] if event['fecha_fin'] else None
        formatted_events.append({
            'id': event['id'],
            'title': event['titulo'],
            'start': start,
            'end': end,
            'description': event['descripcion'],
            'creator': event['creator']
        })
    
    return jsonify(formatted_events)

# Ruta para crear eventos
@app.route('/crear-evento', methods=['POST'])
def crear_evento():
    if not session.get('user'):
        return jsonify({'status': 'error', 'message': 'No autenticado'}), 401
    if request.is_json:
        data = request.get_json()
        titulo = data.get('titulo')
        descripcion = data.get('descripcion')
        fecha_inicio = f"{data.get('fecha')} {data.get('hora_inicio')}" if data.get('hora_inicio') else data.get('fecha')
        fecha_fin = f"{data.get('fecha')} {data.get('hora_fin')}" if data.get('hora_fin') else data.get('fecha')
    else:
        # Fallback por si se accede desde un formulario tradicional
        titulo = request.form['titulo']
        descripcion = request.form['descripcion']
        fecha_inicio = request.form['fecha_inicio'] + ' ' + request.form['hora_inicio']
        fecha_fin = request.form['fecha_fin'] + ' ' + request.form['hora_fin']

    azure_user_id = g.user['azure_user_id']

    try:
        cursor = get_db().cursor()
        cursor.execute("""
            INSERT INTO eventos (titulo, descripcion, fecha_inicio, fecha_fin, azure_user_id)
            VALUES (%s, %s, %s, %s, %s)
        """, (titulo, descripcion, fecha_inicio, fecha_fin, azure_user_id))
        get_db().commit()
        return {"status": "ok"}, 200  # JSON response
    except Exception as e:
        get_db().rollback()
        return {"status": "error", "message": str(e)}, 500

# Ruta principal
@app.route('/')
def home():
    return render_template('home.html')

# Ruta para iniciar sesión
@app.route('/login')
def login():
    try:
        # Generar nonce y state, y almacenarlos en la sesión
        nonce = secrets.token_urlsafe(16)
        state = secrets.token_urlsafe(16)
        session['nonce'] = nonce
        session['state'] = state

        # Definir el URI de redirección
        redirect_uri = url_for('auth', _external=True, _scheme='https')

        # Imprimir para depuración
        print(f"Redirect URI: {redirect_uri}, Nonce: {nonce}, State: {state}")

        # Redirigir al proveedor OAuth
        return azure.authorize_redirect(redirect_uri, nonce=nonce, state=state)
    except Exception as e:
        return f"Error during login: {str(e)}", 500

# Ruta de callback
@app.route('/auth')
def auth():
    try:
        # Obtener el token de acceso
        token = azure.authorize_access_token()

        # Obtener nonce y state desde la sesión
        nonce = session.get('nonce')
        state = session.get('state')

        # Verificar que el estado recibido coincida con el almacenado en la sesión
        if state != request.args.get('state'):
            raise ValueError("State no coincide entre la solicitud y la respuesta")

        if not nonce:
            return "Error: Nonce no encontrado en la sesión", 500

        # Procesar el token y obtener la información del usuario
        user = azure.parse_id_token(token, nonce=nonce)
        if user:
            # Asegurarse de que azure_user_id esté disponible
            azure_user_id = user.get('oid') or user.get('sub')  # 'oid' o 'sub' según Azure AD
            cursor = get_db().cursor()
            cursor.execute("""
                INSERT INTO usuarios (azure_user_id, nombre, email)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE nombre=VALUES(nombre), email=VALUES(email)
            """, (azure_user_id, user.get('name', 'Unknown'), user.get('email', 'No email')))
            get_db().commit()
            cursor.close()
            session['user'] = {'azure_user_id': azure_user_id, 'name': user.get('name', 'Unknown'), 'email': user.get('email', 'No email')}
            session.pop('nonce', None)
            session.pop('state', None)

        return redirect(url_for('profile'))
    except Exception as e:
        return f"Error during auth: {str(e)}", 500

@app.before_request
def load_user():
    # Cargar el usuario desde la sesión para todas las rutas
    user = session.get('user')
    g.user = user

# Ruta para el perfil
@app.route('/profile')
def profile():
    user = session.get('user')
    if not user:
        return redirect(url_for('login'))
    return render_template('profile.html', user=user)

# Ruta para cerrar sesión
@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('Sesión cerrada', 'success')
    return redirect(url_for('home'))

@app.route('/sobre-nosotros')
def sobre_nosotros():
    return render_template('sobre_nosotros.html')

@app.route('/servicios')
def servicios():
    return render_template('servicios.html')

# Configuración de correo desde .env
EMAIL_ADDRESS = os.getenv('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')

@app.route('/contactanos', methods=['GET', 'POST'])
def contactanos():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        email = request.form.get('email')
        telefono = request.form.get('telefono')
        empresa = request.form.get('empresa')
        servicio = request.form.get('servicio')
        mensaje = request.form.get('mensaje')
        return redirect(url_for('contactanos'))
    return render_template('contactanos.html')


required_env_vars = ['FLASK_SECRET_KEY', 'AZURE_AD_CLIENT_ID', 'AZURE_AD_TENANT_ID', 'AZURE_AD_CLIENT_SECRET', 'DB_HOST', 'DB_USER', 'DB_PASS', 'DB_NAME', 'EMAIL_ADDRESS', 'EMAIL_PASSWORD']
if not all(os.getenv(var) for var in required_env_vars):
    raise ValueError("Faltan una o más variables de entorno requeridas.")

if __name__ == '__main__':
    app.run(debug=True)
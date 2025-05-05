from flask import Flask, redirect, url_for, render_template, session, request, flash, g
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv
import os
import secrets  # For generating nonce

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
            session['user'] = user
            session.pop('nonce', None)
            session.pop('state', None)  # Limpiar el state y el nonce

        return redirect(url_for('profile'))
    except Exception as e:
        return f"Error during auth: {str(e)}", 500


@app.before_request
def load_user():
    # Cargar el usuario desde la sesión para todas las rutas
    user = session.get('user')
    # Hacer que esté disponible globalmente en las plantillas
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

@app.route('/calendario')
def calendario():
    return render_template('calendario.html')

@app.route('/sobre-nosotros')
def sobre_nosotros():
    return render_template('sobre_nosotros.html')

@app.route('/servicios')
def servicios():
    return render_template('servicios.html')

@app.route('/contactanos', methods=['GET', 'POST'])
def contactanos():
    if request.method == 'POST':
        # Aquí iría la lógica para procesar el formulario
        # Por ejemplo, enviar un correo electrónico o guardar en base de datos
        nombre = request.form.get('nombre')
        email = request.form.get('email')
        telefono = request.form.get('telefono')
        empresa = request.form.get('empresa')
        servicio = request.form.get('servicio')
        mensaje = request.form.get('mensaje')
        
        # Simulamos un procesamiento exitoso
        flash('¡Mensaje enviado con éxito! Nos pondremos en contacto contigo pronto.', 'success')
        return redirect(url_for('contactanos'))
    
    return render_template('contactanos.html')

if __name__ == '__main__':
    app.run(debug=True)
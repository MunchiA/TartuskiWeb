from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, g
from flask_sqlalchemy import SQLAlchemy  # Replace MySQLdb with Flask-SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from authlib.integrations.flask_client import OAuth
import requests
import json
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from email.mime.text import MIMEText
import smtplib
from utils.email_utils import enviar_correo_contacto
import secrets  # For nonce generation

# Cargar variables de entorno desde .env
load_dotenv()

app = Flask(__name__)

# Usar la clave secreta desde el archivo .env
app.secret_key = os.getenv('FLASK_SECRET_KEY')
if not app.secret_key:
    raise ValueError("SECRET_KEY is not set in .env file")

# Configurar Flask-SQLAlchemy
app.config['SQLALCHEMY_DATABASE_URI'] = (
    f"mysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASS')}@{os.getenv('DB_HOST')}/{os.getenv('DB_NAME')}"
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)  # Initialize Flask-SQLAlchemy

# Cargar variables de entorno para Azure AD
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

# Configurar Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Modelos de la base de datos
class Usuario(db.Model, UserMixin):
    __tablename__ = 'usuarios'
    azure_user_id = db.Column(db.String(255), primary_key=True)
    nombre = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    eventos = db.relationship('Evento', backref='usuario', lazy=True)

    # Necesario para Flask-Login
    def get_id(self):
        return self.azure_user_id

    @property
    def id(self):
        return self.azure_user_id

    @property
    def name(self):
        return self.nombre

    def __repr__(self):
        return f'<Usuario {self.email}>'

class Evento(db.Model):
    __tablename__ = 'eventos'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    titulo = db.Column(db.String(255), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    fecha_inicio = db.Column(db.DateTime, nullable=False)
    fecha_fin = db.Column(db.DateTime, nullable=False)
    azure_user_id = db.Column(db.String(255), db.ForeignKey('usuarios.azure_user_id'), nullable=False)

    def __repr__(self):
        return f'<Evento {self.titulo}>'

# Flask-Login user loader
@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(user_id)

# Rutas para las páginas visibles
@app.route('/')
def home():
    return render_template('home.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/services')
def services():
    return render_template('services.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        # Obtener los datos del formulario
        nombre = request.form.get('name')
        email = request.form.get('email')
        telefono = request.form.get('phone')
        asunto = request.form.get('subject')
        mensaje = request.form.get('message')

        # Verificamos si el formulario contiene los datos requeridos
        if not nombre or not email or not mensaje:
            flash("Por favor, completa todos los campos obligatorios.", "error")
            return redirect(url_for('contact'))

        try:
            # Llamamos a la función para enviar el correo
            enviar_correo_contacto(nombre, email, telefono, asunto, mensaje)
            flash("¡Mensaje enviado correctamente! Nos pondremos en contacto contigo pronto.", "success")
            return redirect(url_for('contact'))
        except Exception as e:
            flash(f"Error al enviar el mensaje: {e}", "error")
            return redirect(url_for('contact'))

    return render_template('contact.html')  

# Ruta para iniciar sesión
@app.route('/login')
def login():
    nonce = secrets.token_urlsafe(16)
    session['nonce'] = nonce
    redirect_uri = url_for('auth', _external=True, _scheme='https')
    return azure.authorize_redirect(redirect_uri, nonce=nonce)

# Ruta de callback
@app.route('/auth')
def auth():
    try:
        token = azure.authorize_access_token()
        nonce = session.pop('nonce', None)
        user = azure.parse_id_token(token, nonce=nonce)

        if user:
            azure_user_id = user.get('oid') or user.get('sub')
            # Use Flask-SQLAlchemy to handle user insertion
            usuario = Usuario.query.get(azure_user_id)
            if not usuario:
                usuario = Usuario(
                    azure_user_id=azure_user_id,
                    nombre=user.get('name', 'Unknown'),
                    email=user.get('email', 'No email')
                )
                db.session.add(usuario)
            else:
                usuario.nombre = user.get('name', 'Unknown')
                usuario.email = user.get('email', 'No email')
            db.session.commit()

            login_user(usuario)  # Log in the user with Flask-Login
            session['user'] = {
                'azure_user_id': azure_user_id,
                'name': user.get('name', 'Unknown'),
                'email': user.get('email', 'No email')
            }

        return redirect(url_for('home'))
    except Exception as e:
        return f"Error during auth: {str(e)}", 500

@app.before_request
def load_user():
    # Cargar el usuario desde la sesión para todas las rutas
    user = session.get('user')
    g.user = user

# Ruta para cerrar sesión
@app.route('/logout')
@login_required
def logout():
    session.pop('user', None)
    logout_user()  # Log out the user with Flask-Login
    flash('Sesión cerrada', 'success')
    return redirect(url_for('home'))

@app.route('/calendar')
@login_required
def calendar():
    eventos = Evento.query.filter_by(azure_user_id=current_user.azure_user_id).all()
    return render_template('calendar.html', events=eventos)

@app.route('/api/events', methods=['GET'])
@login_required
def get_events():
    eventos = Evento.query.filter_by(azure_user_id=current_user.azure_user_id).all()
    events_data = [
        {
            'id': evento.id,
            'title': evento.titulo,
            'start': evento.fecha_inicio.strftime('%Y-%m-%dT%H:%M:%S'),
            'end': evento.fecha_fin.strftime('%Y-%m-%dT%H:%M:%S'),
            'description': evento.descripcion or ''
        }
        for evento in eventos
    ]
    return jsonify(events_data)

@app.route('/add_event', methods=['POST'])
@login_required
def add_event():
    try:
        titulo = request.form['title']
        descripcion = request.form['description']
        fecha_inicio = datetime.strptime(request.form['start_time'], '%Y-%m-%dT%H:%M')
        fecha_fin = datetime.strptime(request.form['end_time'], '%Y-%m-%dT%H:%M')

        nuevo_evento = Evento(
            titulo=titulo,
            descripcion=descripcion,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            azure_user_id=current_user.azure_user_id
        )

        db.session.add(nuevo_evento)
        db.session.commit()
        flash('Evento agregado correctamente', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Hubo un error al agregar el evento: {str(e)}', 'danger')

    return redirect(url_for('calendar'))

@app.route('/delete_event/<int:event_id>', methods=['DELETE'])
def delete_event(event_id):
    try:
        # Intentamos obtener el evento de la base de datos
        evento = Evento.query.get_or_404(event_id)
        
        # Eliminamos el evento de la base de datos
        db.session.delete(evento)
        db.session.commit()
        
        # Respuesta exitosa
        return jsonify({"message": "Evento eliminado con éxito"}), 200
    except Exception as e:
        # Si ocurre un error, revertimos la transacción y enviamos un mensaje de error
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create tables if they don't exist
    app.run(debug=True)
from app import app, db

with app.app_context():
    try:
        db.create_all()
        print("✅ Tablas creadas correctamente (si no existían).")
    except Exception as e:
        print("❌ Error al crear tablas:", e)

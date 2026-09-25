from flask import Flask
from app.models import db
import os

def create_app(config=None):
    app = Flask(__name__)
    
    # Configurações
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cafe_annotations.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB
    app.config['UPLOAD_FOLDER'] = 'app/uploads'
    app.config['ALLOWED_EXTENSIONS'] = {'jpg', 'jpeg', 'png', 'bmp'}
    
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    
    db.init_app(app)
    
    with app.app_context():
        db.create_all()
    
    # Registrar blueprints
    from app.routes import main_bp, api_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    
    return app
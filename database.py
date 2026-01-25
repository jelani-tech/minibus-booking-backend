from flask import Flask
from models.public import db
from config import Config

def init_db(app):
    """Initialize the database"""
    app.config.from_object(Config)
    db.init_app(app)
    
    with app.app_context():
        # Create schemas
        try:
            db.session.execute(db.text("CREATE SCHEMA IF NOT EXISTS clients"))
            db.session.execute(db.text("CREATE SCHEMA IF NOT EXISTS partners"))
            db.session.execute(db.text("CREATE SCHEMA IF NOT EXISTS common"))
            db.session.commit()
        except Exception as e:
            print(f"Schema creation warning: {e}")
            
        db.create_all()
        print("Database initialized successfully")


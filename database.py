from flask import Flask
from models.public import db
from config import Config

def init_db(app):
    """Initialize the database"""
    app.config.from_object(Config)
    db.init_app(app)
    
    with app.app_context():
        db.create_all()
        print("Database initialized successfully")


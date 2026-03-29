from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import bcrypt

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    __table_args__ = {'schema': 'public'}
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    bookings = db.relationship('models.clients.Booking', backref='user', lazy=True)
    
    def set_password(self, password):
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    def check_password(self, password):
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'phone': self.phone,
            'email': self.email,
            'created_at': self.created_at.isoformat()
        }


class Line(db.Model):
    __tablename__ = 'lines'
    __table_args__ = {'schema': 'public'}
    
    id = db.Column(db.UUID(as_uuid=True), primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


class Station(db.Model):
    __tablename__ = 'stations'
    __table_args__ = {'schema': 'public'}

    id = db.Column(db.UUID(as_uuid=True), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }

class Stop(db.Model):
    __tablename__ = 'stops'
    __table_args__ = {'schema': 'public'}

    id = db.Column(db.UUID(as_uuid=True), primary_key=True)
    line_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('public.lines.id'), nullable=False)
    station_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('public.stations.id'), nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    order = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __to_dict(self):
        return {
            'id': self.id,
            'line_id': self.line_id,
            'station_id': self.station_id,
            'longitude': self.longitude,
            'latitude': self.latitude,
            'order': self.order,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }

class Step(db.Model):
    __tablename__ = 'steps'
    __table_args__ = {'schema': 'public'}

    id = db.Column(db.UUID(as_uuid=True), primary_key=True)
    trip_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('clients.trips.id'), nullable=False)
    client_transaction_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('clients.transactions.id'), nullable=False)
    partner_transaction_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('partners.transactions.id'), nullable=False)
    partner_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('partners.partners.id'), nullable=True)
    status = db.Column(db.String(100), nullable=False)
    order = db.Column(db.Integer, nullable=False)
    departure = db.Column(db.String(100), nullable=False)
    arrival = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __to_dict(self):
        return {
            'id': self.id,
            'trip_id': self.trip_id,
            'client_transaction_id': self.client_transaction_id,
            'partner_transaction_id': self.partner_transaction_id,
            'partner_id': self.partner_id,      
            'status': self.status,
            'order': self.order,
            'departure': self.departure,
            'arrival': self.arrival,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }

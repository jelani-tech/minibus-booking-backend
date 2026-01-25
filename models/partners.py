from datetime import datetime
from models.public import db


class Partner(db.Model):
    __tablename__ = 'partners'
    __table_args__ = {'schema': 'partners'}

    id = db.Column(db.UUID(as_uuid=True), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('public.users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }

class Account(db.Model):
    __tablename__ = 'accounts'
    __table_args__ = {'schema': 'partners'}

    id = db.Column(db.UUID(as_uuid=True), primary_key=True)
    partner_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('partners.partners.id'), nullable=False)
    balance = db.Column(db.Float, nullable=False, default=0.0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __to_dict(self):
        return {
            'id': self.id,
            'partner_id': self.partner_id,
            'balance': self.balance,
            'updated_at': self.updated_at
        }

class Transaction(db.Model):
    __tablename__ = 'transactions'
    __table_args__ = {'schema': 'partners'}

    id = db.Column(db.UUID(as_uuid=True), primary_key=True)
    partner_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('partners.partners.id'), nullable=False)
    type = db.Column(db.Enum('TRANSPORT_FEES', 'WITHDRAWL', name='partner_transaction_type', schema='partners'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    departure = db.Column(db.String(100), nullable=True)
    arrival = db.Column(db.String(100), nullable=True)
    payment_method = db.Column(db.Enum('WALLET', 'OM', 'MOMO', 'MM', 'WAVE', 'CREDIT_CARD', 'CASH', name='partner_payment_method', schema='partners'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __to_dict(self):
        return {
            'id': self.id,
            'partner_id': self.partner_id,
            'type': self.type,
            'amount': self.amount,
            'departure': self.departure,
            'arrival': self.arrival,
            'payment_method': self.payment_method,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }

class ScheduledTrip(db.Model):
    __tablename__ = 'scheduled_trips'
    __table_args__ = {'schema': 'partners'}
    
    id = db.Column(db.Integer, primary_key=True)
    departure_city = db.Column(db.String(100), nullable=False)
    arrival_city = db.Column(db.String(100), nullable=False)
    departure_time = db.Column(db.DateTime, nullable=False)
    arrival_time = db.Column(db.DateTime, nullable=False)
    price = db.Column(db.Float, nullable=False)
    available_seats = db.Column(db.Integer, nullable=False, default=18)
    total_seats = db.Column(db.Integer, nullable=False, default=18)
    driver_name = db.Column(db.String(100), nullable=False)
    driver_phone = db.Column(db.String(20), nullable=False)
    vehicle_number = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='active')  # active, cancelled, completed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    bookings = db.relationship('models.clients.Booking', backref='scheduled_trip', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'departure_city': self.departure_city,
            'arrival_city': self.arrival_city,
            'departure_time': self.departure_time.isoformat(),
            'arrival_time': self.arrival_time.isoformat(),
            'price': self.price,
            'available_seats': self.available_seats,
            'total_seats': self.total_seats,
            'driver_name': self.driver_name,
            'driver_phone': self.driver_phone,
            'vehicle_number': self.vehicle_number,
            'status': self.status,
            'created_at': self.created_at.isoformat()
        }


    
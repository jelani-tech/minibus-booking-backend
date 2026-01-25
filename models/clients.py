from datetime import datetime
from models.public import db


class Client(db.Model):
    __tablename__ = 'clients'
    __table_args__ = {'schema': 'clients'}

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
    __table_args__ = {'schema': 'clients'}

    id = db.Column(db.UUID(as_uuid=True), primary_key=True)
    client_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('clients.clients.id'), nullable=False)
    balance = db.Column(db.Float, nullable=False, default=0.0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __to_dict(self):
        return {
            'id': self.id,  
            'client_id': self.client_id,
            'balance': self.balance,
            'updated_at': self.updated_at
        }


class Trip(db.Model):
    __tablename__ = 'trips'
    __table_args__ = {'schema': 'clients'}

    id = db.Column(db.UUID(as_uuid=True), primary_key=True)
    client_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('clients.clients.id'), nullable=False)
    step_number = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __to_dict(self):
        return {
            'id': self.id,
            'client_id': self.client_id,
            'step_number': self.step_number,
            'created_at': self.created_at
        }
    
class Transaction(db.Model):
    __tablename__ = 'transactions'
    __table_args__ = {'schema': 'clients'}

    id = db.Column(db.UUID(as_uuid=True), primary_key=True)
    client_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('clients.clients.id'), nullable=False)
    type = db.Column(db.Enum('TRANSPORT_FEES', 'WALLET_CREDITING', name='client_transaction_type', schema='clients'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    departure = db.Column(db.String(100), nullable=True)
    arrival = db.Column(db.String(100), nullable=True)
    payment_method = db.Column(db.Enum('WALLET', 'OM', 'MOMO', 'MM', 'WAVE', 'CREDIT_CARD', 'CASH', name='client_payment_method', schema='clients'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __to_dict(self):
        return {
            'id': self.id,
            'client_id': self.client_id,
            'type': self.type,
            'amount': self.amount,
            'departure': self.departure,
            'arrival': self.arrival,
            'payment_method': self.payment_method,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }

class Booking(db.Model):
    __tablename__ = 'bookings'
    __table_args__ = {'schema': 'clients'}
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('public.users.id'), nullable=False)
    trip_id = db.Column(db.Integer, db.ForeignKey('partners.scheduled_trips.id'), nullable=False)
    number_of_seats = db.Column(db.Integer, nullable=False, default=1)
    total_price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, confirmed, cancelled
    passenger_name = db.Column(db.String(100), nullable=False)
    passenger_phone = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    payment = db.relationship('Payment', backref='booking', uselist=False, lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'trip_id': self.trip_id,
            'number_of_seats': self.number_of_seats,
            'total_price': self.total_price,
            'status': self.status,
            'passenger_name': self.passenger_name,
            'passenger_phone': self.passenger_phone,
            'created_at': self.created_at.isoformat(),
            'trip': self.scheduled_trip.to_dict() if self.scheduled_trip else None
        }

class Payment(db.Model):
    __tablename__ = 'payments'
    __table_args__ = {'schema': 'clients'}
    
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('clients.bookings.id'), nullable=False, unique=True)
    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(20), nullable=False)  # wave, orange_money, mtn_momo
    transaction_id = db.Column(db.String(100), unique=True, nullable=True)
    status = db.Column(db.String(20), default='pending')  # pending, completed, failed
    payment_provider_response = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'booking_id': self.booking_id,
            'amount': self.amount,
            'payment_method': self.payment_method,
            'transaction_id': self.transaction_id,
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


        

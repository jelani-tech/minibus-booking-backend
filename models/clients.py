from datetime import datetime
from models.public import db


class Client(db.Model):
    __tablename__ = 'clients'
    __table_args__ = {'schema': 'clients'}

    client_id = db.Column(db.UUID(as_uuid=True), primary_key=True)
    user_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('public.users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

def __to_dict(self):
    return {
        'client_id': self.client_id,
        'user_id': self.user_id,
        'created_at': self.created_at,
        'updated_at': self.updated_at
    }


class Account(db.Model):
    __tablename__ = 'accounts'
    __table_args__ = {'schema': 'clients'}

    account_id = db.Column(db.UUID(as_uuid=True), primary_key=True)
    client_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('clients.clients.client_id'), nullable=False)
    balance = db.Column(db.Float, nullable=False, default=0.0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __to_dict(self):
        return {
            'account_id': self.account_id,  
            'client_id': self.client_id,
            'balance': self.balance,
            'updated_at': self.updated_at
        }


class Trip(db.Model):
    __tablename__ = 'trips'
    __table_args__ = {'schema': 'clients'}

    trip_id = db.Column(db.UUID(as_uuid=True), primary_key=True)
    client_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('clients.clients.client_id'), nullable=False)
    step_number = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __to_dict(self):
        return {
            'trip_id': self.trip_id,
            'client_id': self.client_id,
            'step_number': self.step_number,
            'created_at': self.created_at
        }
    
class Transaction(db.Model):
    __tablename__ = 'transactions'
    __table_args__ = {'schema': 'clients'}

    transaction_id = db.Column(db.UUID(as_uuid=True), primary_key=True)
    client_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('clients.clients.client_id'), nullable=False)
    type = db.Column(db.Enum('TRANSPORT_FEES', 'WALLET_CREDITING'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    departure = db.Column(db.String(100), nullable=True)
    arrival = db.Column(db.String(100), nullable=True)
    payment_method = db.Column(db.Enum('WALLET', 'OM', 'MOMO', 'MM', 'WAVE', 'CREDIT_CARD', 'CASH'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __to_dict(self):
        return {
            'transaction_id': self.transaction_id,
            'client_id': self.client_id,
            'type': self.type,
            'amount': self.amount,
            'departure': self.departure,
            'arrival': self.arrival,
            'payment_method': self.payment_method,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }

        

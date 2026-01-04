from datetime import datetime
from models.public import db


class Partner(db.Model):
    __tablename__ = 'partners'
    __table_args__ = {'schema': 'partners'}

    id = db.Column(db.UUID(as_uuid=True), primary_key=True)
    user_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('public.users.id'), nullable=False)
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
    type = db.Column(db.Enum('TRANSPORT_FEES', 'WITHDRAWL'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    departure = db.Column(db.String(100), nullable=True)
    arrival = db.Column(db.String(100), nullable=True)
    payment_method = db.Column(db.Enum('WALLET', 'OM', 'MOMO', 'MM', 'WAVE', 'CREDIT_CARD', 'CASH'), nullable=True)
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

    
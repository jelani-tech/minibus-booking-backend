from datetime import datetime
from models.public import db


class Station(db.Model):
    __tablename__ = 'stations'
    __table_args__ = {'schema': 'common'}

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

class Line(db.Model):
    __tablename__ = 'lines'
    __table_args__ = {'schema': 'common'}

    id = db.Column(db.UUID(as_uuid=True), primary_key=True)
    direction = db.Column(db.String(100), nullable=False)
    stop_number = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __to_dict(self):
        return {
            'id': self.id,
            'direction': self.direction,
            'stop_number': self.stop_number,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }

class Stop(db.Model):
    __tablename__ = 'stops'
    __table_args__ = {'schema': 'common'}

    id = db.Column(db.UUID(as_uuid=True), primary_key=True)
    line_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('common.lines.id'), nullable=False)
    station_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('common.stations.id'), nullable=False)
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
    __table_args__ = {'schema': 'common'}

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

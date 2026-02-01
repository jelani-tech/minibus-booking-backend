from datetime import datetime
from models.public import db

class Line(db.Model):
    __tablename__ = 'lines'
    __table_args__ = {'schema': 'public'} # Using public schema for now as transport schema wasn't explicitly requested and public seems appropriate for shared data

    id = db.Column(db.UUID(as_uuid=True), primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    stops = db.relationship('Stop', backref='line', lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'stops': [stop.to_dict() for stop in self.stops]
        }

class Stop(db.Model):
    __tablename__ = 'stops'
    __table_args__ = {'schema': 'public'}

    id = db.Column(db.UUID(as_uuid=True), primary_key=True)
    line_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('public.lines.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    latitude = db.Column(db.Float, nullable=True) # Split from 'Geographic Coordinates'
    longitude = db.Column(db.Float, nullable=True) # Split from 'Geographic Coordinates'
    order = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'line_id': self.line_id,
            'name': self.name,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'order': self.order,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

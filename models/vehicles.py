from datetime import datetime
from models.public import db

class Vehicle(db.Model):
    __tablename__ = 'vehicles'
    __table_args__ = {'schema': 'partners'} # Placing in partners schema as it's partner-related resource

    id = db.Column(db.UUID(as_uuid=True), primary_key=True)
    plate_number = db.Column(db.String(20), unique=True, nullable=False)
    make = db.Column(db.String(50), nullable=False)
    model = db.Column(db.String(50), nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    available_seats = db.Column(db.Integer, nullable=False)
    image_url = db.Column(db.String(255), nullable=True)
    line_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('public.lines.id'), nullable=False)
    status = db.Column(db.String(20), default='ACTIVE') # ACTIVE, MAINTENANCE, INACTIVE
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    trips = db.relationship('models.partners.ScheduledTrip', backref='vehicle', lazy=True)
    line = db.relationship('models.public.Line', backref='vehicles', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'plate_number': self.plate_number,
            'make': self.make,
            'model': self.model,
            'capacity': self.capacity,
            'available_seats': self.available_seats,
            'line_id': self.line_id,
            'image_url': self.image_url,
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

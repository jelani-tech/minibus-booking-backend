from datetime import datetime, timezone
import uuid
from models.public import db

class PasswordReset(db.Model):
    __tablename__ = 'password_resets'
    __table_args__ = {'schema': 'auth'}

    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone = db.Column(db.String(50), nullable=False, index=True)
    email = db.Column(db.String(100), nullable=False, index=True)
    otp_code = db.Column(db.String(10), nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    used = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    def to_dict(self):
        return {
            'id': str(self.id),
            'phone': self.phone,
            'email': self.email,
            'expires_at': self.expires_at.isoformat(),
            'used': self.used,
            'created_at': self.created_at.isoformat()
        }


class RefreshToken(db.Model):
    __tablename__ = 'refresh_tokens'
    __table_args__ = {'schema': 'auth'}

    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('public.customers.id'), nullable=False, index=True)
    token_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    revoked_at = db.Column(db.DateTime(timezone=True), nullable=True)
    replaced_by_id = db.Column(db.UUID(as_uuid=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    def is_active(self):
        return self.revoked_at is None and self.expires_at > datetime.now(timezone.utc)

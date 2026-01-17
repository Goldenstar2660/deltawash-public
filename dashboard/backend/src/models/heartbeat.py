"""
SQLAlchemy model for Heartbeat entity.

Represents a device health check event sent periodically by devices.
"""
from sqlalchemy import Column, String, UUID, TIMESTAMP, Boolean, ForeignKey, func
from sqlalchemy.orm import relationship
import uuid

from ..database import Base


class Heartbeat(Base):
    """Heartbeat model representing a device health check."""
    
    __tablename__ = "heartbeats"
    
    # Columns
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)
    timestamp = Column(TIMESTAMP(timezone=True), nullable=False)
    firmware_version = Column(String(20), nullable=True)
    online_status = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    device = relationship("Device", back_populates="heartbeats")
    
    def __repr__(self):
        return f"<Heartbeat(id={self.id}, device_id={self.device_id}, online={self.online_status})>"

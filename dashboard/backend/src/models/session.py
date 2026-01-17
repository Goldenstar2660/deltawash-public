"""
SQLAlchemy model for Session entity.

Represents a single handwashing event performed at a device.
"""
from sqlalchemy import Column, String, UUID, TIMESTAMP, Integer, Boolean, ForeignKey, ARRAY, CheckConstraint, func
from sqlalchemy.orm import relationship
import uuid

from ..database import Base


class Session(Base):
    """Session model representing a handwashing session."""
    
    __tablename__ = "sessions"
    
    # Columns
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)
    timestamp = Column(TIMESTAMP(timezone=True), nullable=False)
    duration_ms = Column(Integer, nullable=False)
    compliant = Column(Boolean, nullable=False)
    low_quality = Column(Boolean, nullable=False, default=False)
    missed_steps = Column(ARRAY(Integer), default=list)
    config_version = Column(String(50), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    
    # Constraints
    __table_args__ = (
        CheckConstraint('duration_ms >= 5000 AND duration_ms <= 120000', name='check_duration_range'),
    )
    
    # Relationships
    device = relationship("Device", back_populates="sessions")
    steps = relationship("Step", back_populates="session", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Session(id={self.id}, device_id={self.device_id}, compliant={self.compliant})>"

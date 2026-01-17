"""
SQLAlchemy model for Device entity.

Represents a physical handwashing compliance system deployed at a hospital unit.
"""
from sqlalchemy import Column, String, UUID, TIMESTAMP, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import relationship
import uuid

from ..database import Base


class Device(Base):
    """Device model representing a handwashing compliance device."""
    
    __tablename__ = "devices"
    
    # Columns
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    unit_id = Column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"), nullable=False)
    device_name = Column(String(100), nullable=False)
    firmware_version = Column(String(20), nullable=True)
    installation_date = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('unit_id', 'device_name', name='uq_device_name_per_unit'),
    )
    
    # Relationships
    unit = relationship("Unit", back_populates="devices")
    sessions = relationship("Session", back_populates="device", cascade="all, delete-orphan")
    heartbeats = relationship("Heartbeat", back_populates="device", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Device(id={self.id}, name={self.device_name}, unit_id={self.unit_id})>"

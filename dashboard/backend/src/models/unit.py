"""
SQLAlchemy model for Unit entity.

Represents a physical location or organizational division within a hospital.
"""
from sqlalchemy import Column, String, UUID, TIMESTAMP, func
from sqlalchemy.orm import relationship
import uuid

from ..database import Base


class Unit(Base):
    """Unit model representing a hospital unit (e.g., ICU, ER, Surgery)."""
    
    __tablename__ = "units"
    
    # Columns
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    unit_name = Column(String(100), nullable=False)
    unit_code = Column(String(20), nullable=False, unique=True)
    hospital_id = Column(UUID(as_uuid=True), nullable=True)  # Future: FK to hospitals table
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    devices = relationship("Device", back_populates="unit", cascade="all, delete-orphan")
    users = relationship("User", back_populates="unit")
    
    def __repr__(self):
        return f"<Unit(id={self.id}, code={self.unit_code}, name={self.unit_name})>"

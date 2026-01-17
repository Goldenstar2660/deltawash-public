"""
SQLAlchemy model for Step entity.

Represents a specific WHO handwashing step within a session.
"""
from sqlalchemy import Column, UUID, TIMESTAMP, Integer, Boolean, Float, ForeignKey, CheckConstraint, func
from sqlalchemy.orm import relationship
import uuid

from ..database import Base


class Step(Base):
    """Step model representing a WHO handwashing step."""
    
    __tablename__ = "steps"
    
    # Columns
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    step_id = Column(Integer, nullable=False)
    duration_ms = Column(Integer, nullable=False)
    completed = Column(Boolean, nullable=False)
    confidence_score = Column(Float, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    
    # Constraints
    __table_args__ = (
        CheckConstraint('step_id >= 2 AND step_id <= 7', name='check_step_id_range'),
        CheckConstraint('duration_ms >= 0', name='check_duration_non_negative'),
        CheckConstraint('confidence_score IS NULL OR (confidence_score >= 0.0 AND confidence_score <= 1.0)', name='check_confidence_range'),
    )
    
    # Relationships
    session = relationship("Session", back_populates="steps")
    
    def __repr__(self):
        return f"<Step(id={self.id}, session_id={self.session_id}, step_id={self.step_id}, completed={self.completed})>"

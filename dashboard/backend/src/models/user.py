"""
SQLAlchemy model for User entity.

Represents a dashboard user with role-based access control.
"""
from sqlalchemy import Column, String, UUID, TIMESTAMP, ForeignKey, CheckConstraint, func
from sqlalchemy.orm import relationship
import uuid

from ..database import Base


class User(Base):
    """User model for dashboard authentication and RBAC."""
    
    __tablename__ = "users"
    
    # Columns
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False)
    unit_id = Column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    last_login_at = Column(TIMESTAMP(timezone=True), nullable=True)
    
    # Constraints
    __table_args__ = (
        CheckConstraint(
            "role IN ('org_admin', 'analyst', 'unit_manager', 'technician')",
            name='check_valid_role'
        ),
        CheckConstraint(
            "(role = 'unit_manager' AND unit_id IS NOT NULL) OR (role != 'unit_manager' AND unit_id IS NULL)",
            name='check_unit_manager_has_unit'
        ),
    )
    
    # Relationships
    unit = relationship("Unit", back_populates="users")
    
    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"

"""
Units API endpoints for retrieving organizational units.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from ..dependencies import get_db
from ..models.unit import Unit
from pydantic import BaseModel, ConfigDict
from uuid import UUID


# Schemas
class UnitResponse(BaseModel):
    """Response schema for unit information."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    unit_name: str
    unit_code: str


# Router
router = APIRouter(tags=["units"])


@router.get("/units", response_model=List[UnitResponse])
async def get_units(db: Session = Depends(get_db)) -> List[UnitResponse]:
    """
    Retrieve all units.
    
    Returns:
        List of units with id, name, and code.
    """
    units = db.query(Unit).order_by(Unit.unit_name).all()
    return units

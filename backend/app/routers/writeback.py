
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import List, Optional
from app.database import get_db
from app.services.writeback_engine import get_writeback_engine

router = APIRouter(prefix="/api/writeback", tags=["writeback"])

class WritebackRequest(BaseModel):
    anomalies: List[dict]
    target_system: str = "1C" # 1C | SAP | Oracle

@router.post("/push")
async def push_corrections(payload: WritebackRequest, db: AsyncSession = Depends(get_db)):
    """
    Triggers the Reverse ETL process to push corrections to the source system.
    """
    engine = await get_writeback_engine(db)
    
    # 1. Prepare the package
    package_json = await engine.prepare_correction_package(payload.anomalies)
    
    # 2. Push to target (Simulated OData for now as per Gold Niche spec)
    result = await engine.push_to_1c_odata(package_json, "https://erp.socar.ge/odata")
    
    return {
        "status": "success",
        "message": "Corrections pushed to ERP staging",
        "details": result
    }

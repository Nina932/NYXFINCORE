from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import AsyncSessionLocal
from app.models.all_models import MarketingRequest
from pydantic import BaseModel, EmailStr
from typing import Optional
import logging

logger = logging.getLogger("finai")
router = APIRouter(prefix="/api/marketing", tags=["marketing"])

class MarketingRequestCreate(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    company: Optional[str] = None
    metadata: Optional[dict] = None

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

@router.post("/request")
async def create_marketing_request(
    data: MarketingRequestCreate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Capture a lead from the marketing landing page."""
    try:
        # Check if already exists (optional, maybe they want to request twice)
        
        # Capture some basic metadata from the request
        meta = data.metadata or {}
        meta["ip"] = request.client.host if request.client else "unknown"
        meta["user_agent"] = request.headers.get("user-agent", "unknown")

        new_request = MarketingRequest(
            email=data.email,
            name=data.name,
            company=data.company,
            metadata_json=meta
        )
        
        db.add(new_request)
        await db.commit()
        await db.refresh(new_request)
        
        logger.info(f"Marketing request captured: {data.email}")
        return {"status": "success", "message": "Request logged", "id": new_request.id}
    except Exception as e:
        logger.error(f"Error capturing marketing request: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/requests")
async def list_marketing_requests(
    db: AsyncSession = Depends(get_db)
):
    """Admin-only list of leads (in a real app, this would be guarded)."""
    # Note: In a production app, we'd add @admin_required
    from sqlalchemy import select
    result = await db.execute(select(MarketingRequest).order_by(MarketingRequest.created_at.desc()))
    requests = result.scalars().all()
    return [r.to_dict() for r in requests]

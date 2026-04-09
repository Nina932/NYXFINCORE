"""
Schema profile management — human-in-loop for adaptive validation.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.all_models import SchemaProfile, SchemaVersion, SchemaProposal

router = APIRouter(prefix="/api/schemas", tags=["schemas"])


@router.get("/profiles")
async def list_profiles(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(SchemaProfile).order_by(SchemaProfile.created_at.desc()))
    return [p.to_dict() for p in res.scalars().all()]


@router.get("/proposals")
async def list_proposals(status: str = "pending", db: AsyncSession = Depends(get_db)):
    q = select(SchemaProposal).order_by(SchemaProposal.created_at.desc())
    if status:
        q = q.where(SchemaProposal.status == status)
    res = await db.execute(q)
    return [p.to_dict() for p in res.scalars().all()]


@router.post("/proposals/{proposal_id}/approve")
async def approve_proposal(proposal_id: int, payload: dict = None, db: AsyncSession = Depends(get_db)):
    p = (await db.execute(select(SchemaProposal).where(SchemaProposal.id == proposal_id))).scalar_one_or_none()
    if not p:
        raise HTTPException(404, "Proposal not found")
    if p.status == "approved":
        return {"message": "Already approved", "proposal_id": p.id, "profile_id": p.approved_profile_id}

    payload = payload or {}
    profile_name = payload.get("profile_name") or f"Profile for {p.file_name}"
    file_type = payload.get("file_type") or "Financial Data"
    business_unit = payload.get("business_unit")

    profile = SchemaProfile(name=profile_name, file_type=file_type, business_unit=business_unit, is_active=True)
    db.add(profile)
    await db.flush()

    version = SchemaVersion(profile_id=profile.id, version=1, rules_json=p.suggested_rules_json, is_active=True)
    db.add(version)

    p.status = "approved"
    p.approved_profile_id = profile.id
    await db.commit()
    return {"message": "Approved", "proposal_id": p.id, "profile_id": profile.id}


@router.post("/proposals/{proposal_id}/reject")
async def reject_proposal(proposal_id: int, db: AsyncSession = Depends(get_db)):
    p = (await db.execute(select(SchemaProposal).where(SchemaProposal.id == proposal_id))).scalar_one_or_none()
    if not p:
        raise HTTPException(404, "Proposal not found")
    p.status = "rejected"
    await db.commit()
    return {"message": "Rejected", "proposal_id": p.id}

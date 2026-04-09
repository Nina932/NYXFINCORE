"""
FinAI Custom Tools Router — syncs with frontend CUSTOM_TOOLS array
Frontend stores tools in IndexedDB; backend mirrors them for persistence
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, Dict, Any
from app.database import get_db
from app.models.all_models import CustomTool

router = APIRouter(prefix="/api/tools", tags=["tools"])


class ToolCreate(BaseModel):
    name:         str
    description:  str
    code:         str
    input_schema: Optional[Dict[str, Any]] = None
    is_active:    bool = True


class ToolUpdate(BaseModel):
    description:  Optional[str] = None
    code:         Optional[str] = None
    input_schema: Optional[Dict[str, Any]] = None
    is_active:    Optional[bool] = None


@router.get("")
async def list_tools(db: AsyncSession = Depends(get_db)):
    """List all custom tools. Frontend syncs this on startup."""
    result = await db.execute(select(CustomTool).order_by(CustomTool.created_at.desc()))
    return [t.to_dict() for t in result.scalars().all()]


@router.post("")
async def create_tool(payload: ToolCreate, db: AsyncSession = Depends(get_db)):
    """Create a new custom tool. Called when user saves a tool in Training Hub."""
    existing = (await db.execute(select(CustomTool).where(CustomTool.name == payload.name))).scalar_one_or_none()
    if existing:
        raise HTTPException(409, f"Tool '{payload.name}' already exists. Use PUT to update.")

    tool = CustomTool(
        name=payload.name,
        description=payload.description,
        code=payload.code,
        input_schema=payload.input_schema or {"type": "object", "properties": {}},
        is_active=payload.is_active,
    )
    db.add(tool)
    await db.commit()
    return tool.to_dict()


@router.get("/{tool_id}")
async def get_tool(tool_id: int, db: AsyncSession = Depends(get_db)):
    t = (await db.execute(select(CustomTool).where(CustomTool.id == tool_id))).scalar_one_or_none()
    if not t:
        raise HTTPException(404, "Tool not found")
    return t.to_dict()


@router.put("/{tool_id}")
async def update_tool(tool_id: int, payload: ToolUpdate, db: AsyncSession = Depends(get_db)):
    t = (await db.execute(select(CustomTool).where(CustomTool.id == tool_id))).scalar_one_or_none()
    if not t:
        raise HTTPException(404, "Tool not found")
    if payload.description  is not None: t.description  = payload.description
    if payload.code         is not None: t.code         = payload.code
    if payload.input_schema is not None: t.input_schema = payload.input_schema
    if payload.is_active    is not None: t.is_active    = payload.is_active
    await db.commit()
    return t.to_dict()


@router.delete("/{tool_id}")
async def delete_tool(tool_id: int, db: AsyncSession = Depends(get_db)):
    t = (await db.execute(select(CustomTool).where(CustomTool.id == tool_id))).scalar_one_or_none()
    if not t:
        raise HTTPException(404, "Tool not found")
    await db.delete(t)
    await db.commit()
    return {"message": "Tool deleted", "id": tool_id}


@router.post("/sync")
async def sync_tools(tools: list, db: AsyncSession = Depends(get_db)):
    """
    Bulk sync frontend CUSTOM_TOOLS array to database.
    Frontend calls this after user edits tools in the Training Hub.
    """
    saved = []
    for t_data in tools:
        name = t_data.get("name", "").strip()
        if not name:
            continue
        existing = (await db.execute(select(CustomTool).where(CustomTool.name == name))).scalar_one_or_none()
        if existing:
            existing.description  = t_data.get("description", existing.description)
            existing.code         = t_data.get("code",         existing.code)
            existing.input_schema = t_data.get("input_schema", existing.input_schema)
            saved.append(existing.to_dict())
        else:
            tool = CustomTool(
                name=name,
                description=t_data.get("description", ""),
                code=t_data.get("code", ""),
                input_schema=t_data.get("input_schema") or {"type":"object","properties":{}},
            )
            db.add(tool)
            await db.flush()
            saved.append(tool.to_dict())
    await db.commit()
    return {"synced": len(saved), "tools": saved}

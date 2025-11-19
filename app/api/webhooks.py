from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from app.database import get_db
from app.models.webhook import Webhook
from app.schemas import WebhookCreate, WebhookUpdate, WebhookResponse
from app.utils.webhook_trigger import test_webhook
import httpx

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.get("", response_model=List[WebhookResponse])
async def list_webhooks(db: AsyncSession = Depends(get_db)):
    """List all webhooks."""
    result = await db.execute(select(Webhook).order_by(Webhook.id.desc()))
    webhooks = result.scalars().all()
    return [WebhookResponse.model_validate(w) for w in webhooks]


@router.post("", response_model=WebhookResponse, status_code=201)
async def create_webhook(webhook: WebhookCreate, db: AsyncSession = Depends(get_db)):
    """Create a new webhook."""
    db_webhook = Webhook(
        url=webhook.url,
        event_types=webhook.event_types,
        enabled=webhook.enabled
    )
    
    db.add(db_webhook)
    await db.commit()
    await db.refresh(db_webhook)
    
    return WebhookResponse.model_validate(db_webhook)


@router.get("/{webhook_id}", response_model=WebhookResponse)
async def get_webhook(webhook_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single webhook by ID."""
    result = await db.execute(select(Webhook).where(Webhook.id == webhook_id))
    webhook = result.scalar_one_or_none()
    
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    return WebhookResponse.model_validate(webhook)


@router.put("/{webhook_id}", response_model=WebhookResponse)
async def update_webhook(
    webhook_id: int,
    webhook_update: WebhookUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update an existing webhook."""
    result = await db.execute(select(Webhook).where(Webhook.id == webhook_id))
    db_webhook = result.scalar_one_or_none()
    
    if not db_webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    # Update fields
    update_data = webhook_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_webhook, field, value)
    
    await db.commit()
    await db.refresh(db_webhook)
    
    return WebhookResponse.model_validate(db_webhook)


@router.delete("/{webhook_id}", status_code=204)
async def delete_webhook(webhook_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a webhook."""
    result = await db.execute(select(Webhook).where(Webhook.id == webhook_id))
    webhook = result.scalar_one_or_none()
    
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    await db.delete(webhook)
    await db.commit()
    
    return None


@router.post("/{webhook_id}/test", status_code=200)
async def test_webhook_endpoint(webhook_id: int, db: AsyncSession = Depends(get_db)):
    """Test a webhook by sending a test event."""
    result = await db.execute(select(Webhook).where(Webhook.id == webhook_id))
    webhook = result.scalar_one_or_none()
    
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    if not webhook.enabled:
        raise HTTPException(status_code=400, detail="Webhook is disabled")
    
    # Test the webhook
    try:
        result = await test_webhook(webhook, {"event": "test", "message": "This is a test webhook"})
        return {
            "success": True,
            "status_code": result["status_code"],
            "response_time_ms": result["response_time_ms"],
            "message": "Webhook test successful"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Webhook test failed: {str(e)}")


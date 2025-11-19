import httpx
import asyncio
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.webhook import Webhook
from app.models.product import Product
import json
from datetime import datetime


async def trigger_webhooks(
    event_type: str,
    product: Product,
    db: AsyncSession,
    test_data: Optional[Dict[str, Any]] = None
):
    """
    Trigger webhooks for a product event.
    
    Args:
        event_type: Event type (product.created, product.updated, product.deleted)
        product: Product instance
        db: Database session
        test_data: Optional test data (for testing webhooks)
    """
    # Get enabled webhooks that listen to this event type
    result = await db.execute(
        select(Webhook).where(
            Webhook.enabled == True
        )
    )
    webhooks = result.scalars().all()
    
    # Filter webhooks that listen to this event type
    relevant_webhooks = [
        w for w in webhooks
        if event_type in w.event_types
    ]
    
    if not relevant_webhooks:
        return
    
    # Prepare payload
    if test_data:
        payload = test_data
    else:
        payload = {
            "event": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "id": product.id,
                "name": product.name,
                "sku": product.sku,
                "description": product.description,
                "active": product.active,
                "created_at": product.created_at.isoformat() if product.created_at else None,
                "updated_at": product.updated_at.isoformat() if product.updated_at else None,
            }
        }
    
    # Trigger webhooks asynchronously (fire and forget)
    async def send_webhook(webhook: Webhook):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    webhook.url,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                # Log response (in production, you might want to store this)
                return {
                    "webhook_id": webhook.id,
                    "status_code": response.status_code,
                    "success": 200 <= response.status_code < 300
                }
        except Exception as e:
            # Log error (in production, you might want to store this)
            return {
                "webhook_id": webhook.id,
                "error": str(e),
                "success": False
            }
    
    # Send all webhooks concurrently
    tasks = [send_webhook(w) for w in relevant_webhooks]
    await asyncio.gather(*tasks, return_exceptions=True)


async def test_webhook(webhook: Webhook, test_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Test a webhook by sending a test payload.
    
    Returns:
        Dictionary with status_code and response_time_ms
    """
    import time
    
    start_time = time.time()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                webhook.url,
                json=test_data,
                headers={"Content-Type": "application/json"}
            )
            response_time_ms = (time.time() - start_time) * 1000
            
            return {
                "status_code": response.status_code,
                "response_time_ms": round(response_time_ms, 2),
                "success": 200 <= response.status_code < 300
            }
    except httpx.TimeoutException:
        response_time_ms = (time.time() - start_time) * 1000
        raise Exception(f"Webhook request timed out after {response_time_ms:.2f}ms")
    except Exception as e:
        response_time_ms = (time.time() - start_time) * 1000
        raise Exception(f"Webhook request failed: {str(e)}")


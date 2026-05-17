from __future__ import annotations

from uuid import uuid4

import httpx
from fastapi import FastAPI, HTTPException

from shared.smartdoc_common import (
    NotificationRequest,
    Role,
    Settings,
    WebhookSubscription,
    WebhookSubscriptionRequest,
    has_permission,
)

settings = Settings(service_name="notification-service", service_port=8608)
app = FastAPI(title="SmartDoc Notification Service", version="1.0.0")

notifications: list[dict] = []
subscriptions: dict[str, WebhookSubscription] = {}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.post("/webhooks")
async def add_webhook(request: WebhookSubscriptionRequest, actor_role: Role = Role.INTEGRATOR) -> dict:
    if not has_permission(actor_role, "webhook:manage"):
        raise HTTPException(status_code=403, detail=f"Role {actor_role.value} cannot manage webhooks")
    subscription = WebhookSubscription(
        subscription_id=str(uuid4()),
        url=request.url,
        events=request.events,
        secret=request.secret,
    )
    subscriptions[subscription.subscription_id] = subscription
    return subscription.model_dump(mode="json")


@app.get("/webhooks")
async def list_webhooks() -> dict:
    items = [item.model_dump(mode="json") for item in subscriptions.values()]
    return {"items": items, "count": len(items)}


@app.delete("/webhooks/{subscription_id}")
async def disable_webhook(subscription_id: str, actor_role: Role = Role.INTEGRATOR) -> dict:
    if not has_permission(actor_role, "webhook:manage"):
        raise HTTPException(status_code=403, detail=f"Role {actor_role.value} cannot manage webhooks")
    subscription = subscriptions.get(subscription_id)
    if subscription is None:
        raise HTTPException(status_code=404, detail="Webhook not found")
    subscription.active = False
    return {"subscription_id": subscription_id, "active": False}


async def _deliver_webhook(event: dict, hooks: list[WebhookSubscription]) -> list[dict]:
    deliveries: list[dict] = []
    if not hooks:
        return deliveries

    async with httpx.AsyncClient(timeout=5.0) as client:
        for hook in hooks:
            payload = {"event": event, "subscription_id": hook.subscription_id}
            headers = {"X-SmartDoc-Event": event["event_type"]}
            if hook.secret:
                headers["X-SmartDoc-Secret"] = hook.secret
            try:
                response = await client.post(hook.url, json=payload, headers=headers)
                deliveries.append(
                    {
                        "subscription_id": hook.subscription_id,
                        "status_code": response.status_code,
                        "ok": response.status_code < 400,
                    }
                )
            except Exception as exc:  # noqa: BLE001
                deliveries.append(
                    {
                        "subscription_id": hook.subscription_id,
                        "status_code": None,
                        "ok": False,
                        "error": str(exc),
                    }
                )
    return deliveries


@app.post("/notify")
async def notify(request: NotificationRequest) -> dict:
    item = {
        "notification_id": str(uuid4()),
        "doc_id": request.doc_id,
        "event_type": request.event_type,
        "message": request.message,
        "recipient": request.recipient,
        "severity": request.severity,
    }
    hooks = [
        hook
        for hook in subscriptions.values()
        if hook.active and (not hook.events or request.event_type in hook.events)
    ]
    deliveries = await _deliver_webhook(item, hooks)
    item["deliveries"] = deliveries
    notifications.append(item)
    return item


@app.get("/notify/history")
async def history(limit: int = 200) -> dict:
    return {"items": notifications[-limit:], "count": min(limit, len(notifications))}

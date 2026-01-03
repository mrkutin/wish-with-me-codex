import json
from typing import Any

import aio_pika

from app.config import settings
from app.utils import new_uuid, utcnow


_connection: aio_pika.RobustConnection | None = None


async def get_connection() -> aio_pika.RobustConnection:
    global _connection
    if _connection is None:
        _connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    return _connection


async def publish_event(event_type: str, data: dict[str, Any], trace_id: str | None) -> None:
    connection = await get_connection()
    channel = await connection.channel()
    exchange = await channel.declare_exchange("wishlist.events", aio_pika.ExchangeType.TOPIC, durable=True)
    envelope = {
        "message_id": new_uuid(),
        "type": event_type,
        "occurred_at": utcnow().isoformat(),
        "trace_id": trace_id,
        "data": data,
    }
    message = aio_pika.Message(body=json.dumps(envelope).encode("utf-8"), delivery_mode=aio_pika.DeliveryMode.PERSISTENT)
    await exchange.publish(message, routing_key=event_type)
    await channel.close()

"""Kafka produce helper for banking → payments.events."""

from __future__ import annotations

import json
import logging
import os

from common.kafka_auth import kafka_client_kwargs

log = logging.getLogger("banking.kafka")

_producer = None


def _get_producer():
    global _producer
    if _producer is not None:
        return _producer
    from kafka import KafkaProducer

    kw = kafka_client_kwargs()
    _producer = KafkaProducer(
        **kw,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        key_serializer=lambda v: v.encode("utf-8") if v else None,
        acks="all",
        retries=int(os.getenv("KAFKA_PRODUCER_RETRIES", "5")),
        max_in_flight_requests_per_connection=5,
        linger_ms=int(os.getenv("KAFKA_LINGER_MS", "20")),
        batch_size=int(os.getenv("KAFKA_BATCH_SIZE", "32768")),
        request_timeout_ms=int(os.getenv("KAFKA_REQUEST_TIMEOUT_MS", "30000")),
        compression_type=os.getenv("KAFKA_COMPRESSION", "gzip") or None,
    )
    return _producer


def publish_json(topic: str, payload: dict, key: str | None = None) -> bool:
    bootstrap = os.getenv("KAFKA_BOOTSTRAP", "").strip()
    if not bootstrap:
        log.info("kafka skipped (no bootstrap): topic=%s key=%s", topic, key)
        return False
    try:
        producer = _get_producer()
        fut = producer.send(topic, value=payload, key=key)
        fut.get(timeout=30)
        log.info("kafka published topic=%s key=%s event=%s", topic, key, payload.get("event"))
        return True
    except Exception as exc:
        log.warning("kafka publish failed: %s", exc)
        return False

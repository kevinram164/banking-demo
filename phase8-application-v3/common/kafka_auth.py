"""Kafka client auth — plain or SASL_SSL + SCRAM (platform Strimzi)."""

from __future__ import annotations

import logging
import os

log = logging.getLogger("banking.kafka.auth")


def kafka_client_kwargs() -> dict:
    bootstrap = os.getenv("KAFKA_BOOTSTRAP", "").strip()
    kw: dict = {"bootstrap_servers": [s.strip() for s in bootstrap.split(",") if s.strip()]}
    protocol = os.getenv("KAFKA_SECURITY_PROTOCOL", "").strip()
    if not protocol:
        return kw

    kw["security_protocol"] = protocol
    if protocol in ("SASL_SSL", "SASL_PLAINTEXT"):
        kw["sasl_mechanism"] = os.getenv("KAFKA_SASL_MECHANISM", "SCRAM-SHA-512")
        kw["sasl_plain_username"] = os.getenv("KAFKA_USERNAME", "npd-banking")
        password = os.getenv("KAFKA_PASSWORD", "")
        if not password:
            log.warning("KAFKA_SECURITY_PROTOCOL=%s but KAFKA_PASSWORD empty", protocol)
        kw["sasl_plain_password"] = password

    if protocol in ("SSL", "SASL_SSL"):
        cafile = os.getenv("KAFKA_SSL_CAFILE", "/etc/kafka/certs/ca.crt")
        if os.path.isfile(cafile):
            kw["ssl_cafile"] = cafile
        else:
            log.warning("KAFKA SSL CA missing at %s — TLS verify may fail", cafile)

    return kw

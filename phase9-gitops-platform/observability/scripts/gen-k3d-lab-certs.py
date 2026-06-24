#!/usr/bin/env python3
"""Generate static Linkerd lab CA + issuer (k3d). LAB ONLY — do not use in production."""
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

OUT = (
    Path(__file__).resolve().parent.parent
    / "manifests"
    / "linkerd-identity-k3d"
    / "certs"
)
OUT.mkdir(parents=True, exist_ok=True)

ca_key = ec.generate_private_key(ec.SECP256R1())
ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "root.linkerd.cluster.local")])
ca_cert = (
    x509.CertificateBuilder()
    .subject_name(ca_name)
    .issuer_name(ca_name)
    .public_key(ca_key.public_key())
    .serial_number(x509.random_serial_number())
    .not_valid_before(datetime.now(timezone.utc) - timedelta(days=1))
    .not_valid_after(datetime.now(timezone.utc) + timedelta(days=3650))
    .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
    .add_extension(
        x509.KeyUsage(
            digital_signature=True,
            key_cert_sign=True,
            crl_sign=True,
            key_agreement=False,
            content_commitment=False,
            key_encipherment=False,
            data_encipherment=False,
            encipher_only=False,
            decipher_only=False,
        ),
        critical=True,
    )
    .sign(ca_key, hashes.SHA256())
)

issuer_key = ec.generate_private_key(ec.SECP256R1())
issuer_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "identity.linkerd.cluster.local")])
issuer_cert = (
    x509.CertificateBuilder()
    .subject_name(issuer_name)
    .issuer_name(ca_name)
    .public_key(issuer_key.public_key())
    .serial_number(x509.random_serial_number())
    .not_valid_before(datetime.now(timezone.utc) - timedelta(days=1))
    .not_valid_after(datetime.now(timezone.utc) + timedelta(days=3650))
    .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
    .add_extension(
        x509.KeyUsage(
            digital_signature=True,
            key_cert_sign=True,
            crl_sign=True,
            key_agreement=False,
            content_commitment=False,
            key_encipherment=False,
            data_encipherment=False,
            encipher_only=False,
            decipher_only=False,
        ),
        critical=True,
    )
    .add_extension(
        x509.SubjectAlternativeName([x509.DNSName("identity.linkerd.cluster.local")]),
        critical=False,
    )
    .sign(ca_key, hashes.SHA256())
)

(OUT / "ca.crt").write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))
(OUT / "ca.key").write_bytes(
    ca_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    )
)
(OUT / "issuer.crt").write_bytes(issuer_cert.public_bytes(serialization.Encoding.PEM))
(OUT / "issuer.key").write_bytes(
    issuer_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    )
)
print(f"OK: wrote certs to {OUT}")

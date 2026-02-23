"""Minimal HTTP health server for Phase 8 consumers (no FastAPI)."""
import asyncio


async def run_health_server(port: int = 9999, service_name: str = "consumer"):
    """Run a minimal HTTP server that responds 200 on GET /health."""

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            await reader.read(1024)
            body = b'{"status":"healthy","service":"' + service_name.encode() + b'"}'
            writer.write(
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: application/json\r\n"
                b"Content-Length: " + str(len(body)).encode() + b"\r\n"
                b"\r\n" + body
            )
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(handle, "0.0.0.0", port)
    async with server:
        await server.serve_forever()


def start_health_background(port: int = 9999, service_name: str = "consumer"):
    """Start health server as background task."""
    return asyncio.create_task(run_health_server(port, service_name))

# example-server.py
import os
import asyncio
from datetime import datetime
from typing import Dict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import logging
import sys

app = FastAPI()
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s", handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)

# === Global state ===
capslock_enabled = False
connected_clients: Dict[WebSocket, str] = {}  # websocket -> client id / IP
last_websocket_update: Dict[WebSocket, datetime] = {}  # rate-limiting (optional)

# === Simple HTML page for testing ===
html = """
<!DOCTYPE html>
<html>
  <body>
    <h1>WebSocket server is online!</h1>
    <p>Connect with your client.py script to /ws</p>
  </body>
</html>
"""

@app.get("/")
async def get_root():
    return HTMLResponse(html)

def message_for_state():
    return "1" if capslock_enabled else "0"

async def broadcast_state(message: str):
    for websocket in list(connected_clients.keys()):  # iterate over a copy
        try:
            await websocket.send_text(message)
        except Exception:
            client_id = connected_clients.pop(websocket, "unknown")
            last_websocket_update.pop(websocket, None)
            logger.info(f"Removed disconnected client {client_id}")


def can_update(websocket: WebSocket) -> bool:
    # Optional: implement per-client rate limiting if needed
    return True

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global capslock_enabled
    await websocket.accept()
    client_id = str(websocket.client)  # simple identifier
    connected_clients[websocket] = client_id
    logger.info(f"{client_id} connected ({len(connected_clients)} total)")

    # Send current state
    await websocket.send_text(message_for_state())

    try:
        while True:
            try:
                data = await websocket.receive_text()
                if not can_update(websocket):
                    continue

                if len(data) > 1:
                    logger.info(f"Received invalid data from {client_id}: {data}")
                elif data == "1" and capslock_enabled != True:
                    capslock_enabled = True
                    await broadcast_state(message_for_state())
                elif data == "0" and capslock_enabled != False:
                    capslock_enabled = False
                    await broadcast_state(message_for_state())
            except WebSocketDisconnect:
                # stop processing this client
                break
            except Exception as e:
                logger.warning(f"Error in client loop for {client_id}: {e}")
    finally:
        connected_clients.pop(websocket, None)
        last_websocket_update.pop(websocket, None)
        logger.info(f"{client_id} disconnected ({len(connected_clients)} remaining)")


# Optional: periodic broadcast to ensure all clients stay in sync
@app.on_event("startup")
async def startup_event():
    async def periodic_broadcast():
        last_message = None
        while True:
            message = message_for_state()
            if message != last_message:
                last_message = message
                await broadcast_state(message)
            await asyncio.sleep(0.05)  # 50ms
    asyncio.create_task(periodic_broadcast())

# === Run with uvicorn ===
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)


# I JUST WANT THIS TO WORK I DONT CARE ABOUT AI ANYMORE MAN LET ME HAVE FUNNNNN

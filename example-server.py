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
listening_clients: set[WebSocket] = set()
connected_clients: Dict[WebSocket, str] = {}  # websocket -> client id / IP
last_websocket_update: Dict[WebSocket, datetime] = {}  # rate-limiting (optional)

# === Simple HTML page for testing ===
html = """
<!DOCTYPE html>
<html>
  <head>
    <title>Not-So-Global-CapsLock</title>
    <style>
      body {
        font-family: sans-serif;
        text-align: center;
        margin-top: 50px;
      }
      .caps-state {
        font-size: 2em;
        margin: 20px;
        color: green;
      }
      .caps-state.off {
        color: red;
      }
      .clients-count {
        font-size: 1.2em;
      }
    </style>
  </head>
  <body>
    <h1>Not-So-Global-CapsLock</h1>
    <div id="capsState" class="caps-state off">Caps Lock is OFF</div>
    <div id="clientCount" class="clients-count">Connected: 0</div>

    <script>
      const capsDiv = document.getElementById("capsState");
      const clientsDiv = document.getElementById("clientCount");

      // Connect to status websocket
      const ws = new WebSocket(`wss://${window.location.host}/status`);

      ws.onmessage = (event) => {
        const data = event.data;

        if (data.startsWith("c ")) {
          // Update number of connected clients
          const count = data.split(" ")[1];
          clientsDiv.textContent = `Connected: ${count}`;
        } else if (data === "1") {
          capsDiv.textContent = "Caps Lock is ON";
          capsDiv.classList.remove("off");
          capsDiv.classList.add("on");
        } else if (data === "0") {
          capsDiv.textContent = "Caps Lock is OFF";
          capsDiv.classList.remove("on");
          capsDiv.classList.add("off");
        }
      };

      ws.onopen = () => console.log("Status WebSocket connected");
      ws.onclose = () => console.log("Status WebSocket disconnected");
    </script>
  </body>
</html>
"""


@app.get("/")
async def get_root():
    return HTMLResponse(html)

def message_for_state():
    return "1" if capslock_enabled else "0"

async def broadcast_state(message: str):
    for websocket in list(connected_clients.keys()):
        try:
            await websocket.send_text(message)
        except Exception:
            client_id = connected_clients.pop(websocket, "unknown")
            last_websocket_update.pop(websocket, None)
            logger.info(f"Removed disconnected client {client_id}")

    for websocket in list(listening_clients):
        try:
            await websocket.send_text(message)
        except Exception:
            listening_clients.remove(websocket)

def can_update(websocket: WebSocket) -> bool:
    # Optional: implement per-client rate limiting if needed
    return True

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global capslock_enabled
    await websocket.accept()
    client_id = str(websocket.client)
    connected_clients[websocket] = client_id
    logger.info(f"{client_id} connected ({len(connected_clients)} total)")

    # Send current state
    await websocket.send_text(message_for_state())

    try:
        while True:
            try:
                data = await websocket.receive_text()
            except WebSocketDisconnect:
                # Stop the loop immediately if client disconnects
                break

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
    finally:
        connected_clients.pop(websocket, None)
        last_websocket_update.pop(websocket, None)
        logger.info(f"{client_id} disconnected ({len(connected_clients)} remaining)")

@app.websocket("/status")
async def status_endpoint(websocket: WebSocket):
    await websocket.accept()
    listening_clients.add(websocket)
    client_id = str(websocket.client)
    logger.info(f"{client_id} is listening to status")

    try:
        # Send initial info
        await websocket.send_text(f"c {len(connected_clients)}")  # client count
        await websocket.send_text(message_for_state())            # Caps Lock state

        while True:
            # Periodically update them
            await asyncio.sleep(5)
            await websocket.send_text(f"c {len(connected_clients)}")
    except WebSocketDisconnect:
        pass
    finally:
        listening_clients.remove(websocket)
        logger.info(f"{client_id} stopped listening")


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

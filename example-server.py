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
        <title>not so global capslock</title>

        <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:ital,wght@0,100..800;1,100..800&display=swap" rel="stylesheet">

        <style>
            html{
                font-family: 'JetBrains Mono', sans-serif;
                background-color: rgb(41, 41, 46);
                color: rgb(215, 225, 233);
                overflow: hidden;
            }

            h1 {
                margin-bottom: 3rem;
                text-shadow: 0px 0px 5px rgba(255, 255, 255, 0.44);
            }

            body {
                text-align: center;
                margin-top: 50px;
            }

            .container{
                border: solid;
                border-radius: 10px;
                border-color: rgb(41, 14, 14);
                display: inline-block;
                background-color: rgb(60, 24, 24);
            }
            .container.on{
                border: solid;
                border-radius: 10px;
                border-color: rgb(14, 41, 16);
                display: inline-block;
                background-color: rgb(28, 60, 24);
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
                margin-top: 2rem;
                font-size: 1.2em;
            }

            .yap{
                margin-top: 5rem;
                bottom: 10px;
                right: 10px;
                font-size: 0.8em;
            }

            a{
                text-decoration: none;
                color: rgb(215, 225, 233);
            }
            a:hover{
                text-decoration: underline;
                color: rgb(0, 140, 255);
                text-shadow: 0px 0px 5px rgba(0, 213, 255, 0.44);
            }
      </style>
      </head>

      <body>
            <h1><a href="https://github.com/kommittt/not-so-global-capslock">not-so-global capslock</a></h1>

            <div id="container" class="container">
                <div id="capsState" class="caps-state off">caps lock is off</div>
            </div>
            
            <div id="clientCount" class="clients-count">there are 0 people currently syncing</div>

            <div class="yap">
                how this works: <br>
                everyone who is connected to the server will have their caps lock state synchronized <br>
                so if someone turns on their caps, everyone else's caps will turn on too <br>
                this can cause some chaos especially if there are a lot of people connected

                <br><br><br>
                <b>how to connect?</b> <br>
                1. <a href="https://raw.githubusercontent.com/kommittt/not-so-global-capslock/main/client.py">click here to download the client.py file if you haven't</a> <br>
                2. make sure you have python 3.10+ installed <br>
                3. open command prompt, then type in: pip install websockets <br>
                4. go to wherever you downloaded client.py <br>
                5. then open terminal in that location and run it by typing: python client.py <br>

                <br> <br>
                <a href="https://globalcapslock.com/">check out the original project here</a>
            </div>

            <script>
            const capsDiv = document.getElementById("capsState");
            const clientsDiv = document.getElementById("clientCount");
            const box = document.getElementById("container");

            // Connect to status websocket
            const ws = new WebSocket(`wss://${window.location.host}/status`);

            ws.onmessage = (event) => {
                const data = event.data;

                if (data.startsWith("c ")) {
                    // Update number of connected clients
                    const count = data.split(" ")[1];
                    clientsDiv.textContent = `there are ${count} people currently syncing`;
                } else if (data === "1") {
                    capsDiv.textContent = "CAPS LOCK IS ON";
                    capsDiv.classList.remove("off");
                    capsDiv.classList.add("on");
                    box.classList.remove("off");
                    box.classList.add("on");
                } else if (data === "0") {
                    capsDiv.textContent = "caps Lock is off";
                    capsDiv.classList.remove("on");
                    capsDiv.classList.add("off");
                    box.classList.remove("on");
                    box.classList.add("off");
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
    return True

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global capslock_enabled
    await websocket.accept()
    client_id = str(websocket.client)
    connected_clients[websocket] = client_id
    logger.info(f"{client_id} connected ({len(connected_clients)} total)")

    await websocket.send_text(message_for_state())

    try:
        while True:
            try:
                data = await websocket.receive_text()
            except WebSocketDisconnect:
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
        while True:
            # Periodically send both Caps Lock state and client count
            await websocket.send_text(f"c {len(connected_clients)}")
            await websocket.send_text(message_for_state())
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass
    finally:
        listening_clients.remove(websocket)
        logger.info(f"{client_id} stopped listening")

@app.on_event("start_

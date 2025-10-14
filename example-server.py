import asyncio
import websockets

connected = set()

async def handle_ws(websocket):
    connected.add(websocket)
    try:
        async for message in websocket:
            # broadcast to all other clients
            for conn in connected:
                if conn != websocket:
                    await conn.send(message)
    finally:
        connected.remove(websocket)

async def main():
    async with websockets.serve(handle_ws, "0.0.0.0", 8000):
        await asyncio.Future()  # keep running forever

asyncio.run(main())

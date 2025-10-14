import asyncio
import os
import websockets

# Keep track of connected clients
connected_clients = set()

async def handle_ws(websocket, path):
    if path != "/ws":
        # Reject any path except /ws
        await websocket.close(code=1008, reason="Invalid path")
        return

    connected_clients.add(websocket)
    print(f"Client connected ({len(connected_clients)} total)")

    try:
        async for message in websocket:
            print(f"Received: {message}")

            # Broadcast message to all other clients
            for client in connected_clients:
                if client != websocket:
                    try:
                        await client.send(message)
                    except Exception as e:
                        print(f"Error sending to client: {e}")
    except websockets.ConnectionClosed:
        pass
    finally:
        connected_clients.remove(websocket)
        print(f"Client disconnected ({len(connected_clients)} remaining)")

async def main():
    port = int(os.environ.get("PORT", 8000))
    print(f"Server running on port {port}")
    async with websockets.serve(handle_ws, "", port):
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())

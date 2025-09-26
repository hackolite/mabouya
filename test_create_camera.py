#!/usr/bin/env python3
import asyncio
import websockets
import json

async def create_test_camera():
    uri = "ws://localhost:8765"
    websocket = await websockets.connect(uri)
    
    # Ignore initial world_state message
    await websocket.recv()
    
    # Create a camera
    await websocket.send(json.dumps({
        "type": "create_camera",
        "position": [-1.916838053051368, 1.75, -2.3047472486529443],
        "name": "Camera_1"
    }))
    
    response = await websocket.recv()
    data = json.loads(response)
    print("Camera creation response:", data)
    
    await websocket.close()

if __name__ == "__main__":
    asyncio.run(create_test_camera())

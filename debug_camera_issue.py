#!/usr/bin/env python3
import asyncio
import websockets
import json

async def debug_camera_subscription():
    uri = "ws://localhost:8765"
    websocket = await websockets.connect(uri)
    
    print("Connected to server")
    
    # Ignore initial world_state message
    initial_msg = await websocket.recv()
    print(f"Initial message: {json.loads(initial_msg)['type']}")
    
    # Create a camera
    print("Creating camera...")
    await websocket.send(json.dumps({
        "type": "create_camera",
        "position": [-2, 2, -2],
        "name": "TestCamera"
    }))
    
    response = await websocket.recv()
    camera_data = json.loads(response)
    print(f"Camera created: {camera_data}")
    
    camera_id = camera_data['camera']['id']
    
    # Wait a moment for streaming loop to start
    await asyncio.sleep(1)
    
    # Subscribe to camera
    print(f"Subscribing to camera {camera_id}...")
    await websocket.send(json.dumps({
        "type": "subscribe_camera",
        "camera_id": camera_id
    }))
    
    subscription_response = await websocket.recv()
    sub_data = json.loads(subscription_response)
    print(f"Subscription response: {sub_data}")
    
    if sub_data['type'] == 'subscribed':
        print("Successfully subscribed, waiting for frames...")
        
        # Try to receive frames with timeout
        try:
            for i in range(3):  # Try to get 3 frames
                frame_msg = await asyncio.wait_for(websocket.recv(), timeout=15.0)
                frame_data = json.loads(frame_msg)
                if frame_data['type'] == 'camera_frame':
                    print(f"Received frame #{i+1}, size: {frame_data['width']}x{frame_data['height']}")
                else:
                    print(f"Unexpected message: {frame_data}")
        except asyncio.TimeoutError:
            print("TIMEOUT: No frames received!")
    else:
        print(f"Subscription failed: {sub_data}")
    
    await websocket.close()

if __name__ == "__main__":
    asyncio.run(debug_camera_subscription())

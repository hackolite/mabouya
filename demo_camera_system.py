#!/usr/bin/env python3
"""
Demo script showing the ultra-fast camera system in action
"""

import asyncio
import websockets
import json
import time

async def demo_camera_system():
    """Demonstrate the camera system performance"""
    uri = "ws://localhost:8765"
    
    try:
        async with websockets.connect(uri) as websocket:
            print("🔗 Connected to server")
            
            # Ignore initial messages
            await websocket.recv()  # world_state
            await websocket.recv()  # player_joined
            
            # Create a camera
            print("\n📹 Creating camera...")
            await websocket.send(json.dumps({
                "type": "create_camera",
                "position": [5, 5, 5],
                "name": "DemoCamera",
                "resolution": [240, 180]
            }))
            
            response = await websocket.recv()
            data = json.loads(response)
            print(f"✅ Camera created: {data.get('type')}")
            camera_id = data.get('camera', {}).get('id')
            
            if not camera_id:
                print("❌ Failed to get camera ID")
                return
            
            # Subscribe to camera stream
            print(f"\n📺 Subscribing to camera {camera_id}...")
            await websocket.send(json.dumps({
                "type": "subscribe_camera",
                "camera_id": camera_id
            }))
            
            response = await websocket.recv()
            data = json.loads(response)
            
            if data["type"] == "subscribed":
                print(f"✅ Subscribed to camera stream")
                
                # Receive some frames to test performance
                print("📊 Receiving frames to test real-time performance...")
                frame_count = 0
                start_time = time.time()
                
                for _ in range(10):  # Receive 10 frames
                    message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    data = json.loads(message)
                    
                    if data["type"] == "camera_frame":
                        frame_count += 1
                        frame_size = len(data["frame"])
                        resolution = f"{data['width']}x{data['height']}"
                        print(f"   Frame {frame_count}: {resolution}, {frame_size} bytes")
                
                end_time = time.time()
                elapsed = end_time - start_time
                fps = frame_count / elapsed
                
                print(f"\n🎯 Real-time streaming performance:")
                print(f"   Frames received: {frame_count}")
                print(f"   Time elapsed: {elapsed:.2f}s") 
                print(f"   Streaming FPS: {fps:.1f}")
                print(f"   ✅ Successful real-time camera streaming!")
                
            else:
                print(f"❌ Failed to subscribe: {data.get('message')}")
                
    except Exception as e:
        print(f"❌ Demo failed: {e}")

if __name__ == "__main__":
    asyncio.run(demo_camera_system())
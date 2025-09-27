#!/usr/bin/env python3
"""
Test script to verify that renderer type information is correctly displayed in camera viewer
"""

import asyncio
import websockets
import json
import time

async def test_renderer_display():
    """Test that renderer type is displayed correctly"""
    uri = "ws://localhost:8765"
    
    try:
        async with websockets.connect(uri) as websocket:
            print("🔗 Connected to server")
            
            # Ignore initial messages
            await websocket.recv()  # world_state
            await websocket.recv()  # player_joined
            
            # Create a camera
            print("📹 Creating test camera...")
            await websocket.send(json.dumps({
                "type": "create_camera",
                "position": [0, 5, 0],
                "name": "RendererTestCamera"
            }))
            
            response = await websocket.recv()
            data = json.loads(response)
            
            if data["type"] == "camera_created":
                camera_id = data["camera"]["id"]
                print(f"✅ Camera created: {camera_id}")
                
                # Subscribe to camera stream
                print(f"📺 Subscribing to camera {camera_id}...")
                await websocket.send(json.dumps({
                    "type": "subscribe_camera",
                    "camera_id": camera_id
                }))
                
                # Wait for subscription confirmation
                await websocket.recv()
                print("✅ Subscribed to camera stream")
                
                # Receive a few frames to test renderer type display
                print("📊 Testing renderer type display...")
                for i in range(3):
                    frame_data = await websocket.recv()
                    frame_msg = json.loads(frame_data)
                    
                    if frame_msg["type"] == "camera_frame":
                        renderer = frame_msg.get("renderer", "Unknown")
                        print(f"   Frame {i+1}: {frame_msg['width']}x{frame_msg['height']}, Renderer: {renderer}")
                        
                        # Verify renderer type is included
                        if renderer != "Unknown":
                            print(f"   ✅ Renderer type successfully included: {renderer}")
                        else:
                            print(f"   ❌ Renderer type missing or unknown")
                
                print("🎯 Test completed successfully!")
                
            else:
                print(f"❌ Failed to create camera: {data}")
                
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_renderer_display())
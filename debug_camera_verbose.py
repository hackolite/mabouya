#!/usr/bin/env python3
"""
Debug version of camera viewer with verbose logging
"""
import asyncio
import websockets
import json
import time

async def debug_camera_stream(camera_id, uri="ws://localhost:8765"):
    """Debug version with detailed logging"""
    print(f"🔍 Debug: Connecting to {uri}")
    
    try:
        websocket = await websockets.connect(uri)
        print(f"🔍 Debug: Connected successfully")
        
        # Ignore initial world_state message
        initial_msg = await websocket.recv()
        initial_data = json.loads(initial_msg)
        print(f"🔍 Debug: Received initial message: {initial_data['type']}")
        
        # Subscribe to camera
        print(f"🔍 Debug: Subscribing to camera {camera_id}")
        await websocket.send(json.dumps({
            "type": "subscribe_camera",
            "camera_id": camera_id
        }))
        
        subscription_response = await websocket.recv()
        sub_data = json.loads(subscription_response)
        print(f"🔍 Debug: Subscription response: {sub_data}")
        
        if sub_data['type'] != 'subscribed':
            print(f"❌ Subscription failed: {sub_data}")
            return
        
        print("🔍 Debug: Successfully subscribed, starting frame reception loop")
        frame_count = 0
        last_frame_time = time.time()
        
        while True:
            try:
                print(f"🔍 Debug: Waiting for frame #{frame_count + 1}...")
                message = await asyncio.wait_for(websocket.recv(), timeout=15.0)
                current_time = time.time()
                
                data = json.loads(message)
                if data['type'] == 'camera_frame':
                    frame_count += 1
                    time_since_last = current_time - last_frame_time
                    print(f"✅ Debug: Received frame #{frame_count}, time since last: {time_since_last:.2f}s")
                    last_frame_time = current_time
                    
                    # Stop after receiving 5 frames for debugging
                    if frame_count >= 5:
                        print("🔍 Debug: Received 5 frames, stopping test")
                        break
                else:
                    print(f"🔍 Debug: Unexpected message type: {data['type']}")
                    
            except asyncio.TimeoutError:
                print("❌ Debug: Timeout waiting for frame!")
                elapsed = time.time() - last_frame_time
                print(f"🔍 Debug: {elapsed:.2f} seconds since last frame")
                break
            except Exception as e:
                print(f"❌ Debug: Exception during frame reception: {e}")
                break
        
        await websocket.close()
        print("🔍 Debug: Connection closed")
        
    except Exception as e:
        print(f"❌ Debug: Connection error: {e}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python debug_camera_verbose.py <camera_id>")
        sys.exit(1)
    
    camera_id = sys.argv[1]
    asyncio.run(debug_camera_stream(camera_id))
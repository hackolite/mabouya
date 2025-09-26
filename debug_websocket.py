import asyncio
import websockets
import json

async def debug_connection():
    uri = "ws://localhost:8765"
    print(f"Connecting to {uri}")
    
    websocket = await websockets.connect(uri)
    print("Connected!")
    
    print("Receiving world state...")
    world_state = await websocket.recv()
    print(f"World state: {json.loads(world_state)['type']}")
    
    # Get cameras
    print("Getting cameras...")
    await websocket.send(json.dumps({"type": "get_cameras"}))
    cameras_response = await websocket.recv()
    cameras_data = json.loads(cameras_response)
    print(f"Cameras response: {cameras_data}")
    
    if cameras_data["cameras"]:
        camera_id = list(cameras_data["cameras"].keys())[0]
        print(f"Subscribing to camera: {camera_id}")
        
        await websocket.send(json.dumps({
            "type": "subscribe_camera",
            "camera_id": camera_id
        }))
        
        sub_response = await websocket.recv()
        print(f"Subscription response: {json.loads(sub_response)}")
        
        print("Waiting for frames...")
        for i in range(3):
            try:
                frame_msg = await asyncio.wait_for(websocket.recv(), timeout=3.0)
                frame_data = json.loads(frame_msg)
                print(f"Frame {i+1}: type={frame_data.get('type')}, camera_id={frame_data.get('camera_id')}")
            except asyncio.TimeoutError:
                print(f"Frame {i+1}: TIMEOUT")
                break
    
    await websocket.close()
    print("Connection closed.")

asyncio.run(debug_connection())

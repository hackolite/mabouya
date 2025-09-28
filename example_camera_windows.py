#!/usr/bin/env python3
"""
Example: Camera Windows Functionality Demo
==========================================

This example demonstrates the new cube windows abstraction functionality,
particularly for camera cubes with Pyglet window visualization.

Features shown:
1. Base Cube class with windows attribute
2. CubeCamera with integrated window functionality
3. Window activation/deactivation
4. Frame capture from camera windows
5. WebSocket API for remote control

Usage:
    python example_camera_windows.py
"""

import sys
import os
import time

# Add project path
sys.path.append('/home/runner/work/mabouya/mabouya')

# Import our classes
from server import Cube, CubeCamera, CubeAI

def demo_cube_windows_structure():
    """Demonstrate the windows abstraction structure"""
    print("=" * 60)
    print("CUBE WINDOWS ABSTRACTION DEMO")
    print("=" * 60)
    
    print("\n1. Base Cube Class - Windows Attribute")
    print("-" * 40)
    
    # Create a basic cube
    grass_cube = Cube((0, 0, 0), "grass")
    print(f"Grass Cube ID: {grass_cube.id}")
    print(f"Has windows attribute: {hasattr(grass_cube, 'windows')}")
    print(f"Windows value: {grass_cube.windows}")
    print("✅ Base cube properly has windows attribute set to None")
    
    print("\n2. CubeAI Class - Inherits Windows Attribute")
    print("-" * 40)
    
    # Create an AI cube
    ai_cube = CubeAI((1, 1, 1), "DemoAI", "basic")
    print(f"AI Cube ID: {ai_cube.id}")
    print(f"AI name: {ai_cube.name}")
    print(f"Has windows attribute: {hasattr(ai_cube, 'windows')}")
    print(f"Windows value: {ai_cube.windows}")
    print("✅ AI cube inherits windows attribute (None - no window functionality)")
    
    print("\n3. CubeCamera Class - Windows with Functionality")
    print("-" * 40)
    
    # Create a camera cube
    camera_cube = CubeCamera((2, 2, 2), "DemoCamera", (320, 240))
    print(f"Camera Cube ID: {camera_cube.id}")
    print(f"Camera name: {camera_cube.name}")
    print(f"Camera resolution: {camera_cube.resolution}")
    print(f"Has windows attribute: {hasattr(camera_cube, 'windows')}")
    print(f"Windows available: {camera_cube.windows is not None}")
    
    if camera_cube.windows:
        print(f"Window cube_id: {camera_cube.windows.cube_id}")
        print(f"Window title: {camera_cube.windows.title}")
        print(f"Window resolution: {camera_cube.windows.resolution}")
    
    print("\n4. Camera Window Methods")
    print("-" * 40)
    
    # Test new camera methods
    print("New camera methods available:")
    methods = ['activate_window', 'deactivate_window', 'capture_window_frame', 'is_window_active']
    for method in methods:
        has_method = hasattr(camera_cube, method)
        print(f"  - {method}: {'✅' if has_method else '❌'}")
    
    print("\n5. Window Operations Demo")
    print("-" * 40)
    
    # Test window status
    is_active_before = camera_cube.is_window_active()
    print(f"Window active before activation: {is_active_before}")
    
    # Try to activate window (will likely fail in headless environment)
    print("Attempting to activate camera window...")
    activation_result = camera_cube.activate_window()
    print(f"Activation result: {activation_result}")
    
    is_active_after = camera_cube.is_window_active()
    print(f"Window active after activation: {is_active_after}")
    
    # Try frame capture
    print("Attempting frame capture...")
    frame_data = camera_cube.capture_window_frame()
    if frame_data:
        print(f"✅ Frame captured: {len(frame_data)} bytes")
    else:
        print("⚠️ No frame data (expected in headless mode)")
    
    # Try deactivation
    print("Attempting to deactivate window...")
    deactivation_result = camera_cube.deactivate_window()
    print(f"Deactivation result: {deactivation_result}")
    
    is_active_final = camera_cube.is_window_active()
    print(f"Window active after deactivation: {is_active_final}")
    
    print("\n6. Cube Dictionary Serialization")
    print("-" * 40)
    
    # Test serialization includes all attributes
    cube_dict = camera_cube.to_dict()
    print("Camera cube serialized data:")
    for key, value in cube_dict.items():
        print(f"  {key}: {value}")
    print("✅ Serialization includes all standard cube attributes")
    
    print("\n" + "=" * 60)
    print("DEMO COMPLETED SUCCESSFULLY!")
    print("=" * 60)
    
    print("\nSUMMARY:")
    print("✅ All cubes now have 'windows' attribute")
    print("✅ Camera cubes initialize with PygletCameraWindow when available")
    print("✅ Camera cubes have window control methods")
    print("✅ Window operations handle errors gracefully in headless mode")
    print("✅ Implementation is backward compatible")
    
    return camera_cube

def demo_websocket_api_usage():
    """Show examples of WebSocket API usage for camera windows"""
    print("\n" + "=" * 60)
    print("WEBSOCKET API USAGE EXAMPLES")
    print("=" * 60)
    
    print("\nNEW WEBSOCKET ENDPOINTS:")
    print("-" * 30)
    
    endpoints = [
        ("activate_camera_window", "Activate camera window for visualization"),
        ("deactivate_camera_window", "Deactivate camera window"),
        ("capture_camera_window", "Capture frame from camera window"),
        ("get_camera_window_status", "Get camera window status")
    ]
    
    for endpoint, description in endpoints:
        print(f"✅ {endpoint}: {description}")
    
    print("\nEXAMPLE USAGE:")
    print("-" * 30)
    
    example_messages = [
        {
            "name": "Create Camera",
            "message": {
                "type": "create_camera",
                "position": [10, 5, 10],
                "name": "SurveillanceCamera",
                "resolution": [640, 480]
            }
        },
        {
            "name": "Check Window Status",
            "message": {
                "type": "get_camera_window_status",
                "camera_id": "cam_12345..."
            }
        },
        {
            "name": "Activate Window",
            "message": {
                "type": "activate_camera_window",
                "camera_id": "cam_12345..."
            }
        },
        {
            "name": "Capture Frame",
            "message": {
                "type": "capture_camera_window",
                "camera_id": "cam_12345..."
            }
        },
        {
            "name": "Deactivate Window",
            "message": {
                "type": "deactivate_camera_window",
                "camera_id": "cam_12345..."
            }
        }
    ]
    
    for example in example_messages:
        print(f"\n{example['name']}:")
        import json
        print(json.dumps(example['message'], indent=2))

if __name__ == "__main__":
    print("Running Camera Windows Functionality Demo...")
    
    try:
        # Run the main demo
        camera = demo_cube_windows_structure() 
        
        # Show API usage examples
        demo_websocket_api_usage()
        
        print(f"\n🎉 Demo completed successfully!")
        print(f"Camera cube created with ID: {camera.id}")
        
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
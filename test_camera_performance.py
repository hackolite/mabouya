#!/usr/bin/env python3
"""
Test script for camera rendering performance comparison
"""

import time
import sys
import math
from server import CubeCamera, Cube, World

def create_test_world():
    """Create a test world with various blocks"""
    world = World(size=10)  # Use smaller world for testing
    
    # Add some players for testing
    world.add_player("test_player_1", (5, 2, 5), "TestPlayer1")
    world.add_player("test_player_2", (-5, 2, -5), "TestPlayer2")
    
    print(f"Test world created with {len(world.blocks)} blocks + {len(world.players)} players")
    return world

def test_camera_performance():
    """Test camera rendering performance"""
    print("🧪 Testing Camera Performance...")
    
    # Create test world
    world = create_test_world()
    
    # Create camera
    camera = CubeCamera((5, 3, 5), "TestCamera", resolution=(160, 120))  # Small resolution for testing
    
    # Determine which renderer is active
    if camera.ultra_fast_renderer:
        renderer_type = "Ultra-Fast Renderer"
    elif camera.fast_renderer:
        renderer_type = "Fast Optimized Renderer"
    elif camera.pyglet_renderer:
        renderer_type = "Pyglet Renderer"
    else:
        renderer_type = "Original Ray Tracing"
    
    print(f"📹 Using: {renderer_type}")
    
    # Warm-up render
    print("🔥 Warming up renderer...")
    camera.render_view(world, 0)
    
    # Performance test
    print("⏱️  Running performance test...")
    num_frames = 10
    start_time = time.time()
    
    for frame in range(num_frames):
        # Rotate camera slightly each frame to test different angles
        camera.rotate(5, 0)
        frame_data = camera.render_view(world, frame)
        
        if frame == 0:
            print(f"   Frame size: {len(frame_data)} bytes")
    
    end_time = time.time()
    elapsed = end_time - start_time
    fps = num_frames / elapsed
    ms_per_frame = (elapsed / num_frames) * 1000
    
    print(f"📊 Performance Results:")
    print(f"   Total time: {elapsed:.3f}s")
    print(f"   Average FPS: {fps:.1f}")
    print(f"   ms per frame: {ms_per_frame:.1f}ms")
    
    # Performance expectations
    if fps > 10:
        print("✅ Performance: EXCELLENT (>10 FPS)")
    elif fps > 5:
        print("✅ Performance: GOOD (>5 FPS)")
    elif fps > 2:
        print("⚠️  Performance: ACCEPTABLE (>2 FPS)")  
    else:
        print("❌ Performance: POOR (<2 FPS)")
    
    return fps, ms_per_frame, renderer_type

def test_different_resolutions():
    """Test performance at different resolutions"""
    print("\n🔍 Testing Different Resolutions...")
    
    world = create_test_world()
    resolutions = [(80, 60), (160, 120), (240, 180), (320, 240)]
    
    for res in resolutions:
        camera = CubeCamera((5, 3, 5), f"TestCamera_{res[0]}x{res[1]}", resolution=res)
        
        # Quick performance test
        start_time = time.time()
        for _ in range(3):
            camera.render_view(world, 0)
        elapsed = time.time() - start_time
        
        fps = 3 / elapsed
        pixels = res[0] * res[1]
        
        print(f"   {res[0]}x{res[1]} ({pixels:,} pixels): {fps:.1f} FPS")

if __name__ == "__main__":
    try:
        fps, ms_per_frame, renderer_type = test_camera_performance()
        test_different_resolutions()
        
        print(f"\n🎯 Summary:")
        print(f"   Renderer: {renderer_type}")
        print(f"   Best FPS: {fps:.1f}")
        print(f"   Frame time: {ms_per_frame:.1f}ms")
        
        # Performance comparison reference
        print(f"\n📈 Performance Comparison:")
        print(f"   Original ray tracing typically: ~0.5-2 FPS")
        print(f"   Fast renderer achieves: ~{fps:.1f} FPS")
        if fps > 2:
            improvement = fps / 1.5  # Estimate original performance at ~1.5 FPS
            print(f"   Estimated improvement: ~{improvement:.1f}x faster")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        sys.exit(1)
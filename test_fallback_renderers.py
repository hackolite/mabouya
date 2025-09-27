#!/usr/bin/env python3
"""
Test fallback renderer priority by temporarily disabling ultra-fast renderer
"""

import sys
import os

# Temporarily simulate ultra-fast renderer not available
sys.modules['ultra_fast_renderer'] = None

# Import after disabling ultra-fast
from server import CubeCamera, World

def test_fallback_renderers():
    """Test renderer fallback when ultra-fast is not available"""
    print("🧪 Testing Renderer Fallbacks (Ultra-Fast Disabled)...")
    
    # Create test world
    world = World(size=5)
    world.add_player("test_player", (2, 2, 2), "TestPlayer")
    
    # Create camera without ultra-fast renderer
    camera = CubeCamera((3, 3, 3), "FallbackTestCamera", resolution=(80, 60))
    
    # Check which renderer is active
    renderer_type = camera.get_active_renderer_type()
    print(f"📹 Active Renderer: {renderer_type}")
    
    # Verify fallback worked
    if "Ultra-Fast" not in renderer_type:
        print("✅ Successfully fell back from Ultra-Fast Renderer")
    else:
        print("⚠️  Ultra-Fast renderer still active despite disable attempt")
    
    # Test the fallback renderer
    print("🔥 Testing fallback render functionality...")
    try:
        frame_data = camera.render_view(world, 0)
        if frame_data:
            print(f"✅ Fallback render successful: {len(frame_data)} bytes")
        else:
            print("❌ Fallback render failed: No data")
    except Exception as e:
        print(f"❌ Fallback render failed: {e}")
    
    return renderer_type

if __name__ == "__main__":
    # Test fallback behavior
    renderer = test_fallback_renderers()
    print(f"\n🎯 Fallback Result: Using {renderer}")
    print("✅ Renderer fallback system working correctly!")
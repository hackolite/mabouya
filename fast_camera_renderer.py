"""
Fast Camera Renderer - Optimized Ray Tracing Alternative
========================================================

A more performance-optimized camera renderer that improves upon the original
ray tracing implementation while maintaining compatibility.
"""

import math
import numpy as np
import time

# Try to use numba for JIT compilation if available
try:
    from numba import jit, prange
    HAS_NUMBA = True
except ImportError:
    HAS_NUMBA = False
    # Provide dummy decorators when numba is not available
    def jit(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    
    def prange(*args, **kwargs):
        return range(*args, **kwargs)

class FastCameraRenderer:
    """Fast camera renderer using optimized ray tracing"""
    
    def __init__(self, resolution=(240, 180)):
        self.resolution = resolution
        self.width, self.height = resolution
        
        # Cache for world blocks as numpy arrays for faster access
        self.block_positions = None
        self.block_colors = None
        self._world_cache_hash = None
        
    def _get_block_color_rgb(self, block_type):
        """Get RGB color for block type"""
        colors = {
            "grass": [34, 139, 34],    # Green
            "stone": [128, 128, 128],  # Gray  
            "dirt": [139, 69, 19],     # Brown
            "player": [0, 150, 255],   # Blue
            "camera": [255, 255, 0],   # Yellow
            "ai_agent": [255, 0, 255], # Magenta
        }
        return colors.get(block_type, [139, 69, 19])  # Default to dirt color
    
    def update_world(self, world_blocks):
        """Update world block cache for fast rendering"""
        if not world_blocks:
            self.block_positions = np.array([]).reshape(0, 3)
            self.block_colors = np.array([]).reshape(0, 3)
            return
        
        # Convert world blocks to numpy arrays for faster processing
        positions = []
        colors = []
        
        for position, block in world_blocks.items():
            positions.append(list(position))
            colors.append(self._get_block_color_rgb(block.block_type))
        
        self.block_positions = np.array(positions, dtype=np.float32)
        self.block_colors = np.array(colors, dtype=np.uint8)
    
    def render_camera_view(self, camera_position, camera_rotation, fov=70, frame_count=0):
        """Render camera view with optimized ray tracing"""
        width, height = self.resolution
        
        # Prepare ray directions (vectorized)
        cx, cy, cz = camera_position
        yaw, pitch = camera_rotation
        
        # Pre-calculate rotation matrices
        yaw_rad = math.radians(yaw)
        pitch_rad = math.radians(pitch)
        
        cos_yaw = math.cos(yaw_rad)
        sin_yaw = math.sin(yaw_rad)
        cos_pitch = math.cos(pitch_rad)
        sin_pitch = math.sin(pitch_rad)
        
        fov_rad = math.radians(fov)
        aspect = width / height
        tan_half_fov = math.tan(fov_rad / 2)
        
        # Use optimized rendering if numba is available
        if HAS_NUMBA and self.block_positions is not None and len(self.block_positions) > 0:
            pixels = self._render_optimized(
                width, height, cx, cy, cz,
                cos_yaw, sin_yaw, cos_pitch, sin_pitch,
                tan_half_fov, aspect,
                self.block_positions, self.block_colors
            )
        else:
            # Fallback to regular Python implementation
            pixels = self._render_python(
                width, height, cx, cy, cz,
                cos_yaw, sin_yaw, cos_pitch, sin_pitch,
                tan_half_fov, aspect
            )
        
        # Add visual indicators
        self._add_visual_indicators(pixels, width, height, frame_count)
        
        return pixels.tobytes()
    
    def _render_python(self, width, height, cx, cy, cz, cos_yaw, sin_yaw, cos_pitch, sin_pitch, tan_half_fov, aspect):
        """Python fallback rendering implementation"""
        pixels = np.zeros((height, width, 3), dtype=np.uint8)
        
        for py in range(height):
            for px in range(width):
                # Calculate ray direction
                screen_x = (2.0 * px / width - 1.0) * aspect
                screen_y = 1.0 - 2.0 * py / height
                
                ray_x = screen_x * tan_half_fov
                ray_y = screen_y * tan_half_fov
                ray_z = 1.0
                
                # Apply yaw rotation
                temp_x = ray_x * cos_yaw - ray_z * sin_yaw
                temp_z = ray_x * sin_yaw + ray_z * cos_yaw
                ray_x = temp_x
                ray_z = temp_z
                
                # Apply pitch rotation
                temp_y = ray_y * cos_pitch - ray_z * sin_pitch
                temp_z = ray_y * sin_pitch + ray_z * cos_pitch
                ray_y = temp_y
                ray_z = temp_z
                
                # Normalize ray
                length = math.sqrt(ray_x**2 + ray_y**2 + ray_z**2)
                ray_x /= length
                ray_y /= length
                ray_z /= length
                
                # Simplified ray marching
                color = self._fast_ray_march(cx, cy, cz, ray_x, ray_y, ray_z)
                pixels[py, px] = color
        
        return pixels
    
    def _fast_ray_march(self, ox, oy, oz, dx, dy, dz, max_dist=20):
        """Fast ray marching with fewer iterations"""
        step = 1.5  # Larger step size for better performance
        max_iterations = int(max_dist / step)
        
        if self.block_positions is None or len(self.block_positions) == 0:
            # Sky color gradient
            if dy > 0:
                return [135, 206, 235]  # Light blue sky
            else:
                return [100, 149, 237]  # Darker blue
        
        for i in range(max_iterations):
            # Current position on ray
            x = ox + dx * i * step
            y = oy + dy * i * step
            z = oz + dz * i * step
            
            # Check collision with blocks (vectorized distance check)
            distances = np.sum((self.block_positions - [x, y, z])**2, axis=1)
            hit_idx = np.argmin(distances)
            
            if distances[hit_idx] < 1.0:  # Hit threshold
                return self.block_colors[hit_idx]
        
        # Sky color gradient if no hit
        if dy > 0:
            return [135, 206, 235]  # Light blue sky
        else:
            return [100, 149, 237]  # Darker blue
    
    @staticmethod 
    def _render_optimized(width, height, cx, cy, cz, cos_yaw, sin_yaw, cos_pitch, sin_pitch, tan_half_fov, aspect, block_positions, block_colors):
        """Numba-optimized rendering (only available if numba is installed)"""
        if HAS_NUMBA:
            return FastCameraRenderer._render_optimized_numba(width, height, cx, cy, cz, cos_yaw, sin_yaw, cos_pitch, sin_pitch, tan_half_fov, aspect, block_positions, block_colors)
        else:
            return FastCameraRenderer._render_optimized_python(width, height, cx, cy, cz, cos_yaw, sin_yaw, cos_pitch, sin_pitch, tan_half_fov, aspect, block_positions, block_colors)
    
    @staticmethod
    @jit(nopython=True, parallel=True)
    def _render_optimized_numba(width, height, cx, cy, cz, cos_yaw, sin_yaw, cos_pitch, sin_pitch, tan_half_fov, aspect, block_positions, block_colors):
        """Numba-optimized rendering"""
        pixels = np.zeros((height, width, 3), dtype=np.uint8)
        
        for py in prange(height):
            for px in range(width):
                # Calculate ray direction
                screen_x = (2.0 * px / width - 1.0) * aspect
                screen_y = 1.0 - 2.0 * py / height
                
                ray_x = screen_x * tan_half_fov
                ray_y = screen_y * tan_half_fov
                ray_z = 1.0
                
                # Apply yaw rotation
                temp_x = ray_x * cos_yaw - ray_z * sin_yaw
                temp_z = ray_x * sin_yaw + ray_z * cos_yaw
                ray_x = temp_x
                ray_z = temp_z
                
                # Apply pitch rotation
                temp_y = ray_y * cos_pitch - ray_z * sin_pitch
                temp_z = ray_y * sin_pitch + ray_z * cos_pitch
                ray_y = temp_y
                ray_z = temp_z
                
                # Normalize ray
                length = math.sqrt(ray_x**2 + ray_y**2 + ray_z**2)
                ray_x /= length
                ray_y /= length
                ray_z /= length
                
                # Fast ray marching
                step = 1.5
                max_iterations = 13  # 20/1.5 ≈ 13
                hit = False
                
                for i in range(max_iterations):
                    x = cx + ray_x * i * step
                    y = cy + ray_y * i * step
                    z = cz + ray_z * i * step
                    
                    # Check collision with blocks
                    for j in range(len(block_positions)):
                        bx, by, bz = block_positions[j]
                        dist_sq = (x - bx)**2 + (y - by)**2 + (z - bz)**2
                        if dist_sq < 1.0:
                            pixels[py, px, 0] = block_colors[j, 0]
                            pixels[py, px, 1] = block_colors[j, 1]
                            pixels[py, px, 2] = block_colors[j, 2]
                            hit = True
                            break
                    
                    if hit:
                        break
                
                if not hit:
                    # Sky color
                    if ray_y > 0:
                        pixels[py, px, 0] = 135
                        pixels[py, px, 1] = 206  
                        pixels[py, px, 2] = 235
                    else:
                        pixels[py, px, 0] = 100
                        pixels[py, px, 1] = 149
                        pixels[py, px, 2] = 237
        
        return pixels
    
    @staticmethod
    def _render_optimized_python(width, height, cx, cy, cz, cos_yaw, sin_yaw, cos_pitch, sin_pitch, tan_half_fov, aspect, block_positions, block_colors):
        """Python fallback for optimized rendering"""
        pixels = np.zeros((height, width, 3), dtype=np.uint8)
        
        for py in range(height):
            for px in range(width):
                # Calculate ray direction
                screen_x = (2.0 * px / width - 1.0) * aspect
                screen_y = 1.0 - 2.0 * py / height
                
                ray_x = screen_x * tan_half_fov
                ray_y = screen_y * tan_half_fov
                ray_z = 1.0
                
                # Apply yaw rotation
                temp_x = ray_x * cos_yaw - ray_z * sin_yaw
                temp_z = ray_x * sin_yaw + ray_z * cos_yaw
                ray_x = temp_x
                ray_z = temp_z
                
                # Apply pitch rotation
                temp_y = ray_y * cos_pitch - ray_z * sin_pitch
                temp_z = ray_y * sin_pitch + ray_z * cos_pitch
                ray_y = temp_y
                ray_z = temp_z
                
                # Normalize ray
                length = math.sqrt(ray_x**2 + ray_y**2 + ray_z**2)
                ray_x /= length
                ray_y /= length
                ray_z /= length
                
                # Fast ray marching
                step = 1.5
                max_iterations = 13  # 20/1.5 ≈ 13
                hit = False
                
                for i in range(max_iterations):
                    x = cx + ray_x * i * step
                    y = cy + ray_y * i * step
                    z = cz + ray_z * i * step
                    
                    # Check collision with blocks
                    for j in range(len(block_positions)):
                        bx, by, bz = block_positions[j]
                        dist_sq = (x - bx)**2 + (y - by)**2 + (z - bz)**2
                        if dist_sq < 1.0:
                            pixels[py, px, 0] = block_colors[j, 0]
                            pixels[py, px, 1] = block_colors[j, 1]
                            pixels[py, px, 2] = block_colors[j, 2]
                            hit = True
                            break
                    
                    if hit:
                        break
                
                if not hit:
                    # Sky color
                    if ray_y > 0:
                        pixels[py, px, 0] = 135
                        pixels[py, px, 1] = 206  
                        pixels[py, px, 2] = 235
                    else:
                        pixels[py, px, 0] = 100
                        pixels[py, px, 1] = 149
                        pixels[py, px, 2] = 237
        
        return pixels
    
    def _add_visual_indicators(self, pixels, width, height, frame_count):
        """Add LED indicator and frame counter to rendered image"""
        for py in range(height):
            for px in range(width):
                # LED indicator in top-right corner
                if px >= width - 10 and py <= 8:
                    led_on = (frame_count // 3) % 2 == 0
                    if px >= width - 8 and py <= 6:
                        if led_on:
                            pixels[py, px] = [0, 255, 0]  # Green
                        else:
                            pixels[py, px] = [0, 120, 0]  # Dark green
                    elif px >= width - 10 and py <= 8:
                        if led_on:
                            pixels[py, px] = [0, 200, 0]  # Medium green
                        else:
                            pixels[py, px] = [0, 80, 0]   # Very dark green
                
                # Frame counter in bottom-right corner
                if px >= width - 15 and py >= height - 10:
                    digit = frame_count % 10
                    rel_x = px - (width - 15)
                    rel_y = py - (height - 10)
                    
                    digit_patterns = {
                        0: [[1,1,1,1,1], [1,0,0,0,1], [1,0,0,0,1], [1,0,0,0,1], [1,0,0,0,1], [1,0,0,0,1], [1,0,0,0,1], [1,1,1,1,1]],
                        1: [[0,0,1,0,0], [0,1,1,0,0], [0,0,1,0,0], [0,0,1,0,0], [0,0,1,0,0], [0,0,1,0,0], [0,0,1,0,0], [1,1,1,1,1]],
                        2: [[1,1,1,1,1], [0,0,0,0,1], [0,0,0,0,1], [1,1,1,1,1], [1,0,0,0,0], [1,0,0,0,0], [1,0,0,0,0], [1,1,1,1,1]],
                        3: [[1,1,1,1,1], [0,0,0,0,1], [0,0,0,0,1], [1,1,1,1,1], [0,0,0,0,1], [0,0,0,0,1], [0,0,0,0,1], [1,1,1,1,1]],
                        4: [[1,0,0,0,1], [1,0,0,0,1], [1,0,0,0,1], [1,1,1,1,1], [0,0,0,0,1], [0,0,0,0,1], [0,0,0,0,1], [0,0,0,0,1]],
                        5: [[1,1,1,1,1], [1,0,0,0,0], [1,0,0,0,0], [1,1,1,1,1], [0,0,0,0,1], [0,0,0,0,1], [0,0,0,0,1], [1,1,1,1,1]],
                        6: [[1,1,1,1,1], [1,0,0,0,0], [1,0,0,0,0], [1,1,1,1,1], [1,0,0,0,1], [1,0,0,0,1], [1,0,0,0,1], [1,1,1,1,1]],
                        7: [[1,1,1,1,1], [0,0,0,0,1], [0,0,0,0,1], [0,0,0,0,1], [0,0,0,0,1], [0,0,0,0,1], [0,0,0,0,1], [0,0,0,0,1]],
                        8: [[1,1,1,1,1], [1,0,0,0,1], [1,0,0,0,1], [1,1,1,1,1], [1,0,0,0,1], [1,0,0,0,1], [1,0,0,0,1], [1,1,1,1,1]],
                        9: [[1,1,1,1,1], [1,0,0,0,1], [1,0,0,0,1], [1,1,1,1,1], [0,0,0,0,1], [0,0,0,0,1], [0,0,0,0,1], [1,1,1,1,1]]
                    }
                    
                    if rel_x < 5 and rel_y < 8 and digit in digit_patterns:
                        if digit_patterns[digit][rel_y][rel_x]:
                            pixels[py, px] = [255, 255, 0]  # Yellow counter
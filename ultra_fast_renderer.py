"""
Ultra Fast Camera Renderer
==========================

A minimal, ultra-fast camera renderer that prioritizes speed over visual fidelity.
Uses depth buffer approximation and simplified rendering for real-time performance.
"""

import math
import numpy as np

class UltraFastRenderer:
    """Ultra-fast camera renderer optimized for maximum performance"""
    
    def __init__(self, resolution=(240, 180)):
        self.resolution = resolution
        self.width, self.height = resolution
        
        # Pre-allocate pixel buffer
        self.pixel_buffer = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        # Simple block lookup for nearest blocks only
        self.nearby_blocks = []
        self.sky_color = np.array([135, 206, 235], dtype=np.uint8)
        self.ground_color = np.array([34, 139, 34], dtype=np.uint8)  # Green ground
        
    def update_world(self, world_blocks, camera_position=(0, 0, 0)):
        """Update world with only the nearest blocks for ultra-fast rendering"""
        if not world_blocks:
            self.nearby_blocks = []
            return
        
        cx, cy, cz = camera_position
        
        # Keep only the closest blocks (max 20 for real-time performance)
        block_distances = []
        for position, block in world_blocks.items():
            x, y, z = position
            dist_sq = (x - cx)**2 + (y - cy)**2 + (z - cz)**2
            if dist_sq < 400:  # Only blocks within 20 units
                block_distances.append((dist_sq, position, block))
        
        # Sort by distance and keep only the closest ones
        block_distances.sort()
        self.nearby_blocks = block_distances[:20]  # Max 20 blocks
        
        print(f"UltraFastRenderer: Using {len(self.nearby_blocks)} blocks")
    
    def render_camera_view(self, camera_position, camera_rotation, fov=70, frame_count=0):
        """Ultra-fast camera rendering with improved precision and robustness"""
        cx, cy, cz = camera_position
        yaw, pitch = camera_rotation
        
        # Clear buffer with sky color
        self.pixel_buffer[:] = self.sky_color
        
        # Improved horizon calculation with proper pitch mapping
        # Pitch ranges from -90 (looking up) to +90 (looking down)
        pitch_normalized = max(-90, min(90, pitch))  # Clamp pitch
        horizon_y = int(self.height * (0.5 + pitch_normalized / 180.0))
        horizon_y = max(0, min(self.height - 1, horizon_y))
        
        # Ground color below horizon
        if horizon_y < self.height:
            self.pixel_buffer[horizon_y:, :] = self.ground_color
        
        # Precise trigonometric calculations
        yaw_rad = math.radians(yaw)
        pitch_rad = math.radians(pitch_normalized)
        cos_yaw = math.cos(yaw_rad)
        sin_yaw = math.sin(yaw_rad)
        cos_pitch = math.cos(pitch_rad)
        sin_pitch = math.sin(pitch_rad)
        
        # FOV calculations for proper perspective
        fov_rad = math.radians(fov)
        tan_half_fov = math.tan(fov_rad / 2)
        aspect_ratio = self.width / self.height
        
        # Sort blocks by distance for proper depth ordering
        visible_blocks = []
        for dist_sq, position, block in self.nearby_blocks:
            bx, by, bz = position
            
            # Transform block position relative to camera
            rel_x = bx - cx
            rel_y = by - cy  
            rel_z = bz - cz
            
            # Apply camera rotation transformations
            # First rotate around Y-axis (yaw)
            rot_x = rel_x * cos_yaw - rel_z * sin_yaw
            rot_z = rel_x * sin_yaw + rel_z * cos_yaw
            
            # Then rotate around X-axis (pitch) 
            rot_y = rel_y * cos_pitch + rot_z * sin_pitch
            final_z = -rel_y * sin_pitch + rot_z * cos_pitch
            
            # Skip blocks behind camera (with small epsilon for precision)
            if final_z <= 0.1:
                continue
            
            # Precise perspective projection with proper FOV
            screen_x = (rot_x / final_z) / (tan_half_fov * aspect_ratio)
            screen_y = -(rot_y / final_z) / tan_half_fov
            
            # Convert to pixel coordinates
            pixel_x = int((screen_x + 1) * 0.5 * self.width)
            pixel_y = int((screen_y + 1) * 0.5 * self.height)
            
            # Skip blocks outside screen bounds
            if pixel_x < -50 or pixel_x >= self.width + 50 or pixel_y < -50 or pixel_y >= self.height + 50:
                continue
                
            # Calculate precise block size based on distance and FOV
            distance = math.sqrt(final_z * final_z + rot_x * rot_x + rot_y * rot_y)
            block_size = max(1, int((self.width * 0.05) / distance))  # More precise size calculation
            
            visible_blocks.append((distance, pixel_x, pixel_y, block_size, block))
        
        # Sort by distance (far to near) for proper rendering order
        visible_blocks.sort(reverse=True)
        
        # Render visible blocks with improved precision
        for distance, screen_x, screen_y, block_size, block in visible_blocks:
            color = self._get_block_color(block.block_type)
            
            # Render block as filled rectangle with anti-aliasing consideration
            half_size = block_size // 2
            for dy in range(-half_size, half_size + 1):
                for dx in range(-half_size, half_size + 1):
                    px = screen_x + dx
                    py = screen_y + dy
                    
                    if 0 <= px < self.width and 0 <= py < self.height:
                        # Add subtle depth-based shading for better visual quality
                        depth_factor = max(0.3, min(1.0, 20.0 / distance))
                        shaded_color = (color * depth_factor).astype(np.uint8)
                        self.pixel_buffer[py, px] = shaded_color
        
        # Add visual indicators
        self._add_visual_indicators(frame_count)
        
        return self.pixel_buffer.tobytes()
    
    def _get_block_color(self, block_type):
        """Get RGB color for block type"""
        colors = {
            "grass": [34, 139, 34],    # Green
            "stone": [128, 128, 128],  # Gray  
            "dirt": [139, 69, 19],     # Brown
            "player": [0, 150, 255],   # Blue
            "camera": [255, 255, 0],   # Yellow
            "ai_agent": [255, 0, 255], # Magenta
        }
        return np.array(colors.get(block_type, [139, 69, 19]), dtype=np.uint8)
    
    def _add_visual_indicators(self, frame_count):
        """Add LED indicator and frame counter"""
        width, height = self.width, self.height
        
        # LED indicator in top-right corner
        led_on = (frame_count // 3) % 2 == 0
        led_color = [0, 255, 0] if led_on else [0, 120, 0]
        
        for py in range(min(8, height)):
            for px in range(max(0, width - 10), width):
                if px >= width - 8 and py <= 6:
                    self.pixel_buffer[py, px] = led_color
        
        # Simple frame counter digit in bottom-right
        digit = frame_count % 10
        digit_pattern = self._get_digit_pattern(digit)
        
        start_y = max(0, height - 8)
        start_x = max(0, width - 6)
        
        for dy in range(min(8, height - start_y)):
            for dx in range(min(5, width - start_x)):
                if dy < len(digit_pattern) and dx < len(digit_pattern[dy]):
                    if digit_pattern[dy][dx]:
                        self.pixel_buffer[start_y + dy, start_x + dx] = [255, 255, 0]  # Yellow
    
    def _get_digit_pattern(self, digit):
        """Get 5x8 pattern for digit display"""
        patterns = {
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
        return patterns.get(digit, patterns[0])
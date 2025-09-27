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
        
        # Pre-allocate depth buffer for proper depth testing like pyglet
        self.depth_buffer = np.full((self.height, self.width), np.inf, dtype=np.float32)
        
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
        """Ultra-fast camera rendering with improved precision matching pyglet representation"""
        cx, cy, cz = camera_position
        yaw, pitch = camera_rotation
        
        # Clear buffers
        self.pixel_buffer[:] = self.sky_color
        self.depth_buffer[:] = np.inf
        
        # Improved horizon calculation with proper pitch mapping
        pitch_normalized = max(-90, min(90, pitch))  # Clamp pitch
        horizon_y = int(self.height * (0.5 + pitch_normalized / 180.0))
        horizon_y = max(0, min(self.height - 1, horizon_y))
        
        # Ground color below horizon
        if horizon_y < self.height:
            self.pixel_buffer[horizon_y:, :] = self.ground_color
            # Set ground depth to far distance
            self.depth_buffer[horizon_y:, :] = 1000.0
        
        # Calculate view direction for face culling
        yaw_rad = math.radians(yaw)
        pitch_rad = math.radians(pitch_normalized)
        view_dir = (
            math.cos(pitch_rad) * math.sin(yaw_rad),
            -math.sin(pitch_rad),
            math.cos(pitch_rad) * math.cos(yaw_rad)
        )
        
        # Perspective projection parameters matching pyglet
        aspect_ratio = self.width / self.height
        
        # Render blocks as proper 3D cubes like pyglet
        for dist_sq, position, block in self.nearby_blocks:
            bx, by, bz = position
            base_color = self._get_block_color(block.block_type)
            
            # Get cube faces
            cube_faces = self._get_cube_faces(bx, by, bz)
            
            # Render each visible face
            for face_name, face_data in cube_faces.items():
                # Check if face is visible (back-face culling)
                if not self._is_face_visible(face_data['normal'], view_dir):
                    continue
                
                # Project face vertices
                projected_vertices = []
                depth_values = []
                
                for vertex in face_data['vertices']:
                    projection = self._project_point_perspective(
                        vertex, camera_position, camera_rotation, fov, aspect_ratio
                    )
                    if projection is None:  # Behind camera
                        break
                    projected_vertices.append(projection[:2])  # x, y
                    depth_values.append(projection[2])  # depth
                
                # Only render if all vertices are in front of camera
                if len(projected_vertices) == 4:
                    # Apply face-specific shading
                    shade_factor = min(1.2, max(0.3, face_data['shade_factor']))
                    shaded_color = (base_color * shade_factor).astype(np.uint8)
                    shaded_color = np.clip(shaded_color, 0, 255)
                    
                    # Rasterize the face
                    self._rasterize_face(projected_vertices, shaded_color, depth_values)
        
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
    
    def _get_cube_faces(self, x, y, z, size=1.0):
        """Generate cube faces like pyglet renderer for precise 3D representation"""
        s = size / 2.0
        faces = {
            # Each face defined as 4 vertices (corners) + face normal + face type
            'front': {
                'vertices': [(x-s, y-s, z+s), (x+s, y-s, z+s), (x+s, y+s, z+s), (x-s, y+s, z+s)],
                'normal': (0, 0, 1),
                'shade_factor': 1.0  # Full brightness for front face
            },
            'back': {
                'vertices': [(x+s, y-s, z-s), (x-s, y-s, z-s), (x-s, y+s, z-s), (x+s, y+s, z-s)],
                'normal': (0, 0, -1),
                'shade_factor': 0.6  # Darker for back face
            },
            'left': {
                'vertices': [(x-s, y-s, z-s), (x-s, y-s, z+s), (x-s, y+s, z+s), (x-s, y+s, z-s)],
                'normal': (-1, 0, 0),
                'shade_factor': 0.8  # Medium shade for left face
            },
            'right': {
                'vertices': [(x+s, y-s, z+s), (x+s, y-s, z-s), (x+s, y+s, z-s), (x+s, y+s, z+s)],
                'normal': (1, 0, 0),
                'shade_factor': 0.8  # Medium shade for right face
            },
            'top': {
                'vertices': [(x-s, y+s, z+s), (x+s, y+s, z+s), (x+s, y+s, z-s), (x-s, y+s, z-s)],
                'normal': (0, 1, 0),
                'shade_factor': 1.2  # Brighter for top face (like lighting from above)
            },
            'bottom': {
                'vertices': [(x-s, y-s, z-s), (x+s, y-s, z-s), (x+s, y-s, z+s), (x-s, y-s, z+s)],
                'normal': (0, -1, 0),
                'shade_factor': 0.4  # Darkest for bottom face
            }
        }
        return faces
    
    def _project_point_perspective(self, point, camera_pos, camera_rot, fov, aspect):
        """Project 3D point using perspective projection like pyglet's gluPerspective"""
        cx, cy, cz = camera_pos
        yaw, pitch = camera_rot
        px, py, pz = point
        
        # Transform point relative to camera
        rel_x = px - cx
        rel_y = py - cy
        rel_z = pz - cz
        
        # Apply camera rotation transformations (same as original)
        yaw_rad = math.radians(yaw)
        pitch_rad = math.radians(pitch)
        cos_yaw = math.cos(yaw_rad)
        sin_yaw = math.sin(yaw_rad)
        cos_pitch = math.cos(pitch_rad)
        sin_pitch = math.sin(pitch_rad)
        
        # First rotate around Y-axis (yaw)
        rot_x = rel_x * cos_yaw - rel_z * sin_yaw
        rot_z = rel_x * sin_yaw + rel_z * cos_yaw
        
        # Then rotate around X-axis (pitch) 
        rot_y = rel_y * cos_pitch + rot_z * sin_pitch
        final_z = -rel_y * sin_pitch + rot_z * cos_pitch
        
        # Skip points behind camera
        if final_z <= 0.1:
            return None
            
        # Apply perspective projection matching gluPerspective
        fov_rad = math.radians(fov)
        f = 1.0 / math.tan(fov_rad / 2.0)  # Focal length
        
        # Normalized device coordinates
        ndc_x = (f / aspect) * (rot_x / final_z)
        ndc_y = f * (rot_y / final_z)
        
        # Convert to screen coordinates
        screen_x = int((ndc_x + 1.0) * 0.5 * self.width)
        screen_y = int((1.0 - ndc_y) * 0.5 * self.height)  # Flip Y for screen coords
        
        return (screen_x, screen_y, final_z)
    
    def _is_face_visible(self, face_normal, view_direction):
        """Check if face is visible based on face normal and view direction (back-face culling)"""
        # Calculate dot product to determine if face is facing camera
        dot_product = (face_normal[0] * view_direction[0] + 
                      face_normal[1] * view_direction[1] + 
                      face_normal[2] * view_direction[2])
        return dot_product < 0  # Face is visible if normal points toward camera
    
    def _rasterize_face(self, projected_vertices, color, depth_values):
        """Rasterize a face (quad) with proper depth testing and better shape accuracy"""
        if len(projected_vertices) != 4:
            return
        
        # Get bounding box of the face
        min_x = max(0, min(v[0] for v in projected_vertices))
        max_x = min(self.width - 1, max(v[0] for v in projected_vertices))
        min_y = max(0, min(v[1] for v in projected_vertices))
        max_y = min(self.height - 1, max(v[1] for v in projected_vertices))
        
        if min_x >= max_x or min_y >= max_y:
            return
        
        # Use average depth for the face
        avg_depth = sum(depth_values) / len(depth_values)
        
        # Better quad rasterization: check if point is inside the quad using barycentric coordinates
        # For speed, we'll use a simpler approach: rasterize based on the quad's shape
        v0, v1, v2, v3 = projected_vertices
        
        # Create a more accurate representation by interpolating between vertices
        for y in range(min_y, max_y + 1):
            for x in range(min_x, max_x + 1):
                # Simple point-in-quad test: check if point is inside using cross products
                if self._point_in_quad(x, y, projected_vertices):
                    # Depth test
                    if avg_depth < self.depth_buffer[y, x]:
                        self.depth_buffer[y, x] = avg_depth
                        self.pixel_buffer[y, x] = color
    
    def _point_in_quad(self, px, py, quad_vertices):
        """Check if point (px, py) is inside the quad defined by 4 vertices"""
        # Simple but effective method: count edge crossings
        v0, v1, v2, v3 = quad_vertices
        vertices = [v0, v1, v2, v3, v0]  # Close the polygon
        
        inside = False
        j = 0
        for i in range(1, len(vertices)):
            xi, yi = vertices[i]
            xj, yj = vertices[j]
            
            if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
                inside = not inside
            j = i
        
        return inside
    
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
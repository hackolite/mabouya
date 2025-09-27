"""
Pyglet-based Camera Renderer
============================

High-performance camera rendering using Pyglet OpenGL instead of ray tracing.
Renders camera views to offscreen framebuffers for streaming.
"""

import os
import pyglet
from pyglet.gl import *
import math
import numpy as np

# Set headless mode for Pyglet if needed
if not os.environ.get('DISPLAY'):  
    os.environ['PYGLET_HEADLESS'] = '1'

class PygletCameraRenderer:
    """Renders camera views using Pyglet OpenGL offscreen rendering"""
    
    def __init__(self, resolution=(240, 180)):
        self.resolution = resolution
        self.width, self.height = resolution
        
        try:
            # Create display and window 
            self.display = pyglet.canvas.Display()
            self.screen = self.display.get_default_screen()
            
            # Create minimal config for offscreen rendering
            config = pyglet.gl.Config(double_buffer=False, depth_size=24)
            self.context = self.screen.get_best_config(config).create_context(None)
            
            # Create framebuffer for offscreen rendering
            self.framebuffer = None
            self.color_texture = None
            self.depth_buffer = None
            
            # Rendering batches for different block types
            self.world_batch = pyglet.graphics.Batch()
            self.world_vertices = {}
            
            self._setup_framebuffer()
            self._setup_opengl()
            
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Pyglet renderer: {e}")
    
    def _setup_framebuffer(self):
        """Setup offscreen framebuffer for rendering"""
        self.context.set_current()
        
        # Create framebuffer
        self.framebuffer = GLuint()
        glGenFramebuffers(1, self.framebuffer)
        glBindFramebuffer(GL_FRAMEBUFFER, self.framebuffer)
        
        # Create color texture
        self.color_texture = GLuint()
        glGenTextures(1, self.color_texture)
        glBindTexture(GL_TEXTURE_2D, self.color_texture)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, self.width, self.height, 0, GL_RGB, GL_UNSIGNED_BYTE, None)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, self.color_texture, 0)
        
        # Create depth buffer
        self.depth_buffer = GLuint()
        glGenRenderbuffers(1, self.depth_buffer)
        glBindRenderbuffer(GL_RENDERBUFFER, self.depth_buffer)
        glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH_COMPONENT, self.width, self.height)
        glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_RENDERBUFFER, self.depth_buffer)
        
        # Check framebuffer status
        status = glCheckFramebufferStatus(GL_FRAMEBUFFER)
        if status != GL_FRAMEBUFFER_COMPLETE:
            raise RuntimeError(f"Framebuffer not complete: {status}")
        
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
    
    def _setup_opengl(self):
        """Setup OpenGL state for rendering"""
        self.context.set_current()
        glClearColor(0.5, 0.69, 1.0, 1.0)  # Sky blue background
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_CULL_FACE)
        glCullFace(GL_BACK)
    
    def _cube_vertices(self, x, y, z, size=1.0):
        """Generate vertices for a cube at position (x,y,z)"""
        s = size / 2.0
        vertices = [
            # Front face
            x-s, y-s, z+s,  x+s, y-s, z+s,  x+s, y+s, z+s,  x-s, y+s, z+s,
            # Back face  
            x+s, y-s, z-s,  x-s, y-s, z-s,  x-s, y+s, z-s,  x+s, y+s, z-s,
            # Left face
            x-s, y-s, z-s,  x-s, y-s, z+s,  x-s, y+s, z+s,  x-s, y+s, z-s,
            # Right face
            x+s, y-s, z+s,  x+s, y-s, z-s,  x+s, y+s, z-s,  x+s, y+s, z+s,
            # Top face
            x-s, y+s, z+s,  x+s, y+s, z+s,  x+s, y+s, z-s,  x-s, y+s, z-s,
            # Bottom face
            x-s, y-s, z-s,  x+s, y-s, z-s,  x+s, y-s, z+s,  x-s, y-s, z+s,
        ]
        return vertices
    
    def _get_block_color(self, block_type):
        """Get RGB color for block type"""
        colors = {
            "grass": (34, 139, 34),    # Green
            "stone": (128, 128, 128),  # Gray  
            "dirt": (139, 69, 19),     # Brown
            "player": (0, 150, 255),   # Blue
            "camera": (255, 255, 0),   # Yellow
            "ai_agent": (255, 0, 255), # Magenta
        }
        return colors.get(block_type, (139, 69, 19))  # Default to dirt color
    
    def update_world(self, world_blocks):
        """Update the world geometry for rendering"""
        self.context.set_current()
        
        # Clear existing geometry
        self.world_batch = pyglet.graphics.Batch()
        self.world_vertices = {}
        
        # Add blocks to batch
        for position, block in world_blocks.items():
            x, y, z = position
            vertices = self._cube_vertices(x, y, z)
            color = self._get_block_color(block.block_type)
            
            # Create color array (RGB for each vertex)
            block_color = color * 24  # 24 vertices per cube (6 faces * 4 vertices)
            
            # Add to batch
            vertex_list = self.world_batch.add(
                24, GL_QUADS, None,
                ('v3f', vertices),
                ('c3B', block_color)
            )
            self.world_vertices[position] = vertex_list
    
    def render_camera_view(self, camera_position, camera_rotation, fov=70):
        """Render camera view and return RGB pixel data"""
        self.context.set_current()
        
        # Bind framebuffer for offscreen rendering
        glBindFramebuffer(GL_FRAMEBUFFER, self.framebuffer)
        glViewport(0, 0, self.width, self.height)
        
        # Clear
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        
        # Setup camera matrix
        self._setup_camera_matrix(camera_position, camera_rotation, fov)
        
        # Render world
        glColor3f(1.0, 1.0, 1.0)  # Reset color
        self.world_batch.draw()
        
        # Read pixels from framebuffer
        pixels = (GLubyte * (self.width * self.height * 3))()
        glReadPixels(0, 0, self.width, self.height, GL_RGB, GL_UNSIGNED_BYTE, pixels)
        
        # Convert to bytes and flip vertically (OpenGL has origin at bottom-left)
        pixel_array = np.frombuffer(pixels, dtype=np.uint8)
        pixel_array = pixel_array.reshape((self.height, self.width, 3))
        pixel_array = np.flipud(pixel_array)  # Flip vertically
        
        # Unbind framebuffer
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        
        return pixel_array.tobytes()
    
    def _setup_camera_matrix(self, position, rotation, fov):
        """Setup camera projection and view matrices"""
        cx, cy, cz = position
        yaw, pitch = rotation
        
        # Setup projection matrix
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        aspect = self.width / float(self.height)
        gluPerspective(fov, aspect, 0.1, 60.0)
        
        # Setup view matrix  
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        
        # Apply camera rotation and position
        glRotatef(-pitch, 1, 0, 0)  # Pitch (look up/down)
        glRotatef(-yaw, 0, 1, 0)    # Yaw (look left/right)
        glTranslatef(-cx, -cy, -cz) # Move world opposite to camera
    
    def cleanup(self):
        """Cleanup OpenGL resources"""
        if self.context:
            self.context.set_current()
            
            if self.framebuffer:
                glDeleteFramebuffers(1, self.framebuffer)
            if self.color_texture:
                glDeleteTextures(1, self.color_texture)
            if self.depth_buffer:
                glDeleteRenderbuffers(1, self.depth_buffer)
"""
Cube Windows Abstraction
=======================

Provides window functionality for cubes, particularly camera cubes.
Each cube can have an associated window for visualization and interaction.
"""

import os
import threading
import time
from abc import ABC, abstractmethod

# Set headless mode for Pyglet if no display available
if not os.environ.get('DISPLAY'):  
    # Allow override for testing
    if not os.environ.get('PYGLET_FORCE_WINDOWED'):
        os.environ['PYGLET_HEADLESS'] = '1'

# Try to import Pyglet - handle gracefully if not available
try:
    import pyglet
    from pyglet.gl import *
    PYGLET_AVAILABLE = True
except ImportError as e:
    PYGLET_AVAILABLE = False
    print(f"⚠️ Pyglet not available for cube windows: {e}")
except Exception as e:
    PYGLET_AVAILABLE = False
    print(f"⚠️ Pyglet initialization failed for cube windows: {e}")

class CubeWindow(ABC):
    """Abstract base class for cube window functionality"""
    
    def __init__(self, cube_id, title="Cube Window"):
        self.cube_id = cube_id
        self.title = title
        self.is_active = False
        self.window = None
        
    @abstractmethod
    def create_window(self):
        """Create and initialize the window"""
        pass
        
    @abstractmethod
    def update_view(self, *args, **kwargs):
        """Update the window view with new data"""
        pass
        
    @abstractmethod
    def capture_frame(self):
        """Capture current frame as image data"""
        pass
        
    def activate(self):
        """Activate the window"""
        if not self.is_active:
            self.create_window()
            self.is_active = True
            
    def deactivate(self):
        """Deactivate and close the window"""
        if self.is_active and self.window:
            self.window.close()
            self.window = None
            self.is_active = False


class PygletCameraWindow(CubeWindow):
    """Pyglet window implementation for camera cubes"""
    
    def __init__(self, cube_id, camera_cube, title=None):
        if not PYGLET_AVAILABLE:
            raise RuntimeError("Pyglet not available for camera windows")
            
        if title is None:
            title = f"Camera View - {camera_cube.name}"
        super().__init__(cube_id, title)
        self.camera_cube = camera_cube
        self.resolution = camera_cube.resolution
        self.width, self.height = self.resolution
        self.world_data = {}  # Cache for world data
        self.frame_buffer = None
        self.color_texture = None
        self.window_thread = None
        self.should_run = False
        
    def create_window(self):
        """Create the Pyglet window in a separate thread"""
        if self.window is not None:
            return
            
        self.should_run = True
        self.window_thread = threading.Thread(target=self._run_window, daemon=True)
        self.window_thread.start()
        
        # Wait a bit for window to initialize
        time.sleep(0.1)
        
    def _run_window(self):
        """Run the Pyglet window in a separate thread"""
        try:
            # Create window
            self.window = pyglet.window.Window(
                width=self.width, 
                height=self.height, 
                caption=self.title,
                resizable=True
            )
            
            # Set up OpenGL
            self._setup_opengl()
            
            # Set up event handlers
            @self.window.event
            def on_draw():
                self._render_camera_view()
                
            @self.window.event
            def on_close():
                self.should_run = False
                self.is_active = False
                
            # Run the event loop
            while self.should_run and not self.window.has_exit:
                pyglet.clock.tick()
                self.window.switch_to()
                self.window.dispatch_events()
                self.window.dispatch_event('on_draw')
                self.window.flip()
                time.sleep(1/60)  # 60 FPS
                
        except Exception as e:
            print(f"Error in camera window {self.cube_id}: {e}")
        finally:
            if self.window:
                self.window.close()
                
    def _setup_opengl(self):
        """Setup OpenGL state for 3D rendering"""
        glEnable(GL_DEPTH_TEST)
        glDepthFunc(GL_LEQUAL)
        glEnable(GL_CULL_FACE)
        glCullFace(GL_BACK)
        glClearColor(0.5, 0.8, 1.0, 1.0)  # Sky blue background
        
        # Setup projection
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        aspect_ratio = self.width / self.height
        gluPerspective(self.camera_cube.fov, aspect_ratio, 0.1, 100.0)
        
    def _render_camera_view(self):
        """Render the camera's view of the world"""
        if not self.window:
            return
            
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        
        # Setup camera matrix
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        
        # Apply camera rotation and position
        yaw, pitch = self.camera_cube.rotation
        glRotatef(-pitch, 1, 0, 0)
        glRotatef(-yaw, 0, 1, 0)
        
        x, y, z = self.camera_cube.position
        glTranslatef(-x, -y, -z)
        
        # Render world blocks (simplified visualization)
        self._render_world_blocks()
        
        # Add camera info overlay
        self._render_overlay()
        
    def _render_world_blocks(self):
        """Render world blocks as simple cubes"""
        # This is a simplified version - in a real implementation,
        # you would get the world data and render all blocks
        
        # For now, just render a few sample blocks to show it works
        sample_blocks = [
            ((0, 0, 0), (0.2, 0.8, 0.2)),  # Green grass
            ((1, 0, 0), (0.5, 0.5, 0.5)),  # Gray stone  
            ((0, 0, 1), (0.2, 0.8, 0.2)),  # Green grass
            ((-1, 0, 0), (0.8, 0.6, 0.4)), # Brown dirt
        ]
        
        for (bx, by, bz), color in sample_blocks:
            self._render_cube(bx, by, bz, color)
            
    def _render_cube(self, x, y, z, color):
        """Render a single cube at the given position with the given color"""
        r, g, b = color
        glColor3f(r, g, b)
        
        glPushMatrix()
        glTranslatef(x, y, z)
        
        # Render cube faces
        glBegin(GL_QUADS)
        
        # Front face
        glNormal3f(0, 0, 1)
        glVertex3f(-0.5, -0.5, 0.5)
        glVertex3f(0.5, -0.5, 0.5)
        glVertex3f(0.5, 0.5, 0.5)
        glVertex3f(-0.5, 0.5, 0.5)
        
        # Back face
        glNormal3f(0, 0, -1)
        glVertex3f(-0.5, -0.5, -0.5)
        glVertex3f(-0.5, 0.5, -0.5)
        glVertex3f(0.5, 0.5, -0.5)
        glVertex3f(0.5, -0.5, -0.5)
        
        # Top face
        glNormal3f(0, 1, 0)
        glVertex3f(-0.5, 0.5, -0.5)
        glVertex3f(-0.5, 0.5, 0.5)
        glVertex3f(0.5, 0.5, 0.5)
        glVertex3f(0.5, 0.5, -0.5)
        
        # Bottom face
        glNormal3f(0, -1, 0)
        glVertex3f(-0.5, -0.5, -0.5)
        glVertex3f(0.5, -0.5, -0.5)
        glVertex3f(0.5, -0.5, 0.5)
        glVertex3f(-0.5, -0.5, 0.5)
        
        # Right face
        glNormal3f(1, 0, 0)
        glVertex3f(0.5, -0.5, -0.5)
        glVertex3f(0.5, 0.5, -0.5)
        glVertex3f(0.5, 0.5, 0.5)
        glVertex3f(0.5, -0.5, 0.5)
        
        # Left face
        glNormal3f(-1, 0, 0)
        glVertex3f(-0.5, -0.5, -0.5)
        glVertex3f(-0.5, -0.5, 0.5)
        glVertex3f(-0.5, 0.5, 0.5)
        glVertex3f(-0.5, 0.5, -0.5)
        
        glEnd()
        glPopMatrix()
        
    def _render_overlay(self):
        """Render camera information overlay"""
        if not self.window:
            return
            
        # Switch to 2D rendering for overlay
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        glOrtho(0, self.width, 0, self.height, -1, 1)
        
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()
        
        # Disable depth testing for overlay
        glDisable(GL_DEPTH_TEST)
        
        # Draw simple text info (positions)
        x, y, z = self.camera_cube.position
        yaw, pitch = self.camera_cube.rotation
        
        # Draw colored indicators (simple rectangles as visual indicators)
        glColor3f(1.0, 0.0, 0.0)  # Red indicator
        glBegin(GL_QUADS)
        glVertex2f(10, self.height - 20)
        glVertex2f(30, self.height - 20)
        glVertex2f(30, self.height - 10)
        glVertex2f(10, self.height - 10)
        glEnd()
        
        # Green indicator for active state
        glColor3f(0.0, 1.0, 0.0)  # Green indicator
        glBegin(GL_QUADS)
        glVertex2f(35, self.height - 20)
        glVertex2f(55, self.height - 20)
        glVertex2f(55, self.height - 10)
        glVertex2f(35, self.height - 10)
        glEnd()
        
        # Restore 3D rendering state
        glEnable(GL_DEPTH_TEST)
        glPopMatrix()
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
        
    def update_view(self, world_data=None):
        """Update the camera view with new world data"""
        if world_data:
            self.world_data = world_data
            
    def capture_frame(self):
        """Capture current frame as RGB image data"""
        if not self.window or not self.is_active:
            return None
            
        try:
            # Switch to window context
            self.window.switch_to()
            
            # Read pixels from framebuffer
            buffer = (GLubyte * (3 * self.width * self.height))()
            glReadPixels(0, 0, self.width, self.height, GL_RGB, GL_UNSIGNED_BYTE, buffer)
            
            # Convert to bytes and flip vertically (OpenGL is bottom-up)
            pixel_data = bytes(buffer)
            flipped_data = bytearray()
            
            for row in range(self.height - 1, -1, -1):
                start = row * self.width * 3
                end = start + self.width * 3
                flipped_data.extend(pixel_data[start:end])
                
            return bytes(flipped_data)
            
        except Exception as e:
            print(f"Error capturing frame from camera {self.cube_id}: {e}")
            return None
            
    def deactivate(self):
        """Deactivate and close the window"""
        self.should_run = False
        if self.window_thread and self.window_thread.is_alive():
            self.window_thread.join(timeout=1.0)
        super().deactivate()
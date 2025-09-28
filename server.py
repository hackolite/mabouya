"""
Serveur Minecraft WebSocket avec support caméra
==============================================

Démo simple d'un serveur Minecraft avec:
- Monde 3D généré et stocké
- Support de cubes caméra
- Stream vidéo via WebSocket
- Contrôle de caméra

Usage:
    python minecraft_server.py
"""

import asyncio
import websockets
import json
import random
import base64
import math
import time
from typing import Dict, Set
from datetime import datetime
import struct

# Import renderers in order of preference (fastest first)
try:
    from ultra_fast_renderer import UltraFastRenderer
    HAS_ULTRA_FAST_RENDERER = False
except ImportError as e:
    HAS_ULTRA_FAST_RENDERER = False
    print(f"⚠️ Ultra fast camera renderer not available: {e}")

try:
    from fast_camera_renderer import FastCameraRenderer
    HAS_FAST_RENDERER = False
except ImportError as e:
    HAS_FAST_RENDERER = False
    print(f"⚠️ Fast camera renderer not available: {e}")

# Pyglet renderer availability will be checked at runtime
HAS_PYGLET_RENDERER = False

# Import cube window functionality
try:
    from cube_windows import PygletCameraWindow
    HAS_CUBE_WINDOWS = True
except ImportError as e:
    HAS_CUBE_WINDOWS = False
    print(f"⚠️ Cube windows not available: {e}")

class Cube:
    """Cube de base - classe centrale dont héritent tous les autres cubes"""
    def __init__(self, position, block_type="grass", texture=None, size=(1, 1, 1), 
                 has_camera=False, is_moveable=False, is_traversable=False):
        self.position = tuple(position)
        self.block_type = block_type
        self.texture = texture or block_type  # Texture par défaut basée sur le type
        self.size = size  # Taille du cube (x, y, z)
        self.has_camera = has_camera
        self.is_moveable = is_moveable
        self.is_traversable = is_traversable
        self.id = f"cube_{position[0]}_{position[1]}_{position[2]}_{block_type}"
        
        # Abstraction windows - Each cube can have an associated window
        self.windows = None  # Will be set by subclasses that need window functionality
        
    def move_to(self, new_position):
        """Déplace le cube vers une nouvelle position"""
        if self.is_moveable:
            old_position = self.position
            self.position = tuple(new_position)
            # Mise à jour de l'ID pour refléter la nouvelle position
            self.id = f"cube_{new_position[0]}_{new_position[1]}_{new_position[2]}_{self.block_type}"
            return True
        return False
    
    def can_collide_with(self, other_cube):
        """Vérifie si ce cube peut entrer en collision avec un autre"""
        if self.is_traversable or (hasattr(other_cube, 'is_traversable') and other_cube.is_traversable):
            return False
        
        # Vérification basique de collision basée sur la position
        x1, y1, z1 = self.position
        x2, y2, z2 = other_cube.position
        sx1, sy1, sz1 = self.size
        sx2, sy2, sz2 = getattr(other_cube, 'size', (1, 1, 1))
        
        # Collision AABB (Axis-Aligned Bounding Box)
        return (abs(x1 - x2) < (sx1 + sx2) / 2 and
                abs(y1 - y2) < (sy1 + sy2) / 2 and
                abs(z1 - z2) < (sz1 + sz2) / 2)
    
    def to_dict(self):
        """Sérialise le cube"""
        return {
            "id": self.id,
            "position": self.position,
            "block_type": self.block_type,
            "texture": self.texture,
            "size": self.size,
            "has_camera": self.has_camera,
            "is_moveable": self.is_moveable,
            "is_traversable": self.is_traversable
        }

class Player(Cube):
    """Cube représentant un joueur"""
    def __init__(self, position, player_id, name="Player"):
        super().__init__(position, "player", texture="player", size=(0.8, 1.8, 0.8), 
                        has_camera=False, is_moveable=True, is_traversable=False)
        self.player_id = player_id
        self.name = name
        self.id = f"player_{player_id}"
    
    def update_position(self, new_position):
        """Met à jour la position du joueur"""
        return self.move_to(new_position)

class CubeCamera(Cube):
    """Cube avec caméra intégrée"""
    def __init__(self, position, name="Camera", resolution=(240, 180)):
        super().__init__(position, "camera", texture="camera", size=(1, 1, 1),
                        has_camera=True, is_moveable=True, is_traversable=False)
        self.id = f"cam_{datetime.now().timestamp()}"
        self.name = name
        self.rotation = [0, 0]  # yaw, pitch
        self.fov = 70
        self.resolution = resolution  # Résolution par défaut 240x180 pour balance qualité/performance
        
        # Initialize renderers in order of preference (fastest first)
        self.ultra_fast_renderer = None
        self.fast_renderer = None
        self.pyglet_renderer = None
        
        if HAS_ULTRA_FAST_RENDERER:
            try:
                self.ultra_fast_renderer = UltraFastRenderer(resolution)
                print(f"✅ Caméra {self.name} initialized with ultra-fast renderer")
            except Exception as e:
                print(f"⚠️ Failed to initialize ultra-fast renderer for camera {self.name}: {e}")
                
        if not self.ultra_fast_renderer and HAS_FAST_RENDERER:
            try:
                self.fast_renderer = FastCameraRenderer(resolution)
                print(f"✅ Caméra {self.name} initialized with fast optimized renderer")
            except Exception as e:
                print(f"⚠️ Failed to initialize fast renderer for camera {self.name}: {e}")
                
        if not self.ultra_fast_renderer and not self.fast_renderer:
            # Try to import Pyglet renderer at runtime
            try:
                from pyglet_camera_renderer import PygletCameraRenderer
                self.pyglet_renderer = PygletCameraRenderer(resolution)
                print(f"✅ Caméra {self.name} initialized with Pyglet renderer")
            except Exception as e:
                print(f"⚠️ Failed to initialize Pyglet renderer for camera {self.name}: {e}")
                self.pyglet_renderer = None
        
        if not self.ultra_fast_renderer and not self.fast_renderer and not self.pyglet_renderer:
            print(f"⚠️ Caméra {self.name} will use fallback ray tracing renderer")
        
        self._world_cache_hash = None  # Cache world state to avoid rebuilding geometry every frame
        
        # Initialize window functionality for camera visualization
        if HAS_CUBE_WINDOWS:
            try:
                self.windows = PygletCameraWindow(self.id, self)
                print(f"✅ Caméra {self.name} window initialized")
            except Exception as e:
                print(f"⚠️ Failed to initialize window for camera {self.name}: {e}")
                self.windows = None
        else:
            self.windows = None
        
    def rotate(self, yaw_delta, pitch_delta):
        """Rotation de la caméra"""
        self.rotation[0] += yaw_delta
        self.rotation[1] = max(-90, min(90, self.rotation[1] + pitch_delta))
    
    def move_camera(self, new_position):
        """Déplace la caméra (wrapper spécialisé)"""
        return self.move_to(new_position)
    
    def get_active_renderer_type(self):
        """Retourne le type de rendu actuellement actif"""
        if self.ultra_fast_renderer:
            return "Ultra-Fast Renderer"
        elif self.fast_renderer:
            return "Fast Optimized Renderer"
        elif self.pyglet_renderer:
            return "Pyglet Renderer"
        else:
            return "Original Ray Tracing"
    
    def activate_window(self):
        """Active la fenêtre Pyglet pour visualisation de la caméra"""
        if self.windows:
            try:
                self.windows.activate()
                print(f"✅ Window activated for camera {self.name}")
                return True
            except Exception as e:
                print(f"⚠️ Failed to activate window for camera {self.name}: {e}")
                return False
        else:
            print(f"⚠️ No window available for camera {self.name}")
            return False
    
    def deactivate_window(self):
        """Désactive la fenêtre Pyglet de la caméra"""
        if self.windows:
            try:
                self.windows.deactivate()
                print(f"✅ Window deactivated for camera {self.name}")
                return True
            except Exception as e:
                print(f"⚠️ Failed to deactivate window for camera {self.name}: {e}")
                return False
        return True
    
    def capture_window_frame(self):
        """Capture une image de la fenêtre de la caméra"""
        if self.windows and self.windows.is_active:
            try:
                frame_data = self.windows.capture_frame()
                if frame_data:
                    print(f"✅ Frame captured from camera {self.name} window")
                    return frame_data
                else:
                    print(f"⚠️ No frame data captured from camera {self.name}")
                    return None
            except Exception as e:
                print(f"⚠️ Failed to capture frame from camera {self.name}: {e}")
                return None
        else:
            print(f"⚠️ Window not active for camera {self.name}")
            return None
    
    def is_window_active(self):
        """Vérifie si la fenêtre de la caméra est active"""
        return self.windows and self.windows.is_active
    
    def render_view(self, world, frame_count=0):
        """Génère une vue de la caméra en regardant réellement le monde (ultra-optimisé)"""
        width, height = self.resolution
        
        # Use ultra-fast renderer if available
        if self.ultra_fast_renderer:
            try:
                # Check if world has changed and update renderer geometry
                world_blocks = world.get_all_blocks()
                world_hash = hash(frozenset((pos, block.block_type) for pos, block in world_blocks.items()))
                
                if world_hash != self._world_cache_hash:
                    self.ultra_fast_renderer.update_world(world_blocks, self.position)
                    self._world_cache_hash = world_hash
                
                # Render camera view with ultra-fast renderer
                pixel_data = self.ultra_fast_renderer.render_camera_view(
                    self.position, 
                    self.rotation, 
                    self.fov,
                    frame_count
                )
                
                return pixel_data
                
            except Exception as e:
                print(f"⚠️ Ultra-fast renderer failed for camera {self.name}: {e}")
                print("🔄 Falling back to fast renderer...")
                # Fall through to try fast renderer
        
        # Use fast renderer if available and ultra-fast renderer failed
        if self.fast_renderer:
            try:
                # Check if world has changed and update renderer geometry
                world_blocks = world.get_all_blocks()
                world_hash = hash(frozenset((pos, block.block_type) for pos, block in world_blocks.items()))
                
                if world_hash != self._world_cache_hash:
                    self.fast_renderer.update_world(world_blocks)
                    self._world_cache_hash = world_hash
                
                # Render camera view with fast renderer
                pixel_data = self.fast_renderer.render_camera_view(
                    self.position, 
                    self.rotation, 
                    self.fov,
                    frame_count
                )
                
                return pixel_data
                
            except Exception as e:
                print(f"⚠️ Fast renderer failed for camera {self.name}: {e}")
                print("🔄 Falling back to Pyglet renderer...")
                # Fall through to try Pyglet renderer
        
        # Use Pyglet renderer if available and other renderers failed
        if self.pyglet_renderer:
            try:
                # Check if world has changed and update renderer geometry
                world_blocks = world.get_all_blocks()
                world_hash = hash(frozenset((pos, block.block_type) for pos, block in world_blocks.items()))
                
                if world_hash != self._world_cache_hash:
                    self.pyglet_renderer.update_world(world_blocks)
                    self._world_cache_hash = world_hash
                
                # Render camera view with Pyglet
                pixel_data = self.pyglet_renderer.render_camera_view(
                    self.position, 
                    self.rotation, 
                    self.fov
                )
                
                # Add visual indicators (LED and frame counter) to pixel data
                pixel_array = bytearray(pixel_data)
                self._add_visual_indicators(pixel_array, width, height, frame_count)
                
                return bytes(pixel_array)
                
            except Exception as e:
                print(f"⚠️ Pyglet renderer failed for camera {self.name}: {e}")
                print("🔄 Falling back to ray tracing...")
                # Fall through to ray tracing backup
        
        # Fallback: Original ray tracing implementation
        return self._render_view_raytracing(world, frame_count)
    
    def _add_visual_indicators(self, pixel_array, width, height, frame_count):
        """Add LED indicator and frame counter to rendered image"""
        for py in range(height):
            for px in range(width):
                pixel_offset = (py * width + px) * 3
                
                # LED indicator in top-right corner
                if px >= width - 10 and py <= 8:
                    led_on = (frame_count // 3) % 2 == 0
                    if px >= width - 8 and py <= 6:
                        if led_on:
                            pixel_array[pixel_offset:pixel_offset+3] = [0, 255, 0]  # Green
                        else:
                            pixel_array[pixel_offset:pixel_offset+3] = [0, 120, 0]  # Dark green
                    elif px >= width - 10 and py <= 8:
                        if led_on:
                            pixel_array[pixel_offset:pixel_offset+3] = [0, 200, 0]  # Medium green
                        else:
                            pixel_array[pixel_offset:pixel_offset+3] = [0, 80, 0]   # Very dark green
                
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
                            pixel_array[pixel_offset:pixel_offset+3] = [255, 255, 0]  # Yellow counter
    
    def _render_view_raytracing(self, world, frame_count=0):
        """Fallback ray tracing implementation (original method)"""
        width, height = self.resolution
        pixels = []
        
        cx, cy, cz = self.position
        yaw, pitch = self.rotation
        
        # Convertit rotation en radians
        yaw_rad = math.radians(yaw)
        pitch_rad = math.radians(pitch)
        
        for py in range(height):
            for px in range(width):
                # Calcule l'angle de vue pour ce pixel
                # FOV mapping
                fov_rad = math.radians(self.fov)
                aspect = width / height
                
                # Normalise les coordonnées pixel [-1, 1]
                screen_x = (2.0 * px / width - 1.0) * aspect
                screen_y = 1.0 - 2.0 * py / height
                
                # Direction du rayon pour ce pixel
                # Direction de base (regardant vers +Z)
                ray_x = screen_x * math.tan(fov_rad / 2)
                ray_y = screen_y * math.tan(fov_rad / 2)
                ray_z = 1.0
                
                # Applique la rotation yaw (autour de Y)
                cos_yaw = math.cos(yaw_rad)
                sin_yaw = math.sin(yaw_rad)
                temp_x = ray_x * cos_yaw - ray_z * sin_yaw
                temp_z = ray_x * sin_yaw + ray_z * cos_yaw
                ray_x = temp_x
                ray_z = temp_z
                
                # Applique la rotation pitch (autour de X)
                cos_pitch = math.cos(pitch_rad)
                sin_pitch = math.sin(pitch_rad)
                temp_y = ray_y * cos_pitch - ray_z * sin_pitch
                temp_z = ray_y * sin_pitch + ray_z * cos_pitch
                ray_y = temp_y
                ray_z = temp_z
                
                # Normalise le rayon
                length = math.sqrt(ray_x**2 + ray_y**2 + ray_z**2)
                ray_x /= length
                ray_y /= length
                ray_z /= length
                
                # Ray marching simple
                color = self._ray_march(cx, cy, cz, ray_x, ray_y, ray_z, world)
                
                # Ajoute un indicateur visuel de mise à jour en cours
                # LED clignotante dans le coin supérieur droit pour montrer que c'est "live"
                if px >= width - 10 and py <= 8:
                    # LED qui clignote selon le frame count
                    led_on = (frame_count // 3) % 2 == 0  # Clignote toutes les 3 frames
                    if px >= width - 8 and py <= 6:
                        if led_on:
                            color = [0, 255, 0]  # Vert vif = caméra live
                        else:
                            color = [0, 120, 0]  # Vert foncé quand éteint
                    elif px >= width - 10 and py <= 8:
                        # Bordure autour de la LED
                        if led_on:
                            color = [0, 200, 0]  # Vert moyennement vif
                        else:
                            color = [0, 80, 0]   # Vert très foncé
                
                # Ajoute un petit indicateur numérique pour le frame count dans le coin inférieur droit
                if px >= width - 15 and py >= height - 10:
                    # Affiche les derniers chiffres du frame count comme une grille de pixels
                    digit = frame_count % 10
                    rel_x = px - (width - 15)
                    rel_y = py - (height - 10)
                    
                    # Matrice simple pour afficher les chiffres 0-9 (5x8 pixels)
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
                            color = [255, 255, 0]  # Jaune pour le compteur
                
                pixels.extend(color)
        
        return bytes(pixels)
    
    def _ray_march(self, ox, oy, oz, dx, dy, dz, world, max_dist=20):
        """Lance un rayon et retourne la couleur du premier bloc touché (optimisé)"""
        step = 1.0  # Augmenté à 1.0 pour des steps de 1 bloc complet (25% d'itérations en moins)
        
        # Utilise tous les blocs (réguliers + joueurs)
        all_blocks = world.get_all_blocks()
        
        # Optimisation: réduit la distance max pour moins d'itérations
        max_iterations = int(max_dist / step)
        for i in range(max_iterations):
            # Position actuelle sur le rayon
            x = ox + dx * i * step
            y = oy + dy * i * step
            z = oz + dz * i * step
            
            # Vérifie si on touche un bloc
            block_pos = (int(math.floor(x)), int(math.floor(y)), int(math.floor(z)))
            
            if block_pos in all_blocks:
                block = all_blocks[block_pos]
                # Retourne la couleur selon le type de bloc
                if block.block_type == "grass":
                    return [34, 139, 34]  # Vert
                elif block.block_type == "stone":
                    return [128, 128, 128]  # Gris
                elif block.block_type == "player":
                    return [0, 150, 255]  # Bleu pour les joueurs
                elif block.block_type == "camera":
                    return [255, 255, 0]  # Jaune pour les caméras
                elif block.block_type == "ai_agent":
                    return [255, 0, 255]  # Magenta pour les agents IA
                else:
                    return [139, 69, 19]  # Marron (terre par défaut)
        
        # Couleur du ciel si rien n'est touché
        # Gradient ciel simple
        if dy > 0:
            return [135, 206, 235]  # Bleu ciel
        else:
            return [100, 149, 237]  # Bleu plus foncé vers le bas
    
    def to_dict(self):
        """Sérialise le cube caméra avec informations supplémentaires"""
        base_dict = super().to_dict()
        base_dict.update({
            "name": self.name,
            "rotation": self.rotation,
            "fov": self.fov,
            "resolution": self.resolution
        })
        return base_dict

class CubeAI(Cube):
    """Cube avec intelligence artificielle"""
    def __init__(self, position, name="AI_Agent", ai_type="basic"):
        super().__init__(position, "ai_agent", texture="ai_agent", size=(1, 1, 1),
                        has_camera=False, is_moveable=True, is_traversable=False)
        self.id = f"ai_{datetime.now().timestamp()}"
        self.name = name
        self.ai_type = ai_type  # basic, advanced, neural_network, etc.
        self.behavior_state = "idle"  # idle, moving, observing, interacting
        self.target_position = None
        self.memory = {}  # Pour stocker des informations contextuelles
        self.sensors = []  # Liste des capteurs disponibles
        
    def set_behavior_state(self, state):
        """Change l'état de comportement de l'agent IA"""
        valid_states = ["idle", "moving", "observing", "interacting", "learning"]
        if state in valid_states:
            self.behavior_state = state
            return True
        return False
    
    def set_target(self, target_position):
        """Définit une position cible pour l'agent IA"""
        self.target_position = tuple(target_position)
        self.set_behavior_state("moving")
    
    def add_sensor(self, sensor_type, sensor_config=None):
        """Ajoute un capteur à l'agent IA"""
        sensor = {
            "type": sensor_type,
            "config": sensor_config or {},
            "active": True
        }
        self.sensors.append(sensor)
        return len(self.sensors) - 1  # Retourne l'index du capteur
    
    def update_memory(self, key, value):
        """Met à jour la mémoire de l'agent IA"""
        self.memory[key] = value
    
    def to_dict(self):
        """Sérialise le cube IA avec informations supplémentaires"""
        base_dict = super().to_dict()
        base_dict.update({
            "name": self.name,
            "ai_type": self.ai_type,
            "behavior_state": self.behavior_state,
            "target_position": self.target_position,
            "sensors": self.sensors,
            "memory_keys": list(self.memory.keys())  # Ne sérialise que les clés pour la confidentialité
        })
        return base_dict

class World:
    """Monde Minecraft"""
    def __init__(self, size=20):
        self.size = size
        self.blocks = {}  # Cubes standard du terrain
        self.cameras = {}  # Cubes caméra
        self.ai_agents = {}  # Cubes IA
        self.players = {}  # Cubes joueurs
        self.special_cubes = {}  # Autres cubes spéciaux
        self.generate_world()
    
    def generate_world(self):
        """Génère un monde simple"""
        print("Génération du monde...")
        
        # Sol en herbe
        for x in range(-self.size, self.size):
            for z in range(-self.size, self.size):
                self.blocks[(x, 0, z)] = Cube([x, 0, z], "grass")
        
        # Quelques structures aléatoires
        for _ in range(10):
            x = random.randint(-self.size+5, self.size-5)
            z = random.randint(-self.size+5, self.size-5)
            height = random.randint(2, 5)
            
            for y in range(1, height):
                self.blocks[(x, y, z)] = Cube([x, y, z], "stone")
        
        print(f"Monde généré: {len(self.blocks)} blocs")
    
    def add_camera(self, position, name, resolution=(320, 240)):
        """Ajoute une caméra au monde"""
        camera = CubeCamera(position, name, resolution)
        self.cameras[camera.id] = camera
        return camera
    
    def get_camera(self, camera_id):
        """Récupère une caméra"""
        return self.cameras.get(camera_id)
    
    def add_ai_agent(self, position, name="AI_Agent", ai_type="basic"):
        """Ajoute un agent IA au monde"""
        ai_agent = CubeAI(position, name, ai_type)
        self.ai_agents[ai_agent.id] = ai_agent
        return ai_agent
    
    def get_ai_agent(self, ai_id):
        """Récupère un agent IA"""
        return self.ai_agents.get(ai_id)
    
    def add_player(self, player_id, position, name="Player"):
        """Ajoute un joueur au monde comme un cube"""
        player = Player(position, player_id, name)
        self.players[player_id] = player
        return player
    
    def update_player_position(self, player_id, new_position):
        """Met à jour la position d'un joueur"""
        if player_id in self.players:
            return self.players[player_id].update_position(new_position)
        return False
    
    def remove_player(self, player_id):
        """Supprime un joueur du monde"""
        if player_id in self.players:
            del self.players[player_id]
            return True
        return False
    
    def move_cube(self, cube_id, new_position):
        """Déplace un cube spécifique"""
        # Cherche dans toutes les collections de cubes
        all_collections = [self.cameras, self.ai_agents, self.players, self.special_cubes]
        
        for collection in all_collections:
            if cube_id in collection:
                cube = collection[cube_id]
                if hasattr(cube, 'move_to'):
                    return cube.move_to(new_position)
                break
        return False
    
    def remove_cube(self, cube_id):
        """Supprime un cube du monde"""
        # Cherche dans toutes les collections
        all_collections = [
            (self.cameras, "camera"),
            (self.ai_agents, "ai_agent"), 
            (self.players, "player"),
            (self.special_cubes, "special")
        ]
        
        for collection, cube_type in all_collections:
            if cube_id in collection:
                del collection[cube_id]
                return True
        
        # Cherche dans les blocs standard par position
        for pos, cube in list(self.blocks.items()):
            if cube.id == cube_id and cube.is_moveable:
                del self.blocks[pos]
                return True
        
        return False
    
    def get_all_blocks(self):
        """Retourne tous les blocs (réguliers + tous types de cubes) pour le ray-marching"""
        all_blocks = dict(self.blocks)
        
        # Ajoute tous les types de cubes
        for collection in [self.cameras, self.ai_agents, self.players, self.special_cubes]:
            for cube in collection.values():
                # Convertit la position en coordonnées de bloc
                floored_pos = (int(math.floor(cube.position[0])), 
                              int(math.floor(cube.position[1])), 
                              int(math.floor(cube.position[2])))
                all_blocks[floored_pos] = cube
        
        return all_blocks
    
    def check_collision(self, cube, new_position):
        """Vérifie les collisions pour un cube à une nouvelle position"""
        # Pour simplifier, nous désactivons la collision pour les cubes spéciaux mobiles
        # Dans une implémentation plus avancée, on utiliserait une détection de collision appropriée
        if hasattr(cube, 'is_moveable') and cube.is_moveable:
            return False  # Pas de collision pour les cubes mobiles
        
        return False  # Pas de collision par défaut
    
    def to_dict(self):
        """Sérialise le monde"""
        blocks_data = {}
        for pos, cube in self.blocks.items():
            key = f"{pos[0]},{pos[1]},{pos[2]}"
            blocks_data[key] = cube.block_type
        
        # Ajoute tous les types de cubes spéciaux
        all_special_cubes = []
        all_special_cubes.extend(self.players.values())
        all_special_cubes.extend(self.cameras.values())
        all_special_cubes.extend(self.ai_agents.values())
        all_special_cubes.extend(self.special_cubes.values())
        
        for cube in all_special_cubes:
            key = f"{cube.position[0]},{cube.position[1]},{cube.position[2]}"
            blocks_data[key] = cube.block_type
        
        return {
            "size": self.size,
            "blocks": blocks_data,
            "cameras": {cid: cam.to_dict() for cid, cam in self.cameras.items()},
            "ai_agents": {aid: ai.to_dict() for aid, ai in self.ai_agents.items()},
            "players": {pid: {"position": list(p.position), "name": p.name} for pid, p in self.players.items()},
            "special_cubes": {sid: sc.to_dict() for sid, sc in self.special_cubes.items()}
        }

class MinecraftServer:
    """Serveur Minecraft WebSocket"""
    
    def __init__(self, host="localhost", port=8765):
        self.host = host
        self.port = port
        self.world = World(size=15)
        self.clients = set()
        self.camera_subscribers = {}  # {camera_id: set(websockets)}
        self.player_positions = {}  # {websocket: position} to track player positions
    
    async def start(self):
        """Démarre le serveur"""
        async with websockets.serve(
            lambda websocket: self.handle_client(websocket, None), 
            self.host, 
            self.port,
            ping_interval=20,  # Envoie un ping toutes les 20 secondes
            ping_timeout=10,   # Timeout de 10 secondes pour recevoir un pong
            close_timeout=10   # Timeout de 10 secondes pour fermer proprement
        ):
            print(f"🎮 Serveur Minecraft démarré sur ws://{self.host}:{self.port}")
            print(f"📦 Monde: {len(self.world.blocks)} blocs")
            await asyncio.Future()  # Run forever
    
    async def handle_client(self, websocket, path):
        """Gère une connexion client"""
        self.clients.add(websocket)
        player_id = f"player_{id(websocket)}"
        print(f"✅ Client connecté: {websocket.remote_address} (ID: {player_id})")
        
        # Ajoute le joueur au monde à une position par défaut
        default_position = [0, 2, 0]  # Au-dessus du sol
        self.world.add_player(player_id, default_position, f"Joueur_{len(self.clients)}")
        self.player_positions[websocket] = tuple(default_position)
        
        # Envoie le monde initial
        await self.send_world_state(websocket)
        
        # Broadcast l'arrivée du nouveau joueur à tous les autres clients
        await self.broadcast_to_all({
            "type": "player_joined",
            "player_id": player_id,
            "position": default_position
        })
        
        try:
            async for message in websocket:
                await self.handle_message(websocket, message)
        except websockets.exceptions.ConnectionClosed as e:
            print(f"❌ Client déconnecté: {websocket.remote_address} (code: {e.code})")
        except websockets.exceptions.InvalidMessage as e:
            print(f"❌ Message invalide du client {websocket.remote_address}: {e}")
        except Exception as e:
            print(f"❌ Erreur avec le client {websocket.remote_address}: {e}")
        finally:
            print(f"🧹 Nettoyage des ressources pour le client {websocket.remote_address}")
            self.clients.discard(websocket)
            # Nettoie les abonnements caméra
            for subscribers in self.camera_subscribers.values():
                subscribers.discard(websocket)
            # Supprime le joueur du monde
            if websocket in self.player_positions:
                try:
                    self.world.remove_player(player_id)
                    del self.player_positions[websocket]
                    # Broadcast la déconnexion du joueur
                    await self.broadcast_to_all({
                        "type": "player_left", 
                        "player_id": player_id
                    })
                except Exception as cleanup_error:
                    print(f"⚠️  Erreur lors du nettoyage: {cleanup_error}")
    
    async def handle_message(self, websocket, message):
        """Route les messages"""
        try:
            data = json.loads(message)
            msg_type = data.get("type")
            
            if msg_type == "create_camera":
                await self.handle_create_camera(websocket, data)
            elif msg_type == "subscribe_camera":
                await self.handle_subscribe_camera(websocket, data)
            elif msg_type == "control_camera":
                await self.handle_control_camera(websocket, data)
            elif msg_type == "get_cameras":
                await self.handle_get_cameras(websocket)
            elif msg_type == "create_ai_agent":
                await self.handle_create_ai_agent(websocket, data)
            elif msg_type == "control_ai_agent":
                await self.handle_control_ai_agent(websocket, data)
            elif msg_type == "get_ai_agents":
                await self.handle_get_ai_agents(websocket)
            elif msg_type == "move_cube":
                await self.handle_move_cube(websocket, data)
            elif msg_type == "remove_cube":
                await self.handle_remove_cube(websocket, data)
            elif msg_type == "get_cube_info":
                await self.handle_get_cube_info(websocket, data)
            elif msg_type == "activate_camera_window":
                await self.handle_activate_camera_window(websocket, data)
            elif msg_type == "deactivate_camera_window":
                await self.handle_deactivate_camera_window(websocket, data)
            elif msg_type == "capture_camera_window":
                await self.handle_capture_camera_window(websocket, data)
            elif msg_type == "get_camera_window_status":
                await self.handle_get_camera_window_status(websocket, data)
            elif msg_type == "place_block":
                await self.handle_place_block(websocket, data)
            elif msg_type == "destroy_block":
                await self.handle_destroy_block(websocket, data)
            elif msg_type == "player_position_update":
                await self.handle_player_position_update(websocket, data)
            elif msg_type == "get_player_positions":
                await self.handle_get_player_positions(websocket, data)
            else:
                await websocket.send(json.dumps({
                    "type": "error",
                    "message": f"Type inconnu: {msg_type}"
                }))
        except Exception as e:
            await websocket.send(json.dumps({
                "type": "error",
                "message": str(e)
            }))
    
    async def send_world_state(self, websocket):
        """Envoie l'état du monde"""
        await websocket.send(json.dumps({
            "type": "world_state",
            "world": self.world.to_dict()
        }))
    
    async def handle_create_camera(self, websocket, data):
        """Crée une caméra"""
        position = data.get("position", [0, 2, 0])
        name = data.get("name", "Camera")
        resolution = data.get("resolution", (240, 180))  # Résolution équilibrée pour performance
        
        # Valide la résolution (limites raisonnables)
        if isinstance(resolution, list) and len(resolution) == 2:
            width, height = resolution
            # Limite les résolutions pour éviter les problèmes de performance
            width = max(160, min(1920, width))
            height = max(120, min(1080, height))
            resolution = (width, height)
        else:
            resolution = (240, 180)  # Valeur par défaut équilibrée pour performance
        
        camera = self.world.add_camera(position, name, resolution)
        
        # Initialise les abonnés
        self.camera_subscribers[camera.id] = set()
        
        # Démarre le stream
        asyncio.create_task(self.camera_stream_loop(camera))
        
        await websocket.send(json.dumps({
            "type": "camera_created",
            "camera": camera.to_dict()
        }))
        
        print(f"📷 Caméra créée: {camera.id} à {position}")
    
    async def handle_subscribe_camera(self, websocket, data):
        """Abonne un client au stream caméra"""
        camera_id = data.get("camera_id")
        
        # Vérifie si la caméra existe dans le monde
        if camera_id in self.world.cameras:
            # Initialise les abonnés si pas encore fait
            if camera_id not in self.camera_subscribers:
                self.camera_subscribers[camera_id] = set()
                # Démarre le stream si pas encore actif
                asyncio.create_task(self.camera_stream_loop(self.world.cameras[camera_id]))
            
            self.camera_subscribers[camera_id].add(websocket)
            await websocket.send(json.dumps({
                "type": "subscribed",
                "camera_id": camera_id,
                "message": f"Abonné à la caméra {camera_id}"
            }))
            print(f"👁️  Client abonné à caméra {camera_id}")
        else:
            await websocket.send(json.dumps({
                "type": "error",
                "message": f"Caméra {camera_id} introuvable"
            }))
    
    async def handle_control_camera(self, websocket, data):
        """Contrôle une caméra"""
        camera_id = data.get("camera_id")
        camera = self.world.get_camera(camera_id)
        
        if not camera:
            await websocket.send(json.dumps({
                "type": "error",
                "message": f"Caméra {camera_id} introuvable"
            }))
            return
        
        action = data.get("action")
        
        if action == "rotate":
            yaw = data.get("yaw", 0)
            pitch = data.get("pitch", 0)
            camera.rotate(yaw, pitch)
        elif action == "move":
            delta = data.get("delta", [0, 0, 0])
            camera.position[0] += delta[0]
            camera.position[1] += delta[1]
            camera.position[2] += delta[2]
        
        await websocket.send(json.dumps({
            "type": "camera_updated",
            "camera": camera.to_dict()
        }))
    
    async def handle_get_cameras(self, websocket):
        """Liste toutes les caméras"""
        cameras = {cid: cam.to_dict() for cid, cam in self.world.cameras.items()}
        await websocket.send(json.dumps({
            "type": "cameras_list",
            "cameras": cameras
        }))
    
    async def handle_place_block(self, websocket, data):
        """Place un bloc"""
        position = tuple(data.get("position"))
        block_type = data.get("block_type", "stone")
        
        # Ajoute le bloc au monde
        if position not in self.world.blocks:
            self.world.blocks[position] = Cube(position, block_type)
            print(f"🟦 Bloc placé à {position}: {block_type}")
            
            # Broadcast à tous les clients
            await self.broadcast_to_all({
                "type": "block_placed",
                "position": list(position),
                "block_type": block_type
            })
    
    async def handle_destroy_block(self, websocket, data):
        """Détruit un bloc"""
        position = tuple(data.get("position"))
        
        # Retire le bloc du monde
        if position in self.world.blocks:
            del self.world.blocks[position]
            print(f"💥 Bloc détruit à {position}")
            
            # Broadcast à tous les clients
            await self.broadcast_to_all({
                "type": "block_destroyed",
                "position": list(position)
            })
    
    async def handle_player_position_update(self, websocket, data):
        """Met à jour la position du joueur côté serveur"""
        position = data.get("position", [0, 0, 0])
        player_id = f"player_{id(websocket)}"
        
        # Met à jour la position dans le monde
        old_position = self.player_positions.get(websocket)
        self.world.update_player_position(player_id, position)
        self.player_positions[websocket] = tuple(position)
        
        print(f"🚶 Position joueur {websocket.remote_address} mise à jour: {position}")
        
        # Broadcast la nouvelle position à tous les autres clients
        await self.broadcast_to_others(websocket, {
            "type": "player_position_changed",
            "player_id": player_id,
            "position": position,
            "old_position": list(old_position) if old_position else None
        })
    
    async def handle_get_player_positions(self, websocket):
        """Renvoie les positions de tous les joueurs connectés"""
        positions = {}
        for ws, pos in self.player_positions.items():
            # Use a simple identifier for each client
            client_id = f"player_{id(ws)}"
            positions[client_id] = list(pos)
        
        await websocket.send(json.dumps({
            "type": "player_positions",
            "positions": positions,
            "count": len(positions)
        }))
        
        print(f"📊 Envoyé positions de {len(positions)} joueurs à {websocket.remote_address}")
    
    async def handle_create_ai_agent(self, websocket, data):
        """Crée un nouvel agent IA"""
        position = data.get("position", [0, 1, 0])
        name = data.get("name", "AI_Agent")
        ai_type = data.get("ai_type", "basic")
        
        try:
            ai_agent = self.world.add_ai_agent(position, name, ai_type)
            
            await websocket.send(json.dumps({
                "type": "ai_agent_created",
                "ai_agent": ai_agent.to_dict()
            }))
            
            # Broadcast aux autres clients
            await self.broadcast_to_others(websocket, {
                "type": "ai_agent_added",
                "ai_agent": ai_agent.to_dict()
            })
            
            print(f"🤖 Agent IA créé: {name} à {position}")
            
        except Exception as e:
            await websocket.send(json.dumps({
                "type": "error",
                "message": f"Erreur création agent IA: {str(e)}"
            }))
    
    async def handle_control_ai_agent(self, websocket, data):
        """Contrôle un agent IA"""
        ai_id = data.get("ai_id")
        command = data.get("command")
        
        ai_agent = self.world.get_ai_agent(ai_id)
        if not ai_agent:
            await websocket.send(json.dumps({
                "type": "error",
                "message": "Agent IA introuvable"
            }))
            return
        
        try:
            if command == "move":
                new_position = data.get("position")
                if new_position:
                    success = ai_agent.move_to(new_position)
                    if success:
                        await self.broadcast_to_all({
                            "type": "ai_agent_moved",
                            "ai_id": ai_id,
                            "position": new_position
                        })
            elif command == "set_behavior":
                behavior = data.get("behavior")
                success = ai_agent.set_behavior_state(behavior)
                if success:
                    await self.broadcast_to_all({
                        "type": "ai_agent_behavior_changed",
                        "ai_id": ai_id,
                        "behavior": behavior
                    })
            elif command == "set_target":
                target = data.get("target_position")
                ai_agent.set_target(target)
                await self.broadcast_to_all({
                    "type": "ai_agent_target_set",
                    "ai_id": ai_id,
                    "target": target
                })
            
            await websocket.send(json.dumps({
                "type": "ai_agent_controlled",
                "ai_id": ai_id,
                "command": command,
                "success": True
            }))
            
        except Exception as e:
            await websocket.send(json.dumps({
                "type": "error",
                "message": f"Erreur contrôle agent IA: {str(e)}"
            }))
    
    async def handle_get_ai_agents(self, websocket):
        """Renvoie la liste des agents IA"""
        agents = {aid: agent.to_dict() for aid, agent in self.world.ai_agents.items()}
        
        await websocket.send(json.dumps({
            "type": "ai_agents_list",
            "ai_agents": agents,
            "count": len(agents)
        }))
    
    async def handle_move_cube(self, websocket, data):
        """Déplace un cube spécifique"""
        cube_id = data.get("cube_id")
        new_position = data.get("position")
        
        if not cube_id or not new_position:
            await websocket.send(json.dumps({
                "type": "error",
                "message": "ID du cube et position requis"
            }))
            return
        
        success = self.world.move_cube(cube_id, new_position)
        
        if success:
            await self.broadcast_to_all({
                "type": "cube_moved",
                "cube_id": cube_id,
                "position": new_position
            })
            
            await websocket.send(json.dumps({
                "type": "cube_moved",
                "cube_id": cube_id,
                "position": new_position,
                "success": True
            }))
        else:
            await websocket.send(json.dumps({
                "type": "error",
                "message": "Impossible de déplacer le cube"
            }))
    
    async def handle_remove_cube(self, websocket, data):
        """Supprime un cube"""
        cube_id = data.get("cube_id")
        
        if not cube_id:
            await websocket.send(json.dumps({
                "type": "error",
                "message": "ID du cube requis"
            }))
            return
        
        success = self.world.remove_cube(cube_id)
        
        if success:
            await self.broadcast_to_all({
                "type": "cube_removed",
                "cube_id": cube_id
            })
            
            await websocket.send(json.dumps({
                "type": "cube_removed",
                "cube_id": cube_id,
                "success": True
            }))
        else:
            await websocket.send(json.dumps({
                "type": "error",
                "message": "Impossible de supprimer le cube"
            }))
    
    async def handle_get_cube_info(self, websocket, data):
        """Récupère les informations d'un cube"""
        cube_id = data.get("cube_id")
        
        # Recherche dans toutes les collections
        cube = None
        cube_type = None
        
        if cube_id in self.world.cameras:
            cube = self.world.cameras[cube_id]
            cube_type = "camera"
        elif cube_id in self.world.ai_agents:
            cube = self.world.ai_agents[cube_id]
            cube_type = "ai_agent"
        elif cube_id in self.world.players:
            cube = self.world.players[cube_id]
            cube_type = "player"
        elif cube_id in self.world.special_cubes:
            cube = self.world.special_cubes[cube_id]
            cube_type = "special"
        
        if cube:
            await websocket.send(json.dumps({
                "type": "cube_info",
                "cube": cube.to_dict(),
                "cube_type": cube_type
            }))
        else:
            await websocket.send(json.dumps({
                "type": "error",
                "message": "Cube introuvable"
            }))
    
    async def handle_activate_camera_window(self, websocket, data):
        """Active la fenêtre d'une caméra"""
        camera_id = data.get("camera_id")
        if not camera_id:
            await websocket.send(json.dumps({
                "type": "error", 
                "message": "camera_id requis"
            }))
            return
        
        camera = self.world.cameras.get(camera_id)
        if not camera:
            await websocket.send(json.dumps({
                "type": "error",
                "message": "Caméra introuvable"
            }))
            return
            
        try:
            success = camera.activate_window()
            await websocket.send(json.dumps({
                "type": "camera_window_activated",
                "camera_id": camera_id,
                "success": success,
                "window_active": camera.is_window_active()
            }))
        except Exception as e:
            await websocket.send(json.dumps({
                "type": "error",
                "message": f"Erreur activation fenêtre: {str(e)}"
            }))
    
    async def handle_deactivate_camera_window(self, websocket, data):
        """Désactive la fenêtre d'une caméra"""
        camera_id = data.get("camera_id")
        if not camera_id:
            await websocket.send(json.dumps({
                "type": "error",
                "message": "camera_id requis"
            }))
            return
            
        camera = self.world.cameras.get(camera_id)
        if not camera:
            await websocket.send(json.dumps({
                "type": "error",
                "message": "Caméra introuvable"
            }))
            return
            
        try:
            success = camera.deactivate_window()
            await websocket.send(json.dumps({
                "type": "camera_window_deactivated",
                "camera_id": camera_id,
                "success": success,
                "window_active": camera.is_window_active()
            }))
        except Exception as e:
            await websocket.send(json.dumps({
                "type": "error",
                "message": f"Erreur désactivation fenêtre: {str(e)}"
            }))
    
    async def handle_capture_camera_window(self, websocket, data):
        """Capture une image de la fenêtre de caméra"""
        camera_id = data.get("camera_id")
        if not camera_id:
            await websocket.send(json.dumps({
                "type": "error",
                "message": "camera_id requis" 
            }))
            return
            
        camera = self.world.cameras.get(camera_id)
        if not camera:
            await websocket.send(json.dumps({
                "type": "error",
                "message": "Caméra introuvable"
            }))
            return
            
        try:
            frame_data = camera.capture_window_frame()
            
            if frame_data:
                # Encode frame data as base64 for transmission
                import base64
                frame_b64 = base64.b64encode(frame_data).decode('utf-8')
                
                await websocket.send(json.dumps({
                    "type": "camera_window_frame",
                    "camera_id": camera_id,
                    "frame_data": frame_b64,
                    "resolution": camera.resolution,
                    "format": "RGB"
                }))
            else:
                await websocket.send(json.dumps({
                    "type": "camera_window_frame",
                    "camera_id": camera_id,
                    "frame_data": None,
                    "message": "Aucune données de frame disponible"
                }))
                
        except Exception as e:
            await websocket.send(json.dumps({
                "type": "error",
                "message": f"Erreur capture fenêtre: {str(e)}"
            }))
    
    async def handle_get_camera_window_status(self, websocket, data):
        """Obtient le statut de la fenêtre d'une caméra"""
        camera_id = data.get("camera_id")
        if not camera_id:
            await websocket.send(json.dumps({
                "type": "error",
                "message": "camera_id requis"
            }))
            return
            
        camera = self.world.cameras.get(camera_id)
        if not camera:
            await websocket.send(json.dumps({
                "type": "error", 
                "message": "Caméra introuvable"
            }))
            return
            
        try:
            await websocket.send(json.dumps({
                "type": "camera_window_status",
                "camera_id": camera_id,
                "window_active": camera.is_window_active(),
                "has_window": camera.windows is not None,
                "camera_name": camera.name,
                "resolution": camera.resolution
            }))
        except Exception as e:
            await websocket.send(json.dumps({
                "type": "error",
                "message": f"Erreur statut fenêtre: {str(e)}"
            }))
    
    async def broadcast_to_others(self, sender_websocket, message):
        """Envoie un message à tous les clients sauf l'expéditeur"""
        message_str = json.dumps(message)
        disconnected = []
        
        for client in list(self.clients):
            if client != sender_websocket:
                try:
                    await client.send(message_str)
                except websockets.exceptions.ConnectionClosed:
                    disconnected.append(client)
        
        # Nettoie les connexions fermées
        for client in disconnected:
            self.clients.discard(client)
    
    async def broadcast_to_all(self, message):
        """Envoie un message à tous les clients"""
        message_str = json.dumps(message)
        disconnected = []
        
        for client in list(self.clients):  # Copie pour éviter les modifications pendant l'itération
            try:
                await client.send(message_str)
            except websockets.exceptions.ConnectionClosed:
                disconnected.append(client)
            except Exception as e:
                print(f"⚠️  Erreur lors de l'envoi à un client: {e}")
                disconnected.append(client)
        
        # Nettoie les clients déconnectés
        for client in disconnected:
            self.clients.discard(client)
    
    async def broadcast_to_others(self, sender_websocket, message):
        """Envoie un message à tous les clients sauf l'expéditeur"""
        message_str = json.dumps(message)
        disconnected = []
        
        for client in list(self.clients):  # Copie pour éviter les modifications pendant l'itération
            if client != sender_websocket:
                try:
                    await client.send(message_str)
                except websockets.exceptions.ConnectionClosed:
                    disconnected.append(client)
                except Exception as e:
                    print(f"⚠️  Erreur lors de l'envoi à un client: {e}")
                    disconnected.append(client)
        
        # Nettoie les clients déconnectés
        for client in disconnected:
            self.clients.discard(client)
    
    async def camera_stream_loop(self, camera):
        """Boucle de streaming caméra"""
        fps = 24  # Increased to 24 FPS for ultra-fast, robust real-time rendering
        frame_interval = 1.0 / fps  # Temps entre les frames
        print(f"🎬 Démarrage streaming caméra {camera.id} à {fps} FPS")
        
        try:
            frame_count = 0
            last_frame_time = time.time()
            
            while camera.id in self.world.cameras:
                frame_count += 1
                
                # Contrôle du timing pour maintenir le FPS cible
                current_time = time.time()
                time_since_last_frame = current_time - last_frame_time
                
                if time_since_last_frame < frame_interval:
                    # Attend le temps nécessaire pour maintenir le FPS
                    sleep_time = frame_interval - time_since_last_frame
                    await asyncio.sleep(sleep_time)
                
                last_frame_time = time.time()
                
                # Rendu de la vue caméra
                frame_data = camera.render_view(self.world, frame_count)
                
                # Compresse l'image en JPEG pour réduire la taille
                compressed_frame = self.compress_frame_jpeg(frame_data, camera.resolution)
                
                # Encode en base64
                frame_b64 = base64.b64encode(compressed_frame).decode('utf-8')
                
                # Message de frame
                message = json.dumps({
                    "type": "camera_frame",
                    "camera_id": camera.id,
                    "width": camera.resolution[0],
                    "height": camera.resolution[1],
                    "frame": frame_b64,
                    "format": "jpeg",  # Indique le format de compression
                    "renderer": camera.get_active_renderer_type(),  # Type de rendu actif
                    "timestamp": datetime.now().isoformat()
                })
                
                # Envoie aux abonnés
                subscribers = list(self.camera_subscribers.get(camera.id, set()))
                
                if subscribers:
                    sent_count = 0
                    for ws in subscribers:
                        try:
                            await ws.send(message)
                            sent_count += 1
                        except Exception as e:
                            print(f"❌ Erreur envoi frame #{frame_count}: {e}")
                            self.camera_subscribers[camera.id].discard(ws)
                    
                    # Log plus modéré
                    if frame_count == 1 or frame_count % 10 == 0:
                        print(f"✅ Frame #{frame_count} envoyée à {sent_count} abonné(s) pour {camera.id}")
                else:
                    if frame_count % 30 == 0:  # Log périodique sans abonnés
                        print(f"⏸️  Pas d'abonnés pour {camera.id} (frame #{frame_count})")
                
        except Exception as e:
            print(f"❌ Erreur dans streaming loop: {e}")
            import traceback
            traceback.print_exc()
        
        print(f"🛑 Arrêt streaming caméra {camera.id}")
    
    def compress_frame_jpeg(self, frame_data, resolution, quality=75):
        """Compresse une frame en JPEG pour réduire la taille du message"""
        try:
            from PIL import Image
            import io
            
            width, height = resolution
            
            # Convertit les bytes en array numpy puis en image PIL
            import numpy as np
            frame_array = np.frombuffer(frame_data, dtype=np.uint8)
            frame_array = frame_array.reshape((height, width, 3))
            
            # Crée une image PIL
            img = Image.fromarray(frame_array)
            
            # Compresse en JPEG
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=quality, optimize=True)
            
            compressed_data = buffer.getvalue()
            buffer.close()
            
            # Log de compression (seulement pour la première frame)
            if len(compressed_data) < len(frame_data) * 0.8:  # Si compression > 20%
                compression_ratio = len(compressed_data) / len(frame_data)
                if hasattr(self, '_compression_logged') == False:
                    print(f"📦 Compression JPEG: {len(frame_data)} -> {len(compressed_data)} bytes (ratio: {compression_ratio:.2f})")
                    self._compression_logged = True
            
            return compressed_data
            
        except ImportError:
            # Si PIL n'est pas disponible, retourne les données brutes
            print("⚠️  PIL non disponible pour la compression JPEG")
            return frame_data
        except Exception as e:
            print(f"⚠️  Erreur compression JPEG: {e}")
            return frame_data

if __name__ == "__main__":
    server = MinecraftServer()
    asyncio.run(server.start())

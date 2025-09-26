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
from typing import Dict, Set
from datetime import datetime
import struct

class Cube:
    """Cube de base"""
    def __init__(self, position, block_type="grass"):
        self.position = tuple(position)
        self.block_type = block_type
        self.id = f"cube_{position[0]}_{position[1]}_{position[2]}"

class CubeCamera:
    """Cube avec caméra intégrée"""
    def __init__(self, position, name="Camera"):
        self.id = f"cam_{datetime.now().timestamp()}"
        self.position = list(position)
        self.name = name
        self.rotation = [0, 0]  # yaw, pitch
        self.fov = 70
        self.resolution = (320, 240)
        
    def rotate(self, yaw_delta, pitch_delta):
        """Rotation de la caméra"""
        self.rotation[0] += yaw_delta
        self.rotation[1] = max(-90, min(90, self.rotation[1] + pitch_delta))
    
    def render_view(self, world):
        """Génère une vue de la caméra en regardant réellement le monde"""
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
                pixels.extend(color)
        
        return bytes(pixels)
    
    def _ray_march(self, ox, oy, oz, dx, dy, dz, world, max_dist=50):
        """Lance un rayon et retourne la couleur du premier bloc touché"""
        step = 0.1
        
        for i in range(int(max_dist / step)):
            # Position actuelle sur le rayon
            x = ox + dx * i * step
            y = oy + dy * i * step
            z = oz + dz * i * step
            
            # Vérifie si on touche un bloc
            block_pos = (int(math.floor(x)), int(math.floor(y)), int(math.floor(z)))
            
            if block_pos in world.blocks:
                block = world.blocks[block_pos]
                # Retourne la couleur selon le type de bloc
                if block.block_type == "grass":
                    return [34, 139, 34]  # Vert
                elif block.block_type == "stone":
                    return [128, 128, 128]  # Gris
                else:
                    return [139, 69, 19]  # Marron (terre)
        
        # Couleur du ciel si rien n'est touché
        # Gradient ciel simple
        if dy > 0:
            return [135, 206, 235]  # Bleu ciel
        else:
            return [100, 149, 237]  # Bleu plus foncé vers le bas
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "position": self.position,
            "rotation": self.rotation,
            "fov": self.fov,
            "resolution": self.resolution
        }

class World:
    """Monde Minecraft"""
    def __init__(self, size=20):
        self.size = size
        self.blocks = {}
        self.cameras = {}
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
    
    def add_camera(self, position, name):
        """Ajoute une caméra au monde"""
        camera = CubeCamera(position, name)
        self.cameras[camera.id] = camera
        return camera
    
    def get_camera(self, camera_id):
        """Récupère une caméra"""
        return self.cameras.get(camera_id)
    
    def to_dict(self):
        """Sérialise le monde"""
        blocks_data = {}
        for pos, cube in self.blocks.items():
            key = f"{pos[0]},{pos[1]},{pos[2]}"
            blocks_data[key] = cube.block_type
        
        return {
            "size": self.size,
            "blocks": blocks_data,
            "cameras": {cid: cam.to_dict() for cid, cam in self.cameras.items()}
        }

class MinecraftServer:
    """Serveur Minecraft WebSocket"""
    
    def __init__(self, host="localhost", port=8765):
        self.host = host
        self.port = port
        self.world = World(size=15)
        self.clients = set()
        self.camera_subscribers = {}  # {camera_id: set(websockets)}
    
    async def start(self):
        """Démarre le serveur"""
        async with websockets.serve(self.handle_client, self.host, self.port):
            print(f"🎮 Serveur Minecraft démarré sur ws://{self.host}:{self.port}")
            print(f"📦 Monde: {len(self.world.blocks)} blocs")
            await asyncio.Future()  # Run forever
    
    async def handle_client(self, websocket, path):
        """Gère une connexion client"""
        self.clients.add(websocket)
        print(f"✅ Client connecté: {websocket.remote_address}")
        
        # Envoie le monde initial
        await self.send_world_state(websocket)
        
        try:
            async for message in websocket:
                await self.handle_message(websocket, message)
        except websockets.exceptions.ConnectionClosed:
            print(f"❌ Client déconnecté: {websocket.remote_address}")
        finally:
            self.clients.discard(websocket)
            # Nettoie les abonnements caméra
            for subscribers in self.camera_subscribers.values():
                subscribers.discard(websocket)
    
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
            elif msg_type == "place_block":
                await self.handle_place_block(websocket, data)
            elif msg_type == "destroy_block":
                await self.handle_destroy_block(websocket, data)
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
        
        camera = self.world.add_camera(position, name)
        
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
        
        if camera_id in self.camera_subscribers:
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
    
    async def broadcast_to_all(self, message):
        """Envoie un message à tous les clients"""
        message_str = json.dumps(message)
        disconnected = []
        
        for client in self.clients:
            try:
                await client.send(message_str)
            except:
                disconnected.append(client)
        
        # Nettoie les clients déconnectés
        for client in disconnected:
            self.clients.discard(client)
    
    async def camera_stream_loop(self, camera):
        """Boucle de streaming caméra"""
        fps = 10  # 10 FPS pour la démo
        
        while camera.id in self.world.cameras:
            # Rendu de la vue caméra
            frame_data = camera.render_view(self.world)
            
            # Encode en base64
            frame_b64 = base64.b64encode(frame_data).decode('utf-8')
            
            # Message de frame
            message = json.dumps({
                "type": "camera_frame",
                "camera_id": camera.id,
                "width": camera.resolution[0],
                "height": camera.resolution[1],
                "frame": frame_b64,
                "timestamp": datetime.now().isoformat()
            })
            
            # Envoie aux abonnés
            subscribers = list(self.camera_subscribers.get(camera.id, set()))
            for ws in subscribers:
                try:
                    await ws.send(message)
                except:
                    self.camera_subscribers[camera.id].discard(ws)
            
            await asyncio.sleep(1/fps)

if __name__ == "__main__":
    server = MinecraftServer()
    asyncio.run(server.start())
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

class Cube:
    """Cube de base"""
    def __init__(self, position, block_type="grass"):
        self.position = tuple(position)
        self.block_type = block_type
        self.id = f"cube_{position[0]}_{position[1]}_{position[2]}"

class Player(Cube):
    """Cube représentant un joueur"""
    def __init__(self, position, player_id, name="Player"):
        super().__init__(position, "player")
        self.player_id = player_id
        self.name = name
        self.id = f"player_{player_id}"
    
    def update_position(self, new_position):
        """Met à jour la position du joueur"""
        self.position = tuple(new_position)

class CubeCamera:
    """Cube avec caméra intégrée"""
    def __init__(self, position, name="Camera", resolution=(240, 180)):
        self.id = f"cam_{datetime.now().timestamp()}"
        self.position = list(position)
        self.name = name
        self.rotation = [0, 0]  # yaw, pitch
        self.fov = 70
        self.resolution = resolution  # Résolution par défaut 320x240 pour balance qualité/performance
        
    def rotate(self, yaw_delta, pitch_delta):
        """Rotation de la caméra"""
        self.rotation[0] += yaw_delta
        self.rotation[1] = max(-90, min(90, self.rotation[1] + pitch_delta))
    
    def render_view(self, world, frame_count=0):
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
        self.players = {}  # {player_id: Player} to track players as blocks
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
    
    def add_player(self, player_id, position, name="Player"):
        """Ajoute un joueur au monde comme un bloc"""
        player = Player(position, player_id, name)
        self.players[player_id] = player
        return player
    
    def update_player_position(self, player_id, new_position):
        """Met à jour la position d'un joueur"""
        if player_id in self.players:
            self.players[player_id].update_position(new_position)
            return True
        return False
    
    def remove_player(self, player_id):
        """Supprime un joueur du monde"""
        if player_id in self.players:
            del self.players[player_id]
            return True
        return False
    
    def get_all_blocks(self):
        """Retourne tous les blocs (réguliers + joueurs) pour le ray-marching"""
        all_blocks = dict(self.blocks)
        # Ajoute les joueurs comme des blocs en utilisant leurs coordonnées entières
        for player in self.players.values():
            # Convertit la position flottante du joueur en coordonnées de bloc
            floored_pos = (int(math.floor(player.position[0])), 
                          int(math.floor(player.position[1])), 
                          int(math.floor(player.position[2])))
            all_blocks[floored_pos] = player
        return all_blocks
    
    def to_dict(self):
        """Sérialise le monde"""
        blocks_data = {}
        for pos, cube in self.blocks.items():
            key = f"{pos[0]},{pos[1]},{pos[2]}"
            blocks_data[key] = cube.block_type
        
        # Ajoute les joueurs comme des blocs
        for player in self.players.values():
            key = f"{player.position[0]},{player.position[1]},{player.position[2]}"
            blocks_data[key] = player.block_type
        
        return {
            "size": self.size,
            "blocks": blocks_data,
            "cameras": {cid: cam.to_dict() for cid, cam in self.cameras.items()},
            "players": {pid: {"position": list(p.position), "name": p.name} for pid, p in self.players.items()}
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
            elif msg_type == "place_block":
                await self.handle_place_block(websocket, data)
            elif msg_type == "destroy_block":
                await self.handle_destroy_block(websocket, data)
            elif msg_type == "player_position_update":
                await self.handle_player_position_update(websocket, data)
            elif msg_type == "get_player_positions":
                await self.handle_get_player_positions(websocket)
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
        fps = 2  # Réduit de 3 à 2 FPS pour améliorer les performances CPU
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
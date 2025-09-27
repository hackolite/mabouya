"""
Client Minecraft Jouable avec Création de Caméras
=================================================

Client 3D jouable avec Pyglet permettant de :
- Se déplacer dans le monde
- Placer/détruire des blocs
- Créer des cubes caméra (touche C)
- Voir la liste des caméras (touche L)

Contrôles:
- ZQSD : Déplacement
- Souris : Regarder
- Espace : Sauter
- Clic gauche : Détruire bloc
- Clic droit : Placer bloc
- C : Créer caméra à la position actuelle
- L : Lister les caméras
- Ctrl+W : Basculer wireframes (améliore performance)
- ESC : Libérer souris

Nécessite: pyglet, websockets

Usage:
    python minecraft_playable.py
"""

import pyglet
from pyglet.gl import *
from pyglet.gl import gluPerspective
from pyglet.window import key, mouse
import math
import asyncio
import websockets
import json
import threading
from collections import deque

# Constantes
TICKS_PER_SEC = 60
WALKING_SPEED = 5
FLYING_SPEED = 15
GRAVITY = 20.0
MAX_JUMP_HEIGHT = 1.0
JUMP_SPEED = math.sqrt(2 * GRAVITY * MAX_JUMP_HEIGHT)
TERMINAL_VELOCITY = 50
PLAYER_HEIGHT = 2

def cube_vertices(x, y, z, n):
    """Vertices d'un cube"""
    return [
        x-n,y+n,z-n, x-n,y+n,z+n, x+n,y+n,z+n, x+n,y+n,z-n,
        x-n,y-n,z-n, x+n,y-n,z-n, x+n,y-n,z+n, x-n,y-n,z+n,
        x-n,y-n,z-n, x-n,y-n,z+n, x-n,y+n,z+n, x-n,y+n,z-n,
        x+n,y-n,z+n, x+n,y-n,z-n, x+n,y+n,z-n, x+n,y+n,z+n,
        x-n,y-n,z+n, x+n,y-n,z+n, x+n,y+n,z+n, x-n,y+n,z+n,
        x+n,y-n,z-n, x-n,y-n,z-n, x-n,y+n,z-n, x+n,y+n,z-n,
    ]

def cube_edges(x, y, z, n):
    """Génère les arêtes d'un cube pour le wireframe"""
    # Les 8 sommets du cube
    vertices = [
        (x-n, y-n, z-n),  # 0: arrière-bas-gauche
        (x+n, y-n, z-n),  # 1: arrière-bas-droite  
        (x+n, y+n, z-n),  # 2: arrière-haut-droite
        (x-n, y+n, z-n),  # 3: arrière-haut-gauche
        (x-n, y-n, z+n),  # 4: avant-bas-gauche
        (x+n, y-n, z+n),  # 5: avant-bas-droite
        (x+n, y+n, z+n),  # 6: avant-haut-droite
        (x-n, y+n, z+n),  # 7: avant-haut-gauche
    ]
    
    # Les 12 arêtes du cube (connexions entre les sommets)
    edges = [
        # Face arrière (z-n)
        (0, 1), (1, 2), (2, 3), (3, 0),
        # Face avant (z+n)  
        (4, 5), (5, 6), (6, 7), (7, 4),
        # Connexions avant-arrière
        (0, 4), (1, 5), (2, 6), (3, 7)
    ]
    
    # Convertit en liste de coordonnées pour GL_LINES
    lines = []
    for start_idx, end_idx in edges:
        start = vertices[start_idx]
        end = vertices[end_idx]
        lines.extend([start[0], start[1], start[2], end[0], end[1], end[2]])
    
    return lines

def normalize(position):
    """Normalise position vers coordonnées bloc"""
    return tuple(int(round(x)) for x in position)

class NetworkClient:
    """Client réseau asynchrone"""
    def __init__(self, window, uri="ws://localhost:8765"):
        self.window = window
        self.uri = uri
        self.websocket = None
        self.connected = False
        self.loop = None
        self.cameras = {}
        
    def start(self):
        """Démarre le thread réseau"""
        thread = threading.Thread(target=self._run_loop, daemon=True)
        thread.start()
    
    def _run_loop(self):
        """Boucle asyncio dans un thread"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._connect())
    
    async def _connect(self):
        """Connexion au serveur"""
        try:
            # Configure la connexion WebSocket avec des paramètres de keepalive appropriés
            self.websocket = await websockets.connect(
                self.uri,
                ping_interval=20,  # Envoie un ping toutes les 20 secondes
                ping_timeout=10,   # Timeout de 10 secondes pour recevoir un pong
                close_timeout=10   # Timeout de 10 secondes pour fermer proprement
            )
            self.connected = True
            print("Connecté au serveur")
            
            # Reçoit le monde
            message = await self.websocket.recv()
            data = json.loads(message)
            
            if data["type"] == "world_state":
                world_data = data["world"]  # Capture by value
                pyglet.clock.schedule_once(
                    lambda dt, wd=world_data: self.window.load_world(wd), 
                    0
                )
            
            # Boucle de réception
            async for message in self.websocket:
                data = json.loads(message)
                if data["type"] == "camera_created":
                    camera = data["camera"]
                    self.cameras[camera["id"]] = camera
                    pyglet.clock.schedule_once(
                        lambda dt, c=camera: self.window.on_camera_created(c),
                        0
                    )
                elif data["type"] == "block_placed":
                    position = tuple(data["position"])
                    block_type = data["block_type"]
                    pyglet.clock.schedule_once(
                        lambda dt, pos=position, bt=block_type: self.window._add_block_local(pos, bt),
                        0
                    )
                elif data["type"] == "block_destroyed":
                    position = tuple(data["position"])
                    pyglet.clock.schedule_once(
                        lambda dt, pos=position: self.window._remove_block_local(pos),
                        0
                    )
                elif data["type"] == "player_joined":
                    player_id = data["player_id"]
                    position = tuple(data["position"])
                    pyglet.clock.schedule_once(
                        lambda dt, pid=player_id, pos=position: self.window._add_other_player(pid, pos),
                        0
                    )
                elif data["type"] == "player_left":
                    player_id = data["player_id"]
                    pyglet.clock.schedule_once(
                        lambda dt, pid=player_id: self.window._remove_other_player(pid),
                        0
                    )
                elif data["type"] == "player_position_changed":
                    player_id = data["player_id"]
                    position = tuple(data["position"])
                    pyglet.clock.schedule_once(
                        lambda dt, pid=player_id, pos=position: self.window._update_other_player_position(pid, pos),
                        0
                    )
        except websockets.exceptions.ConnectionClosed as e:
            print(f"Connexion fermée: {e}")
            self.connected = False
        except websockets.exceptions.InvalidMessage as e:
            print(f"Message WebSocket invalide: {e}")
            self.connected = False
        except Exception as e:
            print(f"Erreur réseau: {e}")
            self.connected = False
        finally:
            # Nettoyage de la connexion
            if self.websocket:
                try:
                    await self.websocket.close()
                except:
                    pass
                self.websocket = None
    
    def send_message(self, message):
        """Envoie un message"""
        if self.connected and self.websocket:
            asyncio.run_coroutine_threadsafe(
                self.websocket.send(json.dumps(message)),
                self.loop
            )

class MinecraftWindow(pyglet.window.Window):
    def __init__(self):
        super().__init__(width=800, height=600, caption='Minecraft avec Caméras', resizable=True)
        
        # État
        self.exclusive = False
        self.flying = False
        self.position = (0, 10, 0)
        self.rotation = (0, 0)
        self.strafe = [0, 0]
        self.dy = 0
        
        # Performance settings
        self.show_wireframes = True  # Toggle wireframes for performance
        self.wireframe_distance = 15  # Only show wireframes within this distance
        
        # Monde
        self.world = {}
        self.shown = {}
        self.batch = pyglet.graphics.Batch()
        self._shown = {}
        
        # Wireframes pour tous les cubes (contours noirs épais)
        self.wireframe_batch = pyglet.graphics.Batch()
        self._wireframes = {}  # Stocke les wireframes des blocs
        
        # Caméras (rendues comme cubes jaunes)
        self.cameras = {}
        self.camera_batch = pyglet.graphics.Batch()
        self._camera_cubes = {}
        self._camera_wireframes = {}  # Wireframes des caméras
        
        # Player cube (rendu comme cube bleu)
        self.player_batch = pyglet.graphics.Batch()
        self.player_cube = None
        self.player_wireframe = None  # Wireframe du joueur
        
        # Other players (rendered as colored cubes)
        self.other_players = {}  # {player_id: {"position": (x, y, z), "cube": cube_object, "wireframe": wireframe_object}}
        self.other_players_batch = pyglet.graphics.Batch()
        
        # Réseau
        self.network = NetworkClient(self)
        self.network.start()
        
        # Labels
        self.label = pyglet.text.Label(
            '', font_size=10, x=10, y=self.height - 10,
            anchor_x='left', anchor_y='top', color=(255, 255, 255, 255)
        )
        
        self.info_label = pyglet.text.Label(
            '', font_size=12, x=self.width//2, y=self.height - 30,
            anchor_x='center', anchor_y='top', color=(255, 255, 0, 255)
        )
        
        # Réticule
        self.reticle = None
        self.setup_crosshair()
        
        # Update loop
        pyglet.clock.schedule_interval(self.update, 1.0 / TICKS_PER_SEC)
        
        # Initialize player cube
        self._update_player_cube()
        
    def setup_crosshair(self):
        """Crée le réticule"""
        x, y = self.width // 2, self.height // 2
        n = 10
        self.reticle = pyglet.graphics.vertex_list(
            4,
            ('v2i', (x - n, y, x + n, y, x, y - n, x, y + n))
        )
    
    def load_world(self, world_data):
        """Charge le monde depuis le serveur"""
        print(f"Chargement monde: {len(world_data['blocks'])} blocs")
        
        for pos_str, block_type in world_data["blocks"].items():
            x, y, z = map(int, pos_str.split(','))
            # Skip player blocks as they'll be handled separately
            if block_type != "player":
                self._add_block_local((x, y, z), block_type)
        
        # Charge les caméras existantes
        for cam_id, cam_data in world_data.get("cameras", {}).items():
            self.cameras[cam_id] = cam_data
            self._add_camera_visual(cam_data)
        
        # Charge les joueurs existants (sauf soi-même)
        for player_id, player_data in world_data.get("players", {}).items():
            position = tuple(player_data["position"])
            self._add_other_player(player_id, position)
    
    def add_block(self, position, block_type):
        """Ajoute un bloc localement et envoie au serveur"""
        if position in self.world:
            return
        
        # Envoie la commande au serveur
        if hasattr(self, 'network') and self.network.connected:
            self.network.send_message({
                "type": "place_block",
                "position": list(position),
                "block_type": block_type
            })
        
        # Mise à jour locale pour un retour visuel immédiat
        self._add_block_local(position, block_type)
    
    def _add_block_local(self, position, block_type):
        """Ajoute un bloc localement seulement (pour rendu)"""
        if position in self.world:
            return
            
        self.world[position] = block_type
        
        # Rendu simple (tous en vert pour la démo)
        x, y, z = position
        vertices = cube_vertices(x, y, z, 0.5)
        
        # Couleur selon type
        if block_type == "grass":
            color = (34, 139, 34) * 24
        elif block_type == "stone":
            color = (128, 128, 128) * 24
        else:
            color = (139, 69, 19) * 24
        
        # Ajoute le cube solide
        self._shown[position] = self.batch.add(
            24, GL_QUADS, None,
            ('v3f/static', vertices),
            ('c3B/static', color)
        )
        
        # Ajoute le wireframe seulement si les wireframes sont activés
        # et si le bloc est proche du joueur pour de meilleures performances
        if self.show_wireframes:
            player_x, player_y, player_z = self.position
            distance = math.sqrt((x - player_x)**2 + (y - player_y)**2 + (z - player_z)**2)
            
            if distance <= self.wireframe_distance:
                edges = cube_edges(x, y, z, 0.5)
                edge_count = len(edges) // 3  # 3 coordonnées par vertex
                black_color = (0, 0, 0) * edge_count  # Noir pour toutes les arêtes
                
                self._wireframes[position] = self.wireframe_batch.add(
                    edge_count, GL_LINES, None,
                    ('v3f/static', edges),
                    ('c3B/static', black_color)
                )
        
        self.shown[position] = block_type
    
    def remove_block(self, position):
        """Retire un bloc localement et envoie au serveur"""
        if position not in self.world:
            return
            
        # Envoie la commande au serveur
        if hasattr(self, 'network') and self.network.connected:
            self.network.send_message({
                "type": "destroy_block", 
                "position": list(position)
            })
        
        # Mise à jour locale pour un retour visuel immédiat
        self._remove_block_local(position)
    
    def _remove_block_local(self, position):
        """Retire un bloc localement seulement (pour rendu)"""
        if position in self.world:
            del self.world[position]
            if position in self._shown:
                self._shown[position].delete()
                del self._shown[position]
            if position in self._wireframes and self._wireframes[position]:
                self._wireframes[position].delete()
                del self._wireframes[position]
            if position in self.shown:
                del self.shown[position]
    
    def _add_camera_visual(self, camera):
        """Ajoute un cube jaune pour visualiser la caméra"""
        cam_id = camera["id"]
        x, y, z = camera["position"]
        
        vertices = cube_vertices(x, y, z, 0.6)
        color = (255, 255, 0) * 24  # Jaune
        
        # Ajoute le cube de caméra
        self._camera_cubes[cam_id] = self.camera_batch.add(
            24, GL_QUADS, None,
            ('v3f/static', vertices),
            ('c3B/static', color)
        )
        
        # Ajoute le wireframe seulement si activé
        if self.show_wireframes:
            edges = cube_edges(x, y, z, 0.6)
            edge_count = len(edges) // 3
            black_color = (0, 0, 0) * edge_count
            
            self._camera_wireframes[cam_id] = self.wireframe_batch.add(
                edge_count, GL_LINES, None,
                ('v3f/static', edges),
                ('c3B/static', black_color)
            )
    
    def _update_player_cube(self):
        """Met à jour ou crée le cube du joueur"""
        # Supprime l'ancien cube s'il existe
        if self.player_cube:
            self.player_cube.delete()
        if self.player_wireframe:
            self.player_wireframe.delete()
        
        # Position du joueur
        x, y, z = self.position
        
        # Crée un nouveau cube à la position du joueur
        vertices = cube_vertices(x, y - 1, z, 0.4)  # Légèrement plus petit et décalé vers le bas
        color = (0, 150, 255) * 24  # Bleu pour le joueur
        
        self.player_cube = self.player_batch.add(
            24, GL_QUADS, None,
            ('v3f/static', vertices),
            ('c3B/static', color)
        )
        
        # Ajoute le wireframe seulement si activé
        if self.show_wireframes:
            edges = cube_edges(x, y - 1, z, 0.4)
            edge_count = len(edges) // 3
            black_color = (0, 0, 0) * edge_count
            
            self.player_wireframe = self.wireframe_batch.add(
                edge_count, GL_LINES, None,
                ('v3f/static', edges),
                ('c3B/static', black_color)
            )
    
    def on_camera_created(self, camera):
        """Callback caméra créée"""
        self.cameras[camera["id"]] = camera
        self._add_camera_visual(camera)
        self.show_message(f"Caméra créée: {camera['name']}")
    
    def _add_other_player(self, player_id, position):
        """Ajoute un autre joueur au monde"""
        x, y, z = position
        vertices = cube_vertices(x, y - 1, z, 0.4)  # Même taille que le joueur local
        color = (255, 100, 100) * 24  # Rouge pour les autres joueurs
        
        cube = self.other_players_batch.add(
            24, GL_QUADS, None,
            ('v3f/static', vertices),
            ('c3B/static', color)
        )
        
        # Ajoute le wireframe seulement si activé
        wireframe = None
        if self.show_wireframes:
            edges = cube_edges(x, y - 1, z, 0.4)
            edge_count = len(edges) // 3
            black_color = (0, 0, 0) * edge_count
            
            wireframe = self.wireframe_batch.add(
                edge_count, GL_LINES, None,
                ('v3f/static', edges),
                ('c3B/static', black_color)
            )
        
        self.other_players[player_id] = {"position": position, "cube": cube, "wireframe": wireframe}
        print(f"👤 Joueur {player_id} ajouté à {position}")
    
    def _remove_other_player(self, player_id):
        """Supprime un autre joueur du monde"""
        if player_id in self.other_players:
            self.other_players[player_id]["cube"].delete()
            if "wireframe" in self.other_players[player_id]:
                self.other_players[player_id]["wireframe"].delete()
            del self.other_players[player_id]
            print(f"👤 Joueur {player_id} supprimé")
    
    def _update_other_player_position(self, player_id, new_position):
        """Met à jour la position d'un autre joueur"""
        if player_id in self.other_players:
            # Supprime l'ancien cube et wireframe
            self.other_players[player_id]["cube"].delete()
            if "wireframe" in self.other_players[player_id]:
                self.other_players[player_id]["wireframe"].delete()
            
            # Crée un nouveau cube à la nouvelle position
            x, y, z = new_position
            vertices = cube_vertices(x, y - 1, z, 0.4)
            color = (255, 100, 100) * 24  # Rouge pour les autres joueurs
            
            cube = self.other_players_batch.add(
                24, GL_QUADS, None,
                ('v3f/static', vertices),
                ('c3B/static', color)
            )
            
            # Ajoute le nouveau wireframe seulement si activé
            wireframe = None
            if self.show_wireframes:
                edges = cube_edges(x, y - 1, z, 0.4)
                edge_count = len(edges) // 3
                black_color = (0, 0, 0) * edge_count
                
                wireframe = self.wireframe_batch.add(
                    edge_count, GL_LINES, None,
                    ('v3f/static', edges),
                    ('c3B/static', black_color)
                )
            
            self.other_players[player_id] = {"position": new_position, "cube": cube, "wireframe": wireframe}
    
    def show_message(self, text, duration=3.0):
        """Affiche un message temporaire"""
        self.info_label.text = text
        pyglet.clock.schedule_once(lambda dt: setattr(self.info_label, 'text', ''), duration)
    
    def toggle_wireframes(self):
        """Active/désactive les wireframes pour améliorer les performances"""
        self.show_wireframes = not self.show_wireframes
        status = "activés" if self.show_wireframes else "désactivés"
        self.show_message(f"Wireframes {status} (Ctrl+W pour basculer)")
        
        # Si on désactive les wireframes, on supprime tous les wireframes existants
        if not self.show_wireframes:
            # Supprime les wireframes des blocs
            for wireframe in self._wireframes.values():
                if wireframe:
                    wireframe.delete()
            self._wireframes.clear()
            
            # Supprime les wireframes des caméras
            for wireframe in self._camera_wireframes.values():
                if wireframe:
                    wireframe.delete()
            self._camera_wireframes.clear()
            
            # Supprime le wireframe du joueur
            if self.player_wireframe:
                self.player_wireframe.delete()
                self.player_wireframe = None
            
            # Supprime les wireframes des autres joueurs
            for player_data in self.other_players.values():
                if player_data.get("wireframe"):
                    player_data["wireframe"].delete()
                    player_data["wireframe"] = None
    
    def create_camera_at_position(self):
        """Crée une caméra à la position du joueur"""
        if not self.network.connected:
            self.show_message("Non connecté au serveur!")
            return
        
        # Position devant le joueur
        x, y, z = self.position
        dx, _, dz = self.get_sight_vector()
        
        cam_pos = [x + dx * 3, y, z + dz * 3]
        
        self.network.send_message({
            "type": "create_camera",
            "position": cam_pos,
            "name": f"Camera_{len(self.cameras)+1}"
        })
        
        self.show_message("Création caméra...")
    
    def list_cameras(self):
        """Affiche les caméras"""
        if not self.cameras:
            self.show_message("Aucune caméra")
            return
        
        print("\nCaméras disponibles:")
        for cam_id, cam in self.cameras.items():
            print(f"  - {cam['name']} ({cam_id[:8]}...)")
            print(f"    Position: {cam['position']}")
        
        self.show_message(f"{len(self.cameras)} caméra(s) - voir console")
    
    def hit_test(self, position, vector, max_distance=8):
        """Test de collision rayon"""
        m = 8
        x, y, z = position
        dx, dy, dz = vector
        previous = None
        
        for _ in range(max_distance * m):
            key = normalize((x, y, z))
            if key != previous and key in self.world:
                return key, previous
            previous = key
            x, y, z = x + dx/m, y + dy/m, z + dz/m
        
        return None, None
    
    def get_sight_vector(self):
        """Vecteur de visée"""
        x, y = self.rotation
        m = math.cos(math.radians(y))
        dy = math.sin(math.radians(y))
        dx = math.cos(math.radians(x - 90)) * m
        dz = math.sin(math.radians(x - 90)) * m
        return (dx, dy, dz)
    
    def get_motion_vector(self):
        """Vecteur de mouvement"""
        if any(self.strafe):
            x, y = self.rotation
            strafe = math.degrees(math.atan2(*self.strafe))
            y_angle = math.radians(y)
            x_angle = math.radians(x + strafe)
            
            if self.flying:
                m = math.cos(y_angle)
                dy = math.sin(y_angle)
                if self.strafe[1]:
                    dy = 0.0
                    m = 1
                if self.strafe[0] > 0:
                    dy *= -1
                dx = math.cos(x_angle) * m
                dz = math.sin(x_angle) * m
            else:
                dy = 0.0
                dx = math.cos(x_angle)
                dz = math.sin(x_angle)
        else:
            dx = dy = dz = 0.0
        
        return (dx, dy, dz)
    
    def collide(self, position, height):
        """Détection collision simple"""
        pad = 0.25
        p = list(position)
        np_pos = normalize(position)
        
        for face in [(0, 1, 0), (0, -1, 0), (-1, 0, 0), (1, 0, 0), (0, 0, 1), (0, 0, -1)]:
            for i in range(3):
                if not face[i]:
                    continue
                
                d = (p[i] - np_pos[i]) * face[i]
                if d < pad:
                    continue
                
                for dy in range(height):
                    op = list(np_pos)
                    op[1] -= dy
                    op[i] += face[i]
                    
                    if tuple(op) in self.world:
                        p[i] -= (d - pad) * face[i]
                        if face == (0, -1, 0) or face == (0, 1, 0):
                            self.dy = 0
                        break
        
        return tuple(p)
    
    def update(self, dt):
        """Mise à jour physique"""
        speed = FLYING_SPEED if self.flying else WALKING_SPEED
        d = dt * speed
        dx, dy, dz = self.get_motion_vector()
        dx, dy, dz = dx * d, dy * d, dz * d
        
        if not self.flying:
            self.dy -= dt * GRAVITY
            self.dy = max(self.dy, -TERMINAL_VELOCITY)
            dy += self.dy * dt
        
        # Store old position to check if it changed
        old_position = self.position
        
        x, y, z = self.position
        x, y, z = self.collide((x + dx, y + dy, z + dz), PLAYER_HEIGHT)
        self.position = (x, y, z)
        
        # Update player cube if position changed
        if old_position != self.position:
            self._update_player_cube()
            # Send position update to server
            if hasattr(self, 'network') and self.network.connected:
                self.network.send_message({
                    "type": "player_position_update",
                    "position": list(self.position)
                })
        
        # Mise à jour labels
        x, y, z = self.position
        wireframe_status = "ON" if self.show_wireframes else "OFF"
        self.label.text = f'Position: ({x:.1f}, {y:.1f}, {z:.1f})\nCaméras: {len(self.cameras)} | Joueurs: {len(self.other_players)} | Wireframes: {wireframe_status}\nC: Créer caméra | L: Lister | Ctrl+W: Toggle wireframes'
    
    def on_mouse_press(self, x, y, button, modifiers):
        """Gestion souris"""
        if self.exclusive:
            vector = self.get_sight_vector()
            block, previous = self.hit_test(self.position, vector)
            
            if button == mouse.LEFT and block:
                self.remove_block(block)
            elif button == mouse.RIGHT and previous:
                self.add_block(previous, "stone")
        else:
            self.set_exclusive_mouse(True)
    
    def on_mouse_motion(self, x, y, dx, dy):
        """Mouvement souris"""
        if self.exclusive:
            m = 0.15
            x, y = self.rotation
            x, y = x + dx * m, y + dy * m
            y = max(-90, min(90, y))
            self.rotation = (x, y)
    
    def on_key_press(self, symbol, modifiers):
        """Touches pressées"""
        if symbol == key.Z:
            self.strafe[0] -= 1
        elif symbol == key.S:
            self.strafe[0] += 1
        elif symbol == key.Q:
            self.strafe[1] -= 1
        elif symbol == key.D:
            self.strafe[1] += 1
        elif symbol == key.SPACE:
            if not self.flying:
                self.dy = JUMP_SPEED
        elif symbol == key.TAB:
            self.flying = not self.flying
        elif symbol == key.ESCAPE:
            self.set_exclusive_mouse(False)
        elif symbol == key.C:
            # Créer caméra
            self.create_camera_at_position()
        elif symbol == key.L:
            # Lister caméras
            self.list_cameras()
        elif symbol == key.W and modifiers & key.MOD_CTRL:
            # Toggle wireframes avec Ctrl+W
            self.toggle_wireframes()
    
    def on_key_release(self, symbol, modifiers):
        """Touches relâchées"""
        if symbol == key.Z:
            self.strafe[0] += 1
        elif symbol == key.S:
            self.strafe[0] -= 1
        elif symbol == key.Q:
            self.strafe[1] += 1
        elif symbol == key.D:
            self.strafe[1] -= 1
    
    def set_exclusive_mouse(self, exclusive):
        """Capture souris"""
        super().set_exclusive_mouse(exclusive)
        self.exclusive = exclusive
    
    def on_resize(self, width, height):
        """Redimensionnement"""
        self.label.y = height - 10
        self.info_label.x = width // 2
        self.info_label.y = height - 30
        
        if self.reticle:
            self.reticle.delete()
        self.setup_crosshair()
    
    def set_3d(self):
        """Mode 3D"""
        width, height = self.get_size()
        glEnable(GL_DEPTH_TEST)
        glViewport(0, 0, width, height)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(65.0, width / float(height), 0.1, 60.0)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        
        x, y = self.rotation
        glRotatef(x, 0, 1, 0)
        glRotatef(-y, math.cos(math.radians(x)), 0, math.sin(math.radians(x)))
        x, y, z = self.position
        glTranslatef(-x, -y, -z)
    
    def set_2d(self):
        """Mode 2D"""
        width, height = self.get_size()
        glDisable(GL_DEPTH_TEST)
        glViewport(0, 0, width, height)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(0, width, 0, height, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
    
    def on_draw(self):
        """Rendu"""
        self.clear()
        
        # 3D
        self.set_3d()
        glColor3d(1, 1, 1)
        
        # Dessine les cubes solides
        self.batch.draw()
        self.camera_batch.draw()
        self.player_batch.draw()
        self.other_players_batch.draw()  # Dessine les autres joueurs
        
        # Dessine les wireframes seulement s'ils sont activés
        if self.show_wireframes:
            glLineWidth(2.0)  # Lignes épaisses
            glColor3d(0, 0, 0)  # Noir
            self.wireframe_batch.draw()
            glLineWidth(1.0)  # Restore default line width
        
        # 2D
        self.set_2d()
        self.label.draw()
        self.info_label.draw()
        glColor3d(0, 0, 0)
        self.reticle.draw(GL_LINES)

def setup():
    """Setup OpenGL"""
    glClearColor(0.5, 0.69, 1.0, 1)
    glEnable(GL_CULL_FACE)

if __name__ == '__main__':
    window = MinecraftWindow()
    window.set_exclusive_mouse(True)
    setup()
    pyglet.app.run()
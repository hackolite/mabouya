"""
Viewer Caméra Minecraft
========================

Visualise le flux vidéo d'une caméra en temps réel.
Nécessite: opencv-python, pillow

Installation:
    pip install opencv-python pillow websockets

Usage:
    python camera_viewer.py <camera_id>
    python camera_viewer.py  # Demande l'ID interactivement
"""

import asyncio
import websockets
import json
import base64
import sys
import os
from io import BytesIO
import numpy as np
import argparse

try:
    import cv2
    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False
    print("⚠️  OpenCV non disponible, utilisation de PIL")

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# Détecte si on est dans un environnement sans display
HEADLESS = os.environ.get('DISPLAY') is None or os.environ.get('HEADLESS') == '1'

class CameraViewer:
    def __init__(self, camera_id, uri="ws://localhost:8765", headless=False, save_frames=False, 
                 window_size=(800, 600), fullscreen=False):
        self.camera_id = camera_id
        self.uri = uri
        self.websocket = None
        self.running = False
        self.frame_count = 0
        self.headless = headless or HEADLESS
        self.save_frames = save_frames
        self.use_opencv = HAS_OPENCV and not self.headless
        self.window_size = window_size  # Taille de fenêtre d'affichage
        self.fullscreen = fullscreen  # Mode plein écran
        
        if self.headless:
            print("🖥️  Mode sans affichage activé")
        
    async def connect(self):
        """Connexion au serveur"""
        try:
            # Configure la connexion WebSocket avec des paramètres de keepalive appropriés
            self.websocket = await websockets.connect(
                self.uri,
                ping_interval=20,  # Envoie un ping toutes les 20 secondes  
                ping_timeout=10,   # Timeout de 10 secondes pour recevoir un pong
                close_timeout=10   # Timeout de 10 secondes pour fermer proprement
            )
            print(f"Connecté à {self.uri}")
            
            # Ignore les messages initiaux (world_state et player_joined)
            await self.websocket.recv()  # world_state
            await self.websocket.recv()  # player_joined
            
            # S'abonne à la caméra
            await self.websocket.send(json.dumps({
                "type": "subscribe_camera",
                "camera_id": self.camera_id
            }))
            
            response = await self.websocket.recv()
            data = json.loads(response)
            
            if data["type"] == "subscribed":
                print(f"✅ Abonné à la caméra {self.camera_id}")
                if self.headless:
                    print("Mode sans affichage - Appuyez sur Ctrl+C pour quitter")
                else:
                    print("Contrôles:")
                    print("  'q' - Quitter")
                    print("  's' - Sauvegarder la frame actuelle")
                    print("  'f' - Basculer plein écran/fenêtré")
                    print("  'r' - Réinitialiser la taille de fenêtre")
                self.running = True
            else:
                error_msg = data.get('message', "Impossible de s'abonner")
                print(f"❌ Erreur: {error_msg}")
                return False
            
            return True
            
        except websockets.exceptions.ConnectionClosed as e:
            print(f"❌ Connexion fermée: {e}")
            return False
        except Exception as e:
            print(f"❌ Erreur de connexion: {e}")
            return False
    
    def decode_frame(self, frame_b64, width, height, format_type="raw"):
        """Décode une frame base64 en image"""
        try:
            # Décode base64
            frame_bytes = base64.b64decode(frame_b64)
            
            if format_type == "jpeg":
                # Décompresse le JPEG
                try:
                    from PIL import Image
                    import io
                    
                    # Ouvre l'image JPEG depuis les bytes
                    img = Image.open(io.BytesIO(frame_bytes))
                    
                    # Convertit en array numpy
                    frame_array = np.array(img)
                    
                    return frame_array
                    
                except ImportError:
                    print("⚠️  PIL non disponible pour décompresser JPEG")
                    return None
                except Exception as e:
                    print(f"⚠️  Erreur décompression JPEG: {e}")
                    return None
            else:
                # Format brut (raw RGB)
                try:
                    frame_array = np.frombuffer(frame_bytes, dtype=np.uint8)
                    frame_array = frame_array.reshape((height, width, 3))
                    
                    return frame_array
                except Exception as e:
                    print(f"⚠️  Erreur décodage frame brute: {e}")
                    return None
                    
        except Exception as e:
            print(f"⚠️  Erreur décodage base64: {e}")
            return None
    
    def scale_frame_for_display(self, frame):
        """Redimensionne l'image pour un meilleur affichage si nécessaire"""
        height, width = frame.shape[:2]
        
        # Si l'image est très petite, on l'agrandit avec une interpolation lisse
        if width < 400 or height < 300:
            # Calcule un facteur d'échelle pour avoir au moins 400x300
            scale_x = max(1, 400 // width)
            scale_y = max(1, 300 // height)
            scale = min(scale_x, scale_y)
            
            new_width = width * scale
            new_height = height * scale
            
            # Utilise l'interpolation cubique pour un rendu plus lisse
            return cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
        
        return frame
    
    def toggle_fullscreen(self):
        """Bascule entre mode fenêtré et plein écran"""
        if not self.use_opencv:
            return
            
        try:
            self.fullscreen = not self.fullscreen
            if self.fullscreen:
                cv2.setWindowProperty(f"Camera {self.camera_id}", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
                print("📺 Mode plein écran activé")
            else:
                cv2.setWindowProperty(f"Camera {self.camera_id}", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_NORMAL)
                cv2.resizeWindow(f"Camera {self.camera_id}", self.window_size[0], self.window_size[1])
                print("🖼️  Mode fenêtré activé")
        except Exception as e:
            print(f"⚠️  Erreur lors du basculement plein écran: {e}")
    
    async def stream_loop(self):
        """Boucle de réception et affichage"""
        if self.use_opencv:
            try:
                # Crée une fenêtre redimensionnable avec une taille par défaut plus grande
                cv2.namedWindow(f"Camera {self.camera_id}", cv2.WINDOW_NORMAL)
                
                # Définit la taille initiale de la fenêtre
                cv2.resizeWindow(f"Camera {self.camera_id}", self.window_size[0], self.window_size[1])
                
                # Mode plein écran si demandé
                if self.fullscreen:
                    cv2.setWindowProperty(f"Camera {self.camera_id}", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
                
                print(f"🖼️  Fenêtre d'affichage créée: {self.window_size[0]}x{self.window_size[1]}")
                if self.fullscreen:
                    print("📺 Mode plein écran activé")
                    
            except Exception as e:
                print(f"⚠️  Impossible d'ouvrir la fenêtre d'affichage: {e}")
                print("🖥️  Basculement en mode sans affichage")
                self.headless = True
                self.use_opencv = False
        
        try:
            while self.running:
                # Reçoit une frame
                message = await asyncio.wait_for(self.websocket.recv(), timeout=10.0)
                data = json.loads(message)
                
                if data["type"] == "camera_frame":
                    self.frame_count += 1
                    
                    if self.headless:
                        # Mode sans affichage - juste les stats
                        if self.frame_count == 1:
                            print(f"📺 Première frame reçue (taille: {data['width']}x{data['height']})")
                        elif self.frame_count % 10 == 0:
                            print(f"📊 {self.frame_count} frames reçues")
                        
                        # Sauvegarde optionnelle
                        if self.save_frames and (self.frame_count % 20 == 0):  # Toutes les 20 frames
                            format_type = data.get("format", "raw")
                            frame = self.decode_frame(
                                data["frame"],
                                data["width"],
                                data["height"],
                                format_type
                            )
                            if frame is not None:
                                filename = f"camera_{self.camera_id[:8]}_{self.frame_count}.png"
                                if HAS_PIL:
                                    img = Image.fromarray(frame)
                                    img.save(filename)
                                    print(f"💾 Frame sauvegardée: {filename}")
                    else:
                        # Mode avec affichage
                        format_type = data.get("format", "raw")
                        frame = self.decode_frame(
                            data["frame"],
                            data["width"],
                            data["height"],
                            format_type
                        )
                        
                        if frame is None:
                            continue  # Skip cette frame si décodage échoué
                        
                        # Affiche avec OpenCV ou PIL
                        if self.use_opencv:
                            try:
                                # OpenCV utilise BGR, on convertit
                                frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                                
                                # Ajoute infos sur l'image
                                cv2.putText(
                                    frame_bgr,
                                    f"Frame: {self.frame_count}",
                                    (10, 30),
                                    cv2.FONT_HERSHEY_SIMPLEX,
                                    0.7,
                                    (0, 255, 0),
                                    2
                                )
                                
                                cv2.putText(
                                    frame_bgr,
                                    f"Camera: {self.camera_id[:8]}...",
                                    (10, 60),
                                    cv2.FONT_HERSHEY_SIMPLEX,
                                    0.5,
                                    (255, 255, 255),
                                    1
                                )
                                
                                # Affiche avec une mise à l'échelle adaptative
                                display_frame = self.scale_frame_for_display(frame_bgr)
                                cv2.imshow(f"Camera {self.camera_id}", display_frame)
                                
                                # Gestion des touches
                                key = cv2.waitKey(1) & 0xFF
                                if key == ord('q'):
                                    self.running = False
                                elif key == ord('s'):
                                    filename = f"camera_{self.camera_id}_{self.frame_count}.jpg"
                                    cv2.imwrite(filename, frame_bgr)
                                    print(f"💾 Frame sauvegardée: {filename}")
                                elif key == ord('f'):  # Basculer plein écran
                                    self.toggle_fullscreen()
                                elif key == ord('r'):  # Réinitialiser la taille de fenêtre
                                    cv2.resizeWindow(f"Camera {self.camera_id}", self.window_size[0], self.window_size[1])
                                    print(f"🖼️  Taille de fenêtre réinitialisée: {self.window_size[0]}x{self.window_size[1]}")
                                    
                            except Exception as e:
                                print(f"⚠️  Erreur affichage OpenCV: {e}")
                                print("🖥️  Basculement en mode sans affichage")
                                self.headless = True
                                self.use_opencv = False
                        
                        else:
                            # Affichage PIL (moins interactif)
                            if self.frame_count % 10 == 0:  # Affiche toutes les 10 frames
                                try:
                                    img = Image.fromarray(frame)
                                    img.show(title=f"Camera {self.camera_id} - Frame {self.frame_count}")
                                except Exception as e:
                                    print(f"⚠️  Impossible d'afficher l'image: {e}")
                                    print("🖥️  Basculement en mode sans affichage")
                                    self.headless = True
                        
                        # Stats toutes les 30 frames
                        if self.frame_count % 30 == 0:
                            print(f"📊 {self.frame_count} frames reçues")
        
        except asyncio.TimeoutError:
            print("⏱️  Timeout - Pas de frames reçues dans les 10 secondes")
            print("💡 Vérifiez que le serveur est démarré et que la caméra existe")
        except websockets.exceptions.ConnectionClosed as e:
            print(f"📡 Connexion fermée par le serveur: {e}")
        except websockets.exceptions.InvalidMessage as e:
            print(f"📡 Message WebSocket invalide: {e}")
        except KeyboardInterrupt:
            print("\n⏹️  Arrêté par l'utilisateur")
        except Exception as e:
            print(f"❌ Erreur lors de la réception: {e}")
            import traceback
            traceback.print_exc()
        finally:
            if self.use_opencv:
                try:
                    cv2.destroyAllWindows()
                except:
                    pass
    
    async def start(self):
        """Démarre le viewer"""
        try:
            if await self.connect():
                await self.stream_loop()
        finally:
            # Ferme proprement la connexion WebSocket
            if self.websocket:
                try:
                    await self.websocket.close()
                except:
                    pass
                self.websocket = None

async def list_cameras(uri="ws://localhost:8765"):
    """Liste les caméras disponibles"""
    websocket = None
    try:
        # Configure la connexion WebSocket avec des paramètres de keepalive appropriés
        websocket = await websockets.connect(
            uri,
            ping_interval=20,  # Envoie un ping toutes les 20 secondes  
            ping_timeout=10,   # Timeout de 10 secondes pour recevoir un pong
            close_timeout=10   # Timeout de 10 secondes pour fermer proprement
        )
        
        # Ignore les messages initiaux (world_state et player_joined)
        await websocket.recv()  # world_state
        await websocket.recv()  # player_joined
        
        # Demande la liste
        await websocket.send(json.dumps({"type": "get_cameras"}))
        response = await websocket.recv()
        data = json.loads(response)
        
        if data["type"] == "cameras_list":
            cameras = data["cameras"]
            if cameras:
                print("\n📹 Caméras disponibles:")
                for cam_id, cam_data in cameras.items():
                    print(f"   - {cam_data['name']}")
                    print(f"     ID: {cam_id}")
                    print(f"     Position: {cam_data['position']}")
                    print()
                return list(cameras.keys())
            else:
                print("❌ Aucune caméra disponible")
                return []
        else:
            print("❌ Erreur lors de la récupération des caméras")
            return []
            
    except Exception as e:
        print(f"❌ Erreur lors de la connexion: {e}")
        return []
    finally:
        if websocket:
            try:
                await websocket.close()
            except:
                pass

async def main():
    """Point d'entrée principal"""
    parser = argparse.ArgumentParser(description='🎥 VIEWER CAMÉRA MINECRAFT')
    parser.add_argument('camera_id', nargs='?', help='ID de la caméra à visualiser')
    parser.add_argument('--headless', action='store_true', help='Mode sans affichage')
    parser.add_argument('--save-frames', action='store_true', help='Sauvegarde les frames périodiquement')
    parser.add_argument('--uri', default='ws://localhost:8765', help='URI du serveur WebSocket')
    parser.add_argument('--window-size', default='800x600', help='Taille de la fenêtre d\'affichage (ex: 1024x768)')
    parser.add_argument('--fullscreen', action='store_true', help='Démarre en mode plein écran')
    
    args = parser.parse_args()
    
    print("🎥 VIEWER CAMÉRA MINECRAFT")
    print("=" * 50)
    
    # Parse window size
    try:
        window_width, window_height = map(int, args.window_size.split('x'))
        window_size = (window_width, window_height)
    except ValueError:
        print(f"⚠️  Taille de fenêtre invalide: {args.window_size}, utilisation de 800x600")
        window_size = (800, 600)
    
    camera_id = args.camera_id
    
    # Récupère l'ID de la caméra
    if not camera_id:
        # Liste les caméras disponibles
        cameras = await list_cameras(args.uri)
        
        if not cameras:
            print("\n💡 Créez d'abord une caméra avec minecraft_client.py")
            return
        
        # Demande à l'utilisateur
        if len(cameras) == 1:
            camera_id = cameras[0]
            print(f"📷 Utilisation de la seule caméra disponible: {camera_id}")
        else:
            print("Entrez l'ID de la caméra à visualiser:")
            camera_id = input("> ").strip()
    
    if not camera_id:
        print("❌ Aucune caméra sélectionnée")
        return
    
    # Démarre le viewer
    viewer = CameraViewer(
        camera_id, 
        uri=args.uri, 
        headless=args.headless, 
        save_frames=args.save_frames,
        window_size=window_size,
        fullscreen=args.fullscreen
    )
    await viewer.start()

if __name__ == "__main__":
    if not (HAS_OPENCV or HAS_PIL):
        print("❌ OpenCV ou PIL requis pour l'affichage:")
        print("   pip install opencv-python")
        print("   pip install pillow")
        if not HEADLESS:
            sys.exit(1)
        print("🖥️  Mode sans affichage disponible avec --headless")
    
    asyncio.run(main())

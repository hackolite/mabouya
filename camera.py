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
    def __init__(self, camera_id, uri="ws://localhost:8765", headless=False, save_frames=False):
        self.camera_id = camera_id
        self.uri = uri
        self.websocket = None
        self.running = False
        self.frame_count = 0
        self.headless = headless or HEADLESS
        self.save_frames = save_frames
        self.use_opencv = HAS_OPENCV and not self.headless
        
        if self.headless:
            print("🖥️  Mode sans affichage activé")
        
    async def connect(self):
        """Connexion au serveur"""
        self.websocket = await websockets.connect(self.uri)
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
                print("Appuyez sur 'q' pour quitter, 's' pour sauvegarder une frame")
            self.running = True
        else:
            error_msg = data.get('message', "Impossible de s'abonner")
            print(f"❌ Erreur: {error_msg}")
            return False
        
        return True
    
    def decode_frame(self, frame_b64, width, height):
        """Décode une frame base64 en image"""
        # Décode base64
        frame_bytes = base64.b64decode(frame_b64)
        
        # Convertit en array numpy
        frame_array = np.frombuffer(frame_bytes, dtype=np.uint8)
        frame_array = frame_array.reshape((height, width, 3))
        
        return frame_array
    
    async def stream_loop(self):
        """Boucle de réception et affichage"""
        if self.use_opencv:
            try:
                cv2.namedWindow(f"Camera {self.camera_id}", cv2.WINDOW_NORMAL)
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
                            frame = self.decode_frame(
                                data["frame"],
                                data["width"],
                                data["height"]
                            )
                            filename = f"camera_{self.camera_id[:8]}_{self.frame_count}.png"
                            if HAS_PIL:
                                img = Image.fromarray(frame)
                                img.save(filename)
                                print(f"💾 Frame sauvegardée: {filename}")
                    else:
                        # Mode avec affichage
                        frame = self.decode_frame(
                            data["frame"],
                            data["width"],
                            data["height"]
                        )
                        
                        # Affiche avec OpenCV ou PIL
                        if self.use_opencv:
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
                            
                            # Affiche
                            cv2.imshow(f"Camera {self.camera_id}", frame_bgr)
                            
                            # Gestion des touches
                            key = cv2.waitKey(1) & 0xFF
                            if key == ord('q'):
                                self.running = False
                            elif key == ord('s'):
                                filename = f"camera_{self.camera_id}_{self.frame_count}.jpg"
                                cv2.imwrite(filename, frame_bgr)
                                print(f"💾 Frame sauvegardée: {filename}")
                        
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
        if await self.connect():
            await self.stream_loop()
        
        if self.websocket:
            await self.websocket.close()

async def list_cameras(uri="ws://localhost:8765"):
    """Liste les caméras disponibles"""
    websocket = await websockets.connect(uri)
    
    # Ignore les messages initiaux (world_state et player_joined)
    await websocket.recv()  # world_state
    await websocket.recv()  # player_joined
    
    # Demande la liste
    await websocket.send(json.dumps({"type": "get_cameras"}))
    response = await websocket.recv()
    data = json.loads(response)
    
    await websocket.close()
    
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
    
    return []

async def main():
    """Point d'entrée principal"""
    parser = argparse.ArgumentParser(description='🎥 VIEWER CAMÉRA MINECRAFT')
    parser.add_argument('camera_id', nargs='?', help='ID de la caméra à visualiser')
    parser.add_argument('--headless', action='store_true', help='Mode sans affichage')
    parser.add_argument('--save-frames', action='store_true', help='Sauvegarde les frames périodiquement')
    parser.add_argument('--uri', default='ws://localhost:8765', help='URI du serveur WebSocket')
    
    args = parser.parse_args()
    
    print("🎥 VIEWER CAMÉRA MINECRAFT")
    print("=" * 50)
    
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
        save_frames=args.save_frames
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

#!/usr/bin/env python3
"""
Exemple d'utilisation de la nouvelle architecture de cubes
=========================================================

Ce script démontre comment utiliser les nouvelles fonctionnalités:
- Création de cubes caméra avec streaming
- Création d'agents IA avec comportements
- Déplacement et contrôle des cubes via API
- Gestion des endpoints WebSocket dédiés

Usage:
    python3 example_cube_usage.py
"""

import asyncio
import websockets
import json
import time

class CubeExampleClient:
    def __init__(self, uri="ws://localhost:8765"):
        self.uri = uri
        self.websocket = None
        self.cubes = {}  # Store created cubes
        
    async def connect(self):
        """Connexion au serveur"""
        self.websocket = await websockets.connect(self.uri)
        print(f"🔗 Connecté au serveur {self.uri}")
        
        # Ignore les messages initiaux
        await self.websocket.recv()  # world_state
        await self.websocket.recv()  # player_joined
        
    async def create_camera_cube(self, position, name="DemoCamera"):
        """Crée un cube caméra"""
        print(f"\n📹 Création caméra '{name}' à {position}")
        
        await self.websocket.send(json.dumps({
            "type": "create_camera",
            "position": position,
            "name": name,
            "resolution": [320, 240]
        }))
        
        response = await self.websocket.recv()
        data = json.loads(response)
        
        if data.get("type") == "camera_created":
            camera_id = data["camera"]["id"]
            self.cubes[camera_id] = data["camera"]
            print(f"✅ Caméra créée avec ID: {camera_id}")
            return camera_id
        else:
            print(f"❌ Erreur création caméra: {data}")
            return None
    
    async def create_ai_agent(self, position, name="DemoAI", ai_type="basic"):
        """Crée un agent IA"""
        print(f"\n🤖 Création agent IA '{name}' à {position}")
        
        await self.websocket.send(json.dumps({
            "type": "create_ai_agent",
            "position": position,
            "name": name,
            "ai_type": ai_type
        }))
        
        response = await self.websocket.recv()
        data = json.loads(response)
        
        if data.get("type") == "ai_agent_created":
            ai_id = data["ai_agent"]["id"]
            self.cubes[ai_id] = data["ai_agent"]
            print(f"✅ Agent IA créé avec ID: {ai_id}")
            return ai_id
        else:
            print(f"❌ Erreur création agent IA: {data}")
            return None
    
    async def move_cube(self, cube_id, new_position):
        """Déplace un cube"""
        print(f"\n📦 Déplacement cube {cube_id} vers {new_position}")
        
        await self.websocket.send(json.dumps({
            "type": "move_cube",
            "cube_id": cube_id,
            "position": new_position
        }))
        
        response = await self.websocket.recv()
        data = json.loads(response)
        
        if data.get("success"):
            print(f"✅ Cube déplacé avec succès")
            # Met à jour notre cache
            if cube_id in self.cubes:
                self.cubes[cube_id]["position"] = new_position
        else:
            print(f"❌ Erreur déplacement: {data.get('message', 'Inconnu')}")
    
    async def control_ai_agent(self, ai_id, command, **kwargs):
        """Contrôle un agent IA"""
        print(f"\n🎮 Contrôle agent IA {ai_id}: {command}")
        
        message = {
            "type": "control_ai_agent",
            "ai_id": ai_id,
            "command": command,
            **kwargs
        }
        
        await self.websocket.send(json.dumps(message))
        response = await self.websocket.recv()
        data = json.loads(response)
        
        if data.get("success"):
            print(f"✅ Commande exécutée: {command}")
        else:
            print(f"❌ Erreur commande: {data.get('message', 'Inconnu')}")
    
    async def list_cubes(self):
        """Liste tous les cubes disponibles"""
        print("\n📋 Liste des cubes:")
        
        # Caméras
        await self.websocket.send(json.dumps({"type": "get_cameras"}))
        response = await self.websocket.recv()
        cameras = json.loads(response)
        print(f"  📹 Caméras: {len(cameras.get('cameras', {}))}")
        
        # Agents IA
        await self.websocket.send(json.dumps({"type": "get_ai_agents"}))
        response = await self.websocket.recv()
        agents = json.loads(response)
        print(f"  🤖 Agents IA: {len(agents.get('ai_agents', {}))}")
        
        return cameras.get("cameras", {}), agents.get("ai_agents", {})
    
    async def demonstrate_scenario(self):
        """Démontre un scénario complet d'utilisation"""
        print("🎬 Début du scénario de démonstration")
        
        # 1. Créer plusieurs cubes caméra
        camera1_id = await self.create_camera_cube([10, 3, 10], "SecurityCam1")
        camera2_id = await self.create_camera_cube([15, 2, 5], "SecurityCam2")
        
        await asyncio.sleep(1)
        
        # 2. Créer des agents IA
        ai1_id = await self.create_ai_agent([5, 1, 5], "GuardBot", "advanced")
        ai2_id = await self.create_ai_agent([8, 1, 12], "PatrolBot", "basic")
        
        await asyncio.sleep(1)
        
        # 3. Lister tous les cubes
        cameras, agents = await self.list_cubes()
        
        await asyncio.sleep(1)
        
        # 4. Déplacer les cubes
        if camera1_id:
            await self.move_cube(camera1_id, [12, 4, 8])
        
        if ai1_id:
            await self.move_cube(ai1_id, [6, 1, 7])
        
        await asyncio.sleep(1)
        
        # 5. Contrôler les agents IA
        if ai1_id:
            await self.control_ai_agent(ai1_id, "set_behavior", behavior="observing")
            await asyncio.sleep(0.5)
            await self.control_ai_agent(ai1_id, "set_target", target_position=[10, 1, 10])
        
        if ai2_id:
            await self.control_ai_agent(ai2_id, "set_behavior", behavior="moving")
        
        await asyncio.sleep(1)
        
        # 6. Scénario complexe: surveillance coordonnée
        print("\n🎯 Scénario: Surveillance coordonnée")
        
        if ai1_id and camera1_id:
            print("  - Agent 1 se dirige vers la caméra 1")
            await self.control_ai_agent(ai1_id, "set_target", target_position=[12, 1, 8])
            
            print("  - Caméra 1 se repositionne pour surveillance")
            await self.move_cube(camera1_id, [12, 5, 8])
        
        if ai2_id and camera2_id:
            print("  - Agent 2 patrouille vers la caméra 2")
            await self.control_ai_agent(ai2_id, "set_target", target_position=[15, 1, 5])
            await self.control_ai_agent(ai2_id, "set_behavior", behavior="interacting")
        
        print("\n🎉 Scénario terminé avec succès!")
        print(f"📊 Cubes gérés: {len(self.cubes)}")
        
    async def close(self):
        """Ferme la connexion"""
        if self.websocket:
            await self.websocket.close()
            print("🔌 Connexion fermée")

async def main():
    """Fonction principale de démonstration"""
    client = CubeExampleClient()
    
    try:
        await client.connect()
        await client.demonstrate_scenario()
        
        # Garde la connexion ouverte un moment pour observer
        print("\n⏳ Attente de 5 secondes pour observation...")
        await asyncio.sleep(5)
        
    except KeyboardInterrupt:
        print("\n⛔ Interruption utilisateur")
    except Exception as e:
        print(f"❌ Erreur: {e}")
    finally:
        await client.close()

if __name__ == "__main__":
    print("🚀 Démarrage de l'exemple d'utilisation des cubes")
    print("📝 Assurez-vous que le serveur est démarré (python3 server.py)")
    print("=" * 60)
    
    asyncio.run(main())
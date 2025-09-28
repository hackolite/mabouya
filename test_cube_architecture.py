#!/usr/bin/env python3
"""
Test script pour valider la nouvelle architecture des cubes
"""

import asyncio
import websockets
import json

async def test_cube_architecture():
    """Test des nouvelles fonctionnalités de cubes"""
    uri = "ws://localhost:8765"
    
    try:
        async with websockets.connect(uri) as websocket:
            print("🔗 Connecté au serveur")
            
            # Ignore les messages initiaux
            await websocket.recv()  # world_state
            await websocket.recv()  # player_joined
            
            # Test 1: Créer une caméra
            print("\n📹 Test création de caméra...")
            await websocket.send(json.dumps({
                "type": "create_camera",
                "position": [5, 2, 5],
                "name": "TestCamera",
                "resolution": [320, 240]
            }))
            
            response = await websocket.recv()
            data = json.loads(response)
            print(f"✅ Caméra créée: {data.get('type')}")
            camera_id = data.get('camera', {}).get('id')
            
            # Test 2: Créer un agent IA
            print("\n🤖 Test création d'agent IA...")
            await websocket.send(json.dumps({
                "type": "create_ai_agent",
                "position": [3, 1, 3],
                "name": "TestAI",
                "ai_type": "basic"
            }))
            
            response = await websocket.recv()
            data = json.loads(response)
            print(f"✅ Agent IA créé: {data.get('type')}")
            ai_id = data.get('ai_agent', {}).get('id')
            
            # Test 3: Lister les caméras
            print("\n📋 Test liste des caméras...")
            await websocket.send(json.dumps({"type": "get_cameras"}))
            response = await websocket.recv()
            data = json.loads(response)
            print(f"✅ Caméras trouvées: {len(data.get('cameras', {}))}")
            
            # Test 4: Lister les agents IA
            print("\n📋 Test liste des agents IA...")
            await websocket.send(json.dumps({"type": "get_ai_agents"}))
            response = await websocket.recv()
            data = json.loads(response)
            print(f"✅ Agents IA trouvés: {len(data.get('ai_agents', {}))}")
            
            # Test 5: Déplacer un cube (si on a un ID)
            if camera_id:
                print(f"\n📦 Test déplacement de caméra {camera_id}...")
                await websocket.send(json.dumps({
                    "type": "move_cube",
                    "cube_id": camera_id,
                    "position": [6, 3, 6]
                }))
                response = await websocket.recv()
                data = json.loads(response)
                print(f"✅ Déplacement: {data.get('success', False)}")
            
            # Test 6: Contrôler l'agent IA (si on a un ID)
            if ai_id:
                print(f"\n🎮 Test contrôle agent IA {ai_id}...")
                await websocket.send(json.dumps({
                    "type": "control_ai_agent",
                    "ai_id": ai_id,
                    "command": "set_behavior",
                    "behavior": "observing"
                }))
                response = await websocket.recv()
                data = json.loads(response)
                print(f"✅ Contrôle IA: {data.get('success', False)}")
            
            # Test 7: Tests des fenêtres de caméra (si on a un ID de caméra)
            if camera_id:
                print(f"\n🪟 Test fenêtres caméra {camera_id}...")
                
                # Test statut fenêtre
                await websocket.send(json.dumps({
                    "type": "get_camera_window_status",
                    "camera_id": camera_id
                }))
                response = await websocket.recv()
                data = json.loads(response)
                print(f"✅ Statut fenêtre: has_window={data.get('has_window', False)}")
                
                # Test activation fenêtre
                await websocket.send(json.dumps({
                    "type": "activate_camera_window",
                    "camera_id": camera_id
                }))
                response = await websocket.recv()
                data = json.loads(response)
                print(f"✅ Activation fenêtre: success={data.get('success', False)}")
                
                # Test capture d'image
                await websocket.send(json.dumps({
                    "type": "capture_camera_window",
                    "camera_id": camera_id
                }))
                response = await websocket.recv()
                data = json.loads(response)
                frame_available = data.get('frame_data') is not None
                print(f"✅ Capture image: frame_available={frame_available}")
                
                # Test désactivation fenêtre
                await websocket.send(json.dumps({
                    "type": "deactivate_camera_window",
                    "camera_id": camera_id
                }))
                response = await websocket.recv()
                data = json.loads(response)
                print(f"✅ Désactivation fenêtre: success={data.get('success', True)}")
            
            print("\n🎉 Tests terminés avec succès!")
            
    except Exception as e:
        print(f"❌ Erreur pendant les tests: {e}")

if __name__ == "__main__":
    asyncio.run(test_cube_architecture())
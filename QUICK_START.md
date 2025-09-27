# Guide de Démarrage Rapide - Architecture Cubes

## Installation et Lancement

### 1. Installer les dépendances
```bash
pip install websockets
# Optionnel pour compression d'images:
pip install Pillow
```

### 2. Démarrer le serveur
```bash
python3 server.py
```
Le serveur démarre sur `ws://localhost:8765`

### 3. Tester l'architecture
```bash
python3 test_cube_architecture.py
```

### 4. Démonstration complète
```bash
python3 example_cube_usage.py
```

## Utilisation Rapide via WebSocket

### Créer une caméra
```json
{
    "type": "create_camera",
    "position": [10, 5, 10],
    "name": "MaCaméra",
    "resolution": [320, 240]
}
```

### Créer un agent IA
```json
{
    "type": "create_ai_agent",
    "position": [5, 1, 5],
    "name": "MonAgent",
    "ai_type": "basic"
}
```

### Déplacer un cube
```json
{
    "type": "move_cube",
    "cube_id": "cam_12345...",
    "position": [12, 6, 8]
}
```

### Contrôler un agent IA
```json
{
    "type": "control_ai_agent",
    "ai_id": "ai_12345...",
    "command": "set_behavior",
    "behavior": "observing"
}
```

## Clients Existants

- **Caméra**: `python3 camera.py` - Visualisation des streams caméra
- **Client 3D**: `python3 client.py` - Client interactif 3D

## Architecture en Bref

```
Cube (base)
├── CubeCamera (caméras avec streaming)
├── CubeAI (agents intelligents)
├── Player (joueurs connectés)
└── [Futurs types de cubes]
```

Chaque cube a des propriétés:
- Position, taille, texture
- Capacités (caméra, déplaçable, traversable)
- API dédiée via WebSocket

## Cas d'Usage Typiques

1. **Surveillance**: Caméras + agents patrouilleurs
2. **Test cobotique**: Simulation robots industriels
3. **IA multimodale**: Agents avec capteurs multiples
4. **Recherche**: Environnement d'expérimentation IA

## Endpoints API Principaux

- `create_camera`, `create_ai_agent` - Création
- `move_cube`, `remove_cube` - Gestion
- `control_ai_agent` - Contrôle IA
- `get_cameras`, `get_ai_agents` - Listage

Voir `CUBE_ARCHITECTURE.md` pour la documentation complète.
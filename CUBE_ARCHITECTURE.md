# Architecture des Cubes - Minecraft Clone

## Vue d'ensemble

Cette architecture implémente un système de cubes orienté objet pour un clone de Minecraft permettant de générer des scénarios complexes avec des agents intelligents, capteurs, et caméras pour tester des logiciels de cobotique et des modèles d'IA multimodaux.

## Classes Principales

### 1. Classe Cube (Base)

La classe centrale dont héritent tous les autres cubes.

```python
class Cube:
    def __init__(self, position, block_type="grass", texture=None, size=(1, 1, 1), 
                 has_camera=False, is_moveable=False, is_traversable=False)
```

**Propriétés:**
- `position`: Position 3D (x, y, z)
- `block_type`: Type de bloc (grass, stone, camera, ai_agent, etc.)
- `texture`: Texture visuelle du cube
- `size`: Taille du cube (x, y, z) - par défaut (1, 1, 1)
- `has_camera`: Booléen - si le cube a une caméra
- `is_moveable`: Booléen - si le cube peut être déplacé
- `is_traversable`: Booléen - si on peut passer à travers
- `id`: Identifiant unique généré automatiquement
- `windows`: Abstraction pour fenêtres associées au cube (None par défaut)

**Méthodes principales:**
- `move_to(new_position)`: Déplace le cube (si moveable)
- `can_collide_with(other_cube)`: Vérifie les collisions
- `to_dict()`: Sérialisation pour API

### 2. Classe CubeCamera (Hérite de Cube)

Cube avec capacités de caméra intégrée.

```python
class CubeCamera(Cube):
    def __init__(self, position, name="Camera", resolution=(240, 180))
```

**Propriétés spécifiques:**
- `name`: Nom de la caméra
- `rotation`: [yaw, pitch] pour orientation
- `fov`: Champ de vision (field of view)
- `resolution`: Résolution de rendu (largeur, hauteur)

**Méthodes spécifiques:**
- `rotate(yaw_delta, pitch_delta)`: Rotation de la caméra
- `render_view(world, frame_count)`: Génère la vue caméra
- `move_camera(new_position)`: Déplacement spécialisé caméra
- `activate_window()`: Active la fenêtre Pyglet de visualisation
- `deactivate_window()`: Désactive la fenêtre Pyglet
- `capture_window_frame()`: Capture une image de la fenêtre
- `is_window_active()`: Vérifie si la fenêtre est active

**Fonctionnalités:**
- Streaming vidéo via WebSocket
- Ray marching pour rendu réaliste
- Indicateurs visuels (LED live, compteur de frames)
- Fenêtre Pyglet pour visualisation interactive
- Capture d'images via l'API WebSocket
- API dédiée pour contrôle

### 3. Classe CubeAI (Hérite de Cube)

Cube avec intelligence artificielle intégrée.

```python
class CubeAI(Cube):
    def __init__(self, position, name="AI_Agent", ai_type="basic")
```

**Propriétés spécifiques:**
- `name`: Nom de l'agent IA
- `ai_type`: Type d'IA (basic, advanced, neural_network, etc.)
- `behavior_state`: État comportemental (idle, moving, observing, interacting, learning)
- `target_position`: Position cible pour déplacement
- `memory`: Dictionnaire pour stockage contextuel
- `sensors`: Liste des capteurs disponibles

**Méthodes spécifiques:**
- `set_behavior_state(state)`: Change l'état comportemental
- `set_target(target_position)`: Définit une cible de déplacement
- `add_sensor(sensor_type, config)`: Ajoute un capteur
- `update_memory(key, value)`: Met à jour la mémoire

### 4. Classe Player (Hérite de Cube)

Représente un joueur connecté comme un cube.

```python
class Player(Cube):
    def __init__(self, position, player_id, name="Player")
```

**Propriétés spécifiques:**
- `player_id`: Identifiant unique du joueur
- `name`: Nom du joueur
- Taille: (0.8, 1.8, 0.8) - forme humanoïde
- Déplaçable par défaut

## Gestion du Monde

### Classe World

Gère tous les types de cubes dans des collections séparées:

```python
class World:
    def __init__(self, size=20)
```

**Collections:**
- `blocks`: Cubes standard du terrain
- `cameras`: Cubes caméra
- `ai_agents`: Cubes IA
- `players`: Cubes joueurs
- `special_cubes`: Autres cubes spéciaux

**Méthodes de gestion:**
- `add_camera(position, name, resolution)`: Ajoute une caméra
- `add_ai_agent(position, name, ai_type)`: Ajoute un agent IA
- `move_cube(cube_id, new_position)`: Déplace n'importe quel cube
- `remove_cube(cube_id)`: Supprime un cube
- `check_collision(cube, new_position)`: Vérification des collisions

## API WebSocket

### Endpoints pour Caméras

- `create_camera`: Crée une nouvelle caméra
- `subscribe_camera`: S'abonne au stream d'une caméra
- `control_camera`: Contrôle rotation/mouvement caméra
- `get_cameras`: Liste toutes les caméras

### Endpoints pour Fenêtres de Caméra

- `activate_camera_window`: Active la fenêtre Pyglet d'une caméra
- `deactivate_camera_window`: Désactive la fenêtre d'une caméra  
- `capture_camera_window`: Capture une image de la fenêtre caméra
- `get_camera_window_status`: Obtient le statut de la fenêtre d'une caméra

### Endpoints pour Agents IA

- `create_ai_agent`: Crée un nouvel agent IA
- `control_ai_agent`: Contrôle comportement/mouvement IA
- `get_ai_agents`: Liste tous les agents IA

### Endpoints Génériques Cubes

- `move_cube`: Déplace n'importe quel cube
- `remove_cube`: Supprime un cube
- `get_cube_info`: Informations détaillées d'un cube

## Exemples d'utilisation

### Création d'une caméra de surveillance

```python
# Via WebSocket
{
    "type": "create_camera",
    "position": [10, 5, 10],
    "name": "SecurityCam1",
    "resolution": [640, 480]
}
```

### Contrôle de fenêtre caméra

```python
# Activer la fenêtre de visualisation Pyglet
{
    "type": "activate_camera_window",
    "camera_id": "cam_12345..."
}

# Capturer une image de la fenêtre
{
    "type": "capture_camera_window", 
    "camera_id": "cam_12345..."
}

# Vérifier le statut de la fenêtre
{
    "type": "get_camera_window_status",
    "camera_id": "cam_12345..."
}

# Désactiver la fenêtre
{
    "type": "deactivate_camera_window",
    "camera_id": "cam_12345..."
}
```

### Création d'agent IA avec capteurs

```python
# Via WebSocket
{
    "type": "create_ai_agent",
    "position": [5, 1, 5],
    "name": "GuardBot",
    "ai_type": "advanced"
}

# Puis configuration du comportement
{
    "type": "control_ai_agent",
    "ai_id": "ai_12345...",
    "command": "set_behavior",
    "behavior": "observing"
}
```

### Scénario de surveillance coordonnée

```python
# 1. Créer caméras aux points stratégiques
# 2. Créer agents IA patrouilleurs
# 3. Configurer cibles et comportements
# 4. Déplacer dynamiquement selon besoins
```

## Rendu Visuel

### Couleurs par type de cube
- **Herbe**: Vert (34, 139, 34)
- **Pierre**: Gris (128, 128, 128)
- **Joueur**: Bleu (0, 150, 255)
- **Caméra**: Jaune (255, 255, 0)
- **Agent IA**: Magenta (255, 0, 255)

### Fonctionnalités visuelles
- Ray marching pour rendu réaliste
- Indicateurs visuels sur les caméras (LED, compteurs)
- Support textures personnalisées

## Extensibilité

L'architecture permet facilement d'ajouter:
- Nouveaux types de cubes (héritant de Cube)
- Nouveaux capteurs pour agents IA
- Nouveaux comportements IA
- Nouvelles fonctionnalités caméra
- Endpoints API personnalisés

## Cas d'usage

1. **Test de cobotique**: Agents IA simulant robots industriels
2. **Surveillance intelligente**: Réseau caméras + agents patrouilleurs
3. **IA multimodale**: Agents avec capteurs multiples (vision, audio, etc.)
4. **Architectures distribuées**: Communication inter-agents
5. **Apprentissage par renforcement**: Environnement d'entraînement IA

## Performance

- Streaming caméra optimisé (2 FPS par défaut)
- Ray marching efficace avec steps adaptatifs
- Collections séparées pour recherche rapide
- Compression JPEG optionnelle pour streams
- Gestion mémoire des connexions WebSocket
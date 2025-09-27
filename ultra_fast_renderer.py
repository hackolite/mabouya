import numpy as np
import math
from collections import namedtuple

# --- Définition des blocs ---
Block = namedtuple("Block", ["block_type", "camera", "movable", "traversable"])

class UltraFastRenderer:
    def __init__(self, width=320, height=240):
        self.width = width
        self.height = height
        self.pixel_buffer = np.zeros((height, width, 3), dtype=np.uint8)
        self.sky_color = np.array([135, 206, 235], dtype=np.uint8)  # bleu ciel
        self.blocks = []  # liste de blocs dans le monde

    def add_block(self, x, y, z, block_type="stone", 
                  camera=False, movable=True, traversable=False):
        """Ajoute un bloc au monde"""
        block = Block(block_type, camera, movable, traversable)
        self.blocks.append(((x, y, z), block))

    def _get_block_color(self, block_type):
        colors = {
            "stone": np.array([100, 100, 100], dtype=np.uint8),
            "grass": np.array([0, 200, 0], dtype=np.uint8),
            "dirt": np.array([139, 69, 19], dtype=np.uint8),
            "camera": np.array([200, 0, 0], dtype=np.uint8),
            "ai": np.array([0, 0, 200], dtype=np.uint8),
        }
        return colors.get(block_type, np.array([255, 255, 255], dtype=np.uint8))

    def render_camera_view(self, camera_position, camera_rotation, fov=70, frame_count=0):
        """Rendu caméra avec z-buffer pour précision comparable à Pyglet"""
        cx, cy, cz = camera_position
        yaw, pitch = camera_rotation

        # Efface écran
        self.pixel_buffer[:] = self.sky_color
        z_buffer = np.full((self.height, self.width), np.inf)  # profondeur infinie

        # Prépare matrices de rotation
        yaw_rad, pitch_rad = math.radians(yaw), math.radians(pitch)
        cos_y, sin_y = math.cos(yaw_rad), math.sin(yaw_rad)
        cos_p, sin_p = math.cos(pitch_rad), math.sin(pitch_rad)

        # Projection params
        fov_rad = math.radians(fov)
        aspect = self.width / self.height
        tan_half_fov = math.tan(fov_rad / 2)

        for (bx, by, bz), block in self.blocks:
            # Sommets d’un cube centré
            half = 0.5
            vertices = [
                (bx+dx*half, by+dy*half, bz+dz*half)
                for dx in (-1,1) for dy in (-1,1) for dz in (-1,1)
            ]

            # Transforme sommets caméra
            proj_points = []
            for vx, vy, vz in vertices:
                rel_x, rel_y, rel_z = vx-cx, vy-cy, vz-cz

                # Rotation yaw (Y)
                xz = rel_x*cos_y - rel_z*sin_y
                zz = rel_x*sin_y + rel_z*cos_y

                # Rotation pitch (X)
                yz = rel_y*cos_p - zz*sin_p
                zz2 = rel_y*sin_p + zz*cos_p

                if zz2 <= 0.1:
                    continue  # derrière la caméra

                # Projection perspective
                sx = (xz / zz2) / (tan_half_fov * aspect)
                sy = (yz / zz2) / tan_half_fov
                px = int((sx+1)*0.5*self.width)
                py = int((1-sy)*0.5*self.height)
                proj_points.append((px, py, zz2))

            if not proj_points:
                continue

            # Bounding box écran du cube
            min_x = max(0, min(p[0] for p in proj_points))
            max_x = min(self.width-1, max(p[0] for p in proj_points))
            min_y = max(0, min(p[1] for p in proj_points))
            max_y = min(self.height-1, max(p[1] for p in proj_points))

            # Couleur du bloc
            color = self._get_block_color(block.block_type)
            avg_depth = np.mean([p[2] for p in proj_points])

            for py in range(min_y, max_y+1):
                for px in range(min_x, max_x+1):
                    if avg_depth < z_buffer[py, px]:
                        z_buffer[py, px] = avg_depth
                        depth_factor = max(0.3, min(1.0, 20.0/avg_depth))
                        self.pixel_buffer[py, px] = (color * depth_factor).astype(np.uint8)

        return self.pixel_buffer

# --- Exemple d’utilisation ---
if __name__ == "__main__":
    import cv2
    import time

    renderer = UltraFastRenderer(320, 240)

    # Création d’une petite scène
    for x in range(-3, 4):
        for z in range(-3, 4):
            renderer.add_block(x, -1, z, "grass")  # sol
    renderer.add_block(0, 0, 3, "stone")
    renderer.add_block(1, 0, 5, "camera")
    renderer.add_block(-2, 0, 4, "ai")

    # Boucle de rendu
    cx, cy, cz = 0, 1, 0
    yaw, pitch = 0, 0

    last = time.time()
    frames = 0

    while True:
        frame = renderer.render_camera_view((cx, cy, cz), (yaw, pitch))
        cv2.imshow("Camera View", frame)
        yaw += 1  # tourne la caméra
        frames += 1

        if time.time() - last >= 1:
            print("FPS:", frames)
            frames = 0
            last = time.time()

        if cv2.waitKey(1) == 27:  # ESC pour quitter
            break

    cv2.destroyAllWindows()

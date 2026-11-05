from gint import *
from math import sqrt

# Config
W, H = 64, 64       # Internal render resolution
SCALE = 4           # Upscale factor (64 * 4 = 256px width)
OX, OY = 10, 20     # Position of the tiny original render
BX = (320 - (W * SCALE)) // 2  # Centered X for the big render
BY = OY + H + 10    # Y position for the big render

# Scene Setup
# Spheres: (x, y, z, radius, (r, g, b)) 
# Note: Colors are 0-31
spheres = [
    (0.0, 0.0, 0.5, 0.9, (31, 5, 5)),    # Red (Center)
    (1.2, 0.3, 0.0, 0.5, (5, 5, 31)),    # Blue (Right)
    (-0.7, -0.5, -0.3, 0.4, (5, 31, 5))  # Green (Left)
]

# Lights: (x, y, z)
lights = [(-2, 3, -3), (3, 1, -2)]

def run():
    dclear(C_WHITE)
    dtext(OX, 2, C_BLACK, "Mini Raytracer: Computing...")
    drect(BX-2, BY-2, BX+W*SCALE+2, BY+H*SCALE+2, C_BLACK) # Frame
    dupdate()

    cam_z = -3.0  # Camera position

    # Loop over every pixel of the SMALL resolution
    for y in range(H):
        v = (1.0 - 2.0 * y / H) # Map Y to [-1, 1]
        
        for x in range(W):
            u = (2.0 * x / W - 1.0) # Map X to [-1, 1]
            
            # 1. Ray Generation
            # Perspective projection
            rd_x, rd_y, rd_z = u, v, 1.5 
            # Normalize direction
            d = sqrt(rd_x*rd_x + rd_y*rd_y + rd_z*rd_z)
            rd_x, rd_y, rd_z = rd_x/d, rd_y/d, rd_z/d
            
            ro_x, ro_y, ro_z = 0.0, 0.0, cam_z
            
            # 2. Intersection
            closest_t = 99.0
            hit_obj = None
            
            # Check Spheres
            for s in spheres:
                sx, sy, sz, sr, sc = s
                # Vector Sphere->Origin
                ox, oy, oz = ro_x - sx, ro_y - sy, ro_z - sz
                
                b = ox*rd_x + oy*rd_y + oz*rd_z
                c = (ox*ox + oy*oy + oz*oz) - sr*sr
                h = b*b - c
                
                if h > 0:
                    t = -b - sqrt(h)
                    if 0.01 < t < closest_t:
                        closest_t = t
                        hit_obj = s
            
            # Check Checkerboard Floor (y = -1)
            if rd_y < -0.001: 
                t_floor = (-1.0 - ro_y) / rd_y
                if 0.01 < t_floor < closest_t:
                    closest_t = t_floor
                    hit_obj = "FLOOR"

            # 3. Shading
            color = C_BLACK # Background
            
            if hit_obj:
                # Calculate Hit Point
                px = ro_x + closest_t * rd_x
                py = ro_y + closest_t * rd_y
                pz = ro_z + closest_t * rd_z
                
                # Calculate Normal & Base Color
                if hit_obj == "FLOOR":
                    nx, ny, nz = 0.0, 1.0, 0.0
                    # Checkerboard pattern logic
                    check = (int(px*2) + int(pz*2)) % 2
                    base_c = (20, 20, 20) if check else (10, 10, 10)
                else:
                    sx, sy, sz, sr, sc = hit_obj
                    nx, ny, nz = px - sx, py - sy, pz - sz
                    n_inv = 1.0 / sr
                    nx, ny, nz = nx*n_inv, ny*n_inv, nz*n_inv
                    base_c = sc

                # Lighting Calculation (Diffuse)
                intensity = 0.15 # Ambient
                for lx, ly, lz in lights:
                    # Vector Hit->Light
                    lvx, lvy, lvz = lx - px, ly - py, lz - pz
                    # Normalize
                    l_dist = sqrt(lvx*lvx + lvy*lvy + lvz*lvz)
                    lvx, lvy, lvz = lvx/l_dist, lvy/l_dist, lvz/l_dist
                    
                    dot = nx*lvx + ny*lvy + nz*lvz
                    if dot > 0:
                        intensity += dot * 0.6 

                if intensity > 1.0: intensity = 1.0
                
                # Final Color (0-31 range)
                color = C_RGB(int(base_c[0] * intensity), 
                              int(base_c[1] * intensity), 
                              int(base_c[2] * intensity))

            # 4. Drawing
            # Draw the computed pixel at original size (Top)
            dpixel(OX + x, OY + y, color)
            
            # Draw the pixel upscaled (Bottom)
            # We draw a rectangle of SCALE x SCALE size
            rx, ry = BX + x * SCALE, BY + y * SCALE
            drect(rx, ry, rx + SCALE - 1, ry + SCALE - 1, color)
        
        # Update screen every 4 lines to show progress nicely
        if y % 4 == 0:
            dupdate()

    dtext(OX, DHEIGHT - 20, C_BLACK, "Done! Press [EXE] or [Del]")
    dupdate()

run()
# Wait for exit
while True:
    key = getkey().key
    if key == KEY_DEL or key == KEY_EXIT or key == KEY_EXE:
        break

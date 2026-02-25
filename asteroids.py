from gint import *
from random import randint

# Configuration
WIDTH, HEIGHT = 320, 528
C_BG = C_WHITE
C_FG = C_BLACK

# Fixed-Point Math
SHIFT = 8
ONE = 1 << SHIFT        # 256 is our "1.0"
HALF = ONE >> 1
MAX_X = WIDTH << SHIFT
MAX_Y = HEIGHT << SHIFT

# Lookup Tables
# Pre-calculate Sin/Cos to avoid heavy math module usage at runtime
# 64 angles = 360 degrees (0-63)
LUT_MASK = 63
LUT_SIZE = 64
SIN_LUT = [0] * LUT_SIZE
COS_LUT = [0] * LUT_SIZE

# We need math just once for setup
import math
dtext(10, 10, C_BLACK, "Building Tables...")
dupdate()
for i in range(LUT_SIZE):
    rad = (i / LUT_SIZE) * 2 * math.pi
    SIN_LUT[i] = int(math.sin(rad) * ONE)
    COS_LUT[i] = int(math.cos(rad) * ONE)
del math # Free memory

# Game Constants
MAX_VEL = 6 * ONE
FRICTION = 250 # ~0.97 (250/256)
BULLET_SPEED = 7 * ONE
BULLET_LIFE = 45

# Global Object Lists
entities = []
pending_add = []

class Entity:
    """Base class using Fixed-Point coordinates"""
    def __init__(self, x, y, radius_pixels):
        self.x = int(x)
        self.y = int(y)
        self.vx = 0
        self.vy = 0
        # Radius stored in fixed point for collision checks
        self.radius_sq = (radius_pixels * ONE) ** 2 
        self.angle_idx = 0 # 0-63
        self.dead = False
        self.visible = True

    def update(self):
        self.x += self.vx
        self.y += self.vy

        # Screen Wrapping (with fixed point margin)
        margin = 16 * ONE
        if self.x < -margin: self.x += MAX_X + margin * 2
        elif self.x > MAX_X + margin: self.x -= MAX_X + margin * 2
        
        if self.y < -margin: self.y += MAX_Y + margin * 2
        elif self.y > MAX_Y + margin: self.y -= MAX_Y + margin * 2

    def draw(self, color):
        pass 

class Ship(Entity):
    def __init__(self):
        super().__init__(MAX_X // 2, MAX_Y // 2, 8)
        self.angle_idx = 48 # Point Up (3/4 of circle)
        self.cooldown = 0

    def update(self):
        # Rotation (Integer Steps)
        # Note: Input state is updated in the main loop via clearevents()
        if keydown(KEY_LEFT) or keydown(KEY_4):
            self.angle_idx = (self.angle_idx - 2) & LUT_MASK
        if keydown(KEY_RIGHT) or keydown(KEY_6):
            self.angle_idx = (self.angle_idx + 2) & LUT_MASK

        # Thrust
        if keydown(KEY_UP) or keydown(KEY_8):
            # Thrust force
            thrust = 60 # 60/256 ~ 0.23
            self.vx += (COS_LUT[self.angle_idx] * thrust) >> SHIFT
            self.vy += (SIN_LUT[self.angle_idx] * thrust) >> SHIFT
            
            # Particles (Exhaust)
            # Spawn slightly behind ship
            # Offset -10 pixels
            px = self.x - ((COS_LUT[self.angle_idx] * 10)) 
            py = self.y - ((SIN_LUT[self.angle_idx] * 10))
            
            p = Particle(px, py, 10)
            # Random spray angle
            spray = randint(-4, 4)
            p_ang = (self.angle_idx + 32 + spray) & LUT_MASK # Backwards
            p_spd = randint(ONE, 3*ONE)
            p.vx = (COS_LUT[p_ang] * p_spd) >> SHIFT
            p.vy = (SIN_LUT[p_ang] * p_spd) >> SHIFT
            pending_add.append(p)

        # Friction
        self.vx = (self.vx * FRICTION) >> SHIFT
        self.vy = (self.vy * FRICTION) >> SHIFT
        
        # Shooting
        if self.cooldown > 0: self.cooldown -= 1
        if (keydown(KEY_SHIFT) or keydown(KEY_EXE)) and self.cooldown == 0:
            # Bullet at nose (+10px)
            bx = self.x + ((COS_LUT[self.angle_idx] * 10))
            by = self.y + ((SIN_LUT[self.angle_idx] * 10))
            b = Bullet(bx, by, self.angle_idx)
            # Add ship inertia
            b.vx += self.vx // 2
            b.vy += self.vy // 2
            pending_add.append(b)
            self.cooldown = 10

        super().update()

    def draw(self, color):
        cx, cy = self.x >> SHIFT, self.y >> SHIFT
        
        # Vertices calculation using LUT
        # Nose
        nx = cx + ((COS_LUT[self.angle_idx] * 10) >> SHIFT)
        ny = cy + ((SIN_LUT[self.angle_idx] * 10) >> SHIFT)
        
        # Rear Left (Angle + ~135deg -> +24 indices)
        a2 = (self.angle_idx + 24) & LUT_MASK
        lx = cx + ((COS_LUT[a2] * 8) >> SHIFT)
        ly = cy + ((SIN_LUT[a2] * 8) >> SHIFT)
        
        # Rear Right
        a3 = (self.angle_idx - 24) & LUT_MASK
        rx = cx + ((COS_LUT[a3] * 8) >> SHIFT)
        ry = cy + ((SIN_LUT[a3] * 8) >> SHIFT)

        dline(nx, ny, lx, ly, color)
        dline(lx, ly, rx, ry, color)
        dline(rx, ry, nx, ny, color)

class Rock(Entity):
    def __init__(self, x, y, size_tier):
        r_map = {3: 20, 2: 12, 1: 6}
        super().__init__(x, y, r_map[size_tier])
        self.tier = size_tier
        
        # Random Velocity
        speed = randint(ONE//2, ONE + (ONE>>1))
        ang = randint(0, LUT_MASK)
        self.vx = (COS_LUT[ang] * speed) >> SHIFT
        self.vy = (SIN_LUT[ang] * speed) >> SHIFT
        
        self.rot_speed = 1 if randint(0, 1) else -1
        
        # Generate Shape Points (Fixed Point offsets)
        self.shape = []
        points = 8 if size_tier == 3 else (6 if size_tier == 2 else 4)
        base_r = r_map[size_tier] * ONE
        
        for i in range(points):
            # Even distribution
            a = int((i / points) * LUT_SIZE)
            # Jaggedness
            dist = base_r + randint(-base_r//3, base_r//3)
            px = (COS_LUT[a] * dist) >> SHIFT
            py = (SIN_LUT[a] * dist) >> SHIFT
            self.shape.append((px, py))

    def update(self):
        self.angle_idx = (self.angle_idx + self.rot_speed) & LUT_MASK
        super().update()

    def draw(self, color):
        cx, cy = self.x >> SHIFT, self.y >> SHIFT
        c = COS_LUT[self.angle_idx]
        s = SIN_LUT[self.angle_idx]
        
        screen_pts = []
        # Rotation Transform:
        # X' = X*c - Y*s
        # Y' = X*s + Y*c
        for ox, oy in self.shape:
            # ox, oy are ONE-scaled. c, s are ONE-scaled.
            # Result is ONE*ONE scaled. Shift once to get ONE scaled.
            rx = (ox * c - oy * s) >> SHIFT
            ry = (ox * s + oy * c) >> SHIFT
            # Convert to pixels
            screen_pts.append((cx + (rx >> SHIFT), cy + (ry >> SHIFT)))
            
        for i in range(len(screen_pts)):
            p1 = screen_pts[i]
            p2 = screen_pts[(i+1) % len(screen_pts)]
            dline(p1[0], p1[1], p2[0], p2[1], color)

class Bullet(Entity):
    def __init__(self, x, y, angle_idx):
        super().__init__(x, y, 1)
        self.vx = (COS_LUT[angle_idx] * BULLET_SPEED) >> SHIFT
        self.vy = (SIN_LUT[angle_idx] * BULLET_SPEED) >> SHIFT
        self.life = BULLET_LIFE

    def update(self):
        self.life -= 1
        if self.life <= 0: self.dead = True
        super().update()

    def draw(self, color):
        px, py = self.x >> SHIFT, self.y >> SHIFT
        dpixel(px, py, color)
        dpixel(px+1, py, color)

class Particle(Entity):
    def __init__(self, x, y, life):
        super().__init__(x, y, 0)
        self.life = life
        
    def update(self):
        self.life -= 1
        if self.life <= 0: self.dead = True
        super().update()
        
    def draw(self, color):
        dpixel(self.x >> SHIFT, self.y >> SHIFT, color)

def run():
    global entities, pending_add
    
    dclear(C_BG)
    ship = Ship()
    entities = [ship]
    score = 0
    game_over = False
    
    def spawn_wave(n):
        for _ in range(n):
            # Spawn away from center
            while True:
                rx = randint(0, MAX_X)
                ry = randint(0, MAX_Y)
                # Distance check from ship (approx)
                dx = rx - ship.x
                dy = ry - ship.y
                if dx*dx + dy*dy > (100 * ONE)**2:
                    break
            entities.append(Rock(rx, ry, 3))
            
    spawn_wave(4)

    while True:
        # INPUT PROCESSING
        # Polling events updates keydown() state
        clearevents()
        
        if keydown(KEY_EXIT): break
        
        # ERASE OLD
        for e in entities: 
            if e.visible: e.draw(C_BG)
        drect(0, 0, 100, 20, C_BG) # Clear HUD
        if game_over: drect(60, 200, 260, 300, C_BG)

        # UPDATE
        pending_add = []
        if not game_over:
            for e in entities: e.update()
            
            # Collisions
            bullets = [b for b in entities if isinstance(b, Bullet)]
            rocks = [r for r in entities if isinstance(r, Rock)]
            
            for r in rocks:
                if r.dead: continue
                
                # Check Ship
                if ship.visible:
                    dist_sq = (r.x - ship.x)**2 + (r.y - ship.y)**2
                    # Ship rad ~8, Rock rad variable. 
                    # r.radius_sq is already ONE-scaled squared
                    if dist_sq < r.radius_sq + (10*ONE)**2:
                        ship.visible = False
                        game_over = True
                        # Particles
                        for _ in range(20):
                            p = Particle(ship.x, ship.y, randint(20, 50))
                            ang = randint(0, 63)
                            spd = randint(ONE, 4*ONE)
                            p.vx = (COS_LUT[ang]*spd) >> SHIFT
                            p.vy = (SIN_LUT[ang]*spd) >> SHIFT
                            pending_add.append(p)
                
                # Check Bullets
                for b in bullets:
                    if b.dead: continue
                    dist_sq = (r.x - b.x)**2 + (r.y - b.y)**2
                    if dist_sq < r.radius_sq:
                        b.dead = True
                        r.dead = True
                        score += 100
                        
                        # Split
                        if r.tier > 1:
                            for _ in range(2):
                                pending_add.append(Rock(r.x, r.y, r.tier - 1))
                        
                        # Debris
                        for _ in range(4):
                            p = Particle(r.x, r.y, randint(10, 20))
                            ang = randint(0, 63)
                            spd = randint(ONE, 2*ONE)
                            p.vx = (COS_LUT[ang]*spd) >> SHIFT
                            p.vy = (SIN_LUT[ang]*spd) >> SHIFT
                            pending_add.append(p)
                        break
                        
            # Respawn
            if len(rocks) == 0 and len([x for x in pending_add if isinstance(x, Rock)]) == 0:
                spawn_wave(3)
        
        else:
            # Game Over Update
            for e in entities:
                if isinstance(e, Particle): e.update()
            
            if keydown(KEY_EXE):
                dclear(C_BG)
                ship = Ship()
                entities = [ship]
                spawn_wave(4)
                score = 0
                game_over = False
                continue

        # Clean List
        entities = [e for e in entities if not e.dead]
        entities.extend(pending_add)
        
        # DRAW NEW
        for e in entities:
            if e.visible: e.draw(C_FG)
            
        dtext(5, 5, C_FG, f"Score: {score}")
        if game_over:
            dtext(120, 220, C_FG, "GAME OVER")
            dtext(90, 240, C_FG, "Press [EXE] to Restart")
            
        dupdate()


run()

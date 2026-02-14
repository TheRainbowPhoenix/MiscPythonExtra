from gint import KEY_KBD
from gint import *
import cgui
import cinput
import struct
import math
import random
import gc
import time

try:
    from micropython import opt_level
    opt_level(3)
except ImportError:
    pass

# =============================================================================
# APP CONFIG
# =============================================================================

SCREEN_W = 320
SCREEN_H = 528
HEADER_H = 50

# Internal Buffer Resolution (Half Size)
BUF_W = 160
BUF_H = (528 - HEADER_H) // 2 # ~239
BUF_HEADER_OFFSET = HEADER_H

# =============================================================================
# IMAGE & BUFFER MANAGEMENT
# =============================================================================

class Canvas:
    def __init__(self):
        # Raw buffer RGB565 (2 bytes per pixel) for half-res
        # Size: 160 * 239 * 2 ~= 76 KB
        self.buffer = bytearray()
        self.mv = None
        self.clear(C_WHITE)

    def clear(self, color_int):
        hi = (color_int >> 8) & 0xFF
        lo = color_int & 0xFF
        gc.collect()
        try:
            pix = bytes([lo, hi])
            self.buffer = bytearray(pix * (BUF_W * BUF_H))
            self.mv = memoryview(self.buffer)
        except MemoryError:
            cgui.msgbox("Err: RAM full in Clear")
        dclear(color_int)

    def draw_scaled(self):
        # Full redraw from buffer
        # Can use blit_roi for full screen
        self.blit_roi(0, 0, BUF_W, BUF_H)

    def blit_roi(self, bx, by, bw, bh):
        # Draw buffer region to screen
        # bx, by, bw, bh in buffer coordinates
        if not self.mv: return
        
        cw = BUF_W
        bx = max(0, bx)
        by = max(0, by)
        bw = min(bw, BUF_W - bx)
        bh = min(bh, BUF_H - by)
        
        if bw <= 0 or bh <= 0: return

        sx = bx * 2
        sy = BUF_HEADER_OFFSET + by * 2
        
        buf = self.mv
        
        # Draw line by line to minimize function calls
        for y in range(bh):
            row_start = (by + y) * cw * 2 + (bx * 2)
            row_end = row_start + (bw * 2)
            ys = sy + y * 2
            
            ptr = row_start
            for x in range(bw):
                # Manual 2-byte read is fastest in MicroPython without struct
                lo = buf[ptr]
                hi = buf[ptr+1]
                col = (hi << 8) | lo
                ptr += 2
                
                # Draw 2x2 pixel
                drect(sx + x*2, ys, sx + x*2 + 1, ys + 1, col)

    def stroke_stamp(self, x, y, color, size, opacity, flow, shape):
        # x, y are SCREEN coordinates
        # Map to buffer coordinates
        cx = x // 2
        cy = (y - BUF_HEADER_OFFSET) // 2
        
        # Buffer dimensions
        cw, ch = BUF_W, BUF_H
        
        # Calculate radius in buffer pixels
        # Allow r_buf = 0 for 1-pixel brushes (size 1-3 on screen)
        r_buf = int(size // 4)
        r2_buf = r_buf * r_buf
        
        # Color components
        sr, sg, sb = cgui.unpack_color(color)
        clo = color & 0xFF
        chi = (color >> 8) & 0xFF
        
        # Alpha calculation
        alpha = (opacity / 100.0) * (flow / 100.0)
        alpha = max(0.01, min(1.0, alpha))
        is_solid = (alpha >= 0.98)
        
        # Bounding box in buffer
        x_min = max(0, cx - r_buf)
        x_max = min(cw, cx + r_buf + 1)
        y_min = max(0, cy - r_buf)
        y_max = min(ch, cy + r_buf + 1)
        
        if x_min >= x_max or y_min >= y_max: return None
        
        buf = self.mv
        
        # Draw loops
        for buf_y in range(y_min, y_max):
            dy = buf_y - cy
            
            # Shape bounds optimization for row
            row_x_min, row_x_max = x_min, x_max
            
            if shape == 'circle':
                dy2 = dy*dy
                if dy2 > r2_buf: continue
                # Handling r_buf=0 case where r2_buf=0
                if r2_buf == 0: dx_limit = 0
                else: dx_limit = int(math.sqrt(r2_buf - dy2))
                row_x_min = max(x_min, cx - dx_limit)
                row_x_max = min(x_max, cx + dx_limit + 1)
            elif shape == 'rect_v':
                if abs(dy) > r_buf: continue
                dx_limit = max(1, r_buf//2)
                row_x_min = max(x_min, cx - dx_limit)
                row_x_max = min(x_max, cx + dx_limit + 1)
            elif shape == 'oval':
                if abs(dy) > max(1, r_buf//2): continue
                # Use simplified oval (flattened circle)
                pass 

            if row_x_min >= row_x_max: continue
            
            start_idx = (buf_y * cw + row_x_min) * 2
            
            if is_solid:
                # Optimized solid fill
                # Create pattern for the row width
                # This is faster than per-pixel assignment
                width = row_x_max - row_x_min
                # buf[start_idx : start_idx + width*2] = bytes([clo, chi]) * width
                # MicroPython slice assignment might be slow for repeated creation of bytes calls?
                # Actually loop assignment is safer for memory unless we preallocate patterns.
                # For now, keep loop for safety, optimize later if needed.
                ptr = start_idx
                for _ in range(width):
                    buf[ptr] = clo
                    buf[ptr+1] = chi
                    ptr += 2
            else:
                # Blending
                ptr = start_idx
                for _ in range(row_x_max - row_x_min):
                    dlo = buf[ptr]
                    dhi = buf[ptr+1]
                    dest_c = (dhi << 8) | dlo
                    
                    # Inline unpack (RGB565 -> 5-bit)
                    dr = (dest_c >> 10) & 0x1F
                    dg = (dest_c >> 5) & 0x1F
                    db = dest_c & 0x1F
                    
                    out_r = int(sr * alpha + dr * (1.0 - alpha))
                    out_g = int(sg * alpha + dg * (1.0 - alpha))
                    out_b = int(sb * alpha + db * (1.0 - alpha))
                    
                    # Inline pack (5-bit -> RGB565)
                    res_c = ((out_r & 0x1F) << 10) | ((out_g & 0x1F) << 5) | (out_b & 0x1F)
                    
                    buf[ptr] = res_c & 0xFF
                    buf[ptr+1] = (res_c >> 8) & 0xFF
                    ptr += 2
                    
        return (x_min, y_min, x_max - x_min, y_max - y_min)

# =============================================================================
# FILE IO
# =============================================================================

def save_gip(canvas, filename):
    # Save the small buffer directly
    try:
        with open(filename, "wb") as f:
            f.write(struct.pack("<II", BUF_W, BUF_H))
            f.write(canvas.buffer)
        cgui.msgbox("Saved GIP!")
    except Exception as e:
        cgui.msgbox(f"Error: {e}")

def load_gip(canvas, filename):
    try:
        with open(filename, "rb") as f:
            w, h = struct.unpack("<II", f.read(8))
            if w != BUF_W or h != BUF_H:
                cgui.msgbox("Dim mismatch (Must be half-res)")
                return
            # Read directly into buffer, bypassing potential memoryview write issues
            f.readinto(canvas.buffer)
        canvas.draw_scaled() 
        cgui.msgbox("Loaded GIP")
    except Exception as e:
        cgui.msgbox(f"Error: {e}")

def save_bmp(canvas, filename):
    # Save as 24-bit BGR BMP (RGB888)
    # Convert RGB565 (internal buffer format) -> RGB888
    
    file_size = 54 + BUF_W * BUF_H * 3
    offset = 54
    # No padding needed for 160 width (160*3 = 480 is div by 4)
    row_size = BUF_W * 3
    
    try:
        with open(filename, "wb") as f:
            f.write(b'BM')
            f.write(struct.pack("<I", file_size))
            f.write(b'\x00\x00\x00\x00')
            f.write(struct.pack("<I", offset))
            f.write(struct.pack("<I", 40)) # Header size
            f.write(struct.pack("<i", BUF_W))
            f.write(struct.pack("<i", -BUF_H)) # Top-down
            f.write(struct.pack("<H", 1)) # Planes
            f.write(struct.pack("<H", 24)) # 24-bit
            f.write(struct.pack("<I", 0)) # Compression
            f.write(struct.pack("<I", row_size * BUF_H)) # Image size
            f.write(struct.pack("<ii", 2835, 2835))
            f.write(struct.pack("<II", 0, 0))
            
            buf = canvas.buffer
            row_buf = bytearray(row_size)
            ptr = 0
            
            for y in range(BUF_H):
                r_ptr = 0
                for x in range(BUF_W):
                    lo = buf[ptr]
                    hi = buf[ptr+1]
                    c = (hi << 8) | lo
                    ptr += 2
                    
                    # Unpack RGB565
                    r5 = (c >> 11) & 0x1F
                    g6 = (c >> 5) & 0x3F
                    b5 = c & 0x1F
                    
                    # Scale to 8-bit
                    r8 = (r5 * 255) // 31
                    g8 = (g6 * 255) // 63
                    b8 = (b5 * 255) // 31
                    
                    # Store BGR
                    row_buf[r_ptr] = b8
                    row_buf[r_ptr+1] = g8
                    row_buf[r_ptr+2] = r8
                    r_ptr += 3
                
                f.write(row_buf)
                
        cgui.msgbox("Saved BMP")
    except Exception as e:
        cgui.msgbox(f"Save Err: {e}")

def load_bmp(canvas, filename):
    try:
        with open(filename, "rb") as f:
            header = f.read(54)
            if len(header) < 54: raise ValueError("Bad Header")
            if header[0:2] != b'BM': raise ValueError("Not a BMP")
            
            data_offset = struct.unpack("<I", header[10:14])[0]
            width = struct.unpack("<i", header[18:22])[0]
            height = struct.unpack("<i", header[22:26])[0]
            bpp = struct.unpack("<H", header[28:30])[0]
            comp = struct.unpack("<I", header[30:34])[0]
            
            if bpp != 24: raise ValueError("Need 24-bit BMP")
            if comp != 0: raise ValueError("Compressed BMP unsupported")
            
            flip_y = (height > 0)
            height = abs(height)
            
            # Fill rest with white
            canvas.clear(C_WHITE)
            
            w_copy = min(width, BUF_W)
            h_copy = min(height, BUF_H)
            
            row_bytes = width * 3
            padding = (4 - (row_bytes % 4)) % 4
            row_padded = row_bytes + padding
            
            f.seek(data_offset)
            buf = canvas.buffer
            
            for i in range(height):
                if i >= h_copy: break
                
                y = height - 1 - i if flip_y else i
                if y >= BUF_H: 
                    f.seek(row_padded, 1)
                    continue
                
                row_data = f.read(row_padded)
                if len(row_data) < row_bytes: break
                
                ptr = y * BUF_W * 2
                
                for x in range(w_copy):
                    po = x * 3
                    b8, g8, r8 = row_data[po], row_data[po+1], row_data[po+2]
                    
                    # 888 -> 565
                    r5 = (r8 * 31) // 255
                    g6 = (g8 * 63) // 255
                    b5 = (b8 * 31) // 255
                    
                    c = (r5 << 11) | (g6 << 5) | b5
                    
                    buf[ptr] = c & 0xFF
                    buf[ptr+1] = (c >> 8) & 0xFF
                    ptr += 2

        canvas.draw_scaled()
        cgui.msgbox("Imported BMP")
    except Exception as e:
        cgui.msgbox(f"Err: {e}")

# =============================================================================
# PAINT TOOLS
# =============================================================================

def draw_brush_cursor(x, y, size, color, shape='circle'):
    r = int(size // 2)
    if shape == 'circle': dcircle(x, y, r, color, color)
    elif shape == 'square': drect(x - r, y - r, x + r, y + r, color)
    elif shape == 'rect_v': drect(x - max(1, r//2), y - r, x + max(1, r//2), y + r, color)
    elif shape == 'oval': dellipse(x - r, y - max(1, r//2), x + r, y + max(1, r//2), color, color)

def bresenham(x0, y0, x1, y1):
    points = []
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    
    while True:
        points.append((x0, y0))
        if x0 == x1 and y0 == y1: break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x0 += sx
        if e2 < dx:
            err += dx
            y0 += sy
    return points

# =============================================================================
# MAIN APP
# =============================================================================

# =============================================================================
# UI HELPERS
# =============================================================================

def draw_icon_hamburger(x, y, col):
    # Hamburger Icon
    w = 18
    # Top, Mid, Bot
    cgui.fill_rect(x - w//2, y - 6, w, 2, col)
    cgui.fill_rect(x - w//2, y - 1, w, 2, col)
    cgui.fill_rect(x - w//2, y + 4, w, 2, col)

def draw_icon_brush(x, y, col):
    # Brush Icon (45 deg) - Refined
    # Handle (Longer & Thinner)
    cgui.dpoly([x+6, y-8, x+8, y-6, x, y+2, x-2, y], col, col)
    # Base (Circle, Smaller) with Gap
    cgui.dcircle(x-4, y+4, 2, col, col)
    # Tip (Triangle, Small)
    cgui.dpoly([x-6, y+3, x-3, y+6, x-8, y+8], col, col)

class IconButton(cgui.Button):
    def __init__(self, x, y, w, h, icon_func, color=None):
        super().__init__(x, y, w, h, "", color)
        self.icon_func = icon_func
    
    def draw(self):
        # Background
        base_col = cgui.THEME['accent'] if self.pressed else self.color
        cgui.fill_rect(self.x, self.y, self.w, self.h, base_col)
        # Border
        drect_border(self.x, self.y, self.x+self.w-1, self.y+self.h-1, C_NONE, 1, cgui.THEME['panel_border'])
        # Icon
        cx = self.x + self.w // 2
        cy = self.y + self.h // 2
        self.icon_func(cx, cy, cgui.THEME['text'])

# =============================================================================
# MAIN APP
# =============================================================================

class PaintApp:
    def __init__(self):
        self.canvas = Canvas()
        self.color = C_RGB(31, 0, 0)
        
        # Brush Props
        self.brush_size = 10
        self.brush_spacing = 5
        self.brush_spread = 0
        self.brush_flow = 100
        self.brush_opacity = 100
        self.brush_shape = 'circle'
        
        self.buttons = [
            IconButton(5, 5, 40, 40, draw_icon_hamburger),
            IconButton(50, 5, 40, 40, draw_icon_brush),
            cgui.Button(100, 5, 40, 40, "", self.color)
        ]

    def draw_toolbar(self):
        cgui.draw_panel(0, 0, SCREEN_W, HEADER_H)
        self.buttons[2].color = self.color
        for b in self.buttons:
            b.draw()
        info = f"S:{int(self.brush_size)} {self.brush_shape[:1].upper()}"
        dtext_opt(150, 25, cgui.THEME['text'], C_NONE, DTEXT_LEFT, DTEXT_MIDDLE, info, -1)

    def show_loading(self, text="Loading..."):
         # Modal loading indicator
         cx, cy = SCREEN_W//2, SCREEN_H//2
         w, h = 140, 30
         # Shadow
         cgui.fill_rect(cx - w//2 + 2, cy - h//2 + 2, w, h, C_BLACK)
         dtext_opt(SCREEN_W//2, SCREEN_H//2 - 5, C_WHITE, C_NONE, DTEXT_CENTER, DTEXT_TOP, text, -1)
         dupdate()
         
         

    def handle_menu(self):
        opts = ["New", "Load GIP", "Save GIP", "Save BMP", "Quit"]
        res = cinput.pick(opts, "Menu", theme='dark')
        
        if res == "New":
            self.canvas.clear(C_WHITE)
        elif res == "Save GIP":
            fn = cgui.prompt_filename(".gip")
            if fn: save_gip(self.canvas, fn)
        elif res == "Load GIP":
            fn = cgui.prompt_filename(".gip")
            if fn: load_gip(self.canvas, fn)
        elif res == "Save BMP":
            fn = cgui.prompt_filename(".bmp")
            if fn: save_bmp(self.canvas, fn)
        elif res == "Quit":
            return "QUIT"
        
        # Restore full screen logic
        clearevents()
        dtext_opt(SCREEN_W//2, SCREEN_H//2, C_WHITE, C_BLACK, DTEXT_CENTER, DTEXT_MIDDLE, "Rendering...", -1)
        dupdate()
        self.canvas.draw_scaled()
        self.draw_toolbar()
        dupdate()

    def run(self):
        self.draw_toolbar()
        
        # Initial draw
        self.canvas.draw_scaled()
        dupdate()
        
        painting = False
        last_x, last_y = 0, 0
        dist_acc = 0.0
        
        while True:
            cleareventflips()
            ev = pollevent()
            events = []
            while ev.type != KEYEV_NONE:
                events.append(ev)
                ev = pollevent()
                
            if keypressed(KEY_EXIT): return
            
            # Additional key shortcuts (Menu F1)
            # Use KBD or Menu key
            if keypressed(KEY_KBD) or keypressed(KEY_EXE):
                import cinput
                menu_opts = ["Brush Settings", "Color Picker", "Fill Canvas", "Save BMP", "Import BMP", "Quit"]
                res = cinput.pick(menu_opts, "Menu")
                
                # Robust string/index handling
                sel = None
                if isinstance(res, int) and 0 <= res < len(menu_opts): sel = menu_opts[res]
                elif isinstance(res, str): sel = res
                
                refresh_needed = True
                
                if sel == "Brush Settings":
                     dlg = cgui.BrushDialog(self.brush_size, self.brush_spacing, self.brush_spread, 
                                             self.brush_flow, self.brush_opacity, self.brush_shape)
                     val = dlg.run()
                     if val:
                         self.brush_size = val['size']
                         self.brush_spacing = val['spacing']
                         self.brush_spread = val['spread']
                         self.brush_flow = val['flow']
                         self.brush_opacity = val['opacity']
                         self.brush_shape = val['shape']
                     clearevents()
                elif sel == "Color Picker":
                     picker = cgui.ColorPicker(self.color)
                     new_col = picker.run()
                     if new_col is not None:
                         self.color = new_col
                     clearevents()
                elif sel == "Fill Canvas":
                     if cinput.ask("Fill?", "Overwrite canvas?"):
                         self.canvas.clear(self.color)
                elif sel == "Save BMP":
                     fname = cinput.input("Filename:", "drawing.bmp")
                     if fname:
                         self.show_loading("Saving BMP...")
                         save_bmp(self.canvas, fname)
                         clearevents() # Discard input after heavy op
                elif sel == "Import BMP":
                     fname = cinput.input("Filename:", "drawing.bmp")
                     if fname:
                         self.show_loading("Importing BMP...")
                         load_bmp(self.canvas, fname)
                         clearevents() # Discard input
                elif sel == "Quit": return
                else:
                    refresh_needed = False
                
                if refresh_needed:
                    self.draw_toolbar()
                    self.show_loading("Rendering...")
                    self.canvas.draw_scaled()
                    dupdate()
                    # Discard any buffered touches from the menu interaction time
                    clearevents()

            needs_update = False
            
            for e in events:
                if e.type == KEYEV_TOUCH_DOWN:
                    if e.y < HEADER_H:
                        for btn in self.buttons:
                            if btn.hit(e.x, e.y):
                                btn.pressed = True
                                self.draw_toolbar()
                                needs_update = True
                    else:
                        # Glitch rejection
                        if not (0 <= e.x < SCREEN_W and 0 <= e.y < SCREEN_H): continue
                        
                        painting = True
                        last_x, last_y = e.x, e.y
                        dist_acc = 0.0
                        
                        # Apply initial stamp
                        jx = random.randint(-int(self.brush_spread), int(self.brush_spread)) if self.brush_spread > 0 else 0
                        jy = random.randint(-int(self.brush_spread), int(self.brush_spread)) if self.brush_spread > 0 else 0
                        
                        roi = self.canvas.stroke_stamp(e.x + jx, e.y + jy, self.color, self.brush_size, 
                                                     self.brush_opacity, self.brush_flow, self.brush_shape)
                        if roi:
                            self.canvas.blit_roi(*roi)
                            needs_update = True

                elif e.type == KEYEV_TOUCH_DRAG:
                    if painting:
                        # Glitch rejection
                        if not (0 <= e.x < SCREEN_W and 0 <= e.y < SCREEN_H): continue
                        
                        x0, y0 = last_x, last_y
                        x1, y1 = e.x, e.y
                        dx, dy = x1 - x0, y1 - y0
                        seg_len = math.sqrt(dx*dx + dy*dy)
                        
                        # Sanity check for huge jumps
                        if seg_len > 100: 
                            last_x, last_y = e.x, e.y
                            continue

                        if seg_len > 0:
                            dist_covered = 0.0
                            spacing = max(1.0, self.brush_spacing)
                            
                            next_step = spacing - dist_acc
                            
                            while dist_covered + next_step <= seg_len:
                                dist_covered += next_step
                                
                                t = dist_covered / seg_len
                                # Use int casting for strict coordinates
                                px = int(x0 + dx * t)
                                py = int(y0 + dy * t)
                                
                                # Apply stamp
                                jx = random.randint(-int(self.brush_spread), int(self.brush_spread)) if self.brush_spread > 0 else 0
                                jy = random.randint(-int(self.brush_spread), int(self.brush_spread)) if self.brush_spread > 0 else 0
                                
                                roi = self.canvas.stroke_stamp(px + jx, py + jy, self.color, self.brush_size, 
                                                             self.brush_opacity, self.brush_flow, self.brush_shape)
                                if roi:
                                    self.canvas.blit_roi(*roi)
                                    needs_update = True
                                
                                dist_acc = 0.0
                                next_step = spacing
                                
                            dist_acc += (seg_len - dist_covered)
                        
                        last_x, last_y = e.x, e.y

                elif e.type == KEYEV_TOUCH_UP:
                    if painting:
                        painting = False
                    else:
                        redraw_needed = False
                        # Check buttons
                        if self.buttons[0].pressed: # Menu
                            self.buttons[0].pressed = False
                            import cinput
                            menu_opts = ["Fill Canvas", "Save BMP", "Import BMP", "Quit"]
                            res = cinput.pick(menu_opts, "Menu")
                            
                            sel = None
                            if isinstance(res, int) and 0 <= res < len(menu_opts): sel = menu_opts[res]
                            elif isinstance(res, str): sel = res
                            
                            if sel == "Fill Canvas":
                                if cinput.ask("Fill?", "Overwrite canvas?"):
                                    self.canvas.clear(self.color)
                                    redraw_needed = True
                            elif sel == "Save BMP":
                                fname = cinput.input("Filename:", "drawing.bmp")
                                if fname:
                                    self.show_loading("Saving BMP...")
                                    save_bmp(self.canvas, fname)
                                    clearevents()
                                redraw_needed = True
                            elif sel == "Import BMP":
                                fname = cinput.input("Filename:", "drawing.bmp")
                                if fname:
                                    self.show_loading("Importing BMP...")
                                    load_bmp(self.canvas, fname)
                                    clearevents()

                                redraw_needed = True
                            elif sel == "Quit":
                                return
                            redraw_needed = True

                        elif self.buttons[1].pressed: # Brush
                            self.buttons[1].pressed = False
                            dlg = cgui.BrushDialog(self.brush_size, self.brush_spacing, self.brush_spread, 
                                                 self.brush_flow, self.brush_opacity, self.brush_shape)
                            val = dlg.run()
                            if val:
                                self.brush_size = val['size']
                                self.brush_spacing = val['spacing']
                                self.brush_spread = val['spread']
                                self.brush_flow = val['flow']
                                self.brush_opacity = val['opacity']
                                self.brush_shape = val['shape']
                            clearevents()
                            redraw_needed = True

                        elif self.buttons[2].pressed: # Color
                            self.buttons[2].pressed = False
                            picker = cgui.ColorPicker(self.color)
                            new_col = picker.run()
                            if new_col is not None:
                                self.color = new_col
                            clearevents()
                            redraw_needed = True
                        
                        if redraw_needed:
                            self.draw_toolbar()
                            # Draw Loading
                            self.show_loading("Rendering...")
                            dupdate()
                            self.canvas.draw_scaled()
                        
                        self.draw_toolbar()
                        needs_update = True

            if needs_update:
                dupdate()
            
            time.sleep(0.01)

app = PaintApp()
app.run()
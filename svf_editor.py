from gint import *

dclear(C_RGB(4, 4, 4))
dtext_opt(160, 80, C_WHITE, C_RGB(4, 4, 4), DTEXT_CENTER,DTEXT_CENTER, "SVF Editor", 16)
dupdate()

# =============================================================================
# CONSTANTS & CONFIG
# =============================================================================

import svf
import cinput
import cgui
import time
import math

SCREEN_W = 320
SCREEN_H = 528
HEADER_H = 40
FOOTER_H = 40
LAYER_PANEL_W = 160

# Theme (Dark)
THEME_BG = cgui.THEME['bg']           # Main BG
THEME_PANEL = cgui.THEME['panel']     # Panel BG
THEME_ACCENT = cgui.THEME['accent']   # Active Highlight
THEME_TEXT = cgui.THEME['text']       # Text
THEME_DIM = cgui.THEME['text_dim']    # Disabled/Dim
THEME_BORDER = cgui.THEME['panel_border']

COL_SELECTION = C_RGB(31, 0, 0) # Red selection box
COL_GRID = C_RGB(8, 8, 8)       # Very subtle grid
COL_POLY_PREVIEW = C_RGB(31, 15, 0) # Orange poly line preview

# Tools
TOOL_VIEW = 0
TOOL_SELECT = 1
TOOL_EDIT = 2
TOOL_RECT = 3
TOOL_CIRCLE = 4
TOOL_POLY = 5
TOOL_LINE = 6

TOOL_NAMES = {
    TOOL_VIEW: "View",
    TOOL_SELECT: "Move",
    TOOL_EDIT: "Edit",
    TOOL_RECT: "Rect",
    TOOL_CIRCLE: "Circle", 
    TOOL_POLY: "Poly",
    TOOL_LINE: "Line"
}

TOOL_ICONS = {
    TOOL_VIEW: "VZ",
    TOOL_SELECT: "MV",
    TOOL_EDIT: "NK",
    TOOL_RECT: "SQ",
    TOOL_CIRCLE: "CI",
    TOOL_POLY: "PL",
    TOOL_LINE: "LN"
}

POP_NONE = 0
POP_TOOLS = 1
POP_LAYERS = 2
POP_EDIT = 3 # Cut/Copy/Paste
POP_ADV = 4 # Precise inputs

PERF_DRAG_TIME = 0.5

# =============================================================================
# MATH UTILS
# =============================================================================

def dist_sq(x1, y1, x2, y2):
    return (x1-x2)**2 + (y1-y2)**2

def pt_seg_dist_sq(px, py, x1, y1, x2, y2):
    # Squared distance from point p to segment (x1,y1)-(x2,y2)
    l2 = dist_sq(x1, y1, x2, y2)
    if l2 == 0: return dist_sq(px, py, x1, y1)
    t = ((px - x1) * (x2 - x1) + (py - y1) * (y2 - y1)) / l2
    t = max(0, min(1, t))
    prox_x = x1 + t * (x2 - x1)
    prox_y = y1 + t * (y2 - y1)
    return dist_sq(px, py, prox_x, prox_y)

# =============================================================================
# DATA MODEL
# =============================================================================

class SVFObject:
    def __init__(self, type_id, **kwargs):
        self.type = type_id
        self.props = kwargs
        
    def copy(self):
        new_props = {}
        for k, v in self.props.items():
            if isinstance(v, list):
                new_props[k] = list(v)
            else:
                new_props[k] = v
        return SVFObject(self.type, **new_props)

    def bounds(self):
        t = self.type
        p = self.props
        if t == svf.CMD_RECT or t == svf.CMD_RECT_B or t == svf.CMD_LINE:
            return (min(p['x1'], p['x2']), min(p['y1'], p['y2']), 
                    abs(p['x2']-p['x1']), abs(p['y2']-p['y1']))
        elif t == svf.CMD_CIRCLE:
            return (p['cx'] - p['r'], p['cy'] - p['r'], p['r']*2, p['r']*2)
        elif t == svf.CMD_POLY:
            verts = p['vertices']
            if not verts: return (0,0,0,0)
            xs = verts[0::2]
            ys = verts[1::2]
            minx, maxx = min(xs), max(xs)
            miny, maxy = min(ys), max(ys)
            return (minx, miny, maxx-minx, maxy-miny)
        return (0,0,0,0)

    def draw(self, cam_x, cam_y, zoom):
        def tx(val): return int((val * zoom) + cam_x)
        def ty(val): return int((val * zoom) + cam_y)
        def ts(val): return int(val * zoom)
        
        t = self.type
        p = self.props
        fill = p.get('fill', svf.BIN_C_NONE)
        stroke = p.get('stroke', svf.BIN_C_NONE)
        
        if fill == svf.BIN_C_NONE: fill = C_NONE
        if stroke == svf.BIN_C_NONE: stroke = C_NONE

        if t == svf.CMD_RECT:
            drect(tx(p['x1']), ty(p['y1']), tx(p['x2']), ty(p['y2']), fill)
        elif t == svf.CMD_RECT_B:
            drect_border(tx(p['x1']), ty(p['y1']), tx(p['x2']), ty(p['y2']), 
                         fill, p.get('width', 1), stroke)
        elif t == svf.CMD_CIRCLE:
            dcircle(tx(p['cx']), ty(p['cy']), ts(p['r']), fill, stroke)
        elif t == svf.CMD_LINE:
            dline(tx(p['x1']), ty(p['y1']), tx(p['x2']), ty(p['y2']), stroke)
        elif t == svf.CMD_POLY:
            v_screen = []
            raw = p['vertices']
            for i in range(0, len(raw), 2):
                v_screen.append(tx(raw[i]))
                v_screen.append(ty(raw[i+1]))
            if len(v_screen) >= 6: # At least 3 points
                dpoly(v_screen, fill, stroke)
            elif len(v_screen) >= 4: # Line equivalent
                dline(v_screen[0], v_screen[1], v_screen[2], v_screen[3], stroke)

# =============================================================================
# APP STATE
# =============================================================================

POP_NONE = 0
POP_TOOLS = 1
POP_LAYERS = 2
POP_EDIT = 3 
POP_ADV = 4 
POP_OPT = 5 # Options

class EditorState:
    def __init__(self):
        self.objects = [] 
        self.history = [] 
        self.redo_stack = []
        
        # UI State
        self.tool = TOOL_VIEW
        self.selected_idx = -1
        self.active_popover = POP_NONE
        
        # Camera
        self.cam_x = 0
        self.cam_y = 0
        self.zoom = 1.0
        
        # Colors
        self.curr_fill = C_RGB(31, 0, 0)
        self.curr_stroke = C_BLACK
        
        # Poly Tool State
        self.poly_points = [] # Working points
        
        # Clipboard
        self.clipboard = None
        
        # Options
        self.snap_active = True # False
        self.snap_step = 10 # World units
        self.rm_mode = False # Remove node mode

    def calculate_snap_step(self):
        # Calculate snap step based on zoom (same logic as rulers)
        target_px = 50
        world_step = target_px / self.zoom
        try:
            mag = math.floor(math.log10(world_step))
            power = 10 ** mag
            rel = world_step / power
            if rel < 2: step = 2 * power
            elif rel < 5: step = 5 * power
            else: step = 10 * power
        except: step = 50 
        self.snap_step = step / 5.0 # Snap to minor ticks

    def add_object(self, obj):
        self.push_history()
        self.objects.append(obj)
        self.selected_idx = len(self.objects) - 1
        
    def push_history(self):
        if len(self.history) >= 10: self.history.pop(0)
        self.history.append([o.copy() for o in self.objects])
        self.redo_stack.clear()
        
    def undo(self):
        if not self.history: return
        self.redo_stack.append([o.copy() for o in self.objects])
        self.objects = self.history.pop()
        self.selected_idx = -1
        self.poly_points = [] # Reset working poly
        
    def redo(self):
        if not self.redo_stack: return
        self.history.append([o.copy() for o in self.objects])
        self.objects = self.redo_stack.pop()
        self.selected_idx = -1

    def input_coords(self, target_obj, prop_x, prop_y):
        # Helper for Advanced Input
        pass 

# =============================================================================
# UI COMPONENTS
# =============================================================================

BUTTON_H = 35

def draw_btn_core(x, y, w, h, text, pressed=False, primary=False):
    bg = THEME_ACCENT if pressed else (THEME_PANEL if not primary else THEME_ACCENT)
    fg = THEME_TEXT
    
    cgui.fill_rect(x, y, w, h, bg)
    drect_border(x, y, x+w-1, y+h-1, C_NONE, 1, THEME_BORDER)
    dtext_opt(x + w//2, y + h//2, fg, C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, text, -1)

def draw_color_preview(x, y, w, h, col):
    if col == svf.BIN_C_NONE:
        drect(x, y, x+w, y+h, C_WHITE)
        dline(x, y, x+w, y+h, C_BLACK)
        dline(x, y+h, x+w, y, C_BLACK)
    else:
        drect(x, y, x+w, y+h, col)
    drect_border(x, y, x+w, y+h, C_NONE, 1, THEME_BORDER)

# =============================================================================
# MAIN APP
# =============================================================================

class SVFEditor:
    def __init__(self):
        self.state = EditorState()
        self.running = True
        self.needs_redraw = True
        self.last_draw_time = 0
        
    def world_to_screen(self, wx, wy):
        sx = int(wx * self.state.zoom + self.state.cam_x)
        sy = int(wy * self.state.zoom + self.state.cam_y)
        return sx, sy

    def screen_to_world(self, sx, sy):
        wx = (sx - self.state.cam_x) / self.state.zoom
        wy = (sy - self.state.cam_y) / self.state.zoom
        
        if self.state.snap_active:
            self.state.calculate_snap_step()
            s = self.state.snap_step
            if s > 0:
                wx = round(wx / s) * s
                wy = round(wy / s) * s
            
        return int(wx), int(wy)

    # --- ACTION HANDLERS ---

    def action_cut(self):
        if self.state.selected_idx != -1:
            self.state.clipboard = self.state.objects[self.state.selected_idx].copy()
            self.state.push_history() # Push before delete
            self.state.objects.pop(self.state.selected_idx)
            self.state.selected_idx = -1
            self.state.active_popover = POP_NONE
            self.needs_redraw = True
            
    def action_copy(self):
        if self.state.selected_idx != -1:
            self.state.clipboard = self.state.objects[self.state.selected_idx].copy()
            self.state.active_popover = POP_NONE
            self.needs_redraw = True
            
    def action_paste(self):
        if self.state.clipboard:
            new_obj = self.state.clipboard.copy()
            # Offset slightly
            if 'x1' in new_obj.props:
                new_obj.props['x1'] += 10
                new_obj.props['y1'] += 10
                if 'x2' in new_obj.props:
                    new_obj.props['x2'] += 10
                    new_obj.props['y2'] += 10
            elif 'cx' in new_obj.props:
                new_obj.props['cx'] += 10
                new_obj.props['cy'] += 10
            elif 'vertices' in new_obj.props:
                v = new_obj.props['vertices']
                for i in range(len(v)):
                    v[i] += 10
            
            self.state.add_object(new_obj)
            self.state.active_popover = POP_NONE
            self.needs_redraw = True

    def action_delete(self):
        if self.state.selected_idx != -1:
            self.state.push_history()
            self.state.objects.pop(self.state.selected_idx)
            self.state.selected_idx = -1
            self.state.active_popover = POP_NONE
            self.needs_redraw = True
            
    def action_layer_move(self, up):
        idx = self.state.selected_idx
        if idx == -1: return
        
        objs = self.state.objects
        target = idx + 1 if up else idx - 1
        
        if 0 <= target < len(objs):
            # Swap
            objs[idx], objs[target] = objs[target], objs[idx]
            self.state.selected_idx = target
            self.needs_redraw = True

    # --- DRAW UI ---

    def draw_ui(self):
        st = self.state
        
        # Header
        cgui.draw_panel(0, 0, SCREEN_W, HEADER_H)
        draw_btn_core(5, 5, 40, 30, "=") # Menu
        draw_btn_core(50, 5, 40, 30, "<") # Undo
        if st.redo_stack: draw_btn_core(95, 5, 40, 30, ">") # Redo
        
        draw_btn_core(145, 5, 50, 30, "Edit", pressed=(st.active_popover == POP_EDIT))
        draw_btn_core(200, 5, 45, 30, "Opt", pressed=(st.active_popover == POP_OPT))
        draw_btn_core(SCREEN_W-50, 5, 45, 30, "Adv", pressed=(st.active_popover == POP_ADV))
        
        # Footer
        fy = SCREEN_H - FOOTER_H
        cgui.draw_panel(0, fy, SCREEN_W, FOOTER_H)
        
        # Tool Btn
        curr_icon = TOOL_ICONS.get(st.tool, "??")
        draw_btn_core(5, fy+5, 40, 30, curr_icon, pressed=(st.active_popover == POP_TOOLS), primary=True)
        
        # Colors
        dtext(55, fy+12, THEME_TEXT, "F")
        draw_color_preview(65, fy+5, 30, 30, st.curr_fill)
        dtext(105, fy+12, THEME_TEXT, "S")
        draw_color_preview(115, fy+5, 30, 30, st.curr_stroke)
        
        # Rm Button (Only in Edit Mode)
        if st.tool == TOOL_EDIT:
             draw_btn_core(155, fy+5, 40, 30, "Rm", pressed=st.rm_mode)
        
        # Layer Toggle
        draw_btn_core(SCREEN_W-45, fy+5, 40, 30, "LAYS", pressed=(st.active_popover == POP_LAYERS))

        # --- POPOVERS ---
        
        if st.active_popover == POP_TOOLS:
            # Bottom Left
            ph = len(TOOL_NAMES) * (BUTTON_H+2) + 10
            py = fy - ph
            cgui.draw_panel(5, py, 110, ph)
            
            y_off = py + 5
            for tid, name in TOOL_NAMES.items():
                draw_btn_core(10, y_off, 100, BUTTON_H, name, pressed=(st.tool == tid))
                y_off += BUTTON_H + 2

        elif st.active_popover == POP_OPT:
            # Top Right-ish
            px = 200
            w = 110
            ph = BUTTON_H + 10
            cgui.draw_panel(px, HEADER_H, w, ph)
            
            txt = "Snap: ON" if st.snap_active else "Snap: OFF"
            draw_btn_core(px+5, HEADER_H+5, w-10, BUTTON_H, txt, pressed=st.snap_active)
                
        elif st.active_popover == POP_LAYERS:
            # Right Side Panel
            lx = SCREEN_W - LAYER_PANEL_W
            cgui.draw_panel(lx, HEADER_H, LAYER_PANEL_W, fy - HEADER_H)
            
            dtext(lx+5, HEADER_H+5, THEME_TEXT, "Layers:")
            
            # List Area
            list_h = fy - HEADER_H - 50
            y_off = HEADER_H + 25
            
            for i in range(len(st.objects)-1, -1, -1):
                if y_off > fy - 60: break
                
                obj = st.objects[i]
                # Name resolution
                name = obj.props.get('name', "")
                if not name:
                    if obj.type == svf.CMD_RECT_B: name = f"Rect {i}"
                    elif obj.type == svf.CMD_RECT: name = f"Rect {i}"
                    elif obj.type == svf.CMD_CIRCLE: name = f"Circ {i}"
                    elif obj.type == svf.CMD_LINE: name = f"Line {i}"
                    elif obj.type == svf.CMD_POLY: name = f"Poly {i}"
                    else: name = f"Obj {i}"
                
                bg = THEME_ACCENT if i == st.selected_idx else THEME_PANEL
                cgui.fill_rect(lx+2, y_off, LAYER_PANEL_W-4, 40, bg)
                drect_border(lx+2, y_off, lx+LAYER_PANEL_W-2, y_off+39, C_NONE, 1, THEME_BORDER)
                
                # Preview Icon (30x30 box at lx+5, y_off+5)
                px, py, pw, ph = lx+5, y_off+5, 30, 30
                drect(px, py, px+pw, py+ph, THEME_BG)
                
                # Render Mini Preview
                # Target area: 22x22 inside 4px padding
                tx, ty, tw, th = px+4, py+4, 22, 22
                
                # Calculate bounds
                bx, by, bw, bh = obj.bounds_no_width() if hasattr(obj, 'bounds_no_width') else obj.bounds()
                # Actually obj.bounds() includes width, reasonable.
                # But bounds might be 0 if single point line?
                if bw < 1: bw = 1
                if bh < 1: bh = 1
                
                # Calculate scale to fit
                scale_w = tw / bw
                scale_h = th / bh
                scale = min(scale_w, scale_h)
                
                # Centering offset
                final_w = bw * scale
                final_h = bh * scale
                off_x = tx + (tw - final_w) / 2
                off_y = ty + (th - final_h) / 2
                
                # Draw relative
                f = obj.props.get('fill', svf.BIN_C_NONE)
                s = obj.props.get('stroke', svf.BIN_C_NONE)
                
                # Use clipping? No, just draw safely? 
                # Or just basic shape logic
                if obj.type == svf.CMD_RECT_B or obj.type == svf.CMD_RECT:
                     drect(int(off_x), int(off_y), int(off_x+final_w), int(off_y+final_h), f)
                     if s != svf.BIN_C_NONE and obj.type==svf.CMD_RECT_B:
                         drect_border(int(off_x), int(off_y), int(off_x+final_w), int(off_y+final_h), C_NONE, 1, s)
                elif obj.type == svf.CMD_CIRCLE:
                     # Center is off_x + radius
                     r = (final_w / 2)
                     dcircle(int(off_x+r), int(off_y+r), int(r), f, s)
                elif obj.type == svf.CMD_LINE:
                     # Line is diagonal in bounds?
                     # Need relative coords of points to bounds top-left
                     p = obj.props
                     x1 = (p['x1'] - bx) * scale + off_x
                     y1 = (p['y1'] - by) * scale + off_y
                     x2 = (p['x2'] - bx) * scale + off_x
                     y2 = (p['y2'] - by) * scale + off_y
                     dline(int(x1), int(y1), int(x2), int(y2), s)
                elif obj.type == svf.CMD_POLY:
                     verts = obj.props['vertices']
                     t_verts = []
                     for k in range(0, len(verts), 2):
                         vx = (verts[k] - bx) * scale + off_x
                         vy = (verts[k+1] - by) * scale + off_y
                         t_verts.append(int(vx)); t_verts.append(int(vy))
                     if len(t_verts) >= 6: dpoly(t_verts, f, s)
                     elif len(t_verts) == 4: dline(t_verts[0], t_verts[1], t_verts[2], t_verts[3], s)
                
                dtext(lx+40, y_off+12, THEME_TEXT, name)
                y_off += 42
            
            # Layer Controls (Up/Down + Rename)
            by = fy - 40
            draw_btn_core(lx + 5, by, 45, 30, "Up", primary=True)
            draw_btn_core(lx + 55, by, 45, 30, "Dn", primary=True)
            draw_btn_core(lx + 105, by, 40, 30, "Ren")

        elif st.active_popover == POP_EDIT:
            # Top Center
            px = 145
            w = 100
            ph = 5 * (BUTTON_H+2) + 10
            cgui.draw_panel(px, HEADER_H, w, ph)
            
            opts = ["Cut", "Copy", "Paste", "Delete", "Deselect"]
            y_off = HEADER_H + 5
            for opt in opts:
                draw_btn_core(px+5, y_off, w-10, BUTTON_H, opt)
                y_off += BUTTON_H + 2

        elif st.active_popover == POP_ADV:
            # Top Right
            w = 130
            px = SCREEN_W - w
            ph = 140
            cgui.draw_panel(px, HEADER_H, w, ph)
            
            dtext(px+5, HEADER_H+5, THEME_TEXT, "Precise Move")
            
            # Fake Input Fields
            box_col = C_RGB(4, 4, 4)
            dtext(px+5, HEADER_H+30, THEME_TEXT, "X:")
            cgui.fill_rect(px+25, HEADER_H+25, 90, 20, box_col)
            
            dtext(px+5, HEADER_H+55, THEME_TEXT, "Y:")
            cgui.fill_rect(px+25, HEADER_H+50, 90, 20, box_col)
            
            if st.selected_idx != -1:
                # Show coordinates
                obj = st.objects[st.selected_idx]
                bx, by, bw, bh = obj.bounds()
                dtext(px+30, HEADER_H+30, THEME_TEXT, str(min(obj.props.get('x1', bx), bx)))
                dtext(px+30, HEADER_H+55, THEME_TEXT, str(min(obj.props.get('y1', by), by)))
            
            draw_btn_core(px+10, HEADER_H+80, 110, 30, "Apply")


    def draw_canvas(self):
        st = self.state
        
        # Optimize Drawing using Clipping
        # Only clear/redraw the main canvas area
        # If dragging rapidly, we might skip full redraws in future, but for now we clamp region
        dwindow_set(0, HEADER_H, SCREEN_W, SCREEN_H - FOOTER_H)
        dclear(C_WHITE)
        
        # Axis Lines (0,0)
        cx, cy = self.world_to_screen(0, 0)
        
        # X Axis
        dline(0, cy, SCREEN_W, cy, C_BLACK)
        # Y Axis
        dline(cx, HEADER_H, cx, SCREEN_H - FOOTER_H, C_BLACK)
        
        # Render Order
        for i, obj in enumerate(st.objects):
            obj.draw(st.cam_x, st.cam_y, st.zoom)
            
            if i == st.selected_idx:
                 bx, by, bw, bh = obj.bounds()
                 sx, sy = self.world_to_screen(bx, by)
                 sw, sh = int(bw * st.zoom), int(bh * st.zoom)
                 drect_border(sx-2, sy-2, sx+sw+2, sy+sh+2, C_NONE, 1, COL_SELECTION)
                 
                 # Edit Handles
                 if st.tool == TOOL_EDIT:
                     handles = []
                     if obj.type == svf.CMD_POLY:
                         verts = obj.props['vertices']
                         for j in range(0, len(verts), 2):
                             handles.append((verts[j], verts[j+1]))
                     elif obj.type == svf.CMD_RECT_B or obj.type == svf.CMD_RECT:
                         x1, y1, x2, y2 = obj.props['x1'], obj.props['y1'], obj.props['x2'], obj.props['y2']
                         handles = [(x1,y1), (x2,y1), (x2,y2), (x1,y2)]
                     elif obj.type == svf.CMD_CIRCLE:
                         cx, cy, r = obj.props['cx'], obj.props['cy'], obj.props['r']
                         handles = [(cx, cy), (cx + r, cy)] # Center, Radius
                     elif obj.type == svf.CMD_LINE:
                         handles = [(obj.props['x1'], obj.props['y1']), (obj.props['x2'], obj.props['y2'])]
                     
                     for hx, hy in handles:
                         vx, vy = self.world_to_screen(hx, hy)
                         drect(vx-3, vy-3, vx+3, vy+3, COL_SELECTION)
                         drect_border(vx-3, vy-3, vx+3, vy+3, C_NONE, 1, C_WHITE)

        # Poly Working Preview
        if st.tool == TOOL_POLY and st.poly_points:
            pts = st.poly_points
            
            # Draw start closure hint (Circle at first point)
            sx0, sy0 = self.world_to_screen(pts[0][0], pts[0][1])
            dcircle(sx0, sy0, 6, C_NONE, COL_POLY_PREVIEW)
            
            v_screen = []
            for pt in pts:
                sx, sy = self.world_to_screen(pt[0], pt[1])
                v_screen.append(sx)
                v_screen.append(sy)
            
            if len(pts) >= 3:
                # Fill preview
                dpoly(v_screen, st.curr_fill, st.curr_stroke)
            elif len(pts) == 2:
                # Line preview
                 dline(v_screen[0], v_screen[1], v_screen[2], v_screen[3], st.curr_stroke)
            
            # Draw vertices
            for i in range(0, len(v_screen), 2):
                drect(v_screen[i]-2, v_screen[i+1]-2, v_screen[i]+2, v_screen[i+1]+2, COL_POLY_PREVIEW)

        # Reset window for UI overlays (ruler draws on top)
        dwindow_set(0, 0, SCREEN_W, SCREEN_H)

        # --- RULERS ---
        self.draw_rulers()

    def draw_rulers(self):
        st = self.state
        # Calc nice step (approx 50px screen spacing)
        target_px = 50
        world_step = target_px / st.zoom
        # Power of 10 nice step
        try:
            mag = math.floor(math.log10(world_step))
            power = 10 ** mag
            rel = world_step / power
            if rel < 2: step = 2 * power
            elif rel < 5: step = 5 * power
            else: step = 10 * power
        except: step = 50 # fallback
        
        sub_step = step / 5.0
        
        # Geometry
        ry_top = HEADER_H
        ry_bottom = SCREEN_H - FOOTER_H
        
        # Draw Backgrounds
        cgui.fill_rect(0, ry_top, SCREEN_W, 6, C_WHITE)
        cgui.fill_rect(0, ry_top, 6, ry_bottom - ry_top, C_WHITE)
        dline(0, ry_top+5, SCREEN_W, ry_top+5, C_BLACK) # Boundary
        dline(5, ry_top, 5, ry_bottom, C_BLACK)
        
        # Horizontal
        wx_start, _ = self.screen_to_world(0, 0)
        wx_end, _ = self.screen_to_world(SCREEN_W, 0)
        
        i_start = int(wx_start / sub_step) - 1
        i_end = int(wx_end / sub_step) + 1
        
        for i in range(i_start, i_end + 1):
             val = i * sub_step
             sx, _ = self.world_to_screen(val, 0)
             if 0 <= sx < SCREEN_W:
                 # Check major
                 # Use rough float equality tolerance
                 nearest_major = round(val / step) * step
                 is_major = abs(val - nearest_major) < (sub_step * 0.1)
                 
                 lng = 5 if is_major else 2
                 dline(sx, ry_top, sx, ry_top + lng, C_BLACK)

        # Vertical
        _, wy_start = self.screen_to_world(0, ry_top)
        _, wy_end = self.screen_to_world(0, ry_bottom)
        
        j_start = int(wy_start / sub_step) - 1
        j_end = int(wy_end / sub_step) + 1
        
        for j in range(j_start, j_end + 1):
             val = j * sub_step
             _, sy = self.world_to_screen(0, val)
             if ry_top <= sy < ry_bottom:
                 nearest_major = round(val / step) * step
                 is_major = abs(val - nearest_major) < (sub_step * 0.1)
                 
                 lng = 5 if is_major else 2
                 dline(0, sy, lng, sy, C_BLACK)
        
        # Drag Cursor Indicator in Ruler
        if hasattr(self, 'drag_cursor_pos') and self.drag_cursor_pos:
            cx, cy = self.drag_cursor_pos
            # Draw tick markers in ruler area only
            dline(cx, ry_top, cx, ry_top+10, C_RGB(31,0,0))
            dline(0, cy, 10, cy, C_RGB(31,0,0))

    def handle_tool(self, ev):
        st = self.state
        wx, wy = self.screen_to_world(ev.x, ev.y)
        
        if st.tool == TOOL_POLY:
            if ev.type == KEYEV_TOUCH_DOWN:
                if not st.poly_points:
                    st.poly_points.append((wx, wy))
                else:
                    # Check closure (dist < 15 screen pixels)
                    sx0, sy0 = self.world_to_screen(st.poly_points[0][0], st.poly_points[0][1])
                    d_sq = (ev.x - sx0)**2 + (ev.y - sy0)**2
                    if d_sq < 225: # 15^2
                        # Close
                        if len(st.poly_points) >= 3:
                            flat = [c for pt in st.poly_points for c in pt]
                            st.add_object(SVFObject(svf.CMD_POLY, vertices=flat, 
                                                    fill=st.curr_fill, stroke=st.curr_stroke))
                        st.poly_points = []
                    else:
                        st.poly_points.append((wx, wy))
                    self.needs_redraw = True
            
            elif ev.type == KEYEV_TOUCH_DRAG and st.poly_points:
                # Update last point pos while dragging for precise placement
                st.poly_points[-1] = (wx, wy)
                self.needs_redraw = True

            elif ev.type == KEYEV_DOWN and ev.key == KEY_SHIFT:
                # Finish open poly
                if len(st.poly_points) >= 3:
                     flat = [c for pt in st.poly_points for c in pt]
                     st.add_object(SVFObject(svf.CMD_POLY, vertices=flat, 
                                            fill=st.curr_fill, stroke=st.curr_stroke))
                st.poly_points = []
        
        elif st.tool == TOOL_EDIT:
             self.handle_edit_tool(ev, wx, wy)
             
        elif st.tool == TOOL_SELECT:
             self.handle_select_tool(ev, wx, wy)
             
        elif st.tool == TOOL_RECT:
             self.handle_create_tool(ev, wx, wy, svf.CMD_RECT_B)
        elif st.tool == TOOL_CIRCLE:
             self.handle_create_tool(ev, wx, wy, svf.CMD_CIRCLE)
        elif st.tool == TOOL_LINE:
             self.handle_create_tool(ev, wx, wy, svf.CMD_LINE)
        elif st.tool == TOOL_VIEW:
             self.handle_view_tool(ev)

    def handle_view_tool(self, ev):
        st = self.state
        if ev.type == KEYEV_TOUCH_DOWN:
            self.drag_start_c = (st.cam_x, st.cam_y)
            self.drag_start_s = (ev.x, ev.y)
            self.drag_cursor_pos = (ev.x, ev.y)
            self.last_drag_time = time.time()
            self.drag_accum_x = 0
            self.drag_accum_y = 0
            
        elif ev.type == KEYEV_TOUCH_DRAG and hasattr(self, 'drag_start_s'):
            # Calculate raw delta from last event (not start)
            # Actually easier to track total delta from start
            dx_total = ev.x - self.drag_start_s[0]
            dy_total = ev.y - self.drag_start_s[1]
            
            # Snap Step for View Move (1 big tick = 5 small ticks)
            # st.snap_step is small tick.
            snap_unit = st.snap_step * 5 * st.zoom # in pixels
            
            # Quantize
            q_dx = round(dx_total / snap_unit) * snap_unit
            q_dy = round(dy_total / snap_unit) * snap_unit
            
            # Convert back to world units for camera
            # Camera moves opposite to drag? No, drag moves camera?
            # Usually drag scene: move mouse right -> cam x decreases (scene moves right)
            # Here: st.cam_x = start_c + dx means scene follows finger.
            
            st.cam_x = self.drag_start_c[0] + (q_dx / st.zoom)
            st.cam_y = self.drag_start_c[1] + (q_dy / st.zoom)

            # Stabilization/Ack logic
            self.drag_cursor_pos = (ev.x, ev.y)
            now = time.time()
            if now - self.last_drag_time > PERF_DRAG_TIME: # Debounce/Stable check
                 self.last_drag_time = now
                 self.needs_redraw = True
                 
        elif ev.type == KEYEV_TOUCH_UP:
             self.drag_cursor_pos = None
             self.needs_redraw = True

    def handle_create_tool(self, ev, wx, wy, type_id):
        st = self.state
        if ev.type == KEYEV_TOUCH_DOWN:
            self.drag_start = (wx, wy)
            self.drag_cursor_pos = (ev.x, ev.y)
            self.last_drag_time = time.time()
            props = {'fill': st.curr_fill, 'stroke': st.curr_stroke}
            if type_id == svf.CMD_RECT_B:
                props.update({'x1':wx, 'y1':wy, 'x2':wx+1, 'y2':wy+1, 'width':1})
            elif type_id == svf.CMD_CIRCLE:
                props.update({'cx':wx, 'cy':wy, 'r':1})
            elif type_id == svf.CMD_LINE:
                props.update({'x1':wx, 'y1':wy, 'x2':wx, 'y2':wy})
            
            new_obj = SVFObject(type_id, **props)
            st.add_object(new_obj)
            self.drag_obj = new_obj
            
        elif ev.type == KEYEV_TOUCH_DRAG and hasattr(self, 'drag_obj'):
            o = self.drag_obj
            if o.type == svf.CMD_RECT_B or o.type == svf.CMD_LINE:
                o.props['x2'] = wx
                o.props['y2'] = wy
            elif o.type == svf.CMD_CIRCLE:
                dx = wx - o.props['cx']
                dy = wy - o.props['cy']
                o.props['r'] = int(math.sqrt(dx*dx + dy*dy))
            
            self.drag_cursor_pos = (ev.x, ev.y)
            now = time.time()
            if now - self.last_drag_time > PERF_DRAG_TIME:
                self.last_drag_time = now
                self.needs_redraw = True
            
        elif ev.type == KEYEV_TOUCH_UP:
            self.drag_cursor_pos = None
            self.needs_redraw = True
            if hasattr(self, 'drag_obj'): del self.drag_obj

    def handle_select_tool(self, ev, wx, wy):
        st = self.state
        if ev.type == KEYEV_TOUCH_DOWN:
            hit = -1
            # Hit test (reverse order)
            for i in range(len(st.objects)-1, -1, -1):
                o = st.objects[i]
                bx, by, bw, bh = o.bounds()
                if bx <= wx <= bx+bw and by <= wy <= by+bh:
                    hit = i
                    break
            
            if hit != st.selected_idx:
                st.selected_idx = hit
                if hit != -1:
                    o = st.objects[hit]
                    st.curr_fill = o.props.get('fill', st.curr_fill)
                    st.curr_stroke = o.props.get('stroke', st.curr_stroke)
                self.needs_redraw = True
            
            if hit != -1:
                st.push_history()
                self.drag_start_w = (wx, wy)
                self.drag_init_props = st.objects[hit].copy().props
                self.drag_cursor_pos = (ev.x, ev.y)
                self.last_drag_time = time.time()

        elif ev.type == KEYEV_TOUCH_DRAG and st.selected_idx != -1 and hasattr(self, 'drag_init_props'):
            dx = wx - self.drag_start_w[0]
            dy = wy - self.drag_start_w[1]
            o = st.objects[st.selected_idx]
            p = self.drag_init_props
            
            if 'x1' in p:
                o.props['x1'] = p['x1'] + dx
                o.props['y1'] = p['y1'] + dy
                o.props['x2'] = p['x2'] + dx
                o.props['y2'] = p['y2'] + dy
            elif 'cx' in p:
                o.props['cx'] = p['cx'] + dx
                o.props['cy'] = p['cy'] + dy
            elif 'vertices' in p:
                ov = p['vertices']
                nv = []
                for i in range(len(ov)):
                    nv.append(ov[i] + (dx if i%2==0 else dy))
                o.props['vertices'] = nv
            
            self.drag_cursor_pos = (ev.x, ev.y)
            now = time.time()
            if now - self.last_drag_time > PERF_DRAG_TIME:
                self.last_drag_time = now
                self.needs_redraw = True
            
        elif ev.type == KEYEV_TOUCH_UP:
            self.drag_cursor_pos = None
            self.needs_redraw = True
            if hasattr(self, 'drag_init_props'): del self.drag_init_props

    def handle_edit_tool(self, ev, wx, wy):
        st = self.state
        
        # 1. Check Handle Hit (if selected)
        handle_hit_idx = -1
        
        if st.selected_idx != -1:
             obj = st.objects[st.selected_idx]
             
             # Calculate handles
             handles = []
             if obj.type == svf.CMD_POLY:
                 verts = obj.props['vertices']
                 for i in range(0, len(verts), 2): handles.append((verts[i], verts[i+1]))
             elif obj.type == svf.CMD_RECT_B or obj.type == svf.CMD_RECT:
                 p = obj.props
                 handles = [(p['x1'], p['y1']), (p['x2'], p['y1']), (p['x2'], p['y2']), (p['x1'], p['y2'])]
             elif obj.type == svf.CMD_CIRCLE:
                 p = obj.props
                 handles = [(p['cx'], p['cy']), (p['cx'] + p['r'], p['cy'])]
             elif obj.type == svf.CMD_LINE:
                 p = obj.props
                 handles = [(p['x1'], p['y1']), (p['x2'], p['y2'])]
             
             if ev.type == KEYEV_TOUCH_DOWN:
                 best = 20
                 for i, (hx, hy) in enumerate(handles):
                     sx, sy = self.world_to_screen(hx, hy)
                     dist = abs(ev.x - sx) + abs(ev.y - sy)
                     if dist < best:
                         best = dist
                         handle_hit_idx = i
        
        if ev.type == KEYEV_TOUCH_DOWN:
             if handle_hit_idx != -1:
                 # Check Rm Mode
                 if st.rm_mode and st.selected_idx != -1:
                     obj = st.objects[st.selected_idx]
                     if obj.type == svf.CMD_POLY:
                         verts = obj.props['vertices']
                         if len(verts) > 6: # > 3 points
                             st.push_history()
                             # handle_hit_idx corresponds to point index
                             idx = handle_hit_idx
                             verts.pop(idx*2)
                             verts.pop(idx*2) # Remove y, shift rest
                             self.needs_redraw = True
                             return
                 
                 # Start Drag Handle
                 st.push_history()
                 self.drag_handle_id = handle_hit_idx
                 self.drag_cursor_pos = (ev.x, ev.y)
                 self.last_drag_time = time.time()
             else:
                 # 2. Check Object Hit (Select)
                 hit = -1
                 for i in range(len(st.objects)-1, -1, -1):
                    o = st.objects[i]
                    bx, by, bw, bh = o.bounds()
                    if bx <= wx <= bx+bw and by <= wy <= by+bh:
                        hit = i
                        break
                 
                 if hit != -1:
                     if hit != st.selected_idx:
                        st.selected_idx = hit
                        o = st.objects[hit]
                        st.curr_fill = o.props.get('fill', st.curr_fill)
                        st.curr_stroke = o.props.get('stroke', st.curr_stroke)
                        self.needs_redraw = True
                 elif st.selected_idx != -1:
                     # Deselect if clicked empty space
                     st.selected_idx = -1
                     self.needs_redraw = True
                 
                 # 3. Check Poly Insert (if still selected and poly and no handle hit)
                 if st.selected_idx != -1 and st.objects[st.selected_idx].type == svf.CMD_POLY and handle_hit_idx == -1:
                     obj = st.objects[st.selected_idx]
                     verts = obj.props['vertices']
                     best_seg_dist = 400
                     ins_idx = -1
                     for i in range(0, len(verts), 2):
                         v1x, v1y = verts[i], verts[i+1]
                         ni = (i + 2) % len(verts)
                         v2x, v2y = verts[ni], verts[ni+1]
                         s1x, s1y = self.world_to_screen(v1x, v1y)
                         s2x, s2y = self.world_to_screen(v2x, v2y)
                         d = pt_seg_dist_sq(ev.x, ev.y, s1x, s1y, s2x, s2y)
                         if d < best_seg_dist:
                             best_seg_dist = d
                             ins_idx = ni
                     if ins_idx != -1:
                          st.push_history()
                          verts.insert(ins_idx, wy)
                          verts.insert(ins_idx, wx)
                          self.drag_handle_id = ins_idx // 2
                          self.drag_cursor_pos = (ev.x, ev.y)
                          self.last_drag_time = time.time()
                          self.needs_redraw = True

        elif ev.type == KEYEV_TOUCH_DRAG and hasattr(self, 'drag_handle_id') and st.selected_idx != -1:
             # Drag Handle Logic
             idx = self.drag_handle_id
             obj = st.objects[st.selected_idx]
             p = obj.props
             
             if obj.type == svf.CMD_POLY:
                 if idx*2+1 < len(p['vertices']):
                     p['vertices'][idx*2] = wx
                     p['vertices'][idx*2+1] = wy
             elif obj.type == svf.CMD_RECT_B or obj.type == svf.CMD_RECT:
                 # 0:TL, 1:TR, 2:BR, 3:BL
                 if idx == 0: p['x1'] = wx; p['y1'] = wy
                 elif idx == 1: p['x2'] = wx; p['y1'] = wy
                 elif idx == 2: p['x2'] = wx; p['y2'] = wy
                 elif idx == 3: p['x1'] = wx; p['y2'] = wy
             elif obj.type == svf.CMD_CIRCLE:
                 if idx == 0: p['cx'] = wx; p['cy'] = wy
                 elif idx == 1: 
                     dx = wx - p['cx']; dy = wy - p['cy']
                     p['r'] = int(math.sqrt(dx*dx + dy*dy))
             elif obj.type == svf.CMD_LINE:
                 if idx == 0: p['x1'] = wx; p['y1'] = wy
                 elif idx == 1: p['x2'] = wx; p['y2'] = wy
             
             self.drag_cursor_pos = (ev.x, ev.y)
             now = time.time()
             if now - self.last_drag_time > PERF_DRAG_TIME:
                self.last_drag_time = now
                self.needs_redraw = True

        elif ev.type == KEYEV_TOUCH_UP:
             self.drag_cursor_pos = None
             self.needs_redraw = True
             if hasattr(self, 'drag_handle_id'): del self.drag_handle_id


    def run(self):
        st = self.state
        while self.running:
            if self.needs_redraw:
                self.draw_canvas()
                self.draw_ui()
                dupdate()
                self.needs_redraw = False
            
            cleareventflips()
            ev = pollevent()
            if ev.type == KEYEV_TOUCH_DOWN or ev.type == KEYEV_TOUCH_DRAG:
                # Glitch rejection
                if not (0 <= ev.x < SCREEN_W and 0 <= ev.y < SCREEN_H): continue

            if ev.type == KEYEV_TOUCH_DOWN:
                # Header hit
                if ev.y < HEADER_H:
                    if ev.x < 45: # Menu
                        menu_opts = ["New", "Open", "Save", "Quit"]
                        res = cinput.pick(menu_opts, "Menu")
                        if res == "New": 
                            if cinput.ask("New?", "Clear all?"):
                                st.objects = []; st.history=[]; st.poly_points=[]; self.needs_redraw=True
                        elif res == "Open":
                            fn = cinput.input("Filename:", "drawing.svf")
                            if fn: self.load_file(fn)
                        elif res == "Save":
                            fn = cinput.input("Filename:", "drawing.svf")
                            if fn: self.save_file(fn)
                        elif res == "Quit": self.running = False
                    elif 50 <= ev.x < 90: self.action_undo() # Undo
                    elif 95 <= ev.x < 135: self.action_redo() # Redo
                    elif 145 <= ev.x < 195: # Edit Popover
                        st.active_popover = POP_EDIT if st.active_popover != POP_EDIT else POP_NONE
                        self.needs_redraw = True
                    elif 200 <= ev.x < 245: # Opt Popover
                        st.active_popover = POP_OPT if st.active_popover != POP_OPT else POP_NONE
                        self.needs_redraw = True
                    # Adv Popover
                    elif ev.x > SCREEN_W - 50:
                        st.active_popover = POP_ADV if st.active_popover != POP_ADV else POP_NONE
                        self.needs_redraw = True
                    continue

                # Bottom Bar hit
                if ev.y > SCREEN_H - FOOTER_H:
                    if ev.x < 50:
                        st.active_popover = POP_TOOLS if st.active_popover != POP_TOOLS else POP_NONE
                        self.needs_redraw = True
                    elif 50 < ev.x < 100: # Fill
                         while True:
                             if pollevent().type == KEYEV_TOUCH_UP: break
                             time.sleep(0.01)
                         picker = cgui.ColorPicker(st.curr_fill)
                         col = picker.run()
                         if col is not None: 
                             st.curr_fill = col
                             if st.selected_idx != -1: st.objects[st.selected_idx].props['fill'] = col
                         self.needs_redraw = True
                    elif 100 < ev.x < 150: # Stroke
                         while True:
                             if pollevent().type == KEYEV_TOUCH_UP: break
                             time.sleep(0.01)
                         picker = cgui.ColorPicker(st.curr_stroke)
                         col = picker.run()
                         if col is not None: 
                             st.curr_stroke = col
                             if st.selected_idx != -1: st.objects[st.selected_idx].props['stroke'] = col
                         self.needs_redraw = True
                    elif 155 <= ev.x < 195: # Rm Button
                         if st.tool == TOOL_EDIT:
                             st.rm_mode = not st.rm_mode
                             self.needs_redraw = True
                    elif ev.x > SCREEN_W - 50:
                        st.active_popover = POP_LAYERS if st.active_popover != POP_LAYERS else POP_NONE
                        self.needs_redraw = True
                    continue

                # POPOVERS
                if st.active_popover != POP_NONE:
                    hit_pop = False
                    
                    if st.active_popover == POP_TOOLS:
                        # Bottom Left
                        ph = len(TOOL_NAMES) * (BUTTON_H+2) + 10
                        py = SCREEN_H - FOOTER_H - ph
                        if 5 <= ev.x <= 115 and py <= ev.y <= SCREEN_H - FOOTER_H:
                            hit_pop = True
                            rel_y = ev.y - (py + 5)
                            idx = rel_y // (BUTTON_H+2)
                            # Auto-save poly if switching away
                            if st.tool == TOOL_POLY and len(st.poly_points) >= 3:
                                 flat = [c for pt in st.poly_points for c in pt]
                                 st.add_object(SVFObject(svf.CMD_POLY, vertices=flat, 
                                                        fill=st.curr_fill, stroke=st.curr_stroke))
                            st.poly_points = []
                            
                            keys = list(TOOL_NAMES.keys())
                            if 0 <= idx < len(keys):
                                st.tool = keys[idx]
                                st.active_popover = POP_NONE
                                self.needs_redraw = True
                                
                    elif st.active_popover == POP_EDIT:
                        # Top Center
                        px = 145
                        ph = 5 * (BUTTON_H+2) + 10
                        if px <= ev.x <= px+100 and HEADER_H <= ev.y <= HEADER_H + ph:
                            hit_pop = True
                            rel_y = ev.y - (HEADER_H + 5)
                            idx = rel_y // (BUTTON_H+2)
                            if idx == 0: self.action_cut()
                            elif idx == 1: self.action_copy()
                            elif idx == 2: self.action_paste()
                            elif idx == 3: self.action_delete()
                            elif idx == 4: i = st.selected_idx; st.selected_idx = -1; st.active_popover = POP_NONE; self.needs_redraw=True
                    
                    elif st.active_popover == POP_OPT:
                         px = 200
                         w = 110
                         ph = BUTTON_H + 10
                         if px <= ev.x <= px+w and HEADER_H <= ev.y <= HEADER_H + ph:
                             hit_pop = True
                             st.snap_active = not st.snap_active
                             # Recalc immediately? 
                             st.calculate_snap_step() 
                             self.needs_redraw = True

                    elif st.active_popover == POP_LAYERS:
                        # Full Right Panel
                        lx = SCREEN_W - LAYER_PANEL_W
                        if ev.x > lx:
                            hit_pop = True
                            # Buttons check
                            by = SCREEN_H - FOOTER_H - 40
                            if ev.y > by:
                                # Adjusted hit regions for [Up][Dn][Ren]
                                if lx + 5 <= ev.x <= lx + 50: self.action_layer_move(True) # Up
                                elif lx + 55 <= ev.x <= lx + 100: self.action_layer_move(False) # Dn
                                elif lx + 105 <= ev.x <= lx + 145: # Rename
                                     if st.selected_idx != -1:
                                         obj = st.objects[st.selected_idx]
                                         curr = obj.props.get('name', f"Object {st.selected_idx}")
                                         new_name = cinput.input("Rename Layer", curr)
                                         if new_name:
                                             obj.props['name'] = new_name
                                             self.needs_redraw = True
                            else:
                                # List Select
                                rel_y = ev.y - (HEADER_H + 25)
                                idx = rel_y // 42
                                real_idx = len(st.objects) - 1 - idx
                                if 0 <= real_idx < len(st.objects):
                                    st.selected_idx = real_idx
                                    self.needs_redraw = True

                    elif st.active_popover == POP_ADV:
                        # Top Right
                         w = 130
                         px = SCREEN_W - w
                         ph = 140
                         if ev.x > px and HEADER_H <= ev.y <= HEADER_H + ph:
                             hit_pop = True
                             # Handle input
                             if st.selected_idx != -1:
                                 obj = st.objects[st.selected_idx]
                                 # X Input
                                 if HEADER_H+25 <= ev.y <= HEADER_H+45:
                                     val = cinput.input("Set X", str(obj.props.get('x1', obj.props.get('cx', 0))))
                                     if val and val.isdigit():
                                         dx = int(val) - obj.props.get('x1', obj.props.get('cx', 0))
                                         # Move relative
                                         self.drag_start_w = (0,0); self.drag_init_props = obj.props.copy()
                                         # ...Reuse move logic or set directly? Set directly is easier but complex for polys
                                         # For now just shift x1/cx
                                         if 'x1' in obj.props:
                                              diff = int(val) - obj.props['x1']
                                              obj.props['x1'] += diff
                                              obj.props['x2'] += diff
                                              obj.props['y1'] += 0
                                              obj.props['y2'] += 0
                                         elif 'cx' in obj.props:
                                              obj.props['cx'] = int(val)
                                         self.needs_redraw = True
                                 # Y Input
                                 elif HEADER_H+50 <= ev.y <= HEADER_H+70:
                                     val = cinput.input("Set Y", str(obj.props.get('y1', obj.props.get('cy', 0))))
                                     if val and val.isdigit():
                                          if 'y1' in obj.props:
                                              diff = int(val) - obj.props['y1']
                                              obj.props['y1'] += diff
                                              obj.props['y2'] += diff
                                          elif 'cy' in obj.props:
                                              obj.props['cy'] = int(val)
                                          self.needs_redraw = True


                    if not hit_pop:
                        # Clicked outside
                        if st.tool == TOOL_POLY and st.poly_points:
                            pass # If drawing poly, don't close popover? Actually usually modal.
                        st.active_popover = POP_NONE
                        self.needs_redraw = True
                        continue # Don't pass through to canvas
                    else:
                        continue # Handled by popover

                # Canvas
                self.handle_tool(ev)

            elif ev.type == KEYEV_TOUCH_DRAG or ev.type == KEYEV_TOUCH_UP:
                if st.active_popover == POP_NONE:
                     if not (ev.y < HEADER_H) and not (ev.y > SCREEN_H - FOOTER_H):
                        self.handle_tool(ev)

            # Key handling for Shift (Poly finish)
            elif ev.type == KEYEV_DOWN:
                 # View/Zoom Controls
                 if st.tool == TOOL_VIEW:
                     move_step = st.snap_step if st.snap_active else (10 / st.zoom)
                     if ev.key == KEY_LEFT: st.cam_x += move_step; self.needs_redraw = True
                     elif ev.key == KEY_RIGHT: st.cam_x -= move_step; self.needs_redraw = True
                     elif ev.key == KEY_UP: st.cam_y += move_step; self.needs_redraw = True
                     elif ev.key == KEY_DOWN: st.cam_y -= move_step; self.needs_redraw = True
                     elif ev.key == KEY_PLUS: # Zoom In
                         st.zoom *= 1.1
                         st.cam_x = st.cam_x * 1.1 
                         st.cam_y = st.cam_y * 1.1
                         self.needs_redraw = True
                     elif ev.key == KEY_MINUS: # Zoom Out
                         st.zoom /= 1.1
                         st.cam_x = st.cam_x / 1.1
                         st.cam_y = st.cam_y / 1.1
                         self.needs_redraw = True
                 
                 elif st.tool == TOOL_SELECT and st.selected_idx != -1:
                     move_step = st.snap_step if st.snap_active else 1
                     d_x, d_y = 0, 0
                     if ev.key == KEY_LEFT: d_x = -move_step
                     elif ev.key == KEY_RIGHT: d_x = move_step
                     elif ev.key == KEY_UP: d_y = -move_step
                     elif ev.key == KEY_DOWN: d_y = move_step
                     
                     if d_x != 0 or d_y != 0:
                         o = st.objects[st.selected_idx]
                         if 'x1' in o.props:
                            o.props['x1'] += d_x; o.props['x2'] += d_x
                            o.props['y1'] += d_y; o.props['y2'] += d_y
                         elif 'cx' in o.props:
                            o.props['cx'] += d_x; o.props['cy'] += d_y
                         elif 'vertices' in o.props:
                            v = o.props['vertices']
                            for k in range(0, len(v), 2):
                                v[k] += d_x; v[k+1] += d_y
                         
                         self.needs_redraw = True

                 if ev.key == KEY_SHIFT and st.tool == TOOL_POLY:
                    self.handle_tool(ev)
                 elif ev.key == KEY_EXIT:
                    self.running = False
            
            time.sleep(0.01)

    def load_file(self, filename):
        try:
            with open(filename, "rb") as f: data = f.read()
            objs = svf.VectorDecoder(data).decode()
            
            # Apply 1/10 Scaling (Format default is 10x precision)
            scale_inv = 0.1 
            self.state.objects = []
            
            for o in objs:
                 t = o.pop('type')
                 # Scale props
                 if 'x1' in o: o['x1'] *= scale_inv; o['x2'] *= scale_inv
                 if 'y1' in o: o['y1'] *= scale_inv; o['y2'] *= scale_inv
                 if 'cx' in o: o['cx'] *= scale_inv; o['cy'] *= scale_inv; o['r'] *= scale_inv
                 if 'vertices' in o:
                     o['vertices'] = [v * scale_inv for v in o['vertices']]
                 
                 self.state.objects.append(SVFObject(t, **o))

            self.state.history = []
            self.state.poly_points = []
            self.needs_redraw = True
        except Exception as e: cgui.msgbox(str(e))

    def save_file(self, filename):
        comp = svf.VectorCompiler()
        
        SCALE = 10.0
        def to_int(val): return int(round(val * SCALE))
        
        # Calculate ViewBox (Bounding Box of all elements)
        max_w = 0
        max_h = 0
        
        for obj in self.state.objects:
             b = obj.bounds() # x, y, w, h
             # bounds returns unscaled pixels
             right = b[0] + b[2]
             bottom = b[1] + b[3]
             if right > max_w: max_w = right
             if bottom > max_h: max_h = bottom
             
        # Add a small padding? Or just use exact. 
        # User said "fit the elements".
        # Ensure at least non-zero?
        if max_w < 1: max_w = 320
        if max_h < 1: max_h = 528
        
        comp.add_viewbox(to_int(max_w), to_int(max_h))
        
        for obj in self.state.objects:
            t = obj.type
            p = obj.props
            f = p.get('fill', svf.BIN_C_NONE)
            s = p.get('stroke', svf.BIN_C_NONE)
            
            if t == svf.CMD_RECT_B or t == svf.CMD_RECT: 
                 comp.add_rect(to_int(p['x1']), to_int(p['y1']), to_int(p['x2']), to_int(p['y2']), f, s, p.get('width', 1))
            elif t == svf.CMD_CIRCLE: 
                 comp.add_circle(to_int(p['cx']), to_int(p['cy']), to_int(p['r']), f, s)
            elif t == svf.CMD_LINE: 
                 comp.add_line(to_int(p['x1']), to_int(p['y1']), to_int(p['x2']), to_int(p['y2']), s)
            elif t == svf.CMD_POLY: 
                 verts = [to_int(v) for v in p['vertices']]
                 comp.add_poly(verts, f, s)
            
            # Add name if present
            if 'name' in p and p['name']:
                comp.add_name(p['name'])
                 
        with open(filename, "wb") as f: f.write(comp.get_bytes())
        cgui.msgbox("Saved!")

app = SVFEditor()
app.run()
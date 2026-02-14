from gint import *
from .theme import *

class Button:
    def __init__(self, x, y, w, h, label, color=None):
        self.x, self.y, self.w, self.h = x, y, w, h
        self.label = label
        self.color = color if color else THEME['control_bg']
        self.pressed = False

    def draw(self):
        base_col = THEME['accent'] if self.pressed else self.color
        fill_rect(self.x, self.y, self.w, self.h, base_col)
        drect_border(self.x, self.y, self.x+self.w-1, self.y+self.h-1, C_NONE, 1, THEME['panel_border'])
        dtext_opt(self.x + self.w//2, self.y + self.h//2, THEME['text'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, self.label, -1)

    def hit(self, x, y):
        return self.x <= x < self.x + self.w and self.y <= y < self.y + self.h

class Slider:
    def __init__(self, x, y, w, h, min_v, max_v, current, label, gradient_gen=None, display_unit=""):
        self.x, self.y, self.w, self.h = x, y, w, h
        self.min = min_v
        self.max = max_v
        self.val = current
        self.label = label
        self.dragging = False
        self.gradient_gen = gradient_gen 
        self.display_unit = display_unit

    def draw_clear(self):
        """Clear the slider's full bounding box (label + track + knob overflow)."""
        fill_rect(self.x - 10, self.y - 14, self.w + 20, self.h + 16, THEME['bg'])

    def draw(self):
        val_str = f"{int(self.val)}{self.display_unit}"
        dtext_opt(self.x, self.y - 12, THEME['text'], C_NONE, DTEXT_LEFT, DTEXT_TOP, self.label, -1)
        dtext_opt(self.x + self.w, self.y - 12, THEME['text'], C_NONE, DTEXT_RIGHT, DTEXT_TOP, val_str, -1)
        
        track_h = 8
        track_y = self.y + (self.h - track_h) // 2
        
        if self.gradient_gen:
            steps = 32
            for i in range(steps):
                x_start = self.x + (i * self.w) // steps
                x_end = self.x + ((i + 1) * self.w) // steps
                pct = i / (steps - 1)
                col = self.gradient_gen(pct)
                fill_rect(x_start, track_y, x_end - x_start, track_h, col)
        else:
            fill_rect(self.x, track_y, self.w, track_h, THEME['control_bg'])
            
        drect_border(self.x, track_y, self.x + self.w - 1, track_y + track_h - 1, C_NONE, 1, THEME['text_dim'])
        
        range_v = self.max - self.min
        pct = (self.val - self.min) / range_v if range_v != 0 else 0
        kx = self.x + int(pct * self.w)
        dcircle(kx, track_y + track_h//2, 8, THEME['text'], C_BLACK)

    def update(self, x, y, type):
        if type == KEYEV_TOUCH_DOWN:
            # Hitbox slightly larger for easier touching
            if self.x - 15 <= x <= self.x + self.w + 15 and self.y - 10 <= y <= self.y + self.h + 10:
                self.dragging = True
        elif type == KEYEV_TOUCH_UP:
            self.dragging = False
            
        if self.dragging:
            pct = (x - self.x) / self.w
            pct = max(0.0, min(1.0, pct))
            self.val = self.min + pct * (self.max - self.min)
            return True
        return False

class TabGroup:
    def __init__(self, x, y, w, h, tabs):
        self.x, self.y, self.w, self.h = x, y, w, h
        self.tabs = tabs
        self.selected = 0
        self.tab_w = w // len(tabs)

    def draw(self):
        for i, t in enumerate(self.tabs):
            bx = self.x + i * self.tab_w
            bg = THEME['tab_active'] if i == self.selected else THEME['tab_inactive']
            fill_rect(bx, self.y, self.tab_w, self.h, bg)
            drect_border(bx, self.y, bx + self.tab_w, self.y + self.h, C_NONE, 1, THEME['panel_border'])
            dtext_opt(bx + self.tab_w//2, self.y + self.h//2, THEME['text'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, t, -1)

    def update(self, x, y, type):
        if type == KEYEV_TOUCH_DOWN:
            if self.x <= x <= self.x + self.w and self.y <= y <= self.y + self.h:
                self.selected = (x - self.x) // self.tab_w
                return True
        return False
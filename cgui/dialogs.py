from gint import *
import math
import cinput
import random
import time
from .theme import *
from .colormath import *
from .widgets import *

class ColorPicker:
    # Gradient block constants
    BLOCKS_X = 32
    BLOCKS_Y = 14
    CURSOR_R = 6  # Outer cursor radius + margin for tile overlap check

    def __init__(self, initial_color):
        # Master State is RGB
        self.r, self.g, self.b = unpack_color(initial_color)
        
        # HLS State for the rectangle picker
        self.h_hls, self.l_hls, self.s_hls = rgb_to_hls(self.r, self.g, self.b)
        
        # Other states
        self.h_hsb, self.s_hsb, self.v_hsb = rgb_to_hsb(self.r, self.g, self.b)
        self.c, self.m, self.y_cmyk, self.k = rgb_to_cmyk(self.r, self.g, self.b)

        # Layout Configuration
        self.picker_h = 100
        self.picker_y = HEADER_H + 5
        self.picker_w = SCREEN_W - 20
        self.picker_x = 10
        
        # Pre-calculate block sizes for gradient
        self.bw = self.picker_w // self.BLOCKS_X
        self.bh = self.picker_h // self.BLOCKS_Y
        
        self.tab_y = self.picker_y + self.picker_h + 10
        self.tabs = TabGroup(0, self.tab_y, SCREEN_W, 30, ["RGB", "HSB", "Pal", "CMYK", "Hex"])
        
        self.slider_y_start = self.tab_y + 53
        
        # Cursor tracking for partial patching
        self._cur_cx = -1
        self._cur_cy = -1
        
        # Preview box position (constant)
        self._pv_size = 30
        self._pv_x = SCREEN_W - self._pv_size - 15
        self._pv_y = HEADER_H + 10
        
        # Predefined Palette
        self.palette = [
            C_RGB(0,0,0), C_RGB(31,31,31), C_RGB(15,15,15), C_RGB(20,20,20),
            C_RGB(31,0,0), C_RGB(0,31,0), C_RGB(0,0,31), C_RGB(31,31,0),
            C_RGB(0,31,31), C_RGB(31,0,31), C_RGB(15,0,0), C_RGB(0,15,0),
            C_RGB(0,0,15), C_RGB(31,15,0), C_RGB(0,15,31), C_RGB(15,0,31),
            C_RGB(31,10,10), C_RGB(10,31,10), C_RGB(10,10,31), C_RGB(31,20,10),
            C_RGB(10,31,20), C_RGB(20,10,31), C_RGB(10,20,31), C_RGB(31,15,20),
            C_RGB(25,25,25), C_RGB(10,10,10), C_RGB(25,0,0), C_RGB(0,25,0),
            C_RGB(0,0,25), C_RGB(25,25,0), C_RGB(0,25,25), C_RGB(25,0,25)
        ]

    def sync_from_rgb(self):
        """Update all other color models based on current RGB"""
        self.h_hls, self.l_hls, self.s_hls = rgb_to_hls(self.r, self.g, self.b)
        self.h_hsb, self.s_hsb, self.v_hsb = rgb_to_hsb(self.r, self.g, self.b)
        self.c, self.m, self.y_cmyk, self.k = rgb_to_cmyk(self.r, self.g, self.b)

    def _calc_cursor_pos(self):
        """Get the crosshair pixel position from current HLS."""
        cx = self.picker_x + int((self.h_hls / 360.0) * self.picker_w)
        cy = self.picker_y + int((1.0 - self.l_hls) * self.picker_h)
        cx = max(self.picker_x, min(self.picker_x + self.picker_w, cx))
        cy = max(self.picker_y, min(self.picker_y + self.picker_h, cy))
        return cx, cy

    def _draw_gradient(self):
        """Draw the full HLS gradient. EXPENSIVE — call only once!"""
        bw, bh = self.bw, self.bh
        bx_count, by_count = self.BLOCKS_X, self.BLOCKS_Y
        px, py = self.picker_x, self.picker_y
        
        fill_rect(px, py, self.picker_w, self.picker_h, C_BLACK)
        for by in range(by_count):
            l_val = 1.0 - (by / (by_count - 1))
            for bx in range(bx_count):
                h_val = (bx / (bx_count - 1)) * 360
                r, g, b = hls_to_rgb(h_val, l_val, 1.0)
                fill_rect(px + bx*bw, py + by*bh, bw+1, bh+1, C_RGB(r, g, b))
        drect_border(px, py, px + self.picker_w, py + self.picker_h, C_NONE, 1, C_WHITE)

    def _draw_cursor(self, cx, cy):
        """Draw the crosshair circles at the given position."""
        dcircle(cx, cy, 4, C_BLACK, C_NONE)
        dcircle(cx, cy, 5, C_WHITE, C_NONE)

    def _patch_cursor(self):
        """Erase old cursor by re-rendering only the overlapping gradient tiles,
        then draw new cursor. Typically redraws ~4-8 tiles instead of all 448."""
        old_cx, old_cy = self._cur_cx, self._cur_cy
        new_cx, new_cy = self._calc_cursor_pos()
        
        bw, bh = self.bw, self.bh
        bx_count, by_count = self.BLOCKS_X, self.BLOCKS_Y
        px, py = self.picker_x, self.picker_y
        cr = self.CURSOR_R
        
        # Erase old cursor by redrawing only the tiles it overlapped
        if old_cx >= 0:
            # Determine range of blocks to update
            # Clamp to valid block indices
            start_by = max(0, (old_cy - cr - py) // bh)
            end_by = min(by_count, (old_cy + cr - py) // bh + 2)
            start_bx = max(0, (old_cx - cr - px) // bw)
            end_bx = min(bx_count, (old_cx + cr - px) // bw + 2)
            
            for tby in range(start_by, end_by):
                l_val = 1.0 - (tby / (by_count - 1))
                tile_y = py + tby * bh
                for tbx in range(start_bx, end_bx):
                    h_val = (tbx / (bx_count - 1)) * 360
                    tile_x = px + tbx * bw
                    r, g, b = hls_to_rgb(h_val, l_val, 1.0)
                    fill_rect(tile_x, tile_y, bw+1, bh+1, C_RGB(r, g, b))
        
        # Draw new cursor
        self._draw_cursor(new_cx, new_cy)
        self._cur_cx, self._cur_cy = new_cx, new_cy

    def _update_preview(self):
        """Redraw only the small color preview box."""
        cur_col = pack_color(self.r, self.g, self.b)
        fill_rect(self._pv_x, self._pv_y, self._pv_size, self._pv_size, cur_col)
        drect_border(self._pv_x, self._pv_y, self._pv_x+self._pv_size, self._pv_y+self._pv_size, C_NONE, 2, C_WHITE)

    def _update_tab_content(self, idx, s_r, s_g, s_b, s_h, s_s, s_v, s_c, s_m, s_y, s_k, btn_hex):
        """Clear and redraw only the slider/content area for the active tab."""
        # Clear the content region below tabs, above footer
        content_top = self.slider_y_start - 15
        content_bot = SCREEN_H - FOOTER_H
        fill_rect(0, content_top, SCREEN_W, content_bot - content_top, THEME['bg'])
        
        cur_col = pack_color(self.r, self.g, self.b)
        if idx == 0: # RGB
            s_r.val, s_g.val, s_b.val = self.r, self.g, self.b
            s_r.draw(); s_g.draw(); s_b.draw()
        elif idx == 1: # HSB
            s_h.val, s_s.val, s_v.val = self.h_hsb, self.s_hsb * 100, self.v_hsb * 100
            s_h.draw(); s_s.draw(); s_v.draw()
        elif idx == 2: # Palette
            cols = 4
            cw = (SCREEN_W - 40) // cols
            ch = 38
            for i, c in enumerate(self.palette):
                cx = 20 + (i % cols) * cw
                cy = self.slider_y_start + (i // cols) * ch
                fill_rect(cx, cy, cw-2, ch-2, c)
                if c == cur_col:
                    drect_border(cx, cy, cx+cw-2, cy+ch-2, C_NONE, 2, C_WHITE)
        elif idx == 3: # CMYK
            s_c.val, s_m.val, s_y.val, s_k.val = self.c, self.m, self.y_cmyk, self.k
            s_c.draw(); s_m.draw(); s_y.draw(); s_k.draw()
        elif idx == 4: # Hex
            dtext_opt(SCREEN_W//2, self.slider_y_start + 20, THEME['text'], C_NONE, DTEXT_CENTER, DTEXT_TOP, f"RGB565: 0x{cur_col:04X}", -1)
            r8, g8, b8 = int(self.r/31*255), int(self.g/31*255), int(self.b/31*255)
            dtext_opt(SCREEN_W//2, self.slider_y_start + 110, THEME['text'], C_NONE, DTEXT_CENTER, DTEXT_TOP, f"Hex: #{r8:02X}{g8:02X}{b8:02X}", -1)
            btn_hex.draw()

    def _update_slider(self, slider):
        """Clear and redraw a single slider."""
        slider.draw_clear()
        slider.draw()

    def update_hue_lightness_touch(self, x, y):
        rel_x = x - self.picker_x
        rel_y = y - self.picker_y
        h_pct = max(0.0, min(1.0, rel_x / self.picker_w))
        l_pct = max(0.0, min(1.0, rel_y / self.picker_h))
        self.h_hls = h_pct * 360
        self.l_hls = 1.0 - l_pct
        self.s_hls = 1.0
        self.r, self.g, self.b = hls_to_rgb(self.h_hls, self.l_hls, self.s_hls)
        self.sync_from_rgb()

    def _draw_full(self, btn_ok, btn_cn, btn_hex, s_r, s_g, s_b, s_h, s_s, s_v, s_c, s_m, s_y, s_k):
        """Full redraw of everything, including the expensive gradient. Called once on init and on tab switch."""
        fill_rect(0, 0, SCREEN_W, SCREEN_H, THEME['bg'])
        draw_header("Color Picker")
        self._draw_gradient()
        
        # Draw and track cursor
        cx, cy = self._calc_cursor_pos()
        self._draw_cursor(cx, cy)
        self._cur_cx, self._cur_cy = cx, cy
        
        self._update_preview()
        self.tabs.draw()
        self._update_tab_content(self.tabs.selected, s_r, s_g, s_b, s_h, s_s, s_v, s_c, s_m, s_y, s_k, btn_hex)
        btn_ok.draw()
        btn_cn.draw()
        dupdate()

    def run(self):
        btn_w = SCREEN_W // 2
        btn_ok = Button(btn_w, SCREEN_H - FOOTER_H, btn_w, FOOTER_H, "OK", THEME['ok_btn'])
        btn_cn = Button(0, SCREEN_H - FOOTER_H, btn_w, FOOTER_H, "Cancel", THEME['cancel_btn'])
        
        # RGB Sliders
        s_r = Slider(20, self.slider_y_start, SCREEN_W-40, 30, 0, 31, self.r, "Red", lambda p: pack_color(p*31, self.g, self.b))
        s_g = Slider(20, self.slider_y_start + 48, SCREEN_W-40, 30, 0, 31, self.g, "Green", lambda p: pack_color(self.r, p*31, self.b))
        s_b = Slider(20, self.slider_y_start + 96, SCREEN_W-40, 30, 0, 31, self.b, "Blue", lambda p: pack_color(self.r, self.g, p*31))

        # HSB Sliders
        s_h = Slider(20, self.slider_y_start, SCREEN_W-40, 30, 0, 360, 0, "Hue", lambda p: pack_color(*hsb_to_rgb(p*360, 1, 1)))
        s_s = Slider(20, self.slider_y_start + 48, SCREEN_W-40, 30, 0, 100, 100, "Sat", None, "%")
        s_v = Slider(20, self.slider_y_start + 96, SCREEN_W-40, 30, 0, 100, 100, "Bri", lambda p: pack_color(p*31, p*31, p*31), "%")

        # CMYK Sliders
        s_c = Slider(20, self.slider_y_start, SCREEN_W-40, 30, 0, 100, 0, "Cyan", lambda p: pack_color(0, 31*(1-p), 31*(1-p)), "%")
        s_m = Slider(20, self.slider_y_start+48, SCREEN_W-40, 30, 0, 100, 0, "Magenta", lambda p: pack_color(31*(1-p), 0, 31*(1-p)), "%")
        s_y = Slider(20, self.slider_y_start+96, SCREEN_W-40, 30, 0, 100, 0, "Yellow", lambda p: pack_color(31*(1-p), 31*(1-p), 0), "%")
        s_k = Slider(20, self.slider_y_start+144, SCREEN_W-40, 30, 0, 100, 0, "Black", lambda p: pack_color(31*(1-p), 31*(1-p), 31*(1-p)), "%")

        btn_hex = Button(60, self.slider_y_start + 50, SCREEN_W-120, 40, "Enter Hex Code")

        touch_latched = False
        dirty_full = True     # Full redraw (gradient + everything) — only on init & tab switch
        last_tab = self.tabs.selected
        
        while True:
            # === RENDERING (only what changed) ===
            if dirty_full:
                self._draw_full(btn_ok, btn_cn, btn_hex, s_r, s_g, s_b, s_h, s_s, s_v, s_c, s_m, s_y, s_k)
                dirty_full = False

            # === EVENT POLLING ===
            cleareventflips()
            ev = pollevent()
            events = []
            while ev.type != KEYEV_NONE:
                events.append(ev)
                ev = pollevent()

            touch = None
            for e in events:
                if e.type == KEYEV_TOUCH_DOWN and not touch_latched:
                    touch_latched = True
                    touch = e
                elif e.type == KEYEV_TOUCH_DRAG: touch = e
                elif e.type == KEYEV_TOUCH_UP:
                    touch_latched = False
                    touch = e
                    s_r.dragging = s_g.dragging = s_b.dragging = False
                    s_h.dragging = s_s.dragging = s_v.dragging = False
                    s_c.dragging = s_m.dragging = s_y.dragging = s_k.dragging = False
                    btn_ok.pressed = btn_cn.pressed = btn_hex.pressed = False

            if keypressed(KEY_EXE):
                clearevents()
                return None

            # === INPUT HANDLING (sets granular dirty flags per interaction) ===
            idx = self.tabs.selected
            needs_dupdate = False

            if touch:
                tx, ty = touch.x, touch.y
                
                # --- HSL Picker touch ---
                if self.picker_x <= tx <= self.picker_x + self.picker_w and \
                   self.picker_y <= ty <= self.picker_y + self.picker_h:
                    self.update_hue_lightness_touch(tx, ty)
                    # Partial: patch cursor + preview + active sliders
                    self._patch_cursor()
                    self._update_preview()
                    self._update_tab_content(idx, s_r, s_g, s_b, s_h, s_s, s_v, s_c, s_m, s_y, s_k, btn_hex)
                    needs_dupdate = True
                    
                # --- Footer buttons ---
                elif ty > SCREEN_H - FOOTER_H:
                    if touch.type == KEYEV_TOUCH_DOWN:
                        if btn_ok.hit(tx, ty):
                            btn_ok.pressed = True
                            btn_ok.draw()
                            needs_dupdate = True
                        if btn_cn.hit(tx, ty):
                            btn_cn.pressed = True
                            btn_cn.draw()
                            needs_dupdate = True
                    elif touch.type == KEYEV_TOUCH_UP:
                        if btn_ok.hit(tx, ty):
                            clearevents()
                            return pack_color(self.r, self.g, self.b)
                        if btn_cn.hit(tx, ty):
                            clearevents()
                            return None
                
                # --- Tabs ---
                elif self.tabs.update(tx, ty, touch.type):
                    if self.tabs.selected != last_tab:
                        last_tab = self.tabs.selected
                        # Tab changed — need full redraw for content area + tabs, but NOT gradient
                        self.tabs.draw()
                        self._update_tab_content(self.tabs.selected, s_r, s_g, s_b, s_h, s_s, s_v, s_c, s_m, s_y, s_k, btn_hex)
                        needs_dupdate = True
                
                # --- Sliders (based on active tab) ---
                elif idx == 0: # RGB
                    changed = False
                    if s_r.update(tx, ty, touch.type):
                        self._update_slider(s_r); changed = True
                    if s_g.update(tx, ty, touch.type):
                        self._update_slider(s_g); changed = True
                    if s_b.update(tx, ty, touch.type):
                        self._update_slider(s_b); changed = True
                    if changed:
                        self.r, self.g, self.b = s_r.val, s_g.val, s_b.val
                        self.sync_from_rgb()
                        self._patch_cursor()
                        self._update_preview()
                        needs_dupdate = True
                
                elif idx == 1: # HSB
                    changed = False
                    if s_h.update(tx, ty, touch.type):
                        self._update_slider(s_h); changed = True
                    if s_s.update(tx, ty, touch.type):
                        self._update_slider(s_s); changed = True
                    if s_v.update(tx, ty, touch.type):
                        self._update_slider(s_v); changed = True
                    if changed:
                        r, g, b = hsb_to_rgb(s_h.val, s_s.val/100.0, s_v.val/100.0)
                        self.r, self.g, self.b = r, g, b
                        self.sync_from_rgb()
                        self._patch_cursor()
                        self._update_preview()
                        needs_dupdate = True

                elif idx == 2: # Palette
                    if touch.type == KEYEV_TOUCH_DOWN:
                        cw = (SCREEN_W - 40) // 4
                        ch = 38
                        if 20 <= tx < 20 + 4*cw and self.slider_y_start <= ty:
                            c = (tx - 20) // cw
                            r = (ty - self.slider_y_start) // ch
                            pidx = r * 4 + c
                            if 0 <= pidx < len(self.palette):
                                self.r, self.g, self.b = unpack_color(self.palette[pidx])
                                self.sync_from_rgb()
                                self._patch_cursor()
                                self._update_preview()
                                # Redraw palette to update selection highlight
                                self._update_tab_content(idx, s_r, s_g, s_b, s_h, s_s, s_v, s_c, s_m, s_y, s_k, btn_hex)
                                needs_dupdate = True

                elif idx == 3: # CMYK
                    changed = False
                    if s_c.update(tx, ty, touch.type):
                        self._update_slider(s_c); changed = True
                    if s_m.update(tx, ty, touch.type):
                        self._update_slider(s_m); changed = True
                    if s_y.update(tx, ty, touch.type):
                        self._update_slider(s_y); changed = True
                    if s_k.update(tx, ty, touch.type):
                        self._update_slider(s_k); changed = True
                    if changed:
                        r, g, b = cmyk_to_rgb(s_c.val, s_m.val, s_y.val, s_k.val)
                        self.r, self.g, self.b = r, g, b
                        self.sync_from_rgb()
                        self._patch_cursor()
                        self._update_preview()
                        needs_dupdate = True
                
                elif idx == 4: # Hex
                    if touch.type == KEYEV_TOUCH_DOWN and btn_hex.hit(tx, ty):
                        btn_hex.pressed = True
                        btn_hex.draw()
                        needs_dupdate = True
                    elif touch.type == KEYEV_TOUCH_UP and btn_hex.hit(tx, ty):
                        clearevents()
                        hex_str = cinput.input("Hex Code (RRGGBB):", "")
                        if hex_str:
                            try:
                                v = int(hex_str, 16)
                                r = (v >> 16) & 0xFF
                                g = (v >> 8) & 0xFF
                                b = v & 0xFF
                                self.r = int(r * 31 / 255)
                                self.g = int(g * 31 / 255)
                                self.b = int(b * 31 / 255)
                                self.sync_from_rgb()
                                # Full content refresh
                                self._patch_cursor()
                                self._update_preview()
                                self._update_tab_content(idx, s_r, s_g, s_b, s_h, s_s, s_v, s_c, s_m, s_y, s_k, btn_hex)
                                needs_dupdate = True
                            except ValueError:
                                pass

            if needs_dupdate:
                dupdate()

            # Sleep to avoid busy-looping when idle
            time.sleep(0.02)

class BrushDialog:
    def __init__(self, size, spacing, spread, flow, opacity, shape):
        self.size = size
        self.spacing = spacing
        self.spread = spread
        self.flow = flow
        self.opacity = opacity
        self.shape = shape
        
        self.preview_h = 80
        self.y_start = HEADER_H + self.preview_h + 22

    def draw_preview(self):
        px, py = 20, HEADER_H + 10
        pw, ph = SCREEN_W - 40, self.preview_h
        
        # Clipping optimization
        dwindow_set(px, py, px+pw-1, py+ph-1)
        
        fill_rect(px, py, pw, ph, C_WHITE)
        drect_border(px, py, px+pw, py+ph, C_NONE, 1, THEME['text_dim'])
        
        center_y = py + ph // 2
        col = C_RGB(0, 10, 25)
        r = int(self.size // 2)
        
        rng = random
        
        # Optimization: Fewer points
        step = max(10, self.spacing * 2)
        total_w = pw - 20
        
        x = 10
        while x < total_w:
            # Simple sine wave
            offset_y = int(math.sin(x / 30) * (ph/3.5))
            
            jx = rng.randint(-int(self.spread), int(self.spread)) if self.spread > 0 else 0
            jy = rng.randint(-int(self.spread), int(self.spread)) if self.spread > 0 else 0
            dx, dy = px + x + jx, center_y + offset_y + jy
            
            if self.shape == 'circle': dcircle(int(dx), int(dy), r, col, col)
            elif self.shape == 'square': drect(int(dx-r), int(dy-r), int(dx+r), int(dy+r), col)
            elif self.shape == 'rect_v': drect(int(dx-max(1,r//2)), int(dy-r), int(dx+max(1,r//2)), int(dy+r), col)
            elif self.shape == 'oval': dellipse(int(dx-r), int(dy-max(1,r//2)), int(dx+r), int(dy+max(1,r//2)), col, col)
                
            x += step
            
        dwindow_set(0, 0, SCREEN_W, SCREEN_H)

    def _update_slider(self, slider):
        slider.draw_clear()
        slider.draw()

    def _draw_full(self, sl_size, sl_spac, sl_sprd, sl_flow, sl_opac, shapes, shape_y, btn_ok, btn_cn):
        """Full redraw of the brush dialog UI. Only called on init."""
        fill_rect(0, HEADER_H, SCREEN_W, SCREEN_H - HEADER_H, THEME['bg'])
        draw_header("Brush Settings")
        
        SLIDER_TEXT_Y_OFFSET = 12
        # Ensure we clear area where sliders draw text if needed, but fill_rect covers it.
        
        self.draw_preview()
        
        sl_size.val = self.size
        sl_spac.val = self.spacing
        sl_sprd.val = self.spread
        sl_flow.val = self.flow
        sl_opac.val = self.opacity
        
        sl_size.draw(); sl_spac.draw(); sl_sprd.draw(); sl_flow.draw(); sl_opac.draw()
        
        # Draw shapes row
        self._update_shapes(shapes, shape_y, None)
        
        btn_ok.draw(); btn_cn.draw()
        dupdate()

    def _update_shapes(self, shapes, shape_y, qw=None):
        if qw is None: qw = (SCREEN_W - 40) // 4
        
        # Clear shape area
        fill_rect(0, shape_y, SCREEN_W, 45, THEME['bg'])
        
        for i, s in enumerate(shapes):
            sx = 20 + i * qw
            sy = shape_y
            if s == self.shape: fill_rect(sx, sy, qw-2, 40, THEME['control_bg'])
            drect_border(sx, sy, sx+qw-2, sy+40, C_NONE, 1, THEME['accent'] if s == self.shape else THEME['text_dim'])
            cx, cy = sx + qw//2, sy + 20
            col = THEME['text']
            if s == 'circle': dcircle(cx, cy, 8, col, col)
            elif s == 'square': drect(cx-8, cy-8, cx+8, cy+8, col)
            elif s == 'rect_v': drect(cx-4, cy-8, cx+4, cy+8, col)
            elif s == 'oval': dellipse(cx-10, cy-5, cx+10, cy+5, col, col)

    def run(self):
        sl_size = Slider(20, self.y_start, SCREEN_W-40, 30, 1, 50, self.size, "Size", None, "px")
        sl_spac = Slider(20, self.y_start + 48, SCREEN_W-40, 30, 1, 50, self.spacing, "Spacing", None, "px")
        sl_sprd = Slider(20, self.y_start + 96, SCREEN_W-40, 30, 0, 50, self.spread, "Spread", None, "px")
        sl_flow = Slider(20, self.y_start + 144, SCREEN_W-40, 30, 0, 100, self.flow, "Flow", None, "%")
        sl_opac = Slider(20, self.y_start + 192, SCREEN_W-40, 30, 0, 100, self.opacity, "Opacity", None, "%")
        
        shape_y = self.y_start + 240
        shapes = ['circle', 'square', 'rect_v', 'oval']

        qw = (SCREEN_W - 40) // 4  # Shape button width, used for hit-testing

        btn_w = SCREEN_W // 2
        btn_ok = Button(btn_w, SCREEN_H - FOOTER_H, btn_w, FOOTER_H, "OK", THEME['ok_btn'])
        btn_cn = Button(0, SCREEN_H - FOOTER_H, btn_w, FOOTER_H, "Cancel", THEME['cancel_btn'])
        
        touch_latched = False
        dirty_full = True
        
        while True:
            # Only redraw when state has changed
            if dirty_full:
                self._draw_full(sl_size, sl_spac, sl_sprd, sl_flow, sl_opac, shapes, shape_y, btn_ok, btn_cn)
                dirty_full = False
            
            cleareventflips()
            ev = pollevent()
            events = []
            while ev.type != KEYEV_NONE:
                events.append(ev)
                ev = pollevent()
            
            touch = None
            for e in events:
                if e.type == KEYEV_TOUCH_DOWN and not touch_latched:
                    touch_latched = True
                    touch = e
                elif e.type == KEYEV_TOUCH_DRAG: touch = e
                elif e.type == KEYEV_TOUCH_UP:
                    touch_latched = False
                    touch = e
                    sl_size.dragging = sl_spac.dragging = sl_sprd.dragging = sl_flow.dragging = sl_opac.dragging = False
                    btn_ok.pressed = btn_cn.pressed = False

            if keypressed(KEY_EXIT):
                clearevents()
                return None

            needs_dupdate = False
            if touch:
                tx, ty = touch.x, touch.y
                
                # Check Footer
                if ty > SCREEN_H - FOOTER_H:
                    if touch.type == KEYEV_TOUCH_DOWN:
                        if btn_ok.hit(tx, ty):
                            btn_ok.pressed = True; btn_ok.draw(); needs_dupdate = True
                        if btn_cn.hit(tx, ty):
                            btn_cn.pressed = True; btn_cn.draw(); needs_dupdate = True
                    elif touch.type == KEYEV_TOUCH_UP:
                        if btn_ok.hit(tx, ty):
                            clearevents()
                            return {
                                'size': sl_size.val, 'spacing': sl_spac.val, 'spread': sl_sprd.val,
                                'flow': sl_flow.val, 'opacity': sl_opac.val, 'shape': self.shape
                            }
                        if btn_cn.hit(tx, ty):
                            clearevents()
                            return None

                # Check Shapes
                elif shape_y <= ty <= shape_y + 45:
                     if touch.type == KEYEV_TOUCH_DOWN and 20 <= tx < 20 + 4*qw:
                         idx = (tx - 20) // qw
                         if 0 <= idx < len(shapes):
                             self.shape = shapes[idx]
                             self._update_shapes(shapes, shape_y, qw)
                             self.draw_preview()
                             needs_dupdate = True
                
                # Check Sliders
                else:
                    changed = False
                    if sl_size.update(tx, ty, touch.type):
                        self.size = sl_size.val
                        self._update_slider(sl_size); changed = True
                    if sl_spac.update(tx, ty, touch.type):
                        self.spacing = sl_spac.val
                        self._update_slider(sl_spac); changed = True
                    if sl_sprd.update(tx, ty, touch.type):
                        self.spread = sl_sprd.val
                        self._update_slider(sl_sprd); changed = True
                    if sl_flow.update(tx, ty, touch.type):
                        self.flow = sl_flow.val
                        self._update_slider(sl_flow); changed = True
                    if sl_opac.update(tx, ty, touch.type):
                        self.opacity = sl_opac.val
                        self._update_slider(sl_opac); changed = True
                    
                    if changed:
                        self.draw_preview()
                        needs_dupdate = True

            if needs_dupdate:
                dupdate()

            time.sleep(0.02)
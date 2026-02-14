from gint import *
import time

# =============================================================================
# CONSTANTS & CONFIG
# =============================================================================

SCREEN_W = 320
SCREEN_H = 528

# Layout Dimensions
KBD_H = 260
TAB_H = 30
PICK_HEADER_H = 40
PICK_FOOTER_H = 45
PICK_ITEM_H = 50

# =============================================================================
# THEMES
# =============================================================================

def safe_rgb(r, g, b):
    return C_RGB(r, g, b)

THEMES = {
    'light': {
        'modal_bg': C_WHITE,
        'kbd_bg':   C_WHITE,
        'key_bg':   C_WHITE,
        'key_spec': safe_rgb(28, 29, 28), # Secondary (Light Grey)
        'key_out':  C_DARK,               # Dark (Unused for key borders now)
        'txt':      safe_rgb(4, 4, 4),
        'txt_dim':      safe_rgb(8, 8, 8),
        'accent':   safe_rgb(1, 11, 26),  # Deep Blue
        'txt_acc':  C_WHITE,
        'hl':       safe_rgb(28, 29, 28), # Highlight matches secondary
        'check':    C_WHITE
    },
    'dark': {
        'modal_bg': safe_rgb(7, 7, 8),
        'kbd_bg':   safe_rgb(7, 7, 8),
        'key_bg':   safe_rgb(7, 7, 8),
        'key_spec': safe_rgb(11, 11, 12), # Secondary (Dark Grey)
        'key_out':  safe_rgb(12, 19, 31),
        'txt':      C_WHITE,
        'txt_dim':      safe_rgb(8, 8, 8),
        'accent':   safe_rgb(12, 19, 31),
        'txt_acc':  C_WHITE,
        'hl':       safe_rgb(11, 11, 12),
        'check':    C_WHITE
    },
    'grey': {
        'modal_bg': C_LIGHT,
        'kbd_bg':   C_LIGHT,
        'key_bg':   C_WHITE,
        'key_spec': 0xCE59,
        'key_out':  C_BLACK,
        'txt':      C_BLACK,
        'txt_dim':      safe_rgb(8, 8, 8),
        'accent':   C_BLACK,
        'txt_acc':  C_WHITE,
        'hl':       0xCE59,
        'check':    C_WHITE
    }
}

def get_theme(name_or_dict) -> dict:
    if isinstance(name_or_dict, dict): return name_or_dict
    return THEMES.get(name_or_dict, THEMES['light'])

# =============================================================================
# KEYBOARD WIDGET
# =============================================================================

LAYOUTS = {
    'qwerty': [list("1234567890"), list("qwertyuiop"), list("asdfghjkl:"), list("zxcvbnm,._")],
    'azerty': [list("1234567890"), list("azertyuiop"), list("qsdfghjklm"), list("wxcvbn,._:")],
    'qwertz': [list("1234567890"), list("qwertzuiop"), list("asdfghjkl:"), list("yxcvbnm,._")],
    'abc':    [list("1234567890"), list("abcdefghij"), list("klmnopqrst"), list("uvwxyz,._:")]
}

LAYOUT_SYM = [
    list("1234567890"),
    list("@#$_&-+()/"),
    list("=\\<*\"':;!?"),
    list("{}[]^~`|<>") 
]

class Keyboard:
    def __init__(self, default_tab=0, enable_tabs=True, numpad_opts=None, theme='light', layout='qwerty'):
        self.y = SCREEN_H - KBD_H
        self.visible = True
        self.current_tab = default_tab
        self.enable_tabs = enable_tabs
        self.shift = False
        self.tabs = ["ABC", "Sym", "Math"]
        self.last_key = None
        self.numpad_opts = numpad_opts if numpad_opts else {'float': True, 'neg': True}
        
        self.theme: dict = get_theme(theme)
        self.layout_alpha = LAYOUTS.get(layout, LAYOUTS['qwerty'])
        if layout != 'qwerty':
            self.tabs[0] = layout.upper() if len(layout) <= 3 else "Txt"

    def draw_key(self, x, y, w, h, label, is_special=False, is_pressed=False, is_accent=False):
        t = self.theme
        # Background
        if is_pressed: bg = t['hl']
        elif is_accent: bg = t['accent']
        elif is_special: bg = t['key_spec']
        else: bg = t['key_bg']
            
        txt_col = t['txt_acc'] if is_accent else t['txt']
        # Soft Border using secondary color
        border_col = t['key_spec'] 
        
        drect(x + 1, y + 1, x + w - 1, y + h - 1, bg)
        drect_border(x, y, x + w, y + h, C_NONE, 1, border_col)
        dtext_opt(x + w//2, y + h//2, txt_col, C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, label, -1)

    def draw_tabs(self):
        t = self.theme
        tab_w = SCREEN_W // 3
        border_col = t['key_spec']
        for i, tab_name in enumerate(self.tabs):
            tx = i * tab_w
            is_active = (i == self.current_tab)
            bg = t['kbd_bg'] if is_active else t['key_spec']
            drect(tx, self.y, tx + tab_w, self.y + TAB_H, bg)
            drect_border(tx, self.y, tx + tab_w, self.y + TAB_H, C_NONE, 1, border_col)
            if is_active:
                drect(tx + 1, self.y + TAB_H - 1, tx + tab_w - 1, self.y + TAB_H + 1, t['kbd_bg'])
            dtext_opt(tx + tab_w//2, self.y + TAB_H//2, t['txt'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, tab_name, -1)

    def draw_grid(self):
        layout = LAYOUT_SYM if self.current_tab == 1 else self.layout_alpha
        grid_y = self.y + TAB_H
        row_h = 45 
        for r, row in enumerate(layout):
            count = len(row)
            kw = SCREEN_W // count
            for c, char in enumerate(row):
                kx = c * kw
                ky = grid_y + r * row_h
                label = char.upper() if (self.current_tab == 0 and self.shift) else char
                is_pressed = (self.last_key == label)
                self.draw_key(kx, ky, kw, row_h, label, False, is_pressed)

        # Bottom Control Row
        bot_y = grid_y + 4 * row_h
        bot_h = row_h
        self.draw_key(0, bot_y, 50, bot_h, "CAPS", True, self.shift, False)
        self.draw_key(50, bot_y, 50, bot_h, "<-", True, self.last_key == "BACKSPACE", False)
        self.draw_key(100, bot_y, 160, bot_h, "Space", False, self.last_key == " ", False)
        self.draw_key(260, bot_y, 60, bot_h, "EXE", False, self.last_key == "ENTER", True)

    def update_grid(self, x, y, type):
        grid_y = self.y + TAB_H
        row_h = 45
        row_idx = (y - grid_y) // row_h
        if 0 <= row_idx < 4:
            layout = LAYOUT_SYM if self.current_tab == 1 else self.layout_alpha
            if row_idx >= len(layout): return None
            row_chars = layout[row_idx]
            kw = SCREEN_W // len(row_chars)
            col_idx = min(len(row_chars)-1, max(0, x // kw))
            char = row_chars[col_idx]
            if self.current_tab == 0 and self.shift: char = char.upper()
            if type == KEYEV_TOUCH_DOWN: self.last_key = char
            return char
        elif row_idx == 4:
            cmd = None
            if x < 50:
                if type == KEYEV_TOUCH_DOWN: self.shift = not self.shift
            elif x < 100: cmd = "BACKSPACE"
            elif x < 260: cmd = " "
            else: cmd = "ENTER"
            if type == KEYEV_TOUCH_DOWN: self.last_key = cmd
            return cmd
        return None

    def get_math_rects(self):
        keys = []
        start_y = self.y + TAB_H
        total_h = KBD_H - TAB_H
        row_h = total_h // 4
        side_w = 50
        center_w = SCREEN_W - (side_w * 2)
        numpad_w = center_w // 3
        for i, char in enumerate(["+", "-", "*", "/"]):
            keys.append((0, start_y + i*row_h, side_w, row_h, char, False, True, False))
        r_chars = [("%", False, True, False), (" ", False, True, False), ("<-", "BACKSPACE", True, False), ("EXE", "ENTER", False, True)]
        for i, (disp, val, spec, acc) in enumerate(r_chars):
            keys.append((SCREEN_W - side_w, start_y + i*row_h, side_w, row_h, disp, val, spec, acc))
        nums = [["1","2","3"], ["4","5","6"], ["7","8","9"]]
        for r in range(3):
            for c in range(3):
                keys.append((side_w + c*numpad_w, start_y + r*row_h, numpad_w, row_h, nums[r][c], False, False, False))
        y_bot = start_y + 3*row_h
        unit_w = center_w // 6
        bot_row = [",", "#", "0", "=", "."]
        widths  = [1, 1, 2, 1, 1]
        cur_x = side_w
        for i, char in enumerate(bot_row):
            w = widths[i] * unit_w
            if i == len(bot_row) - 1: w = (side_w + center_w) - cur_x
            keys.append((cur_x, y_bot, w, row_h, char, False, False, False))
            cur_x += w
        return keys

    def get_numpad_rects(self):
        keys = []
        start_y = self.y 
        total_h = KBD_H
        row_h = total_h // 4
        action_w = 80
        digit_w = (SCREEN_W - action_w) // 3
        keys.append((SCREEN_W - action_w, start_y, action_w, row_h, "<-", "BACKSPACE", True, False))
        keys.append((SCREEN_W - action_w, start_y + row_h, action_w, row_h*3, "EXE", "ENTER", False, True))
        nums = [["1","2","3"], ["4","5","6"], ["7","8","9"]]
        for r in range(3):
            for c in range(3):
                keys.append((c*digit_w, start_y + r*row_h, digit_w, row_h, nums[r][c], False, False, False))
        y_bot = start_y + 3*row_h
        bot_keys = []
        if self.numpad_opts['neg']: bot_keys.append("-")
        bot_keys.append("0")
        if self.numpad_opts['float']: bot_keys.append(".")
        if len(bot_keys) > 0:
            bw = (SCREEN_W - action_w) // len(bot_keys)
            cur_x = 0
            for i, k in enumerate(bot_keys):
                w = bw
                if i == len(bot_keys) - 1: w = (SCREEN_W - action_w) - cur_x
                keys.append((cur_x, y_bot, w, row_h, k, False, False, False))
                cur_x += w
        return keys

    def draw_keys_from_rects(self, rects):
        for x, y, w, h, label, val, is_spec, is_acc in rects:
            check_val = val if val is not False else label
            is_pressed = (self.last_key == check_val)
            self.draw_key(x, y, w, h, label, is_spec, is_pressed, is_acc)

    def update_keys_from_rects(self, rects, x, y, type):
        for rx, ry, rw, rh, label, val, is_spec, is_acc in rects:
            if rx <= x < rx + rw and ry <= y < ry + rh:
                ret = val if val is not False else label
                if type == KEYEV_TOUCH_DOWN: self.last_key = ret
                return ret
        return None

    def draw(self):
        if not self.visible: return
        t = self.theme
        drect(0, self.y, SCREEN_W, SCREEN_H, t['kbd_bg'])
        dhline(self.y, t['key_spec'])
        if self.enable_tabs:
            self.draw_tabs()
            if self.current_tab == 2:
                self.draw_keys_from_rects(self.get_math_rects())
            else:
                self.draw_grid()
        else:
            self.draw_keys_from_rects(self.get_numpad_rects())

    def update(self, ev):
        # We only set visual feedback on TOUCH DOWN
        if ev.type == KEYEV_TOUCH_DOWN:
            self.last_key = None # Clear previous visual press
        
        if not self.visible: return None
        
        x, y = ev.x, ev.y
        if y < self.y: return None
        
        # Only process taps on tabs, ignore drags
        if self.enable_tabs and y < self.y + TAB_H:
            if ev.type == KEYEV_TOUCH_DOWN:
                tab_w = SCREEN_W // 3
                self.current_tab = min(2, max(0, x // tab_w))
            return None
            
        # Determine active update method
        method = None
        if not self.enable_tabs: method = lambda t: self.update_keys_from_rects(self.get_numpad_rects(), x, y, t)
        elif self.current_tab == 2: method = lambda t: self.update_keys_from_rects(self.get_math_rects(), x, y, t)
        else: method = lambda t: self.update_grid(x, y, t)
        
        return method(ev.type)

# =============================================================================
# LIST PICKER WIDGET
# =============================================================================

class ListPicker:
    def __init__(self, options, prompt="Select:", theme="light", multi=False):
        self.options = options
        self.prompt = prompt
        self.theme: dict = get_theme(theme)
        self.multi = multi
        self.selected_indices = set() if multi else {0}
        self.cursor_idx = 0
        self.page_start = 0
        
        self.header_h = PICK_HEADER_H
        self.footer_h = PICK_FOOTER_H
        self.item_h = PICK_ITEM_H
        self.view_h = SCREEN_H - self.header_h - self.footer_h
        self.items_per_page = self.view_h // self.item_h
        self.btn_w = 60
        self.last_action = None

    def draw_nav_btn(self, x, w, h, type, is_pressed):
        t = self.theme
        bg = t['hl'] if is_pressed else t['key_spec']
        y = SCREEN_H - h
        
        drect(x, y, x + w, SCREEN_H, bg)
        drect_border(x, y, x + w, SCREEN_H, C_NONE, 1, t['key_spec'])
        
        cx, cy = x + w//2, y + h//2
        col = t['txt']
        
        if type == "UP":
            dpoly([cx, cy-5, cx-5, cy+5, cx+5, cy+5], col, C_NONE)
        elif type == "DOWN":
            dpoly([cx, cy+5, cx-5, cy-5, cx+5, cy-5], col, C_NONE)

    def draw_checkbox(self, x, y, checked):
        t = self.theme
        sz = 20
        
        # Material style
        if checked:
            drect(x, y, x + sz, y + sz, t['accent'])
            # White checkmark
            c = t['check']
            dline(x+4, y+10, x+8, y+14, c)
            dline(x+8, y+14, x+15, y+5, c)
            # Thicken
            dline(x+4, y+11, x+8, y+15, c)
            dline(x+8, y+15, x+15, y+6, c)
        else:
            # Empty box with text color border
            drect_border(x, y, x + sz, y + sz, C_NONE, 2, t['txt'])

    def draw_close_icon(self, x, y, sz, col):
        # Draw X
        dline(x, y, x+sz, y+sz, col)
        dline(x, y+sz, x+sz, y, col)
        # Thicken
        dline(x+1, y, x+sz+1, y+sz, col)
        dline(x+1, y+sz, x+sz+1, y, col)

    def draw(self):
        t = self.theme
        dclear(t['modal_bg'])
        
        # Header
        drect(0, 0, SCREEN_W, self.header_h, t['accent'])
        dtext_opt(SCREEN_W//2, self.header_h//2, t['txt_acc'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, self.prompt, -1)
        
        # Close Button (Top Left) - Hitbox: 0-40, 0-HEADER_H
        self.draw_close_icon(15, 15, 10, t['txt_acc'])
        
        # List Area
        visible_end = min(len(self.options), self.page_start + self.items_per_page)
        y_start = self.header_h
        
        for i in range(self.page_start, visible_end):
            y = y_start + (i - self.page_start) * self.item_h
            
            is_cursor = (i == self.cursor_idx)
            is_checked = i in self.selected_indices
            
            # Selection Background -> Secondary Color
            bg = t['key_spec'] if is_cursor else t['modal_bg']
            txt_col = t['txt'] # Always text color for readability in list
            
            drect(0, y, SCREEN_W, y + self.item_h, bg)
            # Row Border -> Secondary Color
            drect_border(0, y, SCREEN_W, y + self.item_h, C_NONE, 1, t['key_spec'])
            
            x_txt = 20
            if self.multi:
                self.draw_checkbox(10, y + (self.item_h-20)//2, is_checked)
                x_txt = 40
            
            # Draw Item Text
            dtext_opt(x_txt, y + self.item_h//2, txt_col, C_NONE, DTEXT_LEFT, DTEXT_MIDDLE, str(self.options[i]), -1)

        # Vertical Scrollbar (Android style: on the list view)
        if len(self.options) > self.items_per_page:
            sb_w = 4
            sb_x = SCREEN_W - sb_w - 2
            sb_y = self.header_h
            sb_h = self.view_h
            
            # Thumb
            thumb_h = max(20, int((self.items_per_page / len(self.options)) * sb_h))
            scroll_pct = self.page_start / max(1, len(self.options) - self.items_per_page)
            scroll_pct = min(1.0, max(0.0, scroll_pct))
            
            thumb_y = sb_y + int(scroll_pct * (sb_h - thumb_h))
            
            # Draw Thumb (Accent color)
            drect(sb_x, thumb_y, sb_x + sb_w, thumb_y + thumb_h, t['accent'])

        # Footer
        fy = SCREEN_H - self.footer_h
        drect(0, fy, SCREEN_W, SCREEN_H, t['key_spec'])
        dhline(fy, t['key_spec']) # Seamless
        
        # Page Up (Left)
        self.draw_nav_btn(0, self.btn_w, self.footer_h, "UP", self.last_action == "PAGE_UP")
        
        # Page Down (Right)
        self.draw_nav_btn(SCREEN_W - self.btn_w, self.btn_w, self.footer_h, "DOWN", self.last_action == "PAGE_DOWN")
        
        # OK Button (Center)
        ok_pressed = (self.last_action == "OK")
        ok_bg = t['hl'] if ok_pressed else t['key_spec']
        ok_rect_x = self.btn_w
        ok_rect_w = SCREEN_W - 2 * self.btn_w
        
        drect(ok_rect_x, fy, ok_rect_x + ok_rect_w, SCREEN_H, ok_bg)
        drect_border(ok_rect_x, fy, ok_rect_x + ok_rect_w, SCREEN_H, C_NONE, 1, t['key_spec'])
        
        label = "OK" if self.multi else "Select"
        dtext_opt(SCREEN_W//2, fy + self.footer_h//2, t['txt'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, label, -1)

    def run(self):
        # We need a small cooldown state to prevent one tap from registering multiple times
        # on the next frame loop if touch is still held.
        # Simple latch: wait for TOUCH_UP before accepting next TOUCH_DOWN for clicks.
        touch_latched = False
        
        while True:
            self.draw()
            dupdate()
            
            # Important: Clear flips to track new physical key presses correctly
            cleareventflips()
            
            # Poll all events
            ev = pollevent()
            events = []
            while ev.type != KEYEV_NONE:
                events.append(ev)
                ev = pollevent()
            
            # 1. Handle Physical Keys (using keypressed for single-shot)
            if keypressed(KEY_EXIT):
                return None
            if keypressed(KEY_EXE):
                if self.multi:
                    if self.cursor_idx in self.selected_indices: self.selected_indices.remove(self.cursor_idx)
                    else: self.selected_indices.add(self.cursor_idx)
                else:
                    return self.options[self.cursor_idx]
            
            # Navigation (Repeatable keys is fine here, or change to keypressed if too fast)
            if keypressed(KEY_UP): self.cursor_idx = max(0, self.cursor_idx - 1)
            elif keypressed(KEY_DOWN): self.cursor_idx = min(len(self.options) - 1, self.cursor_idx + 1)
            elif keypressed(KEY_LEFT): self.cursor_idx = max(0, self.cursor_idx - self.items_per_page)
            elif keypressed(KEY_RIGHT): self.cursor_idx = min(len(self.options) - 1, self.cursor_idx + self.items_per_page)

            # 2. Handle Touch (Software Latch)
            touch_event = None
            for e in events:
                if e.type == KEYEV_TOUCH_UP:
                    touch_latched = False
                    self.last_action = None # Clear visual feedback
                elif e.type == KEYEV_TOUCH_DOWN and not touch_latched:
                    touch_latched = True
                    touch_event = e
            
            if touch_event:
                fy = SCREEN_H - self.footer_h
                # Header check (Close)
                if touch_event.y < self.header_h:
                    if touch_event.x < 40:
                        return None # Close menu
                
                # Footer check
                elif touch_event.y >= fy:
                    if touch_event.x < self.btn_w:
                        self.last_action = "PAGE_UP"
                        self.cursor_idx = max(0, self.cursor_idx - self.items_per_page)
                    elif touch_event.x > SCREEN_W - self.btn_w:
                        self.last_action = "PAGE_DOWN"
                        self.cursor_idx = min(len(self.options) - 1, self.cursor_idx + self.items_per_page)
                    else:
                        self.last_action = "OK"
                        if self.multi: return [self.options[i] for i in sorted(self.selected_indices)]
                        else: return self.options[self.cursor_idx]
                        
                # List Item Interactions
                elif self.header_h <= touch_event.y < fy:
                    idx = self.page_start + (touch_event.y - self.header_h) // self.item_h
                    if 0 <= idx < len(self.options):
                        self.cursor_idx = idx
                        if self.multi:
                            if idx in self.selected_indices: self.selected_indices.remove(idx)
                            else: self.selected_indices.add(idx)
                        else: return self.options[idx]

            # Enforce scroll bounds after any input
            if self.cursor_idx < self.page_start: self.page_start = self.cursor_idx
            elif self.cursor_idx >= self.page_start + self.items_per_page: self.page_start = self.cursor_idx - self.items_per_page + 1
            
            # Small sleep to prevent busy loop eating battery/CPU
            time.sleep(0.01)

# =============================================================================
# PUBLIC FUNCTIONS
# =============================================================================

def input(prompt="Input:", type="text", theme="light", layout="qwerty"):
    clearevents()
    t = get_theme(theme)
    enable_tabs = True
    start_tab = 0
    numpad_opts = None
    if "numeric" in type:
        enable_tabs = False
        allow_float = "int" not in type 
        allow_neg = "negative" in type
        numpad_opts = {'float': allow_float, 'neg': allow_neg}
    elif type == "math": start_tab = 2
    kbd = Keyboard(default_tab=start_tab, enable_tabs=enable_tabs, numpad_opts=numpad_opts, theme=t, layout=layout)
    text = ""
    running = True
    
    # Touch latch state
    touch_latched = False
    
    while running:
        dclear(t['modal_bg'])
        
        # Header
        drect(0, 0, SCREEN_W, PICK_HEADER_H, t['accent'])
        dtext_opt(SCREEN_W//2, PICK_HEADER_H//2, t['txt_acc'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, prompt, -1)
        
        # Close Button (Top Left) - Reuse drawing logic from picker would be better but let's inline for simplicity
        # Hitbox: 0-40, 0-HEADER_H
        dline(15, 15, 25, 25, t['txt_acc'])
        dline(25, 15, 15, 25, t['txt_acc'])
        dline(16, 15, 26, 25, t['txt_acc'])
        dline(26, 15, 16, 25, t['txt_acc'])
        
        # Input Box
        box_y = 60; box_h = 40
        drect_border(10, box_y, SCREEN_W - 10, box_y + box_h, C_WHITE, 2, t['txt'])
        dtext(15, box_y + 10, C_BLACK, text + "_")
        
        kbd.draw()
        dupdate()
        
        # New Input Handling Loop
        cleareventflips()
        
        # 1. Process Physical Keys (Single Shot)
        if keypressed(KEY_EXIT): return None 
        if keypressed(KEY_EXE): return text
        
        # Backspace repeater logic for physical key (optional, can just use pressed)
        if keypressed(KEY_DEL): text = text[:-1]

        # 2. Process Events
        ev = pollevent()
        events = []
        while ev.type != KEYEV_NONE:
            events.append(ev)
            ev = pollevent()
            
        for e in events:
            # Touch Latch Logic
            if e.type == KEYEV_TOUCH_UP:
                touch_latched = False
                kbd.last_key = None # Clear visual press on release
            
            elif e.type == KEYEV_TOUCH_DOWN and not touch_latched:
                touch_latched = True
                
                # Check for Close Button in Header
                if e.y < PICK_HEADER_H and e.x < 40:
                    return None
                
                res = kbd.update(e)
                if res:
                    if res == "ENTER": running = False
                    elif res == "BACKSPACE": text = text[:-1]
                    elif res == "CAPS": pass
                    elif len(res) == 1: text += res
        
        time.sleep(0.01)
        
    return text

def pick(options, prompt="Select:", theme="light", multi=False):
    picker = ListPicker(options, prompt, theme, multi)
    return picker.run()

class ConfirmationDialog:
    def __init__(self, title, body, ok_text="OK", cancel_text="Cancel", theme="light"):
        self.title = title
        self.body = body
        self.ok_text = ok_text
        self.cancel_text = cancel_text
        self.theme = get_theme(theme)
        
        self.header_h = 40
        self.footer_h = 45
        self.btn_w = SCREEN_W // 2

    def draw_btn(self, x, y, w, h, text, pressed):
        t = self.theme
        bg = t['hl'] if pressed else t['key_spec']
        drect(x, y, x + w, y + h, bg)
        drect_border(x, y, x + w, y + h, C_NONE, 1, t['key_spec'])
        dtext_opt(x + w//2, y + h//2, t['txt'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, text, -1)

    def draw(self, btn_ok_pressed, btn_cn_pressed):
        t = self.theme
        dclear(t['modal_bg'])
        
        # Header
        drect(0, 0, SCREEN_W, self.header_h, t['accent'])
        dtext_opt(SCREEN_W//2, self.header_h//2, t['txt_acc'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, self.title, -1)
        
        # Body
        cy = (SCREEN_H - self.header_h - self.footer_h) // 2 + self.header_h
        dtext_opt(SCREEN_W//2, cy, t['txt'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, self.body, -1)
        
        # Footer
        fy = SCREEN_H - self.footer_h
        self.draw_btn(0, fy, self.btn_w, self.footer_h, self.cancel_text, btn_cn_pressed)
        self.draw_btn(self.btn_w, fy, self.btn_w, self.footer_h, self.ok_text, btn_ok_pressed)

    def run(self):
        touch_latched = False
        btn_ok_pressed = False
        btn_cn_pressed = False
        
        while True:
            self.draw(btn_ok_pressed, btn_cn_pressed)
            dupdate()
            cleareventflips()
            
            # Key Handling
            if keypressed(KEY_EXIT) or keypressed(KEY_DEL): return False
            if keypressed(KEY_EXE): return True
            
            # Event Handling
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
                elif e.type == KEYEV_TOUCH_UP:
                    touch_latched = False
                    touch = e
            
            if touch:
                tx, ty = touch.x, touch.y
                fy = SCREEN_H - self.footer_h
                
                if ty >= fy:
                    if tx < self.btn_w: # Cancel
                        if touch.type == KEYEV_TOUCH_DOWN: btn_cn_pressed = True
                        elif touch.type == KEYEV_TOUCH_UP and btn_cn_pressed: return False
                    else: # OK
                        if touch.type == KEYEV_TOUCH_DOWN: btn_ok_pressed = True
                        elif touch.type == KEYEV_TOUCH_UP and btn_ok_pressed: return True
                
                # Clear presses if touch moves out or ends
                if touch.type == KEYEV_TOUCH_UP:
                    btn_cn_pressed = False
                    btn_ok_pressed = False
            
            time.sleep(0.01)

def ask(title, body, ok_text="OK", cancel_text="Cancel", theme="light"):
    dlg = ConfirmationDialog(title, body, ok_text, cancel_text, theme)
    return dlg.run()
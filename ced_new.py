from gint import *
from io import open
import cinput

# =============================================================================
# CONFIGURATION
# =============================================================================

SCREEN_W = 320
SCREEN_H = 528

# Colors will be loaded from theme
# Default Fallback
COL_BG = C_WHITE
COL_TXT = C_BLACK

# Syntax Highlighting Defaults
COL_KW  = C_BLUE
COL_STR = 0x0480 # Dark Green
COL_COM = 0x7BEF # C_GRAY
COL_NUM = C_RED
COL_OP  = 0xF81F # C_MAGENTA

# Layout
HEADER_H = 40
TEXT_LINE_H = 20
TEXT_MARGIN_X = 5

# =============================================================================
# TOKENIZER (Syntax Highlighting)
# =============================================================================

KEYWORDS = {
    "def", "class", "if", "else", "elif", "while", "for", "import", "from", 
    "return", "True", "False", "None", "break", "continue", "pass", "try", 
    "except", "with", "as", "global", "print", "len", "range", "in", "is", 
    "not", "and", "or"
}

def is_digit(char: str) -> bool:
    return "0" <= char <= "9"

def tokenize_line(line: str) -> list:
    """Simple lexer for syntax highlighting."""
    tokens = []
    i = 0
    length = len(line)
    OPERATORS = set("+-*/%=<>!&|^~")
    SEPARATORS = set("()[]{}:,.")
    
    while i < length:
        char = line[i]
        
        if char == "#":
            tokens.append((line[i:], COL_COM))
            break
        elif char in ('"', "'"):
            quote = char
            start = i
            i += 1
            while i < length and line[i] != quote:
                i += 1
            if i < length: i += 1
            tokens.append((line[start:i], COL_STR))
        elif char in OPERATORS or char in SEPARATORS:
            tokens.append((char, COL_OP))
            i += 1
        elif char == " " or char == "\t":
            tokens.append((char, COL_TXT))
            i += 1
        else:
            start = i
            while i < length:
                c = line[i]
                if c in OPERATORS or c in SEPARATORS or c in (" ", "\t", "#", '"', "'"):
                    break
                i += 1
            word = line[start:i]
            if not word: continue
            
            if is_digit(word[0]):
                tokens.append((word, COL_NUM))
            elif word in KEYWORDS:
                tokens.append((word, COL_KW))
            else:
                tokens.append((word, COL_TXT))
    return tokens

# =============================================================================
# EDITOR CLASS
# =============================================================================

class Editor:
    def __init__(self):
        self.lines = [""]
        self.filename = "untitled.py"
        
        # Theme State
        self.current_theme_name = 'light'
        self.theme = cinput.get_theme(self.current_theme_name)
        self.update_colors()
        
        # Cursor & Viewport
        self.cy = 0
        self.cx = 0
        self.vy = 0
        
        # Instantiate the Keyboard Widget from cinput
        self.keyboard = cinput.Keyboard(theme=self.current_theme_name, layout='qwerty')
        self.keyboard.visible = False 
        
        self.msg = "Welcome to CED"
        self.msg_timer = 100

    def update_colors(self):
        global COL_BG, COL_TXT, COL_KW, COL_STR, COL_COM, COL_NUM, COL_OP
        t = self.theme
        COL_BG = t['modal_bg']
        COL_TXT = t['txt']
        # Adjust syntax colors based on brightness if needed, or keep standard
        # For dark themes, ensure text is readable
        if self.current_theme_name == 'dark':
            COL_KW  = 0x4C7F # Light Blue
            COL_STR = 0x8666 # Light Green
            COL_OP  = 0xF81F # Magenta
        else:
            COL_KW  = C_BLUE
            COL_STR = 0x0480
            COL_OP  = 0xF81F

    def switch_theme(self):
        themes = ['light', 'dark', 'grey']
        try:
            idx = themes.index(self.current_theme_name)
        except: idx = 0
        new_name = themes[(idx + 1) % len(themes)]
        
        self.current_theme_name = new_name
        self.theme = cinput.get_theme(new_name)
        self.update_colors()
        
        # Re-init keyboard with new theme
        vis = self.keyboard.visible
        self.keyboard = cinput.Keyboard(theme=new_name, layout='qwerty')
        self.keyboard.visible = vis

    # --- Cursor Management ---
    
    def clamp_cursor(self):
        if self.cy < 0: self.cy = 0
        if self.cy >= len(self.lines): self.cy = len(self.lines) - 1
        
        line_len = len(self.lines[self.cy])
        if self.cx < 0: self.cx = 0
        if self.cx > line_len: self.cx = line_len

    def scroll_to_cursor(self):
        kb_h = 260 if self.keyboard.visible else 0
        view_h = SCREEN_H - HEADER_H - kb_h
        lines_vis = view_h // TEXT_LINE_H
        
        if self.cy < self.vy:
            self.vy = self.cy
        elif self.cy >= self.vy + lines_vis:
            self.vy = self.cy - lines_vis + 1

    # --- File Operations (Using cinput Dialogs) ---

    def do_menu(self):
        # Use the List Picker for a menu
        opts = ["New", "Save", "Open...", "Theme: " + self.current_theme_name, "Quit"]
        choice = cinput.pick(opts, "Menu", theme=self.current_theme_name)
        
        if choice == "New":
            self.lines = [""]
            self.filename = "untitled.py"
            self.cy = 0; self.cx = 0
        elif choice == "Save":
            self.save_file()
        elif choice == "Open...":
            self.load_file_dialog()
        elif choice and choice.startswith("Theme"):
            self.switch_theme()
        elif choice == "Quit":
            return "QUIT"
        return None

    def load_file_dialog(self):
        fname = cinput.input("File to open:", theme=self.current_theme_name)
        if fname:
            self.load_file(fname)

    def load_file(self, filename):
        try:
            with open(filename, "r") as f:
                content = f.read()
                self.lines = content.replace("\r\n", "\n").split("\n")
                if not self.lines: self.lines = [""]
            self.filename = filename
            self.msg = "Loaded " + filename
            self.cy = 0; self.cx = 0
        except:
            self.msg = "Error loading " + filename
        self.msg_timer = 60

    def save_file(self):
        target = self.filename
        if target == "untitled.py":
            target = cinput.input("Save as:", theme=self.current_theme_name)
            if not target: return 
        
        try:
            with open(target, "w") as f:
                f.write("\n".join(self.lines))
            self.filename = target
            self.msg = "Saved " + target
        except:
            self.msg = "Error saving file"
        self.msg_timer = 60

    # --- Text Editing ---

    def insert_char(self, char):
        self.clamp_cursor()
        line = self.lines[self.cy]
        self.lines[self.cy] = line[:self.cx] + char + line[self.cx:]
        self.cx += 1
        self.clamp_cursor()

    def delete_char(self):
        self.clamp_cursor()
        if self.cx > 0:
            line = self.lines[self.cy]
            self.lines[self.cy] = line[:self.cx-1] + line[self.cx:]
            self.cx -= 1
        elif self.cy > 0:
            curr = self.lines.pop(self.cy)
            self.cy -= 1
            self.cx = len(self.lines[self.cy])
            self.lines[self.cy] += curr
        self.clamp_cursor()

    def new_line(self):
        self.clamp_cursor()
        line = self.lines[self.cy]
        rem = line[self.cx:]
        self.lines[self.cy] = line[:self.cx]
        self.cy += 1
        self.lines.insert(self.cy, rem)
        self.cx = 0
        self.clamp_cursor()

    # --- Drawing ---

    def get_cx_px(self, line, cx):
        w, _ = dsize(line[:cx], None)
        return TEXT_MARGIN_X + w

    def get_cx_from_px(self, line, target_x):
        if target_x <= TEXT_MARGIN_X: return 0
        rel = target_x - TEXT_MARGIN_X
        best_i = 0
        min_diff = 9999
        for i in range(len(line) + 1):
            w, _ = dsize(line[:i], None)
            diff = abs(w - rel)
            if diff < min_diff:
                min_diff = diff
                best_i = i
            else: break
        return best_i

    def draw_icon_menu(self, x, y, col):
        # Hamburger: 3 lines
        for i in range(3):
            drect(x, y + 4 + i*5, x + 18, y + 5 + i*5, col)

    def draw_icon_kbd(self, x, y, col):
        # Keyboard grid icon
        drect_border(x, y+2, x+22, y+16, C_NONE, 1, col)
        # Dots
        for r in range(2):
            for c in range(3):
                px = x + 3 + c*6
                py = y + 5 + r*5
                drect(px, py, px+3, py+2, col)

    def draw(self):
        t = self.theme
        dclear(COL_BG)
        
        # 1. Material Header
        header_col = t['accent']
        header_txt = t['txt_acc']
        
        drect(0, 0, SCREEN_W, HEADER_H, header_col)
        
        # Left Icon: Menu (x=10)
        self.draw_icon_menu(10, 10, header_txt)
        
        # Right Icon: Keyboard Toggle (x=SCREEN_W-35)
        kbd_x = SCREEN_W - 35
        if not self.keyboard.visible:
            self.draw_icon_kbd(kbd_x, 10, header_txt)
        else:
            self.draw_icon_kbd(kbd_x, 10, header_txt)
            drect(kbd_x, 22, kbd_x + 22, 23, header_txt) # Underline active
            
        # Title (Centered)
        title = self.filename + ("*" if False else "") 
        dtext_opt(SCREEN_W//2, HEADER_H//2, header_txt, C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, title, -1)

        # 2. Text Area
        self.scroll_to_cursor()
        
        kb_h = 260 if self.keyboard.visible else 0
        view_h = SCREEN_H - HEADER_H - kb_h
        lines_vis = view_h // TEXT_LINE_H
        
        dwindow_set(0, HEADER_H, SCREEN_W, SCREEN_H - kb_h)
        
        for i in range(lines_vis):
            idx = self.vy + i
            if idx >= len(self.lines): break
            
            line = self.lines[idx]
            y = HEADER_H + i * TEXT_LINE_H + 2
            
            tokens = tokenize_line(line)
            cur_x = TEXT_MARGIN_X
            for text, color in tokens:
                dtext(cur_x, y, color, text)
                w, _ = dsize(text, None)
                cur_x += w
            
            # Cursor
            if idx == self.cy:
                cx_px = self.get_cx_px(line, self.cx)
                drect(cx_px, y, cx_px + 2, y + 18, COL_TXT)

        dwindow_set(0, 0, SCREEN_W, SCREEN_H) 

        # 3. Message Overlay
        if self.msg_timer > 0:
            self.msg_timer -= 1
            dtext(10, SCREEN_H - kb_h - 20, C_RED, self.msg)

        # 4. Keyboard
        self.keyboard.draw()
        
        dupdate()

# =============================================================================
# MAIN LOOP
# =============================================================================

def main():
    editor = Editor()
    clearevents()
    
    running = True
    
    # Touch latch for buttons
    touch_latched = False
    
    while running:
        editor.draw()
        
        cleareventflips()
        
        events = []
        ev = pollevent()
        while ev.type != KEYEV_NONE:
            events.append(ev)
            ev = pollevent()
            
        for e in events:
            # Shortcuts
            if e.type == KEYEV_DOWN:
                if e.key == KEY_MENU or e.key == KEY_SHIFT:
                    res = editor.do_menu()
                    if res == "QUIT": running = False
                    clearevents()
                    break
                
                elif e.key == KEY_EXIT or e.key == KEY_KBD: # KEY_KEYBOARD might need mapping check
                    editor.keyboard.visible = not editor.keyboard.visible
                
                # Nav
                elif e.key == KEY_UP: 
                    editor.cy -= 1; editor.clamp_cursor()
                elif e.key == KEY_DOWN: 
                    editor.cy += 1; editor.clamp_cursor()
                elif e.key == KEY_LEFT: 
                    editor.cx -= 1; editor.clamp_cursor()
                elif e.key == KEY_RIGHT: 
                    editor.cx += 1; editor.clamp_cursor()
                
                # Editing
                elif e.key == KEY_EXE: editor.new_line()
                elif e.key == KEY_DEL: editor.delete_char()

            # Touch Logic - Only process ONCE per press
            if e.type == KEYEV_TOUCH_UP:
                touch_latched = False
                editor.keyboard.last_key = None # Clear visual press
            
            elif e.type == KEYEV_TOUCH_DOWN:
                if not touch_latched:
                    # Mark as latched immediately to prevent subsequent events this frame/sequence
                    touch_latched = True
                    
                    # Header Interaction
                    if e.y < HEADER_H:
                        if e.x < 40: 
                            # Left Icon: Menu
                            if editor.do_menu() == "QUIT": running = False
                        elif e.x > SCREEN_W - 40:
                            # Right Icon: Keyboard
                            editor.keyboard.visible = not editor.keyboard.visible
                    
                    # Text Area Interaction
                    elif not editor.keyboard.visible or e.y < editor.keyboard.y:
                        rel_y = e.y - HEADER_H
                        row = editor.vy + (rel_y // TEXT_LINE_H)
                        if 0 <= row < len(editor.lines):
                            editor.cy = row
                            editor.cx = editor.get_cx_from_px(editor.lines[row], e.x)
                            editor.clamp_cursor()
                    
                    # Keyboard Interaction
                    # Pass the event to keyboard ONLY if it's a new touch
                    # The keyboard widget also has internal latching but we control it here too
                    elif editor.keyboard.visible:
                        res = editor.keyboard.update(e)
                        if res:
                            if res == "ENTER": editor.new_line()
                            elif res == "BACKSPACE": editor.delete_char()
                            elif res == "CAPS": pass
                            elif len(res) == 1: editor.insert_char(res)

main()
import cinput
from gint import *
from .theme import SCREEN_W, SCREEN_H, draw_panel

def prompt_filename(ext=".bmp"):
    name = cinput.input(f"Filename ({ext}):", type="text", theme="dark")
    if name:
        if not name.endswith(ext): name += ext
        return name
    return None

def msgbox(msg):
    # Simple overlay message
    w, h = 200, 100
    x, y = (SCREEN_W-w)//2, (SCREEN_H-h)//2
    draw_panel(x, y, w, h)
    dtext_opt(x + w//2, y + h//2, C_WHITE, C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, msg, -1)
    dupdate()
    cinput.getkey()

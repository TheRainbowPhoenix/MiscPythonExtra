from gint import *

# =============================================================================
# THEME & CONSTANTS
# =============================================================================

SCREEN_W = 320
SCREEN_H = 528
HEADER_H = 40
FOOTER_H = 45

THEME = {
    'bg': C_RGB(4, 4, 4),
    'panel': C_RGB(7, 7, 7),
    'panel_border': C_RGB(10, 10, 10),
    'accent': C_RGB(0, 18, 31),  # Adobe Blue-ish
    'text': C_WHITE,
    'text_dim': C_RGB(20, 20, 20),
    'control_bg': C_RGB(10, 10, 10),
    'control_fg': C_RGB(16, 16, 16),
    'ok_btn': C_RGB(0, 18, 31),
    'cancel_btn': C_RGB(10, 10, 10),
    'tab_active': C_RGB(12, 12, 12),
    'tab_inactive': C_RGB(6, 6, 6)
}

def fill_rect(x, y, w, h, col):
    drect(x, y, x+w-1, y+h-1, col)

def draw_panel(x, y, w, h):
    fill_rect(x, y, w, h, THEME['panel'])
    drect_border(x, y, x+w-1, y+h-1, C_NONE, 1, THEME['panel_border'])

def draw_header(title):
    fill_rect(0, 0, SCREEN_W, HEADER_H, THEME['accent'])
    dtext_opt(SCREEN_W//2, HEADER_H//2, THEME['text'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, title, -1)
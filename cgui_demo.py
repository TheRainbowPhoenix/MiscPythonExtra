from gint import *
import cinput
from cgui import *

# =============================================================================
# DEMO CONSTANTS & HELPERS
# =============================================================================

SCREEN_W = 320
SCREEN_H = 528
HEADER_H = 40

def draw_demo_header(theme_name, title="Demo App"):
    t = cinput.get_theme(theme_name)
    # Header Bar
    drect(0, 0, SCREEN_W, HEADER_H, t['accent'])
    dtext_opt(SCREEN_W//2, HEADER_H//2, t['txt_acc'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, title, -1)
    
    # Menu Icon (Hamburger)
    col = t['txt_acc']
    x, y = 10, 10
    for i in range(3):
        drect(x, y + 4 + i*5, x + 18, y + 5 + i*5, col)

def show_result(theme_name, title, lines):
    """Helper to show results after a dialog closes"""
    t = cinput.get_theme(theme_name)
    dclear(t['modal_bg'])
    draw_demo_header(theme_name, "Result")
    
    y = SCREEN_H // 2 - (len(lines) * 10)
    for line in lines:
        dtext_opt(SCREEN_W//2, y, t['txt'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, line, -1)
        y += 20
        
    dtext_opt(SCREEN_W//2, SCREEN_H - 40, t['txt_dim'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "Press any key...", -1)
    dupdate()
    getkey()

# =============================================================================
# MAIN LOOP
# =============================================================================

def main():
    themes = ['light', 'dark', 'grey']
    layouts = ['qwerty', 'azerty', 'qwertz', 'abc']
    
    curr_theme_idx = 1 # Default to dark to match our dialogs better
    curr_layout_idx = 0
    
    # Default states for our dialogs so they remember settings between opens
    current_color = C_RGB(31, 0, 0) # Red
    current_brush = {
        'size': 10, 'spacing': 5, 'spread': 0, 
        'flow': 100, 'opacity': 100, 'shape': 'circle'
    }

    running = True
    touch_latched = False
    
    while running:
        current_theme_name = themes[curr_theme_idx]
        current_layout_name = layouts[curr_layout_idx]
        t = cinput.get_theme(current_theme_name)
        
        # --- Draw Main Shell ---
        dclear(t['modal_bg']) # Use standard bg instead of modal_bg for main shell
        draw_demo_header(current_theme_name)
        
        # Main Content
        msg = "Tap Menu or press [MENU]"
        dtext_opt(SCREEN_W//2, SCREEN_H//2 - 20, t['txt'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, msg, -1)
        
        # Status
        dtext_opt(SCREEN_W//2, SCREEN_H//2 + 20, t['key_spec'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, f"Theme: {current_theme_name}", -1)
        
        # Show current color preview
        dtext_opt(SCREEN_W//2, SCREEN_H//2 + 50, t['txt_dim'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "Current Color:", -1)
        fill_rect(SCREEN_W//2 - 20, SCREEN_H//2 + 65, 40, 20, current_color)
        drect_border(SCREEN_W//2 - 20, SCREEN_H//2 + 65, SCREEN_W//2 + 20, SCREEN_H//2 + 85, C_NONE, 1, t['txt'])

        dupdate()
        
        # --- Input Loop ---
        cleareventflips()
        
        # 1. Menu Trigger Check
        open_menu = False
        
        # Physical Key
        if keypressed(KEY_MENU) or keypressed(KEY_F1):
            open_menu = True
        if keypressed(KEY_EXIT):
            running = False
            
        # Touch
        ev = pollevent()
        while ev.type != KEYEV_NONE:
            if ev.type == KEYEV_TOUCH_UP:
                touch_latched = False
            elif ev.type == KEYEV_TOUCH_DOWN and not touch_latched:
                touch_latched = True
                # Check Header/Menu Button Hitbox
                if ev.y < HEADER_H and ev.x < 50:
                    open_menu = True
            ev = pollevent()
            
        # 2. Handle Menu Action
        if open_menu:
            # Define Options
            opts = [
                "Color Picker",
                "Brush Settings",
                "Text Input Demo",
                "Integer Input Demo",
                "List Picker Demo",
                f"Switch Theme ({themes[(curr_theme_idx+1)%len(themes)]})",
                f"Switch Layout ({layouts[(curr_layout_idx+1)%len(layouts)]})",
                "Quit"
            ]
            
            # Show Picker
            choice = cinput.pick(opts, "App Menu", theme=current_theme_name)
            
            # Process Result
            if choice == "Quit":
                running = False
            
            # --- NEW FEATURES ---
            elif choice == "Color Picker":
                # Launch our custom ColorPicker
                cp = ColorPicker(current_color)
                res = cp.run()
                if res is not None:
                    current_color = res
            
            elif choice == "Brush Settings":
                # Launch our custom BrushDialog
                bd = BrushDialog(
                    current_brush['size'], current_brush['spacing'], 
                    current_brush['spread'], current_brush['flow'], 
                    current_brush['opacity'], current_brush['shape']
                )
                res = bd.run()
                if res is not None:
                    current_brush = res
                    # Show confirmation
                    show_result(current_theme_name, "Brush Updated", [
                        f"Shape: {res['shape']}",
                        f"Size: {int(res['size'])}px",
                        f"Opacity: {int(res['opacity'])}%"
                    ])
            # --------------------

            elif choice and "Switch Theme" in choice:
                curr_theme_idx = (curr_theme_idx + 1) % len(themes)
                
            elif choice and "Switch Layout" in choice:
                curr_layout_idx = (curr_layout_idx + 1) % len(layouts)
                
            elif choice == "Text Input Demo":
                res = cinput.input(f"Enter text ({current_layout_name}):", type="text", theme=current_theme_name, layout=current_layout_name)
                if res is not None:
                    show_result(current_theme_name, "Input Result", [f"You typed: {res}"])

            elif choice == "Integer Input Demo":
                res = cinput.input("Enter Integer:", type="numeric_int negative", theme=current_theme_name)
                if res is not None:
                    show_result(current_theme_name, "Input Result", [f"Value: {res}"])

            elif choice == "List Picker Demo":
                demo_opts = [f"Item {i}" for i in range(1, 21)]
                res = cinput.pick(demo_opts, "Multi Select Demo", theme=current_theme_name, multi=True)
                if res is not None:
                    # Helper to chunk list for display
                    s = ", ".join([str(x) for x in res])
                    show_result(current_theme_name, "Selection", [f"Count: {len(res)}", s[:30]+"..." if len(s)>30 else s])

main()
from gint import *
import cinput

SCREEN_W = 320
SCREEN_H = 528
HEADER_H = 40

def draw_header(theme, title="Demo App"):
    t = cinput.get_theme(theme)
    # Header Bar
    drect(0, 0, SCREEN_W, HEADER_H, t['accent'])
    dtext_opt(SCREEN_W//2, HEADER_H//2, t['txt_acc'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, title, -1)
    
    # Menu Icon (Hamburger)
    col = t['txt_acc']
    x, y = 10, 10
    for i in range(3):
        drect(x, y + 4 + i*5, x + 18, y + 5 + i*5, col)

def main():
    themes = ['light', 'dark', 'grey']
    layouts = ['qwerty', 'azerty', 'qwertz', 'abc']
    
    curr_theme_idx = 0
    curr_layout_idx = 0
    
    running = True
    touch_latched = False
    
    while running:
        current_theme_name = themes[curr_theme_idx]
        current_layout_name = layouts[curr_layout_idx]
        t = cinput.get_theme(current_theme_name)
        
        #  Draw Main Shell ---
        dclear(t['modal_bg'])
        draw_header(current_theme_name)
        
        # Main Content
        msg = "Tap Menu or press [MENU]"
        dtext_opt(SCREEN_W//2, SCREEN_H//2, t['txt'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, msg, -1)
        dtext_opt(SCREEN_W//2, SCREEN_H//2 + 20, t['key_spec'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, f"Theme: {current_theme_name}", -1)
        
        dupdate()
        
        #  Input Loop ---
        cleareventflips()
        
        # 1. Menu Trigger Check
        open_menu = False
        
        # Physical Key
        if keypressed(KEY_MENU) or keypressed(KEY_F1):
            open_menu = True
        if keypressed(KEY_EXIT):
            running = False
            
        # 2. Event Processing
        ev = pollevent()
        events = []
        while ev.type != KEYEV_NONE:
            events.append(ev)
            ev = pollevent()
            
        for e in events:
            if e.type == KEYEV_TOUCH_UP:
                touch_latched = False
                    
            elif e.type == KEYEV_TOUCH_DOWN and not touch_latched:
                touch_latched = True
                
                # Check Header Click on Press (Ced-style)
                if e.y < HEADER_H and e.x < 50:
                    open_menu = True
        
        # 3. Handle Menu Action
        if open_menu:
            cleareventflips() # Important: Clear events before showing new modal
            # Define Options
            opts = [
                "Text Input Demo",
                "Integer Input Demo",
                "Float Input Demo",
                "List Picker Demo",
                "List View Demo",
                f"Switch Theme ({themes[(curr_theme_idx+1)%len(themes)]})",
                f"Switch Layout ({layouts[(curr_layout_idx+1)%len(layouts)]})",
                "Quit"
            ]
            
            # Show Picker
            choice = cinput.pick(opts, "App Menu", theme=current_theme_name)
            
            # Process Result
            if choice == "Quit":
                running = False
            
            elif choice and "Switch Theme" in choice:
                curr_theme_idx = (curr_theme_idx + 1) % len(themes)
                
            elif choice and "Switch Layout" in choice:
                curr_layout_idx = (curr_layout_idx + 1) % len(layouts)
                
            elif choice == "Text Input Demo":
                res = cinput.input(f"Enter text ({current_layout_name}):", type="text", theme=current_theme_name, layout=current_layout_name)
                # Show Result
                if res is not None:
                    dclear(t['modal_bg'])
                    dtext_opt(SCREEN_W//2, SCREEN_H//2, t['txt'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, f"You typed: {res}", -1)
                    dupdate()
                    getkey()

            elif choice == "Integer Input Demo":
                res = cinput.input("Enter Integer:", type="numeric_int negative", theme=current_theme_name)
                if res is not None:
                    dclear(t['modal_bg'])
                    dtext_opt(SCREEN_W//2, SCREEN_H//2, t['txt'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, f"Value: {res}", -1)
                    dupdate()
                    getkey()

            elif choice == "Float Input Demo":
                res = cinput.input("Enter Float:", type="numeric_float", theme=current_theme_name)
                if res is not None:
                    dclear(t['modal_bg'])
                    dtext_opt(SCREEN_W//2, SCREEN_H//2, t['txt'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, f"Value: {res}", -1)
                    dupdate()
                    getkey()

            elif choice == "List Picker Demo":
                demo_opts = [f"Item {i}" for i in range(1, 21)]
                res = cinput.pick(demo_opts, "Multi Select Demo", theme=current_theme_name, multi=True)
                if res is not None:
                    dclear(t['modal_bg'])
                    # Join list for display
                    res_str = ", ".join([str(x) for x in res])
                    # Wrap text simply
                    dtext_opt(10, SCREEN_H//2, t['txt'], C_NONE, DTEXT_LEFT, DTEXT_MIDDLE, f"Selected: {res_str}", SCREEN_W-20)
                    dupdate()
                    getkey()
            
            elif choice == "List View Demo":
                import cinput_list_demo
                # Reload to ensure fresh start if run multiple times
                try: 
                    import sys
                    if 'cinput_list_demo' in sys.modules: del sys.modules['cinput_list_demo']
                    import cinput_list_demo
                    cinput_list_demo.main()
                except Exception as e:
                    print(f"Error running list demo: {e}")

main()
from gint import *
import cinput
import lzw
import time

# --- Configuration ---
THEME = 'dark'
HEADER_H = 40

def draw_header(title):
    global THEME
    t = cinput.get_theme(THEME)
    drect(0, 0, DWIDTH, HEADER_H, t['accent'])
    dtext_opt(DWIDTH//2, HEADER_H//2, t['txt_acc'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, title, -1)

def show_results(original_text):
    if not original_text:
        return
        
    t = cinput.get_theme(THEME)
    data = original_text.encode()
    
    # Run LZW
    start_t = time.monotonic()
    compressed = lzw.compress(data)
    end_t = time.monotonic()
    
    decompressed = lzw.decompress(compressed)
    
    while True:
        dclear(t['modal_bg'])
        draw_header("LZW Results")
        
        y = 60
        margin = 15
        
        # Original Info
        dtext(margin, y, t['txt_dim'], "Original String:")
        y += 20
        # Truncate for display if too long
        disp_orig = original_text if len(original_text) < 30 else original_text[:27] + "..."
        dtext(margin + 10, y, t['txt'], disp_orig)
        y += 25
        dtext(margin + 10, y, t['txt_dim'], f"Size: {len(data)} bytes")
        
        y += 45
        # Compression Info
        dtext(margin, y, t['txt_dim'], "Compressed Codes:")
        y += 20
        codes_str = ", ".join(map(str, compressed[:8]))
        if len(compressed) > 8: codes_str += " ..."
        dtext(margin + 10, y, t['accent'], codes_str)
        y += 25
        dtext(margin + 10, y, t['txt_dim'], f"Count: {len(compressed)} codes")
        
        y += 45
        # Stats
        # Assume 16-bit codes (2 bytes) for ratio calculation
        ratio = (len(compressed) * 2 / len(data)) * 100 if len(data) > 0 else 0
        dtext(margin, y, t['txt_dim'], "Performance:")
        y += 20
        dtext(margin + 10, y, t['txt'], "Ratio: {:.1f}%".format(ratio))
        y += 20
        dtext(margin + 10, y, t['txt'], "Time: {:.3f}s".format(end_t - start_t))
        
        y += 45
        # Integrity
        status = "Verified OK" if decompressed == data else "FAILED"
        status_col = C_RGB(0, 25, 0) if status == "Verified OK" else C_RGB(31, 0, 0)
        dtext(margin, y, t['txt_dim'], "Integrity Check:")
        y += 20
        dtext(margin + 10, y, status_col, status)

        dtext_opt(DWIDTH//2, DHEIGHT - 40, t['txt_dim'], C_NONE, DTEXT_CENTER, DTEXT_BOTTOM, "[EXE] or [EXIT] to return", -1)
        
        dupdate()
        ev = getkey()
        if ev.key in [KEY_EXE, KEY_EXIT]:
            break

def main():
    global THEME
    while True:
        t = cinput.get_theme(THEME)
        dclear(t['modal_bg'])
        draw_header("LZW Utility")
        
        msg = "Compress and Test Data"
        dtext_opt(DWIDTH//2, DHEIGHT//3, t['txt'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, msg, -1)
        
        dtext_opt(DWIDTH//2, DHEIGHT - 100, t['txt_dim'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "Press [EXE] to start", -1)
        dupdate()
        
        # Menu options
        opts = [
            "Type Custom Text",
            "Example: Repetitive 'aaaa...'",
            "Example: Classic 'TOBEORNOT...'",
            "Example: Large Text Demo",
            "Switch Theme",
            "Exit"
        ]
        
        choice = cinput.pick(opts, "LZW Toolbox", theme=THEME)
        
        if not choice or choice == "Exit":
            break
            
        elif choice == "Switch Theme":
            THEME = 'light' if THEME == 'dark' else 'dark'
            
        elif choice == "Type Custom Text":
            res = cinput.input("Enter text to compress:", theme=THEME)
            if res:
                show_results(res)
                
        elif choice == "Example: Repetitive 'aaaa...'":
            show_results("a" * 100)
            
        elif choice == "Example: Classic 'TOBEORNOT...'":
            show_results("TOBEORNOTTOBEORTOBEORNOT")
            
        elif choice == "Example: Large Text Demo":
            # A more complex string to show dictionary building
            text = "The quick brown fox jumps over the lazy dog. " * 5
            show_results(text)

# Run the app
main()
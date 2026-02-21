from gint import *
import cinput
import compression as comp
import time
import gc

# --- Custom Theme Definition ---
THEME_NAME = 'cyber'
cinput.THEMES[THEME_NAME] = {
    'modal_bg': C_RGB(3, 4, 6),     # Very dark blue-grey
    'kbd_bg':   C_RGB(3, 4, 6),
    'key_bg':   C_RGB(6, 7, 10),
    'key_spec': C_RGB(10, 12, 16),
    'key_out':  C_BLACK,
    'txt':      C_RGB(14, 18, 21),  # Off-white
    'txt_dim':  C_RGB(12, 16, 20),
    'accent':   C_RGB(0, 16, 24),   # Cyan accent
    'txt_acc':  C_WHITE,
    'hl':       C_RGB(0, 10, 16),
    'check':    C_WHITE
}

HEADER_H = 40

# =============================================================================
# RESULTS ACTIVITY
# =============================================================================

class ResultsActivity:
    def __init__(self, algo_name, compress_fn, decompress_fn, test_text):
        self.algo_name = algo_name
        self.compress_fn = compress_fn
        self.decompress_fn = decompress_fn
        self.original = test_text.encode()
        
        self.scroll_y = 0
        self.max_scroll = 0
        
        # Run Benchmarks
        self.run_benchmarks()

    def run_benchmarks(self):
        gc.collect()
        mem_start = gc.mem_free()
        
        # Compression
        t0 = time.monotonic()
        self.compressed = self.compress_fn(self.original)
        t1 = time.monotonic()
        self.comp_time = t1 - t0
        
        # Determine Size
        if isinstance(self.compressed, list):
            self.comp_size = len(self.compressed) * 2 # Approx 16-bit codes
        else:
            self.comp_size = len(self.compressed)
            
        mem_mid = gc.mem_free()
        self.heap_delta = abs(mem_start - mem_mid)
        
        # Decompression
        t2 = time.monotonic()
        self.decompressed = self.decompress_fn(self.compressed)
        t3 = time.monotonic()
        self.decomp_time = t3 - t2
        
        self.verified = (self.decompressed == self.original)
        
        # Calc Layout
        content_h = 300
        view_h = DHEIGHT - HEADER_H
        self.max_scroll = max(0, content_h - view_h)

    def draw_back_arrow(self, x, y, col):
        drect(x + 2, y + 9, x + 18, y + 10, col)
        dline(x + 2, y + 9, x + 9, y + 2, col)
        dline(x + 2, y + 10, x + 9, y + 3, col)
        dline(x + 2, y + 9, x + 9, y + 16, col)
        dline(x + 2, y + 10, x + 9, y + 17, col)

    def draw(self):
        t = cinput.get_theme(THEME_NAME)
        dclear(t['modal_bg'])
        
        y = HEADER_H + 15 - self.scroll_y
        margin = 15
        
        # Display Original
        dtext(margin, y, t['txt_dim'], "Input Data:")
        y += 20
        disp_orig = self.original.decode()
        if len(disp_orig) > 30: disp_orig = disp_orig[:27] + "..."
        dtext(margin + 10, y, t['txt'], f'"{disp_orig}"')
        y += 25
        dtext(margin + 10, y, t['txt_dim'], f"Size: {len(self.original)} bytes")
        
        y += 40
        # Display Stats
        ratio = (self.comp_size / len(self.original)) * 100 if len(self.original) > 0 else 0
        dtext(margin, y, t['txt_dim'], "Compression Stats:")
        y += 20
        dtext(margin + 10, y, t['accent'], f"New Size: {self.comp_size} bytes")
        y += 20
        dtext(margin + 10, y, t['txt'], f"Ratio: {ratio:.1f}%")
        y += 20
        dtext(margin + 10, y, t['txt'], f"Comp Time: {self.comp_time:.3f}s")
        y += 20
        dtext(margin + 10, y, t['txt'], f"Decomp Time: {self.decomp_time:.3f}s")
        y += 20
        dtext(margin + 10, y, t['txt'], f"Heap Delta: {self.heap_delta} bytes")
        
        y += 40
        # Integrity
        status = "Pass (Matches Original)" if self.verified else "FAILED"
        status_col = C_RGB(0, 25, 0) if self.verified else C_RGB(31, 0, 0)
        dtext(margin, y, t['txt_dim'], "Integrity Check:")
        y += 20
        dtext(margin + 10, y, status_col, status)
        
        # Header (drawn last to cover scroll)
        drect(0, 0, DWIDTH, HEADER_H, t['accent'])
        self.draw_back_arrow(10, 10, t['txt_acc'])
        dtext_opt(DWIDTH//2, HEADER_H//2, t['txt_acc'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, f"{self.algo_name} Results", -1)

    def run(self):
        touch_latched = False
        running = True
        while running:
            self.draw()
            dupdate()
            cleareventflips()
            
            ev = pollevent()
            events = []
            while ev.type != KEYEV_NONE:
                events.append(ev)
                ev = pollevent()
                
            if keypressed(KEY_EXIT) or keypressed(KEY_DEL):
                running = False
                
            for e in events:
                if e.type == KEYEV_TOUCH_DOWN:
                    touch_latched = True
                elif e.type == KEYEV_TOUCH_UP:
                    if touch_latched:
                        touch_latched = False
                        if e.y < HEADER_H and e.x < 60:
                            running = False
            time.sleep(0.01)

# =============================================================================
# MAIN MENU APP
# =============================================================================

class CompressionApp:
    def __init__(self):
        self.algorithms = [
            ("LZ77 (Packed Bytes)", comp.lz77_compress, comp.lz77_decompress),
            ("LZW (Dictionary)", comp.lzw_compress, comp.lzw_decompress),
            ("RLE (Run-Length)", comp.rle_compress, comp.rle_decompress)
        ]
        
        self.tests = [
            ("English Text (Markdown)", "# Header\nThis is a normal english text sentence with some repeated repeated words. This is a normal english text sentence."),
            ("Repetitive Data", "A" * 50 + "B" * 50 + "A" * 50),
            ("Classic LZW String", "TOBEORNOTTOBEORTOBEORNOT"),
            ("Custom Input...", "")
        ]

    def build_menu(self):
        items = []
        items.append({'type': 'section', 'text': 'Algorithms', 'height': 25})
        for i, (name, _, _) in enumerate(self.algorithms):
            items.append({'type': 'algo', 'text': name, 'idx': i, 'height': 45, 'arrow': True})
        return items

    def select_test(self):
        opts = [t[0] for t in self.tests]
        choice = cinput.pick(opts, "Select Payload", theme=THEME_NAME)
        if not choice: return None
        
        if choice == "Custom Input...":
            text = cinput.input("Enter text:", type="text", theme=THEME_NAME)
            return text if text else None
            
        for name, text in self.tests:
            if name == choice: return text
        return None

    def run(self):
        items = self.build_menu()
        rect = (0, HEADER_H, DWIDTH, DHEIGHT - HEADER_H)
        lv = cinput.ListView(rect, items, theme=THEME_NAME)
        
        running = True
        while running:
            t = cinput.get_theme(THEME_NAME)
            lv.draw()
            
            # Header
            drect(0, 0, DWIDTH, HEADER_H, t['accent'])
            dtext_opt(DWIDTH//2, HEADER_H//2, t['txt_acc'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "Compression Lab", -1)
            
            dupdate()
            cleareventflips()
            
            ev = pollevent()
            events = []
            while ev.type != KEYEV_NONE:
                events.append(ev)
                ev = pollevent()
                
            if keypressed(KEY_EXIT) or keypressed(KEY_DEL):
                running = False
                
            action = lv.update(events)
            if action:
                type, _, item = action
                if type == 'click' and item.get('type') == 'algo':
                    # Algorithm selected, now pick payload
                    algo = self.algorithms[item['idx']]
                    payload = self.select_test()
                    if payload:
                        activity = ResultsActivity(algo[0], algo[1], algo[2], payload)
                        activity.run()
                        cleareventflips()

            time.sleep(0.01)

# Start
app = CompressionApp()
app.run()
from gint import *
import machine
import cinput
import time

def get_string(addr, max_len=8):
    """Reads a null-terminated string of up to max_len bytes from memory."""
    chars = []
    for i in range(max_len):
        val = machine.mem8[addr + i]
        if val == 0: 
            break
        # Filter for printable ASCII
        if 32 <= val < 127:
            chars.append(chr(val))
        else:
            chars.append('.')
    return "".join(chars)

# =============================================================================
# CUSTOM UI COMPONENTS
# =============================================================================

class MCSListView(cinput.ListView):
    def draw_item(self, x, y, item, is_selected):
        t = self.theme
        h = item['_h']
        
        if item.get('type') == 'section':
            drect(x, y, x + self.w, y + h, t['key_spec'])
            drect_border(x, y, x + self.w, y + h, C_NONE, 1, t['key_spec'])
            dtext_opt(x + 10, y + h//2, t['txt_dim'], C_NONE, DTEXT_LEFT, DTEXT_MIDDLE, str(item['text']), -1)
        else:
            bg = t['hl'] if is_selected else t['modal_bg']
            drect(x, y, x + self.w, y + h, bg)
            drect_border(x, y, x + self.w, y + h, C_NONE, 1, t['key_spec'])
            
            col = t['txt'] # Always black text in light theme
            icon_col = t['txt'] if is_selected else t['accent'] # Black icon if selected
            
            # Draw Custom Icons
            if item.get('type') == 'folder':
                # Breeze style Folder Icon
                inner_col = t['txt_dim']
                # Back Tab (Inner)
                dpoly([x+8, y+12, x+16, y+12, x+20, y+16, x+20, y+22, x+8, y+22], inner_col, inner_col)
                # Front Body (Outer)
                dpoly([x+8, y+21, x+14, y+21, x+19, y+16, x+32, y+16, x+32, y+35, x+8, y+35], icon_col, icon_col)
            elif item.get('type') == 'var':
                # File Icon (Paper with folded corner)
                dpoly([x+12, y+14, x+22, y+14, x+28, y+20, x+28, y+36, x+12, y+36], C_NONE, icon_col)
                dpoly([x+22, y+14, x+22, y+20, x+28, y+20], C_NONE, icon_col)
                dline(x+15, y+24, x+25, y+24, icon_col)
                dline(x+15, y+29, x+25, y+29, icon_col)
                dline(x+15, y+33, x+20, y+33, icon_col)

            # Draw Item Text
            x_off = 42
            dtext_opt(x + x_off, y + h//2, col, C_NONE, DTEXT_LEFT, DTEXT_MIDDLE, str(item['text']), -1)
            
            if item.get('arrow'):
                 ar_x = x + self.w - 15
                 ar_y = y + h//2
                 c = t['txt_dim']
                 dline(ar_x - 4, ar_y - 4, ar_x, ar_y, c)
                 dline(ar_x - 4, ar_y + 4, ar_x, ar_y, c)


class HexViewerDialog:
    def __init__(self, var, theme="light"):
        self.var = var
        self.theme = cinput.get_theme(theme)
        self.header_h = 40
        self.footer_h = 45
        self.btn_w = 320 // 2
        
        # Read up to 256 bytes for the preview (32 lines of 8 bytes)
        self.max_bytes = min(256, var['size'])
        self.chunks = []
        ptr = var['ptr']
        
        for offset in range(0, self.max_bytes, 8):
            bytes_row = []
            chars_row = []
            for k in range(min(8, self.max_bytes - offset)):
                b = machine.mem8[ptr + offset + k]
                bytes_row.append(b)
                chars_row.append(chr(b) if 32 <= b < 127 else '.')
            
            self.chunks.append((offset, bytes_row, chars_row))

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
        drect(0, 0, 320, self.header_h, t['accent'])
        dtext_opt(160, self.header_h//2, t['txt_acc'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, self.var['name'], -1)
        
        # Body Info
        info = "Type: {} | Size: {} bytes".format(self.var['type'], self.var['size'])
        dtext_opt(160, self.header_h + 15, t['txt'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, info, -1)
        
        # Hex Dump Box
        hex_y = self.header_h + 40
        hex_h = 528 - self.footer_h - hex_y - 5
        drect(10, hex_y, 310, hex_y + hex_h, t['key_bg'])
        drect_border(10, hex_y, 310, hex_y + hex_h, C_NONE, 1, t['key_spec'])
        
        ly = hex_y + 4
        for offset, bytes_row, chars_row in self.chunks:
            # Draw offset
            dtext(15, ly, t['txt'], "{:04X}".format(offset))
            
            # Draw hex bytes individually to color "00" differently
            for i, b in enumerate(bytes_row):
                bx = 55 + i * 18
                c = t['txt_dim'] if b == 0 else t['txt']
                dtext(bx, ly, c, "%02X" % b)
                
            # Draw ASCII perfectly aligned horizontally
            for i, ch in enumerate(chars_row):
                cx = 210 + i * 11
                dtext(cx, ly, t['txt'], ch)
                
            ly += 12
            
        if self.var['size'] > self.max_bytes:
            dtext_opt(160, ly + 2, t['txt_dim'], C_NONE, DTEXT_CENTER, DTEXT_TOP, "... (truncated) ...", -1)
        
        # Footer
        fy = 528 - self.footer_h
        self.draw_btn(0, fy, self.btn_w, self.footer_h, "Cancel", btn_cn_pressed)
        self.draw_btn(self.btn_w, fy, self.btn_w, self.footer_h, "Dump to File", btn_ok_pressed)

    def run(self):
        cinput.clearevents()
        cinput.cleareventflips()
        
        touch_latched = False
        btn_ok_pressed = False
        btn_cn_pressed = False
        
        while True:
            self.draw(btn_ok_pressed, btn_cn_pressed)
            dupdate()
            cinput.cleareventflips()
            
            if keypressed(KEY_EXIT) or keypressed(KEY_DEL): return False
            if keypressed(KEY_EXE): return True
            
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
                fy = 528 - self.footer_h
                
                is_cancel = (ty >= fy and tx < self.btn_w)
                is_ok = (ty >= fy and tx >= self.btn_w)
                
                if touch.type == KEYEV_TOUCH_DOWN:
                    if is_cancel: btn_cn_pressed = True
                    elif is_ok: btn_ok_pressed = True
                
                if touch.type == KEYEV_TOUCH_UP:
                    if is_cancel: 
                        cinput.clearevents()
                        return False
                    elif is_ok: 
                        cinput.clearevents()
                        return True
                    
                    btn_cn_pressed = False
                    btn_ok_pressed = False
            
            time.sleep(0.01)

# =============================================================================
# MAIN APPLICATION
# =============================================================================

class MCSBrowser:
    def __init__(self):
        self.theme_name = 'light'
        self.folders = self.get_folders()
        self.current_folder = None
        self.main_scroll = 0
        self.rebuild_list()

    def get_folders(self):
        DIR_BASE = 0x8CF80100
        MAX_DIRS = 0x87
        folders = []
        for i in range(MAX_DIRS):
            dir_addr = DIR_BASE + i * 16
            name = get_string(dir_addr, 8)
            if not name:
                continue
            
            data_ptr = machine.mem32[dir_addr + 8]
            var_num = machine.mem16[dir_addr + 12]
            folders.append({
                'name': name,
                'data_ptr': data_ptr,
                'var_num': var_num
            })
        return folders

    def get_variables(self, folder):
        vars = []
        for j in range(folder['var_num']):
            var_addr = folder['data_ptr'] + j * 20
            var_name = get_string(var_addr, 8)
            var_data_ptr = machine.mem32[var_addr + 8]
            var_size = machine.mem32[var_addr + 12]
            var_type = machine.mem8[var_addr + 16]
            vars.append({
                'name': var_name,
                'size': var_size,
                'type': var_type,
                'ptr': var_data_ptr
            })
        return vars

    def rebuild_list(self):
        items = []
        if self.current_folder is None:
            items.append({'type': 'section', 'text': 'Main Control System', 'height': 30})
            for f in self.folders:
                items.append({
                    'type': 'folder',
                    'text': f['name'] + " (" + str(f['var_num']) + " items)",
                    'folder_data': f,
                    'arrow': True,
                    'height': 50
                })
        else:
            items.append({'type': 'section', 'text': self.current_folder['name'], 'height': 30})
            vars = self.get_variables(self.current_folder)
            for v in vars:
                items.append({
                    'type': 'var',
                    'text': v['name'],
                    'var_data': v,
                    'height': 50
                })
        
        rect = (0, 40, 320, 528 - 40)
        self.list_view = MCSListView(rect, items, row_h=50, headers_h=30, theme=self.theme_name)

    def dump_variable(self, var):
        filename = var['name'].strip() + ".bin"
        try:
            with open(filename, "wb") as f:
                var_size = var['size']
                ptr = var['ptr']
                for offset in range(0, var_size, 64):
                    chunk_size = min(64, var_size - offset)
                    chunk = bytearray(chunk_size)
                    for k in range(chunk_size):
                        chunk[k] = machine.mem8[ptr + offset + k]
                    f.write(chunk)
            
            cinput.ask("Success", "Saved as " + filename, "OK", "", self.theme_name)
        except Exception as e:
            cinput.ask("Error", str(e), "OK", "", self.theme_name)

    def _save_scroll(self):
        """Safely extract scroll position depending on cinput version."""
        return getattr(self.list_view, 'scroll_y', 0)

    def _restore_scroll(self, scroll_val):
        """Safely restore scroll position depending on cinput version."""
        if hasattr(self.list_view, 'scroll_y'):
            self.list_view.scroll_y = scroll_val

    def run(self):
        running = True
        t = cinput.get_theme(self.theme_name)
        
        clearevents()
        cleareventflips()
        
        while running:
            dclear(t['modal_bg'])
            self.list_view.draw()
            
            # Draw Main Header
            drect(0, 0, 320, 40, t['accent'])
            
            if self.current_folder is not None:
                dtext_opt(15, 20, t['txt_acc'], C_NONE, DTEXT_LEFT, DTEXT_MIDDLE, "< Back", -1)
            else:
                dtext_opt(160, 20, t['txt_acc'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "MCS Browser", -1)

            dupdate()
            cleareventflips()
            
            ev = pollevent()
            events = []
            while ev.type != KEYEV_NONE:
                events.append(ev)
                ev = pollevent()
            
            if keypressed(KEY_EXIT) or keypressed(KEY_DEL):
                if self.current_folder is not None:
                    self.current_folder = None
                    self.rebuild_list()
                    self._restore_scroll(self.main_scroll)
                else:
                    running = False
            
            for e in events:
                if e.type == KEYEV_TOUCH_UP and e.y < 40 and e.x < 80:
                    if self.current_folder is not None:
                        self.current_folder = None
                        self.rebuild_list()
                        self._restore_scroll(self.main_scroll)
            
            action = self.list_view.update(events)
            
            if action:
                act_type, idx, item = action
                if act_type == 'click':
                    if item.get('type') == 'folder':
                        self.main_scroll = self._save_scroll()
                        self.current_folder = item['folder_data']
                        self.rebuild_list()
                    elif item.get('type') == 'var':
                        v = item['var_data']
                        # Launch Custom Hex Viewer
                        viewer = HexViewerDialog(v, self.theme_name)
                        if viewer.run():
                            self.dump_variable(v)
                        # Clean events after closing modal
                        clearevents()
                        cleareventflips()

            time.sleep(0.01)

# Run the application
app = MCSBrowser()
app.run()
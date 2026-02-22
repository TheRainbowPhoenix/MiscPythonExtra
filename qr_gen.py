import time
from gint import *
import cinput

# =============================================================================
# THEME CONFIGURATION
# =============================================================================

THEME_NAME = 'aqua'
AQUA_THEME = {
    'modal_bg': C_RGB(28, 30, 31),
    'kbd_bg':   C_RGB(28, 30, 31),
    'key_bg':   C_RGB(31, 31, 31),
    'key_spec': C_RGB(20, 24, 26), 
    'key_out':  C_RGB(0, 0, 0),
    'txt':      C_RGB(2, 4, 6),    
    'txt_dim':  C_RGB(10, 12, 14), 
    'accent':   C_RGB(2, 16, 24),   # Aqua Blueish
    'txt_acc':  C_RGB(31, 31, 31),
    'hl':       C_RGB(20, 24, 26),
    'check':    C_WHITE
}
if THEME_NAME not in cinput.THEMES:
    cinput.THEMES[THEME_NAME] = AQUA_THEME

# =============================================================================
# OPTIMIZED QR CODE ENGINE (V1 to V10, 8-bit mode only)
# =============================================================================

# Galois Field Math
EXP_TABLE = [0] * 256
LOG_TABLE = [0] * 256
for i in range(8): EXP_TABLE[i] = 1 << i
for i in range(8, 256):
    EXP_TABLE[i] = EXP_TABLE[i-4] ^ EXP_TABLE[i-5] ^ EXP_TABLE[i-6] ^ EXP_TABLE[i-8]
for i in range(255):
    LOG_TABLE[EXP_TABLE[i]] = i

def glog(n): return LOG_TABLE[n]
def gexp(n): return EXP_TABLE[n % 255]

class Polynomial:
    def __init__(self, num, shift):
        offset = 0
        while offset < len(num) and num[offset] == 0:
            offset += 1
        if offset == len(num):
            self.num = [0] * (shift + 1)
        else:
            self.num = num[offset:] + [0] * shift

    def __getitem__(self, i): return self.num[i]
    def __iter__(self): return iter(self.num)
    def __len__(self): return len(self.num)

    def __mul__(self, other):
        num = [0] * (len(self) + len(other) - 1)
        for i, item in enumerate(self):
            for j, other_item in enumerate(other):
                if item != 0 and other_item != 0:
                    num[i + j] ^= gexp(glog(item) + glog(other_item))
        return Polynomial(num, 0)

    def __mod__(self, other):
        diff = len(self) - len(other)
        if diff < 0 or self[0] == 0: return self
        ratio = glog(self[0]) - glog(other[0])
        num = [item ^ gexp(glog(other_item) + ratio) for item, other_item in zip(self, other)]
        if diff: num.extend(self[-diff:])
        return Polynomial(num, 0) % other

# Tables
RS_BLOCK_OFFSET = { 1: 0, 0: 1, 3: 2, 2: 3 } # L=1, M=0, Q=3, H=2
RS_BLOCK_TABLE = (
    (1,26,19),(1,26,16),(1,26,13),(1,26,9),
    (1,44,34),(1,44,28),(1,44,22),(1,44,16),
    (1,70,55),(1,70,44),(2,35,17),(2,35,13),
    (1,100,80),(2,50,32),(2,50,24),(4,25,9),
    (1,134,108),(2,67,43),(2,33,15, 2,34,16),(2,33,11, 2,34,12),
    (2,86,68),(4,43,27),(4,43,19),(4,43,15),
    (2,98,78),(4,49,31),(2,32,14, 4,33,15),(4,39,13, 1,40,14),
    (2,121,97),(2,60,38, 2,61,39),(4,40,18, 2,41,19),(4,40,14, 2,41,15),
    (2,146,116),(3,58,36, 2,59,37),(4,36,16, 4,37,17),(4,36,12, 4,37,13),
    (2,86,68, 2,87,69),(4,69,43, 1,70,44),(6,43,19, 2,44,20),(6,43,15, 2,44,16)
)
def rs_blocks(version, ec):
    offset = RS_BLOCK_OFFSET[ec]
    row = RS_BLOCK_TABLE[(version - 1) * 4 + offset]
    blocks = []
    for i in range(0, len(row), 3):
        count, total_count, data_count = row[i:i+3]
        for _ in range(count): blocks.append((total_count, data_count))
    return blocks

PATTERN_POSITION_TABLE = [
    [], [6,18], [6,22], [6,26], [6,30], [6,34], [6,22,38], [6,24,42], [6,26,46], [6,28,50]
]

G15 = (1<<10)|(1<<8)|(1<<5)|(1<<4)|(1<<2)|(1<<1)|1
G18 = (1<<12)|(1<<11)|(1<<10)|(1<<9)|(1<<8)|(1<<5)|(1<<2)|1
G15_MASK = (1<<14)|(1<<12)|(1<<10)|(1<<4)|(1<<1)

def BCH_digit(data):
    d = 0
    while data != 0:
        d += 1
        data >>= 1
    return d

def BCH_type_info(data):
    d = data << 10
    while BCH_digit(d) - BCH_digit(G15) >= 0:
        d ^= (G15 << (BCH_digit(d) - BCH_digit(G15)))
    return ((data << 10) | d) ^ G15_MASK

def BCH_type_number(data):
    d = data << 12
    while BCH_digit(d) - BCH_digit(G18) >= 0:
        d ^= (G18 << (BCH_digit(d) - BCH_digit(G18)))
    return (data << 12) | d

def mask_func(pattern):
    return lambda i, j: (i + j) % 2 == 0 # Force mask 0 to save performance

class BitBuffer:
    def __init__(self):
        self.buffer = []
        self.length = 0
    def put_bit(self, bit):
        buf_index = self.length // 8
        if len(self.buffer) <= buf_index: self.buffer.append(0)
        if bit: self.buffer[buf_index] |= (0x80 >> (self.length % 8))
        self.length += 1
    def put(self, num, length):
        for i in range(length):
            self.put_bit(((num >> (length - i - 1)) & 1) == 1)

def create_bytes(buffer, blocks):
    offset = 0
    maxDc = 0; maxEc = 0
    dcdata = [0]*len(blocks)
    ecdata = [0]*len(blocks)
    for r in range(len(blocks)):
        dcCount = blocks[r][1]
        ecCount = blocks[r][0] - dcCount
        maxDc = max(maxDc, dcCount); maxEc = max(maxEc, ecCount)
        dcdata[r] = [buffer.buffer[i+offset] for i in range(dcCount)]
        offset += dcCount
        
        rsPoly = Polynomial([1], 0)
        for i in range(ecCount): rsPoly = rsPoly * Polynomial([1, gexp(i)], 0)
        rawPoly = Polynomial(dcdata[r], len(rsPoly)-1)
        modPoly = rawPoly % rsPoly
        
        ecdata[r] = [0]*(len(rsPoly)-1)
        for i in range(len(ecdata[r])):
            modIndex = i + len(modPoly) - len(ecdata[r])
            ecdata[r][i] = modPoly[modIndex] if modIndex >= 0 else 0
            
    data = []
    for i in range(maxDc):
        for r in range(len(blocks)):
            if i < len(dcdata[r]): data.append(dcdata[r][i])
    for i in range(maxEc):
        for r in range(len(blocks)):
            if i < len(ecdata[r]): data.append(ecdata[r][i])
    return data

class QRCode:
    def __init__(self, ec=0):
        self.ec = ec
        self.version = 1
        self.modules = []
        self.mc = 21

    def make(self, data):
        data = str(data).encode('utf-8')
        buffer = BitBuffer()
        buffer.put(4, 4) # 8BIT_BYTE MODE
        for v in range(1, 11):
            self.version = v
            length_bits = 8 if v < 10 else 16
            bit_limit = sum([b[1] * 8 for b in rs_blocks(v, self.ec)])
            if len(data) * 8 + length_bits + 4 <= bit_limit:
                break
        else:
            return False # Payload too large for Version 10
            
        buffer.put(len(data), length_bits)
        for c in data: buffer.put(c, 8)
        
        bit_limit = sum([b[1] * 8 for b in rs_blocks(self.version, self.ec)])
        for _ in range(min(bit_limit - buffer.length, 4)): buffer.put_bit(False)
        while buffer.length % 8 != 0: buffer.put_bit(False)
        
        pad = [0xEC, 0x11]
        pad_idx = 0
        while buffer.length < bit_limit:
            buffer.put(pad[pad_idx], 8)
            pad_idx ^= 1
            
        self.data_cache = create_bytes(buffer, rs_blocks(self.version, self.ec))
        self.makeImpl(False, 0)
        return True

    def makeImpl(self, test, mask_pattern):
        self.mc = self.version * 4 + 17
        self.modules = [[None] * self.mc for _ in range(self.mc)]
        self.setup_pos(0, 0)
        self.setup_pos(self.mc - 7, 0)
        self.setup_pos(0, self.mc - 7)
        self.setup_adjust()
        self.setup_timing()
        self.setup_type_info(test, mask_pattern)
        if self.version >= 7: self.setup_type_number(test)
        self.map_data(mask_pattern)

    def setup_pos(self, row, col):
        for r in range(-1, 8):
            if not (0 <= row+r < self.mc): continue
            for c in range(-1, 8):
                if not (0 <= col+c < self.mc): continue
                if (0<=r<=6 and (c==0 or c==6)) or (0<=c<=6 and (r==0 or r==6)) or (2<=r<=4 and 2<=c<=4):
                    self.modules[row+r][col+c] = True
                else: self.modules[row+r][col+c] = False

    def setup_adjust(self):
        pos = PATTERN_POSITION_TABLE[self.version - 1]
        for r in pos:
            for c in pos:
                if self.modules[r][c] is not None: continue
                for dr in range(-2, 3):
                    for dc in range(-2, 3):
                        self.modules[r+dr][c+dc] = (dr in (-2,2) or dc in (-2,2) or (dr==0 and dc==0))

    def setup_timing(self):
        for i in range(8, self.mc - 8):
            if self.modules[i][6] is None: self.modules[i][6] = (i % 2 == 0)
            if self.modules[6][i] is None: self.modules[6][i] = (i % 2 == 0)

    def setup_type_info(self, test, mask_pattern):
        data = (self.ec << 3) | mask_pattern
        bits = BCH_type_info(data)
        for i in range(15):
            mod = (not test and ((bits >> i) & 1) == 1)
            if i < 6: self.modules[i][8] = mod
            elif i < 8: self.modules[i+1][8] = mod
            else: self.modules[self.mc-15+i][8] = mod
            
            if i < 8: self.modules[8][self.mc-i-1] = mod
            elif i < 9: self.modules[8][15-i] = mod
            else: self.modules[8][15-i-1] = mod
        self.modules[self.mc-8][8] = (not test)

    def setup_type_number(self, test):
        bits = BCH_type_number(self.version)
        for i in range(18):
            mod = (not test and ((bits >> i) & 1) == 1)
            self.modules[i // 3][i % 3 + self.mc - 11] = mod
            self.modules[i % 3 + self.mc - 11][i // 3] = mod

    def map_data(self, mask_pattern):
        inc = -1
        row = self.mc - 1
        bitIndex = 7
        byteIndex = 0
        mf = mask_func(mask_pattern)
        dl = len(self.data_cache)
        for col in range(self.mc - 1, 0, -2):
            if col <= 6: col -= 1
            while True:
                for c in (col, col - 1):
                    if self.modules[row][c] is None:
                        dark = False
                        if byteIndex < dl:
                            dark = ((self.data_cache[byteIndex] >> bitIndex) & 1) == 1
                        if mf(row, c): dark = not dark
                        self.modules[row][c] = dark
                        bitIndex -= 1
                        if bitIndex == -1:
                            byteIndex += 1
                            bitIndex = 7
                row += inc
                if row < 0 or row >= self.mc:
                    row -= inc
                    inc = -inc
                    break


# =============================================================================
# APP LOGIC & UI
# =============================================================================

def draw_back_arrow(x, y, col):
    drect(x + 2, y + 9, x + 18, y + 10, col)
    dline(x + 2, y + 9, x + 9, y + 2, col)
    dline(x + 2, y + 10, x + 9, y + 3, col)
    dline(x + 2, y + 9, x + 9, y + 16, col)
    dline(x + 2, y + 10, x + 9, y + 17, col)

def compile_data(d):
    t = d['type']
    if t == 'text':
        return d['Text / URL']
    elif t == 'wifi':
        sec = d.get('Security', 'WPA/WPA2')
        sec_type = "WPA" if "WPA" in sec else ("WEP" if sec=="WEP" else "nopass")
        return f"WIFI:T:{sec_type};S:{d.get('SSID', '')};P:{d.get('Password', '')};;"
    elif t == 'vcard':
        n = d.get('Name', '')
        tel = d.get('Phone', '')
        email = d.get('Email', '')
        return f"BEGIN:VCARD\nVERSION:3.0\nN:{n}\nFN:{n}\nTEL;TYPE=CELL:{tel}\nEMAIL:{email}\nEND:VCARD"
    return ""

def ask_text():
    val = cinput.input("Enter text/URL:", type="text", theme=THEME_NAME)
    return {'type': 'text', 'Text / URL': val} if val else None

def ask_wifi():
    ssid = cinput.input("SSID:", type="text", theme=THEME_NAME)
    if not ssid: return None
    pwd = cinput.input("Password:", type="text", theme=THEME_NAME)
    sec = cinput.pick(["WPA/WPA2", "WEP", "None"], "Security:", theme=THEME_NAME)
    if not sec: return None
    return {'type': 'wifi', 'SSID': ssid, 'Password': pwd, 'Security': sec}

def ask_vcard():
    n = cinput.input("Name:", type="text", theme=THEME_NAME)
    if not n: return None
    tel = cinput.input("Phone:", type="text", theme=THEME_NAME)
    email = cinput.input("Email:", type="text", theme=THEME_NAME)
    return {'type': 'vcard', 'Name': n, 'Phone': tel, 'Email': email}

def edit_data(data_dict, theme):
    t = cinput.get_theme(theme)
    working_copy = dict(data_dict)
    keys = [k for k in working_copy.keys() if k != 'type']
    
    while True:
        opts = []
        for k in keys:
            opts.append({'type': 'item', 'text': f"{k}: {working_copy[k]}", 'id': k, 'arrow': True})
        
        lv = cinput.ListView((0, 40, 320, 528-40), opts, row_h=45, headers_h=30, theme=theme)
        
        choice = None
        running = True
        
        while running:
            dclear(t['modal_bg'])
            lv.draw()
            
            # Header Bar
            HEADER_H = 40
            drect(0, 0, 320, HEADER_H, t['accent'])
            dtext_opt(160, HEADER_H//2, t['txt_acc'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "Edit details", -1)
            
            # Draw Back Arrow (Left)
            draw_back_arrow(10, 10, C_WHITE)
            
            # Draw Check Validate Icon (Right)
            for offset in (0, 1, -1):
                dline(285, 21 + offset, 292, 28 + offset, C_WHITE)
                dline(292, 28 + offset, 305, 15 + offset, C_WHITE)
            
            dupdate()
            cleareventflips()
            
            ev = pollevent()
            events = []
            while ev.type != KEYEV_NONE:
                events.append(ev)
                ev = pollevent()
                
            def handle_back():
                changed = any(working_copy[k] != data_dict[k] for k in keys)
                if changed:
                    if cinput.ask("Save Changes?", "Apply modifications?", "Yes", "No", theme=theme):
                        data_dict.update(working_copy)
                        return True
                    return False
                return False
                
            def handle_check():
                changed = any(working_copy[k] != data_dict[k] for k in keys)
                data_dict.update(working_copy)
                return changed
            
            if keypressed(KEY_EXIT) or keypressed(KEY_DEL):
                return handle_back()
                
            for e in events:
                if e.type == KEYEV_TOUCH_UP:
                    if e.y < HEADER_H:
                        if e.x < 60:
                            return handle_back()
                        elif e.x > 260:
                            return handle_check()
            
            action = lv.update(events)
            if action:
                type_, idx, item = action
                if type_ == 'click':
                    choice = item['id']
                    running = False
            time.sleep(0.01)
            
        if choice:
            if choice == 'Security' and data_dict['type'] == 'wifi':
                new_val = cinput.pick(["WPA/WPA2", "WEP", "None"], "Security:", theme=theme)
                if new_val: working_copy[choice] = new_val
            else:
                new_val = cinput.input(f"Enter {choice}:", type="text", theme=theme)
                if new_val is not None:
                    working_copy[choice] = new_val

def show_qr(data_dict, ec, theme_name):
    t = cinput.get_theme(theme_name)
    qr = None
    
    while True:
        if qr is None:
            dclear(t['modal_bg'])
            drect(0, 0, 320, 40, t['accent'])
            dtext_opt(160, 20, t['txt_acc'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "Generating...", -1)
            dtext_opt(160, 264, t['txt'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "Building Polynomials...", -1)
            dupdate()
            
            raw_data = compile_data(data_dict)
            qr = QRCode(ec)
            success = qr.make(raw_data)
            
            if not success:
                dclear(t['modal_bg'])
                drect(0, 0, 320, 40, t['accent'])
                dtext_opt(160, 20, t['txt_acc'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "Error", -1)
                dtext_opt(160, 264, C_RED, C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "Data too large! (Max V10)", -1)
                dtext_opt(160, 300, t['txt_dim'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "Press [DEL] to return", -1)
                dupdate()
                while True:
                    ev = pollevent()
                    if ev.type == KEYEV_DOWN and ev.key in [KEY_EXIT, KEY_DEL, KEY_EXE]:
                        return
                    time.sleep(0.01)
                return

        dclear(t['modal_bg'])
        
        # Header
        HEADER_H = 40
        drect(0, 0, 320, HEADER_H, t['accent'])
        dtext_opt(160, HEADER_H//2, t['txt_acc'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, f"QR Preview (V{qr.version})", -1)
        
        # Draw Back Arrow (Left)
        draw_back_arrow(10, 10, C_WHITE)

        # Draw Edit Icon in Top Right (Shifted 2px up -> y-offset is 8 instead of 10)
        edit_poly = [20, 7, 3, 17, 3, 21, 6, 21, 17, 9, 14, 6, 3, 17, 3, 17, 20, 7, 20, 6, 20, 6, 20, 6, 20, 5, 20, 5, 18, 3, 18, 3, 17, 3, 17, 3, 17, 3, 16, 3, 15, 5, 18, 8]
        shifted_poly = [val + (285 if i % 2 == 0 else 8) for i, val in enumerate(edit_poly)]
        dpoly(shifted_poly, C_WHITE, C_NONE)
        
        # Calculate Dynamic Scale (Ensuring it fits optimally)
        padding = 8
        scale = min(320 // (qr.mc + padding), 440 // (qr.mc + padding))
        size = qr.mc * scale
        
        ox = (320 - size) // 2
        oy = HEADER_H + (528 - HEADER_H - size) // 2 - 20
        
        # Base white background for safe contrast
        drect(ox - 4*scale, oy - 4*scale, ox + size + 4*scale, oy + size + 4*scale, C_WHITE)
        
        for r in range(qr.mc):
            for c in range(qr.mc):
                if qr.modules[r][c]:
                    # Draw scaled block
                    drect(ox + c*scale, oy + r*scale, ox + c*scale + scale - 1, oy + r*scale + scale - 1, C_BLACK)

        dtext_opt(160, 500, t['txt'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "Press [DEL] to return", -1)
        dupdate()
        
        action = None
        while action is None:
            ev = pollevent()
            if ev.type == KEYEV_DOWN and ev.key in [KEY_EXIT, KEY_DEL, KEY_EXE]:
                return
            elif ev.type == KEYEV_TOUCH_UP:
                if ev.y < HEADER_H:
                    if ev.x > 260:
                        action = 'edit'
                    elif ev.x < 60:
                        return # Back arrow click logic (same as DEL)
            time.sleep(0.01)
            
        if action == 'edit':
            changed = edit_data(data_dict, theme_name)
            if changed:
                qr = None # Force regeneration in next loop

class App:
    def __init__(self):
        self.ec = 1 # L level defaults
        self.theme = THEME_NAME
        
    def run(self):
        opts = [
            {'type': 'section', 'text': 'Generators'},
            {'type': 'item', 'text': "Text / URL", 'id': 'text', 'arrow': True},
            {'type': 'item', 'text': "Wi-Fi Config", 'id': 'wifi', 'arrow': True},
            {'type': 'item', 'text': "Contact (vCard)", 'id': 'vcard', 'arrow': True},
            {'type': 'section', 'text': 'Options'},
            {'type': 'item', 'text': "Settings", 'id': 'settings', 'arrow': True},
            {'type': 'item', 'text': "Quit", 'id': 'quit'}
        ]
        
        while True:
            lv = cinput.ListView((0, 40, 320, 528-40), opts, row_h=45, headers_h=30, theme=self.theme)
            
            choice = None
            running = True
            
            while running:
                t = cinput.get_theme(self.theme)
                dclear(t['modal_bg'])
                lv.draw()
                
                # Interface Header
                drect(0, 0, 320, 40, t['accent'])
                dtext_opt(160, 20, t['txt_acc'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "QR Builder", -1)
                
                dupdate()
                cleareventflips()
                
                ev = pollevent()
                events = []
                while ev.type != KEYEV_NONE:
                    events.append(ev)
                    ev = pollevent()
                
                if keypressed(KEY_EXIT) or keypressed(KEY_DEL):
                    return
                
                action = lv.update(events)
                if action:
                    type_, idx, item = action
                    if type_ == 'click' and item.get('type') != 'section':
                        choice = item['text']
                        running = False
                        
                time.sleep(0.01)

            if not choice or choice == "Quit":
                break
                
            data_dict = None
            if choice == "Text / URL": data_dict = ask_text()
            elif choice == "Wi-Fi Config": data_dict = ask_wifi()
            elif choice == "Contact (vCard)": data_dict = ask_vcard()
            elif choice == "Settings":
                ec_opts = ["L (7%)", "M (15%)", "Q (25%)", "H (30%)"]
                ec_map = {"L (7%)": 1, "M (15%)": 0, "Q (25%)": 3, "H (30%)": 2}
                ec_choice = cinput.pick(ec_opts, "Error Correction", theme=self.theme)
                if ec_choice: self.ec = ec_map[ec_choice]
                continue
                
            if data_dict:
                show_qr(data_dict, self.ec, self.theme)

# Start Application
App().run()
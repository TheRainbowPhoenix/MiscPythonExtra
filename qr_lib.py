from gint import *

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

# --- Helpful rendering tool ---
def draw_qr(qr, x, y, size, fg=C_BLACK, bg=C_WHITE):
    """Draws a generated QRCode object securely to the screen"""
    padding = 2
    scale = size // (qr.mc + padding * 2)
    actual_size = qr.mc * scale
    
    ox = x + (size - actual_size) // 2
    oy = y + (size - actual_size) // 2
    
    # White background with safety padding for reliable scanning
    drect(ox - padding*scale, oy - padding*scale, ox + actual_size + padding*scale, oy + actual_size + padding*scale, bg)
    
    for r in range(qr.mc):
        for c in range(qr.mc):
            if qr.modules[r][c]:
                drect(ox + c*scale, oy + r*scale, ox + c*scale + scale - 1, oy + r*scale + scale - 1, fg)
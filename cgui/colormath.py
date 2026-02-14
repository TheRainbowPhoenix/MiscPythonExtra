from gint import *

def unpack_color(c):
    # Unpack RGB565 (standard gint buffer format)
    # Output scaled to 0-31 for compatibility with existing tools
    r = (c >> 11) & 0x1F
    g_6 = (c >> 5) & 0x3F
    g = g_6 >> 1 # Scale 6-bit (0-63) to 5-bit (0-31)
    b = c & 0x1F
    return r, g, b

def pack_color(r, g, b):
    r = max(0, min(31, int(r)))
    g = max(0, min(31, int(g)))
    b = max(0, min(31, int(b)))
    return C_RGB(r, g, b)

# --- RGB <-> HSB ---

def hsb_to_rgb(h, s, v):
    # h:0-360, s:0-1, v:0-1 -> r,g,b 0-31
    c = v * s
    x = c * (1 - abs(((h / 60) % 2) - 1))
    m = v - c
    
    if 0 <= h < 60: r, g, b = c, x, 0
    elif 60 <= h < 120: r, g, b = x, c, 0
    elif 120 <= h < 180: r, g, b = 0, c, x
    elif 180 <= h < 240: r, g, b = 0, x, c
    elif 240 <= h < 300: r, g, b = x, 0, c
    else: r, g, b = c, 0, x
    
    return int((r+m)*31), int((g+m)*31), int((b+m)*31)

def rgb_to_hsb(r, g, b):
    # r,g,b: 0-31 -> h:0-360, s:0-1, v:0-1
    r, g, b = r/31.0, g/31.0, b/31.0
    mx = max(r, g, b)
    mn = min(r, g, b)
    df = mx - mn
    
    if mx == mn: h = 0
    elif mx == r: h = (60 * ((g-b)/df) + 360) % 360
    elif mx == g: h = (60 * ((b-r)/df) + 120) % 360
    elif mx == b: h = (60 * ((r-g)/df) + 240) % 360
    
    s = 0 if mx == 0 else (df / mx)
    v = mx
    return h, s, v

# --- RGB <-> HLS (Hue, Lightness, Saturation) ---

def hls_to_rgb(h, l, s):
    # h: 0-360, l: 0-1, s: 0-1
    # Output: 0-31
    def hue_to_rgb(p, q, t):
        if t < 0: t += 1
        if t > 1: t -= 1
        if t < 1/6: return p + (q - p) * 6 * t
        if t < 1/2: return q
        if t < 2/3: return p + (q - p) * (2/3 - t) * 6
        return p

    if s == 0:
        r = g = b = l
    else:
        q = l * (1 + s) if l < 0.5 else l + s - l * s
        p = 2 * l - q
        hk = h / 360
        r = hue_to_rgb(p, q, hk + 1/3)
        g = hue_to_rgb(p, q, hk)
        b = hue_to_rgb(p, q, hk - 1/3)
        
    return int(r*31), int(g*31), int(b*31)

def rgb_to_hls(r, g, b):
    # r,g,b: 0-31 -> h:0-360, l:0-1, s:0-1
    r, g, b = r/31.0, g/31.0, b/31.0
    mx = max(r, g, b)
    mn = min(r, g, b)
    l = (mx + mn) / 2
    
    if mx == mn:
        h = 0
        s = 0
    else:
        d = mx - mn
        s = d / (2 - mx - mn) if l > 0.5 else d / (mx + mn)
        if mx == r: h = (g - b) / d + (6 if g < b else 0)
        elif mx == g: h = (b - r) / d + 2
        elif mx == b: h = (r - g) / d + 4
        h *= 60
        
    return h, l, s

# --- RGB <-> CMYK ---

def cmyk_to_rgb(c, m, y, k):
    # c,m,y,k: 0-100 -> r,g,b 0-31
    ck = k / 100.0
    cc = c / 100.0
    cm = m / 100.0
    cy = y / 100.0
    
    r = 31 * (1.0 - cc) * (1.0 - ck)
    g = 31 * (1.0 - cm) * (1.0 - ck)
    b = 31 * (1.0 - cy) * (1.0 - ck)
    return int(r), int(g), int(b)

def rgb_to_cmyk(r, g, b):
    # r,g,b: 0-31 -> c,m,y,k 0-100
    if r == 0 and g == 0 and b == 0:
        return 0, 0, 0, 100
    
    r, g, b = r/31.0, g/31.0, b/31.0
    k = 1 - max(r, g, b)
    c = (1 - r - k) / (1 - k)
    m = (1 - g - k) / (1 - k)
    y = (1 - b - k) / (1 - k)
    
    return int(c*100), int(m*100), int(y*100), int(k*100)
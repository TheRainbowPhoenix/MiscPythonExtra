from gint import *
import time
import math
import struct
import qr_lib

# Colors (RGB555 format: 0-31)
C_BG       = C_RGB(3, 4, 5)
C_PANEL    = C_RGB(6, 7, 8)
C_PANEL_HL = C_RGB(10, 12, 14)
C_BORDER   = C_RGB(4, 5, 6)
C_TEXT     = C_RGB(31, 31, 31)
C_TEXT_DIM = C_RGB(15, 15, 15)
C_ACCENT   = C_RGB(31, 16, 0) # Orange-ish highlight

# Synthesizer State
oscs = [
    {"wave": 0, "vol": 1.0, "coarse": 0, "fine": 0},
    {"wave": 1, "vol": 0.0, "coarse": 0, "fine": 0},
    {"wave": 2, "vol": 0.0, "coarse": 0, "fine": 0}
]

def draw_wave_icon(x, y, wave_type, color):
    if wave_type == 0:   # Sine
        dline(x, y+10, x+4, y+4, color)
        dline(x+4, y+4, x+10, y+10, color)
        dline(x+10, y+10, x+16, y+16, color)
        dline(x+16, y+16, x+20, y+10, color)
    elif wave_type == 1: # Square
        dline(x, y+16, x, y+4, color)
        dline(x, y+4, x+10, y+4, color)
        dline(x+10, y+4, x+10, y+16, color)
        dline(x+10, y+16, x+20, y+16, color)
    elif wave_type == 2: # Saw
        dline(x, y+16, x+20, y+4, color)
        dline(x+20, y+4, x+20, y+16, color)
    elif wave_type == 3: # Triangle
        dline(x, y+16, x+10, y+4, color)
        dline(x+10, y+4, x+20, y+16, color)

def draw_slider(x, y, w, val_pct, label, value_str):
    dline(x, y+10, x+w, y+10, C_TEXT_DIM)
    thumb_x = x + int(val_pct * w)
    dcircle(thumb_x, y+10, 6, C_PANEL_HL, C_TEXT)
    dcircle(thumb_x, y+10, 2, C_ACCENT, C_NONE)
    dtext_opt(x + w//2, y - 5, C_TEXT_DIM, C_NONE, DTEXT_CENTER, DTEXT_BOTTOM, label, -1)
    dtext_opt(x + w//2, y + 25, C_TEXT, C_NONE, DTEXT_CENTER, DTEXT_TOP, value_str, -1)

def draw_ui():
    dclear(C_BG)
    dtext_opt(DWIDTH//2, 20, C_TEXT, C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "3x OSCILLATOR", -1)
    
    for i in range(3):
        y_start = 50 + i * 140
        osc = oscs[i]
        
        drect(5, y_start, DWIDTH-5, y_start+130, C_PANEL)
        drect_border(5, y_start, DWIDTH-5, y_start+130, C_NONE, 1, C_BORDER)
        dtext_opt(15, y_start+15, C_TEXT, C_NONE, DTEXT_LEFT, DTEXT_MIDDLE, f"OSC {i+1}", -1)
        
        for w in range(4):
            bx = 15 + w * 32
            by = y_start + 30
            is_active = (osc['wave'] == w)
            bg_col = C_PANEL_HL if is_active else C_BG
            border_col = C_ACCENT if is_active else C_BORDER
            
            drect(bx, by, bx+28, by+28, bg_col)
            drect_border(bx, by, bx+28, by+28, C_NONE, 1, border_col)
            draw_wave_icon(bx+4, by+4, w, C_ACCENT if is_active else C_TEXT_DIM)
        
        draw_slider(160, y_start + 40, 140, osc['vol'], "VOLUME", f"{int(osc['vol']*100)}%")
        coarse_pct = (osc['coarse'] + 24) / 48.0
        draw_slider(15, y_start + 90, 120, coarse_pct, "COARSE", str(osc['coarse']))
        fine_pct = (osc['fine'] + 100) / 200.0
        draw_slider(160, y_start + 90, 140, fine_pct, "FINE", str(osc['fine']))

    dtext_opt(DWIDTH//2, DHEIGHT-20, C_TEXT_DIM, C_NONE, DTEXT_CENTER, DTEXT_BOTTOM, "[EXE] Export & QR | [EXIT] Quit", -1)

def update_param(osc_idx, param, x):
    osc = oscs[osc_idx]
    if param == 'vol':
        val = (x - 160) / 140.0
        osc['vol'] = max(0.0, min(1.0, val))
    elif param == 'coarse':
        val = int(round((x - 15) / 120.0 * 48)) - 24
        osc['coarse'] = max(-24, min(24, val))
    elif param == 'fine':
        val = int(round((x - 160) / 140.0 * 200)) - 100
        osc['fine'] = max(-100, min(100, val))

def generate_wavetable():
    drect(60, 200, 260, 280, C_BG)
    drect_border(60, 200, 260, 280, C_NONE, 2, C_ACCENT)
    dtext_opt(DWIDTH//2, 240, C_TEXT, C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "Computing Wave & QR...", -1)
    dupdate()
    
    # 1. SAVE THE WAV FILE
    buffer = [0.0] * 256
    for osc in oscs:
        if osc['vol'] <= 0.001: continue
        freq = 2.0 ** (osc['coarse'] / 12.0 + osc['fine'] / 1200.0)
        
        for i in range(256):
            phase = (i * freq / 256.0) % 1.0
            val = 0.0
            if osc['wave'] == 0:   val = math.sin(phase * 2 * math.pi)
            elif osc['wave'] == 1: val = 1.0 if phase < 0.5 else -1.0
            elif osc['wave'] == 2: val = 1.0 - 2.0 * phase
            elif osc['wave'] == 3: val = 4.0 * phase - 1.0 if phase < 0.5 else 3.0 - 4.0 * phase
            buffer[i] += val * osc['vol']
            
    max_amp = max([abs(s) for s in buffer])
    if max_amp > 1.0:
        buffer = [s / max_amp for s in buffer]
        
    samples = [int(s * 32760) for s in buffer]
    data_block = struct.pack('<' + 'h' * 256, *samples)
    header = struct.pack('<4sI4s4sIHHIIHH4sI',
        b'RIFF', 36 + len(data_block), b'WAVE', b'fmt ', 16, 1, 1, 44100, 44100 * 2, 2, 16, b'data', len(data_block))
    
    try:
        with open("wt_osc.wav", "wb") as f:
            f.write(header)
            f.write(data_block)
    except Exception as e:
        print("Save Error")

    # 2. GENERATE AND SHOW QR CODE
    patch_str = "|".join([f"{o['wave']},{o['vol']:.2f},{o['coarse']},{o['fine']}" for o in oscs])
    url = f"https://wt.pho3.be/?p={patch_str}"
    
    qr = qr_lib.QRCode(1) # Level L for minimum size
    if qr.make(url):
        dclear(C_BG)
        qr_lib.draw_qr(qr, DWIDTH//2 - 120, 80, 240, C_BLACK, C_WHITE)
        
        dtext_opt(DWIDTH//2, 350, C_TEXT, C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "Saved to wt_osc.wav!", -1)
        dtext_opt(DWIDTH//2, 380, C_TEXT_DIM, C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "Scan QR to load in Web Synth", -1)
        dtext_opt(DWIDTH//2, 450, C_ACCENT, C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "[Press Any Key]", -1)
        dupdate()
        
        clearevents()
        while True:
            ev = pollevent()
            if ev.type == KEYEV_DOWN: break
            time.sleep(0.01)

def main():
    running = True
    drag_osc = None
    drag_param = None
    clearevents()
    
    while running:
        draw_ui()
        dupdate()
        
        ev = pollevent()
        events = []
        while ev.type != KEYEV_NONE:
            events.append(ev)
            ev = pollevent()
            
        for e in events:
            if e.type == KEYEV_DOWN:
                if e.key == KEY_EXIT: running = False
                elif e.key == KEY_EXE: generate_wavetable()
                    
            elif e.type == KEYEV_TOUCH_DOWN:
                for i in range(3):
                    y_start = 50 + i * 140
                    if y_start <= e.y <= y_start + 130:
                        if 15 <= e.x <= 143 and y_start + 30 <= e.y <= y_start + 58:
                            w = (e.x - 15) // 32
                            if 0 <= w <= 3: oscs[i]['wave'] = w
                        elif 150 <= e.x <= 310 and y_start + 30 <= e.y <= y_start + 70:
                            drag_osc = i; drag_param = 'vol'; update_param(i, 'vol', e.x)
                        elif 5 <= e.x <= 145 and y_start + 80 <= e.y <= y_start + 120:
                            drag_osc = i; drag_param = 'coarse'; update_param(i, 'coarse', e.x)
                        elif 150 <= e.x <= 310 and y_start + 80 <= e.y <= y_start + 120:
                            drag_osc = i; drag_param = 'fine'; update_param(i, 'fine', e.x)

            elif e.type == KEYEV_TOUCH_DRAG:
                if drag_osc is not None and drag_param is not None:
                    update_param(drag_osc, drag_param, e.x)
            elif e.type == KEYEV_TOUCH_UP:
                drag_osc = None; drag_param = None
                
        time.sleep(0.01)
        
main()
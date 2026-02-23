from gint import *
import math
import time

# UI Theme Colors
C_BG       = C_RGB(3, 4, 5)
C_PANEL    = C_RGB(6, 7, 8)
C_PANEL_HL = C_RGB(10, 12, 14)
C_BORDER   = C_RGB(4, 5, 6)
C_TEXT     = C_RGB(31, 31, 31)
C_TEXT_DIM = C_RGB(15, 15, 15)
C_ACCENT   = C_RGB(31, 16, 0)
C_SAW_ACC  = C_RGB(0, 16, 31)

# ==========================================
# 3x OSCILLATOR ENGINE
# ==========================================
class TVST_3xOsc:
    def __init__(self):
        self.oscs = [
            {"wave": 0, "vol": 1.0, "coarse": 0, "fine": 0},
            {"wave": 0, "vol": 0.5, "coarse": -12, "fine": 0},
            {"wave": 0, "vol": 0.25, "coarse": -24, "fine": 0}
        ]
        self.env = {"attack": 0.3, "release": 0.3} 
        self.wt = [0.0] * 256
        self.compile()

    def compile(self):
        self.wt = [0.0] * 256
        for osc in self.oscs:
            if osc['vol'] <= 0.001: continue
            freq = 2.0 ** (osc['coarse'] / 12.0 + osc['fine'] / 1200.0)
            for i in range(256):
                phase = (i * freq / 256.0) % 1.0
                val = 0.0
                if osc['wave'] == 0:   val = math.sin(phase * 2 * math.pi)
                elif osc['wave'] == 1: val = 1.0 if phase < 0.5 else -1.0
                elif osc['wave'] == 2: val = 1.0 - 2.0 * phase
                elif osc['wave'] == 3: val = 4.0 * phase - 1.0 if phase < 0.5 else 3.0 - 4.0 * phase
                self.wt[i] += val * osc['vol']
                
        max_amp = max([abs(s) for s in self.wt] + [0.001])
        if max_amp > 1.0:
            self.wt = [s / max_amp for s in self.wt]

    def render_note(self, buffer, start_idx, freq, duration_samples, sample_rate):
        atk_samples = int(self.env["attack"] * sample_rate)
        rel_samples = int(self.env["release"] * sample_rate)
        max_idx = len(buffer)
        
        base_freq = sample_rate / 256.0
        phase_step = freq / base_freq
        phase = 0.0
        
        total_samples = duration_samples + rel_samples
        for i in range(total_samples):
            buf_i = start_idx + i
            if buf_i >= max_idx: break
            
            env_val = 1.0
            if i < atk_samples and atk_samples > 0:
                env_val = i / atk_samples
            elif i > duration_samples:
                if rel_samples > 0: env_val = max(0.0, 1.0 - ((i - duration_samples) / rel_samples))
                else: env_val = 0.0
            
            idx1 = int(phase) % 256
            idx2 = (idx1 + 1) % 256
            frac = phase - int(phase)
            samp = self.wt[idx1] + frac * (self.wt[idx2] - self.wt[idx1])
            
            buffer[buf_i] += samp * env_val
            phase += phase_step

# ==========================================
# ROLAND-STYLE SUPERSAW ENGINE
# ==========================================
class TVST_Supersaw:
    def __init__(self):
        # Default patch: smooth pad
        self.env = {"attack": 0.4, "release": 0.6}
        self.detune = 0.6
        self.mix = 0.8
        self.vol = 0.7

    def render_note(self, buffer, start_idx, freq, duration_samples, sample_rate):
        atk_samples = int(self.env["attack"] * sample_rate)
        rel_samples = int(self.env["release"] * sample_rate)
        max_idx = len(buffer)
        total_samples = duration_samples + rel_samples
        
        # 7 Detuned Oscillators (Cents map: Center, +/- L1, +/- L2, +/- L3)
        detune_cents = self.detune * 50.0 # Max 50 cents spread
        freqs = [
            freq,
            freq * (2.0 ** (-detune_cents * 0.4 / 1200.0)), freq * (2.0 ** (detune_cents * 0.4 / 1200.0)),
            freq * (2.0 ** (-detune_cents * 0.8 / 1200.0)), freq * (2.0 ** (detune_cents * 0.8 / 1200.0)),
            freq * (2.0 ** (-detune_cents / 1200.0)), freq * (2.0 ** (detune_cents / 1200.0)),
        ]
        
        vols = [1.0, self.mix, self.mix, self.mix*0.8, self.mix*0.8, self.mix*0.6, self.mix*0.6]
        tot = sum(vols)
        vols = [v / tot for v in vols] # Normalize inner oscillators mix
        
        phase = [0.0] * 7
        phase_steps = [f / sample_rate for f in freqs]
        
        # Render Loop (On-the-fly additive saw synthesis)
        for i in range(total_samples):
            buf_i = start_idx + i
            if buf_i >= max_idx: break
            
            env_val = 1.0
            if i < atk_samples and atk_samples > 0:
                env_val = i / atk_samples
            elif i > duration_samples:
                if rel_samples > 0: env_val = max(0.0, 1.0 - ((i - duration_samples) / rel_samples))
                else: env_val = 0.0
                    
            samp = 0.0
            for j in range(7):
                p = phase[j]
                samp += (1.0 - 2.0 * p) * vols[j] # Pure mathematical downward saw
                p += phase_steps[j]
                if p >= 1.0: p -= 1.0
                phase[j] = p
                
            buffer[buf_i] += samp * env_val * self.vol

# ==========================================
# UI COMPONENTS
# ==========================================
def _draw_wave_icon(x, y, wave_type, color):
    if wave_type == 0:
        dline(x, y+10, x+4, y+4, color); dline(x+4, y+4, x+10, y+10, color)
        dline(x+10, y+10, x+16, y+16, color); dline(x+16, y+16, x+20, y+10, color)
    elif wave_type == 1:
        dline(x, y+16, x, y+4, color); dline(x, y+4, x+10, y+4, color)
        dline(x+10, y+4, x+10, y+16, color); dline(x+10, y+16, x+20, y+16, color)
    elif wave_type == 2:
        dline(x, y+16, x+20, y+4, color); dline(x+20, y+4, x+20, y+16, color)
    elif wave_type == 3:
        dline(x, y+16, x+10, y+4, color); dline(x+10, y+4, x+20, y+16, color)

def _draw_slider(x, y, w, val_pct, label, value_str, accent=C_ACCENT):
    dline(x, y+10, x+w, y+10, C_TEXT_DIM)
    thumb_x = x + int(val_pct * w)
    dcircle(thumb_x, y+10, 6, C_PANEL_HL, C_TEXT)
    dcircle(thumb_x, y+10, 2, accent, C_NONE)
    dtext_opt(x + w//2, y - 5, C_TEXT_DIM, C_NONE, DTEXT_CENTER, DTEXT_BOTTOM, label, -1)
    dtext_opt(x + w//2, y + 25, C_TEXT, C_NONE, DTEXT_CENTER, DTEXT_TOP, value_str, -1)

def _update_param(synth, osc_idx, param, x):
    if osc_idx == 'env':
        if param == 'att': synth.env['attack'] = max(0.01, min(2.0, (x - 15) / 120.0 * 2.0))
        elif param == 'rel': synth.env['release'] = max(0.01, min(3.0, (x - 160) / 140.0 * 3.0))
    else:
        osc = synth.oscs[osc_idx]
        if param == 'vol': osc['vol'] = max(0.0, min(1.0, (x - 160) / 140.0))
        elif param == 'coarse': osc['coarse'] = max(-24, min(24, int(round((x - 15) / 120.0 * 48)) - 24))
        elif param == 'fine': osc['fine'] = max(-100, min(100, int(round((x - 160) / 140.0 * 200)) - 100))

def _update_saw_param(synth, param, x):
    if param == 'vol': synth.vol = max(0.0, min(1.0, (x - 15) / 120.0))
    elif param == 'detune': synth.detune = max(0.0, min(1.0, (x - 160) / 140.0))
    elif param == 'mix': synth.mix = max(0.0, min(1.0, (x - 15) / 120.0))

# ==========================================
# DIALOG CONTROLLERS
# ==========================================
def open_synth_dialog(synth):
    running = True
    drag_osc, drag_param = None, None
    clearevents()
    
    while running:
        dclear(C_BG)
        drect(0, 0, DWIDTH, 30, C_PANEL_HL)
        dtext_opt(DWIDTH//2, 15, C_TEXT, C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "TinyVST: 3xOsc", -1)
        
        for i in range(3):
            y_s = 40 + i * 115
            osc = synth.oscs[i]
            drect(5, y_s, DWIDTH-5, y_s+105, C_PANEL)
            drect_border(5, y_s, DWIDTH-5, y_s+105, C_NONE, 1, C_BORDER)
            dtext_opt(15, y_s+15, C_TEXT, C_NONE, DTEXT_LEFT, DTEXT_MIDDLE, f"OSC {i+1}", -1)
            
            for w in range(4):
                bx = 15 + w * 32
                by = y_s + 30
                is_act = (osc['wave'] == w)
                drect(bx, by, bx+28, by+28, C_PANEL_HL if is_act else C_BG)
                drect_border(bx, by, bx+28, by+28, C_NONE, 1, C_ACCENT if is_act else C_BORDER)
                _draw_wave_icon(bx+4, by+4, w, C_ACCENT if is_act else C_TEXT_DIM)
            
            _draw_slider(160, y_s + 40, 140, osc['vol'], "VOLUME", f"{int(osc['vol']*100)}%")
            _draw_slider(15, y_s + 85, 120, (osc['coarse'] + 24) / 48.0, "COARSE", str(osc['coarse']))
            _draw_slider(160, y_s + 85, 140, (osc['fine'] + 100) / 200.0, "FINE", str(osc['fine']))

        env_y = 390
        drect(5, env_y, DWIDTH-5, env_y+80, C_PANEL)
        drect_border(5, env_y, DWIDTH-5, env_y+80, C_NONE, 1, C_BORDER)
        dtext_opt(15, env_y+15, C_TEXT, C_NONE, DTEXT_LEFT, DTEXT_MIDDLE, "ENVELOPE", -1)
        _draw_slider(15, env_y + 40, 120, synth.env['attack']/2.0, "ATTACK", f"{synth.env['attack']:.2f}s")
        _draw_slider(160, env_y + 40, 140, synth.env['release']/3.0, "RELEASE", f"{synth.env['release']:.2f}s")

        dtext_opt(DWIDTH//2, DHEIGHT-20, C_TEXT_DIM, C_NONE, DTEXT_CENTER, DTEXT_BOTTOM, "[EXE] Apply & Close", -1)
        dupdate()
        
        ev = pollevent()
        events = []
        while ev.type != KEYEV_NONE: events.append(ev); ev = pollevent()
            
        for e in events:
            if e.type == KEYEV_DOWN and e.key == KEY_EXE:
                synth.compile()
                running = False
            elif e.type == KEYEV_TOUCH_DOWN:
                for i in range(3):
                    ys = 40 + i * 115
                    if ys <= e.y <= ys + 105:
                        if 15 <= e.x <= 143 and ys + 30 <= e.y <= ys + 58:
                            w = (e.x - 15) // 32
                            if 0 <= w <= 3: synth.oscs[i]['wave'] = w
                        elif 150 <= e.x <= 310 and ys + 20 <= e.y <= ys + 60:
                            drag_osc, drag_param = i, 'vol'; _update_param(synth, i, 'vol', e.x)
                        elif 5 <= e.x <= 145 and ys + 65 <= e.y <= ys + 105:
                            drag_osc, drag_param = i, 'coarse'; _update_param(synth, i, 'coarse', e.x)
                        elif 150 <= e.x <= 310 and ys + 65 <= e.y <= ys + 105:
                            drag_osc, drag_param = i, 'fine'; _update_param(synth, i, 'fine', e.x)
                if env_y <= e.y <= env_y + 80:
                    if 5 <= e.x <= 145 and env_y + 20 <= e.y <= env_y + 70: drag_osc, drag_param = 'env', 'att'; _update_param(synth, 'env', 'att', e.x)
                    elif 150 <= e.x <= 310 and env_y + 20 <= e.y <= env_y + 70: drag_osc, drag_param = 'env', 'rel'; _update_param(synth, 'env', 'rel', e.x)

            elif e.type == KEYEV_TOUCH_DRAG:
                if drag_osc is not None and drag_param is not None: _update_param(synth, drag_osc, drag_param, e.x)
            elif e.type == KEYEV_TOUCH_UP: drag_osc, drag_param = None, None
        time.sleep(0.01)

def open_supersaw_dialog(synth):
    running = True
    drag_param = None
    clearevents()
    
    while running:
        dclear(C_BG)
        drect(0, 0, DWIDTH, 30, C_PANEL_HL)
        dtext_opt(DWIDTH//2, 15, C_TEXT, C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "TinyVST: Supersaw", -1)
        
        # Generator Settings
        y_s = 50
        drect(5, y_s, DWIDTH-5, y_s+140, C_PANEL)
        drect_border(5, y_s, DWIDTH-5, y_s+140, C_NONE, 1, C_BORDER)
        dtext_opt(15, y_s+15, C_TEXT, C_NONE, DTEXT_LEFT, DTEXT_MIDDLE, "OSCILLATOR", -1)
        
        _draw_slider(15, y_s + 40, 120, synth.vol, "VOLUME", f"{int(synth.vol*100)}%", C_SAW_ACC)
        _draw_slider(160, y_s + 40, 140, synth.detune, "DETUNE", f"{int(synth.detune*100)}%", C_SAW_ACC)
        _draw_slider(15, y_s + 90, 120, synth.mix, "STEREO MIX", f"{int(synth.mix*100)}%", C_SAW_ACC)

        # Env Settings
        env_y = 210
        drect(5, env_y, DWIDTH-5, env_y+80, C_PANEL)
        drect_border(5, env_y, DWIDTH-5, env_y+80, C_NONE, 1, C_BORDER)
        dtext_opt(15, env_y+15, C_TEXT, C_NONE, DTEXT_LEFT, DTEXT_MIDDLE, "ENVELOPE", -1)
        _draw_slider(15, env_y + 40, 120, synth.env['attack']/2.0, "ATTACK", f"{synth.env['attack']:.2f}s", C_SAW_ACC)
        _draw_slider(160, env_y + 40, 140, synth.env['release']/3.0, "RELEASE", f"{synth.env['release']:.2f}s", C_SAW_ACC)

        dtext_opt(DWIDTH//2, DHEIGHT-20, C_TEXT_DIM, C_NONE, DTEXT_CENTER, DTEXT_BOTTOM, "[EXE] Apply & Close", -1)
        dupdate()
        
        ev = pollevent()
        events = []
        while ev.type != KEYEV_NONE: events.append(ev); ev = pollevent()
            
        for e in events:
            if e.type == KEYEV_DOWN and e.key == KEY_EXE:
                running = False
            elif e.type == KEYEV_TOUCH_DOWN:
                if y_s <= e.y <= y_s + 140:
                    if 5 <= e.x <= 145 and y_s + 20 <= e.y <= y_s + 70: drag_param = 'vol'; _update_saw_param(synth, 'vol', e.x)
                    elif 150 <= e.x <= 310 and y_s + 20 <= e.y <= y_s + 70: drag_param = 'detune'; _update_saw_param(synth, 'detune', e.x)
                    elif 5 <= e.x <= 145 and y_s + 75 <= e.y <= y_s + 120: drag_param = 'mix'; _update_saw_param(synth, 'mix', e.x)
                elif env_y <= e.y <= env_y + 80:
                    if 5 <= e.x <= 145 and env_y + 20 <= e.y <= env_y + 70: drag_param = 'att'; _update_param(synth, 'env', 'att', e.x)
                    elif 150 <= e.x <= 310 and env_y + 20 <= e.y <= env_y + 70: drag_param = 'rel'; _update_param(synth, 'env', 'rel', e.x)

            elif e.type == KEYEV_TOUCH_DRAG:
                if drag_param in ['vol', 'detune', 'mix']: _update_saw_param(synth, drag_param, e.x)
                elif drag_param in ['att', 'rel']: _update_param(synth, 'env', drag_param, e.x)
            elif e.type == KEYEV_TOUCH_UP: drag_param = None
        time.sleep(0.01)
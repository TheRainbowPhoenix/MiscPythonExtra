from gint import *
import cinput
import time
import math

try:
    import cinput
except ImportError:
    print("ERROR: 'cinput' module not found!")
    print("This program requires the cinput module for user input handling.")
    print("Please download and paste cinput.py in the same folder as this file.")

#  Constants & Colors ---
DWIDTH = 320
DHEIGHT = 528
HEADER_H = 40
ROOT_BAR_H = 80
PIANO_H = 132  # 1/4 of screen height

# Colors (RGB555: 0-31)
COL_BG = C_RGB(28, 28, 28)        # Dark grey
COL_HEADER = C_RGB(5, 5, 5)       # Near black
COL_ACCENT = C_RGB(31, 20, 0)     # Gold/Yellow
COL_WHITE = C_RGB(31, 31, 31)
COL_BLACK = C_RGB(0, 0, 0)
COL_GREY_DIM = C_RGB(14, 14, 14)  # Brighter grey for inactive keys
COL_GREY_DARK = C_RGB(5, 5, 5)    # Inactive black keys
COL_TEXT = C_RGB(31, 31, 31)
COL_CHORD_BG = C_RGB(31, 31, 25)  # Paper/Yellowish
COL_MUTED = C_RGB(15, 15, 15)
COL_STAFF_LINE = C_RGB(5, 5, 5)

# Music Data
NOTES_FLAT = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]
NOTES_SHARP = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

#  Data: Scales ---
SCALE_PATTERNS = {
    "Major": [0, 2, 4, 5, 7, 9, 11],
    "Minor (Aeolian)": [0, 2, 3, 5, 7, 8, 10],
    "Dominant (Mixolydian)": [0, 2, 4, 5, 7, 9, 10],
    "Dorian": [0, 2, 3, 5, 7, 9, 10],
    "Phrygian": [0, 1, 3, 5, 7, 8, 10],
    "Lydian": [0, 2, 4, 6, 7, 9, 11],
    "Locrian": [0, 1, 3, 5, 6, 8, 10],
    "Harmonic Minor": [0, 2, 3, 5, 7, 8, 11],
    "Melodic Minor": [0, 2, 3, 5, 7, 9, 11],
    "Pentatonic Major": [0, 2, 4, 7, 9],
    "Pentatonic Minor": [0, 3, 5, 7, 10],
    "Blues": [0, 3, 5, 6, 7, 10],
    "Whole Tone": [0, 2, 4, 6, 8, 10],
    "Diminished": [0, 3, 6, 9],
    "Augmented": [0, 4, 8]
}

SCALE_CATEGORIES = {
    "--- Major / Common ---": ["Major", "Dominant (Mixolydian)", "Lydian", "Pentatonic Major"],
    "--- Minor ---": ["Minor (Aeolian)", "Dorian", "Phrygian", "Locrian", "Harmonic Minor", "Melodic Minor", "Pentatonic Minor"],
    "--- Other ---": ["Blues", "Whole Tone", "Diminished", "Augmented"]
}

#  Data: Guitar Chords ---
GUITAR_CATEGORIES = {
    "--- Basic ---": ["Major", "Minor", "5", "7", "Major 7th", "Minor 7th", "Sus2", "Sus4"],
    "--- Extended ---": ["6", "m6", "Add2", "Add9", "9", "m9", "Maj9", "7sus4", "9sus4"],
    "--- Advanced ---": ["Dim", "Dim7", "Aug", "m7b5", "11", "m11", "13", "m13"]
}

BARRE_SHAPES = {
    "Major": [(0, "022100"), (1, "x02220")],
    "Minor": [(0, "022000"), (1, "x02210")],
    "5": [(0, "022xxx"), (1, "x022xx")],
    "7": [(0, "020100"), (1, "x02020")],
    "Major 7th": [(0, "021100"), (1, "x02120")],
    "Minor 7th": [(0, "020000"), (1, "x02010")],
    "Sus4": [(0, "022200"), (1, "x02230")],
    "Sus2": [(0, "022xxx"), (1, "x02200")],
    "7sus4": [(0, "020200"), (1, "x02030")],
    "6": [(0, "0x222x"), (1, "x02222")],
    "m6": [(0, "0x221x"), (1, "x02211")],
    "Add9": [(0, "022102"), (1, "x02200")],
    "9": [(0, "020102"), (1, "x02022")],
    "m9": [(0, "020002"), (1, "x02012")],
    "Dim": [(0, "xx1212"), (1, "x0121x")],
    "Dim7": [(0, "xx1212"), (1, "x01212")],
    "Aug": [(0, "032110"), (1, "x02120")],
    "m7b5": [(0, "01001x"), (1, "x0101x")]
}

OPEN_CHORDS = {
    0: { "Major": ["x32010"], "Major 7th": ["x32000"], "7": ["x32310"], "Add9": ["x32030"] },
    2: { "Major": ["xx0232"], "Minor": ["xx0231"], "7": ["xx0212"], "Minor 7th": ["xx0211"], "Sus4": ["xx0233"], "Sus2": ["xx0230"] },
    4: { "Major": ["022100"], "Minor": ["022000"], "7": ["020100"], "Minor 7th": ["020000"] },
    7: { "Major": ["320003"], "7": ["320001"], "Sus4": ["3x0013"] },
    9: { "Major": ["x02220"], "Minor": ["x02210"], "7": ["x02020"], "Minor 7th": ["x02010"], "Sus2": ["x02200"], "Sus4": ["x02230"] }
}

#  State ---
class AppState:
    def __init__(self):
        self.root_idx = 0      # 0=C
        self.scale_name = "Major" 
        self.chord_name = "Major" 
        self.note_mode = "flat"
        self.page = "Main"
        self.running = True
        self.needs_redraw = True
        self.chord_variant_idx = 0
        self.cached_chords = []

state = AppState()

#  Helpers ---

def get_current_notes():
    return NOTES_FLAT if state.note_mode == "flat" else NOTES_SHARP

def get_scale_notes_indices():
    pattern = SCALE_PATTERNS.get(state.scale_name, [])
    return [(state.root_idx + s) for s in pattern]

def parse_chord_string(cstr):
    res = []
    if ',' in cstr: parts = cstr.split(',')
    else: parts = list(cstr)
    for p in parts:
        if p.lower() == 'x': res.append(None)
        else: 
            try: res.append(int(p))
            except: res.append(None)
    while len(res) < 6: res.append(None)
    return res[:6]

def generate_guitar_chords():
    root = state.root_idx
    quality = state.chord_name
    candidates = []
    if root in OPEN_CHORDS and quality in OPEN_CHORDS[root]:
        candidates.extend(OPEN_CHORDS[root][quality])
    if quality in BARRE_SHAPES:
        shapes = BARRE_SHAPES[quality]
        for base_str_idx, pattern in shapes:
            base_note = 4 if base_str_idx == 0 else 9 
            fret = (root - base_note) % 12
            pat_vals = parse_chord_string(pattern)
            new_chord = []
            for val in pat_vals:
                if val is None: new_chord.append(None)
                else: new_chord.append(val + fret)
            candidates.append(new_chord)
    final_list = []
    for c in candidates:
        if isinstance(c, str): final_list.append(parse_chord_string(c))
        else: final_list.append(c)
    state.cached_chords = final_list
    state.chord_variant_idx = 0

#  Staff Drawing Helpers ---

def get_diatonic_step(semitone_idx, mode):
    s = semitone_idx % 12
    if mode == "flat":
        m = {0:(0,0), 1:(1,-1), 2:(1,0), 3:(2,-1), 4:(2,0), 5:(3,0), 6:(4,-1), 7:(4,0), 8:(5,-1), 9:(5,0), 10:(6,-1), 11:(6,0)}
        return m[s]
    else:
        m = {0:(0,0), 1:(0,1), 2:(1,0), 3:(1,1), 4:(2,0), 5:(3,0), 6:(3,1), 7:(4,0), 8:(4,1), 9:(5,0), 10:(5,1), 11:(6,0)}
        return m[s]

TREBLE_POLY = [
    191, 138, 191, 166, 177, 201, 160, 218, 167, 250, 160, 250, 153, 225, 153, 225, 118, 264, 
    107, 299, 118, 323, 142, 344, 177, 344, 163, 271, 170, 271, 184, 341, 202, 334, 212, 313, 
    205, 288, 188, 271, 170, 271, 170, 271, 163, 271, 142, 281, 135, 302, 146, 323, 167, 337, 
    160, 337, 142, 327, 128, 309, 128, 288, 135, 267, 160, 250, 167, 250, 184, 250, 202, 257, 
    219, 274, 223, 302, 219, 323, 205, 341, 184, 348, 195, 400, 184, 421, 156, 435, 139, 428, 
    125, 411, 125, 400, 135, 383, 149, 379, 163, 390, 167, 407, 153, 421, 139, 421, 146, 425, 
    156, 428, 181, 418, 188, 400, 177, 351, 142, 351, 118, 337, 97, 309, 93, 274, 125, 222, 
    149, 197, 153, 194, 170, 176, 184, 138, 174, 113, 174, 113, 160, 127, 149, 166, 153, 194, 
    149, 197, 142, 169, 142, 138, 156, 99, 174, 89, 191, 138
]

TREBLE_DOT = [
    167, 400, 164, 411, 156, 418, 146, 421, 135, 418, 127, 411, 125, 400, 127, 390, 
    135, 382, 146, 379, 156, 382, 164, 390
]

def draw_treble_clef(x, y_g_line, size):
    col = COL_BLACK
    
    src_cx, src_cy = 146, 300
    
    # Determine scaling factor. 
    # The original shape spans roughly ~300px height (y=125 to 435).
    # The target visual size relative to staff spacing (size=11) implies 
    # the whole clef height should be around 50px.
    # Target scale = 50 / 300 = ~0.166
    # If size=11, we need multiplier k such that 11 * k = 0.166 => k ~ 0.015
    scale = size * 0.025
    
    # Helper to transform list
    def transform_and_draw(raw_pts):
        poly = []
        for i in range(0, len(raw_pts), 2):
            px = raw_pts[i]
            py = raw_pts[i+1]
            tx = int(x + (px - src_cx) * scale)
            ty = int(y_g_line + (py - src_cy) * scale)
            poly.extend([tx, ty])
        dpoly(poly, col, C_NONE)

    transform_and_draw(TREBLE_POLY)
    transform_and_draw(TREBLE_DOT)

def draw_staff(x, y, w, h, note_indices):
    line_spacing = 14
    staff_h = line_spacing * 4
    staff_top_y = y + (h - staff_h) // 2
    line_ys = [staff_top_y + i*line_spacing for i in range(5)]
    
    for ly in line_ys:
        dline(x, ly, x+w, ly, COL_STAFF_LINE)
        
    g_line_y = line_ys[3]
    draw_treble_clef(x + 30, g_line_y, 11)
    
    bottom_line_y = line_ys[4]
    step_h = line_spacing / 2
    note_x = x + 70
    note_spacing = (w - 100) / (len(note_indices) + 1)
    if note_spacing > 40: note_spacing = 40
    
    for abs_semitone in note_indices:
        octave = abs_semitone // 12
        step_in_octave, acc = get_diatonic_step(abs_semitone, state.note_mode)
        total_steps_from_c4 = step_in_octave + (octave * 7)
        delta_steps = 2 - total_steps_from_c4
        note_y = int(bottom_line_y + delta_steps * step_h)
        
        # Ledger Lines
        if total_steps_from_c4 <= 0:
            curr_s = 0
            while curr_s >= total_steps_from_c4:
                if curr_s % 2 == 0:
                     ly = int(bottom_line_y + (2 - curr_s) * step_h)
                     dline(int(note_x - 10), ly, int(note_x + 10), ly, COL_STAFF_LINE)
                curr_s -= 1
        
        if total_steps_from_c4 > 10:
             curr_s = 12
             while curr_s <= total_steps_from_c4:
                 if curr_s % 2 == 0:
                     ly = int(bottom_line_y + (2 - curr_s) * step_h)
                     dline(int(note_x - 10), ly, int(note_x + 10), ly, COL_STAFF_LINE)
                 curr_s += 2

        dcircle(int(note_x), note_y, 5, COL_BLACK, COL_BLACK)
        
        if total_steps_from_c4 >= 6:
            dline(int(note_x)-5, note_y, int(note_x)-5, note_y+25, COL_BLACK)
        else:
            dline(int(note_x)+5, note_y, int(note_x)+5, note_y-25, COL_BLACK)
            
        if acc != 0:
            sym = "#" if acc == 1 else "b"
            # Reduced spacing: from -15 to -8
            dtext_opt(int(note_x) - 8, note_y, COL_BLACK, C_NONE, DTEXT_RIGHT, DTEXT_MIDDLE, sym, -1)
            
        note_x += note_spacing

#  Drawing Helpers ---

def draw_header():
    drect(0, 0, DWIDTH, HEADER_H, COL_HEADER)
    for i in range(3): drect(10, 12 + i*6, 28, 13 + i*6, COL_WHITE)
    
    if state.page == "Guitar Tabs": label = state.chord_name
    else: label = state.scale_name
        
    title_text = f"{get_current_notes()[state.root_idx]} {label}"
    tw, _ = dsize(title_text, None)
    box_w = tw + 40
    box_x = (DWIDTH - box_w) // 2
    drect_border(box_x, 4, box_x + box_w, 36, C_NONE, 1, COL_GREY_DIM)
    dtext_opt(DWIDTH//2 - 5, HEADER_H//2, COL_WHITE, C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, title_text, -1)
    
    ax = box_x + box_w - 15
    dpoly([ax-4, 18, ax+4, 18, ax, 24], COL_WHITE, C_NONE)
    
    mode_text = "#" if state.note_mode == "flat" else "b"
    drect_border(DWIDTH - 35, 6, DWIDTH - 5, 34, C_NONE, 1, COL_GREY_DIM)
    dtext_opt(DWIDTH - 20, HEADER_H//2, COL_WHITE, C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, mode_text, -1)

def draw_root_bar():
    y = HEADER_H
    notes = get_current_notes()
    kw = DWIDTH // 12
    scale_indices = [(x % 12) for x in get_scale_notes_indices()]
    
    for i in range(12):
        x = i * kw
        is_sel = (i == state.root_idx)
        in_scale = i in scale_indices if state.page != "Guitar Tabs" else True
        
        if is_sel: bg, txt = COL_ACCENT, COL_BLACK
        elif in_scale: bg, txt = COL_WHITE, COL_BLACK
        else: bg, txt = C_RGB(8, 8, 8), C_RGB(18, 18, 18)
        
        drect(x, y, x + kw, y + ROOT_BAR_H, bg)
        drect_border(x, y, x + kw, y + ROOT_BAR_H, C_NONE, 1, COL_GREY_DIM)
        dtext_opt(x + kw//2, y + ROOT_BAR_H//2, txt, C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, notes[i], -1)

def draw_piano_widget(y_top, height, notes_to_highlight):
    # notes_to_highlight: absolute note indices or relative 0-11
    # We display 1 octave: 7 white keys (C D E F G A B)
    # The snippet logic uses DWIDTH // 7
    
    w_key_w = DWIDTH // 7
    b_key_w = w_key_w // 2 + 4
    b_key_h = (height * 2) // 3
    
    white_indices = [0, 2, 4, 5, 7, 9, 11]
    black_indices = [1, 3, 6, 8, 10]
    black_offsets = [0, 1, 3, 4, 5]
    
    scale_mod = [n % 12 for n in notes_to_highlight]
    
    # 1. Draw White Keys
    for i, idx in enumerate(white_indices):
        x = i * w_key_w
        active = idx in scale_mod
        
        # Color Logic
        bg = COL_WHITE if active else COL_GREY_DIM
        
        drect(x, y_top, x + w_key_w, y_top + height, bg)
        drect_border(x, y_top, x + w_key_w, y_top + height, C_NONE, 1, COL_BLACK)
        
        # Text Logic
        txt_col = COL_BLACK if active else C_RGB(15, 15, 15)
        dtext_opt(x + w_key_w//2, y_top + height - 15, txt_col, C_NONE, DTEXT_CENTER, DTEXT_BOTTOM, get_current_notes()[idx], -1)

    # 2. Draw Black Keys
    for i, idx in enumerate(black_indices):
        ox = (black_offsets[i] + 1) * w_key_w - b_key_w // 2
        active = idx in scale_mod
        
        # Color Logic
        bg = COL_BLACK if active else COL_GREY_DARK
        
        drect(ox, y_top, ox + b_key_w, y_top + b_key_h, bg)
        drect_border(ox, y_top, ox + b_key_w, y_top + b_key_h, C_NONE, 1, COL_WHITE if active else COL_BLACK)
        
        # Text Logic
        txt_col = COL_WHITE if active else C_RGB(20, 20, 20)
        lbl = get_current_notes()[idx]
        if len(lbl) > 1: lbl = lbl[0] # Clip
        dtext_opt(ox + b_key_w//2, y_top + b_key_h - 15, txt_col, C_NONE, DTEXT_CENTER, DTEXT_BOTTOM, lbl, -1)

#  Pages ---

def draw_main_page():
    cy = (DHEIGHT - PIANO_H + HEADER_H + ROOT_BAR_H) // 2
    drect(0, HEADER_H + ROOT_BAR_H, DWIDTH, DHEIGHT - PIANO_H, COL_CHORD_BG)
    
    scale_indices = get_scale_notes_indices()
    scale_notes_str = " - ".join([get_current_notes()[i % 12] for i in scale_indices])
    
    dtext_opt(DWIDTH//2, cy - 20, COL_BLACK, C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "Scale Notes:", -1)
    dtext_opt(DWIDTH//2, cy + 10, COL_ACCENT, C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, scale_notes_str, DWIDTH - 20)
    
    # Piano at bottom (1 octave)
    draw_piano_widget(DHEIGHT - PIANO_H, PIANO_H, scale_indices)

def draw_guitar_page():
    y_start = HEADER_H + ROOT_BAR_H
    drect(0, y_start, DWIDTH, DHEIGHT, COL_CHORD_BG)
    if not state.cached_chords:
        dtext_opt(DWIDTH//2, DHEIGHT//2, COL_BLACK, C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "No chord shape found", -1)
        return

    chord = state.cached_chords[state.chord_variant_idx]
    frets = [f for f in chord if f is not None and f > 0]
    min_fret = min(frets) if frets else 0
    max_fret = max(frets) if frets else 0
    start_fret = 1
    if max_fret > 5: start_fret = min_fret
    
    margin_x = 50
    grid_w = DWIDTH - 2 * margin_x
    grid_h = 180
    grid_y = y_start + 60
    
    label = f"{get_current_notes()[state.root_idx]} {state.chord_name}"
    dtext_opt(DWIDTH//2, y_start + 20, COL_BLACK, C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, label, -1)
    v_label = f"Var {state.chord_variant_idx + 1}/{len(state.cached_chords)}"
    dtext_opt(DWIDTH - 10, y_start + 20, COL_GREY_DIM, C_NONE, DTEXT_RIGHT, DTEXT_MIDDLE, v_label, -1)

    fret_h = grid_h // 5
    str_w = grid_w // 5
    for i in range(6):
        x = margin_x + i * str_w
        dline(x, grid_y, x, grid_y + grid_h, COL_BLACK)
    for i in range(6):
        y = grid_y + i * fret_h
        thick = 3 if i == 0 and start_fret == 1 else 1
        drect(margin_x, y, margin_x + grid_w, y + thick, COL_BLACK)
    
    if start_fret > 1:
        dtext_opt(margin_x - 10, grid_y + fret_h//2, COL_BLACK, C_NONE, DTEXT_RIGHT, DTEXT_MIDDLE, f"{start_fret}fr", -1)

    for s_idx, fret_val in enumerate(chord):
        x_pos = margin_x + s_idx * str_w
        y_top = grid_y - 15
        if fret_val is None:
            dtext_opt(x_pos, y_top, COL_MUTED, C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "X", -1)
        elif fret_val == 0:
            dtext_opt(x_pos, y_top, COL_BLACK, C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "O", -1)
        else:
            rel_fret = fret_val - start_fret + 1
            if 1 <= rel_fret <= 5:
                cy = grid_y + (rel_fret - 1) * fret_h + fret_h // 2
                dcircle(x_pos, cy, 10, COL_ACCENT, C_NONE)

    btn_y = DHEIGHT - 50
    drect_border(20, btn_y, 100, btn_y+40, COL_WHITE, 1, COL_BLACK)
    dtext_opt(60, btn_y+20, COL_BLACK, C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "< Prev", -1)
    drect_border(DWIDTH-100, btn_y, DWIDTH-20, btn_y+40, COL_WHITE, 1, COL_BLACK)
    dtext_opt(DWIDTH-60, btn_y+20, COL_BLACK, C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "Next >", -1)

def draw_piano_page():
    y_start = HEADER_H + ROOT_BAR_H
    
    # 1. Staff Area
    staff_h = DHEIGHT - PIANO_H - y_start
    drect(0, y_start, DWIDTH, y_start + staff_h, COL_CHORD_BG)
    
    scale_indices = get_scale_notes_indices()
    
    # Draw Staff in the middle of this area
    draw_staff(0, y_start, DWIDTH, staff_h, scale_indices)
    
    # 2. Large Piano (1 Octave, 7 keys for width match)
    draw_piano_widget(DHEIGHT - PIANO_H, PIANO_H, scale_indices)

#  Logic ---

def handle_touch(tx, ty):
    global state
    if ty < HEADER_H:
        if tx < 50:
            res = cinput.pick(["Main", "Piano Chords", "Guitar Tabs", "Quit"], "Menu", theme="dark")
            if res == "Quit": state.running = False
            elif res: 
                state.page = res
                if res == "Guitar Tabs": generate_guitar_chords()
            state.needs_redraw = True
        elif tx > DWIDTH - 40:
            state.note_mode = "sharp" if state.note_mode == "flat" else "flat"
            state.needs_redraw = True
        elif DWIDTH//2 - 60 < tx < DWIDTH//2 + 60:
            if state.page == "Guitar Tabs":
                opts = []
                for cat, chords in GUITAR_CATEGORIES.items():
                    opts.append(cat)
                    opts.extend(chords)
                res = cinput.pick(opts, "Select Chord", theme="dark")
                if res and not res.startswith("---"):
                    state.chord_name = res
                    generate_guitar_chords()
                    state.needs_redraw = True
            else:
                opts = []
                for cat, scales in SCALE_CATEGORIES.items():
                    opts.append(cat)
                    opts.extend(scales)
                res = cinput.pick(opts, "Select Scale", theme="dark")
                if res and not res.startswith("---"):
                    state.scale_name = res
                    state.needs_redraw = True
    elif HEADER_H <= ty < HEADER_H + ROOT_BAR_H:
        kw = DWIDTH // 12
        new_root = tx // kw
        if 0 <= new_root < 12:
            state.root_idx = new_root
            if state.page == "Guitar Tabs": generate_guitar_chords()
            state.needs_redraw = True
    elif state.page == "Guitar Tabs" and ty > DHEIGHT - 50:
        if 20 <= tx <= 100: 
            if state.cached_chords:
                state.chord_variant_idx = (state.chord_variant_idx - 1) % len(state.cached_chords)
                state.needs_redraw = True
        elif DWIDTH - 100 <= tx <= DWIDTH - 20: 
            if state.cached_chords:
                state.chord_variant_idx = (state.chord_variant_idx + 1) % len(state.cached_chords)
                state.needs_redraw = True

def main():
    state.needs_redraw = True
    generate_guitar_chords() 
    while state.running:
        if state.needs_redraw:
            dclear(COL_BG)
            draw_header()
            draw_root_bar()
            if state.page == "Main": draw_main_page()
            elif state.page == "Piano Chords": draw_piano_page()
            elif state.page == "Guitar Tabs": draw_guitar_page()
            dupdate()
            state.needs_redraw = False
        
        cleareventflips()
        ev = pollevent()
        while ev.type != KEYEV_NONE:
            if ev.type == KEYEV_TOUCH_DOWN: handle_touch(ev.x, ev.y)
            elif ev.type == KEYEV_DOWN:
                if ev.key == KEY_EXIT: state.running = False
                if ev.key == KEY_MENU: handle_touch(10, 10)
            ev = pollevent()
        time.sleep(0.05)

main()
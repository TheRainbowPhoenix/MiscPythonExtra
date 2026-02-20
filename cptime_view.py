import time
import gc
import array
from gint import *

# --- Colors ---
BG = C_RGB(3, 3, 4)
TAB_BG = C_RGB(6, 6, 8)
TAB_HL = C_RGB(31, 20, 0) # Orange highlight
LCD_ON = C_WHITE
LCD_OFF = C_RGB(5, 5, 5)
LCD_ACCENT = C_RGB(10, 20, 31) # Light blue accent
BTN_GREEN = C_RGB(8, 16, 4)
BTN_RED = C_RGB(20, 5, 5)
BTN_GREY = C_RGB(8, 8, 9)

# 7-Segment configurations (0-9)
SEGMENTS = [0x3F, 0x06, 0x5B, 0x4F, 0x66, 0x6D, 0x7D, 0x07, 0x7F, 0x6F]
KEYPAD = [['1','2','3'], ['4','5','6'], ['7','8','9'], ['DEL','0','START']]

# --- Global State stored entirely in pre-allocated memoryviews ---

# State array indices
S_TAB = 0
S_PRESS_ID = 1
S_PRESS_TIME = 2
S_SW_RUNNING = 3
S_SW_START = 4
S_SW_ACC = 5
S_TM_MODE = 6
S_TM_END = 7
S_TM_REM = 8
S_TM_ALERT = 9
S_LAPS_CNT = 10

# Pre-allocate a 32-bit integer array for all state variables to avoid any allocations
_state_buf = array.array('i', [0] * 16)
state = memoryview(_state_buf)

# Stopwatch Laps (Avoids list of tuples allocation, max 30 laps)
MAX_LAPS = 30
_laps_diff_buf = array.array('i', [0] * MAX_LAPS)
_laps_tot_buf = array.array('i', [0] * MAX_LAPS)
laps_diff = memoryview(_laps_diff_buf)
laps_tot = memoryview(_laps_tot_buf)

# Buffers for timer inputs and drawing digits
tm_input = memoryview(bytearray(6))
shared_digs = memoryview(bytearray(6))

# Button IDs (Integer constants instead of allocating strings)
BTN_SW_LEFT = 1
BTN_SW_RIGHT = 2
BTN_TM_LEFT = 3
BTN_TM_RIGHT = 4

# --- Graphics Helpers ---

def set_visual_press(v_id, now):
    state[S_PRESS_ID] = v_id
    state[S_PRESS_TIME] = now

def check_visual_press(v_id, now):
    return (state[S_PRESS_ID] == v_id and time.ticks_diff(now, state[S_PRESS_TIME]) < 150)

def draw_seg(x, y, w, h, is_horiz, c):
    """Draws a single hexagonal LCD segment using polygons to ensure seamless joints."""
    if is_horiz:
        t_2 = h // 2
        dpoly([x, y+t_2, x+t_2, y, x+w-t_2, y, x+w, y+t_2, x+w-t_2, y+h, x+t_2, y+h], c, C_NONE)
    else:
        t_2 = w // 2
        dpoly([x+t_2, y, x+w, y+t_2, x+w, y+h-t_2, x+t_2, y+h, x, y+h-t_2, x, y+t_2], c, C_NONE)

def draw_digit(x, y, w, h, t, val, on_col, off_col=C_NONE):
    segs = SEGMENTS[val] if val >= 0 else 0
    
    # 0: Top
    c = on_col if (segs & 1) else off_col
    if c != C_NONE: draw_seg(x+t//2, y, w-t, t, True, c)
    
    # 1: Top Right
    c = on_col if (segs & 2) else off_col
    if c != C_NONE: draw_seg(x+w-t, y+t//2, t, h//2-t//2, False, c)
    
    # 2: Bot Right
    c = on_col if (segs & 4) else off_col
    if c != C_NONE: draw_seg(x+w-t, y+h//2, t, h//2-t//2, False, c)
    
    # 3: Bot
    c = on_col if (segs & 8) else off_col
    if c != C_NONE: draw_seg(x+t//2, y+h-t, w-t, t, True, c)
    
    # 4: Bot Left
    c = on_col if (segs & 16) else off_col
    if c != C_NONE: draw_seg(x, y+h//2, t, h//2-t//2, False, c)
    
    # 5: Top Left
    c = on_col if (segs & 32) else off_col
    if c != C_NONE: draw_seg(x, y+t//2, t, h//2-t//2, False, c)
    
    # 6: Middle
    c = on_col if (segs & 64) else off_col
    if c != C_NONE: draw_seg(x+t//2, y+h//2-t//2, w-t, t, True, c)

def draw_colon(x, y, w, h, c):
    drect(x, y+h//3-w//2, x+w, y+h//3+w//2, c)
    drect(x, y+2*h//3-w//2, x+w, y+2*h//3+w//2, c)

def draw_btn(x, y, w, h, text, color, pressed):
    c = C_WHITE if pressed else color
    tc = C_BLACK if pressed else C_WHITE
    drect(x, y, x+w, y+h, c)
    drect_border(x, y, x+w, y+h, C_NONE, 2, C_RGB(10,10,10))
    dtext_opt(x+w//2, y+h//2, tc, C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, text, -1)

def draw_tabs(active_tab):
    drect(0, 0, DWIDTH, 50, TAB_BG)
    c0 = C_WHITE if active_tab == 0 else C_RGB(15,15,15)
    c1 = C_WHITE if active_tab == 1 else C_RGB(15,15,15)
    dtext_opt(80, 25, c0, C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "Stopwatch", -1)
    dtext_opt(240, 25, c1, C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "Timer", -1)
    
    # Underline active
    if active_tab == 0: drect(0, 46, 160, 50, TAB_HL)
    else: drect(160, 46, 320, 50, TAB_HL)
    dhline(50, C_RGB(10,10,10))

# --- Application Logic ---

def update_stopwatch(tx, ty, now):
    current_ms = state[S_SW_ACC]
    if state[S_SW_RUNNING]:
        current_ms += time.ticks_diff(now, state[S_SW_START])

    # Handle Buttons
    if 180 <= ty <= 230:
        if 20 <= tx <= 150:
            set_visual_press(BTN_SW_LEFT, now)
            if state[S_SW_RUNNING]:
                state[S_SW_ACC] += time.ticks_diff(now, state[S_SW_START])
                state[S_SW_RUNNING] = 0
            else:
                state[S_SW_START] = now
                state[S_SW_RUNNING] = 1
        elif 170 <= tx <= 300:
            set_visual_press(BTN_SW_RIGHT, now)
            if state[S_SW_RUNNING]:
                cnt = state[S_LAPS_CNT]
                if cnt < MAX_LAPS:
                    last_total = laps_tot[cnt - 1] if cnt > 0 else 0
                    laps_diff[cnt] = current_ms - last_total
                    laps_tot[cnt] = current_ms
                    state[S_LAPS_CNT] += 1
            elif current_ms > 0:
                state[S_SW_ACC] = 0
                current_ms = 0
                state[S_LAPS_CNT] = 0

    # UI Backing
    drect(10, 60, 310, 160, C_BLACK)
    drect_border(10, 60, 310, 160, C_NONE, 2, C_RGB(10,10,10))

    # Calculate format in-place
    csec = (current_ms // 10) % 100
    sec = (current_ms // 1000) % 60
    min_ = (current_ms // 60000) % 60
    
    shared_digs[0] = min_ // 10
    shared_digs[1] = min_ % 10
    shared_digs[2] = sec // 10
    shared_digs[3] = sec % 10
    shared_digs[4] = csec // 10
    shared_digs[5] = csec % 10

    # Draw Main Time
    draw_digit(20,  80, 35, 70, 8, shared_digs[0], LCD_ON, LCD_OFF)
    draw_digit(65,  80, 35, 70, 8, shared_digs[1], LCD_ON, LCD_OFF)
    draw_colon(105, 80, 6, 70, LCD_ON)
    draw_digit(115, 80, 35, 70, 8, shared_digs[2], LCD_ON, LCD_OFF)
    draw_digit(160, 80, 35, 70, 8, shared_digs[3], LCD_ON, LCD_OFF)
    draw_colon(200, 80, 6, 70, LCD_ON)
    
    # Draw Centiseconds (Smaller)
    draw_digit(215, 100, 25, 50, 6, shared_digs[4], LCD_ON, LCD_OFF)
    draw_digit(245, 100, 25, 50, 6, shared_digs[5], LCD_ON, LCD_OFF)

    # Draw Action Buttons
    l_pressed = check_visual_press(BTN_SW_LEFT, now)
    r_pressed = check_visual_press(BTN_SW_RIGHT, now)

    lbl_left = "Stop" if state[S_SW_RUNNING] else "Start"
    col_left = BTN_RED if state[S_SW_RUNNING] else BTN_GREEN
    lbl_right = "Lap" if state[S_SW_RUNNING] else "Reset"

    draw_btn(20, 180, 130, 50, lbl_left, col_left, l_pressed)
    draw_btn(170, 180, 130, 50, lbl_right, BTN_GREY, r_pressed)

    # Draw Laps List (Most recent on top)
    y = 250
    for i in range(state[S_LAPS_CNT]-1, -1, -1):
        if y > 480: break
        lap_d = laps_diff[i]
        lap_t = laps_tot[i]
        dtext(20, y+10, LCD_ACCENT, "%02d" % (i + 1))
        dtext(80, y+10, C_WHITE, "%02d:%02d.%02d" % ((lap_d//60000)%60, (lap_d//1000)%60, (lap_d//10)%100))
        dtext(200, y+10, C_WHITE, "%02d:%02d.%02d" % ((lap_t//60000)%60, (lap_t//1000)%60, (lap_t//10)%100))
        dhline(y + 35, C_RGB(8,8,8))
        y += 40

def update_timer(tx, ty, now):
    drect(5, 60, 315, 160, C_BLACK)
    drect_border(5, 60, 315, 160, C_NONE, 2, C_RGB(10,10,10))

    dtext_opt(50, 70, C_RGB(15,15,15), C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "Hours", -1)
    dtext_opt(150, 70, C_RGB(15,15,15), C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "Minutes", -1)
    dtext_opt(250, 70, C_RGB(15,15,15), C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "Seconds", -1)

    # Determine Display Digits in-place
    if state[S_TM_MODE] == 0:
        digs_ref = tm_input
    else:
        rem = state[S_TM_REM]
        secs = (rem // 1000) % 60
        mins = (rem // 60000) % 60
        hrs  = (rem // 3600000)
        
        shared_digs[0] = hrs // 10
        shared_digs[1] = hrs % 10
        shared_digs[2] = mins // 10
        shared_digs[3] = mins % 10
        shared_digs[4] = secs // 10
        shared_digs[5] = secs % 10
        digs_ref = shared_digs

    draw_digit(10,  80, 35, 70, 8, digs_ref[0], LCD_ON, LCD_OFF)
    draw_digit(55,  80, 35, 70, 8, digs_ref[1], LCD_ON, LCD_OFF)
    draw_colon(95, 80, 6, 70, LCD_ON)
    draw_digit(110, 80, 35, 70, 8, digs_ref[2], LCD_ON, LCD_OFF)
    draw_digit(155, 80, 35, 70, 8, digs_ref[3], LCD_ON, LCD_OFF)
    draw_colon(195, 80, 6, 70, LCD_ON)
    draw_digit(210, 80, 35, 70, 8, digs_ref[4], LCD_ON, LCD_OFF)
    draw_digit(255, 80, 35, 70, 8, digs_ref[5], LCD_ON, LCD_OFF)

    # Input vs Running Layout
    if state[S_TM_MODE] == 0:
        if ty >= 250:
            pk_x = (tx - 5) // 105
            pk_y = (ty - 250) // 68
            if 0 <= pk_x <= 2 and 0 <= pk_y <= 3:
                pk_id = 100 + pk_y * 10 + pk_x # Make integer ID for the button
                set_visual_press(pk_id, now)
                
                key = KEYPAD[pk_y][pk_x]
                if key == 'START':
                    h = tm_input[0]*10 + tm_input[1]
                    m = tm_input[2]*10 + tm_input[3]
                    s = tm_input[4]*10 + tm_input[5]
                    show_ms = (h*3600 + m*60 + s) * 1000
                    if show_ms > 0:
                        state[S_TM_REM] = show_ms
                        state[S_TM_END] = time.ticks_add(now, show_ms)
                        state[S_TM_MODE] = 1
                elif key == 'DEL':
                    for i in range(5, 0, -1): tm_input[i] = tm_input[i-1]
                    tm_input[0] = 0
                else:
                    for i in range(5): tm_input[i] = tm_input[i+1]
                    tm_input[5] = int(key)
        
        # Draw Keypad
        for r in range(4):
            for c in range(3):
                x, y = 5 + c * 105, 250 + r * 68
                txt = KEYPAD[r][c]
                is_pressed = check_visual_press(100 + r * 10 + c, now)
                
                bg = C_RGB(8,8,8)
                if txt == 'START': bg = BTN_GREEN
                elif txt == 'DEL': bg = BTN_RED
                draw_btn(x, y, 100, 60, txt, bg, is_pressed)
    else:
        # Draw Running Controls
        if 180 <= ty <= 230:
            if 20 <= tx <= 150:
                set_visual_press(BTN_TM_LEFT, now)
                state[S_TM_MODE] = 0
                for i in range(6): tm_input[i] = 0
            elif 170 <= tx <= 300:
                set_visual_press(BTN_TM_RIGHT, now)
                if state[S_TM_MODE] == 1:
                    state[S_TM_MODE] = 2
                else:
                    state[S_TM_MODE] = 1
                    state[S_TM_END] = time.ticks_add(now, state[S_TM_REM])

        draw_btn(20, 180, 130, 50, "Cancel", BTN_GREY, check_visual_press(BTN_TM_LEFT, now))
        
        lbl = "Resume" if state[S_TM_MODE] == 2 else "Pause"
        col = BTN_GREEN if state[S_TM_MODE] == 2 else C_RGB(31, 20, 0)
        draw_btn(170, 180, 130, 50, lbl, col, check_visual_press(BTN_TM_RIGHT, now))


def main():
    touch_latched = False
    last_gc_time = time.ticks_ms()
    
    while True:
        ev = pollevent()
        touch_x, touch_y = -1, -1
        
        # Read events (Latched touch to prevent hold-spam)
        while ev.type != KEYEV_NONE:
            if ev.type == KEYEV_TOUCH_DOWN:
                if not touch_latched:
                    touch_latched = True
                    touch_x, touch_y = ev.x, ev.y
            elif ev.type == KEYEV_TOUCH_UP:
                touch_latched = False
            elif ev.type == KEYEV_DOWN and ev.key == KEY_EXIT:
                return
            ev = pollevent()
            
        now = time.ticks_ms()
        
        # Run Garbage Collector every 2 minutes (120000 ms)
        if time.ticks_diff(now, last_gc_time) > 120000:
            gc.collect()
            last_gc_time = now
        
        # Global background check for timer expiry
        if state[S_TM_MODE] == 1:
            diff = time.ticks_diff(state[S_TM_END], now)
            if diff <= 0:
                state[S_TM_MODE] = 3
                state[S_TM_ALERT] = now
                state[S_TM_REM] = 0
            else:
                state[S_TM_REM] = diff
        
        # App Rendering
        if state[S_TM_MODE] == 3:
            # Full Screen Flashing Timeout Alert
            if ((time.ticks_diff(now, state[S_TM_ALERT])) // 500) % 2 == 0:
                dclear(C_WHITE)
                dtext_opt(160, 264, C_BLACK, C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "TIME'S UP!", -1)
            else:
                dclear(BG)
                dtext_opt(160, 264, C_WHITE, C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "TIME'S UP!", -1)
            
            # Dismiss alert on any tap
            if touch_x >= 0 or touch_y >= 0:
                state[S_TM_MODE] = 0
                for i in range(6): tm_input[i] = 0
        else:
            # Standard Interface Processing
            if 0 < touch_y < 50:
                if touch_x < 160: state[S_TAB] = 0
                elif touch_x > 160: state[S_TAB] = 1
            
            dclear(BG)
            draw_tabs(state[S_TAB])
            
            if state[S_TAB] == 0: update_stopwatch(touch_x, touch_y, now)
            else: update_timer(touch_x, touch_y, now)
                
        dupdate()
        time.sleep(0.02) # Keeps loops light

# Start App
main()
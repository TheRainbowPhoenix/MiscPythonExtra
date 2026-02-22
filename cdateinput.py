import time
import math
from gint import *
import cinput

# =============================================================================
# CONSTANTS & CONFIGURATION
# =============================================================================

SCREEN_W = 320
SCREEN_H = 528

DAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
DOW_SINGLE = ["S", "M", "T", "W", "T", "F", "S"]
MONTH_NAMES = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONTH_NAMES_LONG = ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]

DIGIT_KEYS = {
    KEY_0: 0, KEY_1: 1, KEY_2: 2, KEY_3: 3, KEY_4: 4,
    KEY_5: 5, KEY_6: 6, KEY_7: 7, KEY_8: 8, KEY_9: 9
}

# =============================================================================
# DATE MATH UTILITIES
# =============================================================================

def is_leap(year):
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)

def days_in_month(year, month):
    if month == 2:
        return 29 if is_leap(year) else 28
    return [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]

def day_of_week(year, month, day):
    """Returns 0 for Sunday, 1 for Monday, etc."""
    t = [0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4]
    if month < 3:
        year -= 1
    return (year + year//4 - year//100 + year//400 + t[month-1] + day) % 7

def add_days(y, m, d, delta):
    """Calculates a new date given an offset in days."""
    while delta > 0:
        days_left = days_in_month(y, m) - d
        if delta <= days_left:
            d += delta
            delta = 0
        else:
            delta -= (days_left + 1)
            d = 1
            m += 1
            if m > 12:
                m = 1
                y += 1
    while delta < 0:
        if d > -delta:
            d += delta
            delta = 0
        else:
            delta += d
            m -= 1
            if m < 1:
                m = 12
                y -= 1
            d = days_in_month(y, m)
    return y, m, d

# =============================================================================
# DATE PICKER WIDGET
# =============================================================================

class DatePicker:
    def __init__(self, prompt="Select Date", default_y=2026, default_m=1, default_d=1, theme="light", min_date=None, max_date=None):
        self.prompt = prompt
        self.min_date = min_date
        self.max_date = max_date
        
        self.year, self.month, self.day = self.clamp_date(default_y, default_m, default_d)
        
        self.theme_name = theme
        self.theme = cinput.get_theme(theme)
        
        # Touch States
        self.btn_ok_pressed = False
        self.btn_cn_pressed = False
        self.left_arrow_pressed = False
        self.right_arrow_pressed = False
        
        self.num_buffer = ""
        
        # UI Metrics
        self.header_h = 90
        self.footer_h = 45
        self.btn_w = SCREEN_W // 2

    def clamp_date(self, y, m, d):
        if self.min_date and (y, m, d) < self.min_date:
            return self.min_date
        if self.max_date and (y, m, d) > self.max_date:
            return self.max_date
        return y, m, d
        
    def draw_bold_text(self, x, y, fg, text):
        """Creates a pseudo-bold effect by drawing text twice slightly offset."""
        dtext(x, y, fg, text)
        dtext(x + 1, y, fg, text)

    def draw_btn(self, x, y, w, h, text, pressed):
        t = self.theme
        bg = t['hl'] if pressed else t['key_spec']
        drect(x, y, x + w, y + h, bg)
        drect_border(x, y, x + w, y + h, C_NONE, 1, t['key_spec'])
        dtext_opt(x + w//2, y + h//2, t['txt'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, text, -1)

    def draw(self):
        t = self.theme
        dclear(t['modal_bg'])
        
        # 1. Header (Blue/Accent background)
        drect(0, 0, SCREEN_W, self.header_h, t['accent'])
        dtext(20, 15, t['txt_acc'], self.prompt)
        
        dow = day_of_week(self.year, self.month, self.day)
        date_str = f"{DAY_NAMES[dow]}, {MONTH_NAMES[self.month]} {self.day}"
        self.draw_bold_text(20, 45, t['txt_acc'], date_str)
        self.draw_bold_text(20, 65, t['txt_acc'], str(self.year))
        
        # 2. Month Selector
        my_y = self.header_h + 15
        
        # Active touch backgrounds for arrows
        if self.left_arrow_pressed:
            drect(240, my_y - 5, 275, my_y + 25, t['hl'])
        if self.right_arrow_pressed:
            drect(275, my_y - 5, 315, my_y + 25, t['hl'])
            
        dtext_opt(20, my_y + 10, t['txt'], C_NONE, DTEXT_LEFT, DTEXT_MIDDLE, f"{MONTH_NAMES_LONG[self.month]} {self.year}", -1)
        
        # Left/Right Arrows
        dpoly([260, my_y+10, 265, my_y+4, 265, my_y+16], t['txt'], C_NONE) # <
        dpoly([295, my_y+10, 290, my_y+4, 290, my_y+16], t['txt'], C_NONE) # >
        
        # 3. Days of the week header
        dow_y = my_y + 40
        spacing = 42
        offset_x = (SCREEN_W - 7 * spacing) // 2
        for i in range(7):
            cx = offset_x + i * spacing + 21
            dtext_opt(cx, dow_y, t['txt_dim'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, DOW_SINGLE[i], -1)
            
        # 4. Grid of days
        grid_y = dow_y + 35
        start_dow = day_of_week(self.year, self.month, 1)
        num_days = days_in_month(self.year, self.month)
        
        for d in range(1, num_days + 1):
            pos = start_dow + d - 1
            row = pos // 7
            col = pos % 7
            
            cx = offset_x + col * spacing + 21
            cy = grid_y + row * 40
            
            # Check limits
            is_valid = True
            if self.min_date and (self.year, self.month, d) < self.min_date: is_valid = False
            if self.max_date and (self.year, self.month, d) > self.max_date: is_valid = False
            
            if not is_valid:
                dtext_opt(cx, cy, t['txt_dim'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, str(d), -1)
                continue
            
            if d == self.day:
                drect(cx - 16, cy - 16, cx + 16, cy + 16, t['accent'])
                dtext_opt(cx, cy, t['txt_acc'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, str(d), -1)
            else:
                dtext_opt(cx, cy, t['txt'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, str(d), -1)
                
        # 5. Footer Buttons
        fy = SCREEN_H - self.footer_h
        self.draw_btn(0, fy, self.btn_w, self.footer_h, "CANCEL", self.btn_cn_pressed)
        self.draw_btn(self.btn_w, fy, self.btn_w, self.footer_h, "OK", self.btn_ok_pressed)

    def run(self):
        clearevents()
        cleareventflips()
        
        while True:
            self.draw()
            dupdate()
            cleareventflips()
            
            ev = pollevent()
            events = []
            while ev.type != KEYEV_NONE:
                events.append(ev)
                ev = pollevent()
                
            # --- Physical Keypad Processing ---
            for e in events:
                if e.type == KEYEV_DOWN and e.key in DIGIT_KEYS:
                    digit = DIGIT_KEYS[e.key]
                    new_str = self.num_buffer + str(digit)
                    if int(new_str) > days_in_month(self.year, self.month):
                        new_str = str(digit)
                    
                    if new_str == "0":
                        self.num_buffer = "0" # Wait for next key
                    else:
                        new_d = int(new_str)
                        if new_d == 0:
                            self.num_buffer = "" # Discard double 00 allowing day 0
                        else:
                            y, m, d = self.clamp_date(self.year, self.month, new_d)
                            self.year, self.month, self.day = y, m, d
                            self.num_buffer = new_str
                            if len(self.num_buffer) >= 2:
                                self.num_buffer = ""
                elif e.type in (KEYEV_DOWN, KEYEV_TOUCH_DOWN) and getattr(e, 'key', -1) not in DIGIT_KEYS:
                    self.num_buffer = "" # Reset on arrows, touches, ok/cancel
            
            # --- Physical Keys Navigation ---
            if keypressed(KEY_EXIT) or keypressed(KEY_DEL):
                return None
            if keypressed(KEY_EXE):
                return (self.year, self.month, self.day)
                
            if keypressed(KEY_LEFT):
                self.year, self.month, self.day = self.clamp_date(*add_days(self.year, self.month, self.day, -1))
            elif keypressed(KEY_RIGHT):
                self.year, self.month, self.day = self.clamp_date(*add_days(self.year, self.month, self.day, 1))
            elif keypressed(KEY_UP):
                self.year, self.month, self.day = self.clamp_date(*add_days(self.year, self.month, self.day, -7))
            elif keypressed(KEY_DOWN):
                self.year, self.month, self.day = self.clamp_date(*add_days(self.year, self.month, self.day, 7))
                
            # --- Touch Navigation ---
            for e in events:
                x, y = e.x, e.y
                fy = SCREEN_H - self.footer_h
                
                if e.type == KEYEV_TOUCH_DOWN:
                    if y >= fy:
                        if x < self.btn_w:
                            self.btn_cn_pressed = True
                        else:
                            self.btn_ok_pressed = True
                    elif self.header_h < y < self.header_h + 50:
                        if 240 <= x < 275:
                            self.left_arrow_pressed = True
                        elif x >= 275:
                            self.right_arrow_pressed = True
                            
                elif e.type == KEYEV_TOUCH_UP:
                    # Footer actions
                    if y >= fy:
                        if self.btn_ok_pressed and x >= self.btn_w:
                            return (self.year, self.month, self.day)
                        elif self.btn_cn_pressed and x < self.btn_w:
                            return None
                            
                    # Month navigation and edits
                    elif self.header_h < y < self.header_h + 50:
                        if self.left_arrow_pressed and 240 <= x < 275:
                            new_m = self.month - 1
                            new_y = self.year
                            if new_m < 1:
                                new_m = 12
                                new_y -= 1
                            new_d = min(self.day, days_in_month(new_y, new_m))
                            self.year, self.month, self.day = self.clamp_date(new_y, new_m, new_d)
                        elif self.right_arrow_pressed and x >= 275:
                            new_m = self.month + 1
                            new_y = self.year
                            if new_m > 12:
                                new_m = 1
                                new_y += 1
                            new_d = min(self.day, days_in_month(new_y, new_m))
                            self.year, self.month, self.day = self.clamp_date(new_y, new_m, new_d)
                        elif x < 200:
                            # Open Month/Year picker
                            edit_target = cinput.pick(["Month", "Year"], "Edit", theme=self.theme_name)
                            if edit_target == "Month":
                                new_m_str = cinput.pick(MONTH_NAMES_LONG[1:], "Month", theme=self.theme_name)
                                if new_m_str:
                                    self.month = MONTH_NAMES_LONG.index(new_m_str)
                            elif edit_target == "Year":
                                y_min = self.min_date[0] if self.min_date else 2011
                                y_max = self.max_date[0] if self.max_date else 2048
                                new_y_str = cinput.pick([str(y) for y in range(y_min, y_max + 1)], "Year", theme=self.theme_name)
                                if new_y_str:
                                    self.year = int(new_y_str)
                            
                            new_d = min(self.day, days_in_month(self.year, self.month))
                            self.year, self.month, self.day = self.clamp_date(self.year, self.month, new_d)
                            clearevents() 
                            
                    # Grid clicks
                    elif y > self.header_h + 80 and y < fy:
                        spacing = 42
                        offset_x = (SCREEN_W - 7 * spacing) // 2
                        grid_y = self.header_h + 55 + 35
                        
                        col = (x - offset_x) // spacing
                        row = (y - grid_y + 20) // 40
                        
                        if 0 <= col < 7 and 0 <= row < 6:
                            start_dow = day_of_week(self.year, self.month, 1)
                            clicked_day = row * 7 + col - start_dow + 1
                            
                            if 1 <= clicked_day <= days_in_month(self.year, self.month):
                                y, m, d = self.clamp_date(self.year, self.month, clicked_day)
                                self.year, self.month, self.day = y, m, d
                                
                    # Always clear touch states on release
                    self.btn_ok_pressed = False
                    self.btn_cn_pressed = False
                    self.left_arrow_pressed = False
                    self.right_arrow_pressed = False

            time.sleep(0.01)


# =============================================================================
# TIME PICKER WIDGET (Spinner/Wheel Style)
# =============================================================================

class TimePicker:
    def __init__(self, prompt="Select Time", default_h=12, default_m=0, theme="light", min_time=None, max_time=None):
        self.prompt = prompt
        self.min_time = min_time
        self.max_time = max_time
        
        self.offset_h = float(default_h)
        self.offset_m = float(default_m)
        self.enforce_boundaries()
        
        self.theme = cinput.get_theme(theme)
        self.num_buffer = ""
        
        # Touch States
        self.btn_ok_pressed = False
        self.btn_cn_pressed = False
        
        self.header_h = 90
        self.footer_h = 45
        self.item_h = 45
        self.btn_w = SCREEN_W // 2
        self.center_y = (SCREEN_H - self.header_h - self.footer_h) // 2 + self.header_h
        
        self.focus_col = 0 # 0 for hours, 1 for minutes (used for physical keys)

    def enforce_boundaries(self):
        if self.min_time or self.max_time:
            # Absolute limits applied to drag physics
            if self.min_time:
                min_h, min_m = self.min_time
                if self.offset_h < min_h:
                    self.offset_h = float(min_h)
                if self.offset_h <= min_h and self.offset_m < min_m:
                    self.offset_m = float(min_m)
            if self.max_time:
                max_h, max_m = self.max_time
                if self.offset_h > max_h:
                    self.offset_h = float(max_h)
                if self.offset_h >= max_h and self.offset_m > max_m:
                    self.offset_m = float(max_m)
        else:
            # Wrap around normally
            if self.offset_h < 0: self.offset_h += 24
            if self.offset_h >= 24: self.offset_h -= 24
            if self.offset_m < 0: self.offset_m += 60
            if self.offset_m >= 60: self.offset_m -= 60
        
    def draw_bold_text(self, x, y, fg, text):
        dtext(x, y, fg, text)
        dtext(x + 1, y, fg, text)

    def draw_btn(self, x, y, w, h, text, pressed):
        t = self.theme
        bg = t['hl'] if pressed else t['key_spec']
        drect(x, y, x + w, y + h, bg)
        drect_border(x, y, x + w, y + h, C_NONE, 1, t['key_spec'])
        dtext_opt(x + w//2, y + h//2, t['txt'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, text, -1)

    def draw(self):
        t = self.theme
        dclear(t['modal_bg'])
        
        # 1. Header
        drect(0, 0, SCREEN_W, self.header_h, t['accent'])
        dtext(20, 15, t['txt_acc'], self.prompt)
        
        time_str = f"{int(round(self.offset_h)) % 24:02d}:{int(round(self.offset_m)) % 60:02d}"
        self.draw_bold_text(20, 50, t['txt_acc'], time_str)
        
        # 2. Spinner Setup
        band_y1 = self.center_y - self.item_h // 2
        band_y2 = self.center_y + self.item_h // 2
        
        # Selection Band
        drect(0, band_y1, SCREEN_W, band_y2, t['hl'])
        dhline(band_y1, t['key_spec'])
        dhline(band_y2, t['key_spec'])
        
        # Focus Indicator (for physical keys)
        if self.focus_col == 0:
            drect_border(30, band_y1, 130, band_y2, C_NONE, 1, t['txt_dim'])
        else:
            drect_border(190, band_y1, 290, band_y2, C_NONE, 1, t['txt_dim'])

        # 3. Draw Columns
        cols = [
            (self.offset_h, 24, 80),   # Hours (offset, modulo, x_center)
            (self.offset_m, 60, 240)   # Minutes
        ]
        
        for col_idx, (offset, mod_val, cx) in enumerate(cols):
            base_idx = int(math.floor(offset))
            rem = offset - base_idx
            
            # Draw a few items above and below the center
            for i in range(-3, 4):
                val = base_idx + i
                
                # Check min/max boundary rendering limits
                if self.min_time or self.max_time:
                    if col_idx == 0 and not (0 <= val <= 23): continue
                    if col_idx == 1 and not (0 <= val <= 59): continue
                    
                    if col_idx == 0:
                        if self.min_time and val < self.min_time[0]: continue
                        if self.max_time and val > self.max_time[0]: continue
                    elif col_idx == 1:
                        curr_h = int(round(self.offset_h))
                        if self.min_time and curr_h == self.min_time[0] and val < self.min_time[1]: continue
                        if self.max_time and curr_h == self.max_time[0] and val > self.max_time[1]: continue
                else:
                    val %= mod_val

                cy = self.center_y + int((i - rem) * self.item_h)
                
                # Check if it's currently the centered/selected item
                dist = abs(i - rem)
                is_selected = dist < 0.5
                
                # Aesthetic dimming for non-selected
                col_fg = t['txt'] if is_selected else t['txt_dim']
                
                if self.header_h < cy < SCREEN_H - self.footer_h:
                    dtext_opt(cx, cy, col_fg, C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, f"{val:02d}", -1)
                    
        # Middle colon separator
        dtext_opt(SCREEN_W//2, self.center_y - 2, t['txt'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, ":", -1)

        # 4. Footer Buttons
        fy = SCREEN_H - self.footer_h
        self.draw_btn(0, fy, self.btn_w, self.footer_h, "CANCEL", self.btn_cn_pressed)
        self.draw_btn(self.btn_w, fy, self.btn_w, self.footer_h, "OK", self.btn_ok_pressed)

    def run(self):
        clearevents()
        cleareventflips()
        
        is_dragging = False
        drag_col = None
        last_y = 0
        
        while True:
            self.draw()
            dupdate()
            cleareventflips()
            
            ev = pollevent()
            events = []
            while ev.type != KEYEV_NONE:
                events.append(ev)
                ev = pollevent()

            # --- Physical Keypad Processing ---
            for e in events:
                if e.type == KEYEV_DOWN and e.key in DIGIT_KEYS:
                    digit = DIGIT_KEYS[e.key]
                    new_str = self.num_buffer + str(digit)
                    limit = 23 if self.focus_col == 0 else 59
                    
                    if int(new_str) > limit:
                        new_str = str(digit)
                    
                    val = int(new_str)
                    if self.focus_col == 0:
                        self.offset_h = float(val)
                    else:
                        self.offset_m = float(val)
                        
                    self.enforce_boundaries()
                    self.num_buffer = new_str
                    if len(self.num_buffer) >= 2:
                        self.num_buffer = ""
                elif e.type in (KEYEV_DOWN, KEYEV_TOUCH_DOWN) and getattr(e, 'key', -1) not in DIGIT_KEYS:
                    self.num_buffer = ""

            # --- Physical Keys Navigation ---
            if keypressed(KEY_EXIT) or keypressed(KEY_DEL):
                return None
            if keypressed(KEY_EXE):
                return (int(round(self.offset_h)) % 24, int(round(self.offset_m)) % 60)
                
            if keypressed(KEY_LEFT):
                self.focus_col = 0
            elif keypressed(KEY_RIGHT):
                self.focus_col = 1
            elif keypressed(KEY_UP):
                if self.focus_col == 0: self.offset_h -= 1
                else: self.offset_m -= 1
                self.enforce_boundaries()
            elif keypressed(KEY_DOWN):
                if self.focus_col == 0: self.offset_h += 1
                else: self.offset_m += 1
                self.enforce_boundaries()
                
            # --- Touch Interaction ---
            for e in events:
                fy = SCREEN_H - self.footer_h
                
                if e.type == KEYEV_TOUCH_DOWN:
                    if e.y >= fy:
                        if e.x < self.btn_w:
                            self.btn_cn_pressed = True
                        else:
                            self.btn_ok_pressed = True
                    elif self.header_h < e.y < fy:
                        is_dragging = True
                        last_y = e.y
                        drag_col = 0 if e.x < SCREEN_W // 2 else 1
                        self.focus_col = drag_col
                        
                elif e.type == KEYEV_TOUCH_DRAG and is_dragging:
                    dy = e.y - last_y
                    if drag_col == 0:
                        self.offset_h -= dy / self.item_h
                    else:
                        self.offset_m -= dy / self.item_h
                    self.enforce_boundaries()
                    last_y = e.y
                    
                elif e.type == KEYEV_TOUCH_UP:
                    if is_dragging:
                        # Snap to nearest integer on release safely bound to limits
                        self.offset_h = float(round(self.offset_h))
                        self.offset_m = float(round(self.offset_m))
                        self.enforce_boundaries()
                        
                        is_dragging = False
                        drag_col = None
                    else:
                        # Handle button clicks
                        if e.y >= fy:
                            if self.btn_ok_pressed and e.x >= self.btn_w:
                                return (int(round(self.offset_h)) % 24, int(round(self.offset_m)) % 60)
                            elif self.btn_cn_pressed and e.x < self.btn_w:
                                return None

                    self.btn_ok_pressed = False
                    self.btn_cn_pressed = False

            time.sleep(0.01)

# =============================================================================
# PUBLIC EXPORTED FUNCTIONS
# =============================================================================

def datepick(prompt="Select Date", default_y=2026, default_m=1, default_d=1, theme="light", min_date=None, max_date=None):
    """
    Opens a graphical calendar interface to select a date.
    Returns: (year, month, day) as integers, or None if cancelled.
    """
    picker = DatePicker(prompt, default_y, default_m, default_d, theme, min_date, max_date)
    return picker.run()

def timepick(prompt="Select Time", default_h=12, default_m=0, theme="light", min_time=None, max_time=None):
    """
    Opens a rolling graphical spinner interface to select a 24-hour time.
    Returns: (hour, minute) as integers, or None if cancelled.
    """
    picker = TimePicker(prompt, default_h, default_m, theme, min_time, max_time)
    return picker.run()

# =============================================================================
# USAGE DEMOS
# =============================================================================
def run_demos():
    # Demo 1: Simple Time Picker
    t_res = timepick("Set Alarm", 7, 30, theme="light")
    
    # Demo 2: Constrained Date Picker
    d_res = datepick("Check-in Date", 2026, 5, 15, theme="light", 
                     min_date=(2026, 5, 10), max_date=(2026, 6, 20))
    
    # Demo 3: French Localized Date Picker
    global DAY_NAMES, DOW_SINGLE, MONTH_NAMES, MONTH_NAMES_LONG
    
    # Save original globals (Optional but good practice)
    original_days = DAY_NAMES.copy()
    original_dows = DOW_SINGLE.copy()
    original_months = MONTH_NAMES.copy()
    original_months_long = MONTH_NAMES_LONG.copy()
    
    # Override with French arrays
    DAY_NAMES = ["Dim", "Lun", "Mar", "Mer", "Jeu", "Ven", "Sam"]
    DOW_SINGLE = ["D", "L", "M", "M", "J", "V", "S"]
    MONTH_NAMES = ["", "Jan", "Fev", "Mar", "Avr", "Mai", "Jun", "Jul", "Aoû", "Sep", "Oct", "Nov", "Dec"]
    MONTH_NAMES_LONG = ["", "Janvier", "Fevrier", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Decembre"]
    
    fd_res = datepick("Date de naissance", 2000, 1, 1, theme="light")
    
    # Restore standard locale 
    DAY_NAMES = original_days
    DOW_SINGLE = original_dows
    MONTH_NAMES = original_months
    MONTH_NAMES_LONG = original_months_long

# Uncomment to execute demos
run_demos()
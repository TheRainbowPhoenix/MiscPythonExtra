from gint import *
import cinput
import math
import time

# =============================================================================
# CONFIGURATION
# =============================================================================

SCREEN_W = 320
SCREEN_H = 528
HEADER_H = 40       # Main App Header
LIST_ITEM_H = 45    # Standard list item height
SECTION_H = 25      # Section header height (Smaller as requested)

# --- Custom Theme Definition (Minty Light) ---
THEME_NAME = 'mint'
MINT_THEME = {
    'modal_bg': C_RGB(29, 31, 29),  # Mint Cream 
    'kbd_bg':   C_RGB(29, 31, 29),
    'key_bg':   C_RGB(31, 31, 31),
    'key_spec': C_RGB(22, 26, 22), 
    'key_out':  C_RGB(0, 0, 0),
    'txt':      C_RGB(2, 6, 3),    
    'txt_dim':  C_RGB(10, 14, 10), 
    'accent':   C_RGB(4, 18, 12),   # Sea Green
    'txt_acc':  C_RGB(31, 31, 31),
    'hl':       C_RGB(20, 26, 20),
    'check':    C_WHITE
}

# Inject theme
cinput.THEMES[THEME_NAME] = MINT_THEME

# Constants
CONSTANTS = {
    'g': 9.81, 'R': 8.314, 'c': 3.0e8, 'k': 9.0e9, 'G': 6.674e-11
}

# =============================================================================
# EQUATION DATA
# =============================================================================

class Equation:
    def __init__(self, name, variables, formulas, units=None):
        self.name = name
        self.variables = variables 
        self.formulas = formulas   
        self.units = units if units else {}

# --- Definitions ---
eq_kin_1 = Equation("Velocity", ["v", "u", "a", "t"], {
    "v": lambda x: x['u'] + x['a']*x['t'],
    "u": lambda x: x['v'] - x['a']*x['t'],
    "a": lambda x: (x['v'] - x['u']) / x['t'],
    "t": lambda x: (x['v'] - x['u']) / x['a']
}, {"v":"m/s", "u":"m/s", "a":"m/s^2", "t":"s"})

eq_kin_2 = Equation("Displacement", ["d", "u", "t", "a"], {
    "d": lambda x: x['u']*x['t'] + 0.5*x['a']*(x['t']**2),
    "u": lambda x: (x['d'] - 0.5*x['a']*(x['t']**2))/x['t'],
    "a": lambda x: 2*(x['d'] - x['u']*x['t'])/(x['t']**2)
}, {"d":"m", "u":"m/s", "t":"s", "a":"m/s^2"})

eq_kin_3 = Equation("Time-indep.", ["v", "u", "a", "d"], {
    "v": lambda x: math.sqrt(x['u']**2 + 2*x['a']*x['d']),
    "u": lambda x: math.sqrt(x['v']**2 - 2*x['a']*x['d']),
    "a": lambda x: (x['v']**2 - x['u']**2)/(2*x['d']),
    "d": lambda x: (x['v']**2 - x['u']**2)/(2*x['a'])
}, {"v":"m/s", "u":"m/s", "a":"m/s^2", "d":"m"})

eq_newton = Equation("Newton's 2nd Law", ["F", "m", "a"], {
    "F": lambda x: x['m'] * x['a'],
    "m": lambda x: x['F'] / x['a'],
    "a": lambda x: x['F'] / x['m']
}, {"F":"N", "m":"kg", "a":"m/s^2"})

eq_ke = Equation("Kinetic Energy", ["K", "m", "v"], {
    "K": lambda x: 0.5 * x['m'] * x['v']**2,
    "m": lambda x: 2 * x['K'] / x['v']**2,
    "v": lambda x: math.sqrt(2 * x['K'] / x['m'])
}, {"K":"J", "m":"kg", "v":"m/s"})

eq_pe = Equation("Potential Energy", ["U", "m", "g", "h"], {
    "U": lambda x: x['m'] * x['g'] * x['h'],
    "m": lambda x: x['U'] / (x['g'] * x['h']),
    "h": lambda x: x['U'] / (x['m'] * x['g'])
}, {"U":"J", "m":"kg", "g":"m/s^2", "h":"m"})

eq_circ = Equation("Centripetal Force", ["F", "m", "v", "r"], {
    "F": lambda x: (x['m'] * x['v']**2) / x['r'],
    "m": lambda x: (x['F'] * x['r']) / x['v']**2,
    "r": lambda x: (x['m'] * x['v']**2) / x['F'],
    "v": lambda x: math.sqrt((x['F'] * x['r']) / x['m'])
}, {"F":"N", "m":"kg", "v":"m/s", "r":"m"})

eq_ohm = Equation("Ohm's Law", ["V", "I", "R"], {
    "V": lambda x: x['I'] * x['R'],
    "I": lambda x: x['V'] / x['R'],
    "R": lambda x: x['V'] / x['I']
}, {"V":"V", "I":"A", "R":"\u03A9"})

eq_elec_p = Equation("Power (P=VI)", ["P", "V", "I"], {
    "P": lambda x: x['V'] * x['I'],
    "V": lambda x: x['P'] / x['I'],
    "I": lambda x: x['P'] / x['V']
}, {"P":"W", "V":"V", "I":"A"})

eq_coulomb = Equation("Coulomb's Law", ["F", "q1", "q2", "r", "k"], {
    "F": lambda x: x['k'] * abs(x['q1']*x['q2']) / x['r']**2,
    "r": lambda x: math.sqrt(x['k'] * abs(x['q1']*x['q2']) / x['F'])
}, {"F":"N", "q1":"C", "q2":"C", "r":"m", "k":"const"})

eq_wave = Equation("Wave Eq (v=fL)", ["v", "f", "L"], {
    "v": lambda x: x['f'] * x['L'],
    "f": lambda x: x['v'] / x['L'],
    "L": lambda x: x['v'] / x['f']
}, {"v":"m/s", "f":"Hz", "L":"m"})

eq_period = Equation("Period (T=1/f)", ["T", "f"], {
    "T": lambda x: 1 / x['f'],
    "f": lambda x: 1 / x['T']
}, {"T":"s", "f":"Hz"})

eq_moles = Equation("Molar Mass", ["n", "mass", "M"], {
    "n": lambda x: x['mass'] / x['M'],
    "mass": lambda x: x['n'] * x['M'],
    "M": lambda x: x['mass'] / x['n']
}, {"n":"mol", "mass":"g", "M":"g/mol"})

eq_molarity = Equation("Molarity (C=n/V)", ["C", "n", "V"], {
    "C": lambda x: x['n'] / x['V'],
    "n": lambda x: x['C'] * x['V'],
    "V": lambda x: x['n'] / x['C']
}, {"C":"M", "n":"mol", "V":"L"})

eq_gas = Equation("Ideal Gas (PV=nRT)", ["P", "V", "n", "T", "R"], {
    "P": lambda x: (x['n'] * x['R'] * x['T']) / x['V'],
    "V": lambda x: (x['n'] * x['R'] * x['T']) / x['P'],
    "n": lambda x: (x['P'] * x['V']) / (x['R'] * x['T']),
    "T": lambda x: (x['P'] * x['V']) / (x['n'] * x['R'])
}, {"P":"Pa", "V":"m^3", "n":"mol", "T":"K", "R":"const"})

eq_density = Equation("Density (D=m/V)", ["D", "m", "V"], {
    "D": lambda x: x['m'] / x['V'],
    "m": lambda x: x['D'] * x['V'],
    "V": lambda x: x['m'] / x['D']
}, {"D":"g/mL", "m":"g", "V":"mL"})

MENU_TREE = {
    "Mechanics": {
        "1-D Kinematics": [eq_kin_1, eq_kin_2, eq_kin_3],
        "Newton's Laws": [eq_newton],
        "Work & Energy": [eq_ke, eq_pe],
        "Circular Motion": [eq_circ],
        "Momentum": [
            Equation("Momentum (p=mv)", ["p", "m", "v"], 
                    {"p": lambda x: x['m']*x['v'], "m": lambda x: x['p']/x['v'], "v": lambda x: x['p']/x['m']},
                    {"p":"kgm/s","m":"kg","v":"m/s"})
        ]
    },
    "Electricity": {
        "Circuits": [eq_ohm, eq_elec_p],
        "Electrostatics": [eq_coulomb],
        "Capacitance": [
            Equation("Capacitor (Q=CV)", ["Q", "C", "V"],
                    {"Q":lambda x:x['C']*x['V'], "C":lambda x:x['Q']/x['V'], "V":lambda x:x['Q']/x['C']},
                    {"Q":"C", "C":"F", "V":"V"})
        ]
    },
    "Waves & Light": {
        "Basics": [eq_wave, eq_period],
        "Optics": [
            Equation("Snell's Law", ["n1", "n2", "th1", "th2"],
            {
                "n2": lambda x: x['n1'] * math.sin(math.radians(x['th1'])) / math.sin(math.radians(x['th2'])),
                "n1": lambda x: x['n2'] * math.sin(math.radians(x['th2'])) / math.sin(math.radians(x['th1']))
            }, {"th1":"deg", "th2":"deg"})
        ]
    },
    "Chemistry": {
        "Stoichiometry": [eq_moles, eq_density],
        "Solutions": [eq_molarity],
        "Gas Laws": [eq_gas],
        "Thermodynamics": [
            Equation("Heat (q=mcDT)", ["q", "m", "c", "DT"],
                    {"q":lambda x:x['m']*x['c']*x['DT'], "m":lambda x:x['q']/(x['c']*x['DT'])},
                    {"q":"J", "m":"g", "c":"J/gC", "DT":"C"})
        ]
    }
}

# =============================================================================
# SOLVER ACTIVITY
# =============================================================================

class SolverActivity:
    def __init__(self, equation):
        self.eq = equation
        self.target_var = equation.variables[0] 
        self.values = {v: CONSTANTS.get(v, None) for v in self.eq.variables}
            
        self.scroll_y = 0
        self.max_scroll = 0
        self.result_str = "---"
        self.error_str = None
        
        # UI State
        self.focus_index = 0  # 0: Target Selector, 1..N: Inputs, N+1: Solve Btn
        self.input_vars = []  
        self.recalc_layout()

    def recalc_layout(self):
        self.input_vars = [v for v in self.eq.variables if v != self.target_var and v not in CONSTANTS]
        
        # Calculate max scroll
        content_h = 60 + (len(self.input_vars) * 60) + 60 + 80
        view_h = SCREEN_H - HEADER_H
        self.max_scroll = max(0, content_h - view_h)
        self.result_str = "---"
        self.error_str = None

    def is_solvable(self):
        for v in self.input_vars:
            if self.values[v] is None:
                return False
        return True

    def solve(self):
        if not self.is_solvable():
            self.error_str = "Fill all fields"
            return
        try:
            args = self.values.copy()
            for k, v in CONSTANTS.items():
                args[k] = v
            func = self.eq.formulas.get(self.target_var)
            if func:
                val = func(args)
                unit = self.eq.units.get(self.target_var, "")
                self.result_str = f"{val:.5g} {unit}"
                self.error_str = None
            else:
                self.error_str = "No formula"
        except Exception:
            self.error_str = "Math Error"
            self.result_str = "Error"

    def handle_input_click(self, var_name):
        unit = self.eq.units.get(var_name, "")
        prompt = f"Enter {var_name} ({unit}):"
        val = cinput.input(prompt, type="numeric_float", theme=THEME_NAME, touch_mode=KEYEV_TOUCH_UP)
        if val is not None:
            try:
                self.values[var_name] = float(val)
                if self.is_solvable(): self.solve()
            except: pass

    def cycle_target(self):
        opts = list(self.eq.formulas.keys())
        new_target = cinput.pick(opts, "Solve for...", theme=THEME_NAME, touch_mode=KEYEV_TOUCH_UP)
        if new_target:
            self.target_var = new_target
            self.recalc_layout()

    def draw_back_arrow(self, x, y, col):
        drect(x + 2, y + 9, x + 18, y + 10, col)
        dline(x + 2, y + 9, x + 9, y + 2, col)
        dline(x + 2, y + 10, x + 9, y + 3, col)
        dline(x + 2, y + 9, x + 9, y + 16, col)
        dline(x + 2, y + 10, x + 9, y + 17, col)

    def draw(self):
        t = cinput.get_theme(THEME_NAME)
        dclear(t['modal_bg'])
        
        # --- Content Area (Scrolled) ---
        top_pad = 12
        y = HEADER_H + top_pad - self.scroll_y
        
        margin = 10
        box_h = 50

        # 1. Target Selector
        if y + box_h > HEADER_H and y < SCREEN_H:
            dtext_opt(margin, y, t['txt_dim'], C_NONE, DTEXT_LEFT, DTEXT_TOP, "Solving for:", -1)
            btn_y = y + 15
            highlight = (self.focus_index == 0)
            bc = t['accent'] if highlight else t['key_spec']
            tc = t['txt_acc'] if highlight else t['txt']
            drect(margin, btn_y, SCREEN_W-margin, btn_y + 35, bc)
            dtext_opt(SCREEN_W//2, btn_y + 17, tc, C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, 
                      f"{self.target_var} ({self.eq.units.get(self.target_var, '')})", -1)
            dtext_opt(SCREEN_W-20, btn_y + 17, tc, C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "v", -1)
        y += 60

        # 2. Input Fields
        for i, var in enumerate(self.input_vars):
            if y + box_h > HEADER_H and y < SCREEN_H:
                focus_i = i + 1
                highlight = (self.focus_index == focus_i)
                unit = self.eq.units.get(var, "")
                dtext_opt(margin, y, t['txt_dim'], C_NONE, DTEXT_LEFT, DTEXT_TOP, f"{var} ({unit})", -1)
                
                inp_y = y + 15
                bc = t['accent'] if highlight else t['modal_bg']
                border = t['accent'] if highlight else t['key_spec']
                val_str = str(self.values[var]) if self.values[var] is not None else ""
                
                drect(margin, inp_y, SCREEN_W-margin, inp_y + 35, bc)
                if not highlight: drect_border(margin, inp_y, SCREEN_W-margin, inp_y + 35, C_NONE, 1, border)
                
                col = t['txt_acc'] if highlight else t['txt']
                dtext_opt(20, inp_y + 17, col, C_NONE, DTEXT_LEFT, DTEXT_MIDDLE, val_str, -1)
                
                if self.values[var] is None:
                    dtext_opt(SCREEN_W-20, inp_y + 17, t['txt_dim'], C_NONE, DTEXT_RIGHT, DTEXT_MIDDLE, "Tap to edit", -1)
            y += 60

        # 3. Solve Button
        if y + box_h > HEADER_H and y < SCREEN_H:
            btn_y = y
            focus_i = len(self.input_vars) + 1
            highlight = (self.focus_index == focus_i)
            ready = self.is_solvable()
            
            fill_c = t['accent'] if ready else t['key_spec']
            if highlight and ready: fill_c = C_RGB(0, 25, 31) 
            txt_c = t['txt_acc'] if ready else t['txt_dim']
            
            drect(margin, btn_y, SCREEN_W-margin, btn_y + 40, fill_c)
            dtext_opt(SCREEN_W//2, btn_y + 20, txt_c, C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "SOLVE", -1)
        y += 60

        # 4. Result Area
        if y + 80 > HEADER_H and y < SCREEN_H:
            dline(margin, y, SCREEN_W-margin, y, t['key_spec'])
            dtext_opt(SCREEN_W//2, y + 20, t['txt_dim'], C_NONE, DTEXT_CENTER, DTEXT_TOP, "Result", -1)
            res_col = t['txt']
            if self.error_str: res_col = C_RGB(31, 0, 0)
            disp = self.error_str if self.error_str else self.result_str
            dtext_opt(SCREEN_W//2, y + 50, res_col, C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, disp, -1)
        
        # --- Header ---
        drect(0, 0, SCREEN_W, HEADER_H, t['accent'])
        col = t['txt_acc']
        self.draw_back_arrow(10, 10, col)
        dtext_opt(SCREEN_W//2, HEADER_H//2, t['txt_acc'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, self.eq.name, -1)

    def run(self):
        touch_latched = False
        touch_start_y = 0
        is_dragging = False
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
            
            if keypressed(KEY_DEL): running = False
            
            # --- Keys ---
            if keypressed(KEY_UP):
                self.focus_index = max(0, self.focus_index - 1)
                # Auto Scroll logic omitted for brevity, but could replicate physchem4_2 logic if needed
            elif keypressed(KEY_DOWN):
                self.focus_index = min(len(self.input_vars) + 1, self.focus_index + 1)
            elif keypressed(KEY_EXE):
                if self.focus_index == 0: self.cycle_target()
                elif self.focus_index <= len(self.input_vars):
                    self.handle_input_click(self.input_vars[self.focus_index-1])
                else: self.solve()

            # --- Touch ---
            # Manual touch logic similar to physchem4_2
            touch_e = None
            for e in events:
                if e.type == KEYEV_TOUCH_DOWN:
                    if not touch_latched:
                         touch_latched = True
                         touch_start_y = e.y
                         is_dragging = False
                         touch_e = e # Down
                    else:
                         # Dragging?
                         if abs(e.y - touch_start_y) > 10: is_dragging = True
                         if is_dragging:
                             dy = e.y - touch_start_y
                             self.scroll_y = max(0, min(self.max_scroll, self.scroll_y - dy))
                             touch_start_y = e.y # Reset relative
                elif e.type == KEYEV_TOUCH_UP:
                    if touch_latched:
                        touch_latched = False
                        if not is_dragging:
                            touch_e = e # Click
            
            if touch_e and touch_e.type == KEYEV_TOUCH_UP:
                tx, ty = touch_e.x, touch_e.y
                if ty < HEADER_H and tx < 80:
                    running = False
                elif ty > HEADER_H:
                    abs_y = ty - HEADER_H + self.scroll_y
                    # Target
                    if 0 <= abs_y < 60:
                        self.focus_index = 0
                        self.cycle_target()
                    # Inputs
                    elif 60 <= abs_y < 60 + (len(self.input_vars)*60):
                        idx = (abs_y - 60) // 60
                        if 0 <= idx < len(self.input_vars):
                            self.focus_index = idx + 1
                            self.handle_input_click(self.input_vars[idx])
                    else:
                        solve_y = 60 + (len(self.input_vars)*60)
                        if solve_y <= abs_y < solve_y + 60:
                            self.focus_index = len(self.input_vars) + 1
                            self.solve()

            time.sleep(0.01)

# =============================================================================
# MAIN APP
# =============================================================================

class App:
    def __init__(self):
        self.categories = list(MENU_TREE.keys())
        self.current_category = self.categories[0]
        self.rebuild_list()

    def rebuild_list(self):
        items = []
        if self.current_category in MENU_TREE:
            data = MENU_TREE[self.current_category]
            for section, equations in data.items():
                items.append({'type': 'section', 'text': section, 'height': SECTION_H})
                for eq in equations:
                    items.append({'type': 'eq', 'text': eq.name, 'obj': eq, 'height': LIST_ITEM_H, 'arrow': True})
        
        rect = (0, HEADER_H, SCREEN_W, SCREEN_H - HEADER_H)
        self.list_view = cinput.ListView(rect, items, row_h=LIST_ITEM_H, headers_h=SECTION_H, theme=THEME_NAME)

    def switch_category(self):
        opts = self.categories + ["Quit"]
        new_cat = cinput.pick(opts, "Select Category", theme=THEME_NAME, touch_mode=KEYEV_TOUCH_UP)
        if new_cat == "Quit": return False
        if new_cat:
            self.current_category = new_cat
            self.rebuild_list()
        return True

    def run(self):
        running = True
        while running:
            self.list_view.draw()
            
            # Draw Header and Menu Icon
            t = cinput.get_theme(THEME_NAME)
            drect(0, 0, SCREEN_W, HEADER_H, t['accent'])
            # Menu Icon
            mx, my = 15, HEADER_H//2 - 8
            col = t['txt_acc']
            for i in range(3): drect(mx, my + i*5, mx+18, my + 1 + i*5, col)
            
            dtext_opt(SCREEN_W//2, HEADER_H//2, t['txt_acc'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, self.current_category, -1)
            
            dupdate()
            cleareventflips()
            
            ev = pollevent()
            events = []
            while ev.type != KEYEV_NONE:
                events.append(ev)
                ev = pollevent()
            
            if keypressed(KEY_DEL): running = False
            if keypressed(KEY_MENU): 
                if not self.switch_category(): running = False
                cleareventflips()

            action = self.list_view.update(events)
            
            if action:
                type, idx, item = action
                if type == 'click' and item['type'] == 'eq':
                    solver = SolverActivity(item['obj'])
                    solver.run()
                    # Refresh inputs? 
                    cleareventflips()

            # Touch Logic for Header (Menu)
            for e in events:
                if e.type == KEYEV_TOUCH_UP:
                    if e.y < HEADER_H and e.x < 60:
                        if not self.switch_category(): running = False
                        cleareventflips()

            time.sleep(0.01)

app = App()
app.run()

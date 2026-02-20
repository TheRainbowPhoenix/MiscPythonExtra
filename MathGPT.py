from gint import *
import time
import cinput

# --- Custom Theme Definition (ChatGPT-like Light Theme) ---
GPT_THEME = {
    'modal_bg': C_WHITE,               # White background
    'kbd_bg':   C_RGB(29, 29, 29),     # Light gray keyboard bg
    'key_bg':   C_WHITE,               # White keys
    'key_spec': C_RGB(27, 27, 27),     # Light gray special keys/borders
    'key_out':  C_BLACK,
    'txt':      C_BLACK,               # Black text
    'txt_dim':  C_RGB(14, 14, 14),     # Dark gray text
    'accent':   C_RGB(0, 20, 15),      # Teal/Green accent
    'txt_acc':  C_WHITE,               # White text on accent
    'hl':       C_RGB(24, 24, 24),     # Hover/Highlight gray
    'check':    C_WHITE
}
cinput.THEMES['gpt'] = GPT_THEME

# --- Configuration for MOE Graph ---
ROUTER_COLOR = C_RGB(6, 6, 6)     # Dark Gray
EXPERT_ON = C_RGB(0, 20, 15)      # Teal (Matches theme accent)
EXPERT_OFF = C_RGB(28, 28, 28)    # Light gray

# --- Experts Definitions ---
def expert_add(a, b): return a + b
def expert_sub(a, b): return a - b
def expert_mul(a, b): return a * b
def expert_div(a, b): return a / b if b != 0 else "Error: div by 0"
def expert_echo(a, b): return a

EXPERTS = [
    {"name": "Adder", "keywords": ["add", "plus", "+"], "func": expert_add},
    {"name": "Subtractor", "keywords": ["minus", "sub", "-"], "func": expert_sub},
    {"name": "Multiplier", "keywords": ["times", "mul", "*"], "func": expert_mul},
    {"name": "Divider", "keywords": ["divide", "div", "/"], "func": expert_div},
    {"name": "Echo", "keywords": ["echo", "say", "repeat"], "func": expert_echo}
]

# --- NLP Pre-trained N-Gram Tables ---
VOCAB_NUMS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "hundred": 100
}

VOCAB_OPS = {
    "plus": "add", "and": "add", "+": "add",
    "minus": "sub", "take away": "sub", "-": "sub",
    "times": "mul", "multiplied by": "mul", "*": "mul", "x": "mul",
    "divided by": "div", "over": "div", "/": "div"
}

def nlp_tokenize(text):
    """Simple N-Gram tokenization & text-to-number evaluator returning steps for viz"""
    steps = [("Input", text)]
    text = text.lower()
    
    # 1. Resolve multi-word n-grams first
    for ngram, op in VOCAB_OPS.items():
        if " " in ngram:
            text = text.replace(ngram, op)
            
    # 2. Math string parsing (inject spaces around math symbols like '2+2' -> '2 + 2')
    for char in "+-*/":
        text = text.replace(char, f" {char} ")
    steps.append(("Math Padded", text))
            
    # 3. Clean punctuation
    for char in "?!,;:":
        text = text.replace(char, "")
        
    words = text.split()
    steps.append(("Split", " | ".join(words)))
    
    nums = []
    ops = []
    parsed_view = []
    
    # 4. Tokenize to routing tensors
    for w in words:
        if w in VOCAB_NUMS:
            nums.append(float(VOCAB_NUMS[w]))
            parsed_view.append(f"[{VOCAB_NUMS[w]}]")
        else:
            try:
                nums.append(float(w))
                parsed_view.append(f"[{float(w)}]")
            except ValueError:
                if w in VOCAB_OPS:
                    ops.append(VOCAB_OPS[w])
                    parsed_view.append(f"<{VOCAB_OPS[w]}>")
                elif w in [op for ex in EXPERTS for op in ex["keywords"]]:
                    ops.append(w)
                    parsed_view.append(f"<{w}>")
                else:
                    parsed_view.append(f"~{w}~")
                    
    steps.append(("Tokens", " ".join(parsed_view)))
    return nums, ops, steps

# --- UI Helpers ---
def wrap_text(text, max_chars=35):
    """Wraps text into multiple lines for display"""
    words = text.split()
    lines = []
    curr_line = ""
    for w in words:
        if len(curr_line) + len(w) + 1 <= max_chars:
            curr_line += (w + " ")
        else:
            lines.append(curr_line.strip())
            curr_line = w + " "
    if curr_line: lines.append(curr_line.strip())
    return lines

def draw_header(theme_dict, title):
    """Draws consistent top bar with Close (X) button"""
    drect(0, 0, 320, 40, theme_dict['accent'])
    dtext_opt(160, 20, theme_dict['txt_acc'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, title, -1)
    # Close Button Background (Left)
    drect(5, 5, 35, 35, theme_dict['accent'])
    dtext_opt(20, 20, theme_dict['txt_acc'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "X", -1)

def check_close_btn(events):
    """Checks if X button was pressed"""
    for e in events:
        if e.type == KEYEV_TOUCH_UP and e.x <= 40 and e.y <= 40:
            return True
    return False

def draw_node(x, y, label, active=False):
    color = EXPERT_ON if active else EXPERT_OFF
    text_color = C_WHITE if active else C_BLACK
    dcircle(x, y, 35, color, C_RGB(22, 22, 22))
    dtext_opt(x, y, text_color, C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, label, -1)

def draw_router(x, y):
    dcircle(x, y, 45, ROUTER_COLOR, C_RGB(15, 15, 15))
    dtext_opt(x, y, C_WHITE, C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "ROUTER", -1)

def draw_connection(x1, y1, x2, y2, active=False):
    color = EXPERT_ON if active else C_RGB(24, 24, 24)
    dline(x1, y1, x2, y2, color)

def render_moe(active_idx=-1, result_text="Waiting for input...", show_back=False, is_err=False, title="MathGPT MoE Router", show_steps_btn=False):
    t = cinput.get_theme('gpt')
    dclear(t['modal_bg'])
    draw_header(t, title)
    
    # Result display box
    box_color = C_RGB(29, 29, 29)
    drect(10, 50, 310, 110, box_color)
    drect_border(10, 50, 310, 110, C_NONE, 1, C_RGB(24, 24, 24))
    
    # Render multi-line text
    text_color = C_RED if is_err else t['txt']
    lines = result_text.split('\n')
    line_height = 18
    start_y = 80 - ((len(lines) - 1) * line_height) // 2
    
    for i, line in enumerate(lines):
        # Truncate to prevent long arrays overflowing
        disp_line = line if len(line) < 36 else line[:33] + "..."
        dtext_opt(160, start_y + i * line_height, text_color, C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, disp_line, -1)
    
    # MoE Graph Layout
    rx, ry = 160, 275 # Router position
    expert_positions = [
        (70, 150),  # Top Left
        (250, 150), # Top Right
        (60, 400),  # Bottom Left
        (260, 400), # Bottom Right
        (160, 430)  # Bottom Center (Echo)
    ]
    
    for i, pos in enumerate(expert_positions):
        draw_connection(rx, ry, pos[0], pos[1], active=(i == active_idx))
    
    draw_router(rx, ry)
    for i, pos in enumerate(expert_positions):
        draw_node(pos[0], pos[1], EXPERTS[i]["name"], active=(i == active_idx))
        
    if show_back:
        bx, by, bw, bh = 320 - 110, 528 - 50, 100, 40
        drect(bx, by, bx+bw, by+bh, t['key_spec'])
        drect_border(bx, by, bx+bw, by+bh, C_NONE, 1, t['hl'])
        dtext_opt(bx+bw//2, by+bh//2, t['txt'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "Back", -1)
        
    if show_steps_btn:
        sx, sy, sw, sh = 10, 528 - 50, 130, 40
        drect(sx, sy, sx+sw, sy+sh, t['accent'])
        drect_border(sx, sy, sx+sw, sy+sh, C_NONE, 1, t['hl'])
        dtext_opt(sx+sw//2, sy+sh//2, t['txt_acc'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "View Steps", -1)
        
    dupdate()

# --- Screens ---
def show_step_detail(step):
    t = cinput.get_theme('gpt')
    running = True
    touch_latched = False
    
    bx, by, bw, bh = 320 - 110, 528 - 50, 100, 40
    
    wrapped_desc = wrap_text(step['desc'], max_chars=34)
    wrapped_val = wrap_text(step['value'], max_chars=34)

    while running:
        dclear(t['modal_bg'])
        draw_header(t, step['title'])
        
        # Value Box
        dtext_opt(10, 60, t['txt_dim'], C_NONE, DTEXT_LEFT, DTEXT_MIDDLE, "Output Data:", -1)
        vy = 80
        drect(10, vy, 310, vy + max(40, len(wrapped_val)*20 + 10), t['key_bg'])
        drect_border(10, vy, 310, vy + max(40, len(wrapped_val)*20 + 10), C_NONE, 1, t['hl'])
        for i, line in enumerate(wrapped_val):
            dtext_opt(20, vy + 20 + i*20, t['accent'], C_NONE, DTEXT_LEFT, DTEXT_MIDDLE, line, -1)
            
        # Description
        dtext_opt(10, vy + max(40, len(wrapped_val)*20 + 10) + 20, t['txt_dim'], C_NONE, DTEXT_LEFT, DTEXT_MIDDLE, "Explanation:", -1)
        dy = vy + max(40, len(wrapped_val)*20 + 10) + 40
        for i, line in enumerate(wrapped_desc):
            dtext_opt(10, dy + i*22, t['txt'], C_NONE, DTEXT_LEFT, DTEXT_MIDDLE, line, -1)

        drect(bx, by, bx+bw, by+bh, t['key_spec'])
        drect_border(bx, by, bx+bw, by+bh, C_NONE, 1, t['hl'])
        dtext_opt(bx+bw//2, by+bh//2, t['txt'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "Back", -1)

        dupdate()
        cleareventflips()

        ev = pollevent()
        events = []
        while ev.type != KEYEV_NONE:
            events.append(ev)
            ev = pollevent()

        if keypressed(KEY_EXIT) or keypressed(KEY_EXE): return
        if check_close_btn(events): return

        for e in events:
            if e.type == KEYEV_TOUCH_DOWN and not touch_latched:
                touch_latched = True
            elif e.type == KEYEV_TOUCH_UP:
                if touch_latched:
                    touch_latched = False
                    if bx <= e.x <= bx+bw and by <= e.y <= by+bh:
                        return
        time.sleep(0.01)

def show_steps_list(detailed_steps):
    t = cinput.get_theme('gpt')
    running = True
    touch_latched = False
    
    bx, by, bw, bh = 320 - 110, 528 - 50, 100, 40
    
    # Polygon Scroll buttons layout
    ux, uy, uw, uh = 10, 528 - 50, 45, 40
    dx, dy, dw, dh = 65, 528 - 50, 45, 40
    
    scroll_offset = 0
    visible_items = 6 # Matches about 6 items vertically
    max_scroll = max(0, len(detailed_steps) - visible_items)
    
    while running:
        dclear(t['modal_bg'])
        draw_header(t, "AI Pipeline Logic")
        
        iy = 60
        rects = []
        
        # Display the visible range of items based on scroll offset
        for i in range(scroll_offset, len(detailed_steps)):
            step = detailed_steps[i]
            if iy + 55 > 528 - 50: # Avoid overflowing past bottom buttons
                break
                
            drect(10, iy, 310, iy + 55, t['key_bg'])
            drect_border(10, iy, 310, iy + 55, C_NONE, 1, t['key_spec'])
            
            # Show position numbers to highlight the list is scrollable
            dtext_opt(20, iy + 15, t['txt'], C_NONE, DTEXT_LEFT, DTEXT_MIDDLE, f"[{i+1}/{len(detailed_steps)}] {step['title']}", -1)
            
            val = step['value']
            if len(val) > 30: val = val[:27] + "..."
            dtext_opt(20, iy + 40, t['txt_dim'], C_NONE, DTEXT_LEFT, DTEXT_MIDDLE, val, -1)
            
            rects.append((10, iy, 300, 55, step))
            iy += 65
            
        # --- Draw Graphical Scroll Buttons ---
        if max_scroll > 0:
            # Up Button
            up_bg = t['key_spec'] if scroll_offset > 0 else t['kbd_bg']
            up_col = t['txt'] if scroll_offset > 0 else t['txt_dim']
            drect(ux, uy, ux+uw, uy+uh, up_bg)
            drect_border(ux, uy, ux+uw, uy+uh, C_NONE, 1, t['hl'])
            cx, cy = ux + uw//2, uy + uh//2
            dpoly([cx, cy-8, cx-10, cy+8, cx+10, cy+8], up_col, C_NONE)
            
            # Down Button
            dn_bg = t['key_spec'] if scroll_offset < max_scroll else t['kbd_bg']
            dn_col = t['txt'] if scroll_offset < max_scroll else t['txt_dim']
            drect(dx, dy, dx+dw, dy+dh, dn_bg)
            drect_border(dx, dy, dx+dw, dy+dh, C_NONE, 1, t['hl'])
            cx, cy = dx + dw//2, dy + dh//2
            dpoly([cx, cy+8, cx-10, cy-8, cx+10, cy-8], dn_col, C_NONE)
            
        # Back Button
        drect(bx, by, bx+bw, by+bh, t['key_spec'])
        drect_border(bx, by, bx+bw, by+bh, C_NONE, 1, t['hl'])
        dtext_opt(bx+bw//2, by+bh//2, t['txt'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "Back", -1)
        
        dupdate()
        cleareventflips()

        ev = pollevent()
        events = []
        while ev.type != KEYEV_NONE:
            events.append(ev)
            ev = pollevent()

        if keypressed(KEY_EXIT) or keypressed(KEY_EXE): return
        if check_close_btn(events): return
        
        # --- Keyboard scrolling logic ---
        if keypressed(KEY_DOWN) and scroll_offset < max_scroll:
            scroll_offset += 1
        elif keypressed(KEY_UP) and scroll_offset > 0:
            scroll_offset -= 1

        for e in events:
            if e.type == KEYEV_TOUCH_DOWN and not touch_latched:
                touch_latched = True
            elif e.type == KEYEV_TOUCH_UP:
                if touch_latched:
                    touch_latched = False
                    
                    if bx <= e.x <= bx+bw and by <= e.y <= by+bh:
                        return
                        
                    # --- Touch Page Scrolling ---
                    if max_scroll > 0:
                        if ux <= e.x <= ux+uw and uy <= e.y <= uy+uh:
                            if scroll_offset > 0:
                                scroll_offset = max(0, scroll_offset - visible_items + 1)
                            break
                        if dx <= e.x <= dx+dw and dy <= e.y <= dy+dh:
                            if scroll_offset < max_scroll:
                                scroll_offset = min(max_scroll, scroll_offset + visible_items - 1)
                            break

                    for rx, ry, rw, rh, step in rects:
                        if rx <= e.x <= rx+rw and ry <= e.y <= ry+rh:
                            show_step_detail(step)
                            break
        time.sleep(0.01)

def show_intro():
    t = cinput.get_theme('gpt')
    running = True
    touch_latched = False
    
    texts = [
        "Welcome to the Mixture",
        "of Experts (MoE) demo!",
        "",
        "MoE is the base",
        "for large language models",
        "that allow agent skills",
        "",
        "With Sequential Routing",
        "it can use multiple skills",
        "in a single run",
        "",
        "Note: It reads left-to-right",
        "so 2+3*5 evaluates as (2+3)*5.",
        "Try it out!"
    ]
    
    bx, by, bw, bh = 10, 528 - 50, 100, 40
    
    while running:
        dclear(t['modal_bg'])
        draw_header(t, "MathGPT MoE Router")

        y = 100
        for line in texts:
            dtext_opt(160, y, t['txt'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, line, -1)
            y += 25

        drect(bx, by, bx+bw, by+bh, t['key_spec'])
        drect_border(bx, by, bx+bw, by+bh, C_NONE, 1, t['hl'])
        dtext_opt(bx+bw//2, by+bh//2, t['txt'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "Continue", -1)

        dupdate()
        cleareventflips()

        ev = pollevent()
        events = []
        while ev.type != KEYEV_NONE:
            events.append(ev)
            ev = pollevent()

        if keypressed(KEY_EXE) or keypressed(KEY_EXIT): return True
        if check_close_btn(events): return False

        for e in events:
            if e.type == KEYEV_TOUCH_DOWN and not touch_latched:
                touch_latched = True
            elif e.type == KEYEV_TOUCH_UP:
                if touch_latched:
                    touch_latched = False
                    if bx <= e.x <= bx+bw and by <= e.y <= by+bh:
                        return True
        time.sleep(0.01)

def get_user_input():
    t = cinput.get_theme('gpt')
    user_input = ""
    running = True
    touch_latched = False

    examples = ["What is 21 times 2 ?", "2+3*5", "five and two", "twenty divided by 5"]
    ix, iy, iw, ih = 10, 60, 300, 45
    bx, by, bw, bh = 320 - 110, 528 - 50, 100, 40

    while running:
        dclear(t['modal_bg'])
        draw_header(t, "Enter Math Problem")

        # Input field
        drect(ix, iy, ix+iw, iy+ih, t['key_bg'])
        drect_border(ix, iy, ix+iw, iy+ih, C_NONE, 1, t['hl'])
        disp_text = user_input if user_input else "Tap to enter prompt..."
        col = t['txt'] if user_input else t['txt_dim']
        dtext_opt(20, iy+ih//2, col, C_NONE, DTEXT_LEFT, DTEXT_MIDDLE, disp_text, 280)

        # Examples
        dtext_opt(160, 150, t['txt_dim'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "Or pick an example:", -1)
        ey = 180
        ex_rects = []
        for ex in examples:
            drect(ix, ey, ix+iw, ey+45, t['key_spec'])
            dtext_opt(160, ey+22, t['txt'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, ex, -1)
            ex_rects.append((ix, ey, iw, 45, ex))
            ey += 55

        # Answer Button
        btn_col = t['accent'] if user_input else t['key_spec']
        drect(bx, by, bx+bw, by+bh, btn_col)
        drect_border(bx, by, bx+bw, by+bh, C_NONE, 1, t['hl'])
        dtext_opt(bx+bw//2, by+bh//2, t['txt_acc'] if user_input else t['txt_dim'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "Answer", -1)

        dupdate()
        cleareventflips()

        ev = pollevent()
        events = []
        while ev.type != KEYEV_NONE:
            events.append(ev)
            ev = pollevent()

        if keypressed(KEY_EXIT): return None
        if keypressed(KEY_EXE) and user_input: return user_input
        if check_close_btn(events): return None

        for e in events:
            if e.type == KEYEV_TOUCH_DOWN and not touch_latched:
                touch_latched = True
            elif e.type == KEYEV_TOUCH_UP:
                if touch_latched:
                    touch_latched = False
                    if ix <= e.x <= ix+iw and iy <= e.y <= iy+ih:
                        res = cinput.input("Prompt:", type="text", theme="gpt", layout="qwerty", touch_mode=KEYEV_TOUCH_UP)
                        if res is not None:
                            user_input = res
                    for rx, ry, rw, rh, ex_str in ex_rects:
                        if rx <= e.x <= rx+rw and ry <= e.y <= ry+rh:
                            user_input = ex_str
                    if bx <= e.x <= bx+bw and by <= e.y <= by+bh:
                        if user_input: return user_input
        time.sleep(0.01)

def run_visualizer(user_input):
    nums, ops, nlp_steps = nlp_tokenize(user_input)

    SLEEP_TIME = 0.4 # Faster animations since we can chain multiple steps
    
    # --- Handle single number (Echo) logic safely ---
    if len(nums) == 1:
        if len(ops) == 0:
            ops.append("echo")
        nums.append(0) # Dummy padding for MoE pair-execution logic
        nlp_steps[-1] = (nlp_steps[-1][0], nlp_steps[-1][1] + " <echo>")
    
    # 1. Animate NLP Tokenization Steps
    for step_name, step_val in nlp_steps:
        render_moe(-1, f"{step_name}:\n{step_val}", title="Tokenizing...")
        time.sleep(SLEEP_TIME * 1.5)
        
    # --- Compile Base Details for Explainability ---
    detailed_steps = []
    for name, val in nlp_steps:
        if name == "Input":
            desc = "This is the raw text entered. The AI first converts it to lowercase to standardize the input."
        elif name == "Math Padded":
            desc = "To make parsing easier without complex tools, spaces are added around math symbols like '+' and '-'."
        elif name == "Split":
            desc = "The text is split into an array of individual words (tokens) using spaces as boundaries."
        else: # Tokens
            desc = "Words are mapped to numbers ('two' -> 2.0) and operations ('plus' -> <add>). Unmatched words become ~noise~."
        detailed_steps.append({"title": name, "value": val, "desc": desc})
        
    # 2. Sequential MoE Execution
    is_err = False
    res = None
    active = -1
    output = ""

    if len(nums) < 2:
        output = f"Router Error:\nOnly found {len(nums)} number(s)"
        is_err = True
        detailed_steps.append({"title": "Routing Error", "value": "Missing numbers", "desc": "The router requires at least two numbers to begin processing."})
    elif len(ops) == 0:
        output = "Router Error:\nNo valid operation found"
        is_err = True
        detailed_steps.append({"title": "Routing Error", "value": "Missing operations", "desc": "The router could not find any action keywords to assign to an expert."})
    else:
        # Start with the first number
        res = nums[0]
        
        # Iterate through pairs of (operation, next_number)
        for i in range(min(len(ops), len(nums)-1)):
            op = ops[i]
            next_num = nums[i+1]
            
            # Route to expert
            found_expert = -1
            for j, expert in enumerate(EXPERTS):
                if op in expert["keywords"]:
                    found_expert = j
                    break
                    
            if found_expert == -1:
                output = f"Router Error:\nUnknown op '{op}'"
                is_err = True
                active = -1
                detailed_steps.append({
                    "title": "Routing Error", 
                    "value": f"Unknown token: {op}", 
                    "desc": "The router could not match the operation token to any known expert's keywords."
                })
                break
                
            active = found_expert
            
            # Animate Router thinking for this step
            for _ in range(2):
                if EXPERTS[active]['name'] == 'Echo':
                    render_moe(-1, f"Routing Step {i+1}...\n{res}", title="Routing...")
                else:
                    render_moe(-1, f"Routing Step {i+1}...\n{res} and {next_num}", title="Routing...")
                time.sleep(SLEEP_TIME)
                
            render_moe(active, f"Expert: {EXPERTS[active]['name']}\nComputing...", title="Computing...")
            time.sleep(SLEEP_TIME)
            
            # Save previous result for explainability
            prev_res = res
            
            # Compute using the expert
            res = EXPERTS[active]["func"](res, next_num)
            
            # Check for division by zero error
            if isinstance(res, str) and "Error" in res:
                output = res
                is_err = True
                detailed_steps.append({"title": f"Step {i+1} Error", "value": "Math Error", "desc": res})
                break
            
            # Add step details
            if EXPERTS[active]['name'] == 'Echo':
                desc = f"The Echo expert received the single token [{prev_res}] and echoed it back unmodified."
            else:
                desc = f"The {EXPERTS[active]['name']} expert received the previous total [{prev_res}] and the next token [{next_num}] and computed the new total {res}."
                
            detailed_steps.append({
                "title": f"Step {i+1}: {EXPERTS[active]['name']}", 
                "value": f"Result: {res}", 
                "desc": desc
            })
        
        if not is_err:
            output = f"Final Result: {res}"
        
    # Wait for Back or Close
    running = True
    touch_latched = False
    bx, by, bw, bh = 320 - 110, 528 - 50, 100, 40
    sx, sy, sw, sh = 10, 528 - 50, 130, 40 # View Steps button
    
    while running:
        render_moe(active, output, show_back=True, is_err=is_err, title="Result", show_steps_btn=True)
        cleareventflips()
        
        ev = pollevent()
        events = []
        while ev.type != KEYEV_NONE:
            events.append(ev)
            ev = pollevent()

        if keypressed(KEY_EXIT) or keypressed(KEY_EXE): return True
        if check_close_btn(events): return False

        for e in events:
            if e.type == KEYEV_TOUCH_DOWN and not touch_latched:
                touch_latched = True
            elif e.type == KEYEV_TOUCH_UP:
                if touch_latched:
                    touch_latched = False
                    if bx <= e.x <= bx+bw and by <= e.y <= by+bh:
                        return True
                    if sx <= e.x <= sx+sw and sy <= e.y <= sy+sh:
                        show_steps_list(detailed_steps)
        time.sleep(0.01)

# --- Execution ---
def run_app():
    if not show_intro(): 
        return
        
    while True:
        ui = get_user_input()
        if ui is None: 
            break
        # run_visualizer returns False if App was explicitly closed via 'X'
        if not run_visualizer(ui):
            break

run_app()
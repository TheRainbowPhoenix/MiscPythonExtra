# --------------------------------------------------------------------------
# Markdown Viewer - Simple MD Parser & Renderer
# Inspired by generic MD parsers and webcalc2.py layout engine
# --------------------------------------------------------------------------
from gint import *
import time
import cinput

import svf

#  Constants ---
SCREEN_W = 320
SCREEN_H = 528
HEADER_H = 40

# Colors
C_BG_DEFAULT = C_WHITE
C_TEXT_DEFAULT = C_BLACK
C_CODE_BG = 0xDEFB # Light gray/beige
C_HEADER_BORDER = 0x8410 # Gray
C_QUOTE_BAR = 0xC618 # Silver

# Fonts & Layout
FONT_W = 10
FONT_H = 18
LINE_H = 20 # Added line height for better spacing
TEXT_Y_OFFSET = 4 # Vertical offset for text

# Image Handling
class ImageCache:
    _cache = {} # path -> (w, h, data)
    
    @staticmethod
    def get_info(path):
        if path in ImageCache._cache: return ImageCache._cache[path]
        
        # Load
        data = None
        try:
            with open(path, "rb") as f: data = f.read()
        except:
             return None
        
        try:
            # Check standard SVF
            dims = svf.get_svf_metrics(data)
            w, h = 100, 100 # Default if no viewbox
            if dims:
                w, h = dims
                # Scale from 10x if implicit? No, svf.py metrics return raw values.
                # Editor saves at 10x scale if user requested.
                # But get_svf_metrics reads the raw bytes.
                # If editor stored 3200x5280 for a full screen...
                # We need to know if it's scaled.
                # Usually standard SVF units are pixels or relative.
                # Let's assume raw units.
                pass
            else:
                 # Fallback: maybe calculate bounding box from data?
                 # Too expensive to parse fully here?
                 # User said: "check if vector define size... respect it else load 1 and draw"
                 # If no viewBox, we might just assume some size or decode?
                 pass
            
            ImageCache._cache[path] = (w, h, data)
            return (w, h, data)
        except:
            return None

    @staticmethod
    def get_render_size(path, container_w):
        info = ImageCache.get_info(path)
        if not info: return (0, 0)
        
        orig_w, orig_h, _ = info
        
        # Logic:
        # If w < container_w: use w, h
        # If w > container_w: scale down to fit container width, preserve aspect
        
        # User said: "if viewbox is smaller than width display... but if larger then downscale"
        # Also need to consider 10x scale assumption?
        # If w=3200, it's definitely larger than screen 320.
        # So downscale logic handles the 10x implicitly if Aspect Ratio is correct.
        
        target_w = orig_w
        target_h = orig_h
        
        if target_w > container_w:
            ratio = container_w / target_w
            target_w = container_w
            target_h = int(orig_h * ratio)
            
        return (target_w, target_h)

#  Data Structures ---

class Style:
    def __init__(self):
        self.block = True # Block vs Inline
        self.margin = [0, 0, 0, 0] # T, R, B, L
        self.padding = [0, 0, 0, 0]
        self.border = [0, 0, 0, 0]
        self.bg_color = -1 # Transparent
        self.border_color = C_BLACK
        self.color = C_TEXT_DEFAULT
        self.font_scale = 1 # Reserved for future
        self.align = 0 # 0=Left, 1=Center, 2=Right
        self.pre = False # Preformatted (code blocks)

class Node:
    def __init__(self, type_name, parent=None):
        self.type = type_name
        self.parent = parent
        self.children = []
        self.spans = [] # For text nodes: list of (text, type/style_id)
        self.style = Style()

        # Computed Layout
        self.x = 0
        self.y = 0
        self.w = 0
        self.h = 0
        self.lines = [] # Computed line wrappers

    def add_child(self, child):
        self.children.append(child)
        child.parent = self

#  Markdown Parser ---

#  text sanitization ---

def sanitize_text(text):
    # Basic replacement for common unsupported chars
    if not isinstance(text, str): return str(text)
    return text.replace(u'\u2019', "'").replace(u'\u201c', '"').replace(u'\u201d', '"').replace(u'\u2014', '--')

#  Markdown Parser ---

def parse_inline(text):
    """
    Parses inline markdown: **bold**, `code`, [link](url).
    Returns a list of tuples: (text_content, style_mask, data)
    style_mask: 0=Normal, 1=Bold, 2=Code, 3=Link, 4=Italic, 5=Strikethrough
    """
    spans = []
    i = 0
    length = len(text)

    current_text = ""
    current_style = 0 # 0=Normal

    def flush():
        nonlocal current_text
        if current_text:
            spans.append((current_text, current_style, None))
            current_text = ""

    while i < length:
        # Code backtick
        if text[i] == '`':
            flush()
            if current_style == 2:
                current_style = 0
            else:
                current_style = 2
            i += 1
            continue

        # Bold ** or __
        if i+1 < length and (text[i:i+2] == '**' or text[i:i+2] == '__'):
            flush()
            if current_style == 1:
                current_style = 0
            else:
                current_style = 1
            i += 2
            continue

        # Strikethrough ~~
        if i+1 < length and text[i:i+2] == '~~':
            flush()
            if current_style == 5:
                current_style = 0
            else:
                current_style = 5
            i += 2
            continue

        # Italic * or _
        if text[i] == '*' or text[i] == '_':
            flush()
            if current_style == 4:
                current_style = 0
            else:
                current_style = 4
            i += 1
            continue

        # Image ![alt](url)
        if text[i] == '!' and i+1 < length and text[i+1] == '[':
            end_bracket = text.find(']', i+1)
            if end_bracket != -1 and end_bracket + 1 < length and text[end_bracket+1] == '(':
                end_paren = text.find(')', end_bracket + 1)
                if end_paren != -1:
                    flush()
                    alt_text = text[i+2:end_bracket]
                    img_url = text[end_bracket+2:end_paren]
                    
                    spans.append((alt_text, 6, img_url)) # 6 = Image
                    i = end_paren + 1
                    continue

        # Link [text](url)
        if text[i] == '[':
            end_bracket = text.find(']', i)
            if end_bracket != -1 and end_bracket + 1 < length and text[end_bracket+1] == '(':
                end_paren = text.find(')', end_bracket + 1)
                if end_paren != -1:
                    flush()
                    link_text = text[i+1:end_bracket]
                    link_url = text[end_bracket+2:end_paren]

                    spans.append((link_text, 3, link_url)) # 3 = Link
                    i = end_paren + 1
                    continue

        current_text += text[i]
        i += 1

    flush()

    return spans

def get_quote_depth_content(line):
    # Count leading '>' chars, ignoring spaces
    # Actually, Markdown spec allows space between '>'
    # "> >" is depth 2.
    # ">>" is depth 2.
    # "> text" is depth 1.
    depth = 0
    content = line
    while content.startswith('>'):
        depth += 1
        content = content[1:].strip()
    return depth, content

def parse_markdown(md_text):
    root = Node('root')
    root.style.padding = [10, 5, 10, 5]

    lines = md_text.replace('\r\n', '\n').split('\n')

    i = 0
    n_lines = len(lines)

    while i < n_lines:
        line = lines[i]
        # Check indentation for lists
        indent = len(line) - len(line.lstrip())
        stripped = line.strip()

        # 1. Empty lines
        if not stripped:
            i += 1
            continue

        # 2. Syntax Checking

        # Headers
        if stripped.startswith('#'):
            level = 0
            for char in stripped:
                if char == '#': level += 1
                else: break

            content = stripped[level:].strip()

            node = Node('header', root)
            node.style.block = True
            node.style.margin = [10 if level == 1 else 15, 0, 10, 0]
            node.style.font_scale = 1

            if level <= 2:
                node.style.border = [0, 0, 2, 0] # Bottom border
                node.style.padding = [0, 0, 5, 0]
                node.style.bg_color = C_WHITE

            node.spans = parse_inline(content)
            root.add_child(node)
            i += 1
            continue

        # Horizontal Rule
        if stripped.startswith('---') or stripped.startswith('***'):
            # Check if this is a table header separator
            if stripped.startswith('---') and '|' in stripped:
               pass # Let the table parser handle it (actually table parser handles prev line)
            elif not stripped.startswith('|'): # Only if not a table row
                node = Node('hr', root)
                node.style.margin = [10, 0, 10, 0]
                node.style.h = 2
                node.style.bg_color = C_BLACK
                root.add_child(node)
                i += 1
                continue

        # Tables
        if stripped.startswith('|'):
            # Look ahead to see if it's a table (next line has separator)
            if i + 1 < n_lines:
                next_line = lines[i+1].strip()
                if next_line.startswith('|') and '---' in next_line:
                    # It is a table!

                    # Parse Header
                    header_cells = [c.strip() for c in stripped.strip('|').split('|')]

                    # Parse Separator (Alignment)
                    alignments = [] # 0=Left, 1=Center, 2=Right
                    sep_weights = [] # Width weight based on --- length
                    sep_cells = [c.strip() for c in next_line.strip('|').split('|')]

                    for sep in sep_cells:
                        # Weight calc: count dashes
                        dashes = sep.count('-')
                        if dashes < 1: dashes = 1
                        sep_weights.append(dashes)

                        if sep.startswith(':') and sep.endswith(':'):
                            alignments.append(1)
                        elif sep.endswith(':'):
                            alignments.append(2)
                        else:
                            alignments.append(0)

                    table_node = Node('table', root)
                    table_node.style.margin = [10, 0, 10, 0]
                    table_node.style.border = [1, 1, 1, 1]
                    table_node.col_alignments = alignments
                    table_node.col_weights = sep_weights
                    table_node.col_count = len(header_cells)

                    # Add Header Row
                    row_node = Node('table_row', table_node)
                    row_node.style.bg_color = 0xCE79 # Light header bg
                    for idx, txt in enumerate(header_cells):
                        cell = Node('table_cell', row_node)
                        cell.style.padding = [4, 4, 4, 4]
                        cell.style.border = [0, 1, 1, 0] # R, B
                        cell.style.align = alignments[idx] if idx < len(alignments) else 0
                        cell.spans = parse_inline(txt)
                        row_node.add_child(cell)
                    table_node.add_child(row_node)

                    i += 2

                    # Parse Body
                    while i < n_lines:
                        line = lines[i].strip()
                        if not line.startswith('|'): break

                        cells = [c.strip() for c in line.strip('|').split('|')]
                        row_node = Node('table_row', table_node)

                        for idx, txt in enumerate(cells):
                            if idx >= table_node.col_count: break
                            cell = Node('table_cell', row_node)
                            cell.style.padding = [4, 4, 4, 4]
                            cell.style.border = [0, 1, 1, 0] # R, B
                            cell.style.align = alignments[idx] if idx < len(alignments) else 0
                            cell.spans = parse_inline(txt)
                            row_node.add_child(cell)

                        table_node.add_child(row_node)
                        i += 1

                    root.add_child(table_node)
                    continue

        # Block Quotes
        if stripped.startswith('>'):
            # Detect initial depth
            depth, quote_text = get_quote_depth_content(stripped)

            i += 1
            while i < n_lines:
                next_line = lines[i].strip()
                if not next_line: break
                if any(next_line.startswith(x) for x in ['#', '-', '*', '+', '```', '---']): break

                # Check for > continuation or lazy continuation
                if next_line.startswith('>'):
                    next_depth, next_content = get_quote_depth_content(next_line)
                    if next_depth != depth:
                        break # Depth changed, start new blockquote node
                    quote_text += " " + next_content
                else:
                    # Lazy continuation (depth 0, effectively)
                    # Standard markdown says this belongs to current blockquote
                    quote_text += " " + next_line
                i += 1

            node = Node('blockquote', root)
            # Indent based on depth
            node.style.margin = [5, 0, 5, (depth - 1) * 20]
            node.style.padding = [5, 5, 5, 10]
            node.style.border = [0, 0, 0, 2] # Left border
            node.style.bg_color = 0xEF5D # Light Gray
            node.style.border_color = C_QUOTE_BAR # Silver

            node.spans = parse_inline(quote_text)
            root.add_child(node)
            continue

        # Custom Containers
        if stripped.startswith('::: '):
            container_type = stripped[4:].strip().lower()

            # Colors
            bg_col = 0xEF5D # Gray default
            border_col = C_BLACK

            if 'warning' in container_type:
                bg_col = 0xFFE0 # Yellow-ish
                border_col = 0xFD20 # Orange
            elif 'tip' in container_type:
                bg_col = 0xE7FF # Green-ish
                border_col = 0x07E0 # Green
            elif 'danger' in container_type:
                bg_col = 0xF800 # Red-ish
                border_col = 0xF800 # Red

            node = Node('container', root)
            node.style.margin = [10, 0, 10, 0]
            node.style.padding = [10, 10, 10, 10]
            node.style.bg_color = bg_col
            node.style.border = [1, 1, 1, 4] # Left border thick
            node.style.border_color = border_col

            i += 1

            # Capture content until :::
            container_content = []
            while i < n_lines:
                if lines[i].strip() == ':::':
                    i += 1
                    break
                container_content.append(lines[i])
                i += 1

            # Recurse? Simple implementation: Treat as paragraph text for now
            # Proper implementation would recursively parse markdown inside.
            # Let's try to just parse it as inline text for simplicity, or
            # better yet, re-use parse_markdown recursively but we need to change parse_markdown signature to take a parent node?
            # Or just wrap content in a paragraph node inside this container.

            content_text = "\n".join(container_content)
            para = Node('paragraph', node)
            para.style.margin = [0, 0, 0, 0]
            para.spans = parse_inline(content_text)
            node.add_child(para)

            root.add_child(node)
            continue

        # Code Blocks
        if stripped.startswith('```'):
            code_lines = []
            i += 1
            while i < n_lines:
                if lines[i].strip().startswith('```'):
                    i += 1
                    break
                code_lines.append(lines[i]) # Preserve indentation
                i += 1

            node = Node('code_block', root)
            node.style.pre = True
            node.style.bg_color = C_CODE_BG
            node.style.color = C_BLACK # Black Text for code blocks
            node.style.padding = [5, 5, 5, 5]
            node.style.margin = [5, 0, 5, 0]
            node.style.border = [1, 1, 1, 1]
            # Use default border color (Black) for code blocks

            full_code = "\n".join(code_lines)
            node.spans = [(full_code, 2, None)] # Style 2 = Code

            root.add_child(node)
            continue

        # List Items
        if stripped.startswith('- ') or stripped.startswith('* ') or stripped.startswith('+ '):
            content = stripped[2:].strip()
            node = Node('list_item', root)

            indent_level = indent // 2

            node.style.margin = [2, 0, 2, 5 + (indent_level * 10)]
            node.style.padding = [0, 0, 0, 12] # Indent content for bullet

            # No bullet in text, drawn manually
            node.spans = parse_inline(content)
            root.add_child(node)
            i += 1
            continue

        # Paragraphs
        para_text = stripped
        i += 1
        while i < n_lines:
            next_line = lines[i].strip()
            if not next_line: break
            if any(next_line.startswith(x) for x in ['#', '-', '*', '+', '```', '---', '>']): break

            para_text += " " + next_line
            i += 1

        node = Node('paragraph', root)
        node.style.margin = [0, 0, 8, 0]
        node.spans = parse_inline(para_text)
        root.add_child(node)

    return root

#  Layout Engine ---

def get_wrapped_lines(spans, max_width, is_pre=False):
    """
    Wraps text spans into lines using dsize logic.
    """
    lines = []

    if is_pre:
        # Code block: Sanitized, allow wrap per line.
        raw_text = sanitize_text(spans[0][0])
        style = spans[0][1]
        data = spans[0][2]

        # Split by hard newlines
        hard_lines = raw_text.split('\n')
        for hl in hard_lines:
            if not hl:
                # Empty line -> add empty line
                lines.append([])
                continue

            # Recursively wrap each hard line
            # Treat as normal text (is_pre=False)
            wrapped_subs = get_wrapped_lines([(hl, style, data)], max_width, False)
            if not wrapped_subs: lines.append([])
            else: lines.extend(wrapped_subs)

        return lines

    # Normal Wrapping
    current_line = []
    current_w = 0
    space_w, _ = dsize(" ", None)

    for text, style, data in spans:
        clean_text = sanitize_text(text)
        if style == 6:
             words = [text] # Treat image alt text as single block
        else:
             words = clean_text.split(' ')

        for idx, word in enumerate(words):
            if not word and idx < len(words) - 1: continue # Skip empty splits except maybe single spaces? Logic is fuzzy here.

            # Determine size
            word_w = 0
            word_h = 0
            
            if style == 6: # Image
                # Check if image loaded
                img_path = data
                # Handle relative paths? 
                # Assuming simple paths for now.
                i_w, i_h = ImageCache.get_render_size(img_path, max_width)
                if i_w > 0:
                    word_w = i_w
                    word_h = i_h
                else:
                    word_w, _ = dsize(word, None) # Fallback to alt text size
            else:
                 word_w, _ = dsize(word, None)

            # Determine space before this word
            add_space = False
            if idx > 0 or (current_w > 0 and current_line and not current_line[-1][0].endswith(" ")):
                 if style != 6: add_space = True # Don't auto-space images?

            space_w_curr = space_w if add_space else 0

            # Wrap if overflows
            if current_w + space_w_curr + word_w > max_width and current_w > 0:
                lines.append(current_line)
                current_line = []
                current_w = 0
                space_w_curr = 0

            # Append content
            prefix = " " if space_w_curr else ""
            
            if style == 6 and word_w > 0:
                 # It's an image.
                 # Force wrap if not first item? simple block behavior for big images.
                 if word_w > max_width * 0.5 and current_w > 0:
                      lines.append(current_line)
                      current_line = []
                      current_w = 0
                      prefix = ""
                 
                 current_line.append((prefix + word, style, (data, word_w, word_h))) # Store dims in data
                 current_w += word_w
            else:
                 current_line.append((prefix + word, style, data))
                 current_w += space_w_curr + word_w

    if current_line:
        lines.append(current_line)

    return lines

def resolve_layout(node, container_w):
    s = node.style

    # Margins/Padding
    avail_w = container_w - s.margin[1] - s.margin[3] - s.border[1] - s.border[3]
    content_w = avail_w - s.padding[1] - s.padding[3]

    node.w = container_w

    # Children or Content?
    current_h = s.padding[0] + s.border[0]

    if node.type == 'table':
        # Table Layout Logic
        # Use Weights from --- separator lines
        total_weight = sum(node.col_weights)
        if total_weight == 0: total_weight = 1 # avoid div by zero

        col_widths = []
        for w in node.col_weights:
            # Calculate width based on weight ratio
            cw = int((w / total_weight) * content_w)
            if cw < 20: cw = 20 # Minimum width
            col_widths.append(cw)

        # Re-adjust if we exceeded content_w due to min-width
        if sum(col_widths) > content_w:
             # Scale down uniformly or just clip? Let's verify
             # Simple approach: Recalculate if needed, but for now strict weight
             scale = content_w / sum(col_widths)
             col_widths = [int(cw * scale) for cw in col_widths]

        # 3. Layout Rows/Cells
        rows = node.children # Define rows since we removed the previous block
        current_h = s.padding[0] + s.border[0]

        for row in rows:
            row.x = s.margin[3] + s.border[3] + s.padding[3]
            row.y = current_h
            row.w = sum(col_widths)

            cell_x = 0
            max_cell_h = 0

            for i, cell in enumerate(row.children):
                if i >= len(col_widths): break

                cell.x = cell_x
                cell.y = 0
                cell.w = col_widths[i]

                # Resolve cell content with fixed width
                resolve_layout(cell, col_widths[i])

                max_cell_h = max(max_cell_h, cell.h)
                cell_x += col_widths[i]

            # Stretch all cells to row height
            for cell in row.children:
                cell.h = max_cell_h

            row.h = max_cell_h
            current_h += row.h

        node.h = current_h + s.padding[2] + s.border[2]

    elif node.spans:
        # It's a text/leaf node
        lines = get_wrapped_lines(node.spans, content_w, s.pre)
        node.lines = lines
        
        # Compute variable line heights
        total_h = 0
        node.line_heights = []
        
        for line in lines:
            line_h = LINE_H
            for _, style_id, data in line:
                if style_id == 6: # Image
                    # data is (url, w, h)
                    if isinstance(data, tuple) and len(data) == 3:
                        img_h = data[2] # h
                        if img_h > line_h: line_h = img_h
            
            node.line_heights.append(line_h)
            total_h += line_h
            
        node.h = total_h + s.padding[2] + s.border[2]
        current_h += total_h
    else:
        # Container
        for child in node.children:
            resolve_layout(child, content_w)

            # If parent is table row, children (cells) already have x/y/w set by table layout logic
            if node.type != 'table_row':
                child.x = s.margin[3] + s.border[3] + child.style.margin[3] + s.padding[3]
                child.y = current_h + child.style.margin[0]
                current_h += child.h + child.style.margin[0] + child.style.margin[2]
            else:
                 # Table row height is max of cells
                 pass

    if node.type != 'table_row':
        node.h = current_h + s.padding[2] + s.border[2]

#  Rendering ---

def draw_node(node, abs_x, abs_y, scroll_y, hotspots=None):
    screen_x = abs_x + node.x
    screen_y = abs_y + node.y - scroll_y

    # Cull
    if screen_y > SCREEN_H or screen_y + node.h < HEADER_H:
         return

    s = node.style

    # Background
    bb_w = node.w - s.margin[1] - s.margin[3]
    if s.bg_color != -1:
        drect(screen_x, screen_y, screen_x + bb_w, screen_y + node.h, s.bg_color)

    # Borders

    # Top
    if s.border[0] > 0:
        drect(screen_x, screen_y, screen_x + bb_w, screen_y + s.border[0], s.border_color)

    # Right
    if s.border[1] > 0:
        drect(screen_x + bb_w - s.border[1], screen_y, screen_x + bb_w, screen_y + node.h, s.border_color)

    # Bottom
    if s.border[2] > 0:
        by = screen_y + node.h - s.border[2]
        drect(screen_x, by, screen_x + bb_w, screen_y + node.h, s.border_color)

    # Left
    if s.border[3] > 0:
        drect(screen_x, screen_y, screen_x + s.border[3], screen_y + node.h, s.border_color)

    # Bullet for List Items
    if node.type == 'list_item':
        # Draw bullet centered on first line (circle radius 2)
        bx = screen_x + 6
        # Assume first line is standard text height for bullet alignment?
        # Or vertically center in line?
        first_lh = node.line_heights[0] if hasattr(node, 'line_heights') and node.line_heights else LINE_H
        by = screen_y + s.padding[0] + s.border[0] + (first_lh // 2)
        dcircle(bx, by, 2, C_BLACK, 1)

    # Text Content
    if node.lines:
        txt_y = screen_y + s.padding[0] + s.border[0]
        txt_x_start = screen_x + s.padding[3] + s.border[3]
        
        # Use computed heights if available
        line_heights = getattr(node, 'line_heights', [LINE_H] * len(node.lines))

        for idx, line in enumerate(node.lines):
            curr_x = txt_x_start
            l_h = line_heights[idx]
            
            # Optimization: If we went past the screen, stop drawing lines
            if txt_y > SCREEN_H: break

            if txt_y + l_h > HEADER_H: # and txt_y < SCREEN_H (implied by break above)
                for text, style_id, style_data in line:
                    col = s.color
                    t_w = 0
                    
                    if style_id == 6: # Image
                        # style_data is (url, w, h)
                        if isinstance(style_data, tuple):
                             url, iw, ih = style_data
                             t_w = iw
                             # Render SVF
                             info = ImageCache.get_info(url)
                             if info:
                                 _, _, svf_data = info
                                 # Calculate scale?
                                 # svf_data is raw. 
                                 # We determined iw, ih via get_render_size (which downscaled if needed)
                                 # But we need intrinsic size to know scale factor.
                                 # get_info returns (orig_w, orig_h, data)
                                 orig_w, orig_h, _ = info
                                 # Scale factor = iw / orig_w
                                 scale = 1.0
                                 if orig_w > 0: scale = iw / orig_w
                                 
                                 # Vertical align? Bottom align or center?
                                 # Let's center vertically in line if line height > img height
                                 # But here line height IS img height usually.
                                 # Draw
                                 svf.render_vector_icon(svf_data, int(curr_x), int(txt_y + (l_h - ih)//2), scale)
                                 
                        else:
                             # Fallback text
                             t_w, _ = dsize(text, None)
                             dtext(curr_x, txt_y + (l_h - FONT_H)//2, col, text) # center text
                    
                    else:
                        t_w, _ = dsize(text, None)
                        
                        # Vertically center text in line (for mixed content)
                        # Text height is roughly FONT_H or LINE_H logic?
                        # Standard LINE_H is 20. FONT_H is 18.
                        # We use LINE_H for bounds.
                        draw_y = txt_y + (l_h - LINE_H) // 2 + TEXT_Y_OFFSET
                        # If l_h is huge (image), text sits in middle?
                        # Or baseline? Middle is safer for now.

                        # Style modifications
                        if style_id == 2 and not s.pre: # Inline Code Highlight ONLY
                             drect(curr_x + 1, draw_y - 2, curr_x + t_w, draw_y + LINE_H - 4, 0xCE79)
                        elif style_id == 1: # Bold
                             dtext(curr_x+1, draw_y, col, text)
                        elif style_id == 3: # Link
                             col = C_BLUE
                             dline(curr_x, draw_y + FONT_H - 7, curr_x + t_w, draw_y + FONT_H - 7, C_BLUE)
                             if hotspots is not None:
                                 hotspots.append(((curr_x, txt_y, t_w, l_h), style_data))
                        elif style_id == 4: # Italic/Underscore
                            # Since no italic font, draw a light underline
                            # dline(curr_x, txt_y + LINE_H - 1, curr_x + t_w, txt_y + LINE_H - 1, col)
                            pass
                        elif style_id == 5: # Strikethrough
                            d_y = - 4
                            dline(curr_x, draw_y + FONT_H // 2  + d_y, curr_x + t_w, draw_y + FONT_H // 2 + d_y, col)

                        dtext(curr_x, draw_y, col, text)
                    
                    curr_x += t_w

            txt_y += l_h

    # Children
    for child in node.children:
        draw_node(child, screen_x, screen_y, 0, hotspots)

#  App Shell ---

# ... imports ...
import cinput

# ... existing code ...

#  App Shell & IO ---

def draw_icon_menu(x, y, col):
    for i in range(3):
        drect(x, y + 4 + i*5, x + 18, y + 5 + i*5, col)

def draw_header(title):
    drect(0, 0, SCREEN_W, HEADER_H, 0x8410) # Gray header
    # dtext(10, 12, C_WHITE, title)
    # Menu Icon
    # draw_icon_menu(10, 10, C_WHITE) # If we want icon, need to shift title
    # Let's shift title and draw icon
    drect(0, 0, 40, HEADER_H, 0x8410) # Clear area
    draw_icon_menu(10, 10, C_WHITE)
    dtext(50, 16, C_WHITE, title)

    drect(0, HEADER_H, SCREEN_W, HEADER_H+2, C_BLACK) # Separator

def do_menu(current_file):
    opts = [
        "Open...",
        "Quit"
    ]
    choice = cinput.pick(opts, "Menu")

    if choice == "Open...":
        fname = cinput.input("File to open:")
        if fname: return fname
    elif choice == "Quit":
        return "QUIT"

    return None

def main():
    # Initial Load
    path = "1.md"
    dom = None

    def load(fname):
        nonlocal dom, path
        try:
            with open(fname, "r", encoding="utf-8") as f:
                content = f.read()
            # Parse
            dclear(C_WHITE)
            dtext(10, 200, C_BLACK, "Parsing...")
            dupdate()
            dom = parse_markdown(content)
            resolve_layout(dom, SCREEN_W)
            path = fname
        except Exception:
            # Fallback error
            dom = parse_markdown(f"# Error\nCould not load {fname}")
            resolve_layout(dom, SCREEN_W)
            path = fname

    load(path)

    scroll_y = 0
    running = True
    touch_latched = False

    clearevents()

    while running:
        dclear(C_WHITE)

        # Max Scroll Update
        max_scroll = max(0, dom.h - (SCREEN_H - HEADER_H))

        # Hotspots
        hotspots = []

        # Draw Document
        draw_node(dom, 0, HEADER_H + 5, scroll_y, hotspots)

        # Draw Header
        draw_header(path)

        # Scrollbar
        if dom.h > (SCREEN_H - HEADER_H):
            view_h = SCREEN_H - HEADER_H
            sb_h = max(20, int((view_h / dom.h) * view_h))
            sb_y = HEADER_H + int((scroll_y / dom.h) * view_h)
            drect(SCREEN_W-5, sb_y, SCREEN_W, sb_y+sb_h, 0x8410)

        dupdate()

        # Events
        cleareventflips()
        events = []
        ev = pollevent()
        while ev.type != KEYEV_NONE:
            events.append(ev)
            ev = pollevent()

        for e in events:
            if e.type == KEYEV_DOWN:
                if e.key == KEY_EXIT:
                    running = False
                elif e.key == KEY_UP:
                    scroll_y = max(0, scroll_y - 40)
                elif e.key == KEY_DOWN:
                    scroll_y = min(max_scroll, scroll_y + 40)
                elif e.key == KEY_MENU or e.key == KEY_F1:
                    res = do_menu(path)
                    if res == "QUIT": running = False
                    elif res:
                        load(res)
                        scroll_y = 0
                    clearevents()

            elif e.type == KEYEV_TOUCH_UP:
                touch_latched = False

            elif e.type == KEYEV_TOUCH_DOWN:
                if not touch_latched:
                    touch_latched = True
                    # Header Click
                    if e.y < HEADER_H:
                        if e.x < 50: # Menu area
                            res = do_menu(path)
                            if res == "QUIT": running = False
                            elif res:
                                load(res)
                                scroll_y = 0
                            clearevents()
                    else:
                        # Check Link Hotspots
                        clicked_link = False
                        for (hx, hy, hw, hh), link_url in hotspots:
                            if e.x >= hx and e.x <= hx + hw and e.y >= hy and e.y <= hy + hh:
                                if link_url:
                                    load(link_url)
                                    scroll_y = 0
                                    clicked_link = True
                                    clearevents()
                                    break

                        if not clicked_link:
                            # Drag scroll?
                            pass

    print("Done")

main()
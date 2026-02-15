from gint import *
import struct

# =============================================================================
# BINARY VECTOR FORMAT SPECIFICATION
# =============================================================================
# Header: 4 bytes -> b'VEC1' (Magic + Version)
# Commands: 1 byte Opcode + Data
# Coordinates are typically 2-byte signed shorts (int16)
# Colors are 2-byte unsigned shorts (uint16, RGB555)

# Opcodes
CMD_END       = 0x00  # End of stream
CMD_SET_COLOR = 0x01  # Set Fill/Stroke colors
                      # Data: [Fill: uint16, Stroke: uint16]
                      # Use C_NONE (0xFFFF usually, or specific flag) for transparent

CMD_RECT      = 0x10  # Draw Rectangle
                      # Data: [x1: int16, y1: int16, x2: int16, y2: int16]
                      
CMD_RECT_B    = 0x11  # Draw Bordered Rectangle (custom border width)
                      # Data: [x1, y1, x2, y2 (int16), width: uint8]

CMD_CIRCLE    = 0x20  # Draw Circle
                      # Data: [cx: int16, cy: int16, r: int16]

CMD_ELLIPSE   = 0x21  # Draw Ellipse
                      # Data: [x1, y1, x2, y2] (Bounding box)

CMD_LINE      = 0x30  # Draw Line
                      # Data: [x1, y1, x2, y2]

CMD_POLY      = 0x40  # Draw Polygon
                      # Data: [count: uint8, (x, y)...]
                      # count is number of vertices. Followed by count * 2 int16s.

CMD_TEXT_OPT  = 0x50  # Draw Text (Optional hint)
                      # Data: [x: int16, y: int16, len: uint8, char bytes...]
                      # Uses current stroke color as text color

CMD_OBJ_NAME  = 0x55  # Set Object Name (Metadata)
                      # Data: [len: uint8, char bytes...]

CMD_VIEWBOX   = 0x60  # Set Canvas ViewBox (Metadata)
                      # Data: [width: int16, height: int16]
                      # Defines the intended aspect ratio and coordinate space size.

# Special Color Flag for Transparent (since gint C_NONE is often -1 or specific int)
# In RGB555 (0-31 per channel), standard colors are positive.
# We will use 0xFFFF to represent C_NONE in the binary format.
BIN_C_NONE = 0xFFFF

# =============================================================================
# COMPILER (RUN ON PC)
# =============================================================================

class VectorCompiler:
    def __init__(self):
        self.buffer = bytearray(b'VEC1')
        self.curr_fill = BIN_C_NONE
        self.curr_stroke = BIN_C_NONE

    def set_color(self, fill, stroke):
        # Only write if changed to save space, simple optimization
        if fill != self.curr_fill or stroke != self.curr_stroke:
            self.buffer.append(CMD_SET_COLOR)
            self.buffer.extend(struct.pack('>HH', fill & 0xFFFF, stroke & 0xFFFF))
            self.curr_fill = fill
            self.curr_stroke = stroke

    def add_rect(self, x1, y1, x2, y2, fill, stroke, border_width=1):
        self.set_color(fill, stroke)
        if border_width == 1 and stroke == BIN_C_NONE: # Standard filled rect
             # Drect takes color, not fill/stroke separarely like dpoly
             # gint drect fills. drect_border fills + outlines.
             # We map strictly to primitives.
             self.buffer.append(CMD_RECT)
             self.buffer.extend(struct.pack('>hhhh', x1, y1, x2, y2))
        else:
             # Bordered rect
             self.buffer.append(CMD_RECT_B)
             self.buffer.extend(struct.pack('>hhhhB', x1, y1, x2, y2, border_width))

    def add_circle(self, cx, cy, r, fill, stroke):
        self.set_color(fill, stroke)
        self.buffer.append(CMD_CIRCLE)
        self.buffer.extend(struct.pack('>hhh', cx, cy, r))

    def add_line(self, x1, y1, x2, y2, color):
        self.set_color(BIN_C_NONE, color) # Line uses stroke color usually
        self.buffer.append(CMD_LINE)
        self.buffer.extend(struct.pack('>hhhh', x1, y1, x2, y2))

    def add_poly(self, vertices, fill, stroke):
        """vertices: list of [x, y, x, y...]"""
        if len(vertices) // 2 > 255:
            print("Warning: Polygon too large for format (max 255 vertices)")
            return
        
        self.set_color(fill, stroke)
        self.buffer.append(CMD_POLY)
        count = len(vertices) // 2
        self.buffer.append(count)
        
        # Pack all vertices efficiently
        fmt = '>' + 'h' * len(vertices)
        self.buffer.extend(struct.pack(fmt, *vertices))

    def add_name(self, name):
         """Sets the name of the last added object."""
         if not name: return
         encoded = name.encode('utf-8')
         if len(encoded) > 255: encoded = encoded[:255]
         self.buffer.append(CMD_OBJ_NAME)
         self.buffer.append(len(encoded))
         self.buffer.extend(encoded)

    def add_viewbox(self, w, h):
         """Sets the document viewbox (width, height)."""
         self.buffer.append(CMD_VIEWBOX)
         self.buffer.extend(struct.pack('>hh', int(w), int(h)))

    def get_bytes(self):
        self.buffer.append(CMD_END)
        return bytes(self.buffer)

# =============================================================================
# DECODER_EDITOR (RUN ON DEVICE)
# =============================================================================

class VectorDecoder:
    def __init__(self, data):
        self.data = data
        self.ptr = 0
        self.objects = []
        self.viewbox = None # (w, h)
        
    def decode(self):
        if self.data[0:4] != b'VEC1' and self.data[0:4] != b'VEC2':
            return [] # Invalid header

        self.ptr = 4
        length = len(self.data)
        
        fill_col = C_NONE
        stroke_col = C_NONE
        
        while self.ptr < length:
            cmd = self.data[self.ptr]
            self.ptr += 1
            
            if cmd == CMD_END:
                break
            
            elif cmd == CMD_VIEWBOX:
                w, h = struct.unpack_from('>hh', self.data, self.ptr)
                self.ptr += 4
                self.viewbox = (w, h)
                
            elif cmd == CMD_SET_COLOR:
                f, s = struct.unpack_from('>HH', self.data, self.ptr)
                self.ptr += 4
                fill_col = C_NONE if f == 0xFFFF else f
                stroke_col = C_NONE if s == 0xFFFF else s
                
            elif cmd == CMD_RECT:
                coords = struct.unpack_from('>hhhh', self.data, self.ptr)
                self.ptr += 8
                self.objects.append({
                    'type': CMD_RECT,
                    'x1': coords[0], 'y1': coords[1],
                    'x2': coords[2], 'y2': coords[3],
                    'fill': fill_col, 'stroke': stroke_col
                })
                
            elif cmd == CMD_OBJ_NAME:
                nl = self.data[self.ptr]
                self.ptr += 1
                name_bytes = self.data[self.ptr : self.ptr+nl]
                self.ptr += nl
                if self.objects:
                    self.objects[-1]['name'] = name_bytes.decode('utf-8')

            elif cmd == CMD_RECT_B:
                x1, y1, x2, y2, bw = struct.unpack_from('>hhhhB', self.data, self.ptr)
                self.ptr += 9
                self.objects.append({
                    'type': CMD_RECT_B,
                    'x1': x1, 'y1': y1,
                    'x2': x2, 'y2': y2,
                    'width': bw,
                    'fill': fill_col, 'stroke': stroke_col
                })

            elif cmd == CMD_CIRCLE:
                cx, cy, r = struct.unpack_from('>hhh', self.data, self.ptr)
                self.ptr += 6
                self.objects.append({
                    'type': CMD_CIRCLE,
                    'cx': cx, 'cy': cy, 'r': r,
                    'fill': fill_col, 'stroke': stroke_col
                })

            elif cmd == CMD_LINE:
                coords = struct.unpack_from('>hhhh', self.data, self.ptr)
                self.ptr += 8
                self.objects.append({
                    'type': CMD_LINE,
                    'x1': coords[0], 'y1': coords[1],
                    'x2': coords[2], 'y2': coords[3],
                    'fill': fill_col, 'stroke': stroke_col
                })

            elif cmd == CMD_POLY:
                count = self.data[self.ptr]
                self.ptr += 1
                fmt = '>' + 'h' * (count * 2)
                raw_verts = struct.unpack_from(fmt, self.data, self.ptr)
                # Convert tuple to list
                vertices = list(raw_verts)
                self.ptr += count * 4
                self.objects.append({
                    'type': CMD_POLY,
                    'vertices': vertices,
                    'fill': fill_col, 'stroke': stroke_col
                })
                
        return self.objects

def get_svf_metrics(data):
    """
    Scans the SVF data for a ViewBox command.
    Returns (width, height) if found, else None.
    """
    if len(data) < 4 or (data[0:4] != b'VEC1' and data[0:4] != b'VEC2'): return None
    
    ptr = 4
    length = len(data)
    
    while ptr < length:
        cmd = data[ptr]
        ptr += 1
        
        if cmd == CMD_END: break
        elif cmd == CMD_VIEWBOX:
            return struct.unpack_from('>hh', data, ptr)
        elif cmd == CMD_SET_COLOR: ptr += 4
        elif cmd == CMD_RECT: ptr += 8
        elif cmd == CMD_RECT_B: ptr += 9
        elif cmd == CMD_CIRCLE: ptr += 6
        elif cmd == CMD_LINE: ptr += 8
        elif cmd == CMD_POLY:
             c = data[ptr]
             ptr += 1 + (c * 4)
        elif cmd == CMD_OBJ_NAME:
             nl = data[ptr]
             ptr += 1 + nl
        # Unknown commands might break this, but for now it's fine
    
    return None

# =============================================================================
# RUNTIME RENDERER (RUN ON DEVICE)
# =============================================================================

def render_vector_icon(data, x_off, y_off, scale=1.0):
    """
    Parses and draws the binary vector data.
    scale: Float multiplier (1.0 = original size)
    x_off, y_off: Position offset
    """
    if data[0:4] != b'VEC1' and data[0:4] != b'VEC2':
        return # Invalid header

    ptr = 4
    length = len(data)
    
    # State
    fill_col = C_NONE
    stroke_col = C_NONE
    
    # Helpers for int scaling
    # Assuming coordinates in binary are abstract (e.g. 0-100 range) or pixel relative
    # int() conversion is slow in tight loops? Pre-calc scale.
    
    while ptr < length:
        cmd = data[ptr]
        ptr += 1
        
        if cmd == CMD_END:
            break
        
        elif cmd == CMD_VIEWBOX:
             ptr += 4 # Skip viewbox in renderer, usage is external
            
        elif cmd == CMD_SET_COLOR:
            f, s = struct.unpack_from('>HH', data, ptr)
            ptr += 4
            fill_col = C_NONE if f == 0xFFFF else f
            stroke_col = C_NONE if s == 0xFFFF else s

        elif cmd == CMD_OBJ_NAME:
             # Skip name in renderer
             nl = data[ptr]
             ptr += 1 + nl
            
        elif cmd == CMD_RECT:
            coords = struct.unpack_from('>hhhh', data, ptr)
            ptr += 8
            # Scale & Translate
            x1 = int(coords[0] * scale) + x_off
            y1 = int(coords[1] * scale) + y_off
            x2 = int(coords[2] * scale) + x_off
            y2 = int(coords[3] * scale) + y_off
            drect(x1, y1, x2, y2, fill_col)
            
        elif cmd == CMD_RECT_B:
            x1, y1, x2, y2, bw = struct.unpack_from('>hhhhB', data, ptr)
            ptr += 9
            sx1 = int(x1 * scale) + x_off
            sy1 = int(y1 * scale) + y_off
            sx2 = int(x2 * scale) + x_off
            sy2 = int(y2 * scale) + y_off
            # Border width implies stroke color is used for border
            # drect_border(x1, y1, x2, y2, fill, border_width, border_color)
            drect_border(sx1, sy1, sx2, sy2, fill_col, bw, stroke_col)

        elif cmd == CMD_CIRCLE:
            cx, cy, r = struct.unpack_from('>hhh', data, ptr)
            ptr += 6
            scx = int(cx * scale) + x_off
            scy = int(cy * scale) + y_off
            sr = int(r * scale)
            dcircle(scx, scy, sr, fill_col, stroke_col)

        elif cmd == CMD_LINE:
            coords = struct.unpack_from('>hhhh', data, ptr)
            ptr += 8
            sx1 = int(coords[0] * scale) + x_off
            sy1 = int(coords[1] * scale) + y_off
            sx2 = int(coords[2] * scale) + x_off
            sy2 = int(coords[3] * scale) + y_off
            dline(sx1, sy1, sx2, sy2, stroke_col)

        elif cmd == CMD_POLY:
            count = data[ptr]
            ptr += 1
            # Extract vertices
            fmt = '>' + 'h' * (count * 2)
            raw_verts = struct.unpack_from(fmt, data, ptr)
            ptr += count * 4 # 2 bytes * 2 coords * count
            
            # Transform vertices
            # gint dpoly expects flat list [x,y,x,y...]
            transformed = []
            for i in range(0, len(raw_verts), 2):
                tx = int(raw_verts[i] * scale) + x_off
                ty = int(raw_verts[i+1] * scale) + y_off
                transformed.extend([tx, ty])
            
            dpoly(transformed, fill_col, stroke_col)

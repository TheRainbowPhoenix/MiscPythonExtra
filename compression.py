# Compression Library for PythonExtra
# Optimized for ClassPad (MicroPython) performance

# =============================================================================
# LZ77 (Sliding Window) 
# Best for 200KB Markdown text. Low memory footprint, blazing fast decompression.
# =============================================================================

def lz77_compress(data: bytes) -> bytes:
    """
    Compresses using an adapted text-optimized LZ77 algorithm.
    Excellent for Markdown and ASCII text.
    """
    out = bytearray()
    space = 0
    sstart = 0
    i = 0
    imax = len(data)
    
    while i < imax:
        if (i - sstart) > 2047: 
            sstart = i - 2047
            
        e = 3
        ns = sstart
        ts = data[i:i+e]
        
        while (imax - i) >= e and e <= 10:
            f = data.find(ts, ns, i)
            if f < 0: 
                break
            e += 1
            ts = data[i:i+e]
            ns = f
        e -= 1
        
        if e >= 3:
            dist = i - ns
            byte_val = (dist << 3) | (e - 3)
            if space:
                out.append(32)
                space = 0
            out.append(0x80 | (byte_val >> 8))
            out.append(byte_val & 0xff)
            i += e
        else:
            c = data[i]
            i += 1
            if space:
                if 0x40 <= c <= 0x7f: 
                    out.append(c | 0x80)
                else:
                    out.append(32)
                    if c < 0x80 and (c == 0 or c > 8):
                        out.append(c)
                    else:
                        out.append(1)
                        out.append(c)
                space = 0
            else:
                if c == 32: 
                    space = 1
                else:
                    if c < 0x80 and (c == 0 or c > 8):
                        out.append(c)
                    else:
                        out.append(1)
                        out.append(c)
                        
    if space: 
        out.append(32)
        
    return bytes(out)

def lz77_decompress(data: bytes) -> bytes:
    """Decompresses LZ77 packed bytes (text-optimized)."""
    x = 0
    o = bytearray()
    n_data = len(data)
    
    while x < n_data:
        c = data[x]
        x += 1
        if 0 < c < 9:  
            for _ in range(c):
                if x < n_data:
                    o.append(data[x])
                    x += 1
        elif c < 128: 
            o.append(c)
        elif c >= 0xc0: 
            o.append(32)
            o.append(c & 0x7f)
        else: 
            if x < n_data:
                c2 = data[x]
                x += 1
                val = ((c & 0x3f) << 8) | c2
                m = val >> 3
                n = (val & 7) + 3
                start = len(o) - m
                if start < 0: start = 0
                for _ in range(n):
                    o.append(o[start])
                    start += 1
                    
    return bytes(o)

# =============================================================================
# LZW (Lempel-Ziv-Welch)
# =============================================================================

def lzw_compress(data: bytes) -> list:
    if not data: 
        return []
    
    dict_size = 256
    dictionary = {bytes([i]): i for i in range(dict_size)}
    
    w = bytes()
    compressed_data = []
    
    # Iterating over 'bytes' yields integers directly
    for b in data:
        c = bytes([b])
        wc = w + c
        if wc in dictionary:
            w = wc
        else:
            compressed_data.append(dictionary[w])
            dictionary[wc] = dict_size
            dict_size += 1
            w = c
            
    if w: 
        compressed_data.append(dictionary[w])
        
    return compressed_data

def lzw_decompress(compressed_data: list) -> bytes:
    if not compressed_data: return b""
    dict_size = 256
    dictionary = {i: bytes([i]) for i in range(dict_size)}
    w = dictionary[compressed_data[0]]
    result = [w]
    for k in compressed_data[1:]:
        if k in dictionary: entry = dictionary[k]
        elif k == dict_size: entry = w + w[:1]
        else: raise ValueError("Bad code")
        result.append(entry)
        dictionary[dict_size] = w + entry[:1]
        dict_size += 1
        w = entry
    return b"".join(result)

# =============================================================================
# RLE (Run-Length Encoding)
# =============================================================================

def rle_compress(data: bytes) -> bytes:
    if not data: return b""
    res = bytearray()
    mv = memoryview(data)
    n = len(mv)
    i = 0
    while i < n:
        count = 1
        char = mv[i]
        while i + count < n and mv[i + count] == char and count < 255:
            count += 1
        res.append(char)
        res.append(count)
        i += count
    return bytes(res)

def rle_decompress(data: bytes) -> bytes:
    if not data: return b""
    res = bytearray()
    mv = memoryview(data)
    for i in range(0, len(mv), 2):
        res.extend(bytes([mv[i]]) * mv[i+1])
    return bytes(res)
# LZW Library for PythonExtra - Optimized with memoryview

def compress(data: bytes) -> list:
    """Compresses a sequence of bytes using the LZW algorithm."""
    if not data:
        return []

    # memoryview allows slicing without copying bytes
    mv = memoryview(data)
    
    dict_size = 256
    dictionary = {bytes([i]): i for i in range(dict_size)}
    
    w = bytes()
    compressed_data = []
    
    for i in range(len(mv)):
        c = mv[i:i+1].tobytes() # Need bytes for dict key
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

def decompress(compressed_data: list) -> bytes:
    """Decompresses a list of LZW integer codes back into bytes."""
    if not compressed_data:
        return b""

    dict_size = 256
    # Pre-filling the dictionary with 256 byte objects
    dictionary = {i: bytes([i]) for i in range(dict_size)}
    
    w = dictionary[compressed_data[0]]
    result = [w]
    
    for k in compressed_data[1:]:
        if k in dictionary:
            entry = dictionary[k]
        elif k == dict_size:
            entry = w + w[:1]
        else:
            raise ValueError("Bad compressed code")
            
        result.append(entry)
        dictionary[dict_size] = w + entry[:1]
        dict_size += 1
        w = entry
        
    return b"".join(result)
# MOBI & PalmDB Parser for PythonExtra
from struct import unpack, calcsize
from compression import lz77_decompress as uncompress

def LOG(*args):
    pass # Silent by default to save I/O time

# Compacted Language Map
LANGUAGES = {
    0: {0: ('n/a', 'n/a')},
    1: {0: ('ar', 'Arabic'), 4: ('sa', 'Saudi Arabia'), 12: ('eg', 'Egypt'), 20: ('dz', 'Algeria'), 24: ('ma', 'Morocco'), 28: ('tn', 'Tunisia'), 32: ('om', 'Oman'), 36: ('ye', 'Yemen'), 40: ('sy', 'Syria'), 44: ('jo', 'Jordan'), 48: ('lb', 'Lebanon'), 52: ('kw', 'Kuwait'), 56: ('ae', 'United Arab Emirates'), 60: ('bh', 'Bahrain'), 64: ('qa', 'Qatar')},
    2: {0: ('bg', 'Bulgarian')}, 3: {0: ('ca', 'Catalan')},
    4: {0: ('zh', 'Chinese'), 4: ('tw', 'Taiwan'), 8: ('cn', 'PRC'), 12: ('hk', 'Hong Kong'), 16: ('sg', 'Singapore')},
    5: {0: ('cs', 'Czech')}, 6: {0: ('da', 'Danish')},
    7: {0: ('de', 'German'), 8: ('ch', 'Switzerland'), 12: ('at', 'Austria'), 16: ('lu', 'Luxembourg'), 20: ('li', 'Liechtenstein')},
    8: {0: ('el', 'Greek')},
    9: {0: ('en', 'English'), 4: ('us', 'United States'), 8: ('gb', 'United Kingdom'), 12: ('au', 'Australia'), 16: ('ca', 'Canada'), 20: ('nz', 'New Zealand'), 24: ('ie', 'Ireland'), 28: ('za', 'South Africa'), 32: ('jm', 'Jamaica'), 40: ('bz', 'Belize'), 44: ('tt', 'Trinidad'), 48: ('zw', 'Zimbabwe'), 52: ('ph', 'Philippines')},
    10: {0: ('es', 'Spanish'), 4: ('es', 'Spain'), 8: ('mx', 'Mexico'), 16: ('gt', 'Guatemala'), 20: ('cr', 'Costa Rica'), 24: ('pa', 'Panama'), 28: ('do', 'Dominican Republic'), 32: ('ve', 'Venezuela'), 36: ('co', 'Colombia'), 40: ('pe', 'Peru'), 44: ('ar', 'Argentina'), 48: ('ec', 'Ecuador'), 52: ('cl', 'Chile'), 56: ('uy', 'Uruguay'), 60: ('py', 'Paraguay'), 64: ('bo', 'Bolivia'), 68: ('sv', 'El Salvador'), 72: ('hn', 'Honduras'), 76: ('ni', 'Nicaragua'), 80: ('pr', 'Puerto Rico')},
    11: {0: ('fi', 'Finnish')},
    12: {0: ('fr', 'French'), 4: ('fr', 'France'), 8: ('be', 'Belgium'), 12: ('ca', 'Canada'), 16: ('ch', 'Switzerland'), 20: ('lu', 'Luxembourg'), 24: ('mc', 'Monaco')},
    16: {0: ('it', 'Italian'), 4: ('it', 'Italy'), 8: ('ch', 'Switzerland')},
    17: {0: ('ja', 'Japanese')}, 18: {0: ('ko', 'Korean')}, 19: {0: ('nl', 'Dutch'), 8: ('be', 'Belgium')},
    20: {0: ('no', 'Norwegian'), 4: ('nb', 'Norwegian Bokmaal')},
    21: {0: ('pl', 'Polish')}, 22: {0: ('pt', 'Portuguese'), 4: ('br', 'Brazil'), 8: ('pt', 'Portugal')},
    25: {0: ('ru', 'Russian')}, 29: {0: ('sv', 'Swedish'), 8: ('fi', 'Finland')},
}

MOBI_HDR_FIELDS = (
    ("id", 16, "4s"), ("header_len", 20, "I"), ("mobi_type", 24, "I"), ("encoding", 28, "I"),
    ("UID", 32, "I"), ("generator_version", 36, "I"), ("first_nonbook_idx", 80, "I"),
    ("full_name_offs", 84, "I"), ("full_name_len", 88, "I"), ("locale_highbytes", 92, "H"),
    ("locale_country", 94, "B"), ("locale_language", 95, "B"), ("input_lang", 96, "I"),
    ("output_lang", 100, "I"), ("format_version", 104, "I"), ("first_image_idx", 108, "I"),
    ("exth_flags", 128, "I"), ("drm_offs", 168, "I"), ("drm_count", 172, "I"),
    ("drm_size", 176, "I"), ("drm_flags", 180, "I")
)

EXTH_FMT = ">4x2I"

EXTH_RECORD_TYPES = {
    100: 'author', 101: 'publisher', 103: 'description', 104: 'isbn', 
    105: 'subject', 106: 'publication date', 113: 'asin', 503: 'updated title'
}

class PalmDB:
    def __init__(self, filename):
        self.filename = filename
        with open(filename, 'rb') as f:
            header = f.read(78)
            self.name = header[:32].split(b'\x00')[0].decode('ascii', 'ignore')
            
            f.seek(76)
            self.record_count = unpack('>H', f.read(2))[0]
            self.record_offsets = []
            
            for _ in range(self.record_count):
                offset = unpack('>I', f.read(4))[0]
                f.read(4) # skip attributes and unique ID
                self.record_offsets.append(offset)
                
    def get_record(self, index):
        if index >= self.record_count: return b""
        with open(self.filename, 'rb') as f:
            start = self.record_offsets[index]
            f.seek(start)
            if index + 1 < self.record_count:
                return f.read(self.record_offsets[index+1] - start)
            else:
                return f.read()

def parse_exth(data, pos):
    ret = {}
    if data.find(b'EXTH', pos) != pos:
        return None
    
    end = pos + calcsize(EXTH_FMT)
    hlen, count = unpack(EXTH_FMT, data[pos:end])
    pos = end
    
    for _ in range(count):
        end = pos + 8
        if end > len(data): break
        
        t, l = unpack(">2I", data[pos:end])
        v = data[end:pos + l]
        
        # Only unpack as Int if it's NOT a known text type to avoid TypeError
        if l - 8 == 4 and t not in EXTH_RECORD_TYPES:
            try:
                v = unpack(">I", v)[0]
            except Exception:
                v = v.decode('utf-8', 'ignore')
        else:
            v = v.decode('utf-8', 'ignore')
            
        if t in EXTH_RECORD_TYPES:
            rec = EXTH_RECORD_TYPES[t]
            if rec not in ret: ret[rec] = [v]
            else: ret[rec].append(v)
            
        pos += l
    return ret

class Book:
    def __init__(self, fn):
        self.filename = fn
        self.title = "Unknown"
        self.author = "Unknown"
        self.language = "Unknown"
        self.is_a_book = False
        
        try:
            with open(fn, 'rb') as f:
                d = f.read(78)
                self.type = d[60:68].decode('ascii', 'ignore')
        except OSError:
            return

        if self.type not in ('BOOKMOBI', 'TEXtREAd'):
            return

        self.db = PalmDB(fn)
        self.is_a_book = True
        self.title = self.db.name
        
        rec0 = self.db.get_record(0)
        
        if self.type == 'BOOKMOBI':
            self.mobi = {}
            for field, pos, fmt in MOBI_HDR_FIELDS:
                end = pos + calcsize(">" + fmt)
                if end > len(rec0): continue
                (self.mobi[field],) = unpack(">" + fmt, rec0[pos:end])

            lang_id = self.mobi.get('locale_language', 0)
            if lang_id in LANGUAGES:
                country_id = self.mobi.get('locale_country', 0)
                lang_data = LANGUAGES[lang_id]
                if country_id in lang_data:
                    self.language = lang_data[country_id][1]
                else:
                    self.language = lang_data.get(0, ('', 'Unknown'))[1]

            pos = self.mobi.get('full_name_offs', 0)
            end = pos + self.mobi.get('full_name_len', 0)
            if pos and end <= len(rec0):
                encoding = 'utf-8' if self.mobi.get('encoding') == 65001 else 'cp1252'
                self.title = rec0[pos:end].decode(encoding, 'ignore')

            if (0x40 & self.mobi.get('exth_flags', 0)):
                self.exth = parse_exth(rec0, self.mobi.get('header_len', 0) + 16)
                if self.exth:
                    if 'author' in self.exth:
                        self.author = ' & '.join(self.exth['author'])
                    if 'updated title' in self.exth:
                        self.title = ' '.join(self.exth['updated title'])

    def get_chapter_text(self, record_index):
        """Yields text for a specific record. Safely ignores binary records."""
        if not self.is_a_book or 'mobi' not in self.__dict__:
            return ""
            
        if record_index < 1 or record_index >= self.mobi.get('first_image_idx', 1):
            return ""
            
        raw_data = self.db.get_record(record_index)
        if not raw_data: return ""
        
        # Avoid crashing on structural or media tags
        if raw_data.startswith(b'INDX') or raw_data.startswith(b'FLIS') or \
           raw_data.startswith(b'FCIS') or raw_data.startswith(b'SRCS') or \
           raw_data.startswith(b'BOUNDARY') or raw_data.startswith(b'FDST'):
            return ""
            
        try:
            decompressed = uncompress(raw_data)
        except Exception:
            # Safely skip index errors during corrupt decompression
            return ""
        
        # Simple HTML tag stripper
        res = bytearray()
        in_tag = False
        for b in decompressed:
            if b == 60: in_tag = True       # '<'
            elif b == 62: in_tag = False    # '>'
            elif not in_tag: res.append(b)
            
        return res.decode('utf-8', 'ignore').replace('&nbsp;', ' ')

// Constants matching fxconv.py
const FX_BLACK = 0; // We'll map black to 0, white to 1 (or based on threshold)
// Actually in fxconv.py: FX_BLACK = (0,0,0,255).
// The bit packing logic: color = (px[x,y] == FX_BLACK). So 1 if black.

const FX_CHARSETS = {
    "numeric":  [[0x30, 10]],
    "upper":    [[0x41, 26]],
    "alpha":    [[0x41, 26], [0x61, 26]],
    "alnum":    [[0x41, 26], [0x61, 26], [0x30, 10]],
    "print":    [[0x20, 95]],
    "ascii":    [[0x00, 128]],
    "unicode":  [],
    "256chars": [[0x00, 256]],
};

class Area {
    constructor(area, imgWidth, imgHeight) {
        this.x = parseInt(area.x || 0);
        this.y = parseInt(area.y || 0);
        this.w = parseInt(area.width || imgWidth);
        this.h = parseInt(area.height || imgHeight);

        if (area.size) {
            const parts = area.size.split('x').map(Number);
            this.w = parts[0];
            this.h = parts[1];
        }
    }
}

class Grid {
    constructor(grid) {
        this.border = parseInt(grid.border || 0);
        this.padding = parseInt(grid.padding || 0);
        this.w = parseInt(grid.width || -1);
        this.h = parseInt(grid.height || -1);

        if (grid.size) {
            const parts = grid.size.split('x').map(Number);
            this.w = parts[0];
            this.h = parts[1];
        }

        if (this.w <= 0 || this.h <= 0) {
            throw new Error("size of grid unspecified or invalid");
        }
    }

    size(imgWidth, imgHeight) {
        const b = this.border;
        const p = this.padding;
        const w = this.w;
        const h = this.h;
        const W = w + 2 * p;
        const H = h + 2 * p;
        const columns = Math.floor((imgWidth - b) / (W + b));
        const rows = Math.floor((imgHeight - b) / (H + b));
        return columns * rows;
    }

    *iter(imgWidth, imgHeight) {
        const b = this.border;
        const p = this.padding;
        const w = this.w;
        const h = this.h;
        const W = w + 2 * p;
        const H = h + 2 * p;
        const columns = Math.floor((imgWidth - b) / (W + b));
        const rows = Math.floor((imgHeight - b) / (H + b));

        for (let r = 0; r < rows; r++) {
            for (let c = 0; c < columns; c++) {
                const x = b + c * (W + b) + p;
                const y = b + r * (H + b) + p;
                yield { x, y, w, h };
            }
        }
    }
}

function trim(img, width, height) {
    // Determine bounds of non-white pixels
    // fxconv.py: blank(x) returns true if all pixels in column x are WHITE.

    let left = 0;
    let right = width;

    const isColumnBlank = (x) => {
        for (let y = 0; y < height; y++) {
            if (!img.isWhite(x, y)) return false;
        }
        return true;
    };

    while (left + 1 < right && isColumnBlank(left)) {
        left++;
    }
    while (right - 1 > left && isColumnBlank(right - 1)) {
        right--;
    }

    return { x: left, w: right - left }; // Relative to image origin (0,0)
}


function convert_topti(imageWrapper, params) {
    // 1. Charset
    if (!params.charset) {
        throw new Error("'charset' attribute is required and missing");
    }
    const charsetName = params.charset;
    const blocks = FX_CHARSETS[charsetName];
    if (!blocks) {
        throw new Error(`unknown character set '${charsetName}'`);
    }

    // Calculate total glyph count from blocks
    const glyphCount = blocks.reduce((acc, [start, len]) => acc + len, 0);

    // 2. Grid & Area
    const grid = new Grid(params.grid || {});
    const area = new Area(params.area || {}, imageWrapper.width, imageWrapper.height);

    // Crop imageWrapper concept (logical crop)
    const croppedImage = {
        width: area.w,
        height: area.h,
        isBlack: (x, y) => imageWrapper.isBlack(area.x + x, area.y + y),
        isWhite: (x, y) => imageWrapper.isWhite(area.x + x, area.y + y)
    };

    // Check grid size
    const gridSize = grid.size(croppedImage.width, croppedImage.height);
    if (glyphCount > gridSize) {
        throw new Error(`not enough elements in grid (got ${gridSize}, need ${glyphCount} for '${charsetName}')`);
    }

    // 3. Proportionality & Flags
    const proportional = (params.proportional === 'true' || params.proportional === true);

    // Flags
    const flagsList = (params.flags || "").split(',').filter(f => f);
    const validFlags = new Set(["bold", "italic", "serif", "mono"]);
    let bold = 0, italic = 0, serif = 0, mono = 0;

    for (const f of flagsList) {
        if (!validFlags.has(f)) throw new Error(`unknown flag: ${f}`);
        if (f === 'bold') bold = 1;
        if (f === 'italic') italic = 1;
        if (f === 'serif') serif = 1;
        if (f === 'mono') mono = 1;
    }

    const flags = (bold << 7) | (italic << 6) | (serif << 5) | (mono << 4) | (proportional ? 1 : 0);

    // Metrics
    const lineHeight = parseInt(params.height || grid.h);
    const charSpacing = parseInt(params['char-spacing'] || 1);
    const lineDistance = parseInt(params['line-distance'] || (lineHeight + 1));

    // 4. Encode Blocks
    // data_blocks = b''.join(encode_block(b) for b in blocks)
    // encode_block(b): u32((start << 12) | length)
    // JS equivalent of struct.pack('>I', val) or similar?
    // fxconv.py uses u32(val) which is big-endian bytes I presume?
    // Let's check u32 definition in fxconv.py:
    // def u32(x): return bytes([ (x >> 24) & 255, (x >> 16) & 255, (x >> 8) & 255, x & 255 ])
    // Yes, Big Endian.

    const u32 = (x) => [ (x >>> 24) & 0xFF, (x >>> 16) & 0xFF, (x >>> 8) & 0xFF, x & 0xFF ];
    const u16 = (x) => [ (x >>> 8) & 0xFF, x & 0xFF ];

    let dataBlocks = [];
    for (const [start, length] of blocks) {
        dataBlocks.push(...u32((start << 12) | length));
    }

    // 5. Encode Glyphs
    let dataGlyphs = [];
    let dataWidth = []; // for proportional
    let dataIndex = []; // for proportional

    let totalGlyphsBytes = 0; // Length in bytes of dataGlyphs so far

    let glyphIndex = 0; // Current glyph index being processed

    // Iterate grid
    const iter = grid.iter(croppedImage.width, croppedImage.height);

    for (const region of iter) {
        // if (glyphIndex >= glyphCount) break; // fxconv.py processes all grid cells regardless of charset count

        // Update index (every 8 glyphs)?
        // fxconv.py: if not (number % 8): idx = total_glyphs // 4; data_index += u16(idx)
        // number is the enumeration of grid.iter

        if (glyphIndex % 8 === 0) {
            // Index points to 32-bit words, so byte offset / 4
            const idx = Math.floor(dataGlyphs.length / 4);
            dataIndex.push(...u16(idx));
        }

        // Extract glyph
        // Logical crop of the region from the croppedImage
        let glyphX = region.x;
        let glyphY = region.y;
        let glyphW = region.w;
        let glyphH = region.h;

        // If proportional, trim
        if (proportional) {
            // Need a sub-image for trim function
            const cellImage = {
                width: glyphW,
                height: glyphH,
                isBlack: (x, y) => croppedImage.isBlack(glyphX + x, glyphY + y),
                isWhite: (x, y) => croppedImage.isWhite(glyphX + x, glyphY + y)
            };
            const trimRect = trim(cellImage, glyphW, glyphH);
            // Update glyph region to trimmed
            glyphX += trimRect.x;
            glyphW = trimRect.w;

            dataWidth.push(glyphW);
        }

        // Encode bitmap
        // storage_size = ((glyph.width * glyph.height + 31) >> 5)
        // length = 4 * storage_size
        const storageSize = (glyphW * glyphH + 31) >>> 5;
        const length = 4 * storageSize;
        const bits = new Uint8Array(length);
        let offset = 0;

        for (let y = 0; y < glyphH; y++) {
            for (let x = 0; x < glyphW; x++) {
                // croppedImage coordinates
                const isBlack = croppedImage.isBlack(glyphX + x, glyphY + y);
                if (isBlack) {
                    // bits[offset >> 3] |= ((color * 0x80) >> (offset & 7))
                    // color is 1
                    bits[offset >> 3] |= (0x80 >>> (offset & 7));
                }
                offset++;
            }
        }

        for (let b of bits) {
            dataGlyphs.push(b);
        }

        glyphIndex++;
    }

    // Fill remaining if needed? No, logic breaks when glyphCount reached.

    // 6. Generate Python Output

    // Helper to format bytes
    const formatBytes = (arr) => {
        // Use python repr() style: b'...'
        // printable ascii characters can be used directly, others \xNN
        let s = "b'";
        for (const b of arr) {
            if (b >= 32 && b <= 126 && b !== 39 && b !== 92) { // 39 is ', 92 is \
                s += String.fromCharCode(b);
            } else if (b === 39) {
                s += "\\'";
            } else if (b === 92) {
                s += "\\\\";
            } else {
                s += "\\x" + b.toString(16).padStart(2, '0');
            }
        }
        s += "'";
        return s;
    };

    let output = "import gint\n";
    output += `${params.name} = gint.font(${flags}, `;
    output += `${lineHeight}, ${grid.h}, ${blocks.length}, ${glyphCount}, `;
    output += `${charSpacing}, ${lineDistance}, `;
    output += `${formatBytes(dataBlocks)}, `;
    output += `${formatBytes(dataGlyphs)}`;

    if (proportional) {
        output += `, 0, 0, `; // width, storage_size (ignored)
        output += `${formatBytes(dataIndex)}, ${formatBytes(dataWidth)}`;
    } else {
        const storageSize = (grid.w * grid.h + 31) >>> 5;
        output += `, ${grid.w}, ${storageSize}, `;
        output += `None, None`;
    }
    output += ")\n";

    return output;
}


if (typeof module !== 'undefined' && module.exports) {
    module.exports = { convert_topti, Grid, Area, FX_CHARSETS };
} else {
    window.fxconv = { convert_topti, Grid, Area, FX_CHARSETS };
}

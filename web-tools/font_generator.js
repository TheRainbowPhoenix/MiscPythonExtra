
// We rely on fxconv_core.js for FX_CHARSETS

async function generateFontAtlas(fontFile, fontSize, charsetName, padding = 0, threshold = 128) {
    if (!fontFile) {
        throw new Error("No font file provided.");
    }

    // Load Font
    const buffer = await fontFile.arrayBuffer();
    const fontName = 'customFont_' + Date.now();
    const fontFace = new FontFace(fontName, buffer);
    await fontFace.load();
    document.fonts.add(fontFace);

    const fontStr = `${fontSize}px ${fontName}`;

    // Get Characters
    const blocks = window.fxconv.FX_CHARSETS[charsetName];
    if (!blocks) throw new Error(`Unknown charset: ${charsetName}`);

    let chars = [];
    for (const [start, length] of blocks) {
        for (let i = 0; i < length; i++) {
            chars.push(String.fromCharCode(start + i));
        }
    }

    // Measure Max Dimensions
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    ctx.font = fontStr;

    let maxW = 0;
    let maxH = 0;

    // First pass measurement
    let maxAscent = 0;
    let maxDescent = 0;
    let maxLeft = 0;
    let maxRight = 0;

    for (const char of chars) {
        const metrics = ctx.measureText(char);

        const ascent = metrics.actualBoundingBoxAscent || fontSize;
        const descent = metrics.actualBoundingBoxDescent || 0;
        const left = metrics.actualBoundingBoxLeft || 0;
        const right = metrics.actualBoundingBoxRight || metrics.width;

        if (ascent > maxAscent) maxAscent = Math.ceil(ascent);
        if (descent > maxDescent) maxDescent = Math.ceil(descent);
        if (left > maxLeft) maxLeft = Math.ceil(left);
        if (right > maxRight) maxRight = Math.ceil(right);
    }

    // Cell size must accommodate the largest glyph extensions
    // For consistent baseline, we reserve space for maxAscent and maxDescent
    // For horizontal, maxLeft + maxRight.

    let contentW = maxLeft + maxRight;
    let contentH = maxAscent + maxDescent;

    // Add padding
    contentW += padding * 2;
    contentH += padding * 2;

    // Ensure at least 1px
    if (contentW < 1) contentW = 1;
    if (contentH < 1) contentH = 1;

    const cellW = contentW;
    const cellH = contentH;

    // Calculate Grid Layout
    const count = chars.length;
    // Aim for roughly square texture
    const side = Math.ceil(Math.sqrt(count));
    const cols = side;
    const rows = Math.ceil(count / cols);

    canvas.width = cols * cellW;
    canvas.height = rows * cellH;

    // Fill White (Background)
    ctx.fillStyle = 'white';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Draw Text (Black)
    ctx.fillStyle = 'black';
    ctx.font = fontStr;
    // Align using alphabetic baseline to ensure consistent vertical alignment
    ctx.textBaseline = 'alphabetic';
    ctx.textAlign = 'left';

    for (let i = 0; i < count; i++) {
        const char = chars[i];
        const col = i % cols;
        const row = Math.floor(i / cols);

        // Origin of the cell
        const cellX = col * cellW;
        const cellY = row * cellH;

        // Drawing position:
        // X: cellX + padding + maxLeft (to accommodate left bearing)
        // Y: cellY + padding + maxAscent (to put baseline below ascent)

        const x = cellX + padding + maxLeft;
        const y = cellY + padding + maxAscent;

        ctx.fillText(char, x, y);
    }

    // Thresholding (Black & White)
    const imgData = ctx.getImageData(0, 0, canvas.width, canvas.height);
    const data = imgData.data;
    for (let i = 0; i < data.length; i += 4) {
        const r = data[i];
        const g = data[i+1];
        const b = data[i+2];
        const avg = (r + g + b) / 3;
        // The font rendering is black text on white background.
        // So pixels with LOW average are black (text).
        // If avg < threshold, it becomes black (0). Else white (255).
        const val = avg < threshold ? 0 : 255;
        data[i] = val;
        data[i+1] = val;
        data[i+2] = val;
        // Alpha is already 255 usually, keep it.
    }
    ctx.putImageData(imgData, 0, 0);

    return {
        canvas: canvas,
        grid: {
            width: cellW,
            height: cellH,
            padding: 0, // We baked padding into cellW/H
            border: 0,
            size: `${cellW}x${cellH}`
        }
    };
}

// Attach to window
window.generateFontAtlas = generateFontAtlas;

async function generateUnicodeData(fontFile, fontSize, padding = 0, threshold = 128) {
    if (!fontFile) {
        throw new Error("No font file provided.");
    }

    // Load Font
    const buffer = await fontFile.arrayBuffer();
    const fontName = 'customFont_Uni_' + Date.now();
    const fontFace = new FontFace(fontName, buffer);
    await fontFace.load();
    document.fonts.add(fontFace);

    const fontStr = `${fontSize}px ${fontName}`;
    const ctx = document.createElement('canvas').getContext('2d');
    ctx.font = fontStr;

    // Scan Unicode Blocks
    // We can define standard blocks or just scan chunks.
    // Scanning 65536 chars might be slow but doable.
    // Let's optimize: Check if blocks have ANY visible glyphs.

    // Simplified block list (Basic Multilingual Plane parts)
    // 0x0000 - 0x007F : Basic Latin
    // 0x0080 - 0x00FF : Latin-1 Supplement
    // ...
    // Let's iterate in 256-char blocks? fxconv uses arbitrary block starts but usually aligned.

    const CHUNK_SIZE = 256;
    const MAX_CHAR = 0xFFFF; // Limit to BMP for now

    const results = [];

    // Pre-calculate global metrics to ensure uniform grid across blocks?
    // Or can blocks have different grids?
    // fxconv format: one grid height for the whole font.
    // So we need ONE grid size for ALL blocks.

    let maxAscent = 0;
    let maxDescent = 0;
    let maxLeft = 0;
    let maxRight = 0;

    // We need to know which chars exist.
    // width > 0 is a proxy.
    const populatedChars = new Set();

    for (let c = 0; c <= MAX_CHAR; c++) {
        // Skip control chars? 0-31?
        if (c < 32 && c !== 0) continue; // Keep 0 maybe? No.

        const char = String.fromCharCode(c);
        const metrics = ctx.measureText(char);

        // Filter empty glyphs
        // If width is 0, likely missing.
        // Some fonts return width for missing glyphs (notdef).
        // It's hard to detect perfectly without canvas inspection.
        // Let's assume width > 0 means something.

        if (metrics.width > 0) {
            populatedChars.add(c);

            const ascent = metrics.actualBoundingBoxAscent || fontSize;
            const descent = metrics.actualBoundingBoxDescent || 0;
            const left = metrics.actualBoundingBoxLeft || 0;
            const right = metrics.actualBoundingBoxRight || metrics.width;

            if (ascent > maxAscent) maxAscent = Math.ceil(ascent);
            if (descent > maxDescent) maxDescent = Math.ceil(descent);
            if (left > maxLeft) maxLeft = Math.ceil(left);
            if (right > maxRight) maxRight = Math.ceil(right);
        }
    }

    // Calculate global cell size
    let contentW = maxLeft + maxRight;
    let contentH = maxAscent + maxDescent;
    contentW += padding * 2;
    contentH += padding * 2;
    if (contentW < 1) contentW = 1;
    if (contentH < 1) contentH = 1;

    // Ensure even
    if (contentW % 2 !== 0) contentW++;
    if (contentH % 2 !== 0) contentH++;

    const cellW = contentW;
    const cellH = contentH;

    const commonGrid = {
        width: cellW,
        height: cellH,
        padding: 0,
        border: 0,
        size: `${cellW}x${cellH}`
    };

    // Generate Blocks
    for (let start = 0; start <= MAX_CHAR; start += CHUNK_SIZE) {
        const blockChars = [];
        for (let i = 0; i < CHUNK_SIZE; i++) {
            if (populatedChars.has(start + i)) {
                blockChars.push(String.fromCharCode(start + i));
            }
        }

        if (blockChars.length === 0) continue;

        // Check if this block is worth keeping (e.g. if it's just one weird char?)
        // Let's keep it if > 0.

        // We need to generate a grid for EXACTLY CHUNK_SIZE chars?
        // No, fxconv blocks are (start, length).
        // But if we have gaps? fxconv doesn't support gaps INSIDE a block easily
        // unless we map them to empty space in the grid.
        // Actually fxconv blocks are: "Code points from Start to Start+Length map to consecutive glyphs in the font data".
        // So if we have chars 65, 66, 68... skipping 67...
        // We can make two blocks: [65, 2], [68, 1].
        // Or one block [65, 4] with 67 being empty.
        // Usually fonts cover ranges.
        // Let's try to identify contiguous ranges from `populatedChars`.

        // Find ranges in this chunk? Or globally?
        // Let's do it globally.
    }

    const sortedChars = Array.from(populatedChars).sort((a, b) => a - b);
    if (sortedChars.length === 0) throw new Error("No characters found in font.");

    let ranges = [];
    let currentRange = { start: sortedChars[0], end: sortedChars[0] };

    for (let i = 1; i < sortedChars.length; i++) {
        const code = sortedChars[i];
        if (code === currentRange.end + 1) {
            currentRange.end = code;
        } else {
            ranges.push(currentRange);
            currentRange = { start: code, end: code };
        }
    }
    ranges.push(currentRange);

    // Optimization: Merge small gaps?
    // If gap is small (< 16 chars?), it's cheaper to include empty glyphs than overhead of new block?
    // Let's stick to strict ranges for now.

    // Generate images for ranges
    const output = [];

    for (const range of ranges) {
        const count = range.end - range.start + 1;
        const chars = [];
        for (let i = 0; i < count; i++) chars.push(String.fromCharCode(range.start + i));

        const cvs = document.createElement('canvas');
        const side = Math.ceil(Math.sqrt(count));
        const cols = side;
        const rows = Math.ceil(count / cols);

        cvs.width = cols * cellW;
        cvs.height = rows * cellH;

        const cCtx = cvs.getContext('2d');
        cCtx.fillStyle = 'white';
        cCtx.fillRect(0, 0, cvs.width, cvs.height);

        cCtx.fillStyle = 'black';
        cCtx.font = fontStr;
        cCtx.textBaseline = 'alphabetic';
        cCtx.textAlign = 'left';

        for (let i = 0; i < count; i++) {
            const char = chars[i];
            const col = i % cols;
            const row = Math.floor(i / cols);

            const x = col * cellW + padding + maxLeft;
            const y = row * cellH + padding + maxAscent;

            cCtx.fillText(char, x, y);
        }

        // Threshold
        const idata = cCtx.getImageData(0, 0, cvs.width, cvs.height);
        const d = idata.data;
        for (let i = 0; i < d.length; i+=4) {
            const avg = (d[i] + d[i+1] + d[i+2]) / 3;
            const val = avg < threshold ? 0 : 255;
            d[i] = val;
            d[i+1] = val;
            d[i+2] = val;
        }
        cCtx.putImageData(idata, 0, 0);

        output.push({
            start: range.start,
            canvas: cvs,
            grid: commonGrid,
            // Pre-calculate image data for wrapper?
            data: idata.data
        });
    }

    return output;
}

window.generateUnicodeData = generateUnicodeData;

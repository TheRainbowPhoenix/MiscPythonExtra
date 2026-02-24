
// We rely on fxconv_core.js for FX_CHARSETS

async function generateFontAtlas(fontFile, fontSize, charsetName, padding = 0) {
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
    for (const char of chars) {
        const metrics = ctx.measureText(char);
        const w = Math.ceil(metrics.width);
        let h = fontSize;
        // Use actualBoundingBoxAscent/Descent if available for tighter bounds
        if (metrics.actualBoundingBoxAscent && metrics.actualBoundingBoxDescent) {
             h = Math.ceil(metrics.actualBoundingBoxAscent + metrics.actualBoundingBoxDescent);
        }

        if (w > maxW) maxW = w;
        if (h > maxH) maxH = h;
    }

    // Ensure even width/height? Not strictly necessary but safer for some grids
    if (maxW % 2 !== 0) maxW++;
    if (maxH % 2 !== 0) maxH++;

    // Force square cell if padding not specified? Or just use bounding box.
    // Use the max bounding box as the cell size.

    const cellW = maxW + (padding * 2);
    const cellH = maxH + (padding * 2);

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
    ctx.textBaseline = 'middle';
    ctx.textAlign = 'center';

    for (let i = 0; i < count; i++) {
        const char = chars[i];
        const col = i % cols;
        const row = Math.floor(i / cols);

        const x = col * cellW + cellW / 2;
        const y = row * cellH + cellH / 2;

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
        const val = avg < 128 ? 0 : 255;
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

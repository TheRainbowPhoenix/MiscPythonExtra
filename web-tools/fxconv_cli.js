const fs = require('fs');
const { PNG } = require('pngjs');
const { convert_topti } = require('./fxconv_core.js');

function parseArgs(args) {
    const params = {};
    let inputFile = null;
    let outputFile = null;

    let i = 0;
    while (i < args.length) {
        const arg = args[i];

        if (arg === '-o' || arg === '--output') {
            outputFile = args[++i];
        } else if (arg.startsWith('--')) {
            // Flags like --py, --font are ignored
        } else if (arg.includes(':')) {
            const [key, val] = arg.split(/:(.+)/); // Split only on first colon
            const parts = key.split('.');
            let current = params;
            for (let j = 0; j < parts.length - 1; j++) {
                if (!current[parts[j]]) current[parts[j]] = {};
                current = current[parts[j]];
            }
            // Handle boolean strings? fxconv.py seems to take strings and parse later.
            // convert_topti expects "true" string for proportional.
            current[parts[parts.length - 1]] = val;
        } else {
            if (!inputFile) inputFile = arg;
        }
        i++;
    }
    return { inputFile, outputFile, params };
}

function main() {
    const args = process.argv.slice(2);
    if (args.length === 0) {
        console.log("Usage: node fxconv_cli.js <input.png> -o <output.py> [params...]");
        process.exit(1);
    }

    const { inputFile, outputFile, params } = parseArgs(args);

    if (!inputFile) {
        console.error("Error: No input file specified.");
        process.exit(1);
    }

    // Default output file name if not specified?
    // fxconv.py defaults to input.o but since we target .py...
    const finalOutputFile = outputFile || inputFile.replace(/\.[^/.]+$/, "") + ".py";

    fs.createReadStream(inputFile)
        .pipe(new PNG())
        .on('parsed', function() {
            const width = this.width;
            const height = this.height;
            const data = this.data;

            const imageWrapper = {
                width: width,
                height: height,
                isBlack: (x, y) => {
                    if (x < 0 || x >= width || y < 0 || y >= height) return false;
                    const idx = (width * y + x) << 2;
                    const r = data[idx];
                    const g = data[idx+1];
                    const b = data[idx+2];
                    const a = data[idx+3];

                    if (a < 128) return false; // Transparent is not black
                    // Quantize thresholds: (0+85)/2 = 42.5
                    const avg = (r + g + b) / 3;
                    return avg < 43;
                },
                isWhite: (x, y) => {
                    if (x < 0 || x >= width || y < 0 || y >= height) return true;
                    const idx = (width * y + x) << 2;
                    const r = data[idx];
                    const g = data[idx+1];
                    const b = data[idx+2];
                    const a = data[idx+3];

                    if (a < 128) return false; // Transparent is not white
                    // Quantize thresholds: (170+255)/2 = 212.5
                    const avg = (r + g + b) / 3;
                    return avg > 212;
                }
            };

            try {
                const output = convert_topti(imageWrapper, params);
                fs.writeFileSync(finalOutputFile, output);
                console.log(`Successfully wrote to ${finalOutputFile}`);
            } catch (e) {
                console.error("Conversion failed:", e.message);
                process.exit(1);
            }
        })
        .on('error', function(err) {
            console.error("Error reading image:", err.message);
            process.exit(1);
        });
}

main();

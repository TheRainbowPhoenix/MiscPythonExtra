# pe-headless — local inspector & USB remote

```sh
# Linux: capture a game without a framebuffer
PE_DRAW_TRACE=/tmp/graphics.draw /path/to/micropython render_raytracer.py
python3 tools/pe-headless/view.py --trace /tmp/graphics.draw --source render_raytracer.py

# Windows full instrumentation: read screen.mmap and click Record
python3 tools/pe-headless/view.py --shm /path/to/session/screen.mmap

# Linux: start a virtual calculator USB server, then use a second terminal
PE_USB_PORT=8765 /path/to/micropython tools/pe-headless/spu_remote_server.py
python3 tools/pe-headless/spu_tcp.py --port 8765 ping
python3 tools/pe-headless/spu_tcp.py --port 8765 exec "print(6 * 7)"
python3 tools/pe-headless/spu_tcp.py --port 8765 stop

# Profile and compare the raytracer in a native headless build
python3 tools/pe-headless/profile_raytracer.py --exe /path/to/micropython \
  --original tools/pe-headless/fixtures/raytracer_baseline.py --optimized render_raytracer.py \
  --json /tmp/raytracer-profile.json

# Preview the Tk inspector without an instrumented process
python3 tools/pe-headless/view.py --demo
```

# USB traffic inspector: start a localhost proxy between client and VM
python3 tools/pe-headless/usb_trace_proxy.py --port 8766 --target 8765 --log /tmp/usb.jsonl
python3 tools/pe-headless/spu_tcp.py --port 8766 exec "print(6 * 7)"
python3 tools/pe-headless/view.py --remote-log /tmp/usb.jsonl --demo

The native Linux USB server binds to **127.0.0.1 only**. It accepts Python code execution for local development; never expose its port publicly. It supports spu-tools `PING`, `EXEC`, `STATUS` and `STOP` but intentionally rejects raw SPU registers and DSP memory operations. For original spu-tools scripts, `spu_tcp.py --run /path/to/spu-tools/script.py ...` patches `USBClient.connect()` to use TCP (requires pyusb).

Recordings are opt-in, batched, and read on a background thread. Windows full instrumentation uses its existing 1 MiB SHM screen and trace ring; Linux and small Windows variants use `PE_DRAW_TRACE` files and approximate geometry, not raster playback. The Graphics inspector is an inspired UI, not a complete WebKit debugger. Pillow is optional for showing full-host RGB565 screen pixels.

The inspector retains the original **Performance, Console, Sources, Storage, Timelines, Remote** icon tabs and adds **Graphics**. Remote displays logged USB packets, direction, sizes, and hex previews; serial remains unimplemented. Unlike the archived full native debugger, this standalone recording viewer currently provides a static source view and Graphics/USB recordings rather than active VM stepping or storage instrumentation.

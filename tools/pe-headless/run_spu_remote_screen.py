#!/usr/bin/env python3
"""Ready-to-run spu-tools RemoteScreen demo over a virtual gint.USB socket.

Install upstream spu-tools (Python >=3.14; pip install pyusb) and run:
  python run_spu_remote_screen.py --spu-tools ../spu-tools --port 8765

For Windows with the SHM USB bridge and USB packet inspector, use --port 8766.
Start the MicroPython remote server first:
  PE_USB_PORT=8765 micropython tools/pe-headless/spu_remote_server.py  # Linux
or on Windows launch the server with view.py --usb-bridge.

This tests the real upstream comm.draw.RemoteScreen and USBClient API.
It deliberately does NOT emulate SPU memory, ISA, or the coprocessor.
"""
import argparse
import math
from pathlib import Path
import socket
import sys
import time


class VirtualUSB:
    """Minimal PyUSB-style socket device accepted by spu-tools USBClient."""

    def __init__(self, port):
        deadline=time.monotonic()+8
        while True:
            try:
                self.sock=socket.create_connection(("127.0.0.1",port),timeout=2)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(.05)
        self.sock.settimeout(6)

    def write(self, endpoint, data, timeout=2000):
        if endpoint != 0x02:
            raise ValueError("expected USB OUT 0x02")
        return self.sock.send(bytes(data))

    def read(self, endpoint, length, timeout=2000):
        if endpoint != 0x81:
            raise ValueError("expected USB IN 0x81")
        self.sock.settimeout(None if timeout is None else timeout / 1000)
        try:
            return self.sock.recv(length)
        except socket.timeout as error:
            # USBClient.drain expects PyUSB's timeout exception.
            from usb.core import USBTimeoutError
            raise USBTimeoutError("virtual USB timeout") from error

    def close(self):
        self.sock.close()


def run_demo(path, port, frames, delay):
    sys.path.insert(0, str(path.resolve()))
    from comm.draw import (Color, DrawClear, DrawRect, DrawLine,
                           DrawText, DrawUpdate, RemoteScreen)
    from comm.usbclient import USBClient

    device = VirtualUSB(port)
    try:
        with USBClient(device, 64) as client:
            client.check_version()
            client.set_status("Virtual RemoteScreen demo")
            screen = RemoteScreen(client)
            w, h = screen.get_width(), screen.get_height()
            print("Remote gint display:", w, "x", h, flush=True)
            for frame in range(frames):
                x = int((w - 80) * frame / max(1, frames - 1))
                y = int((h - 130) * (0.5 + 0.35 * math.sin(frame * 0.25)))
                screen.add(
                    DrawClear(Color.WHITE),
                    DrawRect(0, 0, w - 1, 35, Color.BLUE),
                    DrawText(9, 9, Color.WHITE, "spu-tools / virtual USB"),
                    DrawRect(x, y, x + 64, y + 58, Color.GREEN),
                    DrawLine(0, h - 1, x + 32, y + 29, Color.RED),
                    DrawText(9, h - 34, Color.BLACK, "Frame %d/%d" % (frame + 1, frames)),
                    DrawUpdate(),
                )
                screen.push()
                if delay:
                    time.sleep(delay)
            print("PASS: %d genuine spu-tools RemoteScreen frames" % frames)
            client.stop()
    finally:
        device.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spu-tools", type=Path, default=Path("../spu-tools"))
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--frames", type=int, default=36)
    parser.add_argument("--delay", type=float, default=0.06)
    args = parser.parse_args()
    if args.frames < 1 or args.frames > 600:
        parser.error("--frames must be between 1 and 600")
    if not 1 <= args.port <= 65535:
        parser.error("invalid TCP port")
    run_demo(args.spu_tools, args.port, args.frames, args.delay)


if __name__ == "__main__":
    main()

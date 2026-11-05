"""Cross-platform Graphics recording readers for PythonExtra headless and SHM hosts.

The lightweight hosts write 32-byte records when PE_DRAW_TRACE is enabled.
The full Windows instrumentation host writes 256-byte events into its existing
SPSC shared-memory trace ring while H_FLAGS bit 0x100 is enabled.
The consumer never requests a framebuffer copy from the MicroPython process.
"""
import dataclasses
import mmap
import os
from pathlib import Path
import struct
import threading
import time
from collections import deque

TRACE_HEADER = b"PEDRAW1\n"
EVENT = struct.Struct("<QIIiiii")
SHM_MAGIC = 0x50454931
SHM_SIZE = 1048576
SHM_CTRL = 1024
SHM_RING = 400000
SHM_CAP = 1024
SHM_ENTRY_SIZE = 256
SHM_FLAGS = 17 * 4
RECORD_FLAG = 0x100
METHODS = {
    1: "dclear", 2: "drect", 3: "dpixel", 4: "dtext",
    5: "dline", 6: "dtext_opt", 7: "drect_border", 8: "dcircle",
    9: "dupdate", 10: "dellipse", 11: "dsubimage", 12: "dhline",
    13: "dvline", 14: "dimage", 15: "dpoly",
}


@dataclasses.dataclass(frozen=True)
class DrawEvent:
    when_ns: int
    name: str
    duration_ns: int
    args: tuple = ()
    method_id: int = 0


class FileTraceReader:
    """Reads only whole records; safe against partial producer writes."""

    def __init__(self, path):
        self.path = Path(path)
        self.offset = 8
        self.pending = b""

    def read(self):
        if not self.path.is_file():
            return []
        with self.path.open("rb") as f:
            if f.read(8) != TRACE_HEADER:
                raise ValueError("not a PEDRAW1 trace")
            size = os.fstat(f.fileno()).st_size
            if size < self.offset:
                self.offset = 8
                self.pending = b""
            f.seek(self.offset)
            new = f.read(4 * 1024 * 1024)
            self.offset += len(new)
        block = self.pending + new
        count = len(block) // EVENT.size
        self.pending = block[count * EVENT.size:]
        return [
            DrawEvent(when, METHODS.get(kind, "method_%d" % kind),
                      duration, (x, y, a, b), kind)
            for when, kind, duration, x, y, a, b in
            (EVENT.unpack_from(block, i * EVENT.size) for i in range(count))
        ]

    def close(self):
        pass


class SharedMemoryTraceReader:
    """Reads the full host's native SPSC ring; only one trace reader may own it."""

    def __init__(self, path):
        self.file = Path(path).open("r+b")
        if os.fstat(self.file.fileno()).st_size != SHM_SIZE:
            raise ValueError("expected 1 MiB PE_MAP shared memory")
        self.shared = mmap.mmap(self.file.fileno(), SHM_SIZE)
        if struct.unpack_from("<I", self.shared)[0] != SHM_MAGIC:
            self.close()
            raise ValueError("not a PE instrumentation mapping")
        self.drops = 0

    def recording(self, enabled):
        flags = struct.unpack_from("<I", self.shared, SHM_FLAGS)[0]
        if enabled:
            flags |= RECORD_FLAG
        else:
            flags &= ~RECORD_FLAG
        struct.pack_into("<I", self.shared, SHM_FLAGS, flags)

    def read(self):
        write, read, drops = struct.unpack_from("<III", self.shared, SHM_CTRL)
        self.drops = drops
        if ((write - read) & 0xffffffff) > SHM_CAP:
            read = (write - SHM_CAP) & 0xffffffff
        events = []
        # Ring entries are published before the producer increments write.
        while read != write:
            offset = SHM_RING + (read % SHM_CAP) * SHM_ENTRY_SIZE
            stamp, kind, value, _extra = struct.unpack_from("<QIII", self.shared, offset)
            if 41 <= kind <= 55:
                method = kind - 40
                label = self.shared[offset + 20:offset + 256].split(b"\x00", 1)[0]
                name = label.decode("utf-8", "replace") or METHODS.get(method, "?")
                events.append(DrawEvent(stamp * 1000, name, max(value, 0) * 1000,
                                        (), method))
            read = (read + 1) & 0xffffffff
        struct.pack_into("<I", self.shared, SHM_CTRL + 4, read)
        return events

    def framebuffer(self):
        """Read RGB565 VRAM using sequence-lock checking; viewers can coexist."""
        for _ in range(4):
            seq1 = struct.unpack_from("<I", self.shared, 7 * 4)[0]
            if seq1 & 1:
                continue
            pixels = bytes(self.shared[4096:4096 + 320 * 528 * 2])
            seq2 = struct.unpack_from("<I", self.shared, 7 * 4)[0]
            if seq1 == seq2:
                return pixels
        return None

    def close(self):
        if hasattr(self, "shared"):
            self.shared.close()
        self.file.close()


class FrameStore:
    """Bounded immutable completed frames; a live frame is kept separately."""

    def __init__(self, limit=300):
        self.frames = deque(maxlen=limit)
        self.active = []
        self.total_events = 0

    def append(self, events):
        completed = 0
        for event in events:
            self.active.append(event)
            self.total_events += 1
            if event.name == "dupdate":
                self.frames.append(tuple(self.active))
                self.active.clear()
                completed += 1
        return completed

    def summary(self, frame):
        methods = {}
        for event in frame:
            calls, ns = methods.get(event.name, (0, 0))
            methods[event.name] = (calls + 1, ns + event.duration_ns)
        return sorted(methods.items(), key=lambda x: x[1][1], reverse=True)


class RecorderThread(threading.Thread):
    """Read disk or SHM on a non-Tk thread and deliver batches via a queue."""

    def __init__(self, reader, output_queue, interval=0.015):
        super().__init__(name="pe-graphics-reader", daemon=True)
        self.reader = reader
        self.output_queue = output_queue
        self.interval = interval
        self.stop_event = threading.Event()

    def run(self):
        try:
            while not self.stop_event.is_set():
                events = self.reader.read()
                if events:
                    self.output_queue.put(events)
                self.stop_event.wait(self.interval)
        except Exception as error:
            self.output_queue.put(error)

    def stop(self):
        self.stop_event.set()
        self.join(timeout=2)
        self.reader.close()

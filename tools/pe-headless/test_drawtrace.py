#!/usr/bin/env python3
"""Parser/SHM protocol tests for the standalone devtools inspector."""
import mmap
from pathlib import Path
import struct
import tempfile
import unittest
from drawtrace import (
    DrawEvent, EVENT, TRACE_HEADER, FileTraceReader, SharedMemoryTraceReader,
    FrameStore, SHM_SIZE, SHM_RING, SHM_CTRL, SHM_FLAGS, RECORD_FLAG
)

class TraceTests(unittest.TestCase):
    def test_record_file_and_frame_split(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"test.draw"
            record=lambda stamp,kind,x: EVENT.pack(stamp,kind,1000,x,2,3,4)
            path.write_bytes(TRACE_HEADER+record(1,2,5)+record(2,9,0)
                             +record(3,3,9)+record(4,9,0)[:7])
            reader=FileTraceReader(path)
            first=reader.read()
            self.assertEqual([x.name for x in first],["drect","dupdate","dpixel"])
            path.open("ab").write(record(4,9,0)[7:])
            second=reader.read()
            self.assertEqual([x.name for x in second],["dupdate"])
            store=FrameStore()
            self.assertEqual(store.append(first),1)
            self.assertEqual(store.append(second),1)
            self.assertEqual(len(store.frames),2)
            self.assertEqual(store.summary(store.frames[0])[0][0],"drect")

    def test_shm_graphics_stack_and_frame_boundary(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"screen.mmap"
            with path.open("wb") as f:
                f.truncate(SHM_SIZE)
            with path.open("r+b") as f, mmap.mmap(f.fileno(),SHM_SIZE) as mm:
                struct.pack_into("<II",mm,0,0x50454931,1)
                struct.pack_into("<III",mm,SHM_CTRL,2,0,0)
                names=(b"drect\nCPChat_host.py|47|main",b"dupdate\nCPChat_host.py|64|main")
                for i,(kind,label) in enumerate(zip((42,49),names)):
                    offset=SHM_RING+i*256
                    struct.pack_into("<QIII",mm,offset,100+i,kind,22,0)
                    mm[offset+20:offset+20+len(label)]=label
            reader=SharedMemoryTraceReader(path)
            try:
                events=reader.read()
                self.assertEqual([e.name for e in events],["drect","dupdate"])
                self.assertEqual(events[0].stack,("CPChat_host.py|47|main",))
                store=FrameStore()
                self.assertEqual(store.append(events),1)
                self.assertEqual(len(store.frames[0]),2)
            finally:
                reader.close()

    def test_shm_ring_and_framebuffer_independence(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"screen.mmap"
            with path.open("wb") as f:
                f.truncate(SHM_SIZE)
            with path.open("r+b") as f, mmap.mmap(f.fileno(),SHM_SIZE) as mm:
                struct.pack_into("<II",mm,0,0x50454931,1)
                struct.pack_into("<III",mm,SHM_CTRL,2,0,0)
                struct.pack_into("<QIII",mm,SHM_RING,110,42,20,0)
                mm[SHM_RING+20:SHM_RING+25]=b"drect"
                struct.pack_into("<QIII",mm,SHM_RING+256,120,49,40,0)
                mm[SHM_RING+276:SHM_RING+283]=b"dupdate"
                struct.pack_into("<H",mm,4096,0x1234)
            reader=SharedMemoryTraceReader(path)
            try:
                reader.recording(True)
                self.assertTrue(struct.unpack_from("<I",reader.shared,SHM_FLAGS)[0]&RECORD_FLAG)
                result=reader.read()
                self.assertEqual([x.name for x in result],["drect","dupdate"])
                self.assertEqual(result[0].duration_ns,20000)
                self.assertEqual(struct.unpack_from("<I",reader.shared,SHM_CTRL+4)[0],2)
                self.assertEqual(reader.framebuffer()[:2],b"\x34\x12")
                with path.open("rb") as second, mmap.mmap(second.fileno(),SHM_SIZE,access=mmap.ACCESS_READ) as screen:
                    self.assertEqual(screen[4096:4098],b"\x34\x12")
                reader.recording(False)
                self.assertFalse(struct.unpack_from("<I",reader.shared,SHM_FLAGS)[0]&RECORD_FLAG)
            finally:
                reader.close()

if __name__=="__main__":
    unittest.main()

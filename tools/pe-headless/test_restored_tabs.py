#!/usr/bin/env python3
"""Exercise the real tab names/icons and USB trace integration."""
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import tkinter as tk
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
from remote_trace import load_events
from usb_trace_proxy import PacketDecoder
from view import Inspector

class Tabs(unittest.TestCase):
    def test_original_tabs_and_icons(self):
        root=tk.Tk()
        root.withdraw()
        try:
            app=Inspector(root,demo=True)
            root.update()
            names=[app.tabs.tab(i,"text") for i in range(app.tabs.index("end"))]
            self.assertEqual(names,["Performance","Console","Sources","Storage",
                                    "Timelines","Graphics","Remote"])
            self.assertEqual(len(app.tab_icons),len(names))
            for i in range(len(names)):
                self.assertEqual(str(app.tabs.tab(i,"compound")),"left")
                self.assertTrue(app.tabs.tab(i,"image"))
            self.assertEqual(len(app.frames.frames),68)
            for name in names:
                app.tabs.select(app.pages[name])
                root.update()
                self.assertEqual(app.tab,name)
            self.assertTrue(hasattr(app,"remote_tree"))
            self.assertTrue(hasattr(app,"remote_status"))
            labels=[x.cget("text") for container in app.pages["Remote"].winfo_children()
                    for x in container.winfo_children() if isinstance(x,tk.Label)]
            self.assertIn("Serial: not implemented",labels)
        finally:
            root.destroy()

    def test_usb_packets_with_partial_tcp_chunks(self):
        with tempfile.TemporaryDirectory() as temp:
            trace=Path(temp)/"usb.jsonl"
            def log(item):
                with trace.open("a",encoding="utf-8") as f:
                    f.write(json.dumps(item)+"\n")
            def write(item):
                log({"time":"00:00","direction":item["direction"],"kind":item["kind"],
                     "size":item["size"],"preview":item["preview"]})
            decoder=PacketDecoder("Host → MicroPython",write)
            pkt=struct.pack(">II",0x1003,7)+b"print(1)"
            decoder.feed(pkt[:5]); decoder.feed(pkt[5:11]);decoder.feed(pkt[11:])
            parsed=load_events(trace)
            self.assertEqual(len(parsed),1)
            self.assertEqual(parsed[0]["kind"],"EXEC")
            self.assertEqual(parsed[0]["size"],7)
            self.assertEqual(parsed[0]["direction"],"Host → MicroPython")

if __name__=="__main__":
    unittest.main()

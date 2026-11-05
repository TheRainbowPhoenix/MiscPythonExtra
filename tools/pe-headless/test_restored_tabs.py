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
        root.geometry('1240x780')
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
            widths=[app.tab_boxes[name].winfo_width() for name in names]
            self.assertTrue(all(w>=100 for w in widths),widths)
            for name in names:
                app.tabs.select(app.pages[name])
                root.update()
                self.assertEqual(app.tab,name)
                self.assertEqual([app.tab_boxes[n].winfo_width() for n in names],widths)
            self.assertTrue(hasattr(app,"remote_tree"))
            self.assertFalse(hasattr(app,"remote_status"))
            self.assertNotIn("direction",app.remote_tree["columns"])
            from remote_panel import direction,hexdump
            record={"kind":"EXEC","direction":"MicroPython -> Host",
                    "size":4,"payload_hex":"00 41 FF 42"}
            self.assertEqual(direction(record),(True,"PY -> Host"))
            self.assertIn("00000000",hexdump(record))
            self.assertIn("|.A.B",hexdump(record))
            app.remote_panel.update([record])
            self.assertEqual(len(app.remote_tree.get_children()),1)
            app.remote_tree.selection_set("0")
            app.remote_panel.select()
            self.assertIn("00 41 FF 42",app.remote_detail.get("1.0","end"))
            app.remote_panel.popup()
            self.assertTrue([x for x in app.pages["Remote"].winfo_children() if isinstance(x,tk.Toplevel)])

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
            decoder=PacketDecoder("Host -> MicroPython",write)
            pkt=struct.pack(">II",0x1003,7)+b"print(1)"
            decoder.feed(pkt[:5]); decoder.feed(pkt[5:11]);decoder.feed(pkt[11:])
            parsed=load_events(trace)
            self.assertEqual(len(parsed),1)
            self.assertEqual(parsed[0]["kind"],"EXEC")
            self.assertEqual(parsed[0]["size"],7)
            self.assertEqual(parsed[0]["direction"],"Host -> MicroPython")

if __name__=="__main__":
    unittest.main()

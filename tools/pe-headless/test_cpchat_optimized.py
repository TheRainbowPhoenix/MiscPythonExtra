#!/usr/bin/env python3
"""Exercise the real cinput widgets and compare idle redraw budgets.

This is a deterministic compatibility/allocation-pressure regression, not a
hardware heap or GC benchmark. An actual fxcp profiling run is still needed.
"""
import importlib
import pathlib
import re
import runpy
import sys
import time
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = pathlib.Path(__file__).resolve().parent / "examples/CPChat_optimized.py"


def fake_gint():
    source=(ROOT/"cinput.py").read_text(encoding="utf-8")
    keys=set(re.findall(r"\b(?:KEY(?:EV)?_[A-Z_0-9]+|C_[A-Z_0-9]+|DTEXT_[A-Z_0-9]+)\b", source))
    keys.update(("KEYEV_NONE","KEYEV_DOWN","KEYEV_TOUCH_DOWN",
                 "KEYEV_TOUCH_UP","KEY_EXIT","C_BLACK","C_WHITE","C_NONE"))
    gint=types.ModuleType("gint")
    for index, name in enumerate(sorted(keys), 10):
        setattr(gint,name,index)
    gint.KEYEV_NONE=0
    gint.KEYEV_DOWN=1
    gint.KEYEV_TOUCH_DOWN=2
    gint.KEYEV_TOUCH_UP=3
    gint.KEY_EXIT=4
    gint.C_NONE=-1
    gint.C_BLACK=0
    gint.C_WHITE=65535
    gint.C_RGB=lambda r,g,b: (r<<11)|(g<<6)|b
    counters={"calls":0,"frames":0,"polls":0,"read":0}
    def draw(*args):
        counters["calls"]+=1
    def update(*args):
        counters["frames"]+=1
    for name in ("dclear","drect","dtext","dhline","dline","dtext_opt",
                 "drect_border","dpixel","dvline","dcircle","dpoly",
                 "dellipse","dimage","dsubimage","dwindow_get","dwindow_set"):
        setattr(gint,name,draw)
    gint.dupdate=update
    gint.cleareventflips=lambda:None
    gint.dsize=lambda *args:(12,10)
    gint.dnsize=lambda *args:(12,10)
    gint.drsize=lambda *args:(2,12)
    class Event:
        type=0
        key=0
        x=0
        y=0
    def event():
        counters["polls"]+=1
        e=Event()
        if counters["polls"]>=250:
            e.type=gint.KEYEV_DOWN
            e.key=gint.KEY_EXIT
        return e
    gint.pollevent=event
    class USB:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def fxlink_header(self,*args): pass
        def write(self,*args): counters["read"]+=1
        def flush(self): pass
        def read(self,*args): return b""
    gint.USB=USB
    gint.__all__=[x for x in vars(gint) if not x.startswith("_")]
    return gint,counters


class CPChatTests(unittest.TestCase):
    def test_real_cinput_idle_and_usb(self):
        gint,counters=fake_gint()
        old=sys.modules.get("gint")
        old_cinput=sys.modules.pop("cinput",None)
        orig=(getattr(time,"ticks_ms",None),getattr(time,"ticks_diff",None),time.sleep)
        elapsed=[0]
        time.ticks_ms=lambda:elapsed[0]
        time.ticks_diff=lambda a,b:a-b
        time.sleep=lambda seconds:elapsed.__setitem__(0,elapsed[0]+int(seconds*1000))
        sys.modules["gint"]=gint
        try:
            code=runpy.run_path(str(SCRIPT),run_name="__smoke__")
            cinput=importlib.import_module("cinput")
            self.assertIs(code["cinput"],cinput)
            code["main"]()
            self.assertGreaterEqual(counters["polls"],250)
            self.assertLessEqual(counters["frames"],2)
            self.assertGreaterEqual(counters["read"],5)
            baseline=cinput.Keyboard(enable_tabs=True,theme="light")
            baseline_calls=counters["calls"]
            for _ in range(249):
                baseline.draw()
            extra=counters["calls"]-baseline_calls
            self.assertGreater(extra,counters["calls"]-extra)
            print("PASS: real cinput idle frames=%d vs 249 baseline frames" %
                  counters["frames"])
            print("PASS: native draw calls avoided during idle; USB polls=%d" %
                  counters["read"])
        finally:
            sys.modules.pop("cinput",None)
            if old_cinput is not None:sys.modules["cinput"]=old_cinput
            if old is None:sys.modules.pop("gint",None)
            else:sys.modules["gint"]=old
            for key,value in zip(("ticks_ms","ticks_diff","sleep"),orig):
                if value is None:delattr(time,key)
                else:setattr(time,key,value)


if __name__=="__main__":
    unittest.main()

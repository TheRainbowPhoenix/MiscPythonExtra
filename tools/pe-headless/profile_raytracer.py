#!/usr/bin/env python3
"""Compare native MicroPython raytracer timings and check CPython pixel output.

  python tools/pe-headless/profile_raytracer.py \
    --exe /path/to/micropython \
    --original tools/pe-headless/fixtures/raytracer_baseline.py --optimized render_raytracer.py
"""
import argparse
import array
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time
import types

# Matches the full host's RGB565 color encoding.
WIDTH, HEIGHT = 320, 528
SIZE = WIDTH * HEIGHT

def prepare(source):
    # Original demo waits forever for EXE after its final frame. Bench only
    # the unchanged run() function and avoid modifying the source on disk.
    code = Path(source).read_text(encoding="utf-8")
    anchor = "\nrun()\n"
    cut = code.rfind(anchor)
    if cut < 0:
        raise ValueError("raytracer must end with a run() invocation")
    return code[:cut] + anchor


def capture_pixels(source):
    pixels = array.array("H",[65535]) * SIZE
    calls = Counter()
    frames = []
    texts = []

    def c_rgb(r,g,b):
        return (int(r)<<11) | (int(g)<<6) | int(b)

    def clear(color):
        calls["dclear"] += 1
        pixels[:] = array.array("H",[int(color)&0xffff]) * SIZE

    def pixel(x,y,color):
        calls["dpixel"] += 1
        if 0<=x<WIDTH and 0<=y<HEIGHT:
            pixels[y*WIDTH+x] = int(color) & 0xffff

    def rect(x1,y1,x2,y2,color):
        calls["drect"] += 1
        if x1>x2: x1,x2=x2,x1
        if y1>y2: y1,y2=y2,y1
        left=max(0,x1);right=min(WIDTH-1,x2)
        top=max(0,y1);bottom=min(HEIGHT-1,y2)
        if right>=left and bottom>=top:
            row=array.array("H",[int(color)&0xffff])*(right-left+1)
            for y in range(top,bottom+1):
                pixels[y*WIDTH+left:y*WIDTH+right+1]=row

    def dtext(x,y,color,text):
        calls["dtext"]+=1
        texts.append((x,y,color,text))

    def update():
        calls["dupdate"]+=1
        frames.append(hashlib.blake2b(pixels.tobytes(),digest_size=16).hexdigest())

    gint=types.ModuleType("gint")
    gint.C_RGB=c_rgb
    gint.dclear=clear
    gint.dpixel=pixel
    gint.drect=rect
    gint.dtext=dtext
    gint.dupdate=update
    for name,value in {"C_WHITE":65535,"C_BLACK":0,"C_RED":63488,
                       "KEY_DEL":68,"KEY_EXE":21,"KEY_EXIT":116,
                       "DWIDTH":WIDTH,"DHEIGHT":HEIGHT}.items():
        setattr(gint,name,value)
    old=sys.modules.get("gint")
    sys.modules["gint"]=gint
    try:
        exec(compile(prepare(source),str(source),"exec"),{"__name__":"__main__"})
    finally:
        if old is None:
            del sys.modules["gint"]
        else:
            sys.modules["gint"]=old
    return {"hash":hashlib.sha256(pixels.tobytes()).hexdigest(),
            "frames":frames,"texts":texts,"calls":dict(calls)}


def native_benchmark(exe,source,trials,record=False):
    samples=[]
    code=("p="+repr(str(Path(source).resolve()))+";"
          "s=open(p).read();"
          "i=s.rfind(chr(10)+'run()'+chr(10));"
          "exec(compile(s[:i]+chr(10)+'run()'+chr(10),p,'exec'))")
    for _ in range(trials):
        with tempfile.TemporaryDirectory(prefix="pe-raytrace-") as directory:
            env=dict(os.environ)
            if record:
                env["PE_DRAW_TRACE"]=str(Path(directory)/"render.draw")
            else:
                env.pop("PE_DRAW_TRACE",None)
            start=time.perf_counter_ns()
            proc=subprocess.run([str(exe),"-c",code],
                cwd=directory,env=env,stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,timeout=90)
            elapsed=(time.perf_counter_ns()-start)/1e6
            if proc.returncode:
                raise RuntimeError("MicroPython exit %d: %s" %
                    (proc.returncode,proc.stderr.decode("utf-8","replace")[-1200:]))
            sample={"wall_ms":round(elapsed,3)}
            if record:
                path=Path(directory)/"render.draw"
                raw=path.read_bytes()
                import struct
                entry=struct.Struct("<QIIiiii")
                if not raw.startswith(b"PEDRAW1\n"):
                    raise AssertionError("recording not produced")
                events=[entry.unpack_from(raw,i) for i in range(8,len(raw),entry.size)]
                sample["draw_calls"]=len(events)
                sample["draw_cpu_ms"]=round(sum(e[2] for e in events)/1e6,3)
                sample["frames"]=sum(e[1]==9 for e in events)
            samples.append(sample)
    return {"samples":samples,
            "median_wall_ms":round(statistics.median(x["wall_ms"] for x in samples),3)}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--exe",type=Path,required=True)
    p.add_argument("--original",type=Path,required=True)
    p.add_argument("--optimized",type=Path,required=True)
    p.add_argument("--trials",type=int,default=3)
    p.add_argument("--json",type=Path)
    args=p.parse_args()
    original=capture_pixels(args.original)
    optimized=capture_pixels(args.optimized)
    assert original==optimized, ("render mismatch",
         {k:(original.get(k),optimized.get(k)) for k in original
          if original.get(k)!=optimized.get(k)})
    print("PASS: exact RGB565 pixels, frame hashes, text and draw calls")
    exe=str(args.exe.resolve())
    a=native_benchmark(exe,args.original,args.trials)
    b=native_benchmark(exe,args.optimized,args.trials)
    # Recording overhead is measured separately from regular execution.
    trace=native_benchmark(exe,args.optimized,1,record=True)
    speed=(a["median_wall_ms"]/b["median_wall_ms"]) if b["median_wall_ms"] else 0
    result={"original":a,"optimized":b,"optimized_recorded":trace,
            "speedup":round(speed,3),"pixel_hash":original["hash"],
            "frames":len(original["frames"]),"draw_calls":original["calls"]}
    print(json.dumps(result,indent=2))
    if args.json:
        args.json.parent.mkdir(parents=True,exist_ok=True)
        args.json.write_text(json.dumps(result,indent=2)+"\n")
    # Do not set a speedup success threshold: CI noise and varying VM timings.
    # Exact pixel and event-sequence equivalence remains mandatory.

if __name__=="__main__":
    main()

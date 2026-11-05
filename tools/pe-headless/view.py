#!/usr/bin/env python3
"""PythonExtra developer inspector: Safari/WebKit-inspired Graphics recordings.

Native lightweight host: PE_DRAW_TRACE=/tmp/scene.draw micropython file.py
Inspect: python tools/pe-headless/view.py --trace /tmp/scene.draw

Full Windows SHM host: python tools/pe-headless/view.py --shm SESSION/screen.mmap
Click Record before drawing. SHM screen readers remain independent.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import queue
import sys
import tkinter as tk
from tkinter import filedialog, ttk, messagebox

from drawtrace import (
    DrawEvent, FileTraceReader, SharedMemoryTraceReader, FrameStore, RecorderThread
)

CHROME = "#f2f2f3"
EDGE = "#d9dadd"
TEXT = "#343b45"
MUTED = "#818995"
BLUE = "#79b6f7"
PURPLE = "#ae79dd"
GREEN = "#8bc447"
ORANGE = "#e5ae8a"
OP_COLORS = {
    "dpixel": "#8dcc58", "drect": "#9dd359", "dclear": "#ecc2a1",
    "dtext": "#aa88dd", "dline": "#8bbbdc", "dupdate": "#90c74b",
}


class Inspector:
    def __init__(self, root, reader=None, source=None, demo=False):
        self.root = root
        root.title("PythonExtra — Web Inspector")
        root.geometry("1230x780")
        root.configure(bg=CHROME)
        self.reader = reader
        self.worker = None
        self.messages = queue.Queue()
        self.frames = FrameStore()
        self.selected_frame = 0
        self.recording = False
        self.source = source
        self.demo = demo
        self.tab = "Graphics"
        self.preview_picture = None
        self.vars = {}
        self._style()
        self._layout()
        if demo:
            self._make_demo()
            self._update_frames()
        if reader:
            self.worker = RecorderThread(reader, self.messages)
            self.worker.start()
        root.after(50, self._drain)
        root.protocol("WM_DELETE_WINDOW", self._close)

    def _style(self):
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure(".", font=("Arial", 10), background=CHROME, foreground=TEXT)
        style.configure("TFrame", background=CHROME)
        style.configure("TButton", padding=(10, 5), relief="flat", borderwidth=1)
        style.map("TButton", background=[("active", "#e3e6ea")])
        style.configure("TLabel", background=CHROME)
        style.configure("Treeview", rowheight=23, background="white",
                        fieldbackground="white", foreground=TEXT, borderwidth=0)
        style.configure("Treeview.Heading", background="#f4f5f6",
                        font=("Arial", 10, "bold"), padding=4)
        style.map("Treeview", background=[("selected", "#d8eafa")])
        style.configure("Vertical.TScrollbar", width=10)

    def _label(self, parent, text, **kw):
        return tk.Label(parent, text=text, bg=kw.pop("bg", CHROME),
                        fg=kw.pop("fg", TEXT), font=kw.pop("font", ("Arial", 10)),
                        **kw)

    def _layout(self):
        tabs = tk.Frame(self.root, bg=CHROME, height=39,
                        highlightbackground=EDGE, highlightthickness=1)
        tabs.pack(fill="x")
        tabs.pack_propagate(False)
        for tab in ("Elements", "Console", "Sources", "Network",
                    "Timelines", "Storage", "Graphics", "Layers", "Audit"):
            button = tk.Button(tabs, text=tab, font=("Arial", 10),
                               relief="flat", borderwidth=0, cursor="hand2",
                               bg=CHROME, fg="#626a74", padx=13,
                               activebackground="#dfecf8",
                               command=lambda t=tab: self.show_tab(t))
            button.pack(side="left", fill="y", padx=(0, 1))
            self.vars[tab] = button
        self.toolbar = tk.Frame(self.root, bg="#fafafa", height=40,
                                highlightbackground=EDGE, highlightthickness=1)
        self.toolbar.pack(fill="x")
        self.toolbar.pack_propagate(False)
        self.record_btn = tk.Button(self.toolbar, text="● Record",
            fg="#dc5657", bg="#fafafa", borderwidth=0, font=("Arial", 10, "bold"),
            command=self.toggle_record)
        self.record_btn.pack(side="left", padx=(14, 7))
        ttk.Button(self.toolbar, text="Import", command=self.import_trace).pack(side="left", padx=3)
        ttk.Button(self.toolbar, text="Export", command=self.export).pack(side="left", padx=3)
        self._label(self.toolbar, "Events", fg="#539bd4",
                    font=("Arial", 10, "bold"), bg="#fafafa").pack(side="left", padx=(20, 8))
        self._label(self.toolbar, "Frames", bg="#fafafa").pack(side="left", padx=8)
        self.status = self._label(self.toolbar, "No recording loaded", fg=MUTED, bg="#fafafa")
        self.status.pack(side="right", padx=16)
        self.body = tk.Frame(self.root, bg="white")
        self.body.pack(fill="both", expand=True)
        self.show_tab("Graphics")

    def show_tab(self, tab):
        self.tab = tab
        for name, widget in self.vars.items():
            widget.configure(bg="#e2f0ff" if tab == name else CHROME,
                             fg="#2c78b8" if tab == name else "#626a74")
        for child in self.body.winfo_children():
            child.destroy()
        if tab == "Graphics":
            self._graphics()
        elif tab == "Timelines":
            self._timelines()
        elif tab == "Sources":
            self._sources()
        elif tab == "Console":
            self._console()
        else:
            self._generic(tab)

    def _graphics(self):
        pane = tk.PanedWindow(self.body, orient="horizontal", bg=EDGE,
                              sashwidth=4, bd=0)
        pane.pack(fill="both", expand=True)
        left = tk.Frame(pane, bg="white", width=325)
        right = tk.Frame(pane, bg="white")
        pane.add(left, minsize=300, width=320)
        pane.add(right, minsize=560)
        self._label(left, "▣  Canvas 1 — PythonExtra gint", bg="#f5f5f6",
                    font=("Arial", 10, "bold"), anchor="w").pack(fill="x", ipady=9, padx=1)
        self._label(left, "▾  Recording 1", bg="white", anchor="w",
                    fg="#4f87c3").pack(fill="x", padx=18, pady=(9, 4))
        self._label(left, "Frames", bg="white", font=("Arial", 10, "bold"),
                    anchor="w").pack(fill="x", padx=14, pady=(8, 5))
        self.frame_list = tk.Listbox(left, selectmode="browse", activestyle="none",
                                     bg="white", relief="flat", highlightthickness=0,
                                     font=("Arial", 10))
        self.frame_list.pack(fill="both", expand=True, padx=12, pady=(0, 6))
        self.frame_list.bind("<<ListboxSelect>>", self._select_list)
        self._label(left, "Select a frame to inspect its drawing calls",
                    bg="#f7f7f8", fg=MUTED, font=("Arial", 9),
                    anchor="w").pack(fill="x", ipady=8)
        self._label(right, "Overview  ›  Canvas 1  ›  Recording 1",
                    bg="#f8f8f9", fg="#3b444d",
                    font=("Arial", 10, "bold"), anchor="w").pack(fill="x", ipady=11)
        self.timeline = tk.Canvas(right, height=120, bg="#fbfbfc",
                                  highlightthickness=0)
        self.timeline.pack(fill="x")
        self.timeline.bind("<Button-1>", self._select_timeline)
        self.timeline.bind("<Configure>", lambda e: self._draw_timeline())
        bar = tk.Frame(right, bg="#f4f4f5", height=36)
        bar.pack(fill="x")
        self._label(bar, "Frame", bg="#f4f4f5", font=("Arial", 10, "bold")).pack(side="left", padx=(15, 5))
        self.scale = ttk.Scale(bar, from_=0, to=1, orient="horizontal", command=self._slider)
        self.scale.pack(side="left", fill="x", expand=True, padx=10)
        self.frame_label = self._label(bar, "0 of 0", bg="#f4f4f5", fg=MUTED)
        self.frame_label.pack(side="right", padx=16)
        split = tk.PanedWindow(right, orient="horizontal", sashwidth=4, bd=0, bg=EDGE)
        split.pack(fill="both", expand=True)
        events_panel = tk.Frame(split, bg="white")
        detail_panel = tk.Frame(split, bg="white", width=280)
        split.add(events_panel, minsize=330)
        split.add(detail_panel, minsize=210)
        self._label(events_panel, "Drawing calls — selected frame",
                    bg="#fbfbfb", anchor="w", font=("Arial", 10, "bold")).pack(fill="x", ipady=9, padx=6)
        fields=("call", "time", "cost")
        self.tree = ttk.Treeview(events_panel, columns=fields, show="headings",
                                 selectmode="browse")
        for field, title, width in (("call", "Operation", 160),
                                     ("time", "Start", 95), ("cost", "Duration", 95)):
            self.tree.heading(field, text=title)
            self.tree.column(field, width=width, stretch=(field=="call"), anchor="w")
        scroll=ttk.Scrollbar(events_panel, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._selected_call)
        self._label(detail_panel, "Call details", bg="#fafafa", anchor="w",
                    font=("Arial", 10, "bold")).pack(fill="x", ipady=9, padx=7)
        self.details = tk.Text(detail_panel, height=7, bg="white",
                               fg=TEXT, font=("Consolas", 10), borderwidth=0,
                               wrap="word")
        self.details.pack(fill="x", padx=10, pady=8)
        self._label(detail_panel, "Graphics preview", bg="#fafafa", anchor="w",
                    font=("Arial", 10, "bold")).pack(fill="x", ipady=9, padx=7)
        self.preview = tk.Canvas(detail_panel, bg="#f7f7f7", width=250, height=275,
                                 highlightthickness=0)
        self.preview.pack(fill="both", expand=True, padx=8, pady=8)
        self.summary = self._label(detail_panel, "No frame selected", fg=MUTED,
                                   anchor="w", bg="white", justify="left")
        self.summary.pack(fill="x", padx=12, pady=10)
        self._update_frames()

    def _timelines(self):
        self._label(self.body, "Timeline Recording 1   ›   Layout & Rendering",
                    bg="#f5f5f6", anchor="w",
                    font=("Arial", 11, "bold")).pack(fill="x", ipady=10)
        self.timeline=tk.Canvas(self.body, bg="#fcfcfd", highlightthickness=0)
        self.timeline.pack(fill="both", expand=True)
        self.timeline.bind("<Configure>", lambda e: self._draw_timeline(multi=True))
        self._draw_timeline(multi=True)

    def _sources(self):
        self._label(self.body, "Sources  ›  Python programs", anchor="w",
                    bg="#f4f4f5").pack(fill="x", ipady=10)
        editor=tk.Text(self.body, wrap="none", bg="#fcfcfe", fg=TEXT,
                       font=("Consolas", 11), relief="flat", padx=17, pady=12)
        editor.pack(fill="both", expand=True)
        if self.source and Path(self.source).is_file():
            lines=Path(self.source).read_text(encoding="utf-8").splitlines()
            editor.insert("1.0", "\n".join("%4d   %s" % (i, line)
                                           for i,line in enumerate(lines,1)))
        else:
            editor.insert("1.0", "Select --source <program.py> to display its source.")
        editor.configure(state="disabled")

    def _console(self):
        self._label(self.body, "Console  ›  Evaluations     Errors     Warnings     Logs",
                    bg="#f7f7f7", anchor="w").pack(fill="x", ipady=9)
        self.console=tk.Text(self.body, bg="white", fg=TEXT,
                             font=("Consolas", 11), relief="flat", padx=15, pady=12)
        self.console.pack(fill="both", expand=True)
        self.console.insert("end", "PythonExtra inspector ready\n")
        self.console.insert("end", "%d completed frames; %d recorded calls\n" %
                            (len(self.frames.frames),self.frames.total_events))
        self.console.configure(state="disabled")

    def _generic(self, tab):
        self._label(self.body, tab, bg="#f6f6f7", anchor="w",
                    font=("Arial", 12, "bold")).pack(fill="x", ipady=10, padx=10)
        self._label(self.body, "No %s events in this Graphics recording" % tab.lower(),
                    bg="white", fg=MUTED).pack(pady=90)

    def _draw_timeline(self, multi=False):
        if not hasattr(self, "timeline") or not self.timeline.winfo_exists():
            return
        c=self.timeline
        c.delete("all")
        width=max(400,c.winfo_width())
        frames=list(self.frames.frames)
        n=max(len(frames),1)
        pad=180 if multi else 45
        upper=62 if multi else 42
        if multi:
            for i,(name,color) in enumerate((("Screenshots","#34333f"),
                ("Layout & Rendering",GREEN),("JavaScript & Events",PURPLE),
                ("CPU",GREEN))):
                y=42+i*62
                c.create_text(12,y+8,text=name,fill=TEXT,anchor="w",font=("Arial",10))
                c.create_line(pad,y-6,width,y-6,fill=EDGE)
                for k in range(min(n,250)):
                    x=pad+(width-pad)*(k+0.5)/n
                    c.create_rectangle(x-2,y-1,x+2,y+25,fill=color,outline="")
        else:
            for k in range(min(n,500)):
                x=pad+(width-pad-15)*(k+0.5)/n
                color="#78a9df" if k==self.selected_frame else "#5a5968"
                c.create_rectangle(x-3,25,x+3,74,fill=color,outline="")
                if k%max(1,n//12)==0:
                    c.create_text(x,91,text=str(k+1),font=("Arial",9),fill=MUTED)
            c.create_text(13,10,text="Recording",fill=MUTED,anchor="nw")
            c.create_line(pad,103,width,103,fill=EDGE)

    def _update_frames(self):
        if self.tab!="Graphics" or not hasattr(self,"frame_list"):
            return
        frames=list(self.frames.frames)
        self.frame_list.delete(0,"end")
        for i,frame in enumerate(frames):
            elapsed=sum(e.duration_ns for e in frame)/1e6
            self.frame_list.insert("end","▧  Frame %-5d    %8.3f ms" % (i+1,elapsed))
        if frames:
            self.selected_frame=min(self.selected_frame,len(frames)-1)
            self.frame_list.selection_set(self.selected_frame)
        self.scale.configure(to=max(len(frames)-1,1))
        self.scale.set(self.selected_frame)
        self._render_frame()
        self._draw_timeline()

    def _slider(self,value):
        if not self.frames.frames or self.tab!="Graphics":
            return
        index=max(0,min(len(self.frames.frames)-1,int(round(float(value)))))
        if index!=self.selected_frame:
            self.select_frame(index)

    def _select_list(self,event):
        selection=self.frame_list.curselection()
        if selection:
            self.select_frame(selection[0])

    def _select_timeline(self,event):
        n=len(self.frames.frames)
        if n:
            self.select_frame(min(n-1,max(0,int((event.x-45)/max(1,self.timeline.winfo_width()-60)*n))))

    def select_frame(self,index):
        if not self.frames.frames:
            return
        self.selected_frame=min(max(index,0),len(self.frames.frames)-1)
        self._render_frame()
        self._draw_timeline()
        if hasattr(self,"frame_list"):
            self.frame_list.selection_clear(0,"end")
            self.frame_list.selection_set(self.selected_frame)
            self.frame_list.see(self.selected_frame)
        if hasattr(self,"scale"):
            self.scale.set(self.selected_frame)

    def _render_frame(self):
        if self.tab!="Graphics" or not self.frames.frames:
            return
        frame=list(self.frames.frames)[self.selected_frame]
        self.frame_label.configure(text="%d of %d" % (self.selected_frame+1,len(self.frames.frames)))
        for key in self.tree.get_children():
            self.tree.delete(key)
        start=frame[0].when_ns
        for i,event in enumerate(frame[:3000]):
            self.tree.insert("", "end", iid=str(i),
                values=("%04d  %s"%(i+1,event.name),
                        "%.3f ms"%((event.when_ns-start)/1e6),
                        "%.3f ms"%(event.duration_ns/1e6)))
        self.summary.configure(text="%d drawing calls\n%.3f ms in measured methods" %
                               (len(frame),sum(e.duration_ns for e in frame)/1e6))
        self._preview(frame)
        if frame:
            self.tree.selection_set("0")
            self._selected_call(None)

    def _preview(self,frame):
        canvas=self.preview
        if not canvas.winfo_exists():
            return
        canvas.delete("all")
        w=max(210,canvas.winfo_width()); h=max(250,canvas.winfo_height())
        if isinstance(self.reader,SharedMemoryTraceReader):
            # Read published RGB565 pixels directly from the versioned SHM
            # mapping. No data is requested from, or serialized by, the VM.
            raw=self.reader.framebuffer()
            if raw is not None:
                try:
                    from PIL import Image, ImageTk
                    picture=Image.frombytes("RGB",(320,528),raw,"raw","BGR;16")
                    factor=min((w-20)/320,(h-20)/528)
                    size=(max(1,int(320*factor)),max(1,int(528*factor)))
                    picture=picture.resize(size,Image.Resampling.NEAREST)
                    self.preview_picture=ImageTk.PhotoImage(picture)
                    canvas.create_image(w/2,h/2,image=self.preview_picture)
                    return
                except (ImportError,ValueError):
                    # Fall back to geometry when optional Pillow is missing.
                    pass
        # A command footprint preview for trace-only builds, not raster output.
        scale=min((w-22)/320,(h-22)/528)
        ox=(w-320*scale)/2;oy=(h-528*scale)/2
        canvas.create_rectangle(ox,oy,ox+320*scale,oy+528*scale,
                                fill="#ffffff",outline="#bcbfc2")
        for event in frame[-1500:]:
            x,y,a,b=(list(event.args)+[0,0,0,0])[:4]
            if event.name=="drect":
                canvas.create_rectangle(ox+x*scale,oy+y*scale,ox+a*scale,oy+b*scale,
                                        outline=GREEN,width=1)
            elif event.name=="dpixel":
                canvas.create_rectangle(ox+x*scale,oy+y*scale,
                                        ox+x*scale+2,oy+y*scale+2,
                                        fill="#315785",outline="")
            elif event.name=="dline":
                canvas.create_line(ox+x*scale,oy+y*scale,ox+a*scale,oy+b*scale,
                                   fill="#7c9fd1")
        canvas.create_text(8,h-10,text="Trace geometry (not a framebuffer)",
                           anchor="sw",font=("Arial",9),fill=MUTED)

    def _selected_call(self,event):
        if not self.frames.frames or not hasattr(self,"tree"):
            return
        selection=self.tree.selection()
        if not selection:
            return
        frame=list(self.frames.frames)[self.selected_frame]
        pos=int(selection[0])
        if pos>=len(frame):
            return
        call=frame[pos]
        self.details.delete("1.0","end")
        self.details.insert("end","Method: %s\n"%call.name)
        self.details.insert("end","Duration: %.4f ms\n"%(call.duration_ns/1e6))
        self.details.insert("end","Timestamp: %.3f ms\n"%(call.when_ns/1e6))
        if call.args:
            self.details.insert("end","Arguments: %s\n"%(", ".join(map(str,call.args))))

    def toggle_record(self):
        enabled=not self.recording
        if isinstance(self.reader, SharedMemoryTraceReader):
            self.reader.recording(enabled)
        self.recording=enabled
        self.record_btn.configure(text="■ Stop" if enabled else "● Record",
                                  fg="#b72e2e" if enabled else "#dc5657")
        self.status.configure(text="Recording" if enabled else "Recording stopped")

    def export(self):
        name=filedialog.asksaveasfilename(defaultextension=".json",
                filetypes=[("JSON recordings","*.json")])
        if not name:
            return
        frames=[[{"name":e.name,"duration_ns":e.duration_ns,
                  "when_ns":e.when_ns,"args":e.args}
                 for e in frame] for frame in self.frames.frames]
        Path(name).write_text(json.dumps({"frames":frames},indent=2)+"\n",
                              encoding="utf-8")

    def import_trace(self):
        name=filedialog.askopenfilename(filetypes=[("Draw trace","*.draw *.bin"),("All","*")])
        if not name:
            return
        try:
            new_reader=FileTraceReader(name)
            events=new_reader.read()
            self.frames=FrameStore()
            self.frames.append(events)
            self.selected_frame=0
            self.status.configure(text="%d frames imported"%len(self.frames.frames))
            self._update_frames()
        except Exception as error:
            messagebox.showerror("Import failed",str(error))

    def _drain(self):
        received=0
        try:
            while received<30:
                batch=self.messages.get_nowait()
                if isinstance(batch,Exception):
                    self.status.configure(text="Reader: %s"%batch)
                elif self.recording or not isinstance(self.reader,SharedMemoryTraceReader):
                    self.frames.append(batch)
                    received+=1
        except queue.Empty:
            pass
        if received:
            self.status.configure(text="%d frames · %d draw calls" %
                                 (len(self.frames.frames),self.frames.total_events))
            if self.tab=="Graphics":
                at_end=self.selected_frame >= max(0,len(self.frames.frames)-received-1)
                if at_end:
                    self.selected_frame=max(0,len(self.frames.frames)-1)
                self._update_frames()
            elif self.tab=="Timelines":
                self._draw_timeline(multi=True)
        if self.root.winfo_exists():
            self.root.after(50,self._drain)

    def _make_demo(self):
        ts=1000000000000
        ops=("dclear","dtext","drect","dpixel","dpixel","dline","dupdate")
        for frame in range(68):
            for i,kind in enumerate(ops):
                args=(8+i*6,30+frame%14,22+i*8,150) if kind!="dupdate" else (0,0,0,0)
                self.frames.append([DrawEvent(ts,kind,(60+i*23)*1000,args)])
                ts+=1400000
            ts+=28000000
        self.selected_frame=15
        self.status.configure(text="Demo · 68 captured frames")

    def _close(self):
        if self.worker:
            self.worker.stop()
        elif self.reader:
            self.reader.close()
        self.root.destroy()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    group=p.add_mutually_exclusive_group()
    group.add_argument("--trace",type=Path,help="PE_DRAW_TRACE recording file")
    group.add_argument("--shm",type=Path,help="full Windows PE_MAP screen.mmap")
    group.add_argument("--demo",action="store_true",help="show built-in example recording")
    p.add_argument("--source",type=Path,help="program to inspect in Sources tab")
    p.add_argument("--screenshot",type=Path,help="capture UI screenshot for CI")
    args=p.parse_args()
    reader=FileTraceReader(args.trace) if args.trace else (
        SharedMemoryTraceReader(args.shm) if args.shm else None)
    root=tk.Tk()
    app=Inspector(root,reader=reader,source=args.source,demo=args.demo)
    if args.screenshot:
        def capture():
            from PIL import ImageGrab
            root.update_idletasks()
            x,y=root.winfo_rootx(),root.winfo_rooty()
            args.screenshot.parent.mkdir(parents=True,exist_ok=True)
            ImageGrab.grab(bbox=(x,y,x+root.winfo_width(),y+root.winfo_height())).save(args.screenshot)
            root.after(200,root.destroy)
        root.after(650,capture)
    root.mainloop()

if __name__=="__main__":
    main()

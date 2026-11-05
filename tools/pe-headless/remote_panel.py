"""Compact USB packet panel used by the pe-headless Remote tab.

The producer captures up to 64 KiB of each packet for bounded hex inspection.
Uses drawn Tk PhotoImage arrows, not font-dependent Unicode symbols.
"""
import tkinter as tk
from tkinter import ttk

def direction(item):
    label=str(item.get("direction",""))
    sent=label.startswith("MicroPython") or label.startswith("PY ->")
    return sent, "PY -> Host" if sent else "PY <- Host"

def hexdump(item):
    data=item.get("payload_hex") or item.get("data_hex") or item.get("preview") or ""
    try:
        raw=bytes.fromhex(data)
    except (TypeError,ValueError):
        raw=b""
    size=int(item.get("size") or len(raw))
    lines=["%s | %s | %d B"%(item.get("kind","USB"),direction(item)[1],size),""]
    for address in range(0,len(raw),16):
        chunk=raw[address:address+16]
        text=" ".join("%02X"%x for x in chunk)
        ascii_text="".join(chr(x) if 32<=x<127 else "." for x in chunk)
        lines.append("%08X  %-47s |%-16s|"%(address,text,ascii_text))
    if not raw:
        lines.append("No payload bytes captured")
    elif len(raw)<size:
        lines.append("... %d additional bytes were not captured"%(size-len(raw)))
    return "\n".join(lines)

def arrow(outbound):
    image=tk.PhotoImage(width=16,height=16)
    color="#339257" if outbound else "#388ac4"
    for y in range(3,13):
        image.put(color,(8,y))
    for n in range(5):
        y=3+n if outbound else 12-n
        image.put(color,(8-n,y))
        image.put(color,(8+n,y))
    return image

class RemotePanel:
    def __init__(self,parent,has_log=False):
        self.root=parent
        self.events=[]
        self.selected=None
        self.images=(arrow(True),arrow(False))
        self.status=tk.Label(parent,text="USB packet trace | Serial: not implemented",
                             font=("Segoe UI",10),bg="#fafafa",fg="#7d858e",
                             anchor="w",padx=12,pady=8)
        self.status.pack(fill="x")
        filters=tk.Frame(parent,bg="white")
        filters.pack(fill="x",padx=12,pady=8)
        tk.Label(filters,text="USB",bg="white",font=("Segoe UI",10,"bold")).pack(side="left",padx=(2,10))
        self.direction=tk.StringVar(value="All")
        combo=ttk.Combobox(filters,width=10,textvariable=self.direction,
                           state="readonly",values=("All","Sent","Received"))
        combo.pack(side="left")
        combo.bind("<<ComboboxSelected>>",lambda e:self.render())
        tk.Label(filters,text="Filter",bg="white").pack(side="left",padx=(15,6))
        self.search=tk.StringVar()
        entry=ttk.Entry(filters,textvariable=self.search)
        entry.pack(side="left",fill="x",expand=True)
        self.search.trace_add("write",lambda *_:self.render())
        self.panes=ttk.Panedwindow(parent,orient="horizontal")
        self.panes.pack(fill="both",expand=True,padx=10,pady=(0,8))
        left=ttk.Frame(self.panes)
        right=ttk.Frame(self.panes)
        self.panes.add(left,weight=1)
        self.panes.add(right,weight=1)
        self.root.after_idle(lambda:self.panes.sashpos(0,530))
        cols=("time","direction","kind","length")
        self.tree=ttk.Treeview(left,columns=cols,show="tree headings",selectmode="browse")
        self.tree.heading("#0",text="")
        self.tree.column("#0",width=30,stretch=False)
        for key,text,width in (("time","Time",125),("direction","Direction",100),
                               ("kind","Packet",115),("length","Length",75)):
            self.tree.heading(key,text=text)
            self.tree.column(key,width=width,stretch=key=="kind")
        self.tree.tag_configure("sent",foreground="#328d55")
        self.tree.tag_configure("recv",foreground="#3688bd")
        scrollbar=ttk.Scrollbar(left,orient="vertical",command=self.tree.yview)
        scrollbar.pack(side="right",fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(fill="both",expand=True)
        self.tree.bind("<<TreeviewSelect>>",self.select)
        self.tree.bind("<Double-Button-1>",self.popup)
        tk.Label(right,text="Packet bytes | Hex + ASCII",bg="#fafafa",
                 font=("Segoe UI",10,"bold"),padx=9,pady=9,anchor="w").pack(fill="x")
        self.detail=tk.Text(right,wrap="none",font=("Consolas",10),
                 bg="#fcfcfe",fg="#343a42",relief="flat",padx=8,pady=8)
        self.detail.pack(fill="both",expand=True)
        self.detail.configure(state="disabled")
        scroll=ttk.Scrollbar(right,orient="horizontal",command=self.detail.xview)
        scroll.pack(fill="x")
        self.detail.configure(xscrollcommand=scroll.set)
        tk.Label(right,text="Double-click a packet for full-size hex view",
                 bg="white",fg="#7c838b",anchor="w",padx=8,pady=7).pack(fill="x")

    def update(self,events):
        self.events=list(events)[-1000:]
        self.render()

    def render(self):
        if not self.tree.winfo_exists():
            return
        old=self.selected
        self.tree.delete(*self.tree.get_children())
        search=self.search.get().strip().lower()
        selected=self.direction.get()
        visible=0
        for i,item in enumerate(self.events):
            outgoing,short=direction(item)
            if selected=="Sent" and not outgoing:continue
            if selected=="Received" and outgoing:continue
            haystack=" ".join(str(item.get(key,"")) for key in
                ("kind","direction","time","preview","payload_hex")).lower()
            if search and search not in haystack:continue
            stamp=str(item.get("time",""))
            if "T" in stamp:
                stamp=stamp.split("T",1)[1].rstrip("Z")
            self.tree.insert("","end",iid=str(i),
               image=self.images[0 if outgoing else 1],
               tags=("sent" if outgoing else "recv",),
               values=(stamp,short,item.get("kind","USB"),
                       str(item.get("size",0))+" B"))
            visible+=1
        self.status.configure(text="%d USB packets | Serial: not implemented"%visible)
        if old is not None and str(old) in self.tree.get_children():
            self.tree.selection_set(str(old))
            self.select()
        elif self.tree.get_children():
            self.tree.selection_set(self.tree.get_children()[0])
            self.select()

    def select(self,event=None):
        chosen=self.tree.selection()
        if not chosen:return
        self.selected=int(chosen[0])
        item=self.events[self.selected]
        self.detail.configure(state="normal")
        self.detail.delete("1.0","end")
        self.detail.insert("1.0",hexdump(item))
        self.detail.configure(state="disabled")

    def popup(self,event=None):
        chosen=self.tree.selection()
        if not chosen:return
        item=self.events[int(chosen[0])]
        window=tk.Toplevel(self.root)
        window.title("USB packet - "+str(item.get("kind","data")))
        window.geometry("880x550")
        text=tk.Text(window,wrap="none",font=("Consolas",10),
             bg="#fafbfc",fg="#343a42",padx=10,pady=10)
        text.pack(fill="both",expand=True)
        text.insert("1.0",hexdump(item))
        text.configure(state="disabled")

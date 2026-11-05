#!/usr/bin/env python3
"""Trace virtual calculator USB streams without modifying the interpreter.

The proxy listens on localhost and forwards to the Linux gint.USB server:
  python tools/pe-headless/usb_trace_proxy.py --listen 8766 --target 8765 \
      --log /tmp/usb.jsonl
  python tools/pe-headless/spu_tcp.py --port 8766 exec "print(6*7)"
  python tools/pe-headless/view.py --remote-log /tmp/usb.jsonl

Messages are decoded as the spu-tools >II packet format where possible.
Data previews are bounded. No raw memory packets are executed by this tool.
"""
import argparse
import datetime as dt
import json
from pathlib import Path
import selectors
import socket
import struct
import time

KINDS={
    0x1001:"PING",0x1002:"STOP",0x1003:"EXEC",0x1004:"STATUS",
    0x2001:"WRITE_8",0x2002:"WRITE_16",0x2003:"WRITE_32",
    0x2021:"MASK_8",0x2022:"MASK_16",0x2023:"MASK_32",
    0x2011:"READ_8",0x2012:"READ_16",0x2013:"READ_32",
    0x80000001:"STREAM",
}
HEADER=struct.Struct(">II")
MAX_PACKET=1024*1024

class PacketDecoder:
    def __init__(self, direction, log):
        self.direction=direction
        self.log=log
        self.data=bytearray()
        self.raw=False

    def feed(self, chunk):
        self.data.extend(chunk)
        while True:
            if self.raw:
                self._log("RAW",self.data)
                self.data.clear()
                break
            if len(self.data)<8:
                break
            kind,size=HEADER.unpack_from(self.data)
            if kind not in KINDS and (kind&0xF0000000)!=0xF0000000:
                self.raw=True
                continue
            if size>MAX_PACKET:
                # Avoid storing or trusting a corrupt packet size.
                self._log("INVALID_HEADER",self.data[:8])
                self.raw=True
                del self.data[:8]
                continue
            if len(self.data)<size+8:
                break
            payload=bytes(self.data[8:8+size])
            del self.data[:size+8]
            self._log(KINDS.get(kind,"ERROR_0x%08X"%kind),payload,kind)
    def _log(self,kind,payload,packet_type=None):
        self.log({"time":dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds"),
                  "direction":self.direction,"kind":kind,
                  "size":len(payload),
                  "preview":bytes(payload[:96]).hex(" "),
                  "packet_type":packet_type})

def proxy(listen, upstream_host, target_port, listen_port, log, stop_after_one=False, ready=None):
    for host in (listen,upstream_host):
        if host not in ("127.0.0.1","localhost"):
            raise ValueError("USB virtual transport must bind to localhost only")
    with Path(log).open("a",encoding="utf-8",buffering=1) as trace:
        def write(record):
            trace.write(json.dumps(record,ensure_ascii=False)+"\n")
        with socket.socket() as server:
            server.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
            server.bind(("127.0.0.1",listen_port))
            server.listen(4)
            if ready is not None:
                ready(server.getsockname()[1])
            while True:
                client,_=server.accept()
                try:
                    upstream=socket.create_connection((upstream_host,target_port),timeout=10)
                except Exception:
                    client.close()
                    if stop_after_one:raise
                    continue
                with client,upstream,selectors.DefaultSelector() as watch:
                    client.setblocking(False)
                    upstream.setblocking(False)
                    a=PacketDecoder("Host → MicroPython",write)
                    b=PacketDecoder("MicroPython → Host",write)
                    watch.register(client,selectors.EVENT_READ,(upstream,a))
                    watch.register(upstream,selectors.EVENT_READ,(client,b))
                    while True:
                        readable=watch.select(timeout=0.25)
                        if not readable:
                            continue
                        close=False
                        for key,_ in readable:
                            src=key.fileobj
                            dest,decoder=key.data
                            try:
                                chunk=src.recv(16384)
                            except BlockingIOError:
                                continue
                            if not chunk:
                                close=True
                                break
                            decoder.feed(chunk)
                            dest.setblocking(True)
                            try:
                                dest.sendall(chunk)
                            finally:
                                dest.setblocking(False)
                        if close:
                            break
                if stop_after_one:
                    return

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--port",type=int,default=8766)
    p.add_argument("--target",type=int,default=8765)
    p.add_argument("--listen",default="127.0.0.1")
    p.add_argument("--upstream-host",default="127.0.0.1")
    p.add_argument("--log",required=True,type=Path)
    args=p.parse_args()
    for x in (args.port,args.target):
        if not 1<=x<=65535:
            p.error("ports must be 1..65535")
    print("Remote USB trace: tcp://127.0.0.1:%d -> :%d | %s" %
          (args.port,args.target,args.log),flush=True)
    proxy(args.listen,args.upstream_host,args.target,args.port,args.log)

if __name__=="__main__":
    main()

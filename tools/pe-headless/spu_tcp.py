#!/usr/bin/env python3
"""Use spu-tools' normal remote USBClient over localhost TCP, no USB hardware.

  python tools/pe-headless/spu_tcp.py --port 8765 ping
  python tools/pe-headless/spu_tcp.py --port 8765 exec "print(2 + 2)"
  python tools/pe-headless/spu_tcp.py --port 8765 --run ../spu-tools/run_demo.py ...

With --run, the original spu-tools USBClient.connect() is patched to use a
TCP byte-stream device. SPU RAM/register operations are *not* emulated.
"""
import argparse
import runpy
import socket
import struct
import sys
from pathlib import Path

class SocketUSBDevice:
    """PyUSB-style read/write shim for spu-tools' unchanged USBClient."""

    def __init__(self, host="127.0.0.1", port=8765):
        if host not in ("127.0.0.1", "localhost"):
            raise ValueError("remote device must remain on loopback")
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=5)
        self.sock.settimeout(10)

    def write(self, endpoint, data, timeout=2000):
        if endpoint != 0x02:
            raise ValueError("expected USB bulk OUT endpoint 0x02")
        return self.sock.send(bytes(data))

    def read(self, endpoint, size, timeout=2000):
        if endpoint != 0x81:
            raise ValueError("expected USB bulk IN endpoint 0x81")
        self.sock.settimeout(None if timeout is None else timeout/1000)
        try:
            return self.sock.recv(size)
        except socket.timeout as err:
            try:
                from usb.core import USBTimeoutError
                raise USBTimeoutError("virtual USB read timed out") from err
            except ImportError:
                raise TimeoutError("virtual USB read timed out") from err

    def close(self):
        self.sock.close()


class FramedClient:
    def __init__(self, port=8765):
        self.conn=socket.create_connection(("127.0.0.1",port),timeout=6)
        self.conn.settimeout(10)

    def __enter__(self):
        return self

    def __exit__(self,*unused):
        self.conn.close()

    def _exact(self,n):
        out=bytearray()
        while len(out)<n:
            chunk=self.conn.recv(n-len(out))
            if not chunk:
                raise EOFError("virtual USB disconnected")
            out.extend(chunk)
        return bytes(out)

    def request(self,kind,data=b""):
        self.conn.sendall(struct.pack(">II",kind,len(data))+data)
        response,length=struct.unpack(">II",self._exact(8))
        payload=self._exact(length)
        if response!=kind:
            raise RuntimeError("Device rejected 0x%x: %s" %
                               (response,payload.decode("utf-8","replace")))
        return payload

    def ping(self):
        response=self.request(0x1001,b"spu-tools TCP")
        version=struct.unpack(">I",response[:4])[0]
        return version,response[4:]

    def exec(self,source):
        return self.request(0x1003,source.encode("utf-8")).decode("utf-8")


def launch_spu_tools(path,arguments,port):
    script=Path(path).resolve()
    sys.path.insert(0,str(script.parent))
    from comm.usbclient import USBClient
    original=USBClient.__dict__["connect"]

    def connect(cls):
        return cls(SocketUSBDevice(port=port),64)
    USBClient.connect=classmethod(connect)
    sys.argv=[str(script)]+list(arguments)
    try:
        runpy.run_path(str(script),run_name="__main__")
    finally:
        USBClient.connect=original


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--port",type=int,default=8765)
    p.add_argument("--run",type=Path,help="run unchanged spu-tools script")
    p.add_argument("command",nargs="?",choices=("ping","exec","status","stop"))
    p.add_argument("rest",nargs=argparse.REMAINDER)
    args, extras=p.parse_known_args()
    if args.run:
        launch_spu_tools(args.run,([args.command] if args.command else [])+args.rest+extras,args.port)
        return
    if extras:
        p.error("unexpected arguments: "+" ".join(extras))
    if args.command is None:
        p.error("select ping, exec, status, stop or --run")
    with FramedClient(args.port) as client:
        if args.command=="ping":
            print(client.ping())
        elif args.command=="exec":
            print(client.exec(" ".join(args.rest)),end="")
        elif args.command=="status":
            client.request(0x1004," ".join(args.rest).encode("utf-8"))
        elif args.command=="stop":
            client.request(0x1002)

if __name__=="__main__":
    main()

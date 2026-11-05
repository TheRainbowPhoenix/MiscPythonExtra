"""Local CPChat fxlink response backend for an instrumented PythonExtra guest.

Windows: run Windows SHM usb_bridge.py on 8765, USB trace proxy on 8766,
then python tools/pe-headless/cpchat_backend.py --port 8766.

CPChat.py sends fxlink 'python/text' frames containing CMD|poll,
CMD|switch|<channel> or SAY|<message>. This backend sends small
SYS|SYNC, SYS|..., MSG|... responses. It is not a real chat service.
"""
import argparse
import datetime
import socket
import struct
import time

FXLINK=struct.Struct("<III16s16s")

def exact(sock,size):
    result=bytearray()
    while len(result)<size:
        part=sock.recv(size-len(result))
        if not part:
            raise EOFError("USB peer disconnected")
        result.extend(part)
    return bytes(result)

def packet(payload):
    return FXLINK.pack(0x100,len(payload),2048,b"python",b"text")+payload

def receive(sock):
    version,n,transfer,application,kind=FXLINK.unpack(exact(sock,44))
    if version!=0x100 or transfer!=2048 or n>1048576:
        raise ValueError("invalid fxlink header")
    if application.split(b"\\0",1)[0]!=b"python" or kind.split(b"\\0",1)[0]!=b"text":
        raise ValueError("unexpected CPChat fxlink stream")
    return exact(sock,n)

def response(command):
    text=command.decode("utf-8","replace").strip()
    if text=="CMD|poll":
        data=("SYS|SYNC|"+datetime.datetime.now().strftime("%H:%M:%S")+"\n").encode("ascii")
    elif text.startswith("CMD|switch|"):
        data=b"SYS|Switched\n"
    elif text.startswith("SAY|"):
        # Keep the response <64 total bytes for the original CPChat.py
        # single USB read. Messages sent by the guest are not truncated.
        data=("MSG|Bot|"+text[4:][:9]+"\n").encode("ascii","replace")
    else:
        data=b"SYS|Ready\n"
    return packet(data)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port",type=int,default=8766)
    args=parser.parse_args()
    deadline=time.monotonic()+15
    while True:
        try:
            s=socket.create_connection(("127.0.0.1",args.port),timeout=2)
            break
        except OSError:
            if time.monotonic()>deadline:
                raise RuntimeError("USB trace proxy not reachable")
            time.sleep(.1)
    with s:
        print("CPChat demo backend connected",flush=True)
        while True:
            try:
                command=receive(s)
                reply=response(command)
                print("PY -> Host:",command.decode("utf-8","replace").strip(),flush=True)
                s.sendall(reply)
            except (OSError,EOFError):
                return

if __name__=="__main__":
    main()

#!/usr/bin/env python3
"""Tests loopback USB forwarding and the Remote tab's packet log."""
import json
import socket
import struct
import tempfile
import threading
from pathlib import Path
import time
import unittest
from usb_trace_proxy import proxy
from remote_trace import load_events

def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1",0))
        return s.getsockname()[1]

def exact(sock,n):
    data=b""
    while len(data)<n:
        chunk=sock.recv(n-len(data))
        if not chunk:raise EOFError("unexpected end")
        data+=chunk
    return data

class ProxyTests(unittest.TestCase):
    def test_real_bidirectional_usb_packet_capture(self):
        target=free_port()
        source=free_port()
        ready=threading.Event()
        with tempfile.TemporaryDirectory() as td:
            log=Path(td)/"usb.jsonl"
            def server():
                with socket.socket() as listener:
                    listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
                    listener.bind(("127.0.0.1",target))
                    listener.listen(1)
                    ready.set()
                    conn,_=listener.accept()
                    with conn:
                        head=exact(conn,8)
                        kind,size=struct.unpack(">II",head)
                        self.assertEqual(kind,0x1003)
                        self.assertEqual(exact(conn,size),b"print(42)")
                        packet=struct.pack(">II",0x1003,3)+b"42\n"
                        conn.sendall(packet)
            worker=threading.Thread(target=server,daemon=True)
            worker.start()
            self.assertTrue(ready.wait(3))
            listening=threading.Event()
            observer=threading.Thread(target=proxy,
                args=("127.0.0.1","127.0.0.1",target,source,log),
                kwargs={"stop_after_one":True,"ready":lambda p:listening.set()},
                daemon=True)
            observer.start()
            self.assertTrue(listening.wait(3))
            with socket.create_connection(("127.0.0.1",source),timeout=3) as client:
                client.sendall(struct.pack(">II",0x1003,9)[:3])
                client.sendall(struct.pack(">II",0x1003,9)[3:]+b"print(42)")
                self.assertEqual(exact(client,11),struct.pack(">II",0x1003,3)+b"42\n")
            worker.join(3);observer.join(3)
            self.assertFalse(observer.is_alive())
            events=load_events(log)
            self.assertEqual([e["kind"] for e in events],["EXEC","EXEC"])
            self.assertEqual([e["size"] for e in events],[9,3])
            self.assertEqual(events[0]["direction"],"Host -> MicroPython")
            self.assertEqual(events[1]["direction"],"MicroPython -> Host")


    def test_cpchat_fxlink_frames_and_backend(self):
        from usb_trace_proxy import PacketDecoder
        from cpchat_backend import response, FXLINK
        captured=[]
        guest=PacketDecoder("MicroPython -> Host",captured.append)
        outgoing=FXLINK.pack(0x100,9,2048,b"python",b"text")+b"CMD|poll\n"
        for part in (outgoing[:2],outgoing[2:17],outgoing[17:]):
            guest.feed(part)
        self.assertEqual(len(captured),1)
        self.assertEqual(captured[0]["kind"],"fxlink python/text")
        self.assertEqual(bytes.fromhex(captured[0]["payload_hex"]),b"CMD|poll\n")
        answer=response(b"CMD|poll\n")
        self.assertLess(len(answer),64)
        host=PacketDecoder("Host -> MicroPython",captured.append)
        host.feed(answer[:10])
        host.feed(answer[10:])
        self.assertEqual(captured[1]["kind"],"fxlink python/text")
        self.assertTrue(bytes.fromhex(captured[1]["payload_hex"]).startswith(b"SYS|SYNC|"))

if __name__=="__main__":
    unittest.main()

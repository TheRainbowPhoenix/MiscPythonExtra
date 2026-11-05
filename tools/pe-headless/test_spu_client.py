#!/usr/bin/env python3
"""Check actual upstream spu-tools USBClient against the TCP gint.USB server."""
import argparse
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import time

from spu_tcp import SocketUSBDevice

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--exe",type=Path,required=True)
    p.add_argument("--server",type=Path,required=True)
    p.add_argument("--spu-tools",type=Path,required=True)
    a=p.parse_args()
    sys.path.insert(0,str(a.spu_tools.resolve()))
    from comm.usbclient import USBClient, DeviceError
    with socket.socket() as sock:
        sock.bind(("127.0.0.1",0))
        port=sock.getsockname()[1]
    env=dict(os.environ,PE_USB_PORT=str(port))
    child=subprocess.Popen([str(a.exe.resolve()),str(a.server.resolve())],
                           stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env)
    try:
        deadline=time.monotonic()+12
        dev=None
        while time.monotonic()<deadline:
            try:
                dev=SocketUSBDevice(port=port)
                break
            except OSError:
                if child.poll() is not None: break
                time.sleep(0.05)
        if dev is None: raise RuntimeError("Linux USB server did not open port")
        with USBClient(dev,64) as client:
            client.check_version()
            client.set_status("upstream client connected")
            assert client.exec_all("print(2*21)")=="42\n"
            assert client.exec_all("a=4")==""
            assert client.exec_all("print(a+5)")=="9\n"
            print("PASS: real spu-tools USBClient version, status and EXEC")
            try:
                client.read(0xFE2FFD00,4,32)
            except DeviceError as error:
                assert "not emulated" in str(error),str(error)
            else:
                raise AssertionError("unsafe DSP memory read should be rejected")
            print("PASS: unimplemented SPU register reads rejected")
            client.stop()
        out,err=child.communicate(timeout=8)
        assert child.returncode==0,(out,err)
        print("PASS: upstream spu-tools USBClient via TCP shim")
    finally:
        if child.poll() is None:
            child.kill()
            child.communicate(timeout=5)

if __name__=="__main__":
    main()

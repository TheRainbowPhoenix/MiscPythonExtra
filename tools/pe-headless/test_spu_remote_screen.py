#!/usr/bin/env python3
"""Native MicroPython + genuine spu-tools RemoteScreen end-to-end smoke test."""
import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys
import time


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--exe",type=Path,required=True)
    p.add_argument("--server",type=Path,required=True)
    p.add_argument("--spu-tools",type=Path,required=True)
    p.add_argument("--frames",type=int,default=8)
    args=p.parse_args()
    with socket.socket() as candidate:
        candidate.bind(("127.0.0.1",0))
        port=candidate.getsockname()[1]
    env=dict(os.environ,PE_USB_PORT=str(port))
    guest=subprocess.Popen([str(args.exe.resolve()),str(args.server.resolve())],
          env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    script=Path(__file__).with_name("run_spu_remote_screen.py").resolve()
    try:
        result=subprocess.run([sys.executable,str(script),
              "--spu-tools",str(args.spu_tools.resolve()),
              "--port",str(port),"--frames",str(args.frames),"--delay","0"],
              capture_output=True,text=True,timeout=35)
        if result.returncode!=0:
            raise AssertionError("remote screen failed: "+result.stdout+"\n"+result.stderr)
        assert "PASS: %d genuine spu-tools RemoteScreen frames"%args.frames in result.stdout,result.stdout
        stdout,stderr=guest.communicate(timeout=8)
        assert guest.returncode==0,(stdout,stderr)
        print(result.stdout.strip())
        print("PASS: native MicroPython gint.USB / upstream RemoteScreen")
    finally:
        if guest.poll() is None:
            guest.kill()
            guest.communicate(timeout=5)


if __name__=="__main__":
    main()

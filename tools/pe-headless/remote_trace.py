"""Read bounded, append-only USB Remote JSONL traces.

The producer is the standalone localhost proxy. The UI never consumes bytes
from a live USB socket or shares the VM's draw/graphics event ring.
"""
import json
from pathlib import Path

def load_events(path, max_lines=1000):
    source=Path(path)
    if not source.is_file():
        return []
    # Stay bounded even if a remote session emits a huge number of packets.
    with source.open("rb") as stream:
        size=stream.seek(0,2)
        stream.seek(max(0,size-4*1024*1024))
        if stream.tell():
            stream.readline()
        data=stream.readlines()
    out=[]
    for raw in data[-max_lines:]:
        try:
            event=json.loads(raw)
        except (ValueError,UnicodeDecodeError):
            continue
        if not isinstance(event,dict):
            continue
        out.append({key:event.get(key) for key in
                    ("time","direction","kind","size","preview","payload_hex","truncated","packet_type")})
    return out

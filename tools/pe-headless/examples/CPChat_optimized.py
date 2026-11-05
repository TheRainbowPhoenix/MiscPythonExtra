"""Lower-allocation CPChat using the original cinput widgets.

Run under the Windows fxcp_instrument host:
  python view.py examples/CPChat_optimized.py --exe bin/micropython.exe --usb-demo
The UI is redrawn only on visible state changes, not every 10ms poll.
"""
import gint
import time
import cinput

cinput.THEMES["light"]["accent"] = gint.C_RGB(22, 0, 0)
cinput.THEMES["light"]["txt_acc"] = gint.C_WHITE

MAX_HISTORY = 96
POLL_MS = 1000


def wrap_text(author, text, max_len=36):
    full = "%s: %s" % (author, text)
    return [full[i:i + max_len] for i in range(0, len(full), max_len)]


def main():
    theme = cinput.THEMES["light"]
    bg, accent, white = theme["modal_bg"], theme["accent"], theme["txt_acc"]
    black = gint.C_BLACK
    keyboard = cinput.Keyboard(enable_tabs=True, theme="light")
    chat = cinput.ListView((0, 30, 320, 198), [], row_h=25, theme="light")
    current_input = ""
    touch_latched = False
    last_sync = "Wait..."
    last_poll = time.ticks_ms()
    dirty = True
    receive_buffer = bytearray()
    pending_read = False
    events = []

    def append(text):
        chat.items.append({"text": text, "type": "item"})
        if len(chat.items) > MAX_HISTORY:
            del chat.items[:len(chat.items) - MAX_HISTORY]
        chat.recalc_layout()
        chat.scroll_y = chat.max_scroll

    with gint.USB() as usb:
        while True:
            now = time.ticks_ms()
            if time.ticks_diff(now, last_poll) >= POLL_MS:
                try:
                    packet = b"CMD|poll\n"
                    usb.fxlink_header("python", "text", len(packet))
                    usb.write(packet)
                    usb.flush()
                    pending_read = True
                except OSError:
                    pass
                last_poll = now

            if pending_read:
                try:
                    chunk = usb.read(64, 0)
                    if chunk:
                        receive_buffer.extend(chunk)
                    while len(receive_buffer) >= 44:
                        version = int.from_bytes(receive_buffer[:4], "little")
                        length = int.from_bytes(receive_buffer[4:8], "little")
                        transfer = int.from_bytes(receive_buffer[8:12], "little")
                        if version != 256 or transfer != 2048 or length > 4096:
                            del receive_buffer[:1]
                            continue
                        if len(receive_buffer) < 44 + length:
                            break
                        payload = bytes(receive_buffer[44:44 + length])
                        del receive_buffer[:44 + length]
                        pending_read = False
                        for line in payload.split(b"\n"):
                            if not line:
                                continue
                            text = line.decode("ascii", "ignore").strip()
                            if text == "SYS|CLEAR":
                                chat.items.clear()
                                chat.recalc_layout()
                                chat.scroll_y = 0
                                dirty = True
                            elif text.startswith("SYS|SYNC|"):
                                updated = text.split("|", 2)[2]
                                if updated != last_sync:
                                    last_sync = updated
                                    dirty = True
                            elif text.startswith("SYS|"):
                                append("[*] " + text.split("|", 1)[1])
                                dirty = True
                            elif text.startswith("MSG|"):
                                parts = text.split("|", 2)
                                if len(parts) == 3:
                                    for wrapped in wrap_text(parts[1], parts[2]):
                                        append(wrapped)
                                    dirty = True
                except OSError:
                    pending_read = False

            events.clear()
            event = gint.pollevent()
            while event.type != gint.KEYEV_NONE:
                if event.type == gint.KEYEV_DOWN and event.key == gint.KEY_EXIT:
                    return
                events.append(event)
                event = gint.pollevent()

            if events:
                # Preserve all cinput input and layout behavior.
                chat.update(events)
                dirty = True
                for event in events:
                    if event.type == gint.KEYEV_TOUCH_UP:
                        touch_latched = False
                        keyboard.last_key = None
                    elif event.type == gint.KEYEV_TOUCH_DOWN and not touch_latched:
                        touch_latched = True
                        if event.y >= 268:
                            key = keyboard.update(event)
                            if key == "ENTER":
                                if current_input.startswith("/switch "):
                                    channel = current_input.split(" ", 1)[1]
                                    packet = ("CMD|switch|" + channel + "\n").encode("utf-8")
                                else:
                                    packet = ("SAY|" + current_input + "\n").encode("utf-8")
                                try:
                                    usb.fxlink_header("python", "text", len(packet))
                                    usb.write(packet)
                                    usb.flush()
                                    pending_read = True
                                except OSError:
                                    pass
                                current_input = ""
                            elif key == "BACKSPACE":
                                current_input = current_input[:-1]
                            elif key and len(key) == 1:
                                current_input += key

            if dirty:
                gint.dclear(bg)
                gint.drect(0, 0, 320, 30, accent)
                gint.dtext(5, 8, white, "Planet-Casio Chat")
                gint.dtext(220, 8, white, last_sync)
                chat.draw()
                gint.drect(0, 228, 320, 268, bg)
                gint.dhline(228, black)
                gint.dtext(5, 240, black, current_input + "_")
                keyboard.draw()
                gint.dupdate()
                gint.cleareventflips()
                dirty = False

            # Responsive touch polling without expensive idle redraws.
            time.sleep(0.025)


if __name__ == "__main__":
    main()

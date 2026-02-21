from gint import *
import cinput
import mobi
import time

# --- Configuration ---
THEME = 'light'
HEADER_H = 40
SCREEN_W = 320
SCREEN_H = 528

def draw_header(title):
    t = cinput.get_theme(THEME)
    drect(0, 0, SCREEN_W, HEADER_H, t['accent'])
    
    # Draw text twice with an offset of 1 to create a "bold" effect
    dtext_opt(SCREEN_W//2, HEADER_H//2, t['txt_acc'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, title, -1)
    dtext_opt(SCREEN_W//2 + 1, HEADER_H//2, t['txt_acc'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, title, -1)

class ReaderActivity:
    def __init__(self, book: mobi.Book):
        self.book = book
        self.current_record = 1
        self.max_record = book.mobi.get('first_image_idx', 2) - 1
        self.text_lines = []
        self.scroll_y = 0
        self.load_record()

    def load_record(self):
        self.text_lines = []
        self.scroll_y = 0
        raw_text = self.book.get_chapter_text(self.current_record)
        
        # If the record was skipped (e.g., an INDX block), mark it clearly
        if not raw_text.strip():
            self.text_lines.append("[System Record or Empty Page]")
            return

        # Smart word wrapping using dsize
        space_w, _ = dsize(" ", None)
        max_w = SCREEN_W - 10 # 5px margin on left and right
        
        # Preserve newlines by splitting into paragraphs first
        paragraphs = raw_text.replace('\r\n', '\n').split('\n')
        
        for para in paragraphs:
            # Detect explicit empty lines/spacing
            if not para.strip():
                self.text_lines.append("")
                continue
                
            words = para.split()
            current_line = ""
            current_w = 0
            
            for word in words:
                word_w, _ = dsize(word, None)
                
                # Wrap if adding this word overflows the line width
                if current_w + space_w + word_w > max_w and current_w > 0:
                    self.text_lines.append(current_line)
                    current_line = word
                    current_w = word_w
                else:
                    if current_line:
                        current_line += " " + word
                        current_w += space_w + word_w
                    else:
                        current_line = word
                        current_w = word_w
                        
            # Append the very last line of the paragraph
            if current_line:
                self.text_lines.append(current_line)

    def draw(self):
        t = cinput.get_theme(THEME)
        dclear(t['modal_bg'])
        draw_header(f"Reading: Page {self.current_record}/{self.max_record}")
        
        # Next Page Toolbar Button (Flat Right Arrow)
        if self.current_record < self.max_record:
            col = t['txt_acc']
            btn_x = SCREEN_W - 40
            cy = HEADER_H // 2
            dline(btn_x + 15, cy - 6, btn_x + 23, cy, col)
            dline(btn_x + 15, cy + 6, btn_x + 23, cy, col)
            dline(btn_x + 14, cy - 6, btn_x + 22, cy, col)
            dline(btn_x + 14, cy + 6, btn_x + 22, cy, col)

        # Prev Page Toolbar Button (Flat Left Arrow)
        if self.current_record > 1:
            col = t['txt_acc']
            btn_x = 0
            cy = HEADER_H // 2
            dline(btn_x + 25, cy - 6, btn_x + 17, cy, col)
            dline(btn_x + 25, cy + 6, btn_x + 17, cy, col)
            dline(btn_x + 26, cy - 6, btn_x + 18, cy, col)
            dline(btn_x + 26, cy + 6, btn_x + 18, cy, col)

        y = HEADER_H + 10
        start_line = self.scroll_y
        end_line = min(len(self.text_lines), start_line + 25)
        
        for i in range(start_line, end_line):
            # Safe draw avoiding rendering empty strings if any
            if self.text_lines[i]:
                dtext(5, y, t['txt'], self.text_lines[i])
            y += 18
            
        # Footer
        msg = "[↑/↓] Scroll | [←/→] Prev/Next Page | [EXIT] Quit"
        dtext_opt(SCREEN_W//2, SCREEN_H - 15, t['txt_dim'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, msg, -1)
        dupdate()

    def run(self):
        clearevents()
        cleareventflips()
        touch_latched = False
        
        while True:
            self.draw()
            cleareventflips()
            
            ev = pollevent()
            events = []
            while ev.type != KEYEV_NONE:
                events.append(ev)
                ev = pollevent()
            
            if keypressed(KEY_EXIT) or keypressed(KEY_DEL):
                break
            elif keypressed(KEY_DOWN):
                if self.scroll_y < max(0, len(self.text_lines) - 25):
                    self.scroll_y += 5
            elif keypressed(KEY_UP):
                if self.scroll_y > 0:
                    self.scroll_y -= 5
            elif keypressed(KEY_RIGHT):
                if self.current_record < self.max_record:
                    self.current_record += 1
                    self.load_record()
            elif keypressed(KEY_LEFT):
                if self.current_record > 1:
                    self.current_record -= 1
                    self.load_record()
                    
            for e in events:
                if e.type == KEYEV_TOUCH_DOWN:
                    touch_latched = True
                elif e.type == KEYEV_TOUCH_UP:
                    if touch_latched:
                        touch_latched = False
                        
                        # Detect toolbar taps (Top Header Area)
                        if e.y < HEADER_H:
                            # Tapped Next Page
                            if e.x > SCREEN_W - 60 and self.current_record < self.max_record:
                                self.current_record += 1
                                self.load_record()
                            # Tapped Prev Page
                            elif e.x < 60 and self.current_record > 1:
                                self.current_record -= 1
                                self.load_record()
            
            time.sleep(0.01)

def show_book_info(book: mobi.Book):
    t = cinput.get_theme(THEME)
    clearevents()
    
    while True:
        dclear(t['modal_bg'])
        draw_header("Book Info")
        
        margin = 15
        y = 60
        
        dtext(margin, y, t['txt_dim'], "Title:")
        y += 20
        dtext(margin + 10, y, t['txt'], book.title[:35])
        
        y += 40
        dtext(margin, y, t['txt_dim'], "Author:")
        y += 20
        dtext(margin + 10, y, t['txt'], book.author[:35])
        
        y += 40
        dtext(margin, y, t['txt_dim'], "Language:")
        y += 20
        dtext(margin + 10, y, t['txt'], book.language)
        
        y += 40
        dtext(margin, y, t['txt_dim'], "Records:")
        y += 20
        dtext(margin + 10, y, t['accent'], str(book.db.record_count))

        dtext_opt(SCREEN_W//2, SCREEN_H - 50, t['txt'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "[EXE] Read Book", -1)
        dtext_opt(SCREEN_W//2, SCREEN_H - 30, t['txt_dim'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "[EXIT] Back", -1)
        
        dupdate()
        ev = getkey()
        if ev.key == KEY_EXIT:
            break
        elif ev.key == KEY_EXE:
            reader = ReaderActivity(book)
            reader.run()

def main():
    global THEME
    while True:
        t = cinput.get_theme(THEME)
        dclear(t['modal_bg'])
        draw_header("Mobi Library")
        
        opts = [
            "Open custom file...",
            "Switch Theme",
            "Exit"
        ]
        
        choice = cinput.pick(opts, "Menu", theme=THEME)
        
        if not choice or choice == "Exit":
            break
            
        elif choice == "Switch Theme":
            THEME = 'dark' if THEME == 'light' else 'light'
            
        elif choice == "Open custom file...":
            filepath = cinput.input("Enter .mobi file path:", type="text", theme=THEME)
            if filepath:
                try:
                    book = mobi.Book(filepath)
                    if book and book.is_a_book:
                        show_book_info(book)
                    else:
                        raise ValueError()
                except Exception:
                    dclear(t['modal_bg'])
                    draw_header("Error")
                    dtext_opt(SCREEN_W//2, SCREEN_H//2, t['txt'], C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "Invalid or Missing File!", -1)
                    dupdate()
                    getkey()

main()
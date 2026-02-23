from gint import *
import tvst
import time
import struct
import math
import random
import array

# Colors
C_BG    = C_RGB(4, 5, 6)
C_GRID  = C_RGB(8, 9, 10)
C_NOTE  = C_RGB(16, 31, 16) # Classic Green (3xOsc)
C_DRUM  = C_RGB(31, 16, 16) # Red (Drums)
C_SAW   = C_RGB(16, 16, 31) # Blue (Supersaw)
C_UI    = C_RGB(10, 12, 14)
C_TEXT  = C_RGB(31, 31, 31)
C_TEXT_DIM  = C_RGB(21, 21, 21)

class TVST_Drums:
    """Headless Generative Drum Synthesizer"""
    def __init__(self):
        self.env = {"release": 0.2}

    def render_note(self, buffer, start_idx, freq, duration_samples, sample_rate):
        max_idx = len(buffer)
        if freq < 100:  # KICK DRUM
            phase = 0.0
            for i in range(duration_samples):
                buf_i = start_idx + i
                if buf_i >= max_idx: break
                env = max(0.0, 1.0 - (i / duration_samples)) ** 2
                inst_freq = 40.0 + 110.0 * max(0.0, 1.0 - (i / (sample_rate * 0.05)))
                phase += inst_freq / sample_rate
                samp = math.sin(phase * 2 * math.pi) * env
                buffer[buf_i] += samp * 0.9
        else:  # SNARE DRUM
            phase = 0.0
            for i in range(duration_samples):
                buf_i = start_idx + i
                if buf_i >= max_idx: break
                env_body = max(0.0, 1.0 - (i / (sample_rate * 0.08))) ** 2
                env_noise = max(0.0, 1.0 - (i / duration_samples))
                phase += 180.0 / sample_rate
                body = math.sin(phase * 2 * math.pi) * env_body
                noise = (random.random() * 2.0 - 1.0) * env_noise
                samp = (body * 0.4 + noise * 0.6)
                buffer[buf_i] += samp * 0.7

def render_track(tracks, bpm):
    drect(40, 200, 280, 300, C_UI)
    drect_border(40, 200, 280, 300, C_NONE, 2, C_NOTE)
    dtext_opt(DWIDTH//2, 250, C_TEXT, C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "Allocating Buffer...", -1)
    dupdate()
    
    SR = 22050 
    beat_sec = 60.0 / bpm
    sixteenth_sec = beat_sec / 4.0
    
    last_end_time = 0
    tail_sec = 0
    for synth, notes in tracks:
        if notes:
            end_t = max([start + duration for freq, start, duration in notes])
            last_end_time = max(last_end_time, end_t)
        tail_sec = max(tail_sec, synth.env.get("release", 0.0))
        
    total_sec = (last_end_time * sixteenth_sec) + tail_sec + 0.5
    total_samples = int(total_sec * SR)
    
    # 🚨 Fast allocation: standard list replication is fastest and doesn't re-alloc inside loops
    buffer = [0.0] * total_samples 
    
    drect(40, 200, 280, 300, C_UI)
    drect_border(40, 200, 280, 300, C_NONE, 2, C_NOTE)
    dtext_opt(DWIDTH//2, 250, C_TEXT, C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "Rendering WAV...", -1)
    dupdate()

    for synth, notes in tracks:
        for freq, start_beats, dur_beats in notes:
            start_sec = start_beats * sixteenth_sec
            dur_sec = dur_beats * sixteenth_sec
            
            start_idx = int(start_sec * SR)
            dur_samples = int(dur_sec * SR)
            synth.render_note(buffer, start_idx, freq, dur_samples, SR)
            
    # 🚨 Performant Normalization: In-place loops instead of creating new massive array fragments
    max_amp = 0.001
    for s in buffer:
        abs_s = abs(s)
        if abs_s > max_amp: max_amp = abs_s
        
    if max_amp > 1.0:
        for i in range(total_samples):
            buffer[i] /= max_amp
            
    drect(40, 200, 280, 300, C_UI)
    drect_border(40, 200, 280, 300, C_NONE, 2, C_NOTE)
    dtext_opt(DWIDTH//2, 250, C_TEXT, C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "Saving track.wav...", -1)
    dupdate()
    
    try:
        # 🚨 Performant Chunk Packing: Avoids list comprehension
        chunk_samples = [0] * 128
        with open("track.wav", "wb") as f:
            data_size = total_samples * 2
            header = struct.pack('<4sI4s4sIHHIIHH4sI',
                b'RIFF', 36 + data_size, b'WAVE', 
                b'fmt ', 16, 1, 1, SR, SR * 2, 2, 16, 
                b'data', data_size)
            f.write(header)
            
            for i in range(0, total_samples, 128):
                n = min(128, total_samples - i)
                for j in range(n):
                    chunk_samples[j] = int(buffer[i+j] * 32760)
                f.write(struct.pack('<' + 'h' * n, *chunk_samples[:n]))
                
        dtext_opt(DWIDTH//2, 280, C_RGB(0,31,0), C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "Saved Successfully!", -1)
    except Exception as e:
        dtext_opt(DWIDTH//2, 280, C_RGB(31,0,0), C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "File Error.", -1)
    
    dupdate()
    time.sleep(2.0)

def main():
    synth_osc = tvst.TVST_3xOsc()
    synth_drums = TVST_Drums()
    synth_saw = tvst.TVST_Supersaw()
    
    # Track 1 Sequence (Arp)
    # Set the 3xOsc to Sawtooth (wave type 2) for a pluckier arp
    synth_osc.oscs[0]["wave"] = 2
    synth_osc.oscs[1]["wave"] = 2
    synth_osc.compile()

    # Track 1 Sequence (Arp perfectly following the Pad's harmony)
    freqs = [
        # Beat 1: A Major (A4, E5, C#5, E5)
        440.00, 659.25, 554.37, 659.25,
        # Beat 2: F# Minor (F#4, C#5, A4, C#5)
        369.99, 554.37, 440.00, 554.37,
        # Beat 3: D Major (D4, A4, F#4, A4)
        293.66, 440.00, 369.99, 440.00,
        # Beat 4: E Major (E4, B4, G#4, B4)
        329.63, 493.88, 415.30, 493.88
    ]
    
    notes_osc = []
    for i in range(16): 
        # Bouncy driving rhythm
        dur = 0.5 if i % 2 == 0 else 0.8
        notes_osc.append((freqs[i], i, dur))

    # Track 2 Sequence (Drums - Fast DnB loop)
    notes_drums = []
    for b in range(4): 
        base = b * 4
        notes_drums.append((50, base + 0, 0.8))     # Kick
        notes_drums.append((200, base + 1, 0.8))    # Snare
        notes_drums.append((50, base + 2.5, 0.8))   # Kick
        notes_drums.append((200, base + 3, 0.8))    # Snare

    # Track 3 Sequence (Supersaw Chords - Warm Pad)
    notes_saw = [
        # A Major Pad
        (440.00, 0, 4), (554.37, 0, 4), (659.25, 0, 4),
        # F# Minor Pad
        (369.99, 4, 4), (440.00, 4, 4), (554.37, 4, 4),
        # D Major Pad
        (293.66, 8, 4), (369.99, 8, 4), (440.00, 8, 4),
        # E Major Pad
        (329.63, 12, 4), (415.30, 12, 4), (493.88, 12, 4)
    ]

    tracks = [
        (synth_osc, notes_osc),
        (synth_drums, notes_drums),
        (synth_saw, notes_saw)
    ]

    # Dynamically scale UI mapping to fit all distinct pitches
    all_notes = sorted(list(set([f for s, trk in tracks for f, _, _ in trk])), reverse=True)
    
    labels = {
        659.25: "E5", 554.37: "C#5", 493.88: "B4", 440.00: "A4",
        415.30: "G#4", 369.99: "F#4", 329.63: "E4", 293.66: "D4",
        200: "SNR", 50: "KCK", 523.25: "C5", 392.00: "G4", 349.23: "F4"
    }

    running = True
    clearevents()
    
    while running:
        dclear(C_BG)
        
        # Header
        drect(0,0,DWIDTH,30,C_UI)
        dtext_opt(10, 15, C_TEXT, C_NONE, DTEXT_LEFT, DTEXT_MIDDLE, "TinyDAW", -1)
        dtext_opt(DWIDTH-10, 15, C_TEXT, C_NONE, DTEXT_RIGHT, DTEXT_MIDDLE, "130 BPM", -1)
        
        # Playlist Zone
        py = 40
        drect(0, py, DWIDTH, py+100, C_UI)
        drect_border(0, py, DWIDTH, py+100, C_NONE, 1, C_GRID)
        dtext_opt(5, py+10, C_TEXT, C_NONE, DTEXT_LEFT, DTEXT_TOP, "Playlist", -1)
        
        drect(40, py+25, 310, py+45, C_RGB(10,16,10))
        dtext_opt(45, py+35, C_NOTE, C_NONE, DTEXT_LEFT, DTEXT_MIDDLE, "Trk 1: 3xOsc - Arp", -1)
        
        drect(40, py+50, 310, py+70, C_RGB(16,10,10))
        dtext_opt(45, py+60, C_DRUM, C_NONE, DTEXT_LEFT, DTEXT_MIDDLE, "Trk 2: Drums - Beat", -1)

        drect(40, py+75, 310, py+95, C_RGB(10,10,16))
        dtext_opt(45, py+85, C_SAW, C_NONE, DTEXT_LEFT, DTEXT_MIDDLE, "Trk 3: Supersaw - Pad", -1)
        
        # Piano Roll Zone
        ry = 150
        rh = 360
        drect(0, ry, DWIDTH, ry+rh, C_UI)
        drect_border(0, ry, DWIDTH, ry+rh, C_NONE, 1, C_GRID)
        dtext_opt(5, ry+10, C_TEXT, C_NONE, DTEXT_LEFT, DTEXT_TOP, "Piano Roll", -1)
        
        pitch_y = {f: ry + 30 + i * 25 for i, f in enumerate(all_notes)}
        
        for i in range(16):
            x = 40 + i * 17
            col = C_GRID if i % 4 != 0 else C_RGB(12,14,16)
            dline(x, ry+30, x, ry+rh, col)
            
        for freq in all_notes:
            y = pitch_y[freq]
            drect(0, y-12, 38, y+12, C_RGB(24,24,24))
            drect_border(0, y-12, 38, y+12, C_NONE, 1, C_GRID)
            dtext_opt(19, y, C_TEXT, C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, labels.get(freq, "?"), -1)
            
        # Draw Notes
        for freq, start, dur in notes_osc: drect(40+int(start*17), pitch_y[freq]-8, 40+int((start+dur)*17)-2, pitch_y[freq]+8, C_NOTE)
        for freq, start, dur in notes_saw: drect(40+int(start*17), pitch_y[freq]-8, 40+int((start+dur)*17)-2, pitch_y[freq]+8, C_SAW)
        for freq, start, dur in notes_drums: drect(40+int(start*17), pitch_y[freq]-8, 40+int((start+dur)*17)-2, pitch_y[freq]+8, C_DRUM)
            
        dtext_opt(DWIDTH//2, DHEIGHT-30, C_TEXT, C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "[1] 3xOsc | [2] Supersaw", -1)
        dtext_opt(DWIDTH//2, DHEIGHT-15, C_TEXT_DIM, C_NONE, DTEXT_CENTER, DTEXT_MIDDLE, "[EXE] Render & Export", -1)
        dupdate()
        
        ev = pollevent()
        events = []
        while ev.type != KEYEV_NONE: events.append(ev); ev = pollevent()
            
        for e in events:
            if e.type == KEYEV_DOWN:
                if e.key == KEY_1: tvst.open_synth_dialog(synth_osc)
                elif e.key == KEY_2: tvst.open_supersaw_dialog(synth_saw)
                elif e.key == KEY_EXE: render_track(tracks, 130 // 3)
                elif e.key == KEY_EXIT: running = False
                
        time.sleep(0.01)

main()
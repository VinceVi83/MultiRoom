import os, sys, time, socket, queue
import sounddevice as sd
import numpy as np
import threading
from faster_whisper import WhisperModel
from config_loader import cfg

MICRO_GAIN, TRIGGER_THRESHOLD = 3.0, 0.05
MODEL_SIZE, DEVICE, COMPUTE_TYPE = "medium", "cuda", "float16"
WSL_IP, PORT = "172.21.8.200", 5000

def init_cuda():
    base = os.path.join(os.environ['LOCALAPPDATA'], 'Python', 'pythoncore-3.14-64', 'Lib', 'site-packages')
    for d in ['cublas', 'cudnn', 'cuda_runtime']:
        path = os.path.join(base, 'nvidia', d, 'bin')
        if os.path.exists(path):
            os.add_dll_directory(path)
            os.environ['PATH'] = path + os.pathsep + os.environ['PATH']

class WhisperEngine:
    def __init__(self):
        print(f"[*] Loading {MODEL_SIZE}...")
        self.model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)

    def transcribe(self, audio):
        segments, _ = self.model.transcribe(audio, language=cfg.LANGUAGE, vad_filter=True,
                                            initial_prompt="Command, VLC, Playlist, Jukebox, Touhou, Japanese.")
        return "".join([s.text for s in segments]).strip()

class AudioBuffer:
    def __init__(self):
        self.buffer, self.active, self.silence = [], False, 0

    def push(self, chunk, vol):
        self.buffer.append(chunk)
        if not self.active and len(self.buffer) > 20: self.buffer.pop(0)

        if vol > TRIGGER_THRESHOLD:
            self.active, self.silence = True, 0
        elif self.active:
            self.silence += 1

        return self.active and self.silence > 30

    def pull(self):
        data = np.concatenate(self.buffer, axis=0).flatten()
        self.buffer, self.active, self.silence = [], False, 0
        return data

def send(text):
    if not text: return
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2.0)
            s.connect((WSL_IP, PORT))
            s.sendall(text.encode('utf-8'))
            print(f"\n[SENT] {text}")
    except Exception:
        print("\n[ERR] Server unreachable")

def run_mic_test(duration=5):
    """Displays a volume bar for X seconds to validate hardware."""
    print("\n" + "="*40)
    print(f"--- INITIAL MIC TEST ({duration}s) ---")
    print("="*40)

    test_q = queue.Queue()
    def test_cb(indata, f, t, s):
        amp = np.clip(indata.copy() * MICRO_GAIN, -1.0, 1.0)
        test_q.put(np.max(np.abs(amp)))

    with sd.InputStream(samplerate=16000, channels=1, callback=test_cb):
        end_time = time.time() + duration
        while time.time() < end_time:
            vol = test_q.get()
            bar = "█" * int(vol * 50)
            status = "!! OK !!" if vol > TRIGGER_THRESHOLD else "TOO LOW"
            print(f" Test: {bar.ljust(40)} | Vol: {vol:.4f} | {status}", end="\r")

    print("\n\n[*] Test completed. Loading AI model...\n")

def main():
    init_cuda()
    run_mic_test(5)
    engine, manager, q = WhisperEngine(), AudioBuffer(), queue.Queue()

    def cb(indata, f, t, s):
        amp = np.clip(indata.copy() * MICRO_GAIN, -1.0, 1.0)
        q.put((amp, np.max(np.abs(amp))))

    exit_event = threading.Event()
    print("[*] Listening active (Ctrl+C to stop)...")
    try:
        with sd.InputStream(samplerate=16000, channels=1, callback=cb):
            while not exit_event.is_set():
                try:
                    chunk, vol = q.get(timeout=0.1)

                    if manager.push(chunk, vol):
                        print("\n[*] AI Processing...")
                        audio_data = manager.pull()
                        text = engine.transcribe(audio_data)
                        send(text)

                    status = "CAPTURING" if manager.active else "IDLE"
                    print(f" {status} | Vol: {vol:.4f} ".ljust(30), end="\r")

                except queue.Empty:
                    continue
    except KeyboardInterrupt:
        print("\n[!] Shutdown requested (Ctrl+C)...")
    finally:
        exit_event.set()
        print("[*] Cleaning up and closing stream.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nShutdown.")

import numpy as np
import pyaudio
import socket
import signal
import sys
from collections import deque
from tools.whisper_engine import WhisperEngine

class SimpleVoiceNode:
    """Simple Voice Node for audio transcription and command sending
    
    Role: Captures audio input, transcribes speech using Whisper, and sends commands to a socket server.
    
    Methods:
        __init__(self, host='127.0.0.1', port=28888) : Initialize the voice node with host and port settings.
        start(self) : Start the audio recording and processing loop.
        _handle_action(self, frames) : Process transcribed audio and send to socket server.
    """
    def __init__(self, host='127.0.0.1', port=28888):
        self.host = host
        self.port = port
        self.running = True
        self.pre_roll = deque(maxlen=40)
        self.whisper = WhisperEngine()
        self.pa = pyaudio.PyAudio()

    def start(self):
        stream = self.pa.open(format=pyaudio.paInt16, channels=1, rate=16000, 
                             input=True, frames_per_buffer=1024)

        BAR_WIDTH = 20
        MAX_RMS = 2500
        
        try:
            while self.running:
                frames, recording, silent_chunks = [], False, 0
                
                while self.running:
                    data = stream.read(1024, exception_on_overflow=False)
                    rms = np.sqrt(np.mean(np.frombuffer(data, dtype=np.int16).astype(np.float64)**2))
                    
                    if rms > 500 and not recording:
                        recording = True
                        frames.extend(list(self.pre_roll)) 
                        frames.append(data)
                        silent_chunks = 0
                    elif recording:
                        frames.append(data)
                        if rms < 350:
                            silent_chunks += 1
                        else:
                            silent_chunks = 0
                        
                        if silent_chunks > 25 or len(frames) > 215:
                            break
                    else:
                        self.pre_roll.append(data)
                    
                    meter = int((min(rms, MAX_RMS) / MAX_RMS) * BAR_WIDTH)
                    bar = "█" * meter + "-" * (BAR_WIDTH - meter)
                    status = "[REC] " if recording else "[IDLE]"
                    
                    print(f" {status} | {bar} | RMS: {int(rms):<5} | Len: {len(frames):<3}", end="\r")

                if frames and self.running:
                    self._handle_action(frames)
                    
                    frames, recording = [], False
                    self.pre_roll.clear()

        finally:
            stream.stop_stream()
            stream.close()
            self.pa.terminate()

    def _handle_action(self, frames):
        audio_np = np.frombuffer(b"".join(frames), dtype=np.int16).astype(np.float32) / 32768.0
        text = self.whisper.transcribe(audio_np)
        
        if text:
            print(f"[Whisper] -> {text}")
            try:
                with socket.create_connection((self.host, self.port), timeout=5) as sock:
                    sock.sendall(f"DEBUG:test:{text}\n".encode('utf-8'))
            except Exception as e:
                print(f"[!] Send error: {e}")

if __name__ == "__main__":
    node = SimpleVoiceNode()
    signal.signal(signal.SIGINT, lambda s, f: sys.exit(0))
    node.start()

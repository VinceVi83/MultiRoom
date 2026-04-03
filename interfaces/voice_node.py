import os, sys, subprocess, platform, argparse, time
import numpy as np
import wave
import pyaudio
from collections import deque
import signal
from tools.whisper_engine import WhisperEngine
from tools.hub_messenger import HubMessenger

class UnifiedSpeechSystem:
    """Unified Speech Processing System
    
    Role: Manages audio input, speech-to-text transcription, and push-to-talk operations.
    
    Methods:
        __init__(self, mode, cert_path=None, user='test', password='test') : Initialize the system with operating mode and credentials.
        start(self) : Start the audio processing loop for continuous input.
        _handle_stt_action(self, frames) : Process audio frames through speech-to-text engine and send to hub.
        _handle_ptt_action(self, frames) : Handle push-to-talk by saving audio and sending to hub.
        stop(self) : Stop the audio processing loop and cleanup resources.
    """
    def __init__(self, mode, cert_path=None, user="test", password="test"):
        self.mode = mode
        self.running = True
        self.temp_wav = "temp_voice.wav"
        self.pre_roll = deque(maxlen=40)
        self.stream = None
        
        try:
            self.messenger = HubMessenger(
                host="172.21.8.200",
                cert_path=cert_path, 
                user=user, 
                password=password
            )

            if self.mode == "stt":
                self.whisper = WhisperEngine()
            self.pa = pyaudio.PyAudio()
        except Exception as e:
            print(f"[CRITICAL] System initialization failed: {e}")
            raise

    def start(self):
        stream = self.pa.open(format=pyaudio.paInt16, channels=1, rate=16000, 
                             input=True, frames_per_buffer=1024)
        self.stream = stream
        BAR_WIDTH = 20
        MAX_RMS = 2500
        
        try:
            while self.running:
                frames, recording, silent_chunks = [], False, 0
                
                while self.running:
                    try:
                        data = stream.read(1024, exception_on_overflow=False)
                    except Exception as e:
                        print(f"[WARN] Audio glitch: {e}")
                        time.sleep(0.1)
                        continue
                    
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
                    if self.mode == "ptt":
                        self._handle_ptt_action(frames)
                    else:
                        self._handle_stt_action(frames)
                    
                    frames, recording = [], False
                    self.pre_roll.clear()

        finally:
            stream.stop_stream()
            stream.close()
            self.pa.terminate()

    def _handle_stt_action(self, frames):
        try:
            audio_np = np.frombuffer(b"".join(frames), dtype=np.int16).astype(np.float32) / 32768.0
            text = self.whisper.transcribe(audio_np)
            if text:
                print(f"[*] Sending to Hub: {text}")
                self.messenger.send_stt(text)
        except Exception as e:
            print(f"[ERROR] STT processing failed: {e}")

    def _handle_ptt_action(self, frames):
        with wave.open(self.temp_wav, 'wb') as wf:
            wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(16000)
            wf.writeframes(b''.join(frames))
        
        self.messenger.send_ptt(self.temp_wav)

    def stop(self):
        self.stream.stop_stream()
        self.stream.close()
        self.pa.terminate()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", "--mode", choices=['stt', 'ptt'], required=True, help="Operating mode")
    parser.add_argument("-c", "--cert", help="Path to the cert.pem certificate")
    parser.add_argument("--user", default="test", help="Login user")
    parser.add_argument("--password", default="test", help="Login password")
    args = parser.parse_args()
    
    signal.signal(signal.SIGINT, lambda sig, frame: node.stop())
    try:
        node = UnifiedSpeechSystem(mode=args.mode, cert_path=args.cert, user=args.user, password=args.password)
        node.start()
    except KeyboardInterrupt:
        if node: node.stop()
        sys.exit(0)
    except Exception as e:
        print(f"[FATAL] Node crashed: {e}")
        sys.exit(1)

import os
import socket
import ssl
import pyaudio
import wave
import threading
import time
import numpy as np
import hashlib
import uuid
import platform
import subprocess
from http.server import SimpleHTTPRequestHandler, HTTPServer
from config_loader import cfg


class STT:
    """Speech-to-Text (STT) system for capturing and processing voice commands.

    Methods:
        __init__(http_port, json_path): Initializes the STT system with audio configuration.
        get_hardware_signature(): Generates a unique hardware signature using platform info.
        test_microphone(): Tests the microphone level and reports signal strength.
        _serve_file(): Starts a one-shot HTTP server for the Hub file transfer.
        record_audio(): Records audio from the microphone until silence threshold.
        send_link_to_hub(): Sends the recorded audio link to the Hub with signature.
        run(): Starts the STT system in continuous listening mode.
    """

    def __init__(self):
        self.temp_filename = "temp_voice.wav"
        self.http_port = 8090
        self.gain = 2.0
        self.chunk = 1024
        self.format = pyaudio.paInt16
        self.channels = 1
        self.rate = 44100
        self.record_seconds = 5

        self.audio = pyaudio.PyAudio()

    def get_hardware_signature(self):
        try:
            os_id = str(subprocess.check_output('wmic csproduct get uuid'), 'utf-8').split('\n')[1].strip()
            mac_addr = ':'.join(['{:02x}'.format((uuid.getnode() >> ele) & 0xff)
                                for ele in range(0, 8*6, 8)][::-1])
            raw_signature = f"{platform.node()}-{os_id}-{mac_addr}"
            return hashlib.sha256(raw_signature.encode()).hexdigest()
        except Exception:
            return hashlib.sha256(platform.node().encode()).hexdigest()

    def test_microphone(self):
        print("[*] Testing microphone signal...")
        stream = self.audio.open(format=self.format, channels=self.channels,
                                 rate=self.rate, input=True,
                                 frames_per_buffer=self.chunk)
        try:
            data = stream.read(self.chunk * 10)
            audio_data = np.frombuffer(data, dtype=np.int16)
            rms = np.sqrt(np.mean(audio_data**2))

            if rms < 100:
                print(f"[!] WARNING: Very low level ({rms:.2f}). Check your Windows settings.")
            else:
                print(f"[OK] Microphone active (RMS Level: {rms:.2f})")
        except Exception as e:
            print(f"[!] Microphone Test Error: {e}")
        finally:
            stream.stop_stream()
            stream.close()

    def _serve_file(self):
        handler = SimpleHTTPRequestHandler
        server = HTTPServer(('0.0.0.0', self.http_port), handler)
        server.handle_request()

    def record_audio(self):
        print("\n[Listening] Waiting for a voice command. ..")

        stream = self.audio.open(format=self.format, channels=self.channels,
                                 rate=self.rate, input=True,
                                 frames_per_buffer=self.chunk)
        frames = []
        is_recording = False
        silent_chunks = 0

        THRESHOLD = 300
        SILENCE_LIMIT = int(self.rate / self.chunk * 3.0)
        CONTINUE_THRESHOLD = THRESHOLD * 0.8

        while True:
            data = stream.read(self.chunk)
            audio_data_raw = np.frombuffer(data, dtype=np.int16)
            audio_data_float = audio_data_raw.astype(np.float64)
            rms = np.sqrt(np.mean(audio_data_float**2))

            if rms > THRESHOLD or (is_recording and rms > CONTINUE_THRESHOLD):
                if not is_recording:
                    print(f">>> [DETECTION] Volume: {rms:.0f} - Recording...")
                    is_recording = True

                amplified_data = (audio_data_raw * self.gain).clip(-32768, 32767).astype(np.int16)
                frames.append(amplified_data.tobytes())
                silent_chunks = 0
            elif is_recording:
                frames.append(data)
                silent_chunks += 1
                if silent_chunks > SILENCE_LIMIT:
                    break

            if is_recording and len(frames) > int(self.rate / self.chunk * 10):
                break

        print("[!] [FIN] Processing...")
        stream.stop_stream()
        stream.close()

        with wave.open(self.temp_filename, 'wb') as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(self.audio.get_sample_size(self.format))
            wf.setframerate(self.rate)
            wf.writeframes(b''.join(frames))

    def send_link_to_hub(self):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        local_ip = socket.gethostbyname(socket.gethostname())
        url = f"http://{local_ip}:{self.http_port}/{self.temp_filename}"
        hw_signature = self.get_hardware_signature()
        secure_packet = f"{hw_signature}:PTT:{url}"
        print(secure_packet)

        try:
            threading.Thread(target=self._serve_file, daemon=True).start()
            time.sleep(0.2)

            with socket.create_connection((cfg.sys.HUB_IP, 28888), timeout=5) as sock:
                with context.wrap_socket(sock, server_hostname=cfg.sys.HUB_IP) as ssock:
                    ssock.sendall(secure_packet.encode('utf-8'))
                    print(f"[OK] Signal sent to Hub : {url}")
                    response = ssock.recv(1024).decode('utf-8')
                    print(f"[SERVER SAYS] : {response}")
                    time.sleep(0.5)
        except Exception as e:
            print(f"[!] Error transmission : {e}")

    def run(self):
        self.test_microphone()
        print("\n[SYSTEM] Automatic mode activated. Continuous listening...")
        try:
            while True:
                self.record_audio()
                self.send_link_to_hub()
                print("\n[REPOS] Ready for the next command...")
        except KeyboardInterrupt:
            print("\nStopping the script.")

if __name__ == "__main__":
    stt = STT()
    stt.run()

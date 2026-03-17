from faster_whisper import WhisperModel
from config_loader import cfg
import os


class WhisperEngine:
    """Manages the Whisper model for speech recognition tasks.

    Methods:
    - __init__(self) : Initializes the Whisper model with GPU or CPU configuration based on system settings.
    - transcribe(self, audio) : Transcribes audio data to text using the loaded model with VAD filtering.
    """

    def __init__(self):
        print(f"[*] Loading Whisper for {cfg.sys.WHISPER}...")
        if cfg.sys.WHISPER == "GPU":
            self.model = WhisperModel("distil-large-v3", device="cuda", compute_type="float16")
        elif cfg.sys.WHISPER == "CPU":
            self.model = WhisperModel("medium", device="cpu", compute_type="int8", cpu_threads=4, num_workers=1)

        self.vad_params = dict(threshold=0.35, min_speech_duration_ms=250)

    def transcribe(self, audio):
        segments, _ = self.model.transcribe(audio, language=cfg.LANGUAGE, vad_filter=True, vad_parameters=self.vad_params,
                                       initial_prompt="Alisu, Command, VLC, Playlist, Jukebox, Touhou, Japanese.")

        return "".join([s.text for s in segments]).strip()

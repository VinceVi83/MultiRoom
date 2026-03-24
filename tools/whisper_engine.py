from faster_whisper import WhisperModel
import os
try:
    from config_loader import cfg
    WHISPER_MODE = cfg.sys.WHISPER
    LANGUAGE = cfg.sys.LANGUAGE
except (ImportError, AttributeError):
    WHISPER_MODE = "GPU"
    LANGUAGE = "fr"

def initialize_cuda():
    base_nvidia = os.path.join(os.environ['APPDATA'], 'Python', 'Python312', 'site-packages', 'nvidia')
    sub_folders = ['cublas/bin', 'cudnn/bin', 'cuda_runtime/bin', 'cublas_cu12/bin']
    
    for folder in sub_folders:
        path = os.path.normpath(os.path.join(base_nvidia, folder))
        if os.path.exists(path):
            try:
                os.add_dll_directory(path)
                os.environ['PATH'] = path + os.pathsep + os.environ['PATH']
            except Exception as e:
                pass


if os.name == 'nt':
    initialize_cuda()

class WhisperEngine:
    """Whisper Engine
    
    Role: Manages the Whisper model for speech recognition tasks.
    
    Methods:
        __init__(self) : Initializes the Whisper model with GPU or CPU configuration based on system settings.
        transcribe(self, audio) : Transcribes audio data to text using the loaded model with VAD filtering.
    """

    def __init__(self):
        if WHISPER_MODE == "GPU":
            self.model = WhisperModel("medium", device="cuda", compute_type="float16")
        elif WHISPER_MODE == "CPU":
            self.model = WhisperModel("medium", device="cpu", compute_type="int8", cpu_threads=4, num_workers=1)

        self.vad_params = dict(threshold=0.35, min_speech_duration_ms=250)

    def transcribe(self, audio):
        segments, _ = self.model.transcribe(audio, language=LANGUAGE, vad_filter=True,
                                       initial_prompt="Alisu, Touhou, Playlist, VLC, Japanese, Mail-moi.")

        return "".join([s.text for s in segments]).strip()

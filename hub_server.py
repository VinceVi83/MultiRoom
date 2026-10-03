import os
import re
import subprocess
import sys
import threading
import time
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from common.conf_manager import cfg, setup_logging
from tools.task_context import TaskContext
from router_llm import RouterLLM
from user_session import UserSession
from common.llm_client import llm

import logging
setup_logging()
logger = logging.getLogger(__name__)

cfg.debug = 1 if "-d" in sys.argv or "--debug" in sys.argv else 0
cfg.verbose = 1 if "-v" in sys.argv or "--verbose" in sys.argv else 0
cfg.report = 1 if "-r" in sys.argv or "--report" in sys.argv else 0
cfg.no_bypass = 0 if "--no-bypass" in sys.argv else 1

app = FastAPI()

router = RouterLLM()

sessions: dict[str, UserSession] = {}
sessions_lock = threading.Lock()

_audio_sink = None
_audio_sink_lock = threading.Lock()


def _pulse_env() -> dict:
    env = os.environ.copy()
    env['XDG_RUNTIME_DIR'] = '/run/user/1000'
    env['PULSE_SERVER'] = 'unix:/run/user/1000/pulse/native'
    return env


def _run_pactl_command(args, check=True):
    try:
        result = subprocess.run(
            ["pactl"] + args,
            capture_output=True,
            text=True,
            check=check,
            env=_pulse_env(),
        )
        return result
    except subprocess.CalledProcessError as e:
        if check:
            raise
        return e


def _detect_audio_sink():
    try:
        _run_pactl_command(["get-sink-volume", "@DEFAULT_SINK@"])
        return "@DEFAULT_SINK@"
    except subprocess.CalledProcessError:
        pass

    try:
        result = _run_pactl_command(["list", "short", "sinks"])
        lines = result.stdout.strip().split('\n')
        if lines and lines[0]:
            first_sink_index = lines[0].split('\t')[0]
            logger.info(f"Using first available audio sink: {first_sink_index}")
            return first_sink_index

        logger.error("No audio sinks found")
        return None
    except Exception as e:
        logger.error(f"Failed to detect audio sink: {e}")
        return None


def _get_audio_sink():
    global _audio_sink
    with _audio_sink_lock:
        if _audio_sink is None:
            _audio_sink = _detect_audio_sink()
        return _audio_sink


class CommandRequest(BaseModel):
    username: str
    command: str
    origin: str | None = None

class AnnouncementRequest(BaseModel):
    file_path: str
    location: str | None = None

class AnnouncementTTSRequest(BaseModel):
    text: str
    lang: str = "jp"
    location: str = None

def get_or_create_session(username: str) -> UserSession:
    with sessions_lock:
        if username not in sessions:
            sessions[username] = UserSession(username=username, index=len(sessions))
        return sessions[username]


@app.post("/command")
def post_command(req: CommandRequest):
    if req.username not in cfg.sys.security.USERS:
        raise HTTPException(status_code=403, detail="Unknown user")
    session = get_or_create_session(req.username)
    try:
        if 'http' in req.command:
            req.command = llm.transcribe(req.command)['content']
    except Exception as e:
        logger.error(f"Error processing command: {e} {req.command}")
    context = TaskContext(user_input=req.command, session=session, origin=req.origin)
    router.add_to_queue(context)
    return {"status": "queued"}


@app.delete("/session/{username}")
def delete_session(username: str):
    with sessions_lock:
        session = sessions.pop(username, None)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    session.stop_all_services()
    return {"status": "deleted"}


def _create_vocal(text: str, lang: str = "jp") -> str:
    try:
        if lang == "jp":
            return _create_vocal_jp(text)
        # elif lang == "fr": # TODO: need better prompt or model or STT...
        #     return _create_vocal_fr(text)
        elif lang == "en":
            return _create_vocal_jp(text)
        elif lang == "fren":
            text = _transcribe_with_llm(text, cfg.agents.translator_fren)
            return _create_vocal_jp(text)
        else:
            logger.error(f"Unsupported language: {lang}")
            return None
    except Exception as e:
        logger.exception(f"Error creating vocal: {e}")
        return None


def _create_vocal_jp(text: str) -> str:
    base = cfg.sys.tts.rstrip("/")
    try:
        r = requests.post(
            f"{base}/audio_query",
            params={"text": text, "speaker": 3},
            timeout=10,
        )
        r.raise_for_status()
        query = r.json()
        r = requests.post(
            f"{base}/synthesis",
            params={"speaker": 3},
            json=query,
            timeout=10,
        )
        r.raise_for_status()
        timestamp = int(time.time() * 1000)
        file_path = f"/tmp/vocal_jp_{timestamp}.wav"
        with open(file_path, "wb") as f:
            f.write(r.content)
        logger.info(f"Created JP vocal file: {file_path}")
        return file_path
    except Exception as e:
        logger.error(f"Error creating JP vocal: {e}")
        return None

def _transcribe_with_llm(text: str, system_prompt: str) -> str:
    try:
        response = llm.call(
            system_prompt,
            text,
            model=cfg.sys.llm_model.large_model,
            mode='creative'
        )
        processed_text = response.get("content", text)
        logger.info(f"LLM transcription result: {text} {response}")
        return processed_text
    except Exception as e:
        logger.error(f"Error in LLM transcription: {e}")
        return text

# def _create_vocal_fr(text: str) -> str:
#     base = cfg.sys.tts.rstrip("/")
#     try:
#         processed_text = _transcribe_with_llm(text, cfg.agents.tts_furansugo)
#         processed_text = romaji_to_katakana(processed_text)
#         logger.info(f"Processed FR text for TTS: {processed_text}")
#         r = requests.post(
#             f"{base}/audio_query",
#             params={"text": processed_text, "speaker": 1},
#             timeout=10,
#         )
#         r.raise_for_status()
#         query = r.json()
#         r = requests.post(
#             f"{base}/synthesis",
#             params={"speaker": 1},
#             json=query,
#             timeout=10,
#         )
#         r.raise_for_status()
#         timestamp = int(time.time() * 1000)
#         file_path = f"/tmp/vocal_fr_{timestamp}.wav"
#         with open(file_path, "wb") as f:
#             f.write(r.content)
#         logger.info(f"Created FR vocal file: {file_path}")
#         return file_path
#     except Exception as e:
#         logger.error(f"Error creating FR vocal: {e}")
#         return None

@app.post("/play_announcement")
def play_announcement_with_tts(request: AnnouncementTTSRequest):
    text = request.text
    lang = request.lang
    location = request.location
    try:
        file_path = _create_vocal(text, lang)
        if not file_path:
            raise HTTPException(status_code=500, detail="Failed to generate vocal file")
        logger.info(f"Generated vocal file: {file_path}")
        announcement_request = AnnouncementRequest(
            file_path=file_path,
            location=location
        )
        result = play_announcement(announcement_request)
        
        return {
            "status": "success",
            "text": text,
            "lang": lang,
            "file_path": file_path,
            "location": location,
            "announcement_result": result
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error in play_announcement_with_tts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/announcement")
def play_announcement(req: AnnouncementRequest):
    active_sessions = []
    with sessions_lock:
        for username, user_session in sessions.items():
            try:
                if (user_session.get_vlc_is_active() is True and
                    "Music VLC" in user_session.services):
                    vlc_manager = user_session.services["Music VLC"]
                    if (hasattr(vlc_manager, 'vlc_instance') and
                        vlc_manager.vlc_instance is not None):
                        logger.info(f"Pausing VLC for user: {username}")
                        vlc_manager.vlc_instance.handle_simple_command("TOGGLE")
                        active_sessions.append(user_session)
            except Exception as e:
                logger.error(f"Error pausing VLC for {username}: {e}")
    time.sleep(2)
    saved_volume = None
    target_sink = None

    if req.location is not None:
        target_sink = req.location
        logger.info(f"Using provided location as sink: {target_sink}")
    else:
        target_sink = _get_audio_sink()
        if target_sink is None:
            logger.error("No audio sink detected")
            raise HTTPException(status_code=503, detail="No audio sink detected")

    try:
        result = _run_pactl_command(["get-sink-volume", target_sink])
        m = re.search(r'(\d+)%', result.stdout)
        if not m:
            raise HTTPException(status_code=500, detail="Could not read current volume")
        saved_volume = int(m.group(1))
        logger.info(f"Saved volume: {saved_volume}% (sink: {target_sink})")

        _run_pactl_command(["set-sink-mute", target_sink, "0"])
        _run_pactl_command(["set-sink-volume", target_sink, "40000"])
        verify = _run_pactl_command(["get-sink-volume", target_sink])
        logger.info(f"Volume after set-sink-volume 100%: {verify.stdout.strip()}")
        if "100%" not in verify.stdout:
            logger.warning(f"Le volume ne semble pas être passé à 100% sur {target_sink}")

        if not os.path.isfile(req.file_path):
            logger.error(f"File not found: {req.file_path}")
            raise HTTPException(status_code=404, detail="Announcement file not found")

        env = _pulse_env()
        cmd = ["paplay"]
        if target_sink and target_sink != "@DEFAULT_SINK@":
            cmd += [f"--device={target_sink}"]
        cmd.append(req.file_path)
        logger.info(f"Playing announcement with command: {' '.join(cmd)}")
        result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                    text=True, env=env, check=True)
        if result.returncode != 0:
            logger.error(f"paplay failed: {result.stderr}")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error playing announcement: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if saved_volume is not None and target_sink is not None:
            try:
                _run_pactl_command(["set-sink-volume", target_sink, f"{saved_volume}%"])
                logger.info(f"Volume restored to {saved_volume}% (sink: {target_sink})")
            except Exception as e:
                logger.error(f"Failed to restore volume: {e}")
        
        for user_session in active_sessions:
            try:
                vlc_manager = user_session.services["Music VLC"]
                logger.info(f"Resuming VLC for user: {user_session.username}")
                vlc_manager.vlc_instance.handle_simple_command("TOGGLE")
            except Exception as e:
                logger.error(f"Error resuming VLC for {user_session.username}: {e}")

    return {"status": "played", "file_path": req.file_path, "location": target_sink}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=cfg.sys.HUB_PORT)


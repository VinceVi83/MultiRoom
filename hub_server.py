import threading
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sys
from common.conf_manager import cfg, setup_logging
from tools.task_context import TaskContext
from router_llm import RouterLLM
from user_session import UserSession

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


class CommandRequest(BaseModel):
    username: str
    command: str


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
    context = TaskContext(user_input=req.command, session=session)
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=cfg.sys.HUB_PORT)


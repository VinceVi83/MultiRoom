import argparse
import requests
import time
from config.conf_manager import cfg

BASE_URL = f"http://localhost:{cfg.sys.HUB_PORT}"


def send_command(username: str, command: str):
    resp = requests.post(f"{BASE_URL}/command", json={"username": username, "command": command})
    resp.raise_for_status()
    print(resp.json())


def delete_session(username: str):
    resp = requests.delete(f"{BASE_URL}/session/{username}")
    print(resp.status_code, resp.json())
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-u", "--user", default="system")
    parser.add_argument("command", nargs="+")
    parser.add_argument("--delete-session", action="store_true")
    args = parser.parse_args()

    command_text = " ".join(args.command)
    send_command(args.user, command_text)
    # send_command("system", "Allume la lumière dans la cuisine")
    # time.sleep(10)
    # send_command("system", "Eteint la lumière dans la cuisine")
    # delete_session("system")

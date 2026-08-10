import asyncio
import websockets
import json
import os
import time
import threading
import subprocess
from collections import deque
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class CommandQueue:
    def __init__(self, spam_window=2.0, max_commands_in_window=2, cooldown_period=5.0):
        self.queue = deque()
        self.command_history = deque()
        self.spam_window = spam_window
        self.max_commands_in_window = max_commands_in_window
        self.cooldown_period = cooldown_period
        self.is_blocked = False
        self.block_until = 0
        self.processing_task = None
        self._lock = asyncio.Lock()

    async def add_command(self, command_info):
        async with self._lock:
            current_time = time.time()
            if self.is_blocked:
                if current_time < self.block_until:
                    logger.info(f"Command blocked (spam protection active until {datetime.fromtimestamp(self.block_until)})")
                    return False
                else:
                    self.is_blocked = False
                    logger.info("Spam protection deactivated, resuming normal operation")
            self.command_history.append({
                'timestamp': current_time,
                'command': command_info.get('command', ''),
                'eid': command_info.get('eid', ''),
                'action': command_info.get('action', '')
            })
            self._clean_history(current_time)
            if self._is_spam(current_time):
                logger.warning(f"Spam detected! Blocking commands for {self.cooldown_period} seconds")
                self.is_blocked = True
                self.block_until = current_time + self.cooldown_period
                self.queue.clear()
                return False
            command_info['timestamp'] = current_time
            self.queue.append(command_info)
            if self.processing_task is None or self.processing_task.done():
                self.processing_task = asyncio.create_task(self._process_queue())
            return True

    def _clean_history(self, current_time):
        cutoff_time = current_time - self.spam_window
        while self.command_history and self.command_history[0]['timestamp'] < cutoff_time:
            self.command_history.popleft()

    def _is_spam(self, current_time):
        if len(self.command_history) > self.max_commands_in_window:
            recent_commands = [cmd for cmd in self.command_history if cmd['timestamp'] > current_time - 0.5]
            if len(recent_commands) > self.max_commands_in_window:
                entities = set(cmd['eid'] for cmd in recent_commands if cmd['eid'])
                if len(entities) > 2:
                    return True
                if len(recent_commands) > 5:
                    return True
        return False

    async def _process_queue(self):
        while self.queue:
            async with self._lock:
                if self.is_blocked and time.time() < self.block_until:
                    await asyncio.sleep(0.1)
                    continue
                if not self.queue:
                    break
                command_info = self.queue.popleft()
            try:
                command_age = time.time() - command_info.get('timestamp', time.time())
                if command_age > 5.0:
                    logger.info(f"Ignoring old command (age: {command_age:.2f}s): {command_info.get('command', '')}")
                    continue
                logger.info(f"Processing queued command: {command_info.get('command', '')}")
                if 'callback' in command_info and command_info['callback']:
                    await asyncio.to_thread(
                        command_info['callback'],
                        command_info['command'],
                        command_info.get('eid'),
                        command_info.get('action')
                    )
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Error processing queued command: {e}")

class HAListener:
    """Home Assistant WebSocket Event Listener
    
    Role: Monitors Home Assistant events and triggers corresponding actions via AI Hub.
    
    Methods:
        __init__(self, cfg) : Initialize listener with config, mapping, and hub messenger.
        _load_mapping(self) : Load action mapping from JSON file.
        _parse_and_learn_from_output(self, output, entity_id, action, original_command) : Parse command output and learn native commands.
        _update_action_mapping(self, entity_id, action, new_command) : Update mapping with learned native command.
        run_ha_listener(self) : Start listener in daemon thread.
        start(self) : Main loop to connect to WebSocket and process events.
        _auth(self, ws) : Authenticate with Home Assistant WebSocket.
        _sub(self, ws) : Subscribe to events.
        _process(self, event) : Process incoming event data.
        _delayed_trigger(self, eid, action) : Delayed action trigger with error handling.
        trigger(self, eid, name, action, command) : Execute the actual command/service call.
    """
    def __init__(self, cfg):
        self.cfg = cfg
        self.uri = f"ws://{self.cfg.ha_config.HA_HOSTNAME}:8123/api/websocket"
        self.token = self.cfg.ha_config.HA_TOKEN
        self.start_time = time.time()
        self.mapping = {}
        self.pending_tasks = {}
        self.command_queue = CommandQueue(
            spam_window=2.0,
            max_commands_in_window=3,
            cooldown_period=5.0
        )
        self._load_mapping()

    def send_cmd(self, content, entity_id=None, action=None):
        try:
            cmd = [self.cfg.ha_config.python_bin, "-m", "tools.hub_messenger"]
            cmd.append(content.strip())
            process = subprocess.Popen(
                cmd, 
                cwd=self.cfg.ha_config.working_dir,
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate()

            if entity_id and action and not content.startswith('@'):
                combined_output = (stdout or "") + (stderr or "")
                if combined_output.strip():
                    self._parse_and_learn_from_output(combined_output, entity_id, action, content)
            return stdout, stderr
        except Exception as e:
            logger.error(f"HAListener sent order error: {e}")
            return None, str(e)

    def _load_mapping(self):
        mapping_file = os.path.join(self.cfg.DATA_DIR, "ha_action_mapping.json")
        try:
            if os.path.exists(mapping_file):
                with open(mapping_file, "r", encoding="utf-8") as f:
                    self.mapping = json.load(f)
        except Exception as e:
            logger.error(f"loading mapping: {e}")

    def _parse_and_learn_from_output(self, output, entity_id, action, original_command):
        if not output or not output.strip():
            return

        json_str = output.strip()
        if '{' in json_str and '}' in json_str:
            first_brace = json_str.find('{')
            last_brace = json_str.rfind('}')
            if first_brace < last_brace:
                json_str = json_str[first_brace:last_brace+1]
        try:
            data = json.loads(json_str)
            success = False
            result_action = None
            category = "Unknown"
            sub_category = "Unknown"
            location = "Unknown"

            return_code = data.get('return_code') or data.get('returnCode') or data.get('ReturnCode')
            if return_code and 'SUCCESS' in str(return_code):
                success = True

            result_action = data.get('result') or data.get('Result') or data.get('RESULT')
            if not result_action and isinstance(data.get('Result'), dict):
                result_action = data.get('Result', {}).get('action')

            category = data.get('category') or data.get('Category') or data.get('CATEGORY') or "Unknown"
            location = data.get('location') or data.get('Location') or data.get('LOCATION') or "Unknown"
            if not location and isinstance(data.get('data'), dict):
                location = data.get('data', {}).get('LOCATION_CLEANER_AGENT', {}).get('location') or "Unknown"

            sub_cat_data = data.get('sub_category') or data.get('subCategory') or data.get('sub_category')
            if isinstance(sub_cat_data, dict):
                sub_category = sub_cat_data.get('label') or "Unknown"
            elif sub_cat_data:
                sub_category = sub_cat_data

            if sub_category == "Unknown":
                sub_category = data.get('sub_category') or data.get('subCategory') or "Unknown"

            if success and result_action:
                full_native_command = f"@{category.lower()};-;{location};-;{sub_category};-;{result_action}"
                self._update_action_mapping(entity_id, action, full_native_command)
                logger.info(f"Learned native command for {entity_id}/{action}: '{original_command}' -> '{full_native_command}'")
        except json.JSONDecodeError:
            pass
        except Exception as e:
            logger.error(f"Error parsing learning output: {e}")

    def _update_action_mapping(self, entity_id, action, new_command):
        mapping_file = os.path.join(self.cfg.DATA_DIR, "ha_action_mapping.json")
        try:
            if entity_id in self.mapping:
                actions = self.mapping[entity_id].get("actions", {})
                if action in actions:
                    actions[action] = new_command
                    with open(mapping_file, "w", encoding="utf-8") as f:
                        json.dump(self.mapping, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to update action mapping: {e}")

    def run_ha_listener(self):
        self.start_time = time.time()
        def _target():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            def handle_async_exception(loop, context):
                msg = context.get("exception", context["message"])
                logger.error(f"Async task crash: {msg}", exc_info=context.get("exception"))

            loop.set_exception_handler(handle_async_exception)
            try:
                logger.info("Starting Home Assistant listener thread.")
                loop.run_until_complete(self.start())
            except Exception as e:
                logger.critical(f"Fatal crash in listener thread: {e}", exc_info=True)
            finally:
                logger.warning("Listener thread stopped.")

        thread = threading.Thread(target=_target, daemon=True)
        thread.start()

    async def start(self):
        while True:
            try:
                async with websockets.connect(self.uri, ping_interval=20, ping_timeout=10) as ws:
                    if await self._auth(ws):
                        await self._sub(ws)
                        self.start_time = time.time()
                        while True:
                            raw_msg = await ws.recv()
                            msg = json.loads(raw_msg)
                            if msg.get("type") == "event":
                                await self._process(msg["event"])
            except Exception as e:
                logger.error(f"Reconnecting in 5s... ({e})")
                await asyncio.sleep(5)

    async def _auth(self, ws):
        try:
            await ws.recv() 
            await ws.send(json.dumps({"type": "auth", "access_token": self.token}))
            res = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
            return res.get("type") == "auth_ok"
        except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed, Exception) as e:
            logger.error(f"Auth error: {e}")
            return False

    async def _sub(self, ws):
        await ws.send(json.dumps({"id": 1, "type": "subscribe_events"}))

    async def _process(self, event):
        if time.time() - self.start_time < 10:
            return

        edata = event.get("data", {})
        eid = edata.get("entity_id")
        if not eid or eid not in self.mapping:
            return

        attrs = edata.get("new_state", {}).get("attributes", {})
        action = edata.get("event_type") or attrs.get("event_type")

        if not action or str(action).lower() in ["unknown", "none", "unavailable"]:
            return

        if eid in self.pending_tasks:
            self.pending_tasks[eid].cancel()

        self.pending_tasks[eid] = asyncio.create_task(self._delayed_trigger(eid, action))

    async def _delayed_trigger(self, eid, action):
        try:
            await asyncio.sleep(0.5) 
            btn_config = self.mapping[eid]
            btn_name = btn_config.get("name", eid)
            custom_message = btn_config.get("actions", {}).get(action)
            if custom_message:
                await self.trigger(eid, btn_name, action, custom_message)
            self.pending_tasks.pop(eid, None)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"in delayed trigger for {eid}: {e}")
            self.pending_tasks.pop(eid, None)

    async def trigger(self, eid, name, action, command):
        logger.info(f"EXECUTION: [{name}] -> Action: {action} -> Command: {command}")

        if "TO BE CONFIGURED" in command or "NEW" in command:
            logger.info(f"Action ignored: Please edit JSON for {eid}")
            return
        if command.startswith("service:"):
            service_call = command.replace("service:", "")
            logger.info(f"Service call HA: {service_call}")
        else:
            command_info = {
                'command': command,
                'eid': eid,
                'name': name,
                'action': action,
                'callback': self.send_cmd
            }
            added = await self.command_queue.add_command(command_info)
            if added:
                logger.info(f"Command queued: '{command}'")
            else:
                logger.info(f"Command rejected by spam filter: '{command}'")

if __name__ == "__main__":
    from config_loader import cfg
    try:
        ha_listener = HAListener(cfg.home_automation)
        asyncio.run(ha_listener.start())
    except KeyboardInterrupt:
        logger.error("\nStopping the listener.")
    except Exception as e:
        logger.error(f"Fatal error: {e}")

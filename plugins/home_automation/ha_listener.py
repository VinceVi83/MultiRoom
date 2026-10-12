import asyncio
import websockets
import json
import os
import time
import threading
import subprocess
from collections import deque
from datetime import datetime
from common.conf_manager import Utils
import ast
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
            now = time.time()
            if self.is_blocked:
                if now < self.block_until:
                    logger.info(f"Command blocked until {datetime.fromtimestamp(self.block_until)}")
                    return False
                self.is_blocked = False
                logger.info("Spam protection deactivated")

            self.command_history.append({
                'timestamp': now,
                'command': command_info.get('command', ''),
                'eid': command_info.get('eid', ''),
                'action': command_info.get('action', ''),
            })
            self._clean_history(now)

            if self._is_spam(now):
                logger.warning(f"Spam detected, blocking for {self.cooldown_period}s")
                self.is_blocked = True
                self.block_until = now + self.cooldown_period
                self.queue.clear()
                return False

            command_info['timestamp'] = now
            self.queue.append(command_info)
            if self.processing_task is None or self.processing_task.done():
                self.processing_task = asyncio.create_task(self._process_queue())
            return True

    def _clean_history(self, now):
        cutoff = now - self.spam_window
        while self.command_history and self.command_history[0]['timestamp'] < cutoff:
            self.command_history.popleft()

    def _is_spam(self, now):
        if len(self.command_history) <= self.max_commands_in_window:
            return False
        recent = [c for c in self.command_history if c['timestamp'] > now - 0.5]
        if len(recent) <= self.max_commands_in_window:
            return False
        entities = {c['eid'] for c in recent if c['eid']}
        return len(entities) > 2 or len(recent) > 5

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
                age = time.time() - command_info.get('timestamp', time.time())
                if age > 5.0:
                    logger.info(f"Ignoring old command (age: {age:.2f}s)")
                    continue
                logger.info(f"Processing queued command: {command_info.get('command', '')}")
                callback = command_info.get('callback')
                if callback:
                    await asyncio.to_thread(
                        callback,
                        command_info['command'],
                        command_info.get('eid'),
                        command_info.get('action'),
                    )
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Error processing queued command: {e}", exc_info=True)


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
            cooldown_period=5.0,
        )
        self._load_mapping()

    def _load_mapping(self):
        mapping_file = os.path.join(self.cfg.config_dir, "ha_action_mapping.json")
        try:
            if os.path.exists(mapping_file):
                with open(mapping_file, "r", encoding="utf-8") as f:
                    self.mapping = json.load(f)
                logger.info(f"Loaded mapping: {len(self.mapping)} entities")
            else:
                logger.warning(f"Mapping file not found: {mapping_file}")
        except Exception as e:
            logger.error(f"Loading mapping failed: {e}", exc_info=True)

    def _update_action_mapping(self, entity_id, action, new_command):
        mapping_file = os.path.join(self.cfg.config_dir, "ha_action_mapping.json")
        try:
            if entity_id not in self.mapping:
                logger.warning(f"Entity {entity_id} not in mapping, skipping update")
                return

            entry = self.mapping[entity_id]
            if not isinstance(entry, dict):
                logger.warning(f"Unexpected mapping structure for {entity_id}")
                return

            if isinstance(entry.get("actions"), dict):
                entry["actions"][action] = new_command
            else:
                entry[action] = new_command

            with open(mapping_file, "w", encoding="utf-8") as f:
                json.dump(self.mapping, f, indent=2, ensure_ascii=False)
            logger.info(f"Updated mapping {entity_id}/{action} -> {new_command}")
        except Exception as e:
            logger.error(f"Failed to update mapping: {e}", exc_info=True)

    def _parse_and_learn_from_output(self, output, entity_id, action, original_command):
        if isinstance(output, dict):
            data = output
        else:
            if not output or not output.strip():
                return
            json_str = output.strip()
            if '{' in json_str and '}' in json_str:
                first_brace = json_str.find('{')
                last_brace = json_str.rfind('}')
                if first_brace < last_brace:
                    json_str = json_str[first_brace:last_brace + 1]
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError:
                try:
                    data = ast.literal_eval(json_str)
                except (ValueError, SyntaxError) as e:
                    logger.error(f"Failed to parse learning output: {e}")
                    return
        if not isinstance(data, dict):
            return

        return_code = data.get('return_code') or data.get('returnCode') or data.get('ReturnCode')
        rc_str = str(return_code).upper() if return_code else ""
        if 'NOTHING_TO_DO' in rc_str:
            return
        if 'SUCCESS' not in rc_str:
            return

        category = data.get('category') or data.get('Category') or "Unknown"
        location = data.get('location') or data.get('Location') or "Unknown"
        sub_cat_data = data.get('sub_category') or data.get('subCategory')
        if isinstance(sub_cat_data, dict):
            sub_category = sub_cat_data.get('label') or "Unknown"
        elif sub_cat_data:
            sub_category = sub_cat_data
        else:
            sub_category = "Unknown"

        if sub_category == "Unknown":
            return

        full_native_command = f"@{category.lower()};-;{location};-;{sub_category};-;Unknown"
        self._update_action_mapping(entity_id, action, full_native_command)
        logger.info(f"Learned {entity_id}/{action}: '{original_command}' -> '{full_native_command}'")

    @staticmethod
    def _extract_output(result):
        if result is None:
            return ""
        if isinstance(result, str):
            return result
        if isinstance(result, (tuple, list)):
            return "".join(str(p) for p in result if p)
        if isinstance(result, dict):
            return json.dumps(result)
        return str(result)

    def send_cmd(self, content, entity_id=None, action=None):
        try:
            result = Utils.send_command_multiroom(content.strip())
            logger.info(f"send_cmd result: {result}")

            if entity_id and action and not content.startswith('@'):
                output = self._extract_output(result)
                if output and output.strip():
                    self._parse_and_learn_from_output(output, entity_id, action, content)
            return result
        except Exception as e:
            logger.error(f"send_cmd error: {e}", exc_info=True)
            return None

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
                logger.info("Starting Home Assistant listener thread")
                loop.run_until_complete(self.start())
            except Exception as e:
                logger.critical(f"Fatal crash in listener thread: {e}", exc_info=True)
            finally:
                logger.warning("Listener thread stopped")

        threading.Thread(target=_target, daemon=True).start()

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
        except Exception as e:
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

        if not action or str(action).lower() in ("unknown", "none", "unavailable"):
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
            logger.error(f"delayed_trigger error for {eid}: {e}", exc_info=True)
            self.pending_tasks.pop(eid, None)

    async def trigger(self, eid, name, action, command):
        logger.info(f"EXECUTION: [{name}] -> {action} -> {command}")

        if "TO BE CONFIGURED" in command or "NEW" in command:
            logger.info(f"Action ignored, edit JSON for {eid}")
            return
        if command.startswith("service:"):
            logger.info(f"Service call HA: {command.replace('service:', '')}")
            return

        added = await self.command_queue.add_command({
            'command': command,
            'eid': eid,
            'name': name,
            'action': action,
            'callback': self.send_cmd,
        })
        if added:
            logger.info(f"Command queued: '{command}'")
        else:
            logger.info(f"Command rejected by spam filter: '{command}'")


if __name__ == "__main__":
    from common.conf_manager import cfg
    try:
        ha_listener = HAListener(cfg.home_automation)
        asyncio.run(ha_listener.start())
    except KeyboardInterrupt:
        logger.error("Stopping the listener")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)

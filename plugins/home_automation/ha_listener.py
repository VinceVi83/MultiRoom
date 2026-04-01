import asyncio
import websockets
import json
import os
from config_loader import cfg
from tools.hub_messenger import HubMessenger

class HAListener:
    """Home Assistant WebSocket Event Listener
    
    Role: Monitors Home Assistant events and triggers corresponding actions via AI Hub.
    
    Methods:
        __init__(self) : Initialize listener with config, mapping, and hub messenger.
        _load_mapping(self) : Load action mapping from JSON file.
        start(self) : Main loop to connect to WebSocket and process events.
        _auth(self, ws) : Authenticate with Home Assistant WebSocket.
        _sub(self, ws) : Subscribe to events.
        _process(self, event) : Process incoming event data.
        _delayed_trigger(self, eid, action) : Delayed action trigger with error handling.
        trigger(self, eid, name, action, command) : Execute the actual command/service call.
    """
    def __init__(self, cfg):
        self.cfg = cfg
        self.uri = f"ws://{self.cfg.home_automation.ha_config.HA_HOSTNAME}:8123/api/websocket"
        self.token = self.cfg.home_automation.ha_config.HA_TOKEN
        self.mapping = {}
        self.pending_clicks = {}
        self._load_mapping()

        user = "system"
        pwd = ""
        for i in self.cfg.sys.LIST_USERS:
            if i == "system" and i in self.cfg.sys.security.DICO_USERS.keys():
                pwd = self.cfg.sys.security.DICO_USERS[user]

        self.messenger = HubMessenger(
            host="127.0.0.1",
            port=self.cfg.sys.config.HUB_PORT,
            user=user,
            password=pwd
        )

    def _load_mapping(self):
        mapping_file = os.path.join(self.cfg.home_automation.DATA_DIR, "ha_action_mapping.json")
        try:
            if os.path.exists(mapping_file):
                with open(mapping_file, "r", encoding="utf-8") as f:
                    self.mapping = json.load(f)
        except Exception as e:
            print(f"Error loading mapping: {e}")

    async def start(self):
        while True:
            try:
                async with websockets.connect(self.uri, ping_interval=20, ping_timeout=10) as ws:
                    if await self._auth(ws):
                        await self._sub(ws)
                        while True:
                            raw_msg = await ws.recv()
                            msg = json.loads(raw_msg)
                            if msg.get("type") == "event":
                                self._process(msg["event"])
            except Exception as e:
                print(f"Reconnecting in 5s... ({e})")
                await asyncio.sleep(5)

    async def _auth(self, ws):
        try:
            await ws.recv() 
            await ws.send(json.dumps({"type": "auth", "access_token": self.token}))
            res = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
            return res.get("type") == "auth_ok"
        except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed, Exception) as e:
            print(f"Auth error: {e}")
            return False

    async def _sub(self, ws):
        await ws.send(json.dumps({"id": 1, "type": "subscribe_events"}))

    def _process(self, event):
        edata = event.get("data", {})
        eid = edata.get("entity_id")
        
        if not eid or eid not in self.mapping:
            return

        attrs = edata.get("new_state", {}).get("attributes", {})
        action = edata.get("event_type") or attrs.get("event_type")

        if not action or str(action).lower() in ["unknown", "none", "unavailable"]:
            return

        if eid in self.pending_clicks:
            self.pending_clicks[eid].cancel()

        self.pending_clicks[eid] = asyncio.create_task(self._delayed_trigger(eid, action))

    async def _delayed_trigger(self, eid, action):
        try:
            await asyncio.sleep(0.5) 
            
            btn_config = self.mapping[eid]
            btn_name = btn_config.get("name", eid)
            custom_message = btn_config.get("actions", {}).get(action)

            if custom_message:
                self.trigger(eid, btn_name, action, custom_message)
            
            self.pending_clicks.pop(eid, None)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Error in delayed trigger for {eid}: {e}")
            self.pending_clicks.pop(eid, None)

    def trigger(self, eid, name, action, command):
        print(f"EXECUTION: [{name}] -> Action: {action} -> Command: {command}")

        if "TO BE CONFIGURED" in command or "NEW" in command:
            print(f"Action ignored: Please edit JSON for {eid}")
            return

        if command.startswith("service:"):
            service_call = command.replace("service:", "")
            print(f"Service call HA: {service_call}")
        else:
            print(f"Sending to AI Hub: '{command}'")
            asyncio.create_task(
                asyncio.to_thread(self.messenger.send_stt, command, False)
            )

if __name__ == "__main__":
    try:
        asyncio.run(HAListener().start())
    except KeyboardInterrupt:
        print("\nStopping the listener.")
    except Exception as e:
        print(f"Fatal error: {e}")

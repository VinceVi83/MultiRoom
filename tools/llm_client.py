import socket
import time
import json
import asyncio
from typing import Dict
from ollama import Client, AsyncClient
import requests
from config.conf_manager import cfg, setup_logging
import threading
import logging

logger = logging.getLogger(__name__)

def _process_llm_result(response):
    logger.info(response)
    content = response.message.content.strip()
    if not content:
        return None
    start = content.find('{')
    end = content.rfind('}')
    if start != -1 and end != -1:
        try:
            data = json.loads(content[start:end + 1])
            return {k.lower(): v for k, v in data.items()} if isinstance(data, dict) else {"content": content}
        except:
            pass
    return {"content": content}

def get_llm_config(mode: str = 'instruct'):
    configs = {
        'instruct': {
            'model': 'qwen2.5:3b',
            'options': {
                'num_predict': 256,
                'temperature': 0.1,
                'top_p': 0.5,
                'top_k': 10,
                'repeat_penalty': 1.5,
                'presence_penalty': 0.5,
                'frequency_penalty': 0.5
            }
        },
        'summarize': {
            'model': 'qwen2.5:3b',
            'options': {
                'num_predict': 512,
                'temperature': 0.1,
                'top_p': 0.5,
                'top_k': 10,
                'repeat_penalty': 1.5,
                'presence_penalty': 0.5,
                'frequency_penalty': 0.5
            }
        },
        'creative': {
            'model': 'qwen2.5:7b',
            'options': {
                'num_predict': 512,
                'temperature': 1.2,
                'top_p': 0.95,
                'repeat_penalty': 1.1
            }
        }
    }
    cfg = configs.get(mode, configs['instruct'])
    return cfg['model'], cfg['options']

class LLMRequest:
    """
    LLM request configuration builder for Ollama API calls.

    Operates as follows:
        1. Initializes with system prompt, user prompt, and optional model/options/mode.
        2. Loads default model and options from get_llm_config based on the specified mode.
        3. get_payload() formats the configuration into a dictionary for Ollama API consumption.

    Methods:
        __init__(self, system_prompt, user_prompt, model=None, options=None, mode='instruct') : Initializes with prompts and optional configuration.
        get_payload(self) : Returns formatted payload for Ollama chat API.

    Usage:
        config = LLMRequest(system_prompt="You are helpful", user_prompt="Hello")
        payload = config.get_payload()
    """
    def __init__(self, system_prompt, user_prompt, model=None, options=None, mode='instruct'):
        default_model, default_options = get_llm_config(mode)
        self.model = model or default_model
        self.options = options or default_options
        self.messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

    def get_payload(self):
        return {
            "model": self.model,
            "messages": self.messages,
            "options": self.options
        }

class OllamaServiceAsync:
    """
    Asynchronous service for LLM interactions via Ollama API.

    Operates as follows:
        1. Initializes AsyncClient with the specified server URL.
        2. generate() sends async chat request via client.chat() and processes result.
        3. call() creates LLMRequest and calls generate() for simplified usage.

    Methods:
        __init__(self, url) : Initializes async client with server URL.
        generate(self, config) : Executes async LLM generation and returns processed result.
        call(self, system_prompt, user_prompt, model=None, options=None, mode='instruct') : Convenience method creating config and generating response.

    Usage:
        service = OllamaServiceAsync("http://localhost:11434")
        result = await service.call("You are helpful", "Hello")
    """

    def __init__(self, url):
        self.url = url
        self.client = AsyncClient(host=self.url)

    async def generate(self, config):
        try:
            response = await self.client.chat(**config.get_payload())
            return _process_llm_result(response)
        except Exception as e:
            return {"content": str(e), "error": f"LLM_CALL_FAILED: {str(e)}"}

    async def call(self, system_prompt, user_prompt, model=None, options=None, mode='instruct'):
        config = LLMRequest(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            options=options,
            mode=mode
        )
        return await self.generate(config)

class OllamaService:
    """
    Synchronous service for LLM interactions with WAN/LAN fallback and health monitoring.

    Operates as follows:
        1. Initializes sync clients for LAN and optional WAN URLs.
        2. Starts background thread via _monitor_loop to track endpoint availability.
        3. _monitor_loop periodically checks WAN/LAN connectivity with adaptive intervals.
        4. generate() routes requests to WAN (if available) or LAN, with automatic model fallback.
        5. call() creates LLMRequest and calls generate().

    Handles multiple locations: WAN and LAN endpoints with automatic failover.

    Methods:
        __init__(self, url_lan, url_wan=None) : Initializes clients and starts monitoring thread.
        list(self) : Returns available models from local client.
        _monitor_loop(self) : Background thread monitoring endpoint health.
        generate(self, config_obj) : Generates response with automatic WAN/LAN routing and fallback.
        call(self, system_prompt, user_prompt, model=None, options=None, mode='instruct') : Convenience method creating config and generating response.

    Usage:
        service = OllamaService("http://localhost:11434", "http://remote:11434")
        result = service.call("You are helpful", "Hello")
    """

    def __init__(self, url_lan, url_wan=None):
        self.local_url = url_lan
        self.wan_url = url_wan
        self.client_local = Client(host=self.local_url)
        self.client_wan = Client(host=self.wan_url) if self.wan_url else None
        self.is_ready = False
        self.wan_available = False
        self._interrupt_monitor = threading.Event()
        threading.Thread(target=self._monitor_loop, daemon=True).start()

    def list(self):
        return self.client_local.list()

    def _monitor_loop(self):
        last_wan_state = None
        while True:
            wait_time = 600
            if self.wan_url:
                try:
                    self.wan_available = requests.get(f"{self.wan_url}/api/version", timeout=1.5).status_code == 200
                except:
                    self.wan_available = False
            try:
                self.is_ready = requests.get(f"{self.local_url}/api/version", timeout=1.0).status_code == 200
            except:
                self.is_ready = False
            if not self.is_ready or not self.wan_available:
                wait_time = 60

            if self.wan_available != last_wan_state:
                if not self.wan_available:
                    logger.warning(f"WAN DISCONNECTED | Switching to 1min monitoring")
                else:
                    logger.info(f"WAN CONNECTED | Standard monitoring (10min)")
                last_wan_state = self.wan_available
            self._interrupt_monitor.wait(timeout=wait_time)
            self._interrupt_monitor.clear()

    def generate(self, config_obj):
        payload = config_obj.get_payload()
        logger.info(f"Payload: {payload}")
        if self.wan_available and self.client_wan:
            client = self.client_wan
            if not payload['model']:
                target_model = getattr(cfg.llm, 'default_model_wan', payload['model'])
                config_obj.model = target_model
            network_type = "WAN"
        else:
            client = self.client_local
            if not payload['model']:
                target_model = getattr(cfg.llm, 'default_model_lan', payload['model'])
                config_obj.model = target_model
            network_type = "LAN"

        try:
            logger.info(f"Dispatching to {network_type} | Model: {config_obj.model}")
            resp = client.chat(**config_obj.get_payload())
            logger.info(f"LLM Resp {resp}")
            return _process_llm_result(resp)
        except Exception as e:
            logger.error(f"{network_type} Failed: {e}")
            if client == self.client_wan:
                target_model = getattr(cfg.llm, 'fallback_model_wan', payload['model'])
                config_obj.model = target_model
                resp = client.chat(**config_obj.get_payload())
                return _process_llm_result(resp)
            raise e

    def call(self, system_prompt, user_prompt, model=None, options=None, mode='instruct'):
        config = LLMRequest(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            options=options,
            mode=mode
        )
        return self.generate(config)

class LLMGatewayClient:
    """
    Client for interacting with LLM Gateway server with Wake-on-LAN support.

    Operates as follows:
        1. Initializes with server IP, port, MAC address, and wakeup port.
        2. _tcp_check verifies TCP connectivity to the gateway server.
        3. If server is unreachable, _send_wol broadcasts Wake-on-LAN magic packet.
        4. _wait_for_wakeup blocks for up to 60 seconds waiting for server response.
        5. _notify_wol_success calls /wol-ack endpoint to confirm wakeup.
        6. generate() sends formatted request to /call-llm endpoint.
        7. call() orchestrates full workflow including WOL if necessary.

    Methods:
        __init__(self, server_ip, port, server_mac, wakeup_port, timeout=120) : Initializes client configuration.
        _tcp_check(self) : Checks TCP connectivity to gateway server.
        _send_wol(self) : Sends Wake-on-LAN magic packet to server MAC address.
        _notify_wol_success(self) : Notifies gateway of successful wakeup via /wol-ack.
        _wait_for_wakeup(self) : Waits for server to become reachable after WOL.
        generate(self, config_obj) : Sends request to /call-llm endpoint and returns response.
        call(self, system_prompt, user_prompt, model=None, options=None, mode='instruct') : Executes full request workflow with WOL support.

    Usage:
        client = LLMGatewayClient("192.168.1.100", 8000, "aa:bb:cc:dd:ee:ff", 9)
        result = client.call("You are helpful", "Hello")
    """
    def __init__(self, server_ip, port, server_mac, wakeup_port, timeout=120):
        self.base_url = f"http://{server_ip}:{port}"
        self.server_ip = server_ip
        self.server_mac = server_mac
        self.wakeup_port = wakeup_port
        self.timeout = timeout
        self.session = requests.Session()
        self.wan_available = True

    def _tcp_check(self):
        try:
            with socket.create_connection((self.server_ip, self.wakeup_port), timeout=1):
                return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            return False

    def _send_wol(self):
        logger.info(f"[LLMGatewayClient] AI PC unreachable, sending WOL to {self.server_mac}")
        mac_clean = self.server_mac.replace(":", "").replace("-", "")
        if len(mac_clean) != 12:
            raise ValueError(f"Invalid MAC address: {self.server_mac}")
        mac_bytes = bytes.fromhex(mac_clean)
        magic_packet = b'\xff' * 6 + mac_bytes * 16
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            s.sendto(magic_packet, ('<broadcast>', 9))
        logger.info(f"[LLMGatewayClient] Magic packet sent to {self.server_mac}")

    def _notify_wol_success(self):
        try:
            requests.post(f"{self.base_url}/wol-ack", timeout=5)
            logger.info("[LLMGatewayClient] /tmp/wol created on AI PC.")
        except requests.RequestException as e:
            logger.info(f"[LLMGatewayClient] Failed to notify wol-ack: {e}")

    def _wait_for_wakeup(self):
        start_time = time.time()
        while time.time() - start_time < 60:
            if self._tcp_check():
                return True
            time.sleep(1)
        return False

    def generate(self, config_obj) -> Dict:
        p = config_obj.get_payload()
        payload = {
            "system_prompt": p['messages'][0]['content'],
            "prompt": p['messages'][1]['content'],
            "model": p['model'],
            "options": p['options']
        }
        try:
            resp = self.session.post(f"{self.base_url}/call-llm", json=payload, timeout=self.timeout)
            resp.raise_for_status()
            return {"content": resp.json().get("result", "")}
        except Exception as e:
            return {"content": str(e), "error": f"GATEWAY_FAILED: {e}"}

    def call(self, system_prompt, user_prompt, model=None, options=None, mode='instruct'):
        config = LLMRequest(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            options=options,
            mode=mode
        )
        if self._tcp_check():
            logger.info("[LLMGatewayClient] AI PC reachable, sending request directly...")
            return self.generate(config)
        self._send_wol()
        if not self._wait_for_wakeup():
            raise TimeoutError("AI PC not responding after WOL.")
        self._notify_wol_success()
        return self.generate(config)

class LLMGatewayClientAsync:
    """
    Asynchronous wrapper for LLMGatewayClient using asyncio.

    Operates as follows:
        1. Initializes with synchronous LLMGatewayClient instance.
        2. generate() runs sync generate() in a thread via asyncio.to_thread.
        3. call() creates LLMRequest and calls generate().

    Methods:
        __init__(self, server_ip, port, server_mac, wakeup_port) : Initializes with sync client parameters.
        generate(self, config_obj) : Executes sync generate asynchronously in a thread.
        call(self, system_prompt, user_prompt, model=None, options=None, mode='instruct') : Convenience method creating config and generating response.

    Usage:
        client = LLMGatewayClientAsync("192.168.1.100", 8000, "aa:bb:cc:dd:ee:ff", 9)
        result = await client.call("You are helpful", "Hello")
    """
    def __init__(self, server_ip, port, server_mac, wakeup_port):
        self._sync = LLMGatewayClient(server_ip, port, server_mac, wakeup_port)

    async def generate(self, config_obj):
        return await asyncio.to_thread(self._sync.generate, config_obj)

    async def call(self, system_prompt, user_prompt, model=None, options=None, mode='instruct'):
        config = LLMRequest(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            options=options,
            mode=mode
        )
        return await self.generate(config)

def init_llm_service():
    try:
        llm = LLMGatewayClient(
            cfg.llm_gateway.server_ip,
            cfg.llm_gateway.port,
            cfg.llm_gateway.server_mac,
            cfg.llm_gateway.wakeup_port
        )
        llm_async = LLMGatewayClientAsync(
            cfg.llm_gateway.server_ip,
            cfg.llm_gateway.port,
            cfg.llm_gateway.server_mac,
            cfg.llm_gateway.wakeup_port
        )
        base_url = f"http://{cfg.llm_gateway.server_ip}:{cfg.llm_gateway.port}"
        logger.info("LLMGateway connected successfully")
        return llm, llm_async, base_url
    except Exception as e:
        logger.info(f"LLMGateway not available: {e}")
        try:
            base_url = getattr(cfg.llm.lan_url, 'local_url', "http://127.0.0.1:11434")
            wan_url = getattr(cfg.llm.wan_url, 'wan_url', None)
            llm = OllamaService(base_url, wan_url)
            llm_async = OllamaServiceAsync(base_url)
            logger.info(f"Fallback Ollama connected on {base_url}")
            return llm, llm_async, base_url
        except Exception as e2:
            raise RuntimeError(
                f"No LLM service available:\n"
                f"  - LLMGateway: {e}\n"
                f"  - Ollama: {e2}"
            )

llm, llm_async, base_url = init_llm_service()
model, options = get_llm_config('instruct')

def test_llm_call():
    result = llm.call(
        system_prompt="You are a Python expert assistant",
        user_prompt="Explain decorators"
    )
    logger.info(result['content'])

    result = llm.call(
        system_prompt="You are a Python expert assistant",
        user_prompt="Explain decorators",
        model=model,
        options=options
    )
    logger.info(result['content'])

async def test_llm_call_async():
    result = await llm_async.call(
        system_prompt="You are a Python expert assistant",
        user_prompt="Explain decorators"
    )
    logger.info(result['content'])

if __name__ == "__main__":
    setup_logging()
    try:
        r = requests.get(f"{base_url}/models")
        logger.info(f"Available models {base_url}: {r.json()}")
    except Exception as e:
        try:
            models_data = llm.client_local.list()
            models = models_data.models if hasattr(models_data, 'models') else models_data.get('models', [])
            logger.info(f"Available models on {base_url}:")
            for m in models:
                name = m.model if hasattr(m, 'model') else m.get('name', str(m))
                logger.info(f"  - {name}")
        except Exception as e:
            logger.info(f"Could not list models: {e}")

    test_llm_call()
    asyncio.run(test_llm_call_async())

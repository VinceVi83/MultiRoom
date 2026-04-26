import threading
import ollama
import json
import requests
import time
from config_loader import cfg
from types import SimpleNamespace
import threading
import logging
logger = logging.getLogger(__name__)

class OllamaClient:
    """Ollama API Client for LLM interactions
    
    Role: Manages Ollama connections, model management, and executes LLM queries.
    
    Methods:
        __init__(self) : Initialize the Ollama client with configuration.
        _check_connection(self) : Verify Ollama server connectivity.
        _start_reconnect_thread(self) : Start background reconnection thread.
        _reconnect_loop(self) : Loop to reconnect when offline.
        _print_verbose(self, message) : Print message if verbose mode is enabled.
        _print_debug(self, message) : Print message if debug mode is enabled.
        normalize_keys(self, d) : Normalize dictionary keys to lowercase.
        execute(self, user_input, agent_cfg=None) : Execute LLM query.
        manage_vram(self, target_model) : Manage VRAM by switching models.
        _prepare(self, c, user_input) : Prepare request parameters.
    """
    def __init__(self):
        self.local_url = cfg.sys.config.OLLAMA_SERVER_LAN
        self.wan_url = cfg.sys.config.OLLAMA_SERVER_WAN

        self.client_local = ollama.Client(host=self.local_url)
        self.client_wan = ollama.Client(host=self.wan_url) if self.wan_url else None
        self.main_model = cfg.sys.config.MODEL_NAME_MAIN
        self.current_model = None
        self._lock = threading.Lock()
        self.is_ready = True
        
        threading.Thread(target=self._monitor_loop, daemon=True).start()

    def _monitor_loop(self):
        while True:
            if self.wan_url:
                try:
                    self.wan_available = requests.get(f"{self.wan_url}/api/version", timeout=1.5).status_code == 200
                except:
                    self.wan_available = False
            try:
                self.is_ready = requests.get(f"{self.local_url}/api/version", timeout=1.0).status_code == 200
            except:
                self.is_ready = False
            
            time.sleep(600)

    def _print_debug(self, message):
        if not self.is_ready:
            return
        if not cfg.debug:
            return
        logger.debug(message)
        
    def _print_verbose(self, message):
        if not self.is_ready:
            return
        if not cfg.verbose:
            return
        logger.info(message)

    def normalize_keys(self, d):
        if isinstance(d, dict):
            return {k.lower(): self.normalize_keys(v) for k, v in d.items()}
        return d

    def execute(self, user_input, agent_cfg=None):
        if not self.is_ready and not self.wan_available:
            return {"error": "Ollama is offline", "status": "reconnecting"}
        
        if agent_cfg and getattr(agent_cfg, 'model', None) is None:
            agent_cfg.model = self.main_model

        with self._lock:
            is_wan = self.wan_available and self.client_wan
            client = self.client_wan if is_wan else self.client_local
            active_url = self.wan_url if is_wan else self.local_url
            self.manage_vram(agent_cfg.model, active_url)

            try:
                self._print_verbose("TARGET MODEL  : " + agent_cfg.model)
                self._print_verbose("SYSTEM PROMPT : " + agent_cfg.prompt + "...")
                self._print_verbose("USER INPUT    : " + user_input)

                response = client.chat(**self._prepare(agent_cfg, user_input))
                content = response['message']['content'].strip()

                if agent_cfg.use_json:
                    result = json.loads(content)
                elif "{" in content and "}" in content:
                    try:
                        start = content.find('{')
                        end = content.rfind('}') + 1
                        raw_dict = json.loads(content[start:end])
                        result = {str(k).strip().upper(): v for k, v in raw_dict.items()}
                    except json.JSONDecodeError:
                        result = {"report": content, "error": "json.JSONDecodeError"}
                    except Exception as e:
                        result = {"report": content, "error": "json.JSONDecodeError"}
                else:
                    result = content
                    
                self._print_verbose("RESULT        : " + str(result))
                o_load   = response.get('load_duration', 0) / 1e9
                o_p_eval = response.get('prompt_eval_duration', 0) / 1e9
                o_eval   = response.get('eval_duration', 0) / 1e9
                inference_time = o_p_eval + o_eval
                metrics = {
                    "o_load": o_load, 
                    "inference_time": inference_time
                }
                if isinstance(result, dict):
                        result = result | metrics
                else:
                    result = {"content": result} | metrics

                if cfg.debug:
                    o_total  = response.get('total_duration', 0) / 1e9
                    self._print_debug("MODEL & AGENT      : " + f"{agent_cfg.name} {agent_cfg.model} \n")
                    self._print_debug("Load Time (VRAM)   : " + str(o_load) + ".3fs")
                    self._print_debug("Inference (GPU)    : " + str(inference_time) + ".3fs")
                    self._print_debug("TOTAL DURATION     : " + str(o_total) + ".3fs\n")

                result = self.normalize_keys(result)
                if isinstance(result, dict):
                    result['engine'] = 'wan' if is_wan else 'local'
                return result

            except Exception as e:
                if is_wan:
                    self.wan_available = False
                    logger.warning(f"WAN failed: {e}. Retrying locally...")
                    return self.execute(user_input, agent_cfg) # Récursion vers le local
                
                self.is_ready = False
                return {'id': '0', 'error': str(e)}

    def manage_vram(self, target_model, url):
        if self.current_model and self.current_model != target_model:
            try:
                requests.post(f"{url}/api/generate", 
                             json={"model": self.current_model, "keep_alive": 0}, 
                             timeout=1)
            except:
                pass
        self.current_model = target_model

    def _prepare(self, c, user_input):
        params = c.to_dict()
        params["messages"] = params["messages"] + [{"role": "user", "content": user_input}]
        return params


def create_agent_config(prompt, model=None, use_json=True, **custom_options):
    base_options = {
        "seed": 42,
        "temperature": 0.0,
        "num_predict": 100,
        "num_ctx": 4096,
        "top_k": 1,
        "top_p": 0.0
    }
    base_options.update(custom_options)

    return SimpleNamespace(
        model=model or cfg.MODEL_NAME_MAIN,
        prompt=prompt,
        use_json=use_json,
        options=SimpleNamespace(**base_options)
    )


llm = OllamaClient()

if __name__ == "__main__":
    config_from_yaml = cfg.ALL_PURPOSE.ROUTER_AGENT
    result = llm.execute("Turn on the living room light", agent_cfg=cfg.ALL_PURPOSE.LOCATION_CLEANER_AGENT)
    result = llm.execute("I want to listen to my Touhou playlist", agent_cfg=config_from_yaml)
    result = llm.execute("Stop the music", agent_cfg=config_from_yaml)
    result = llm.execute("I need to buy butter, eggs, steaks", agent_cfg=config_from_yaml)

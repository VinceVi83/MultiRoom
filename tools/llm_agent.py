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
        execute(self, user_input, agent_cfg=None, debug=False, verbose=False) : Execute LLM query.
        manage_vram(self, target_model) : Manage VRAM by switching models.
        _prepare(self, c, user_input) : Prepare request parameters.
    """
    def __init__(self):
        self.base_url = cfg.sys.config.OLLAMA_SERVER
        self.client = ollama.Client(host=self.base_url)
        self.main_model = cfg.sys.config.MODEL_NAME_MAIN
        self.current_model = None
        self.debug = False
        self.verbose = False
        self._lock = threading.Lock()
        
        self.is_ready = True
        self.retry_count = 0
        self.max_delay = 3600
        
        self._check_connection()

    def _check_connection(self):
        try:
            self.client.list()
            self.is_ready = True
            self.retry_count = 0
        except:
            self.is_ready = False
            self._start_reconnect_thread()

    def _start_reconnect_thread(self):
        thread = threading.Thread(target=self._reconnect_loop, daemon=True)
        thread.start()

    def _reconnect_loop(self):
        while not self.is_ready:
            self.retry_count += 1
            delay = min(self.retry_count ** 2, self.max_delay)
            time.sleep(delay)
            try:
                self.client.list()
                self.is_ready = True
                self.retry_count = 0
            except:
                pass

    def _print_debug(self, message):
        if not self.is_ready:
            return
        if not self.debug:
            return
        logger.debug(message)
        
    def _print_verbose(self, message):
        if not self.is_ready:
            return
        if not self.verbose:
            return
        logger.info(message)

    def normalize_keys(self, d):
        if isinstance(d, dict):
            return {k.lower(): self.normalize_keys(v) for k, v in d.items()}
        return d

    def execute(self, user_input, agent_cfg=None, debug=False, verbose=False):
        self.verbose = verbose
        self.debug = debug
        if not self.is_ready:
            return {"error": "Ollama is offline", "status": "reconnecting"}

        with self._lock:
            self.manage_vram(agent_cfg.model)
            agent_cfg_final = agent_cfg
            agent_cfg_final.user_input = user_input

            try:
                self._print_verbose("TARGET MODEL  : " + agent_cfg_final.model)
                self._print_verbose("SYSTEM PROMPT : " + agent_cfg_final.prompt + "...")
                self._print_verbose("USER INPUT    : " + user_input)

                response = self.client.chat(**self._prepare(agent_cfg, user_input))
                content = response['message']['content'].strip()

                if agent_cfg_final.use_json:
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

                if self.debug:
                    o_total  = response.get('total_duration', 0) / 1e9
                    self._print_debug("MODEL & AGENT      : " + f"{agent_cfg.name} {agent_cfg.model} \n")
                    self._print_debug("Load Time (VRAM)   : " + str(o_load) + ".3fs")
                    self._print_debug("Inference (GPU)    : " + str(inference_time) + ".3fs")
                    self._print_debug("TOTAL DURATION     : " + str(o_total) + ".3fs\n")

                result = self.normalize_keys(result)
                return result

            except Exception as e:
                self.is_ready = False
                self._start_reconnect_thread()
                return {'ID': '0', 'error': str(e)}

    def manage_vram(self, target_model):
        if self.current_model is not None and self.current_model != target_model:
            self._print_debug("manage_vram change model")
            try:
                requests.post(
                    f"{self.base_url}/api/generate",
                    json={"model": self.current_model, "keep_alive": 0},
                    timeout=5
                )
            except Exception:
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
    result = llm.execute("Turn on the living room light", agent_cfg=cfg.ALL_PURPOSE.LOCATION_CLEANER_AGENT, verbose=True)
    result = llm.execute("I want to listen to my Touhou playlist", agent_cfg=config_from_yaml, verbose=True)
    result = llm.execute("Stop the music", agent_cfg=config_from_yaml, verbose=True)
    result = llm.execute("I need to buy butter, eggs, steaks", agent_cfg=config_from_yaml, verbose=True)

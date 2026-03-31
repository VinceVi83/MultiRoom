import threading
import ollama
import json
import requests
import time
from config_loader import cfg
from types import SimpleNamespace
import threading


class OllamaClient:
    """Ollama Client
    
    Role: Thread-safe singleton client to manage Ollama interactions and VRAM optimization.
    
    Methods:
        __init__(self) : Initializes the client using centralized configuration.
        execute(self, user_input, agent_cfg=None, debug=False, verbose=False) : Executes a synchronized LLM request for a specific agent.
        manage_vram(self, target_model) : Unloads the current model if a different one is requested.
        _prepare(self, c, user_input) : Formats the cfg object for self.client.chat(**...).
    """

    def __init__(self):
        self.base_url = cfg.sys.config.OLLAMA_SERVER
        self.client = ollama.Client(host=self.base_url)
        self.main_model = cfg.sys.config.MODEL_NAME_MAIN
        self.current_model = None
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

    def execute(self, user_input, agent_cfg=None, debug=False, verbose=False):
        if not self.is_ready:
            return {"error": "Ollama is offline", "status": "reconnecting"}

        with self._lock:
            self.manage_vram(agent_cfg.model)
            agent_cfg_final = agent_cfg
            agent_cfg_final.user_input = user_input

            try:
                if verbose:
                    print(f"\n{'='*20} VERBOSE MODE {'='*20}")
                    print(f"TARGET MODEL  : {agent_cfg_final.model}")
                    print(f"SYSTEM PROMPT : {agent_cfg_final.prompt}...")
                    print(f"USER INPUT    : {user_input}")

                response = self.client.chat(**self._prepare(agent_cfg, user_input))

                content = response['message']['content'].strip()
                result = json.loads(content) if agent_cfg_final.use_json else content

                if verbose:
                    print(f"RESULT        : {result}")
                    print(f"{'='*54}")

                if debug:
                    o_load   = response.get('load_duration', 0) / 1e9
                    o_p_eval = response.get('prompt_eval_duration', 0) / 1e9
                    o_eval   = response.get('eval_duration', 0) / 1e9
                    o_total  = response.get('total_duration', 0) / 1e9

                    inference_time = o_p_eval + o_eval

                    print(f"\n--- PERFORMANCE ---")
                    print(f"Load Time (VRAM)   : {o_load:.3f}s")
                    print(f"Inference (GPU)    : {inference_time:.3f}s")
                    print(f"TOTAL DURATION     : {o_total:.3f}s\n")

                return result

            except Exception as e:
                self.is_ready = False
                self._start_reconnect_thread()
                return {'ID': '0', 'error': str(e)}

    def manage_vram(self, target_model):
        if self.current_model and self.current_model != target_model:
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
    """Generates an agent config using MODEL_NAME_MAIN by default"""
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

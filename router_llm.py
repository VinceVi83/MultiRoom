import queue
import threading
import json
import time
import importlib
from config_loader import cfg
from tools.llm_agent import llm
from tools.task_context import TaskContext
from tools.utils import Utils

class RouterLLM:
    """AI Router module that orchestrates intent detection, interactive web research, and service dispatching.

    Methods:
        __init__(self) : Initializes the RouterLLM instance with command queue, threading, and service instances.
        add_to_queue(self, context) : Adds a TaskContext to the command queue for processing.
        _initialize_service_registry(self) : Builds the service registry from loaded plugins.
        select_and_execute(self, context) : Detects intent via LLM and calls the appropriate service immediately.
        inference_loop(self) : Background worker processing the command queue.
        format_result(self, result) : Transforms a dictionary into a string 'KEY:Value' or returns the raw string.
        start(self) : Starts the inference loop in a separate daemon thread.
        stop(self) : Stops the inference loop and waits for thread completion.
    """

    def __init__(self):
        self.command_queue = queue.Queue()
        self.service_registry = {}
        self.is_running = True
        self.debug = False
        self._initialize_service_registry()
        self.start()

    def add_to_queue(self, context):
        if isinstance(context, TaskContext):
            self.command_queue.put(context)

    def _initialize_service_registry(self):
        if self.debug:
            print("\n--- [Router] Building Service Registry ---")

        for i, plugin_name in enumerate(cfg.LOADED_PLUGINS, start=1):
            try:

                module_path = f"plugins.{plugin_name}.service"
                module = importlib.import_module(module_path)
                class_name = "".join([x.capitalize() for x in plugin_name.split('_')]) + "Service"

                if hasattr(module, class_name):
                    service_class = getattr(module, class_name)
                    instance = service_class()

                    instance.plugin_name = plugin_name

                    self.service_registry[str(i)] = instance
                    if self.debug:
                        print(f"  [ID {i}] Registered: {plugin_name} ({class_name})")
                else:
                    print(f"  [!] Class {class_name} not found in {module_path}")

            except Exception as e:
                print(f"  [!] Failed to load {plugin_name}: {e}")

    def select_and_execute(self, context):
        start_total = time.time()

        category_res = llm.execute(context.user_input, cfg.sys.Global.router_agent)
        choice = str(category_res.get('result', '0'))
        if choice != '0' and choice.isdigit():
            context.category = cfg.LOADED_PLUGINS[int(choice)-1].upper()

            service_instance = self.service_registry.get(choice)
            if service_instance and hasattr(service_instance, 'execute'):
                return_code = service_instance.execute(context)
                context.return_code = Utils.format_result(return_code)

        context.duration_llm = time.time() - start_total
        context.duration = time.time() - context.start
        return context._archive_and_rename()

    def inference_loop(self):
        print("--- [Router] Inference Engine Ready ---")
        while self.is_running:
            try:
                context = self.command_queue.get(timeout=1.0)
                if context is None:
                    break

                response_context = self.select_and_execute(context)

                json_output = json.dumps(response_context.to_dict())
                socks = getattr(context.session, 'socks', [])
                for s in socks:
                    try:
                        s.sendall(json_output.encode() + b"\n")
                    except:
                        pass

                self.command_queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                print(f"SERVER_ERROR in Inference Loop: {e}")
                time.sleep(1)

    def format_result(self, result):
        if isinstance(result, dict):
            return ",".join([f"{k}:{v}" for k, v in result.items()])
        return str(result)

    def start(self):
        self.thread = threading.Thread(target=self.inference_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.is_running = False
        self.thread.join()


engine = RouterLLM()

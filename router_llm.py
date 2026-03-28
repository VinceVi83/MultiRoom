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
    """RouterLLM
    
    Role: Manages LLM routing, plugin registration, and command queue processing.
    
    Methods:
        __init__(self) : Initializes the RouterLLM instance with command queue, threading, and service instances.
        add_to_queue(self, context) : Adds a TaskContext to the command queue for processing.
        _initialize_service_registry(self) : Builds the service registry from loaded plugins.
        execute_native(self, context) : Executes native format commands on registered services.
        select_and_execute(self, context) : Detects intent via LLM and calls the appropriate service immediately.
        inference_loop(self) : Background worker processing the command queue.
        start(self) : Starts the inference loop in a separate daemon thread.
        stop(self) : Stops the inference loop and waits for thread completion.
    """

    def __init__(self):
        self.command_queue = queue.Queue()
        self.service_registry = {}
        self.is_running = True
        self.debug = False
        self.test = False
        self._initialize_service_registry()
        self.start()

    def add_to_queue(self, context):
        if isinstance(context, TaskContext):
            self.command_queue.put(context)

    def _initialize_service_registry(self):
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
                    self.service_registry[plugin_name] = instance
                else:
                    print(f"  [!] Class {class_name} not found in {module_path}")

            except Exception as e:
                print(f"  [!] Failed to load {plugin_name}: {e}")

    def execute_native(self, context):
        parts = context.user_input.lstrip('@').split(';-;', 3)
        
        if len(parts) < 4:
            print(f"[!] Native Format Error: {context.user_input}")
            return "FORMAT_ERROR"

        plugin_name = parts[0]
        context.location = parts[1] if parts[1] else "Unknown"
        context.label    = parts[2].upper()
        context.result   = parts[3]

        service_instance = self.service_registry.get(plugin_name)
        
        if service_instance and hasattr(service_instance, 'execute_native'):
            try:
                context.return_code = service_instance.execute_native(context)
            except Exception as e:
                print(f"[!] Service {plugin_name} execute_native failed: {e}")
                context.return_code = cfg.RETURN_CODE.ERR
        else:
            context.return_code = cfg.RETURN_CODE.ERR

        return context._archive_and_rename()

    def select_and_execute(self, context):
        start_total = time.time()

        try:
            category_res = llm.execute(context.user_input, cfg.sys.Global.router_agent)
            choice = str(category_res.get('ID', '0'))
            if choice != '0' and choice.isdigit():
                context.category = cfg.LOADED_PLUGINS[int(choice)-1].upper()

                service_instance = self.service_registry.get(choice)
                if service_instance and hasattr(service_instance, 'execute'):
                    try:
                        return_code = service_instance.execute(context)
                        context.return_code = Utils.format_result(return_code)
                    except Exception as e:
                        print(f"[!] Service {choice} execute failed: {e}")
                        context.return_code = cfg.RETURN_CODE.ERR
            else:
                print("NONSENSE")
        except Exception as e:
            print(f"[!] LLM execution failed: {e}")
            context.return_code = cfg.RETURN_CODE.ERR

        context.duration_llm = time.time() - start_total
        context.duration = time.time() - context.start
        return context._archive_and_rename()

    def inference_loop(self):
        llm.execute("Be ready", cfg.sys.Global.router_agent)
        last_activity = time.time()
        keep_alive_threshold = 240

        while self.is_running:
            try:
                context = self.command_queue.get(timeout=1.0)
                if context is None:
                    break
                last_activity = time.time()
                response_context = {}
                
                if context.user_input.startswith('@'):
                    response_context = self.execute_native(context)
                elif self.test:
                    result = llm.execute(context.user_input, cfg.sys.Global.pre_process_agent)
                    if result.get('valid', 0):
                        response_context = self.select_and_execute(context)
                    else:
                        print("--- [Router] Input rejected: Does not meet criteria ---")
                        continue
                else:
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
                if time.time() - last_activity >= keep_alive_threshold:
                    try:
                        self.llm.execute("Be ready", cfg.sys.Global.router_agent)
                    except:
                        pass
                    last_activity = time.time()
                continue
            except Exception as e:
                print(f"SERVER_ERROR in Inference Loop: {e}")
                time.sleep(1)

    def start(self):
        self.thread = threading.Thread(target=self.inference_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.is_running = False
        self.command_queue.put(None) 
        if hasattr(self, 'thread') and self.thread.is_alive():
            self.thread.join(timeout=5.0)

import queue
import threading
import json
import time
import importlib
from config_loader import cfg, PluginConfig
from tools.llm_agent import llm
from tools.task_context import TaskContext
from tools.utils import Utils
import copy

class RouterLLM:
    """RouterLLM
    
    Role: Manages LLM routing, plugin registration, and command queue processing.
    
    Methods:
        __init__(self) : Initialize router with service registry and start inference loop.
        add_to_queue(self, context) : Add a TaskContext to the command queue.
        _initialize_service_registry(self) : Initialize service registry from loaded plugins.
        execute_native(self, context) : Execute native format commands.
        get_location(self, context) : Get/clean location using LLM agent.
        bypass_location(self, context) : Check if user input bypasses location.
        bypass_router(self, context) : Check if user input bypasses router.
        select_plugin(self, context) : Select plugin based on user input.
        select_and_execute(self, context, callback_internal_request_api) : Select plugin and execute it.
        callback_internal_request_api(self, context) : Handle internal API requests.
        inference_loop(self) : Main inference loop for processing commands.
        start(self) : Start the inference thread.
        stop(self) : Stop the inference thread.
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
                    cfg_final = PluginConfig()
                    plugin_obj = getattr(cfg, plugin_name, None)
                    if plugin_obj:
                        vars(cfg_final).update(copy.deepcopy(vars(plugin_obj)))
                    plugin_obj_2 = getattr(cfg, plugin_name.upper(), None)
                    if plugin_obj_2:
                        vars(cfg_final).update(copy.deepcopy(vars(plugin_obj_2)))
                    cfg_final.RETURN_CODE = copy.deepcopy(cfg.RETURN_CODE)
                    service_class = getattr(module, class_name)
                    instance = service_class(cfg_final)
                    self.service_registry[plugin_name.upper()] = instance
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
        context.sub_category = parts[2].upper()
        context.result   = parts[3]
        service_instance = self.service_registry.get(plugin_name.upper())
        if service_instance and hasattr(service_instance, 'execute_native'):
            try:
                context.return_code = service_instance.execute_native(context)
            except Exception as e:
                print(f"[!] Service {plugin_name} execute_native failed: {e}")
                context.return_code = cfg.RETURN_CODE.ERR
        else:
            context.return_code = cfg.RETURN_CODE.ERR

        return context._archive_and_rename()

    def get_location(self, context):
        if Utils.enable_bypass() and self.bypass_location(context):
            return

        local_res = llm.execute(context.user_input, cfg.ALL_PURPOSE.LOCATION_CLEANER_AGENT, verbose=False, debug=False)
        if local_res.get('cleaned_command') != 'none':
            context.location = local_res.get('location')
        context.add_step('LOCATION_CLEANER_AGENT', local_res)
        return

    def bypass_location(self, context):
        user_input_lower = context.user_input.lower()
        for keyword in cfg.sys.config.BYPASS_ALL:
            if keyword.lower() in user_input_lower:
                context.location = "ALL"
                context.add_step('bypass_location', {'Location': "ALL", 'bypass': 1})
                return True

        for keyword in cfg.sys.config.REPLACE_LOCATIONS:
            if keyword.lower() in user_input_lower:
                context.location = keyword
                context.add_step('bypass_location', {'Location': keyword, 'bypass': 1})
                return True
        return False

    def bypass_router(self, context):
        user_input_lower = context.user_input.lower()
        
        for category, keywords in cfg.ROUTER.items():
            for keyword in keywords:
                keyword_lower = keyword.lower()
                if keyword_lower in user_input_lower:
                    return {'PLUGIN': category, 'bypass': 1}
        return None

    def select_plugin(self, context):
        category_res = None
        if Utils.enable_bypass():
            category_res = self.bypass_router(context)
        if not category_res:
            category_res = llm.execute(context.user_input, cfg.ALL_PURPOSE.ROUTER_AGENT)

        context.add_step('ROUTER_AGENT', category_res)
        context.category = category_res.get('PLUGIN', 'UNKNOWN')
        return context.category.lower() in cfg.LOADED_PLUGINS

    def select_and_execute(self, context):
        start_total = time.time()
        try:
            if not self.select_plugin(context):
                context.return_code = cfg.RETURN_CODE.ERR
                return context._archive_and_rename()
            plugin_obj = getattr(cfg, context.category.lower(), None)
            if plugin_obj.config.USE_LOCATION:
                self.get_location(context)
        except Exception as e:
            print(f"[!] LLM execution failed: {e}")
            context.return_code = cfg.RETURN_CODE.ERR
            return context._archive_and_rename()

        try:
            service_instance = self.service_registry.get(context.category)
            if service_instance and hasattr(service_instance, 'execute'):
                return_code = service_instance.execute(context, self.callback_internal_request_api)
                context.return_code = Utils.format_result(return_code)
  
        except Exception as e:
            print(f"[!] Service {context.category} execute failed: {e}")
            return context._archive_and_rename()

        context.duration_llm = time.time() - start_total
        context.duration = time.time() - context.start
        return context._archive_and_rename()

    def callback_internal_request_api(self, context):
        if not context.data_request:
            return cfg.RETURN_CODE.ERR
        data = context.data_request.get("internal_api")
        if not data:
            return cfg.RETURN_CODE.ERR

        plugin_name = data["plugin"]
        service_instance = self.service_registry.get(plugin_name, "None")
        if service_instance and hasattr(service_instance, 'execute_api'):
            try:
                context.return_code = service_instance.execute_api(data)
            except Exception as e:
                print(f"[!] Service {plugin_name} callback_internal_request_api failed: {e}")
                context.return_code = cfg.RETURN_CODE.ERR
                return cfg.RETURN_CODE.ERR
        else:
            return cfg.RETURN_CODE.ERR
        return cfg.RETURN_CODE.SUCCESS

    def inference_loop(self):
        llm.execute("Be ready", cfg.ALL_PURPOSE.ROUTER_AGENT)
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
                    result = llm.execute(context.user_input, cfg.ALL_PURPOSE.pre_process_agent)
                    if result.get('valid', 0):
                        response_context = self.select_and_execute(context)
                    else:
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
                        self.llm.execute("Be ready", cfg.ALL_PURPOSE.ROUTER_AGENT)
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

"""
Main AI Router module.
Orchestrates intent detection, interactive web research, and service dispatching.
"""
import os
import json
import threading
import queue
import time
from config_loader import cfg
from tools.llm_agent import llm
from tools.my_calendar import CalendarService
from tools.scraper import ScraperService
from services.services import ServiceDispatcher
from services.shopping import ShoppingService
from tools.mailer_proton import send_mail

class RouterLLM:
    """
    Handles command routing and persistent state for interactive AI services.
    """
    def __init__(self):
        self.command_queue = queue.Queue()
        self.is_running = True
        self.search_cache = {"results": [], "query": ""}
        threading.Thread(target=self.inference_loop, daemon=True).start()
        self.calendar = CalendarService()
        self.web_scraper = ScraperService()
        self.shopping = ShoppingService()
        self.debug = False

    def dispatch_request(self, context):
        start_total = time.time()
        context.user_input = context.user_input.replace("vais", "veux")
        category_res = llm.execute(context.user_input, cfg.RouterLLM.router_thematic)
        context.category = cfg.DICO_THEME_MAPPING.get(category_res.get('result'))
        config = cfg.routing_table.get(context.category)

        if config:
            sub_res = llm.execute(context.user_input, config["agent"])
            res_id = str(sub_res.get('ID'))
            context.label = config["mapping"].get(res_id)
            if context.label:
                context.result = ServiceDispatcher.execute(context)
            else:
                context.result = f"ID [{res_id}] not found in the dictionary {context.category}"

        context.duration = time.time() - start_total
        return context._archive_and_rename()

    def inference_loop(self):
        """
        Background worker processing the command queue.
        """
        while self.is_running:
            item = self.command_queue.get()
            if item is None: break
            context = item
            try:
                response_context = self.dispatch_request(context)
                json_output = json.dumps(response_context.to_dict())
                for s in context.session.socks:
                    try:
                        s.sendall(json_output.encode())
                    except: pass
            except Exception as e:
                print(f"SERVER_ERROR: {e}")
            finally:
                self.command_queue.task_done()

    def format_result(self, result):
        """Transforms a dictionary into a string 'KEY:Value' or returns the raw string"""
        if isinstance(result, dict):
            return ",".join([f"{k}:{v}" for k, v in result.items()])
        return str(result)

if __name__ == "__main__":
    router = RouterLLM()

import socket
import json
from config_loader import cfg
from tools.llm_agent import llm
from pathlib import Path
import argparse
import time
from tools.task_context import TaskContext

def record_text(file, text):
    try:
        with open(file, 'a', encoding='utf-8') as fichier:
            fichier.write(text + '\n')
    except IOError as e:
        print(f"Error : {e}")

def load_json_tests():
    file_path = Path(cfg.DATA_DIR) / 'output.json'
    if not file_path.exists():
        return []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error reading JSON: {e}")
        return []

def run_batch_test_mode():
    while True:
        test_groups = load_json_tests()
        
        if not test_groups:
            break

        _display_test_menu(test_groups)
        choice = input('\nSelect a number (or [Q] to quit) : ').strip().lower()

        if choice == 'q':
            break

        try:
            idx = int(choice) - 1
            if not (0 <= idx < len(test_groups)):
                print(f"[!] Error: Choose a number between 1 and {len(test_groups)}.")
                continue
        except ValueError:
            print("[!] Error: Invalid input. Please enter a number.")
            continue

        _execute_test_group(test_groups[idx])

def _display_test_menu(test_groups: list):
    print(f"\n{'='*10} TEST LIST {'='*10}")
    for i, group in enumerate(test_groups, 1):
        name = group.get('expected', 'Unnamed')
        print(f"[{i}] {name}")
    print(f"{'='*32}")
    print('[Q] Quit')

def _execute_test_group(group: dict):
    expected_label = group.get('expected', 'Unknown')
    commands = group.get('ordre', [])
    
    print(f"\n>>> STARTING TEST: {expected_label}")
    
    contexts = []
    for cmd in commands:
        clean_cmd = cmd.replace('test:', '')
        context = TaskContext(clean_cmd)
        
        start_time = time.perf_counter()
        test_full_chain(context)
        context.time = time.perf_counter() - start_time
        
        contexts.append(context)

    _display_results(expected_label, contexts)

def _is_test_success(ctx, label):
    loc_ok = (ctx.location in label) if 'ALL' in label else True
    return (
        ctx.category in label and
        ctx.sub_category in label and
        ctx.return_code == cfg.RETURN_CODE.SUCCESS and
        ctx.result in label and
        loc_ok
    )

def _display_results(label: str, contexts: list):
    successes = 0
    ko_contexts = []

    for ctx in contexts:
        status = "OK" if _is_test_success(ctx, label) else "KO"
        print(f"[{status}] {ctx.user_input[:30]:<30} | Duration: {ctx.time:.4f}s")

        if _is_test_success(ctx, label):
            successes += 1
        else:
            ko_contexts.append(ctx)

    total = len(contexts)
    rate = (successes / total * 100) if total > 0 else 0

    print(f"\n{'='*20} RESULT: {label} {'='*20}")
    
    if successes == total:
        print(f"ALL OK ({successes}/{total})")
    else:
        print(f"SOME TESTS FAILED ({successes}/{total}) - {rate:.2f}%")
        print(f"\n--- FAILED DETAILS ---")
        for ctx in ko_contexts:
            print(ctx)

def run_debug_server(host='0.0.0.0', port=28888):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen(5)

    file_path = Path(cfg.DATA_DIR) / 'record.txt'
    try:
        while True:
            client_sock, addr = server.accept()
            data = client_sock.recv(4096).decode('utf-8').strip()
            
            record_text(file_path, data)
            if data:
                parts = data.split(':', 2)
                
                if len(parts) < 3:
                    client_sock.sendall(b'ERR_FORMAT\n')
                    client_sock.close()
                    continue

                sig, tag, content = parts

                if tag == 'Auth':
                    client_sock.sendall(b'AUTH_OK\n')
                
                elif tag == 'test':
                    context = TaskContext()
                    context.user_input = content
                    test_full_chain(context)
                    
                    client_sock.sendall(f'PROCESSED\n'.encode())
                    
    except AttributeError:
        print(f"[!] Error: Agent not found in YAML.")
        client_sock.sendall(b'ERR_CONFIG\n')
        client_sock.close()

    except KeyboardInterrupt:
        pass
    finally:
        server.close()

def get_location(context):
    local_res = llm.execute(context.user_input, cfg.ALL_PURPOSE.LOCATION_CLEANER_AGENT, verbose=False, debug=False)
    context.add_durations(local_res)
    if local_res.get('cleaned_command') != 'none':
        context.location = local_res.get('location')
        context.user_input = local_res.get('cleaned_command')
    context.add_step('LOCATION_CLEANER_AGENT', local_res)
    return True

def test_full_chain(context):
    print(f"\n=== Testing Input: {context.user_input} ===")
    
    route_res = llm.execute(context.user_input, cfg.ALL_PURPOSE.ROUTER_AGENT, verbose=False, debug=False)
    context.add_durations(route_res)
    plugin_name = route_res.get('PLUGIN', 'NONE')
    
    if plugin_name == 'NONE':
        print('Result: NONSENSE / No route found')
        return

    context.category = plugin_name
    context.add_step('ROUTER_AGENT', route_res)

    handlers = {
        'SCHEDULER': _handle_scheduler,
        'MUSIC_VLC': _handle_music,
        'AGENDA': _handle_agenda,
        'DAILY': _handle_daily,
        'HOME_AUTOMATION': _handle_home_auto
    }

    handler = handlers.get(plugin_name)
    if handler:
        handler(context)
    else:
        print(f"Plugin {plugin_name} not managed.")

def _handle_scheduler(context):
    time_data = llm.execute(context.user_input, cfg.SCHEDULER.TIME_EXTRACTOR_AGENT, False, False)
    context.add_durations(time_data)
    intent_data = llm.execute(context.user_input, cfg.SCHEDULER.INTENT_AGENT, False, False)
    context.add_durations(intent_data)
    
    raw_cmd = intent_data.get('action', context.user_input)
    mode_data = llm.execute(raw_cmd, cfg.SCHEDULER.SYSTEM_AGENT, False, False)
    context.add_durations(mode_data)

def _handle_music(context):
    get_location(context)
    bypass_map = {
        'PLAYLIST_AGENT': ['playlist'],
        'MUSIC': ['vlc', 'augmente', 'monte', 'baisse', 'diminue', 'moins', 'plus', 'précédent', 'suivant', 'après', 'remets']
    }
    
    matched = next((k for k, v in bypass_map.items() if any(w in context.user_input.lower() for w in v)), None)
    
    if matched:
        context.sub_category = matched
        context.add_step('sub_category', {'label': matched, 'bypass': 1})
    else:
        res = llm.execute(context.user_input, cfg.MUSIC_VLC.MUSIC_AGENT, False, False)
        context.add_durations(res)
        context.sub_category = res.get('CATEGORY', 'NONE')
        context.add_step('sub_category', res)

    if context.sub_category == 'PLAYLIST_AGENT':
        pl_res = llm.execute(context.user_input, cfg.MUSIC_VLC.PLAYLIST_AGENT, False, False)
        context.add_durations(pl_res)
        action = pl_res.get('ACTION', 'ERR')
        if action in ['UNKNOWN', 'PLAY', 'CREATE', 'ADD', 'DEL', 'INFO']:
            context.result, context.return_code = action, cfg.RETURN_CODE.SUCCESS
        context.add_step('Result', pl_res)
        
    elif context.sub_category == 'MUSIC':
        vlc_res = llm.execute(context.user_input, cfg.MUSIC_VLC.VLC_AGENT, False, False)
        context.add_durations(vlc_res)
        action = vlc_res.get('ACTION', '0')
        if action in ['UNKNOWN', 'TOGGLE', 'PREVIOUS', 'NEXT', 'VOL_DOWN', 'VOL_UP', 'SHUFFLE', 'INFO']:
            context.result, context.return_code = action, cfg.RETURN_CODE.SUCCESS
        context.add_step('Result', vlc_res)
    
    elif context.sub_category in ['DISCOVER', 'DISCOVERY']:
        context.return_code = cfg.RETURN_CODE.SUCCESS

def _handle_agenda(context):
    res = llm.execute(context.user_input, cfg.AGENDA.CALENDAR_AGENT, False, False)
    context.add_durations(res)
    action = res.get('ACTION', 'NONE')
    context.sub_category = action
    context.add_step('sub_category', res)
    
    if action in ['NEXT_RDV', 'NEXT_CONCERT', 'CURRENT_WEEK', 'NEXT_WEEK', 'MAIL_NEXT_CONCERT']:
        context.result, context.return_code = 'Done', cfg.RETURN_CODE.SUCCESS

def _handle_daily(context):
    is_fridge = any(w in context.user_input.lower() for w in ['frigo', 'fridge'])
    agent = cfg.DAILY.FRIDGE_AGENT if is_fridge else cfg.DAILY.DAILY_AGENT
    
    res = llm.execute(context.user_input, agent, False, False)
    context.add_durations(res)
    action = res.get('ACTION', 'NONE')
    context.sub_category = action
    context.add_step('sub_category', res)

    if action in ['SHOP_ADD', 'FRIDGE_ADD']:
        items = llm.execute(context.user_input, cfg.DAILY.EXTRACT_FOOD_AGENT, False, False)
        context.add_durations(items)
        context.add_step('result', items)
        
    if action in ['SHOP_ADD', 'SHOP_DEL', 'SHOP_INFO', 'SHOP_MAIL', 'FRIDGE_ADD', 'FRIDGE_REM', 'FRIDGE_INFO', 'FRIDGE_MAIL']:
        context.result, context.return_code = 'Done', cfg.RETURN_CODE.SUCCESS

def _handle_home_auto(context):
    get_location(context)
    res = llm.execute(context.user_input, cfg.HOME_AUTOMATION.DOMOTIC_AGENT, False, False)
    context.add_durations(res)
    action, dtype = res.get('ACTION', 'NONE'), res.get('TYPE', 'NONE')
    context.sub_category = f"{dtype}:{action}"
    context.add_step('sub_category', res)

    if dtype in ['LIGHT', 'SWITCH', 'WEATHER'] and action in ['ON', 'OFF', 'TOGGLE', 'INFO']:
        context.result, context.return_code = 'Done', cfg.RETURN_CODE.SUCCESS
    else:
        context.result = 'Failed'
    
def _display_global_report(all_results):
    total_queries = 0
    total_success = 0
    failed_reports = []
    total_time = 0

    for group in all_results:
        label = group['label']
        for ctx in group['contexts']:
            total_queries += 1
            total_time += ctx.time
            
            loc_ok = (ctx.location in label) if 'ALL' in label else True
            is_success = (
                ctx.category in label and
                ctx.sub_category in label and
                ctx.return_code == cfg.RETURN_CODE.SUCCESS and
                ctx.result in label and
                loc_ok
            )

            status = " [OK] " if is_success else " [KO] "
            print(f"{status} {ctx.user_input[:40]:<40} | {ctx.time:.4f}s")

            if is_success:
                total_success += 1
            else:
                failed_reports.append((label, ctx))

    print(f"\n\n{'#'*60}")
    print(f"{' '*15} GLOBAL AUTOMATION REPORT")
    print(f"{'#'*60}")
    
    if failed_reports:
        print(f"\nFAILED REPORTS ({len(failed_reports)}):")
        for label, ctx in failed_reports:
            print(f"\n[EXPECTATION]: {label}")
            print(f"[ACTUAL CONTEXT]:")
            print(ctx)
    else:
        print("\nALL TESTS ARE GREEN!")

    rate = (total_success / total_queries * 100) if total_queries > 0 else 0
    print(f"\n{'='*60}")
    print(f"FINAL SCORE   : {total_success}/{total_queries}")
    print(f"SUCCESS RATE  : {rate:.2f}%")
    print(f"TOTAL TIME    : {total_time:.2f}s")
    print(f"AVERAGE/TEST  : {(total_time/total_queries):.4f}s" if total_queries > 0 else "")
    print(f"{'='*60}\n")

def run_automatic_all_tests():
    test_groups = load_json_tests()
    if not test_groups:
        return

    all_results = []
    print(f"\nLAUNCHING {len(test_groups)} AUTOMATIC TEST GROUPS\n")

    for group in test_groups:
        label = group.get('expected', 'Unknown')
        commands = group.get('ordre', [])
        group_contexts = []

        for cmd in commands:
            ctx = TaskContext(cmd.replace('test:', ''))
            start = time.perf_counter()
            test_full_chain(ctx)
            ctx.time = time.perf_counter() - start
            group_contexts.append(ctx)
        
        all_results.append({'label': label, 'contexts': group_contexts})

    _display_global_report(all_results)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Debug Server & Batch Tester')
    parser.add_argument('-t', '--test', action='store_true', help='Interactive mode')
    parser.add_argument('-a', '--auto', action='store_true', help='Global automatic mode')
    args = parser.parse_args()

    if args.auto:
        run_automatic_all_tests()
    elif args.test:
        run_batch_test_mode()
    else:
        run_debug_server()

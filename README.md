# Multiroom project or A.L.I.S.U.

*“Multiroom builds the way, A.L.I.S.U. makes the play.”*

**A.L.I.S.U. (Assistant LLM Interface System Unit)** is a functional interface designed to pilot home automation and various digital services within a **Multiroom** infrastructure.

The goal is to simplify service execution (music, home automation, agenda, shopping list) through a central orchestrator, replacing repetitive manual/physical tasks with an intelligent service layer.

## Demo & Performance
To showcase the real-time capabilities of **A.L.I.S.U.**, a video demonstration is available. It highlights the full pipeline: Voice Capture ➔ Whisper Transcription ➔ LLM Intent Extraction ➔ Service Execution.

### [Watch the Demo: Voice-Controlled Media Orchestration](https://www.youtube.com/watch?v=JYTv3L7crkk)
*(Note: This video is unlisted and intended for technical review.)*

**What you will see in the demo:**
* **Full Pipeline Integration:** End-to-end processing from natural language to hardware/service action.
* **Smart Extraction:** How A.L.I.S.U. interprets natural language to pilot the **VLC Lua HTTP interface**.
* **Reliability Focus:** The demo features the core logic, current development prioritizes **enhanced prompt robustness** for higher recognition accuracy and extract information.

# Roadmap
- [x] **Automated Routing**: Intent detection via local LLM + keyword bypass (Core logic operational, continuous refinement).
- [x] **Env Initialization**: Automatically create a default `config*.yaml` in `~/Documents/ALISU_DATA/` if it's missing or empty.
- [x] **Config Simplification**: Strict validation and isolation of unconfigured services.
- [x] **Resilience & Fail-safe**: Dynamic deactivation of offline services during startup (Fail-Safe).
- [-] **Benchmarking & Regression**: Refactoring existing internal test suite.
    * *Current state:* System already records `.wav` and `.json` logs. A "Replay" system exists to compare **Expected vs Obtained** results.
	* *Benchemark:* Done, with batch_test.py
- [-] **Auto Test**: Automated testing suite for core services and orchestrator logic.
- [x] **Rolling Buffer**: Audio stream optimization (RAM-based).
- [-] **Playlists & Alarms**: Music queue management and scheduled musical alarms.
    * *Current state:* Schedule alarm possible but too complex get an expected result, because it need better prompting and phrasing...
- [-] **Local TTS Integration**: Implementing **VoiceSpeak** (or similar CLI-based TTS) for voice feedback.
- [-] **Edge Hardware**: Integration of Raspberry Pi nodes as satellite microphones/speakers.
- [-] **Synchronize-Latency Multiroom**: Integrate real-time audio synchronization for multiple VLC clients on the same stream without offset or drift (**Already tested a working solution**).
- [-] **Physical PTT Nodes**: Use of Bluetooth/WiFi devices (e.g., shutter buttons) as remote Push-To-Talk triggers for command input.
- [x] **Future Optimization**: Experimenting with lighter models (Phi-3, Gemma) for lower hardware requirements.
    * *Current state:* Change llama3.1:8b to qwen2.5:3b, optimized all prompts for performance and implemented keyword-based regex routing to bypass unnecessary LLM calls. Disabled JSON mode to further reduce request latency.
## Vision & Origines
This project was born during my student years, long before the rise of modern LLMs. It originated from a dream: building a personal Jarvis to manage a massive local music library (Touhou music) stored on a NAS, and to control smart objects via voice commands.

Back then (around 2017), consumer home automation was still in its infancy. It mostly consisted of simplistic gadgets, locked within proprietary applications and heavily dependent on the Cloud. My goal was to prove that with limited means, a smart architecture, and well-integrated voice recognition, one could surpass closed commercial solutions which, for the most part, remain just as restrictive today.

### What sets A.L.I.S.U. apart:

* **Performance vs. Cost:** Leveraging accessible hardware to create a fluid multiroom system that evolves with the times.
* **Decentralized Intelligence:** Using a local GPU (Whisper, Llama 3.1) to process intent locally, ensuring total privacy.
* **Scalability:** A student challenge evolved into a sophisticated orchestrator unifying VLC, Home Assistant, and custom APIs.

## Features
* **Orchestration:** Centralized control of multiroom services.
* **Intelligent Layer:** LLM-powered interface for natural interaction.
* **Automation:** Streamlined execution of daily digital tasks.

## System Components

The project centralizes multiple tools through a **Hub-and-Spoke** architecture:

1. **The Hub (Central Server)**: Managed by `hub_server.py`, it receives secure commands (SSL) and routes them to specialized agents via a central dispatcher.
2. **A.L.I.S.U. (Interface Layer)**: Utilizes a local LLM to interpret natural language requests and route execution to dedicated Python scripts. It incorporates keyword-based filtering to bypass the LLM when possible, improving response speed and command accuracy.
3. **Integrated Services**:
    * **Home Automation**: Control of Home Assistant entities (Lights, plug, etc.).
    * **Music**: Full control of VLC via the **Lua HTTP interface***.
	* **Library**: Management of local music libraries.
    * **Utilities**: Web search (via SearXNG), calendar management, weather, and automated email reporting.
	* **Shopping**: Management of shopping lists and inventory.

## Project Structure

```text
.
├── hub_server.py   # Main service hub
├── config_loader.py       # Configuration loading & validation
├── agents_config.yaml     # Global routing
├── plugins/               # Modular Extensions (VLC, HA, Agenda, Mail etc.)
├── tools/                 # Engines: Whisper, Scraper
└── interfaces/            # Control nodes (PC, Voice, Simulators)
```

### 3. Execution
```bash
python hub_server.py
```

## Operational Flow: Order, Execution & Feedback
Everything is centralized. The `Core Orchestrator` integrates the transcription engine and communicates directly with the `RouterLLM` internally.


```text
 [ DEVICES/Users ]     [ HUB SERVER ]               [ ROUTER LLM ]              [ PLUGIN ]
 (Text/PTT/Stream)    (Hardware Gateway)          (Order Dispatcher)       (Intelligence & Logic)
      |                       |                            |                         |
      |-- (1) Triple Input -->|                            |                         |
      |   a. Direct Text      |                            |                         |
      |   b. PTT (Audio File) |                            |                         |
      |   c. Audio Stream     |                            |                         |
      |                       |                            |                         |
      | [IF PTT: NO WAIT] ----> (Close connection/Ack)     |                         |
      |                       |                            |                         |
      |                       |---(2) Whisper (Text) ----->|                         |
      |                       |                            |                         |
      |                 [ IDLE / LISTENING ]       [ Command Queue ]                 |
      |                       |                            |                         |
      |                       |                    (3) Router Agent                  |
      |                       |                    (Selects Plugin ID)               |
      |                       |                            |                         |
      |                       |                    (4) SEND ORDER                    |
      |                       |                            |---- execute(context) -->|
      |                       |                            |                         |
      |                       |                            |                 [ INSIDE PLUGIN ]
      |                       |                            |                  (5) Sub-Agents 
      |                       |                            |                 (6) Plugin Logic
      |                       |                            |                (7) UPDATE CONTEXT
      |                       |                            |                         |
      |                       |                            |                         |
      |                       |                            |<--(8) RETURN CODE ------|
      |                       |                            |                         |
      |                       |                    (9) FORMAT CONTEXT                |
      |                       |                        (To JSON)                     |
      |                       |                            |                         |
      |<---(11) Result -------| <---(10) Enriched JSON ----|                         |
      |    (If persistent)    |                            |                         |
```

# Tutorial: Plugin Integration 
To ensure project compatibility and maintainability, every new plugin must strictly follow the directory structure and naming conventions defined below.

Directory Architecture
Create a new folder within the **`plugins/`** directory. Use lowercase and underscores (**`snake_case`**) exclusively for the folder name.
```text
plugins/
└── my_new_plugin/
    ├── config.yaml           # Plugin configuration
    ├── user.yaml             # User configuration for plugin
    ├── agents_config.yaml    # LLM system prompts and model settings
    ├── logic_module.py       # Core backend logic and processing
    └── service.py            # Gateway class/API bridge
```
# Development Note
This project was developed using a "Human-in-the-loop" LLM-assisted workflow.

While **A.L.I.S.U.** is designed to be 100% local and sovereign in production, various LLMs were used as development tools to accelerate coding, refactoring, and documentation. I treat these LLM tools as advanced assistants, but always strictly guided to ensure the final architecture remains local-first and fully under control.

# Installation & Configuration
## Prerequisites
To ensure stability and optimal performance, please verify your environment meets the following requirements:

### Operating System
* **Native Linux** (Highly Recommended)
    > [!CAUTION]
    > **A note on WSL2:** While Windows Subsystem for Linux (WSL2) is technically compatible. I am currently using this setup, but be aware it is **not recommended** for beginners. Beyond GPU passthrough issues, it significantly complicates networking. You will need to manually configure the **Windows Firewall** and port forwarding to allow external access to your services.

### Disclaimer
> [!IMPORTANT]
> **API Costs**: If you choose to use external APIs (OpenAI, Anthropic, etc.) instead of local models, **you are solely responsible for your own costs**. I am not responsible for any unexpected credit exhaustion or bills.

### Hardware (GPU)
> **Note**: High-end hardware is **only required if you intend to run LLMs locally**. If you are using external APIs (OpenAI, Anthropic, etc.), these requirements do not apply.
* **NVIDIA (Confirmed)**: 
    * **Minimum**: RTX 3060 (12GB VRAM). 
    * **Recommended**: RTX 3080 or higher.
* **Apple Silicon (Untested)**: 
    * **Potential**: Mac Mini (M1/M2/M3/M4). Should technically work for local LLMs at least to provide local LLM.
	
### Driver Requirements
* **NVIDIA Drivers:** Ensure you have the latest stable drivers installed.
* **CUDA Toolkit:** Must be correctly mapped to your environment (check with `nvcc --version`).

### Installation
```bash
git clone [https://github.com/VinceVi83/MultiRoom.git](https://github.com/VinceVi83/MultiRoom.git)
   cd MultiRoom
```

### 1. System Prerequisites
* **Ollama**: For running local Large Language Models. 
    * *Default model*: **`qwen2.5:3b`** (can be modified in configuration).
* **SearXNG**: For web search services.
* **Home Assistant**: For domotic integration.
* **VLC**: With the HTTP Lua interface enabled.

### 2. Software Setup
1. **Dependencies**: Install the required Python libraries via the requirements file:
   ```bash
   pip install -r requirements.txt
   ```
2. **Environment**: Everything is managed in `~/Documents/ALISU_DATA/`:
   * Use **`.env_example`** as a template, fill in your credentials (IPs, Ports, API keys), and rename it to **`.env`**.
3. **SSL Certificates**:
   * Create a `Certification/` folder inside `ALISU_DATA/`.
   * Place your **`cert.pem`** and **`key.pem`** files there to enable secure communication.
   * *Tip*: To generate test certificates: 
     `openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -sha256 -days 365 -nodes`

## ConfigFile: **`.env_template`**

This file serves as a blueprint for local configuration. It contains the environment variables required for the plugin to function without exposing sensitive data.

* **Deployment**: Automatically copied to DATA_DIR/ALISU_DATA/plugins/ at startup.
* **Action**: Edit the copied file in the data directory, not the template.
* **Custom Config**: You can define your own settings here, they become accessible in your code via cfg.plugin_name.
* **Mandatory**: The **`DESCRIPTION`** field is **required**, it is injected into the router prompt to trigger your plugin.
* **Note**: Contains API keys and secrets. Never commit the final .env file.

## LLM configuration: **`agents_config.yaml`**
* **Role**: Defines System Prompts, temperature, and model selection.
* **Utility**: Essential if you want to use a router architecture or orchestrate multiple specialized agents within the plugin.

## Functional Core: **`logic_module.py`**
* **Role**: Implementation of specific features, internal workflows, and integration with third-party tools or APIs.
* **Focus**: This is where you code your custom tools and specific logic rules.

## Plugin Controller: **`service.py`**
The system's bridge to your logic.

* **Router Link**: The Router LLM matches your .env description to trigger the execute method.
* **Execution**: Central entry point for all incoming requests routed to your plugin.
* **Integration**: Orchestrates the flow between agents_config and logic_module.

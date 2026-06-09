# GAOS™ Low-Level System Requirements — v3.3

**Document ID:** GAOS-LLSR-3.3  
**Product:** Ghost Assistant Operating System (GAOS™)  
**Vendor:** Aether Frameworks Ltd  
**Status:** Released  
**Date:** 2026-06-09  
**Revision:** 2.0  

---

## Table of Contents

1. [Purpose and Scope](#1-purpose-and-scope)
2. [Component Requirements](#2-component-requirements)
3. [Module-Level Requirements](#3-module-level-requirements)
4. [Interface Requirements](#4-interface-requirements)
5. [Data Requirements](#5-data-requirements)
6. [Configuration Requirements](#6-configuration-requirements)
7. [Error Handling Requirements](#7-error-handling-requirements)
8. [Security Requirements](#8-security-requirements)
9. [Deployment Requirements](#9-deployment-requirements)

---

## 1. Purpose and Scope

### 1.1 Purpose

This document defines the Low-Level System Requirements (LLSR) for the Ghost Assistant Operating System (GAOS™) version 3.3. It provides precise, implementer-facing specifications for every software component, all 34 functional modules, all external API interfaces, all data schemas, the complete configuration schema, error handling behaviour, security controls, and deployment requirements.

This document is the companion to the High-Level System Requirements document (GAOS-HLSR-3.3). Where the HLSR defines *what* the system must do, this document defines *how* each component must behave. A developer SHALL be able to implement, verify, or audit any aspect of the system using only this document and the referenced public API specifications.

### 1.2 Scope

This document covers:
- All five core Python source files: `gaos_core.py`, `gaos_ai.py`, `gaos_launcher.py`, `gaos_server.py`, `gaos_install.py`
- All 34 module files in the `modules/` directory
- All external API integrations
- All Google Sheets tab schemas
- The complete `config.json` schema
- Error handling and circuit breaker specifications
- Security controls at the implementation level
- Deployment configurations for Railway.app and Linux systemd

### 1.3 Requirement Identifier Convention

All requirements in this document follow the pattern `<TYPE>-<COMPONENT>-<SEQ>`:

- `COMP-CORE-NNN` — gaos_core.py requirements
- `COMP-AI-NNN` — gaos_ai.py requirements
- `COMP-LAUN-NNN` — gaos_launcher.py requirements
- `COMP-SRV-NNN` — gaos_server.py requirements
- `COMP-INST-NNN` — gaos_install.py requirements
- `MOD-NN-NNN` — module-level requirements (NN = two-digit module number)
- `IFACE-NNN` — interface requirements
- `DATA-NNN` — data schema requirements
- `CFG-NNN` — configuration requirements
- `ERR-NNN` — error handling requirements
- `SEC-NNN` — security requirements
- `DEPLOY-NNN` — deployment requirements

---

## 2. Component Requirements

### 2.1 gaos_core.py — Shared Runtime Library

`gaos_core.py` is the single shared runtime library imported by all modules and by `gaos_server.py`. It SHALL expose the complete set of utility functions described below and SHALL have no module-level side effects other than configuring the root `gaos` logger.

#### 2.1.1 Configuration Loading

**COMP-CORE-001** — The function `load_config(path="config.json")` SHALL open and JSON-parse the file at the given path. On any exception (FileNotFoundError, JSONDecodeError, PermissionError) it SHALL log an ERROR and return an empty dict `{}`. It SHALL NOT raise exceptions to callers.

**COMP-CORE-002** — The function `get_secret(key_path: str, default=None)` SHALL: (1) convert the dot-separated key_path to SCREAMING_SNAKE_CASE and attempt to read from `os.environ`; (2) if not found in environment, call `load_config()` and traverse the dict using each dot-separated segment as a key; (3) return `default` if any key is missing or traversal fails. Environment variable values SHALL take precedence over `config.json` values.

#### 2.1.2 Logging

**COMP-CORE-003** — The function `get_logger(name: str)` SHALL return a `logging.Logger` instance named `gaos.<name>`. If the logger has no handlers, it SHALL attach a `StreamHandler` with the format `%(asctime)s  %(name)s  %(levelname)s  %(message)s`. The logger SHALL have `propagate = False` to prevent duplicate log entries via the root logger.

#### 2.1.3 Gmail Connectivity

**COMP-CORE-004** — The function `connect_gmail()` SHALL: (1) attempt to load credentials from `token.json` using `google.oauth2.credentials.Credentials.from_authorized_user_file` with scopes `gmail.modify` and `gmail.compose`; (2) if no valid credentials exist, attempt to refresh using the stored refresh token; (3) if refresh fails or no token file exists, initiate the `InstalledAppFlow.run_local_server(port=0)` browser flow using `credentials.json`; (4) write the resulting credentials to `token.json`; (5) build and return a Gmail API service object using `googleapiclient.discovery.build("gmail", "v1")`. On any exception it SHALL log an ERROR and return `None`.

**COMP-CORE-005** — The function `gmail_search(gmail, query: str, max_results: int = 25)` SHALL call `gmail.users().messages().list(userId="me", q=query, maxResults=max_results)` and return the `messages` list from the response. On exception it SHALL log an ERROR and return `[]`.

**COMP-CORE-006** — The function `gmail_get_message(gmail, message_id: str)` SHALL retrieve the full message with `format="full"`, construct a `headers_dict` from the `payload.headers` list, extract body text via `gmail_get_body_text`, and return `(headers_dict, body_text)`. On exception it SHALL return `({}, "")`.

**COMP-CORE-007** — The function `gmail_get_body_text(msg: dict)` SHALL recursively traverse the message payload, return the decoded content of the first `text/plain` part found, decoding with `utf-8` and `errors="replace"`. If no plain-text part is found it SHALL return `""`.

**COMP-CORE-008** — The function `gmail_download_pdf(gmail, message_id: str)` SHALL retrieve the full message, iterate all message parts recursively, identify any part with `mimeType == "application/pdf"` or a filename ending `.pdf`, download the attachment bytes (via `messages.attachments().get` if an `attachmentId` is present, or from inline body data otherwise), and return `(pdf_bytes, filename)`. If no PDF is found it SHALL return `(None, None)`. On exception it SHALL log an ERROR and return `(None, None)`.

**COMP-CORE-009** — The function `gmail_create_draft(gmail, to: str, subject: str, body: str)` SHALL: retrieve the sender's email address via `gmail.users().getProfile(userId="me")`; construct a `MIMEText` message; base64url-encode it; call `gmail.users().drafts().create`. On exception it SHALL log an ERROR.

**COMP-CORE-010** — The function `gmail_send(gmail, to, from_addr, subject, body)` SHALL construct a `MIMEText` message, base64url-encode it, and call `gmail.users().messages().send(userId="me")`. On exception it SHALL log an ERROR.

**COMP-CORE-011** — The function `gmail_mark_read(gmail, message_id: str)` SHALL call `gmail.users().messages().modify` with `removeLabelIds: ["UNREAD"]`. On exception it SHALL log an ERROR.

**COMP-CORE-012** — The function `gmail_label(gmail, message_id: str, label_name: str)` SHALL: (1) list all labels via `gmail.users().labels().list`; (2) look up the label ID by case-insensitive name match; (3) if not found, create the label via `gmail.users().labels().create`; (4) apply the label via `gmail.users().messages().modify` with `addLabelIds`. On exception it SHALL log an ERROR.

#### 2.1.4 Google Sheets Access

**COMP-CORE-013** — The internal function `_get_sheets_client()` SHALL: (1) return the cached `_sheets_client` if already initialised; (2) if `service_account.json` exists, authenticate via `google.oauth2.service_account.Credentials.from_service_account_file` with scopes `spreadsheets` and `drive`, then call `gspread.authorize`; (3) if `service_account.json` does not exist but `token.json` exists, authenticate via `google.oauth2.credentials.Credentials.from_authorized_user_file`, refresh if expired, then call `gspread.authorize`; (4) if neither file exists, log an ERROR and return `None`. The result SHALL be cached in the module-level `_sheets_client` variable.

**COMP-CORE-014** — The function `sheets_read_all(sheet_id, tab_name)` SHALL call `gspread.Spreadsheet.worksheet(tab_name).get_all_records(default_blank="")` and return the result as a list of dicts. On exception it SHALL log an ERROR and return `[]`.

**COMP-CORE-015** — The function `sheets_append_row(sheet_id, tab_name, row_values: list)` SHALL call `worksheet.append_row(row_values, value_input_option="USER_ENTERED")`. On exception it SHALL log an ERROR.

**COMP-CORE-016** — The function `sheets_update_cell(sheet_id, tab_name, row_index: int, col, value: str)` SHALL: if `col` is a string, resolve it to a 1-based column index by reading `ws.row_values(1)` and finding the matching header; then call `ws.update_cell(row_index, col_idx, value)`. On exception it SHALL log an ERROR.

**COMP-CORE-017** — The function `sheets_find_or_create_tab(sheet_id, tab_name, headers=None)` SHALL: list all worksheets in the spreadsheet; if `tab_name` is not present, create it with `add_worksheet(title=tab_name, rows=200, cols=20)` and optionally append the `headers` row. It SHALL do nothing if the tab already exists. On exception it SHALL log a WARNING.

#### 2.1.5 AI Interface

**COMP-CORE-018** — The function `ask_deepseek(api_key, prompt, max_tokens=500, expect_json=True, system=None)` SHALL attempt to import `gaos_ai` and delegate to `gaos_ai.ask_ai(prompt, api_key=api_key, max_tokens=max_tokens, expect_json=expect_json, system=system)`. If `gaos_ai` is not importable (ImportError), it SHALL fall back to a direct DeepSeek API call with 3-attempt retry logic (exponential backoff: 1s, 2s) and the same return semantics.

**COMP-CORE-019** — The function `chat_deepseek(api_key, messages, system_prompt=None, max_tokens=500)` SHALL delegate to `gaos_ai.chat_ai` if available, or fall back to a direct DeepSeek chat API call.

#### 2.1.6 Communication Helpers

**COMP-CORE-020** — The function `send_sms(account_sid, auth_token, from_number, to_number, body)` SHALL POST to `https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json` with Basic Auth (`account_sid:auth_token`), form data `{From, To, Body}`, and a timeout of 30 seconds. On exception it SHALL log an ERROR.

**COMP-CORE-021** — The function `send_whatsapp(account_sid, auth_token, from_number, to_number, body)` SHALL prepend `whatsapp:` to both `from_number` and `to_number` if not already present, truncate `body` to 1,600 characters, and POST to the same Twilio Messages endpoint as `send_sms`. On exception it SHALL log an ERROR.

**COMP-CORE-022** — The function `post_to_slack(webhook_url, message)` SHALL POST `{"text": message}` as JSON to `webhook_url` with a timeout of 15 seconds. On exception it SHALL log an ERROR.

#### 2.1.7 PDF Extraction

**COMP-CORE-023** — The function `extract_pdf_text(pdf_bytes: bytes)` SHALL import `pdfplumber` lazily, open the PDF from a `BytesIO` buffer, extract text from each page, join pages with `\n`, and return the combined text. On exception it SHALL log an ERROR and return `""`.

#### 2.1.8 Utility Functions

**COMP-CORE-024** — The function `archive_file(archive_folder, content: bytes, filename: str)` SHALL create the directory (and parents) if it does not exist, and write `content` to `<archive_folder>/<filename>`. If the target path already exists, it SHALL append a numeric suffix (`_1`, `_2`, etc.) until a unique path is found. On exception it SHALL log an ERROR.

**COMP-CORE-025** — The function `safe_text(value, default="")` SHALL convert `value` to a stripped string. If `value` is `None`, empty string, or whitespace-only, it SHALL return `default`. It SHALL never raise.

**COMP-CORE-026** — The function `timestamp()` SHALL return the current local datetime as a string in the format `"%Y-%m-%d %H:%M:%S"`.

**COMP-CORE-027** — The function `twiml_gather(prompt_text, action_url)` SHALL return a valid TwiML XML string containing a `<Response><Gather input="speech" speechTimeout="auto" language="en-GB" action="{action_url}"><Say voice="Polly.Amy">{prompt_text}</Say></Gather></Response>`. It SHALL XML-escape `&`, `<`, `>` in both `prompt_text` and `action_url`.

**COMP-CORE-028** — The function `twiml_say_hangup(text)` SHALL return a TwiML XML string containing `<Response><Say voice="Polly.Amy">{text}</Say><Hangup/></Response>` with `text` XML-escaped.

#### 2.1.9 Scheduling

**COMP-CORE-029** — The function `should_run_at(hour, weekday=None, day_of_month=None, minute_start=0, minute_window=5)` SHALL return `True` only when ALL of the following conditions are met: `datetime.now().hour == hour`; `datetime.now().minute` is in the range `[minute_start, minute_start + minute_window)`; if `weekday` is not `None`, `datetime.now().weekday() == weekday`; if `day_of_month` is not `None`, `datetime.now().day == day_of_month`. It SHALL return `False` otherwise and SHALL never raise.

**COMP-CORE-030** — The function `run_loop(action_fn, poll_seconds=300)` SHALL execute `action_fn()` in a `while True` loop, sleeping `poll_seconds` between calls. All exceptions raised by `action_fn` SHALL be caught and logged as ERROR. The function SHALL exit cleanly on `KeyboardInterrupt`, printing `"\nStopped.\n"`.

#### 2.1.10 Knowledge Base

**COMP-CORE-031** — The function `load_chatbot_knowledge(cfg: dict)` SHALL read all rows from the tab specified by `cfg["google_sheets"]["tabs"]["chatbot"]` (default `"Chatbot_Knowledge"`), filter rows where both `Question` and `Answer` fields are non-empty, format each as `"Q: {question}\nA: {answer}"`, and return all pairs joined by `"\n\n"`. On exception it SHALL return `""`.

#### 2.1.11 Audit and Usage Logging

**COMP-CORE-032** — The function `log_action(cfg, module, action, status="ok", detail="")` SHALL append a row `[timestamp(), module, action, status, detail[:250]]` to the tab specified by `cfg["google_sheets"]["tabs"]["actions_log"]` (default `"Actions_Log"`). On exception it SHALL log a WARNING (not ERROR) to avoid recursive failure loops.

**COMP-CORE-033** — The function `log_usage(cfg, module, tokens: int, cost_gbp: float = 0.0)` SHALL append a row `[timestamp(), module, tokens, round(cost_gbp, 6)]` to the `Usage_Log` tab. On exception it SHALL log a WARNING.

#### 2.1.12 System Stats

**COMP-CORE-034** — The function `get_memory_usage_mb()` SHALL use `psutil.Process(os.getpid()).memory_info().rss / 1_048_576` to return current process RSS memory in MB as a float. If `psutil` is unavailable it SHALL return `0.0`.

**COMP-CORE-035** — The function `get_system_stats()` SHALL return a dict containing `memory_mb` (from `get_memory_usage_mb()`), and where `psutil` is available, `disk_usage_percent` and `cpu_percent` (with `interval=0.1`).

---

### 2.2 gaos_ai.py — AI Provider Manager

#### 2.2.1 Circuit Breaker

**COMP-AI-001** — The `_CircuitBreaker` class SHALL be initialised with `name`, `threshold` (default 5), and `cooldown` (in seconds). It SHALL maintain internal state: `failures` (int), `opened_at` (float, epoch time), and `state` (str: `"closed"` | `"open"` | `"half-open"`).

**COMP-AI-002** — The `_CircuitBreaker.allow()` method SHALL return `True` when state is `"closed"` or `"half-open"`. When state is `"open"`, it SHALL check whether `time.time() - self.opened_at >= self.cooldown`; if so, transition to `"half-open"` (logging an INFO) and return `True`; otherwise return `False`.

**COMP-AI-003** — The `_CircuitBreaker.success()` method SHALL reset `failures` to 0 and transition state to `"closed"`, logging an INFO if transitioning from a non-closed state.

**COMP-AI-004** — The `_CircuitBreaker.failure()` method SHALL increment `failures` by 1. When `failures >= threshold`, it SHALL set state to `"open"`, record `opened_at = time.time()`, and log a WARNING identifying the provider name and failure count.

#### 2.2.2 Provider

**COMP-AI-005** — The `_Provider` class SHALL be initialised with `name`, `api_url`, `model`, `api_key`, `cost_per_1k`, and `breaker_cooldown`. It SHALL maintain `total_tokens`, `total_cost`, and `total_calls` counters initialised to zero.

**COMP-AI-006** — The internal `_Provider._post(messages, max_tokens, temperature, expect_json)` method SHALL: (1) return `None` immediately if `api_key` is absent or starts with `"YOUR_"`; (2) call `self.breaker.allow()` and return `None` if disallowed; (3) construct the request payload with `model`, `messages`, `max_tokens`, `temperature`; (4) if `expect_json` is `True` and provider name is `"deepseek"`, add `response_format: {"type": "json_object"}`; (5) POST with Bearer auth header and 60-second timeout; (6) on success: update `total_tokens`, `total_cost`, `total_calls`, call `breaker.success()`, return the content string; (7) on any exception: call `breaker.failure()`, log a WARNING, return `None`.

**COMP-AI-007** — The `_Provider.ask(prompt, max_tokens, expect_json, system)` method SHALL construct a messages list (optionally prepending a system message), call `_post` with `temperature=0.0`, and return `None` on failure. If `expect_json` is `True` and the raw content is not `None`, it SHALL strip markdown fences (`` ```json `` and `` ``` ``), attempt `json.loads`, and return the parsed object. On `json.loads` failure it SHALL log a WARNING with the raw content (truncated to 120 chars) and return `None`.

**COMP-AI-008** — The `_Provider.chat(messages, system_prompt, max_tokens)` method SHALL call `_post` with `temperature=0.4` and `expect_json=False`, returning the content string or `None`.

#### 2.2.3 AI Manager

**COMP-AI-009** — The `_AIManager._build()` method SHALL: read `config.json` (ignoring errors); resolve the DeepSeek key from `os.environ.get("DEEPSEEK_API_KEY")` or `cfg["deepseek"]["api_key"]`; resolve the Groq key from `os.environ.get("GROQ_API_KEY")` or `cfg["groq"]["api_key"]`; create a DeepSeek `_Provider` with `api_url="https://api.deepseek.com/v1/chat/completions"`, `model="deepseek-chat"`, `cost_per_1k=0.00014`, `breaker_cooldown=600` if the key is valid; create a Groq `_Provider` with `api_url="https://api.groq.com/openai/v1/chat/completions"`, `model="llama-3.3-70b-versatile"`, `cost_per_1k=0.0`, `breaker_cooldown=300` if the key is valid; append valid providers to `self._providers` in the order DeepSeek, Groq.

**COMP-AI-010** — The `_AIManager.ask(prompt, max_tokens, expect_json, system)` method SHALL iterate `self._providers` in order, call `p.ask(...)`, and return the first non-None result. If the responding provider is not `self._providers[0]`, it SHALL log a WARNING indicating failover. If all providers return `None`, it SHALL log an ERROR and return `{}` if `expect_json` else `""`.

**COMP-AI-011** — The `_AIManager.chat(messages, system_prompt, max_tokens)` method SHALL follow the same failover logic as `ask`, returning the first non-None string. On total failure it SHALL log an ERROR and return `""`.

**COMP-AI-012** — The `_AIManager.status()` method SHALL return a dict with `active_provider` (name of first provider, or `"none"`), and a `providers` list. Each provider entry SHALL include `name`, `calls`, `tokens`, `cost_gbp` (rounded to 6 decimal places), and `circuit_state`.

**COMP-AI-013** — The module-level `_manager` variable SHALL be `None` on import. `_get_manager()` SHALL initialise `_AIManager()` on first call and cache it. The `reset()` function SHALL set `_manager = None` to force re-initialisation on the next call.

**COMP-AI-014** — The public functions `ask_ai` and `chat_ai` SHALL accept an `api_key` parameter for backward compatibility with existing module code but SHALL ignore it; key resolution SHALL occur exclusively inside `_AIManager._build()`.

---

### 2.3 gaos_launcher.py — Module Orchestrator

**COMP-LAUN-001** — The module SHALL define `MODULE_FILES` as a dict mapping two-digit string module IDs (e.g. `"01"`, `"08"`) to fully qualified Python module paths (e.g. `"modules.module_01_invoice_scanner"`). All 34 active modules SHALL be registered. Module IDs 09 and 11 SHALL NOT be present (merged into module 08 in v3.2).

**COMP-LAUN-002** — The module SHALL define `MODULE_NAMES` as a dict mapping the same IDs to human-readable names for display and process naming.

**COMP-LAUN-003** — The module SHALL define `ROLES` as a dict. Each role entry SHALL contain `name`, `tagline`, `modules` (list of two-digit ID strings), and `price` (int GBP). The six named roles SHALL be: `admin` (01, 05, 06, 07, 08, 27), `sales` (02, 03, 04, 08, 15), `finance` (08, 13, 14, 16, 19, 20, 36), `receptionist` (10, 12, 22, 23), `marketer` (17, 18, 21, 32, 33, 34), `intelligence` (25, 26, 28, 29, 30, 31, 35).

**COMP-LAUN-004** — The `TIERS` dict SHALL map role keys to module lists, and `"full_team"` SHALL resolve to the de-duplicated union of all role module lists plus `"24"` and `"36"`.

**COMP-LAUN-005** — The `SERVER_MODULES` constant SHALL be `{"22", "23", "24"}`. The `launch()` function SHALL separate module IDs into `poller_ids` (not in `SERVER_MODULES`) and `server_needed` (in `SERVER_MODULES`).

**COMP-LAUN-006** — For each `poller_id`, the `launch()` function SHALL create a `multiprocessing.Process` with `target=start_module`, `args=(module_id,)`, and `name=MODULE_NAMES[module_id]`, call `p.start()`, and append to the `processes` list.

**COMP-LAUN-007** — If any `server_needed` module IDs are present, `launch()` SHALL print an informational notice directing the operator to start `gaos_server.py` in a separate terminal. It SHALL NOT attempt to start these modules as polling processes.

**COMP-LAUN-008** — The `launch()` function SHALL call `p.join()` for all poller processes, blocking until all exit. On `KeyboardInterrupt`, it SHALL call `p.terminate()` for each process and print a shutdown message.

**COMP-LAUN-009** — The `start_module(module_id)` function SHALL call `importlib.import_module(MODULE_FILES[module_id])` and then call `module.run()`. Exceptions from `run()` will propagate naturally and terminate that child process only.

**COMP-LAUN-010** — The CLI `main()` function SHALL handle the following command-line patterns: no args or `help` → print usage; `list` → print all modules grouped by role; `module <id>` → launch single module à la carte; `<role_key>` → launch the corresponding tier. Unknown module IDs and unknown role keys SHALL print a user-friendly error message and return without raising.

---

### 2.4 gaos_server.py — Flask Web Server

**COMP-SRV-001** — The Flask application SHALL be created as `app = Flask(__name__)` with the alias `application = app` for gunicorn compatibility.

**COMP-SRV-002** — On module load, `_load()` SHALL call `core.load_config()` and assign the result to the module-level `cfg` dict.

**COMP-SRV-003** — The `_get_gmail()` function SHALL lazily connect Gmail on first call that requires it (currently no route uses Gmail directly; this is provided for future use). If connection fails it SHALL log a WARNING and return `None`.

**COMP-SRV-004** — Modules 22, 23, and 24 SHALL be imported lazily via `_chatbot()`, `_whatsapp()`, and `_voice()` functions respectively. Each SHALL attempt `from modules import module_NN_xxx as m` on first call and cache the result. If import fails it SHALL log an ERROR and return `None`.

**COMP-SRV-005** — `GET /health` SHALL return HTTP 200 with Content-Type `application/json` and body `{"status": "ok", "modules": {"chatbot": bool, "whatsapp": bool, "voice": bool}, "config_loaded": bool, "gmail_connected": bool}`. It SHALL never return a non-200 status under normal server operation.

**COMP-SRV-006** — `POST /chat` SHALL: parse the JSON request body (force=True, default `{}`); extract `session_id` (default `"default"`) and `message` (stripped); return HTTP 400 with `{"error": "message is required"}` if message is empty; call `m.handle_message(cfg, session_id, message)` from the Module 22 handler; return `{"reply": reply}` as JSON. If Module 22 is unavailable it SHALL return HTTP 503. On any other exception it SHALL return HTTP 500 with a safe error reply.

**COMP-SRV-007** — `POST /whatsapp` SHALL: extract `Body` and `From` from `request.form`; if either is empty, return an empty TwiML `<Response/>`; call `m.handle_message(cfg, sender, body)` from the Module 23 handler; return the reply wrapped in TwiML `<Message>` with `mimetype="text/xml"`. On unavailability or exception it SHALL return a TwiML message with an appropriate fallback text.

**COMP-SRV-008** — `POST /voice` SHALL: extract `CallSid` from `request.form`; call `m.greeting(cfg, call_sid)` from the Module 24 handler; return the resulting TwiML with `mimetype="text/xml"`. On unavailability it SHALL return `twiml_say_hangup("Thank you for calling. Please try again shortly.")`.

**COMP-SRV-009** — `POST /voice/handle` SHALL: extract `CallSid`, `From`, and `SpeechResult` from `request.form`; call `m.handle_turn(cfg, call_sid, caller, speech_text)` from Module 24; return TwiML. On unavailability or exception it SHALL return a `twiml_say_hangup` response.

**COMP-SRV-010** — `GET /widget.js` SHALL serve the file `static/widget.js` from the directory containing `gaos_server.py`, with `mimetype="application/javascript"`.

**COMP-SRV-011** — When run directly (`__name__ == "__main__"`), the server SHALL read `port` from `cfg.get("server", {}).get("port", 8080)` and start with `app.run(host="0.0.0.0", port=port, debug=False)`.

---

### 2.5 gaos_install.py — Industry Pack Installer

**COMP-INST-001** — The `TAB_HEADERS` dict SHALL define column header lists for all standard and pack-specific tab names. Tab names defined SHALL include at minimum all 25 standard tabs listed in Section 5 of this document.

**COMP-INST-002** — The `load_packs()` function SHALL read and JSON-parse `industry_packs.json` from the same directory as `gaos_install.py`. On `FileNotFoundError` or `JSONDecodeError` it SHALL print a descriptive error and call `sys.exit(1)`.

**COMP-INST-003** — The `install_pack(pack_key)` function SHALL perform five steps in sequence: (1) create all sheet tabs; (2) seed `FAQ_Knowledge_Base`; (3) seed `Chatbot_Knowledge` if different from FAQ tab; (4) seed `Licences`; (5) write `contract_template.txt`. It SHALL then merge tab keys into `config.json`.

**COMP-INST-004** — The `_create_tabs(sheet_id, tabs)` function SHALL call `core.sheets_find_or_create_tab` for each tab in the pack's `sheet_tabs` dict, passing the header row from `TAB_HEADERS` if the tab name is present there.

**COMP-INST-005** — The `_seed_faq(sheet_id, tab_name, faq_rows)` function SHALL first call `core.sheets_read_all` to check for existing rows. If the tab already has rows, it SHALL print a skip message and return without writing. This prevents duplicate seeding on re-runs.

**COMP-INST-006** — The `_seed_licences` function SHALL follow the same pre-check-and-skip pattern as `_seed_faq`. Each licence row written SHALL have the format `[Description, "" (expiry to fill), alert_days_before, "Active", ""]`.

**COMP-INST-007** — The `_update_config_tabs` function SHALL read `config.json`, merge each `key: tab_name` from the pack's `sheet_tabs` dict into `cfg["google_sheets"]["tabs"]` (only for keys not already present), and write the updated config back. It SHALL gracefully handle a missing `config.json`.

**COMP-INST-008** — Before provisioning, `install_pack` SHALL verify that `google_sheets.sheet_id` in `config.json` is a non-empty string that does not equal `"YOUR_GOOGLE_SHEET_ID_HERE"`. If this check fails it SHALL print a descriptive error and call `sys.exit(1)`.

---

## 3. Module-Level Requirements

### Zone 1 — React

#### Module 01 — Invoice Scanner

**MOD-01-001** | **ID:** 01 | **Name:** Invoice Scanner | **Zone:** React | **Trigger:** Gmail poll — unread emails with PDF attachment  
**Schedule/Condition:** Every poll cycle. Gmail query: `is:unread has:attachment filename:pdf`  
**Inputs:** Gmail message with PDF attachment; `config.json`  
**Processing:**
1. The module SHALL call `core.gmail_get_message` to retrieve sender information.
2. The module SHALL call `core.gmail_download_pdf` to retrieve attachment bytes and filename.
3. If no PDF is found, the module SHALL call `core.gmail_mark_read` and return `False`.
4. The module SHALL call `core.extract_pdf_text` on the PDF bytes.
5. If the extracted text is empty (scanned PDF), the module SHALL mark as read and return `False`.
6. The module SHALL submit the first 4,000 characters of PDF text to the AI via `core.ask_deepseek` requesting JSON with keys `VendorName`, `InvoiceDate` (YYYY-MM-DD), `TotalAmount`, `TaxAmount`, `InvoiceNumber`.
7. The module SHALL call `_is_duplicate(cfg, vendor, invoice_date, invoice_number)` which reads Invoice_Log and returns `True` if a row with the same VendorName+InvoiceDate OR the same InvoiceNumber already exists. If duplicate, the module SHALL log a WARNING and return `False` without writing any row.
8. The module SHALL call `_anomaly_note(cfg, amount_str)` which reads the `invoice_avg` key from GAOS_Memory; if the parsed amount exceeds 2.5× the average, it returns an anomaly warning string; otherwise returns `""`.
9. The module SHALL append an 8-column row to `Invoice_Log` containing: VendorName, InvoiceDate, TotalAmount, TaxAmount, InvoiceNumber, sender address, timestamp, anomaly note.
10. The module SHALL archive the PDF bytes via `core.archive_file` to `settings.archive_folder` with filename `{VendorName}_{original_filename}`.
11. The module SHALL send an alert email to `gmail.alert_email` summarising the extracted fields, including InvoiceNumber and any anomaly note.
12. The module SHALL call `core.gmail_mark_read`.

**Outputs:** Row in Invoice_Log (8 columns); archived PDF; alert email to owner  
**Error Behaviour:** Any per-message exception SHALL be caught, logged as ERROR, and processing SHALL continue with the next message. AI extraction failure SHALL use fallback values `{"VendorName": "Extraction Failed", ...}`. Duplicate detection failure SHALL not prevent processing.

---

#### Module 02 — Lead Catcher

**MOD-02-001** | **ID:** 02 | **Name:** Lead Catcher | **Zone:** React | **Trigger:** Gmail poll  
**Schedule/Condition:** Every poll. Gmail query: `is:unread (subject:enquiry OR subject:"contact form" OR subject:"new submission")`  
**Inputs:** Incoming enquiry email; business name from config  
**Processing:**
1. The module SHALL immediately apply the Gmail label `"GAOS/Lead"` to the message (before any processing) to prevent Module 03 double-processing.
2. The module SHALL retrieve message headers and body text.
3. If body text is empty, the module SHALL mark as read and return `False`.
4. The module SHALL submit the first 2,000 characters of body text to AI requesting JSON keys: `LeadName`, `LeadEnquiry`, `SuggestedReply`, `LeadScore` (`"Hot"`, `"Warm"`, or `"Cold"`).
5. On AI failure, the module SHALL log an ERROR, mark as read, and return `False`.
6. The module SHALL call `core.gmail_create_draft` with the suggested reply addressed to the sender.
7. The module SHALL append a row to `Lead_Log`: LeadName, sender email, enquiry summary, LeadScore, timestamp. The `Status` column SHALL store the AI-assigned score (`"Hot"`, `"Warm"`, or `"Cold"`).
8. If Twilio is configured (account_sid does not contain `"YOUR_"`), the module SHALL send a WhatsApp alert to `twilio.owner_mobile`. For `"Hot"` leads, the message prefix SHALL be `"🔥 HOT LEAD"`; for others it SHALL be `"New lead"`.
9. The module SHALL call `core.gmail_mark_read`.

**Outputs:** Gmail label; draft reply; Lead_Log row; WhatsApp alert  
**Error Behaviour:** Per-message exceptions are caught by the calling loop.

---

#### Module 03 — Urgent Lead Alert

**MOD-03-001** | **ID:** 03 | **Name:** Urgent Lead Alert | **Zone:** React | **Trigger:** Gmail poll  
**Schedule/Condition:** Every poll. Gmail query: emails matching urgency criteria, explicitly excluding messages bearing the `"GAOS/Lead"` label (to avoid double-alerting leads already handled by Module 02).  
**Inputs:** High-urgency enquiry email  
**Processing:**
1. The module SHALL search for unread emails that match its urgency criteria AND do NOT have the `GAOS/Lead` label.
2. The module SHALL submit up to 1,500 characters of body text to AI requesting JSON keys: `Name`, `Need` (5 words max), `Phone`.
3. The module SHALL fire an SMS to `twilio.owner_mobile` with the message `"URGENT LEAD: {Name} wants {Need}. Call back now: {Phone}"`.
4. On AI failure, the module SHALL use fallback values and still fire the SMS.
5. The module SHALL mark the message as read.

**Outputs:** SMS to owner  
**Error Behaviour:** If Twilio is not configured, the module SHALL skip SMS silently.

---

#### Module 04 — Review Requester

**MOD-04-001** | **ID:** 04 | **Name:** Review Requester | **Zone:** React | **Trigger:** Sheets poll  
**Schedule/Condition:** Every poll cycle. Reads `Completed_Jobs` tab.  
**Processing:** The module SHALL read all rows from `Completed_Jobs`. For each row where `Status` indicates completion and `Review Sent` is blank, it SHALL send an email to the client's address containing the `business.google_review_link` and update the `Review Sent` column.

---

#### Module 05 — Contract Sender

**MOD-05-001** | **ID:** 05 | **Name:** Contract Sender | **Zone:** React | **Trigger:** Sheets poll  
**Schedule/Condition:** Every poll. Reads `Contract_Log` tab.  
**Processing:** For each row in `Contract_Log` where status indicates a new contract and `Contract Sent` is blank, the module SHALL read `contract_template.txt`, substitute client-specific placeholders, email the contract to the client, and update the `Contract Sent` column.

---

#### Module 06 — FAQ Auto-Reply

**MOD-06-001** | **ID:** 06 | **Name:** FAQ Auto-Reply | **Zone:** React | **Trigger:** Gmail poll  
**Schedule/Condition:** Every poll. Searches for unread emails matching FAQ patterns.  
**Processing:** The module SHALL read all rows from `FAQ_Knowledge_Base`. For each matching unread email, it SHALL submit the question to AI with the knowledge base content and create a draft reply if the confidence threshold is met (≥90%). It SHALL NOT auto-send; drafts are for owner review. When the AI returns `CanAnswer: false`, the module SHALL append a row to the `FAQ_Gaps` tab (default name `"FAQ_Gaps"`, configurable via tab key `faq_gaps`) containing: email subject (truncated to 120 chars), body text (truncated to 200 chars), sender address, and timestamp. This enables the owner to identify recurring unanswered questions and expand the knowledge base.

---

#### Module 07 — Team Broadcaster

**MOD-07-001** | **ID:** 07 | **Name:** Team Broadcaster | **Zone:** React | **Trigger:** Gmail poll or Sheets condition  
**Processing:** The module SHALL read broadcast triggers and send notifications to the configured Slack webhook and/or team email addresses. It SHALL use `core.post_to_slack` for Slack delivery. For payment-related trigger events, the module SHALL apply the regex `r'[£$€]\s*[\d,]+(?:\.\d{2})?'` to the email body and, if a monetary amount is found, SHALL include it in bold in the Slack notification (e.g. `"Payment received — *£1,250.00*"`). If no amount is found, the notification is sent without the amount suffix.

---

### Zone 2 — Chase

#### Module 08 — Unified Item Chaser

**MOD-08-001** | **ID:** 08 | **Name:** Unified Item Chaser | **Zone:** Chase | **Trigger:** Sheets poll  
**Schedule/Condition:** Every poll cycle.  
**Inputs:** `Invoice_Log`, `Proposals`, `Pending_Documents` tabs  
**Processing:**
The module SHALL process three named `ChaseConfig` entries in sequence:

*Payment Chaser:*  
- Tab: `Invoice_Log` (key `invoices`)  
- Date column: `Invoice Date`; Status column: `Status`; Done values: `(paid, cancelled, void)`  
- Chase column: `Chase Sent`; Email column: `Source Email`; Name column: `Vendor`  
- Threshold: 14 days from Invoice Date

*Proposal Chaser:*  
- Tab: `Proposals` (key `proposals`)  
- Date column: `Proposal Date`; Status column: `Status`; Done values: `(accepted, declined, cancelled)`  
- Chase column: `Chase Sent`; Email column: `Client Email`; Name column: `Client Name`  
- Threshold: 5 days from Proposal Date

*Document Chaser:*  
- Tab: `Pending_Documents` (key `pending_documents`)  
- Date column: `Requested Date`; Status column: `Received`; Done values: `(yes, received, ✓)`  
- Chase column: `Chased`; Email column: `Client Email`; Name column: `Client Name`  
- Threshold: 3 days from Requested Date

For each `ChaseConfig`, the generic engine SHALL:
1. Read all rows from the tab.
2. For each row: skip if status is in `done_values`; skip if email is empty.
3. Parse the date column value using format `"%Y-%m-%d"` (first 10 characters). Skip rows with unparseable dates.
4. For non-escalating chasers (proposals, documents): skip if chase column equals `"sent"` (case-insensitive) or if days elapsed < `chaser.days`.
5. For the escalating Payment Chaser: determine the current tier from the `Chase Sent` cell value (`""` or `"no"` → tier 0; `"sent"` or `"sent-1"` → tier 1; `"sent-2"` → tier 2; `"sent-3"` → tier 3). Skip if already at the maximum tier (tier 3). The threshold for the next tier is taken from `escalation_days[current_tier]` (values: 14, 21, 30). For tier-0 rows where the vendor name matches a known late payer from GAOS_Memory, the threshold SHALL be reduced to `min(14, 7) = 7` days.
6. Before sending any chase email, call `_recently_emailed(gmail, email)` which searches the Gmail sent folder for `to:{email} in:sent newer_than:2d`. If a message was sent to that address in the last 48 hours, skip the row and log an INFO.
7. For escalating chasers, call `build_payment_email(row, cfg, level=next_tier)` where level 1 is polite, level 2 is firm, level 3 is final notice. Mark the cell `"Sent-{next_tier}"`.
8. For non-escalating chasers, call the appropriate builder and mark the cell `"Sent"`.
9. Send the email via `core.gmail_send`.
10. Update the chase column cell using `core.sheets_update_cell(sheet_id, tab, row_index + 2, chase_col, mark)`.

The `run_all_chasers` function SHALL load the late-payer list from GAOS_Memory once (via `_get_late_payers(cfg)`) and pass it to each `check_and_chase` call.

**Outputs:** Chase emails (Sent-1/Sent-2/Sent-3 for payments; Sent for proposals/documents); updated Sheets cells  
**Error Behaviour:** Per-chaser exceptions are caught and logged; remaining chasers still execute.

---

#### Module 10 — Appointment Reminder

**MOD-10-001** | **ID:** 10 | **Name:** Appointment Reminder | **Zone:** Chase | **Trigger:** Sheets poll  
**Schedule/Condition:** Every poll. Reads `Appointments` tab.  
**Processing:**
1. The module SHALL read all rows from `Appointments`.
2. For each row: parse `Date` (YYYY-MM-DD) and `Time` (HH:MM) into a `datetime` object.
3. If parse fails, skip the row.
4. Before sending any reminder, call `_client_requested_reschedule(gmail, email)` which searches Gmail for `from:{email} newer_than:3d` and scans for reschedule keywords (e.g. "reschedule", "change appointment", "can we move", "different time", "postpone"). If a reschedule request is detected, update the `Status` column to `"Reschedule Requested"` and skip the reminder.
5. Calculate `hours_until = (appt_dt - datetime.now()).total_seconds() / 3600`.
6. If `21 <= hours_until <= 25` and the `Reminder Sent` column is blank (24-hour reminder): send SMS and email; update `Reminder Sent`.
7. If `1 <= hours_until <= 3` and the `2h Sent` equivalent column is blank (2-hour reminder): send SMS and email; update the 2h column.
8. SMS message format: `"Hi {client}, {prefix} — you have an appointment with {business} at {time_str}. Reply STOP to opt out."`

**Outputs:** Reminder SMS and email; updated Sheets columns; `Status` updated to `"Reschedule Requested"` when detected

---

#### Module 12 — No-Show Follow-Up

**MOD-12-001** | **ID:** 12 | **Name:** No-Show Follow-Up | **Zone:** Chase | **Trigger:** Sheets poll  
**Schedule/Condition:** Every poll. Reads `Appointments` tab for same-day missed appointments.  
**Processing:** For appointments where the scheduled time has passed today, status is not "attended" or equivalent, and no no-show communication has been sent, the module SHALL send a follow-up email/SMS and update the `No_Show_Sent` column.

---

### Zone 3 — Report

#### Module 13 — Daily Digest

**MOD-13-001** | **ID:** 13 | **Name:** Daily Digest | **Zone:** Report | **Trigger:** Timed  
**Schedule:** Daily at 08:00 (`core.should_run_at(8)`)  
**Processing:**
1. The module SHALL read row counts from: `Lead_Log`, `Invoice_Log`, `Completed_Jobs`, `Appointments`.
2. It SHALL count yesterday's rows by matching the date column against `(datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")`.
3. It SHALL construct a plain-text summary of the counts and submit to AI with the prompt requesting a 200-word or fewer email body in professional-but-warm tone, referencing the date and key highlights.
4. It SHALL send the AI-generated digest email to `gmail.alert_email` with subject including the date.
5. After sending the email, if `slack.webhook_url` is configured and does not contain `"YOUR_"`, it SHALL call `core.post_to_slack` with a message containing the date as a bold header followed by the first 12 lines of the digest body.

**Outputs:** Daily digest email to owner; Slack post (if configured)

---

#### Module 14 — Weekly Revenue Snapshot

**MOD-14-001** | **ID:** 14 | **Name:** Weekly Revenue Snapshot | **Zone:** Report | **Trigger:** Timed  
**Schedule:** Every Monday at 08:00 (`core.should_run_at(8, weekday=0)`)  
**Processing:** Reads `Invoice_Log` for the past 7 days, sums amounts, compares with prior week, and emails an AI-generated revenue summary.

---

#### Module 15 — Lead Pipeline Report

**MOD-15-001** | **ID:** 15 | **Name:** Lead Pipeline Report | **Zone:** Report | **Trigger:** Timed  
**Schedule:** Every Friday at 17:00 (`core.should_run_at(17, weekday=4)`)  
**Processing:** Reads `Lead_Log`, counts by status, calculates conversion rate, and emails an AI-generated pipeline summary.

---

#### Module 16 — Staff Timesheet Summary

**MOD-16-001** | **ID:** 16 | **Name:** Staff Timesheet Summary | **Zone:** Report | **Trigger:** Timed  
**Schedule:** Every Friday at 18:00 (`core.should_run_at(18, weekday=4)`)  
**Processing:** Reads `Timesheets` tab, aggregates hours per employee for the current week, and emails a summary.

---

### Zone 4 — Schedule

#### Module 17 — Birthday and Anniversary Mailer

**MOD-17-001** | **ID:** 17 | **Zone:** Schedule | **Trigger:** Timed  
**Schedule:** Daily at 09:00. Reads `Clients` tab for today's birthdays/anniversaries and sends personalised emails.

#### Module 18 — Social Post Scheduler

**MOD-18-001** | **ID:** 18 | **Zone:** Schedule | **Trigger:** Every poll  
**Processing:** Reads `Social_Queue` tab. For rows where `Scheduled Date` is today or past, `Status` is pending, and `Platform`/`Caption` are populated, marks them as published and (where configured) posts via available APIs.

#### Module 19 — Monthly Invoice Generator

**MOD-19-001** | **ID:** 19 | **Zone:** Schedule | **Trigger:** Timed  
**Schedule:** 1st of each month at 08:00 (`core.should_run_at(8, day_of_month=1)`)  
**Processing:** Reads `Retainer_Clients` tab. For active clients, generates an invoice email based on `Amount` and `Billing Day`, sends to client email, and appends a row to `Invoice_Log`. Invoice numbers SHALL use the format `INV-YYYYMM-NNN` where YYYYMM is the current year-month and NNN is a zero-padded sequence starting from where the current month's existing Invoice_Log entries left off (i.e. the module reads Invoice_Log to count rows already prefixed with `INV-{YYYYMM}` and increments from that count). This ensures sequential numbers across manual and automated invoices within the same month.

#### Module 20 — Licence and Expiry Alert

**MOD-20-001** | **ID:** 20 | **Zone:** Schedule | **Trigger:** Timed  
**Schedule:** Daily at 09:00. Reads `Licences` tab. For items where `Expiry Date` is within `Alert Days Before` days of today and `Last Alerted` is not today, sends an alert email and updates `Last Alerted`.

#### Module 21 — Re-Engagement Mailer

**MOD-21-001** | **ID:** 21 | **Zone:** Schedule | **Trigger:** Timed  
**Schedule:** Every Monday at 10:00 (`core.should_run_at(10, weekday=0)`)  
**Processing:** Reads `Clients` tab. For clients where `Last Contact` date is more than `INACTIVE_DAYS` (default 90) days in the past, sends a re-engagement email and updates the `Re-Engaged` column with the current timestamp. Before sending, the module SHALL check the `Status` column; if the value matches any of: `churned`, `inactive`, `cancelled`, `lost`, `do not contact` (case-insensitive), the row SHALL be skipped silently. Rows where `Re-Engaged` is already set to `"sent"` (case-insensitive) SHALL also be skipped.

---

### Zone 5 — Converse

#### Module 22 — Website Chatbot

**MOD-22-001** | **ID:** 22 | **Zone:** Converse | **Trigger:** Flask webhook POST /chat  
**Processing:**
1. `handle_message(cfg, session_id, message)` SHALL retrieve or create a conversation history list for `session_id` in the module-level `_conversations` dict.
2. It SHALL call `core.load_chatbot_knowledge(cfg)` to retrieve the knowledge base.
3. It SHALL call `build_system_prompt(cfg, knowledge)` to construct the system prompt limiting replies to 60 words.
4. It SHALL append `{"role": "user", "content": message}` to the history.
5. It SHALL call `core.chat_deepseek(api_key, history[-MAX_HISTORY:], system_prompt)`.
6. It SHALL append the assistant reply to the history.
7. It SHALL call `detect_and_log_lead(cfg, session_id, message, history)` to capture any email addresses.
8. It SHALL return the reply string.

**COMP-SRV note:** `MAX_HISTORY = 10` turns per session. History is stored in process memory; it does not persist across server restarts.

**MOD-22-002** — `detect_and_log_lead` SHALL use a regex to detect email addresses in the user message. On detection, it SHALL use AI to extract Name and Interest from the last 6 turns of conversation, then append a row to `Lead_Log`.

---

#### Module 23 — WhatsApp AI Agent

**MOD-23-001** | **ID:** 23 | **Zone:** Converse | **Trigger:** Flask webhook POST /whatsapp  
**Processing:**
1. `handle_message(cfg, sender, body)` SHALL check whether the message matches a Chief of Staff query pattern (if Module 35 is available) and delegate if so.
2. Otherwise, it SHALL load chatbot knowledge and generate a reply via `core.chat_deepseek`.
3. Conversation history SHALL be maintained per `sender` (phone number) in module-level memory.
4. The reply SHALL be returned as a plain string for the server to wrap in TwiML.

---

#### Module 24 — AI Voice Agent

**MOD-24-001** | **ID:** 24 | **Zone:** Converse | **Trigger:** Flask webhook POST /voice and POST /voice/handle  
**Processing:**
1. `greeting(cfg, call_sid)` SHALL load chatbot knowledge and return `core.twiml_gather(greeting_prompt, action_url)` where `action_url` is `"{server.public_url}/voice/handle"`.
2. `handle_turn(cfg, call_sid, caller, speech_text)` SHALL: load or retrieve conversation history for `call_sid`; append the speech text as user turn; call `core.chat_deepseek` with the chatbot system prompt and history; append the reply; return `core.twiml_gather(reply, action_url)`.
3. If `speech_text` is empty, the module SHALL return a polite `twiml_gather` re-prompting the caller.
4. Voice output SHALL use AWS Polly voice `"Polly.Amy"` in `language="en-GB"`.

---

### Zone 6 — Learn

#### Module 25 — GAOS Learn

**MOD-25-001** | **ID:** 25 | **Zone:** Learn | **Trigger:** Timed  
**Schedule:** Every Monday at 07:00 (`core.should_run_at(7, weekday=0)`)  
**Processing:** Executes the weekly learning cycle in order: `learn_invoices`, `learn_leads`, `learn_revenue`, `learn_faqs`, `learn_appointments`, `learn_chase_rate`, and calls `learn_appointment_peak()` from within `learn_appointments`. Each function reads the relevant tab, computes statistics, and calls `save_memory` to upsert key-value rows in `GAOS_Memory`.

`learn_chase_rate(cfg)` SHALL read all Invoice_Log rows, compute the proportion with a non-blank `Chase Sent` value that is not `"no"`, and if this proportion exceeds 40%, save the key `chase_rate` to GAOS_Memory with an advisory such as `"Chase rate is high — X% of invoices required chasing. Review payment terms."`.

`learn_appointment_peak()` (called from `learn_appointments`) SHALL classify each appointment's `Time` column into one of four named slots — morning (before 12:00), lunchtime (12:00–13:59), afternoon (14:00–17:59), evening (18:00 and later) — count appointments per slot, and save the name of the busiest slot to GAOS_Memory as `appointment_peak_time`.

**MOD-25-002** — `save_memory(cfg, key, value)` SHALL read all rows from `GAOS_Memory`, find an existing row with matching `Key`, and update its `Value` cell if found. If not found, it SHALL append a new row `[key, value, timestamp()]`.

**MOD-25-003** — `inject(cfg, base_prompt)` SHALL call `get_context(cfg)` and, if a non-empty context string is returned, prepend it to `base_prompt` as `"{context}\n\n{base_prompt}"`. If no memory exists, it SHALL return `base_prompt` unchanged.

**MOD-25-004** — Minimum data thresholds for learning functions: `learn_invoices` and `learn_leads` SHALL require at least 5 rows. `learn_revenue` SHALL require at least 10 rows. Functions SHALL return silently without writing memory if the threshold is not met.

---

#### Module 26 — Client Pulse

**MOD-26-001** | **ID:** 26 | **Zone:** Learn | **Trigger:** Timed  
**Schedule:** Every Monday at 07:30 (`core.should_run_at(7, weekday=0, minute_start=30)`)  
**Processing:** Reads `Clients` tab. For clients where `Last Contact` is more than 30 days ago, appends to `Client_Pulse_Log`, saves the at-risk client names to GAOS_Memory as `at_risk_clients`, and sends an alert email to the owner listing silent clients. After identifying at-risk clients, the module SHALL cross-reference them against Invoice_Log: for any at-risk client whose name matches a vendor with an unpaid invoice (Status not in `paid`, `cancelled`, `void`), that client SHALL be added to a `danger` list. If the danger list is non-empty, the module SHALL save a `danger_signals` key to GAOS_Memory with a message of the form `"Double risk: {names} — relationship cooling AND unpaid invoice. Immediate personal contact recommended."`

---

#### Module 27 — Document Sentinel

**MOD-27-001** | **ID:** 27 | **Zone:** Learn | **Trigger:** Every poll  
**Processing:** Reads `Sentinel_Actions` or compliance-related tabs. Monitors for expired or missing compliance documents. On detection, sends an alert and logs to `Sentinel_Actions`.

---

#### Module 28 — Planning Radar

**MOD-28-001** | **ID:** 28 | **Zone:** Learn | **Trigger:** Timed  
**Schedule:** Every Monday at 08:00 (`core.should_run_at(8, weekday=0)`)  
**Processing:** Fetches planning applications from the council planning portal URL configured in `business.council_planning_url`. Filters for applications near `business.postcode`. Logs new applications to the lead or notes log and emails relevant findings to the owner.

---

### Zone 0 — Sense

#### Module 29 — Gazette Monitor

**MOD-29-001** | **ID:** 29 | **Zone:** Sense | **Trigger:** Timed  
**Schedule:** Daily at 07:00 (`core.should_run_at(7)`)  
**Inputs:** London Gazette API; `Invoice_Log` and `Clients` tabs  
**Processing:**
1. The module SHALL fetch insolvency notices using `GAZETTE_API` with `notice-type=2700`, `start-publish-date=(today - 1 day)`, `results-page-size=50`, `format=application/json`.
2. It SHALL fetch strike-off notices using `notice-type=2750` with the same parameters.
3. It SHALL fetch estate notices using `notice-type=2600`.
4. For insolvency and strike-off notices, it SHALL call `extract_company_names()` to parse company names from notice records by checking fields `companyName`, `company_name`, `name`, `title`, `subject` and by applying the regex `r'[A-Z][A-Z &\'\-]{2,}\s+(?:LIMITED|LTD|PLC|LLP|PARTNERSHIP)'` on body text.
5. It SHALL call `cross_reference()` to compare extracted names against vendors in `Invoice_Log` and names in `Clients` using `fuzzy_match()`.
6. `fuzzy_match(gazette_name, client_name)` SHALL: strip `LIMITED/LTD/PLC/LLP` from both names; return `True` if one contains the other, or if both names share the same first 6 characters (where length > 6).
7. For estate notices, up to 10 notices SHALL be logged to `Lead_Log` as estate leads.
8. If any insolvency or strike-off matches are found, the module SHALL send an immediate risk alert email to `gmail.alert_email`.

**Outputs:** `Gazette_Hits` tab rows; alert email; `Lead_Log` entries for estate notices

---

#### Module 30 — Land Registry Radar

**MOD-30-001** | **ID:** 30 | **Zone:** Sense | **Trigger:** Timed  
**Schedule:** Every Monday at 09:00 (`core.should_run_at(9, weekday=0)`)  
**Processing:**
1. The module SHALL download the Land Registry Price Paid monthly update from `https://publicdata.landregistry.gov.uk/market-trend-data/price-paid-data/a/pp-monthly-update-new-version.csv`.
2. It SHALL parse the CSV (using `csv.reader` on `io.StringIO`) and filter rows by postcode prefix matching `business.postcode`.
3. For each matching sale, it SHALL compute a renovation potential score: property type score (D=4, S=3, T=3, F=1, O=2) + price bracket score (≥£600k=4, ≥£350k=3, ≥£200k=2, ≥£100k=1, else 0).
4. It SHALL log the top-scored properties to `Land_Registry_Leads` tab.
5. It SHALL email a summary to the owner if new leads were found.

---

#### Module 31 — Rate and Macro Pulse

**MOD-31-001** | **ID:** 31 | **Zone:** Sense | **Trigger:** Timed  
**Schedule:** Daily at 12:00 (BoE rate check); 1st of month at 08:00 (ONS CPI check)  
**Processing:**
1. BoE Rate: The module SHALL fetch the BoE IADB CSV for series `IUMABEDR` (base rate). It SHALL compare the latest rate against `RATE_MEMORY_KEY` stored in `GAOS_Memory`. On a change, it SHALL alert the owner and draft client outreach emails.
2. ONS CPI: On the 1st of each month, the module SHALL fetch CPIH data from `https://api.beta.ons.gov.uk/v1/datasets/cpih01/...`. For each row in `Retainer_Clients`, it SHALL calculate inflation erosion since the contract's `Last Invoice` date. When erosion exceeds `EROSION_ALERT_THRESHOLD = 0.08` (8%), it SHALL flag the retainer for price review.
3. Both data points SHALL be logged to `Macro_Log`.

---

### Zone 7 — Marketer

#### Module 32 — Newsletter Mailer

**MOD-32-001** | **ID:** 32 | **Zone:** Marketer | **Trigger:** Timed  
**Schedule:** First Monday of the month at 09:00 (detected using `should_run_at(9, weekday=0, day_of_month=None)` combined with a check that `datetime.now().day <= 7`)  
**Processing:** Reads `Newsletter_Queue` for active subscribers. Generates or reads newsletter content. Sends individual emails. Logs send status to `Campaign_Log`.

---

#### Module 33 — Review Monitor

**MOD-33-001** | **ID:** 33 | **Zone:** Marketer | **Trigger:** Every poll  
**Processing:** Monitors Gmail for Google review notification emails (query: `is:unread from:@google.com` with subject containing "New review", "review", or "rated your business"). For each notification:
1. Attempts to extract star rating using regex patterns from the email snippet and subject.
2. Attempts to extract reviewer name from the snippet/subject.
3. Submits to AI to draft an appropriate response (≤60 words for positive, ≤80 words for negative).
4. Appends a row to `Reviews_Log`: reviewer, stars, snippet (120 chars), response draft, timestamp, status.
5. For negative reviews (≤3 stars): sends SMS to `twilio.owner_mobile`; sends alert email to `gmail.alert_email` with the draft response; if `slack.webhook_url` is configured and not a placeholder, calls `core.post_to_slack` with a message including the star rating, reviewer name, snippet (150 chars), and a note that a draft response is ready.
6. For positive reviews: sends an email to `gmail.alert_email` with the draft response for the owner to post.
7. Marks the Gmail notification as read.

---

#### Module 34 — Campaign Digest

**MOD-34-001** | **ID:** 34 | **Zone:** Marketer | **Trigger:** Timed  
**Schedule:** Every Friday at 17:00 (`core.should_run_at(17, weekday=4)`)  
**Processing:** Reads `Campaign_Log`. Summarises campaign performance (sent, opens, clicks, replies) using AI. Emails digest to owner.

---

### Zone 8 — Chief of Staff

#### Module 35 — AI Chief of Staff

**MOD-35-001** | **ID:** 35 | **Zone:** Chief of Staff | **Trigger:** Timed + on-demand WhatsApp  
**Schedule:** Daily at 07:30; Monday at 07:45 for weekly summary  
**Processing:**
1. The module SHALL define an `IntelItem` dataclass with fields: `category` (urgent/warm/watch/good/info), `role` (which virtual role), `headline` (str), `detail` (str), `score` (float), `action` (str).
2. The `gather_intelligence(cfg)` function SHALL read GAOS_Memory for a `danger_signals` key. If present, it SHALL create an `IntelItem` with `category="urgent"` and `score=85`. If no danger signals exist but `at_risk_clients` is present in GAOS_Memory, it SHALL create a `"watch"` IntelItem with `score=55`.
3. At 07:30 daily, the module SHALL read data from all active role data sources, instantiate `IntelItem` objects for each actionable item, sort by score descending, construct an AI prompt, call `learn.inject(cfg, prompt)` to prepend the full GAOS_Memory context, submit to AI, and produce a briefing email and WhatsApp message.
4. At 07:45 on Mondays, it SHALL produce a weekly strategic summary. The weekly-summary AI prompt SHALL also be passed through `learn.inject(cfg, prompt)` before submission.
5. `handle_if_cos_query(cfg, sender, message)` SHALL be callable by Module 23. It SHALL detect natural-language queries matching patterns including: "what needs my attention", "who owes me money", "how many leads", "double risk", "danger signal". On a match, it SHALL construct an intelligence prompt, pass it through `learn.inject(cfg, prompt)`, generate an AI response, and return `(True, reply_text)`. If no pattern matches it SHALL return `(False, None)`.

---

### Zone 9 — Utility

#### Module 36 — Cost Rollup Reporter

**MOD-36-001** | **ID:** 36 | **Zone:** Utility | **Trigger:** Timed  
**Schedule:** 1st of each month at 09:00 (`core.should_run_at(9, day_of_month=1)`)  
**Processing:**
1. The module SHALL read all rows from `Usage_Log`.
2. It SHALL filter rows to the previous calendar month by matching the `Date` column prefix against `"{last_year}-{last_month:02d}"`.
3. It SHALL aggregate total tokens and total cost per module name using a dict.
4. It SHALL compute the grand total cost in GBP.
5. It SHALL estimate subscription revenue from the active roles defined in `config.json`.
6. It SHALL compute an estimated gross margin.
7. It SHALL email the formatted report to `gmail.alert_email`.
8. If no usage data exists for the period, it SHALL log an INFO and return without sending.

---

## 4. Interface Requirements

### 4.1 Gmail API

**IFACE-001** — The system SHALL use `googleapiclient.discovery.build("gmail", "v1", credentials=creds)` to construct the Gmail service object.

**IFACE-002** — All Gmail API calls SHALL use `userId="me"` to operate on the authenticated account.

**IFACE-003** — The system SHALL use `gmail.users().messages().list(q=query, maxResults=N)` for inbox search. The `q` parameter SHALL use standard Gmail search operator syntax.

**IFACE-004** — Message retrieval SHALL use `format="full"` to retrieve headers, body parts, and attachment metadata in a single call.

**IFACE-005** — PDF attachments larger than the inline data threshold SHALL be retrieved via `gmail.users().messages().attachments().get(messageId=..., id=attachment_id)`.

**IFACE-006** — The Gmail API client SHALL use OAuth2 credentials with scopes `https://www.googleapis.com/auth/gmail.modify` and `https://www.googleapis.com/auth/gmail.compose` only.

---

### 4.2 Google Sheets API

**IFACE-007** — The system SHALL use `gspread` version 6.x as the Sheets client library.

**IFACE-008** — The spreadsheet SHALL be opened by key using `gspread.Client.open_by_key(sheet_id)`.

**IFACE-009** — Worksheet records SHALL be read via `worksheet.get_all_records(default_blank="")`, which returns a list of dicts keyed by the header row.

**IFACE-010** — Row appends SHALL use `worksheet.append_row(values, value_input_option="USER_ENTERED")` to allow Sheets to parse date strings and currency values.

**IFACE-011** — Cell updates SHALL use `worksheet.update_cell(row, col, value)` with 1-based row and column indices.

**IFACE-012** — The Sheets client SHALL authenticate via service account (preferred) or user OAuth token. Service account credentials SHALL be loaded from `service_account.json`. The service account SHALL have `Editor` access granted on the target spreadsheet.

---

### 4.3 DeepSeek API

**IFACE-013** — DeepSeek API calls SHALL be made to `https://api.deepseek.com/v1/chat/completions` via HTTPS POST.

**IFACE-014** — The request body SHALL be JSON with fields: `model` (`"deepseek-chat"`), `messages` (array of `{role, content}` objects), `max_tokens` (int), `temperature` (float). For JSON-mode requests, `response_format: {"type": "json_object"}` SHALL be added.

**IFACE-015** — The `Authorization` header SHALL be `Bearer <api_key>`.

**IFACE-016** — The response content SHALL be extracted from `response.json()["choices"][0]["message"]["content"]`. Token usage SHALL be read from `response.json()["usage"]["total_tokens"]`.

**IFACE-017** — The request timeout SHALL be 60 seconds.

---

### 4.4 Groq API

**IFACE-018** — Groq API calls SHALL be made to `https://api.groq.com/openai/v1/chat/completions` via HTTPS POST with the same request/response format as DeepSeek (OpenAI-compatible).

**IFACE-019** — The model identifier SHALL be `"llama-3.3-70b-versatile"`.

**IFACE-020** — The `response_format: json_object` parameter SHALL NOT be included in Groq requests. JSON extraction for Groq SHALL rely on prompt instructions and post-processing regex cleanup.

**IFACE-021** — The Groq circuit breaker cooldown SHALL be 300 seconds (5 minutes), shorter than DeepSeek's 600 seconds, reflecting the free-tier nature of the service.

---

### 4.5 Twilio REST API

**IFACE-022** — SMS and WhatsApp messages SHALL be sent via `POST https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json` with form data `{From, To, Body}` and HTTP Basic Authentication (`account_sid:auth_token`).

**IFACE-023** — WhatsApp sender and recipient numbers SHALL be prefixed with `"whatsapp:"` (e.g. `"whatsapp:+14155238886"`).

**IFACE-024** — Voice webhook responses SHALL be valid TwiML XML documents returned with `Content-Type: text/xml`. The `<Gather>` element SHALL specify `input="speech"`, `speechTimeout="auto"`, `language="en-GB"`, and the `action` URL pointing to `/voice/handle` on the public server.

**IFACE-025** — The `<Say>` voice element SHALL use `voice="Polly.Amy"` for all spoken responses.

**IFACE-026** — Twilio webhook `POST /whatsapp` delivers message data as HTML form fields (`Body`, `From`, `To`). The system SHALL read these from `request.form`.

---

### 4.6 Slack Webhook

**IFACE-027** — Slack notifications SHALL be sent via `POST <webhook_url>` with `Content-Type: application/json` and body `{"text": "<message>"}`.

**IFACE-028** — The Slack webhook URL SHALL be stored in `config.json` at `slack.webhook_url`. If the value contains `"YOUR_"` or is absent, Slack calls SHALL be skipped silently.

---

### 4.7 London Gazette API

**IFACE-029** — Gazette notices SHALL be fetched from `https://www.thegazette.co.uk/notice/search` via HTTP GET with parameters: `notice-type` (code string), `start-publish-date` (YYYY-MM-DD), `results-page-size=50`, `format=application/json`.

**IFACE-030** — The `Accept: application/json` header SHALL be included in the request.

**IFACE-031** — The response JSON structure SHALL be examined for results under keys `results`, `_embedded.notices`, or `notices` (in that order). The module SHALL handle all three structures to account for Gazette API versioning.

**IFACE-032** — Notice type codes: insolvency = `"2700"`, strike-off = `"2750"`, estate = `"2600"`.

---

### 4.8 HM Land Registry API

**IFACE-033** — Price Paid monthly data SHALL be downloaded from `https://publicdata.landregistry.gov.uk/market-trend-data/price-paid-data/a/pp-monthly-update-new-version.csv`.

**IFACE-034** — The CSV SHALL be decoded as UTF-8 and parsed with Python's `csv.reader`. Column positions follow the Land Registry Price Paid Data specification: index 0 = transaction ID, 1 = price, 2 = date of transfer, 3 = postcode, 4 = property type (D/S/T/F/O), 5 = new build flag, 6 = tenure, 7 = PAON, 8 = SAON, 9 = street, etc.

---

### 4.9 Bank of England API

**IFACE-035** — The BoE base rate SHALL be fetched from the IADB CSV endpoint: `https://www.bankofengland.co.uk/boeapps/database/_iadb-FromShowColumns.asp?csv.x=yes&Datefrom=01/{m}/{y}&Dateto=now&SeriesCodes=IUMABEDR&CSVF=TN&UsingCodes=Y`.

**IFACE-036** — The response is a plain CSV. The latest rate row SHALL be the last row with a numeric value in the rate column.

---

### 4.10 ONS Statistics API

**IFACE-037** — CPI data SHALL be fetched from `https://api.beta.ons.gov.uk/v1/datasets/cpih01/editions/time-series/versions/20/observations?geography=K02000001&aggregate=cpih1dim1A0`.

**IFACE-038** — The response is JSON. The latest CPIH index value SHALL be extracted from the most recent time period entry.

---

## 5. Data Requirements

All persistent data SHALL be stored in named tabs of a single Google Sheets spreadsheet. Column names are case-sensitive and must match the definitions below. All dates SHALL be stored as strings in `YYYY-MM-DD` format unless otherwise noted.

### DATA-001 — Invoice_Log

| Column | Type | Constraint |
|--------|------|-----------|
| Vendor | String | Vendor/supplier name from AI extraction (replaces legacy `Client`) |
| Invoice Date | String | YYYY-MM-DD |
| Amount | String | Currency string, e.g. `"£1,250.00"` (also `TotalAmount`) |
| Tax | String | Tax amount from AI extraction |
| Invoice Number | String | AI-extracted invoice reference; used for deduplication |
| Source Email | String | Sender email address from the PDF attachment email |
| Timestamp | String | YYYY-MM-DD HH:MM:SS of when the row was written |
| Notes | String | Anomaly flag (e.g. `"⚠ Amount 3.1× above average"`) or blank |
| Status | String | Free text; recognised values: `paid`, `cancelled`, `void` |
| Chase Sent | String | `""` or `"no"` → unsent; `"Sent-1"` → first chase sent; `"Sent-2"` → second chase; `"Sent-3"` → final notice |

### DATA-002 — Lead_Log

| Column | Type | Constraint |
|--------|------|-----------|
| Name | String | AI-extracted lead name or `"there"` |
| Email | String | Sender email address |
| Enquiry | String | AI-extracted enquiry summary |
| Status | String | AI-assigned score: `"Hot"`, `"Warm"`, or `"Cold"`. May be updated to `"Won"`, `"Converted"` etc. by the owner. |
| Timestamp | String | YYYY-MM-DD HH:MM:SS |

### DATA-003 — Completed_Jobs

| Column | Type | Constraint |
|--------|------|-----------|
| Date | String | YYYY-MM-DD |
| Client | String | Client name |
| Email | String | Client email |
| Service | String | Service description |
| Status | String | Must contain completion indicator for Module 04 |
| Review Sent | String | `""` or `"Sent"` |

### DATA-004 — Contract_Log

| Column | Type | Constraint |
|--------|------|-----------|
| Date | String | YYYY-MM-DD |
| Client | String | Client name |
| Email | String | Client email |
| Service | String | Service description |
| Status | String | Contract status |
| Contract Sent | String | `""` or `"Sent"` |

### DATA-005 — FAQ_Knowledge_Base / Chatbot_Knowledge

| Column | Type | Constraint |
|--------|------|-----------|
| Question | String | Non-empty; used as lookup key |
| Answer | String | Non-empty; used as response content |
| Category | String | Optional grouping label |

### DATA-006 — Appointments

| Column | Type | Constraint |
|--------|------|-----------|
| Date | String | YYYY-MM-DD |
| Time | String | HH:MM (24-hour) |
| Client | String | Client name |
| Email | String | Client email |
| Phone | String | Mobile number for SMS |
| Service | String | Appointment type |
| Status | String | e.g. `"confirmed"`, `"attended"`, `"no-show"` |
| Reminder Sent | String | `""` or `"Sent"` (24h reminder) |
| No_Show_Sent | String | `""` or `"Sent"` (no-show follow-up) |

### DATA-007 — Proposals

| Column | Type | Constraint |
|--------|------|-----------|
| Proposal Date | String | YYYY-MM-DD |
| Client Name | String | Required for chase email |
| Client Email | String | Required for chase email |
| Value | String | Currency string, optional |
| Status | String | Recognised done values: `accepted`, `declined`, `cancelled` |
| Chase Sent | String | `""` or `"Sent"` |

### DATA-008 — Pending_Documents

| Column | Type | Constraint |
|--------|------|-----------|
| Requested Date | String | YYYY-MM-DD |
| Client Name | String | Required |
| Email | String | Required for chase email |
| Document | String | Document description (shown in chase email) |
| Received | String | Recognised done values: `yes`, `received`, `✓` |
| Chased | String | `""` or `"Sent"` |

### DATA-009 — Clients

| Column | Type | Constraint |
|--------|------|-----------|
| Name | String | Required |
| Email | String | Required |
| Phone | String | Optional mobile number |
| Type | String | Client category |
| Last Contact | String | YYYY-MM-DD; used by Modules 21 and 26 |
| Re-Engaged | String | Timestamp of last re-engagement email, or `"sent"` |
| Notes | String | Optional |
| Status | String | Optional. Values recognised by Module 21: `churned`, `inactive`, `cancelled`, `lost`, `do not contact`. Rows with any of these values are excluded from re-engagement emails. |

### DATA-010 — Retainer_Clients

| Column | Type | Constraint |
|--------|------|-----------|
| Name | String | Required |
| Email | String | Required |
| Amount | String | Monthly fee currency string |
| Billing Day | String | Day of month for billing |
| Status | String | `"Active"` or similar |
| Last Invoice | String | YYYY-MM-DD; used by Module 31 for CPI erosion |

### DATA-011 — Licences

| Column | Type | Constraint |
|--------|------|-----------|
| Description | String | Licence/compliance item name |
| Expiry Date | String | YYYY-MM-DD; blank until client fills in |
| Alert Days Before | Number | Days before expiry to alert |
| Status | String | `"Active"` or `"Expired"` |
| Last Alerted | String | YYYY-MM-DD |

### DATA-012 — Timesheets

| Column | Type | Constraint |
|--------|------|-----------|
| Week Ending | String | YYYY-MM-DD |
| Employee | String | Staff name |
| Mon through Sat | Number | Hours worked each day |
| Total Hours | Number | Sum of daily hours |
| Notes | String | Optional |

### DATA-013 — Gazette_Hits

| Column | Type | Constraint |
|--------|------|-----------|
| Date | String | YYYY-MM-DD |
| Company | String | Company name from Gazette |
| Notice Type | String | `INSOLVENCY` or `STRIKE-OFF WARNING` |
| Details | String | Summary of notice |
| Actioned | String | `""` or `"Yes"` |

### DATA-014 — Land_Registry_Leads

| Column | Type | Constraint |
|--------|------|-----------|
| Date | String | Date of sale YYYY-MM-DD |
| Address | String | Full property address |
| Price | String | Sale price |
| Buyer | String | Optional |
| Seller | String | Optional |
| Status | String | Lead status |
| Notes | String | Optional |

### DATA-015 — Macro_Log

| Column | Type | Constraint |
|--------|------|-----------|
| Date | String | YYYY-MM-DD |
| Type | String | `"BOE_RATE"` or `"ONS_CPI"` |
| Value | String | Rate or index value |
| Change | String | Delta from previous reading |
| Notes | String | AI-generated commentary |

### DATA-016 — GAOS_Memory

| Column | Type | Constraint |
|--------|------|-----------|
| Date | String | YYYY-MM-DD HH:MM:SS of last update |
| Category | String | Learning category (optional) |
| Key | String | Unique key; used for upsert lookup |
| Value | String | Plain-English memory statement |
| Source | String | Module that wrote this row |

Standard keys written by the learning cycle:

| Key | Written By | Example Value |
|-----|-----------|--------------|
| `invoice_avg` | Module 25 `learn_invoices` | `"Average invoice value: £842.50 across 23 invoices"` |
| `top_vendors` | Module 25 `learn_invoices` | `"Top 3 vendors by invoice volume: ACME Ltd, Buildco, FastParts"` |
| `late_payers` | Module 25 `learn_invoices` | `"Suppliers with previous late payment chases: ACME Ltd, FastParts"` |
| `lead_conversion` | Module 25 `learn_leads` | `"Lead conversion rate: 34% (12 won from 35 leads)"` |
| `appointment_peak_time` | Module 25 `learn_appointments` | `"Busiest appointment slot: morning"` |
| `chase_rate` | Module 25 `learn_chase_rate` | `"Chase rate is high — 52% of invoices required chasing. Review payment terms."` |
| `at_risk_clients` | Module 26 | `"Clients with no contact in 30+ days: Acme Corp, Green Solutions Ltd"` |
| `danger_signals` | Module 26 | `"Double risk: Acme Corp — relationship cooling AND unpaid invoice. Immediate personal contact recommended."` |

### DATA-017 — Actions_Log

| Column | Type | Constraint |
|--------|------|-----------|
| Timestamp | String | YYYY-MM-DD HH:MM:SS |
| Module | String | Module identifier string |
| Action | String | Action description |
| Status | String | `"ok"` or `"error"` |
| Detail | String | Max 250 characters |

### DATA-018 — Usage_Log

| Column | Type | Constraint |
|--------|------|-----------|
| Timestamp | String | YYYY-MM-DD HH:MM:SS |
| Module | String | Module identifier |
| Tokens | Number | Total tokens for this AI call |
| Cost GBP | Number | Estimated cost to 6 decimal places |

### DATA-019 — Social_Queue

| Column | Type | Constraint |
|--------|------|-----------|
| Scheduled Date | String | YYYY-MM-DD |
| Platform | String | Target platform name |
| Caption | String | Post content |
| Image URL | String | Optional media URL |
| Status | String | `"pending"` or `"published"` |

### DATA-020 — Client_Pulse_Log

| Column | Type | Constraint |
|--------|------|-----------|
| Client | String | Client name |
| Email | String | Client email |
| Last Contact | String | YYYY-MM-DD |
| Days Silence | Number | Days since last contact |
| Status | String | Alert status |
| Actioned | String | `""` or `"Yes"` |

### DATA-021 — FAQ_Gaps

| Column | Type | Constraint |
|--------|------|-----------|
| Subject | String | Email subject, truncated to 120 characters |
| Body Preview | String | First 200 characters of email body |
| From | String | Sender email address |
| Timestamp | String | YYYY-MM-DD HH:MM:SS when logged |

This tab is written by Module 06 whenever an incoming email cannot be answered from the FAQ knowledge base. It allows the owner to identify recurring knowledge gaps and add new entries to `FAQ_Knowledge_Base`. The tab is auto-created by Module 06 with these column headers if it does not exist; no manual setup is required.

---

## 6. Configuration Requirements

The `config.json` file is the sole client-specific configuration artefact for a standard deployment. All fields below correspond directly to keys observed in `config.example.json`.

### 6.1 Top-Level Structure

**CFG-001** — `config.json` SHALL be a valid JSON object. Parsing failures SHALL cause `load_config()` to return `{}`, which will cause individual modules to fail on first access to missing keys, logged as per-module errors.

### 6.2 AI Provider Configuration

**CFG-002** — `deepseek.api_key` | Type: String | Required: Yes (for AI features) | Validation: Must not equal `"YOUR_DEEPSEEK_KEY_HERE"`. When absent or placeholder, DeepSeek provider is not loaded. May be overridden by `DEEPSEEK_API_KEY` environment variable.

**CFG-003** — `groq.api_key` | Type: String | Required: No (free fallback) | Validation: Must not equal `"YOUR_GROQ_KEY_HERE"`. May be overridden by `GROQ_API_KEY` environment variable.

### 6.3 Gmail Configuration

**CFG-004** — `gmail.watch_inbox` | Type: String | Required: Yes | Validation: Must be a valid Gmail address. This is the inbox monitored by all email-polling modules and the from-address for outbound emails.

**CFG-005** — `gmail.alert_email` | Type: String | Required: Yes | Description: Destination for all owner alert emails (digests, risk alerts, cost reports). May be the same as `watch_inbox` or a separate personal address.

### 6.4 Google Sheets Configuration

**CFG-006** — `google_sheets.sheet_id` | Type: String | Required: Yes | Validation: Must not equal `"YOUR_GOOGLE_SHEET_ID_HERE"`. This is the 44-character Google Sheets document ID from the spreadsheet URL.

**CFG-007** — `google_sheets.tabs` | Type: Object | Required: Yes | Description: Maps logical tab keys (e.g. `"invoices"`, `"leads"`) to actual Google Sheets tab names (e.g. `"Invoice_Log"`, `"Lead_Log"`). If a key is absent, modules use the default tab name shown in Section 5. The following keys SHALL be present for full system operation:

| Key | Default Tab Name | Required By |
|-----|-----------------|-------------|
| `invoices` | `Invoice_Log` | Modules 01, 08, 25, 29, 36 |
| `leads` | `Lead_Log` | Modules 02, 03, 15, 22, 29 |
| `reviews` | `Completed_Jobs` | Module 04 |
| `contracts` | `Contract_Log` | Module 05 |
| `faq` | `FAQ_Knowledge_Base` | Module 06 |
| `appointments` | `Appointments` | Modules 10, 12, 25 |
| `proposals` | `Proposals` | Module 08 |
| `pending_documents` | `Pending_Documents` | Module 08 |
| `clients` | `Clients` | Modules 21, 26, 29 |
| `social_queue` | `Social_Queue` | Module 18 |
| `retainer_clients` | `Retainer_Clients` | Modules 19, 31 |
| `licences` | `Licences` | Module 20 |
| `timesheets` | `Timesheets` | Module 16 |
| `chatbot` | `Chatbot_Knowledge` | Modules 22, 23, 24 |
| `sentinel_actions` | `Sentinel_Actions` | Module 27 |
| `gazette_hits` | `Gazette_Hits` | Module 29 |
| `land_leads` | `Land_Registry_Leads` | Module 30 |
| `macro_log` | `Macro_Log` | Module 31 |
| `newsletter_queue` | `Newsletter_Queue` | Module 32 |
| `reviews_log` | `Reviews_Log` | Module 33 |
| `campaign_log` | `Campaign_Log` | Module 34 |
| `memory` | `GAOS_Memory` | Modules 25, 35 |
| `pulse_log` | `Client_Pulse_Log` | Module 26 |
| `actions_log` | `Actions_Log` | All modules (audit) |
| `usage_log` | `Usage_Log` | gaos_ai.py, Module 36 |
| `faq_gaps` | `FAQ_Gaps` | Module 06 |

### 6.5 Twilio Configuration

**CFG-008** — `twilio.account_sid` | Type: String | Required: For SMS/WA/Voice | Validation: A Twilio Account SID beginning with `"AC"`. If contains `"YOUR_"`, all Twilio calls are skipped.

**CFG-009** — `twilio.auth_token` | Type: String | Required: For SMS/WA/Voice | Validation: Non-empty string. Transmitted as HTTP Basic Auth password.

**CFG-010** — `twilio.from_number` | Type: String | Required: For SMS | Format: E.164 format, e.g. `"+441234567890"`.

**CFG-011** — `twilio.owner_mobile` | Type: String | Required: For SMS alerts (Modules 02, 03) | Format: E.164 format.

**CFG-012** — `twilio.whatsapp_from` | Type: String | Required: For WhatsApp | Format: `"whatsapp:+14155238886"` (Twilio sandbox or provisioned number). If not prefixed with `"whatsapp:"`, the core library will prepend it.

### 6.6 Slack Configuration

**CFG-013** — `slack.webhook_url` | Type: String | Required: No | Default: Absent or `"YOUR_SLACK_WEBHOOK_URL_HERE"`. If contains `"YOUR_"` or is absent, Slack calls are skipped with a log warning.

### 6.7 Business Configuration

**CFG-014** — `business.name` | Type: String | Required: Yes | Used in AI prompts, email sign-offs, and chatbot system prompts.

**CFG-015** — `business.google_review_link` | Type: String | Required: For Module 04 | Format: Google review URL.

**CFG-016** — `business.owner_name` | Type: String | Required: Should | Used in personalised AI prompt context.

**CFG-017** — `business.owner_mobile` | Type: String | Required: For Module 03 SMS | E.164 format.

**CFG-018** — `business.booking_link` | Type: String | Required: No | Used in appointment and chatbot responses.

**CFG-019** — `business.website` | Type: String | Required: No | Used in email footers.

**CFG-020** — `business.postcode` | Type: String | Required: For Module 30 | UK postcode, e.g. `"LS1 4AP"`. Used to filter Land Registry results.

**CFG-021** — `business.council_planning_url` | Type: String | Required: For Module 28 | URL of the local council planning search portal.

**CFG-022** — `business.type` | Type: String | Required: No | Industry type hint, e.g. `"trades"`. Used by some modules to tune AI prompts.

### 6.8 Settings

**CFG-023** — `settings.check_every_seconds` | Type: Integer | Required: Yes | Default: 300 | Minimum: 60 | Description: Poll interval in seconds for all polling-mode modules.

**CFG-024** — `settings.archive_folder` | Type: String | Required: For Module 01 | Default: `"gaos_archive"` | Description: Relative or absolute path to the directory where PDF invoices are archived.

**CFG-025** — `settings.heartbeat_file` | Type: String | Required: No | Default: `"gaos_heartbeat.json"` | Description: Path to the heartbeat file written each poll cycle.

**CFG-026** — `settings.auto_restart_hours` | Type: Integer | Required: No | Default: 24 | Description: Interval after which the process orchestrator restarts itself to prevent memory accumulation.

**CFG-027** — `settings.alert_after_consecutive_failures` | Type: Integer | Required: No | Default: 3 | Description: Number of consecutive module failures before sending an owner alert.

**CFG-028** — `settings.cost_tracking_enabled` | Type: Boolean | Required: No | Default: `true` | Description: Whether to write rows to Usage_Log on every AI call.

**CFG-029** — `settings.ai_failover_alert` | Type: Boolean | Required: No | Default: `true` | Description: Whether to send an alert when AI failover occurs.

### 6.9 Server Configuration

**CFG-030** — `server.port` | Type: Integer | Required: For Zone 5 | Default: 8080 | Description: Port on which `gaos_server.py` listens in development mode.

**CFG-031** — `server.public_url` | Type: String | Required: For Module 24 (voice) | Format: HTTPS URL, e.g. `"https://your-gaos-server.up.railway.app"` | Description: The publicly accessible URL of the Flask server. Used to construct the `action` attribute of TwiML `<Gather>` elements for the voice callback.

### 6.10 Active Roles

**CFG-032** — `active_roles` | Type: Array of Strings | Required: No | Description: Optional list of active role keys for informational use by Module 35 (Chief of Staff) to determine which data sources to include in briefings. Valid values: `"admin"`, `"sales"`, `"finance"`, `"receptionist"`, `"marketer"`, `"intelligence"`.

---

## 7. Error Handling Requirements

### 7.1 Circuit Breaker Specification

**ERR-001** — Each AI provider SHALL have exactly one independent `_CircuitBreaker` instance. Circuit breaker state is process-local and is not persisted to disk or Sheets.

**ERR-002** — Circuit breaker thresholds:

| Provider | Failure Threshold | Cooldown (seconds) |
|----------|------------------|--------------------|
| DeepSeek | 5 | 600 |
| Groq | 5 | 300 |

**ERR-003** — A circuit breaker failure SHALL be triggered by any of: HTTP non-2xx response; `requests.exceptions.Timeout`; `requests.exceptions.ConnectionError`; `json.JSONDecodeError` on the response body; `KeyError` when accessing `choices[0]`.

**ERR-004** — A circuit breaker success SHALL be triggered only when a full, parseable response is received from the provider.

**ERR-005** — When a circuit breaker transitions to `"open"`, a WARNING log entry SHALL be written. When it transitions from `"open"` or `"half-open"` to `"closed"`, an INFO log entry SHALL be written.

### 7.2 Module-Level Retry Policy

**ERR-006** — The `ask_deepseek` fallback (direct call, used when `gaos_ai` is not importable) SHALL retry up to 3 times with exponential backoff: attempt 1 immediately, attempt 2 after 1 second, attempt 3 after 2 seconds.

**ERR-007** — Module action functions SHALL NOT implement their own retry loops for AI calls. Retry logic is the responsibility of `gaos_ai.py`. Module code SHALL treat a returned empty dict or empty string as a handled failure.

**ERR-008** — Sheets operations (read, append, update) SHALL NOT retry automatically. Transient Sheets API failures will manifest as empty results or silent no-ops in the current poll cycle. The next poll cycle provides implicit retry.

### 7.3 Alert Conditions

**ERR-009** — The system SHALL alert the owner after `settings.alert_after_consecutive_failures` (default 3) consecutive poll cycles in which the same module raises an unhandled exception. The alert SHALL be sent via `core.gmail_send` to `gmail.alert_email`.

**ERR-010** — The system SHALL log a WARNING when AI failover from DeepSeek to Groq occurs. If `settings.ai_failover_alert` is `true`, it SHALL additionally send a notification to the owner.

**ERR-011** — Module 29 (Gazette Monitor) SHALL send an immediate email alert when an insolvency or strike-off match is found. This is not an error condition but an urgent business alert. The alert email SHALL include the matched company name, the matched known contact, and actionable next steps.

### 7.4 Fallback Behaviour

**ERR-012** — When `core.connect_gmail()` returns `None` (e.g. missing `credentials.json`), modules that depend on Gmail SHALL log an ERROR at startup and exit their `run()` function. The `run_loop` will not be entered.

**ERR-013** — When `core._get_sheets_client()` returns `None`, all Sheets operations SHALL return empty lists or silently no-op. Modules will behave as if all tabs are empty.

**ERR-014** — When Module 22, 23, or 24 is unavailable (import error), the Flask server SHALL return HTTP 503 for `/chat` and a TwiML fallback message for `/whatsapp`, `/voice`, and `/voice/handle`. The server SHALL continue serving all other routes.

**ERR-015** — When `extract_pdf_text` returns `""` (scanned PDF or pdfplumber failure), Module 01 SHALL mark the email as read, log a WARNING, and return `False`. No data SHALL be written to Sheets for that email.

### 7.5 Logging Standards

**ERR-016** — `ERROR` level SHALL be used for: exceptions that prevent processing of a specific item (email, row, etc.); failed external API calls; missing required configuration.

**ERR-017** — `WARNING` level SHALL be used for: circuit breaker state changes; unexpected but recoverable data conditions (empty email body, unparseable date); Twilio or Slack skipped due to placeholder config; fallback to secondary AI provider.

**ERR-018** — `INFO` level SHALL be used for: successful completion of processing steps; scheduled task execution; startup messages.

**ERR-019** — `DEBUG` level MAY be used for verbose intermediate state during development. DEBUG messages SHALL NOT appear in production logs at the default INFO level.

---

## 8. Security Requirements

### 8.1 Secret Storage

**SEC-001** — No API key, OAuth token, auth token, or password SHALL appear in any Python source file, whether as a literal string, constant, or default parameter value.

**SEC-002** — `config.json` SHALL be listed in `.gitignore` in the project root. If `config.json` is detected in version control, it SHALL be considered a security defect.

**SEC-003** — `token.json`, `credentials.json`, and `service_account.json` SHALL be listed in `.gitignore`. These files SHALL never be committed to version control.

**SEC-004** — In production deployments, all secrets SHALL be injected via environment variables rather than `config.json`. The following environment variables SHALL be recognised: `DEEPSEEK_API_KEY`, `GROQ_API_KEY`. Additional secrets MAY be injected using the dot-path convention (e.g. `TWILIO_ACCOUNT_SID` for `twilio.account_sid`).

### 8.2 OAuth Token Lifecycle

**SEC-005** — The Gmail OAuth2 flow SHALL use the `InstalledAppFlow.run_local_server(port=0)` method, which opens a random local port for the OAuth callback. This method SHALL only be invoked when no valid `token.json` exists.

**SEC-006** — `token.json` SHALL be written using standard Python file I/O (`open` with `"w"` mode). It SHALL not be written to any network location.

**SEC-007** — Expired OAuth tokens SHALL be refreshed using `credentials.refresh(google.auth.transport.requests.Request())`. If the refresh token is expired or revoked, the system SHALL log an ERROR and return `None` from `connect_gmail()`. Manual re-authorisation (deletion of `token.json` and re-run) will be required.

**SEC-008** — The Gmail OAuth scopes SHALL be exactly: `["https://www.googleapis.com/auth/gmail.modify", "https://www.googleapis.com/auth/gmail.compose"]`. No other Gmail or Google API scopes SHALL be requested.

**SEC-009** — The Google Sheets/Drive OAuth scopes SHALL be exactly: `["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]`. These are required by the `gspread` library for read/write access.

### 8.3 API Key Validation

**SEC-010** — Before registering any AI provider, the `_AIManager._build()` method SHALL check whether the resolved API key starts with `"YOUR_"`. Such keys SHALL be treated as absent; the provider SHALL NOT be added to the active list.

**SEC-011** — Before making any Twilio API call, the system SHALL check whether `account_sid` contains the substring `"YOUR_"`. If so, the call SHALL be silently skipped and a WARNING logged. This check SHALL be performed inline in each Twilio call site in `gaos_core.py` and in module code.

### 8.4 HTTP Security

**SEC-012** — All outbound HTTP requests made by the system SHALL use HTTPS. The `requests` library's default TLS verification SHALL NOT be disabled (`verify=False` SHALL NOT appear in any production code).

**SEC-013** — The Flask development server (`app.run`) SHALL use `debug=False`. Flask debug mode SHALL NOT be enabled in any deployment.

**SEC-014** — The Flask server does not implement Twilio webhook signature verification in this version. The operator SHOULD restrict Twilio webhook endpoints to Twilio IP ranges at the network/proxy level. Twilio signature verification (using `twilio.request_validator.RequestValidator`) is a SHOULD requirement for future versions.

### 8.5 Data Handling

**SEC-015** — Email body content submitted to AI providers SHALL be truncated to the minimum required length for the specific module's task (Module 01: 4,000 chars; Module 02: 2,000 chars; Module 03: 1,500 chars). This reduces personal data exposure in API requests.

**SEC-016** — The `detail` field written to `Actions_Log` SHALL be truncated to 250 characters. No full email bodies, attachment content, or credential values SHALL appear in the Actions_Log.

**SEC-017** — Conversation history for Modules 22, 23, and 24 SHALL be stored in process memory only. Conversation history SHALL NOT be written to Google Sheets in full. Only extracted lead details (name, email, interest) from chatbot conversations SHALL be written to `Lead_Log`.

---

## 9. Deployment Requirements

### 9.1 Supported Environments

**DEPLOY-001** — The system SHALL support deployment on Railway.app using the configuration defined in `deploy/railway.toml`.

**DEPLOY-002** — The system SHALL support deployment on any Linux VPS or cloud instance using the systemd service unit defined in `deploy/gaos.service`.

**DEPLOY-003** — The system SHALL support Oracle Cloud Always Free tier instances (1 OCPU, 1 GB RAM, Ubuntu 22.04 LTS or later).

**DEPLOY-004** — Local development SHALL be supported on macOS, Windows, and Linux with Python 3.11+ installed.

### 9.2 Resource Minimums

**DEPLOY-005** — Minimum RAM: 512 MB for a single-role deployment. Recommended: 1 GB for Full Team deployment (34 concurrent processes).

**DEPLOY-006** — Minimum disk: 1 GB for code, dependencies, and PDF archive. The `gaos_archive` directory size is proportional to invoice volume.

**DEPLOY-007** — Minimum CPU: 1 vCPU. The system is primarily I/O-bound (network calls to APIs). CPU usage should remain below 10% average on a 1 vCPU instance.

### 9.3 Dependency Installation

**DEPLOY-008** — All Python dependencies SHALL be installable via `pip install -r requirements.txt` using the pinned versions in `requirements.txt`. The required packages and their pinned versions are:

| Package | Version |
|---------|---------|
| requests | 2.31.0 |
| pdfplumber | 0.10.3 |
| gspread | 6.0.2 |
| google-auth | 2.29.0 |
| google-auth-oauthlib | 1.2.0 |
| google-auth-httplib2 | 0.2.0 |
| google-api-python-client | 2.126.0 |
| flask | 3.0.2 |
| gunicorn | 21.2.0 |
| psutil | 5.9.8 |

**DEPLOY-009** — Python runtime version SHALL be 3.11.x as specified in `deploy/runtime.txt`.

### 9.4 Startup Sequence

**DEPLOY-010** — The required startup sequence for a complete GAOS™ deployment SHALL be:

1. Install Python dependencies (`pip install -r requirements.txt`).
2. Place `credentials.json` (Google OAuth desktop client) in the project root.
3. Place `service_account.json` (Google service account key) in the project root, OR complete the Gmail OAuth flow to generate `token.json`.
4. Copy `config.example.json` to `config.json` and populate all required fields.
5. Run `python gaos_install.py --pack <industry>` to provision the Google Sheets data layer.
6. Start the polling modules: `python gaos_launcher.py <role>` or `python gaos_launcher.py full_team`.
7. If Zone 5 modules (22, 23, 24) are included in the active tier, start the web server separately: `gunicorn gaos_server:app` or `python gaos_server.py`.
8. Configure Twilio webhook URLs to point to `{server.public_url}/whatsapp` and `{server.public_url}/voice`.

**DEPLOY-011** — Steps 6 and 7 SHALL be independent processes. On Railway.app, `gaos_server.py` is the primary process (start command: `gunicorn gaos_server:app`). The polling launcher SHALL be started as a separate worker process or service.

### 9.5 Railway.app Configuration

**DEPLOY-012** — The `deploy/railway.toml` file SHALL specify: `builder = "NIXPACKS"`, `startCommand = "gunicorn gaos_server:app"`, `restartPolicyType = "ON_FAILURE"`, `restartPolicyMaxRetries = 10`.

**DEPLOY-013** — On Railway.app, all secrets SHALL be configured as Railway environment variables (not in `config.json`). The Railway deployment SHALL not contain `config.json` in version control.

**DEPLOY-014** — Railway.app health checks SHALL target `GET /health` on the configured public port. The `/health` endpoint SHALL respond within 2 seconds for the deployment to be considered healthy.

### 9.6 Linux systemd Configuration

**DEPLOY-015** — The `deploy/gaos.service` systemd unit file SHALL specify: `Type=simple`, `ExecStart=/usr/bin/python3 gaos_launcher.py full_team` (or the appropriate role), `Restart=always`, `RestartSec=10`, `WorkingDirectory=/home/ubuntu/gaos` (or the actual installation path), `User=ubuntu` (or appropriate non-root user).

**DEPLOY-016** — The systemd service SHALL be enabled to start on boot via `systemctl enable gaos`.

**DEPLOY-017** — On Oracle Cloud Always Free or Linux VPS deployments, `gaos_server.py` SHALL be run as a separate systemd service or under a process manager (e.g. `supervisor`), distinct from the polling launcher service.

**DEPLOY-018** — The deployment user SHALL have read/write access to the project directory, the `gaos_archive` subdirectory, `config.json`, `token.json`, and `gaos_heartbeat.json`. It SHALL NOT require root privileges.

### 9.7 First-Run Gmail OAuth

**DEPLOY-019** — On the first run in an environment without a valid `token.json`, `connect_gmail()` will attempt to open a browser for OAuth authorisation. In headless server environments, this will fail. The operator SHALL: complete the OAuth flow on a machine with a browser; copy the generated `token.json` to the server; ensure the server has no write permission to `credentials.json` (to prevent re-triggering the flow).

**DEPLOY-020** — The generated `token.json` contains a refresh token that is valid indefinitely (until manually revoked in the Google Cloud Console). The system will automatically refresh the access token before expiry without requiring re-authorisation.

---

*End of GAOS™ Low-Level System Requirements — v3.3*  
*Document ID: GAOS-LLSR-3.3 | Aether Frameworks Ltd*

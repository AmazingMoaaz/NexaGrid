<h1 align="center">
  <img src="assets/nexagrid-logo.svg" alt="NexaGrid" width="520">
</h1>

<p align="center">
  <b>Three services that run your backend from one box.</b><br>
  A Flask API that ingests and fixes broken JSON, a file receiver that accepts anything you throw
  at it, and a remote operations console with a Go agent that phones home every three seconds.<br>
  Each one deploys on its own, talks plain HTTP, and logs everything.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.8%2B-3776AB?logo=python&logoColor=white" alt="Python 3.8+">
  <img src="https://img.shields.io/badge/Go-1.18%2B-00ADD8?logo=go&logoColor=white" alt="Go 1.18+">
  <img src="https://img.shields.io/badge/Flask-2.x-000000?logo=flask&logoColor=white" alt="Flask">
  <img src="https://img.shields.io/badge/cloud-none-lightgrey" alt="No cloud">
</p>

---

## 📍 At a glance

| | | |
| :-: | --- | --- |
| 📡 | **API Gateway** | <http://sisi.datacenter-eg.site> — JSON ingestion and file writes, port `8585` |
| 📦 | **Vault** | <http://up.datacenter-eg.site> — file uploads and downloads, port `8787` |
| 🖥️ | **Remote Console** | <http://weza.datacenter-eg.site> — command execution from the browser, port `8000` |
| 🤖 | **Agent** | A compiled Go binary that runs on the target, polls the console, executes, reports back |
| ☁️ | **Cloud** | None. Everything stays on your infrastructure |

---

## 🧩 What's inside

| | Part | What it does | Runs on |
| :-: | --- | --- | --- |
| 📡 | **NexaGrid API** | Receives JSON payloads, auto-repairs malformed ones, logs every request with full metadata, reads and writes files on command. Comes with its own health endpoint. | Any server with Python + Flask |
| 📦 | **NexaGrid Vault** | Accepts file uploads in any format — JSON with base64, multipart form-data, raw binary — hashes every file for integrity, sanitises filenames, deduplicates collisions, and serves files back. | Any server with Python |
| 🖥️ | **NexaGrid Remote** | A web console that queues commands and a relay server that brokers them to the agent. Open it in a browser, type a command, get the output back. No SSH, no VPN, no port forwarding. | Any server with Python |
| 🤖 | **NexaGrid Agent** | A single Go binary. It connects out to the relay, polls every 3 seconds, executes whatever arrives (CMD, PowerShell, or `/bin/sh`, auto-detected), and sends back the output plus the machine's hostname, user, and OS. | The target machine |

### 🗺️ How it fits together

```text
  📦 Any client ──POST──▶ 📡 NexaGrid API (:8585)       stores to data.txt, logs to requests.json
                                                          reads back file content in every response

  📤 Any client ──POST──▶ 📦 NexaGrid Vault (:8787)      saves to received Files/, returns hash + URL
                 ◀──GET──  /files/<name>                  serves files back with correct MIME type

  🖥️ Browser ──cmd──▶ 🔄 Relay Server (:8000) ◀──poll── 🤖 Agent (target)
       │                      │                              │
       │   POST /api/send     │     GET /api/get             │
       │                      │                              │
       └── GET /api/response ◀┘◀── POST /api/response ──────┘
```

The agent never accepts incoming connections: it dials out to the relay and keeps polling.
The relay queues commands and holds responses until the browser picks them up. No browser has
to stay open for the agent to keep running.

---

## 📡 NexaGrid API

- 🔗 **Endpoints.** `POST /sisi` ingests JSON and stores every request in `requests.json`.
  `POST /send` writes arbitrary content to `data.txt` and returns its contents as plain text.
  `GET /health` is a liveness probe. `GET /` returns the full endpoint catalogue with feature list.
- 🔧 **JSON repair.** Payloads with unquoted keys (`{name: "value"}`) or bare array values
  (`{"list":[one,two,three]}`) are auto-fixed before processing. The original and fixed versions
  are both logged.
- 📋 **Audit trail.** Every request is logged with timestamp, endpoint, method, client IP,
  User-Agent, payload size, and response status — both to a rotating log file (10 MB, 5 backups)
  and to `requests.json` as newline-delimited JSON.
- 📄 **File content in responses.** Every successful response includes the current contents of
  `data.txt`, its filename, and its size, so the caller always knows what's on disk.
- 🛡️ **Error handling.** HTTP exceptions and unhandled errors both return a standardised JSON
  envelope with error code, description, timestamp, and API version. Nothing leaks a stack trace.

## 📦 NexaGrid Vault

- 📤 **Upload anything.** JSON body with a `file` field (text or base64), multipart form-data with
  one or more files, or raw bytes with no content type at all. The server figures it out.
- 🏷️ **Filename preservation.** The original filename is kept, sanitised (path separators and
  dangerous characters stripped), and if a collision exists, a counter suffix is added:
  `report.pdf` → `report_1.pdf`. The response includes both the original and saved names.
- 🔐 **Integrity.** Every file gets an MD5 hash at upload time, returned in the response and sent
  as an `X-File-Hash` header on download. The caller can verify nothing was altered.
- 📊 **File info.** MIME type detected automatically, binary vs text classification, encoding,
  and a content preview (first 100 characters for text, byte count for binary) in the response.
- 🆔 **Request tracking.** Every upload gets a unique 8-character request ID, returned in the
  response and as an `X-Request-ID` header. Errors include it too.
- 📥 **Downloads.** `GET /files/<filename>` serves the file with the correct MIME type and a
  `Content-Disposition: attachment` header. Missing files return a JSON error with the filename.
- 📊 **Status.** `POST /status` returns the upload directory path, total file count, and a fresh
  request ID.

## 🖥️ NexaGrid Remote

- 🌐 **Web console.** Open the browser, type a command, hit Execute (or press Enter). The output
  appears in a scrollable terminal pane with timestamps on every line.
- ⚡ **Quick commands.** One-click buttons for `whoami`, `hostname`, `ipconfig`, `dir C:\`,
  `systeminfo`, and `net user`. They fill the input and fire immediately.
- 🔀 **Shell picker.** A dropdown next to the input: Auto (agent decides), CMD, or PowerShell.
  The agent honours the selection.
- 🟢 **Connection status.** The console polls `/api/status` every 3 seconds. A green bar means
  the agent has checked in within the last 15 seconds; red means it hasn't.
- 📋 **System info.** The agent sends its hostname, username, and OS with every response. The
  console shows them in the info bar at the top.
- ⏱️ **Timeout.** If no response arrives within 30 seconds, the console shows "Command timeout"
  instead of hanging.

### 🤖 The Agent

- 🖥️ **Cross-platform.** Runs on Windows and Linux. One binary, no dependencies, no install.
- 🧠 **Auto shell detection.** Commands containing `Get-`, `Invoke-`, or `$` go to PowerShell;
  everything else goes to CMD on Windows, `/bin/sh` on Linux. The dropdown override takes
  priority.
- 🔄 **3-second polling.** Lightweight GET requests. When there's no command, the agent gets an
  empty response and sleeps.
- 🔒 **TLS.** All traffic to the relay is HTTPS.
- 📡 **Beacon.** On startup, the agent sends a beacon with its hostname, user, and OS so the
  console knows it's alive before any command is sent.
- 🧱 **Resilient.** Network errors don't crash it. A failed poll returns an empty command and the
  loop continues.

---

## 🧰 Tech stack

| | Layer | Built with |
| :-: | --- | --- |
| 🐍 | **API** | Python 3.8+, Flask, `RotatingFileHandler` for logs, dataclasses for config |
| 🐍 | **Vault** | Python 3.8+, standard library only: `http.server`, `socketserver`, `mimetypes`, `hashlib` |
| 🐍 | **Relay** | Python 3.8+, standard library only: `http.server` with `ThreadingMixIn`, JSON files for state |
| 🌐 | **Console** | Plain HTML, CSS, JavaScript. No framework, no build step. Courier New and green-on-black |
| 🤖 | **Agent** | Go 1.18+, standard library only: `net/http`, `os/exec`, `crypto/tls`, `encoding/json` |
| 📂 | **Storage** | Flat files: `data.txt`, `requests.json`, `received Files/`, `data/commands.json`, `data/responses.json` |

---

## 📁 Project layout

```text
nexagrid/
├── 📡 API/
│   └── main.py                 the Flask API: JSON ingestion, file writes, logging
├── 📦 Receiver/
│   └── main.py                 the upload server: any format in, hashed files out
├── 🖥️ Shell/
│   ├── index.html              the web console: command input, output pane, status bar
│   ├── server.py               the relay: queues commands, holds responses, serves the UI
│   └── shell.go                the agent: polls, executes, reports back
├── 🎨 assets/
│   └── nexagrid-logo.svg       the project logo
└── 📝 README.md
```

---

## 🚀 Getting started

### 📡 Run the API

```bash
cd API
pip install flask
python main.py
# => NexaGrid API listening on 0.0.0.0:8585
```

The dashboard is then at `http://<server>:8585`. Send JSON to `/sisi`, write files with `/send`,
check health at `/health`.

### 📦 Run the Vault

```bash
cd Receiver
python main.py
# => NexaGrid Vault listening on 0.0.0.0:8787
```

Upload a file:

```bash
curl -X POST http://localhost:8787/upload \
  -H "Content-Type: application/json" \
  -d '{"filename": "hello.txt", "file": "Hello, NexaGrid!", "encoding": "text"}'
```

Download it back:

```bash
curl http://localhost:8787/files/hello.txt
```

### 🖥️ Run the Remote Console

```bash
# Start the relay
cd Shell
python server.py
# => NexaGrid Relay listening on 0.0.0.0:8000
```

Open `http://<server>:8000` in a browser. The console is ready, waiting for an agent.

### 🤖 Build and run the Agent

```bash
cd Shell
go build -o nexagrid-agent shell.go
./nexagrid-agent
```

The agent connects to the relay, sends a beacon, and starts polling. The console's status bar
turns green. Type a command and hit Execute.

On Windows, the agent auto-detects whether to use CMD or PowerShell. On Linux, it uses
`/bin/sh`.

---

## 📝 Notes

- ⚡ **The API repairs JSON before rejecting it.** If you send `{"names":[foo,bar,baz]}`, it
  becomes `{"names":["foo","bar","baz"]}` and processes normally. The original and fixed versions
  are both logged.
- 📂 **Vault filenames are sanitised but preserved.** `../../etc/passwd` becomes `______etc_passwd`.
  Collisions add a counter: `report.txt`, `report_1.txt`, `report_2.txt`.
- 🔄 **The relay uses flat JSON files, not a database.** Commands and responses are arrays in
  `data/commands.json` and `data/responses.json`. This is intentional: the relay is stateless
  enough to restart without losing anything that matters.
- 🖥️ **The console polls for 30 seconds, then gives up.** If the agent is slow, try again. The
  command is not lost — it stays in the queue until the agent picks it up.
- 🔒 **The agent skips TLS verification** (`InsecureSkipVerify: true`). This is for self-signed
  certs on internal infrastructure. For public deployments, replace with proper certificate
  validation.

---

## ⚠️ Usage policy

> [!CAUTION]
> NexaGrid Remote executes **real commands on real machines**.

- 🔐 **Deploy only on systems you own** or have explicit written authorisation to manage.
- 🧪 **Intended for** authorised penetration testing, security research, CTF competitions, and
  legitimate infrastructure administration.
- 🚫 **Not intended for** unauthorised access, exfiltration, or any use that violates applicable
  law.
- 💾 **Back up before deploying.** The agent executes whatever it receives. There is no undo.

---

<p align="center">
  <b>NexaGrid</b><br>
  <sub>Three services. One box. No cloud.</sub>
</p>

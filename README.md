# GAOS™ v3.0 — Ghost Assistant Operating System

A Python automation platform that runs as a **virtual team** for UK small businesses. 35 AI-powered modules handle admin, sales, finance, appointments, marketing, and business intelligence — autonomously, around the clock.

Built by **Aether Frameworks**.

---

## Virtual Roles

| Role | Modules | Price |
|---|---|---|
| Virtual Admin | Invoice Scanner, Contract Sender, FAQ Reply, Team Broadcaster, Document Chaser, Document Sentinel | £199/mo |
| Virtual Sales | Lead Catcher, Urgent Alert, Review Requester, Proposal Chaser, Pipeline Report | £199/mo |
| Virtual Finance | Payment Chaser, Daily Digest, Revenue Snapshot, Timesheet Summary, Invoice Generator, Expiry Alert | £249/mo |
| Virtual Receptionist | Appointment Reminder, No-Show Follow-Up, Website Chatbot, WhatsApp AI Agent | £299/mo |
| Virtual Marketer | Birthday Mailer, Social Scheduler, Re-Engagement Mailer, Newsletter Mailer, Review Monitor, Campaign Digest | £199/mo |
| Virtual Intelligence | GAOS Learn, Client Pulse, Planning Radar, Gazette Monitor, Land Registry Radar, Rate & Macro Pulse, AI Chief of Staff | £149/mo |
| AI Voice Agent | Answers inbound calls via Twilio | £99/mo add-on |
| **Full Team** | All 35 modules | **£999/mo** |

---

## Quickstart

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Google credentials

**Gmail** — download `credentials.json` from Google Cloud Console (OAuth2 Desktop App). On first run, GAOS opens a browser to authorise and saves `token.json` automatically.

**Google Sheets** — create a `service_account.json` (Service Account key) with Sheets Editor access on the target spreadsheet. Falls back to `token.json` if absent.

### 3. Configure
```bash
cp config.example.json config.json
# Fill in: DeepSeek API key, Google Sheet ID, Gmail addresses,
#          Twilio credentials, Slack webhook, business details
```

### 4. Run a role
```bash
python gaos_launcher.py admin          # Virtual Admin (6 modules)
python gaos_launcher.py sales          # Virtual Sales (5 modules)
python gaos_launcher.py finance        # Virtual Finance (6 modules)
python gaos_launcher.py receptionist   # Virtual Receptionist (4 modules)
python gaos_launcher.py marketer       # Virtual Marketer (6 modules)
python gaos_launcher.py intelligence   # Virtual Intelligence (7 modules)
python gaos_launcher.py full_team      # All 35 modules
python gaos_launcher.py module 08      # Single module a la carte
python gaos_launcher.py list           # Show all modules and pricing
```

### 5. Start the web server (for chatbot, WhatsApp, voice)
```bash
python gaos_server.py
# Production:
gunicorn gaos_server:app
```

---

## Conversational Modules (web server required)

| Module | Route | Description |
|---|---|---|
| 22 — Website Chatbot | `POST /chat` | AI chatbot on your website via embeddable widget |
| 23 — WhatsApp AI Agent | `POST /whatsapp` | Twilio webhook — AI replies to WhatsApp messages |
| 24 — AI Voice Agent | `POST /voice` + `/voice/handle` | Twilio webhook — AI answers inbound phone calls |

**Embed the chatbot widget on any webpage:**
```html
<script src="https://your-gaos-server.railway.app/widget.js"
        data-gaos-url="https://your-gaos-server.railway.app"
        data-business-name="Your Business Name">
</script>
```

---

## Google Sheet Tabs Required

Create one Google Sheet with these tabs (names configurable in `config.json`):

`Invoice_Log` · `Lead_Log` · `Completed_Jobs` · `Contract_Log` · `FAQ_Knowledge_Base` · `Appointments` · `Proposals` · `Pending_Documents` · `Clients` · `Social_Queue` · `Retainer_Clients` · `Licences` · `Timesheets` · `Chatbot_Knowledge` · `Sentinel_Actions` · `Newsletter_Queue` · `Reviews_Log` · `Campaign_Log` · `GAOS_Memory` · `Client_Pulse_Log`

---

## Deploy to Railway

See `deploy/FREE_SERVER_GUIDE.md` for full instructions.

The `deploy/railway.toml` and `deploy/Procfile` are pre-configured:
- `web` process: `gunicorn gaos_server:app` (chatbot, WhatsApp, voice)
- `worker` process: `python gaos_launcher.py full_team` (all polling modules)

---

## Tech Stack

- **AI**: DeepSeek (`deepseek-chat`, OpenAI-compatible API)
- **Email**: Gmail API (OAuth2)
- **Database**: Google Sheets via gspread
- **SMS / WhatsApp / Voice**: Twilio REST API
- **Team alerts**: Slack Incoming Webhooks
- **PDF parsing**: pdfplumber
- **Web server**: Flask + Gunicorn
- **Free public data**: UK Planning Portal, Land Registry Price Paid, Bank of England IADB, ONS CPI, London Gazette

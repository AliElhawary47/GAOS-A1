# GAOS™ Setup Guide — v3.3
### Ghost Assistant Operating System · Aether Frameworks
### Follow in order. Allow 30–40 minutes for full setup.

---

## What You Need

- A Windows, Mac, or Linux computer
- This `GAOS/` folder
- A Google account (for Gmail + Sheets)
- A DeepSeek account (primary AI — typically under £5/month)
- A Groq account (free fallback AI — no credit card required)
- Optional: Twilio account (for SMS / WhatsApp / Voice)
- Optional: Slack webhook (for team notifications)

---

## Step 1 — Install Python (5 min)

1. Go to https://www.python.org/downloads/
2. Download Python 3.11 or higher
3. Run the installer — **tick "Add Python to PATH"** before clicking Install
4. Verify:
   ```
   python --version
   ```
   Should show `Python 3.11.x` or higher.

---

## Step 2 — Install Dependencies (2 min)

Navigate to the GAOS folder:
```
cd Desktop/GAOS        (Mac/Linux)
cd Desktop\GAOS        (Windows)
```
Then run:
```
pip install -r requirements.txt
```

---

## Step 3 — Create Your Config (2 min)

1. Make a copy of `config.example.json`
2. Rename the copy to `config.json`
3. Open `config.json` — you will fill in values in the steps below.

---

## Step 4 — DeepSeek API Key (3 min)

**Primary AI provider. Typical cost: £2–5/month for a busy GAOS deployment.**

1. Go to https://platform.deepseek.com → sign up
2. API Keys → Create API Key → copy it (starts with `sk-`)
3. In `config.json`:
   ```json
   "deepseek": { "api_key": "sk-your-key-here" }
   ```

Alternatively, set as an environment variable:
```
export DEEPSEEK_API_KEY="sk-your-key-here"
```

---

## Step 5 — Groq API Key (3 min) — FREE FALLBACK

**This is your automatic backup. If DeepSeek goes down, Groq takes over immediately.**
Groq's free tier requires no credit card and is generous enough for a full GAOS deployment.

1. Go to https://groq.com → sign up (free, no credit card)
2. Go to https://console.groq.com/keys → Create API Key
3. Copy the key (starts with `gsk_`)
4. In `config.json`:
   ```json
   "groq": { "api_key": "gsk_your-key-here" }
   ```

**How failover works:**
- DeepSeek is your primary (higher quality, low cost)
- Groq is your automatic fallback (free, always ready)
- If DeepSeek goes down, GAOS switches to Groq with no interruption
- When DeepSeek recovers, the next call switches back automatically
- All 34 modules benefit automatically — no code changes required

---

## Step 6 — Connect Gmail (10 min)

### Part A — Enable the APIs
1. Go to https://console.cloud.google.com → sign in with your Gmail
2. Create a new project called **GAOS**
3. Search **Gmail API** → Enable
4. Search **Google Sheets API** → Enable
5. Search **Google Drive API** → Enable

### Part B — OAuth credentials (for reading email)
1. Credentials → Create Credentials → OAuth client ID
2. Configure consent screen: External · app name "GAOS" · add your Gmail as test user
3. Application type: **Desktop app** → Create
4. Download JSON → rename to `credentials.json`
5. Put it in the GAOS folder

### Part C — Service account (for writing to Sheets)
1. Credentials → Create Credentials → Service Account
2. Name it `gaos-sheets` → Create → Done
3. Click the service account → Keys → Add Key → JSON → Download
4. Rename to `service_account.json` → put in GAOS folder
5. Copy the service account email (`xxx@xxx.iam.gserviceaccount.com`)

### Part D — Fill config
```json
"gmail": {
  "watch_inbox": "your_gmail@gmail.com",
  "alert_email": "your_personal_email@gmail.com"
}
```

---

## Step 7 — Set Up Google Sheets (5 min)

1. In Google Drive, create a spreadsheet called **GAOS Data**
2. **Share** it with your service account email (from Step 6C) as Editor
3. Copy the Sheet ID from the URL:
   `docs.google.com/spreadsheets/d/ >>>COPY THIS<<< /edit`
4. In `config.json`:
   ```json
   "google_sheets": { "sheet_id": "PASTE_ID_HERE", ... }
   ```

The industry pack installer creates all required tabs automatically in the next step.

---

## Step 8 — Install an Industry Pack (3 min)

Choose the pack that matches the client's business:

```bash
python gaos_install.py --pack trades         # plumbers, builders, roofers
python gaos_install.py --pack legal          # solicitors, conveyancers
python gaos_install.py --pack clinic         # dental, physio, GP
python gaos_install.py --pack agency         # marketing, design, PR
python gaos_install.py --pack property       # estate agents, letting agents
python gaos_install.py --pack accountancy    # accountants, bookkeepers
```

This creates all sheet tabs, pre-populates the FAQ knowledge base, seeds licence/compliance items, and writes an industry-specific contract template.

---

## Step 9 — Twilio (Optional — SMS / WhatsApp / Voice)

Required for: Module 03 (Urgent Lead SMS), Module 10 (Appointment SMS), Module 23 (WhatsApp), Module 24 (Voice).

1. Go to https://www.twilio.com → sign up (free trial includes credit)
2. Buy a UK phone number from the console
3. Copy Account SID and Auth Token
4. Fill `config.json`:
   ```json
   "twilio": {
     "account_sid": "...",
     "auth_token":  "...",
     "from_number": "+44...",
     "owner_mobile": "+44..."
   }
   ```

Skip this step if you are only running invoice / lead / contract / FAQ modules.

---

## Step 10 — Slack (Optional — team notifications)

Required for: Module 07 (Team Broadcaster). Also used by: Module 13 (Daily Digest), Module 33 (negative review alerts).

1. Go to https://api.slack.com/apps → Create New App → From scratch
2. Incoming Webhooks → Activate → Add New Webhook to Workspace → pick a channel
3. Copy the webhook URL
4. In `config.json`:
   ```json
   "slack": { "webhook_url": "https://hooks.slack.com/services/..." }
   ```

---

## Step 11 — Fill Business Details

```json
"business": {
  "name":                 "Your Business Ltd",
  "google_review_link":   "https://g.page/r/...",
  "owner_name":           "Your Name",
  "owner_mobile":         "+44...",
  "booking_link":         "https://calendly.com/yourbusiness",
  "website":              "https://yourbusiness.co.uk",
  "postcode":             "LS1 4AP",
  "type":                 "trades"
}
```

---

## Step 12 — Run GAOS

### Full system (all roles):
```bash
python gaos_launcher.py full_team
```

### A specific role:
```bash
python gaos_launcher.py admin
python gaos_launcher.py sales
python gaos_launcher.py finance
python gaos_launcher.py intelligence
```

### A single module:
```bash
python gaos_launcher.py module 08
```

### List all modules:
```bash
python gaos_launcher.py list
```

**First run:** a browser window opens to approve Gmail access — click Allow. You will see each module start and begin watching.

**To stop:** press `Ctrl+C` — all modules shut down cleanly.

### Test it:
- **Module 01:** Email a PDF invoice to your watch inbox
- **Module 02/03:** Email yourself with "enquiry" in the subject
- **Module 04:** Add a row to `Completed_Jobs` with `Status = Completed`
- **Module 08:** Add a row to `Invoice_Log` with a date 15+ days ago and Status = unpaid — you should see `Chase Sent` updated to `Sent-1`. After 21+ days it will update to `Sent-2`, then `Sent-3` at 30+ days.
- **Module 06 FAQ gaps:** Send an email with a question that is not in your FAQ knowledge base — the question will be logged to the `FAQ_Gaps` sheet tab for review.
- **Module 21:** Add a row to `Clients` with a `Last Contact` date 90+ days ago. Set `Status` to `churned` and confirm the row is skipped; clear Status to confirm the re-engagement email sends.

---

## Step 13 — Web Server (Chatbot / WhatsApp / Voice)

The conversational modules (22, 23, 24) run on a separate Flask server.

In a separate terminal:
```bash
python gaos_server.py
```

Or for production (always-on):
```bash
gunicorn gaos_server:app --bind 0.0.0.0:8080
```

Embed the chatbot widget on any website:
```html
<script src="https://your-server.up.railway.app/widget.js"
        data-gaos-url="https://your-server.up.railway.app"
        data-business-name="Your Business"></script>
```

---

## Deploying Always-On

### Option A: Railway.app (recommended, free tier available)
1. Push the GAOS folder to a GitHub repo
2. Connect Railway to your repo → it reads `railway.toml` from the repository root
3. Set environment variables in the Railway dashboard (API keys etc.)

### Option B: Oracle Cloud Always Free (runs 10+ clients per VM)
```bash
sudo cp deploy/gaos.service /etc/systemd/system/
sudo systemctl enable gaos
sudo systemctl start gaos
sudo journalctl -fu gaos   # watch logs
```

### Option C: Any Linux VPS with systemd
Same commands as Option B.

See `deploy/FREE_SERVER_GUIDE.md` for the full Oracle Cloud walkthrough.

---

## File Structure After Setup

```
GAOS/
  config.json               ← your filled settings
  credentials.json          ← from Google (Step 6B)
  service_account.json      ← from Google (Step 6C)
  token.json                ← auto-created on first run
  gaos_heartbeat.json       ← auto-updated every poll cycle
  contract_template.txt     ← auto-generated by installer
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Module not found" | Run `pip install -r requirements.txt` |
| "config.json not found" | Copy `config.example.json` → `config.json` |
| "Sheet not found" | Check Sheet ID; share with service account? |
| "Invalid credentials" | Delete `token.json` and run again |
| "PDF text empty" | Scanned/image PDF — OCR not supported; invoice row is skipped and email marked read |
| "Duplicate invoice skipped" | Module 01 found an existing row with matching vendor+date or invoice number — normal if email was re-forwarded |
| "Chase not escalating" | Check that `Chase Sent` cell shows `Sent-1` / `Sent-2` not a legacy value — any value other than blank/no/sent-1/sent-2/sent-3 is treated as tier 1 |
| "DeepSeek errors" | Check API key + balance at deepseek.com. Groq fallback handles this automatically |
| "Groq failover active" | DeepSeek is down — Groq is covering. Normal. Check deepseek.com status |
| "Both providers failing" | Check both API keys in config.json |
| "High memory" | Normal — engine auto-restarts every 24 hours |

---

*Aether Frameworks Ltd — GAOS™ v3.3*

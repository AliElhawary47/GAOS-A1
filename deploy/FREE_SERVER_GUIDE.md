# GAOS™ Free 24/7 Server Deployment
### Run GAOS continuously at zero cost

---

## The Two Best Free Options

### Option A — Railway.app (Recommended for beginners)
**Why:** Deploy in 5 minutes from a browser. Works from an iPad.
**Cost:** Free — ~$0.30/month usage, well within the $5 free credit.
**Uptime:** 24/7 continuous, auto-restarts on failure.

### Option B — Oracle Cloud Always Free (Recommended for long-term)
**Why:** Genuinely free forever. No credit card surprises.
**Cost:** £0.00 forever. Oracle's Always Free tier never expires.
**Uptime:** 24/7 on a virtual machine you fully control.

---

## Option A: Deploy on Railway.app (15 mins, browser only)

### Step 1: Push code to GitHub
1. Go to github.com → sign in (or create free account)
2. Create a new repository called `gaos`
3. Upload all files from your `gaos/` folder (drag and drop)
4. NEVER include `config.json`, `token.json`, or `credentials.json` —
   they hold your real keys and are gitignored on purpose.
   Config goes in as environment variables (Step 3).

### Step 2: Connect to Railway
1. Go to railway.app → "Start a New Project"
2. Click "Deploy from GitHub repo"
3. Select your `gaos` repository
4. Railway uses `railway.toml` and starts the web server automatically

### Step 3: Add your config (environment variables)
In Railway dashboard → your service → Variables tab, add the variables
from `deploy/.env.example`:
- `GAOS_CONFIG_JSON` — the full contents of your config.json, one line
- `GAOS_TOKEN_JSON`  — contents of a token.json generated locally
- `GAOS_HEADLESS=1`
The code already reads these — no modification needed.

### Step 4: Add the worker service (the 30 polling modules)
Railway's start command only runs the **web server** (chatbot, WhatsApp,
voice). To also run the polling modules, add a second service:
1. Railway project → "+ New" → "GitHub Repo" → same `gaos` repository
2. In the new service → Settings → Start Command, set:
   `python gaos_launcher.py full_team`
3. Copy the same Variables onto this service
(Use `admin`, `sales`, `finance`, `receptionist`, `marketer`,
`intelligence`, or `module 08` instead of `full_team` to run a subset.)

### Step 5: Watch it run
- Railway dashboard shows live logs for both services
- You will see each module starting up
- Visit `https://your-app.up.railway.app/health` to confirm the web
  server is live

---

## Option B: Oracle Cloud Always Free VM (30 mins)

### Why Oracle is the better long-term choice
Oracle Cloud gives you a free ARM virtual machine with:
- 4 CPU cores
- 24 GB RAM
- 200 GB storage
- Truly free forever (not a trial)

This is enough to run multiple clients' GAOS installations simultaneously.

### Step 1: Create Oracle Cloud account
1. Go to cloud.oracle.com → "Start for Free"
2. Create an account (requires a credit card for identity verification — you will NOT be charged)
3. Choose "Always Free" resources only

### Step 2: Create your VM
1. In Oracle Console → Compute → Instances → Create Instance
2. Name: `gaos-server`
3. Image: Ubuntu 22.04 (Minimal)
4. Shape: VM.Standard.A1.Flex (Always Free — ARM)
   Set: 2 OCPUs, 12 GB RAM
5. Networking: create a new VCN, allow public IP
6. SSH keys: generate a key pair, download the private key
7. Click Create

### Step 3: Connect and set up
Open a terminal (or use the Oracle Cloud Shell — no SSH client needed):

```bash
# Connect to your VM
ssh -i your-private-key.key ubuntu@YOUR_VM_IP

# Update and install Python
sudo apt update && sudo apt install -y python3 python3-pip git

# Upload your GAOS files
# (easiest: use the GitHub method — clone your repo)
git clone https://github.com/YOURUSERNAME/gaos.git
cd gaos

# Install dependencies
pip3 install -r requirements.txt --break-system-packages

# Add your config
nano config.json
# Paste in your filled config.json content, save with Ctrl+X
```

### Step 4: Run GAOS as background services (systemd)
GAOS is two processes: the **launcher** (30 polling modules) and the
**web server** (chatbot, WhatsApp, voice). Ready-made unit files ship in
the repo's `deploy/` folder — install both so the whole product runs and
survives reboots:

```bash
# Install both unit files (edit User/WorkingDirectory if yours differ)
sudo cp deploy/gaos.service deploy/gaos-web.service /etc/systemd/system/

# Enable and start both
sudo systemctl daemon-reload
sudo systemctl enable --now gaos gaos-web

# Check they are running
sudo systemctl status gaos gaos-web

# Watch live logs
sudo journalctl -fu gaos
sudo journalctl -fu gaos-web
```

To run a single role instead of the full team, edit `ExecStart` in
`gaos.service` and replace `full_team` with `admin`, `sales`, `finance`,
`receptionist`, `marketer`, `intelligence`, or `module 08`.

### Managing multiple clients on Oracle
Each client gets their own folder and systemd service:
```
/home/ubuntu/
  gaos_client_1/   → gaos-client1.service
  gaos_client_2/   → gaos-client2.service
  gaos_client_3/   → gaos-client3.service
```

The ARM VM can comfortably run 10+ simultaneous GAOS installations
since GAOS is extremely lightweight (mostly sleeping between polls).

---

## Cost Summary

| Component | Cost |
|---|---|
| Railway.app hosting | Free ($5/month credit, GAOS uses ~$0.30) |
| Oracle Cloud VM | £0.00 forever |
| DeepSeek AI | Covered by client's £5/month token fee |
| Gmail / Google Sheets | Free (client's own account) |
| Twilio SMS | Client pays directly (~£0.04/SMS) |
| **Total to you** | **£0.00** |

---

## Recommended Path

1. **Start with Railway** — get your first client live in 15 minutes
2. **Move to Oracle** once you have 3+ clients — one VM hosts them all for free forever

---

*Aether Frameworks — GAOS™ v3.4*

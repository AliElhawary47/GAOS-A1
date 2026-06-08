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
4. Make sure `config.json` (with your real keys) is included
   OR use Railway environment variables (see Step 3)

### Step 2: Connect to Railway
1. Go to railway.app → "Start a New Project"
2. Click "Deploy from GitHub repo"
3. Select your `gaos` repository
4. Railway detects the `Procfile` and starts automatically

### Step 3: Add your config (two options)

**Option A — Upload config.json directly (easiest)**
Simply make sure `config.json` is in your GitHub repo.

**Option B — Use Railway Variables (more secure)**
In Railway dashboard → your project → Variables tab:
- Add each key from config.json as an environment variable
- Then modify `gaos_core.py` to read from `os.environ` for sensitive keys

### Step 4: Watch it run
- Railway dashboard shows live logs
- You will see each module starting up
- Accessible from your iPad browser at any time

### Changing the tier
In Railway → Settings → Start Command:
Change `enterprise` to `core`, `pro`, or `module 01` etc.

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

### Step 4: Run GAOS as a background service (systemd)
This makes GAOS start automatically when the server reboots.

```bash
# Create a systemd service file
sudo nano /etc/systemd/system/gaos.service
```

Paste this:
```ini
[Unit]
Description=GAOS Ghost Assistant Operating System
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/gaos
ExecStart=/usr/bin/python3 gaos_launcher.py enterprise
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable gaos
sudo systemctl start gaos

# Check it is running
sudo systemctl status gaos

# Watch live logs
sudo journalctl -fu gaos
```

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

*Aether Frameworks — GAOS™ v2.0*

# GAOS™ v3.4 — Ghost Assistant Operating System
### Aether Frameworks Ltd

A modular business automation platform that watches a client's email, runs AI on what it sees, and executes back-office actions automatically — 24 hours a day, without staff. No per-seat licence. Client owns the system.

**v3.3 adds:** Escalating payment-chase tiers (14/21/30-day, Sent-1/2/3) with early threshold for known late payers, duplicate-send guard on all chasers, AI lead scoring (Hot/Warm/Cold), sequential invoice numbers (INV-YYYYMM-NNN), invoice deduplication and anomaly flagging, FAQ gap logging to `FAQ_Gaps`, reschedule-request detection in appointment reminders, Daily Digest Slack delivery, Slack negative-review alerts, churn-status exclusion in re-engagement mailer, danger-signal cross-referencing in Client Pulse, and GAOS_Memory injection across all Chief of Staff prompts.

**v3.4 adds:** Unified sheet schemas across all 34 modules (the installer headers are now the single source of truth), send-failure detection (no more lost or duplicate emails/SMS), duplicate-send guards on all mailers, fixed external data feeds (Gazette, Land Registry, BoE, ONS), automatic AI usage logging to `Usage_Log`, AI provider status on `/health`, and core system tabs auto-created by the installer.

**v3.2 adds:** AI provider failover (DeepSeek → Groq free tier), module consolidation (35→34 modules), `run_loop` / `should_run_at` helpers, unified chaser, monthly cost reporting, and industry pack installer.

---

## Virtual Team Model

Six role-based subscription bundles. Mix and match — no forced tiers.

| Role | Price | Modules | What it does |
|------|-------|---------|--------------|
| **Virtual Admin** | £199/mo | 01 05 06 07 08 27 | Invoices, contracts, FAQ, documents |
| **Virtual Sales** | £199/mo | 02 03 04 08 15 | Leads, proposals, reviews, pipeline |
| **Virtual Finance** | £249/mo | 08 13 14 16 19 20 36 | Chasing, reports, invoicing, costs |
| **Virtual Receptionist** | £299/mo | 10 12 22 23 | Appointments, chatbot, WhatsApp |
| **+ AI Voice Agent** | +£99/mo | 24 | Inbound phone handling (add-on) |
| **Virtual Marketer** | £199/mo | 17 18 21 32 33 34 | Social, newsletter, reviews, re-engagement |
| **Virtual Intelligence** | £149/mo | 25 26 28 29 30 31 35 | Business memory, market radar, briefings |
| **Full Team** | **£999/mo** | All 34 modules | Everything — save £394/mo vs individual |

**Setup fees:** £400 (1 role) · £900 (2–3 roles) · £1,600 (Full Team)

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure
cp config.example.json config.json
# edit config.json — fill in DeepSeek key, Groq key (free), Gmail, Sheets IDs

# 3. Install an industry pack (creates all sheet tabs + pre-populates FAQs)
python gaos_install.py --pack trades   # or legal / clinic / agency / property / accountancy

# 4. Run the full system
python gaos_launcher.py full_team

# 5. Run a single role
python gaos_launcher.py finance

# 6. Run a single module
python gaos_launcher.py module 08
```

First run opens a browser once to approve Gmail access. See **docs/SETUP.md** for the complete walkthrough.

---

## Industry Packs

Pre-configured setups for six verticals. Installed in under a minute.

| Pack | Target businesses | Key extras |
|------|------------------|------------|
| `trades` | Plumbers, electricians, builders, roofers | Gas Safe licences, trade FAQ, material quotes |
| `legal` | Solicitors, conveyancers, paralegals | Case log, deadline tracker, SRA compliance |
| `clinic` | GP practices, dentists, physio | Patient recalls, CQC, appointment-heavy |
| `agency` | Marketing, design, PR firms | Retainer billing, social scheduling |
| `property` | Estate agents, letting agents | Property listings, viewings, landlord compliance |
| `accountancy` | Accountants, bookkeepers, tax advisors | Tax deadlines, MTD, recurring billing |

Each pack includes: pre-populated FAQ knowledge base, licence-expiry seed data, industry-specific contract template, and correct sheet tab names.

---

## The 34 Modules

### Zone 1 — React (email-triggered, every poll)
| # | Module | What it does |
|---|--------|-------------|
| 01 | Invoice Scanner | Extracts data from PDF invoices; deduplicates; flags anomalies; logs to Sheets |
| 02 | Lead Catcher | Detects enquiry emails; scores lead Hot/Warm/Cold; drafts reply; pings owner on WhatsApp |
| 03 | Urgent Lead Alert | High-value leads → instant SMS to owner |
| 04 | Review Requester | Sends review link after completed jobs |
| 05 | Contract Sender | Auto-generates and emails service agreements |
| 06 | FAQ Auto-Reply | Drafts replies to common questions; logs unanswered gaps to FAQ_Gaps |
| 07 | Team Broadcaster | Centralised Slack / email team notifications with payment amount extraction |

### Zone 2 — Chase (condition-driven, every poll)
| # | Module | Threshold |
|---|--------|----------|
| 08 | Unified Item Chaser | Payments (14/21/30d escalating tiers) · Proposals (5d) · Documents (3d) — early chase for known late payers |
| 10 | Appointment Reminder | 24h + 2h before; detects client reschedule requests |
| 12 | No-Show Follow-Up | Day-of missed appointments |

### Zone 3 — Report (timed)
| # | Module | Schedule |
|---|--------|---------|
| 13 | Daily Digest | Daily 08:00 — also delivers to Slack if configured |
| 14 | Weekly Revenue Snapshot | Monday 08:00 |
| 15 | Lead Pipeline Report | Friday 17:00 |
| 16 | Staff Timesheet Summary | Friday 18:00 |

### Zone 4 — Schedule (timed)
| # | Module | Schedule |
|---|--------|---------|
| 17 | Birthday & Anniversary Mailer | Daily 09:00 |
| 18 | Social Post Scheduler | Every poll |
| 19 | Monthly Invoice Generator | 1st of month 08:00 — sequential invoice numbers (INV-YYYYMM-NNN) |
| 20 | Licence & Expiry Alert | Daily 09:00 |
| 21 | Re-Engagement Mailer | Monday 10:00 — skips churned/inactive/do-not-contact clients |

### Zone 5 — Converse (Flask server, webhook-driven)
| # | Module | Description |
|---|--------|------------|
| 22 | Website Chatbot | Embeddable AI chat widget |
| 23 | WhatsApp AI Agent | Two-way WhatsApp conversations |
| 24 | AI Voice Agent | Inbound phone calls (Voice add-on) |

### Zone 6 — Learn (timed)
| # | Module | Schedule |
|---|--------|---------|
| 25 | GAOS Learn | Monday 07:00 — adaptive business memory; learns chase rate and appointment peak time |
| 26 | Client Pulse | Monday 07:30 — silence-gap radar; cross-references with unpaid invoices for danger signals |
| 27 | Document Sentinel | Every poll — compliance document watch |
| 28 | Planning Radar | Monday 08:00 — nearby planning applications |

### Zone 0 — Sense (external data)
| # | Module | Schedule |
|---|--------|---------|
| 29 | Gazette Monitor | Daily 07:00 — insolvency & estate notices |
| 30 | Land Registry Radar | Monday 09:00 — new property sales = leads |
| 31 | Rate & Macro Pulse | Daily 12:00 + 1st of month — BoE rate + ONS CPI |

### Zone 7 — Marketer
| # | Module | Schedule |
|---|--------|---------|
| 32 | Newsletter Mailer | First Monday of month 09:00 |
| 33 | Review Monitor | Every poll — negative reviews alert via email, SMS, and Slack |
| 34 | Campaign Digest | Friday 17:00 |

### Zone 8 — Chief of Staff
| # | Module | Schedule |
|---|--------|---------|
| 35 | AI Chief of Staff | Daily 07:30 briefing + Monday 07:45 weekly summary — memory-injected prompts; danger-signal detection |

### Zone 9 — Utility
| # | Module | Schedule |
|---|--------|---------|
| 36 | Cost Rollup Reporter | 1st of month 09:00 — AI cost + margin report |

---

## AI Failover

GAOS uses two AI providers with automatic failover so AI features never go dark:

```
core.ask_deepseek() / core.chat_deepseek()
          │
          ▼
      gaos_ai.py
          │
          ├── DeepSeek (primary)   deepseek-chat, ~£2–5/month
          │       Circuit breaker: 5 failures → 10-min cooldown
          │
          └── Groq (fallback)      llama-3.3-70b, FREE TIER
                  Circuit breaker: 5 failures → 5-min cooldown
```

All 34 modules inherit failover automatically — zero code changes needed.
Add your free Groq key at `groq.com` → paste into `config.json` under `"groq": { "api_key": "gsk_..." }`.

---

## File Structure

```
GAOS/
  gaos_core.py           — Shared runtime: Gmail, Sheets, AI, Twilio, scheduling
  gaos_ai.py             — AI Provider Manager: DeepSeek + Groq failover
  gaos_launcher.py       — Role definitions, module registry, CLI entry point
  gaos_server.py         — Flask server: chatbot, WhatsApp, voice webhooks
  gaos_install.py        — Industry pack installer
  industry_packs.json    — 6 industry configurations (FAQ + licences + contracts)
  config.example.json    — Config template (copy to config.json)
  contract_template.txt  — Contract template (rewritten by the installer)
  requirements.txt       — Python dependencies
  Procfile               — Heroku-style process types (web + worker)
  railway.toml           — Railway config (web server start command)
  runtime.txt            — Pins python-3.11.9 for cloud builds

  modules/
    module_01_invoice_scanner.py  ...  module_36_cost_rollup.py

  static/
    widget.js              Embeddable chatbot widget served at /widget.js

  tests/
    test_deployment_readiness.py

  deploy/
    .env.example           Cloud environment variable template
    gaos.service           systemd unit — polling launcher (full_team)
    gaos-web.service       systemd unit — gunicorn web server
    FREE_SERVER_GUIDE.md   Oracle Cloud always-free setup
    CHATBOT_EMBED.md       How to embed the chatbot widget

  docs/
    SETUP.md               Step-by-step setup guide (~30 mins)
    PRICING.md             Pricing structure and ROI calculator
    HLSR.md                High-Level System Requirements
    LLSR.md                Low-Level System Requirements
```

---

## Chatbot Widget Embed

One line on any website to enable the AI chatbot:

```html
<script src="https://your-server.up.railway.app/widget.js"
        data-gaos-url="https://your-server.up.railway.app"
        data-business-name="Your Business"></script>
```

---

## Key Design Principles

1. **Modular** — Every module is independent and sellable standalone.
2. **DRY** — All shared logic in `gaos_core.py` and `gaos_ai.py` — never duplicated.
3. **Fault-isolated** — Each module runs as a separate `Process`; one crash cannot stop others.
4. **Redundant** — AI failover (DeepSeek → Groq) means AI features never go dark.
5. **Observable** — Every action logged to `Actions_Log`; AI usage logged to `Usage_Log`.
6. **Client-owned** — Runs inside the client's own Gmail, Sheets, and Drive.
7. **Low-cost** — DeepSeek keeps AI at fractions of a penny per task. Groq fallback is free.
8. **Config-driven** — Roles defined by data; new bundles need zero new code.

---

*Aether Frameworks Ltd — GAOS™ v3.4*

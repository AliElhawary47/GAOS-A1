# GAOS™ High-Level System Requirements — v3.3

**Document ID:** GAOS-HLSR-3.3  
**Product:** Ghost Assistant Operating System (GAOS™)  
**Vendor:** Aether Frameworks Ltd  
**Status:** Released  
**Date:** 2026-06-09  
**Revision:** 2.0  

---

## Table of Contents

1. [Purpose and Scope](#1-purpose-and-scope)
2. [Stakeholders](#2-stakeholders)
3. [System Context Diagram](#3-system-context-diagram)
4. [System-Level Functional Requirements](#4-system-level-functional-requirements)
5. [Non-Functional Requirements](#5-non-functional-requirements)
6. [System Constraints](#6-system-constraints)
7. [Assumptions and Dependencies](#7-assumptions-and-dependencies)
8. [Acceptance Criteria](#8-acceptance-criteria)

---

## 1. Purpose and Scope

### 1.1 Purpose

This document defines the High-Level System Requirements (HLSR) for the Ghost Assistant Operating System (GAOS™) version 3.3. It establishes the functional capabilities, non-functional properties, constraints, and acceptance criteria that the system must satisfy. It is intended to serve as the authoritative requirements baseline for design, implementation, testing, and audit activities.

GAOS™ is a modular, Python-based business automation platform designed to operate continuously inside a client's own Google account. The system watches a Gmail inbox, processes incoming email with artificial intelligence, and executes back-office actions automatically across nine operational zones covering administration, sales, finance, customer engagement, scheduling, conversational AI, business intelligence, external monitoring, and marketing.

This document does not prescribe internal implementation details. Detailed component-level and module-level specifications are contained in the companion Low-Level System Requirements document (GAOS-LLSR-3.3).

### 1.2 Scope

The scope of GAOS™ v3.2 encompasses:

- A shared runtime library providing Gmail OAuth connectivity, Google Sheets data access, AI routing, Twilio messaging, scheduling utilities, audit logging, and cost tracking.
- An AI Provider Manager implementing a primary-plus-fallback provider architecture with per-provider circuit breaker logic.
- A process orchestrator that launches and supervises independent operating-system-level processes for each active module.
- A Flask-based web server serving three conversational modules via HTTP webhooks.
- An industry pack installer that provisions Google Sheet tabs, seeds knowledge bases, and writes contract templates.
- Thirty-four independent functional modules covering the full range of back-office automation tasks described in this document.
- A subscription-based virtual-role bundling model in which modules are grouped into six named roles and one full-team tier.

The following are explicitly out of scope for this version:

- Relational database management systems.
- Native mobile applications.
- Outbound call dialling (inbound voice only via Twilio webhook).
- Multi-tenancy within a single deployment instance (each deployment serves one client).
- Per-seat or per-user licensing enforcement at the platform level.

### 1.3 Document Conventions

Requirements are identified by a hierarchical identifier of the form `<TYPE>-<SEQ>`, where `<TYPE>` is a short category code and `<SEQ>` is a three-digit sequence number. The obligation level is indicated by the modal verb used:

- **SHALL** — mandatory requirement; non-compliance constitutes a defect.
- **SHOULD** — strongly recommended; deviation requires documented justification.
- **MAY** — optional capability; implementation at vendor or deployer discretion.

---

## 2. Stakeholders

### 2.1 Stakeholder Register

| ID | Stakeholder | Role | Primary Concerns |
|----|-------------|------|-----------------|
| SH-01 | System Owner / Reseller (Aether Frameworks Ltd) | Develops, maintains, and licences the GAOS™ platform to end-clients | Reliability, maintainability, commercial viability, security |
| SH-02 | End-Client Business | Subscribes to one or more virtual role bundles; owns the deployment | Automation accuracy, 24/7 availability, data privacy, cost |
| SH-03 | End-Client Customers | Individuals whose emails, enquiries, and appointments are processed | Response quality, data handling, privacy |
| SH-04 | AI Providers (DeepSeek, Groq) | Supply LLM inference APIs consumed by the system | API key validity, rate limit compliance, accurate attribution |
| SH-05 | Google | Provides Gmail API and Google Sheets API under OAuth2 | Scope minimisation, token security, quota compliance |
| SH-06 | Twilio | Provides SMS, WhatsApp, and Voice webhook infrastructure | Webhook authentication, message body length compliance |
| SH-07 | Deployment Operator | Configures and operates the hosting environment | Startup simplicity, resource predictability, log access |

### 2.2 Stakeholder Interests

**SH-01 (Aether Frameworks Ltd):** The system SHALL be maintainable as a single codebase deployable across many client accounts without per-account code changes. The only client-specific artefact SHALL be `config.json` (or equivalent environment variables) and the Google credential files.

**SH-02 (End-Client Business):** The system SHALL operate continuously without requiring the client to interact with the platform day-to-day. The client SHALL own all data (Google Sheets, Gmail, archived files). Subscription cancellation SHALL not result in data loss or lock-in.

**SH-03 (End-Client Customers):** Personal data processed by the system SHALL be handled in accordance with applicable data protection law. Automated replies and AI-generated content SHALL be clearly purposeful and accurate.

**SH-04 (AI Providers):** The system SHALL present requests in the format specified by each provider's API contract. API keys SHALL be stored securely and not transmitted to third parties.

**SH-05 (Google):** The system SHALL request only the minimum OAuth scopes required (`gmail.modify`, `gmail.compose` for Gmail; `spreadsheets` and `drive` for Sheets). OAuth tokens SHALL be refreshed automatically and not stored in version-controlled files.

**SH-06 (Twilio):** Webhook endpoints SHALL respond with valid TwiML within Twilio's timeout window. WhatsApp message bodies SHALL not exceed 1,600 characters.

---

## 3. System Context Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          EXTERNAL ACTORS                                        │
│                                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │ End-Client   │  │ Website      │  │ WhatsApp /   │  │  Calling Public  │   │
│  │  Customers   │  │  Visitors    │  │  SMS Users   │  │  (Voice callers) │   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘   │
│         │ Email           │ JS Widget        │ Twilio Webhook     │ Twilio      │
└─────────┼─────────────────┼──────────────────┼────────────────────┼─────────────┘
          │                 │                  │                    │
          ▼                 ▼                  ▼                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        GOOGLE SERVICES                                          │
│  ┌──────────────────────────┐     ┌──────────────────────────────────────────┐ │
│  │      Gmail API           │     │          Google Sheets API               │ │
│  │  (OAuth2 — gmail.modify  │     │  (Service Account / OAuth2 token.json)   │ │
│  │   gmail.compose)         │     │  25 tabs — sole persistent data store    │ │
│  └────────────┬─────────────┘     └──────────────────┬───────────────────────┘ │
└───────────────┼──────────────────────────────────────┼─────────────────────────┘
                │                                      │
                ▼                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                     GAOS™ v3.2 DEPLOYMENT                                       │
│                                                                                 │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │  gaos_launcher.py                                                          │ │
│  │  Process Orchestrator — spawns one OS process per active module            │ │
│  │  Roles: admin | sales | finance | receptionist | marketer |                │ │
│  │         intelligence | full_team                                           │ │
│  └───────────────────────────────────┬────────────────────────────────────────┘ │
│                                      │  multiprocessing.Process                 │
│  ┌───────────────────────────────────┼────────────────────────────────────────┐ │
│  │               34 MODULES (9 Zones)│                                        │ │
│  │                                   ▼                                        │ │
│  │  Zone 1 React:  01 02 03 04 05 06 07  (email-triggered pollers)            │ │
│  │  Zone 2 Chase:  08 10 12              (condition-driven pollers)            │ │
│  │  Zone 3 Report: 13 14 15 16          (timed, daily/weekly)                 │ │
│  │  Zone 4 Schedule:17 18 19 20 21      (timed)                               │ │
│  │  Zone 5 Converse:22 23 24            (Flask webhook — gaos_server.py)       │ │
│  │  Zone 6 Learn:  25 26 27 28          (timed/polling)                       │ │
│  │  Zone 0 Sense:  29 30 31             (external data, timed)                │ │
│  │  Zone 7 Marketer:32 33 34            (timed/polling)                       │ │
│  │  Zone 8 CoS:    35                   (timed briefing + WhatsApp on-demand) │ │
│  │  Zone 9 Utility:36                   (monthly, 1st of month)               │ │
│  └───────────────────────────────────┬────────────────────────────────────────┘ │
│                                      │                                          │
│  ┌───────────────────────────────────▼────────────────────────────────────────┐ │
│  │  gaos_core.py — Shared Runtime Library                                     │ │
│  │  Gmail helpers · Sheets helpers · Scheduling · Twilio · Slack · Logging   │ │
│  └───────────────────────────────────┬────────────────────────────────────────┘ │
│                                      │                                          │
│  ┌───────────────────────────────────▼────────────────────────────────────────┐ │
│  │  gaos_ai.py — AI Provider Manager                                          │ │
│  │  DeepSeek (primary, deepseek-chat) → Groq (fallback, llama-3.3-70b)       │ │
│  │  Circuit breaker per provider — 5 failures → open → cooldown → half-open  │ │
│  └───────────────────────────────────┬────────────────────────────────────────┘ │
│                                      │                                          │
│  ┌───────────────────────────────────▼────────────────────────────────────────┐ │
│  │  gaos_server.py — Flask Web Server                                         │ │
│  │  /health  /chat  /whatsapp  /voice  /voice/handle  /widget.js              │ │
│  │  Production: gunicorn gaos_server:app                                      │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────────────────────┬─┘
                                                                                │
          ┌────────────────────┬─────────────────────┬────────────────────────┘
          │                    │                      │
          ▼                    ▼                      ▼
┌─────────────────┐ ┌────────────────────┐ ┌──────────────────────────────────┐
│  AI PROVIDERS   │ │  TWILIO            │ │  EXTERNAL DATA SOURCES           │
│                 │ │                    │ │                                  │
│  DeepSeek API   │ │  SMS Messages      │ │  London Gazette API (free)       │
│  (deepseek-chat)│ │  WhatsApp Msgs     │ │  HM Land Registry (free)         │
│                 │ │  Voice TwiML       │ │  Bank of England API (free)      │
│  Groq API       │ │                    │ │  ONS Statistics API (free)       │
│  (llama-3.3-70b)│ │                    │ │  Council Planning Portals        │
└─────────────────┘ └────────────────────┘ └──────────────────────────────────┘
          │
          ▼
┌────────────────┐
│  SLACK         │
│  Incoming      │
│  Webhooks      │
└────────────────┘
```

---

## 4. System-Level Functional Requirements

### SFR-001 — Continuous Gmail Inbox Monitoring

**Title:** Unattended inbox polling  
**Priority:** Must  
**Description:** The system SHALL poll the configured Gmail inbox at a configurable interval (default 300 seconds) for new unread messages, and SHALL route each message to the appropriate processing modules without requiring human intervention.  
**Rationale:** Core value proposition of the platform is 24/7 unattended operation. Without continuous polling, all email-triggered modules are inoperative.

---

### SFR-002 — AI-Assisted Content Processing

**Title:** LLM-based email and document analysis  
**Priority:** Must  
**Description:** The system SHALL use one or more large-language model (LLM) API providers to extract structured data from unstructured email content and PDF documents, to generate contextually appropriate draft replies, and to produce natural-language summaries. The system SHALL route all AI calls through a unified provider manager that abstracts provider selection from module code.  
**Rationale:** AI inference is the mechanism by which raw email text is converted into actionable structured data. Provider abstraction ensures modules do not need to be rewritten when provider configuration changes.

---

### SFR-003 — AI Provider Failover

**Title:** Automatic primary-to-fallback AI failover  
**Priority:** Must  
**Description:** The system SHALL maintain at least two configured AI providers in priority order. When the primary provider (DeepSeek) is unavailable or returns an error, the system SHALL automatically route the request to the fallback provider (Groq) without any module code change or operator intervention. Failover events SHALL be logged.  
**Rationale:** DeepSeek is a commercial API subject to outages. Groq's free tier provides a cost-free fallback. Without automatic failover, all AI-dependent modules would fail silently during any primary provider outage.

---

### SFR-004 — Google Sheets as Sole Persistent Data Store

**Title:** Sheets-only persistence  
**Priority:** Must  
**Description:** The system SHALL read and write all persistent business data exclusively via the Google Sheets API. The system SHALL NOT require any relational database, local file database, or cloud database service. All data SHALL be stored in named tabs within a single Google Spreadsheet owned by the client.  
**Rationale:** Google Sheets is universally accessible to business owners without technical training. It eliminates database infrastructure cost and complexity. It ensures the client retains direct ownership and visibility of all their data.

---

### SFR-005 — Modular Process Isolation

**Title:** One OS process per module  
**Priority:** Must  
**Description:** The system SHALL launch each active module as a separate operating-system process. A failure (exception, crash, or unresponsive state) in any one module process SHALL NOT affect the operation of any other module process.  
**Rationale:** Without process isolation, a bug in one module could bring down the entire GAOS instance. Given that modules interact with external services that may behave unexpectedly, fault isolation is essential for production reliability.

---

### SFR-006 — Virtual Role Bundle Activation

**Title:** Role-based module selection  
**Priority:** Must  
**Description:** The system SHALL support activation of modules in predefined bundles corresponding to virtual roles: Virtual Admin (01, 05, 06, 07, 08, 27), Virtual Sales (02, 03, 04, 08, 15), Virtual Finance (08, 13, 14, 16, 19, 20, 36), Virtual Receptionist (10, 12, 22, 23), Virtual Marketer (17, 18, 21, 32, 33, 34), Virtual Intelligence (25, 26, 28, 29, 30, 31, 35), and Full Team (all 34 modules). Individual modules SHALL also be launchable à la carte.  
**Rationale:** The virtual-role model is the commercial offering. The launcher must map role names to module lists so that a client who subscribes to a specific tier activates only the modules they have licensed.

---

### SFR-007 — Email-Triggered Automation (Zone 1)

**Title:** React zone processing  
**Priority:** Must  
**Description:** The system SHALL implement a set of email-triggered modules that detect specific email types (PDF invoices, lead enquiries, urgent leads, completed-job markers, new contracts, FAQ questions, and broadcast triggers) and SHALL automatically execute the corresponding back-office actions (data extraction, AI lead scoring, draft reply creation, SMS/WhatsApp alerts, Sheets logging, label assignment) within one poll cycle of message arrival. The Invoice Scanner SHALL deduplicate incoming invoices against the Invoice_Log and flag amounts that are anomalously high relative to the vendor average stored in GAOS_Memory. The Lead Catcher SHALL classify each lead as Hot, Warm, or Cold using AI and store the score in Lead_Log. The FAQ Auto-Reply module SHALL log every unanswered question to a dedicated FAQ_Gaps tab so the owner can improve the knowledge base over time. The Team Broadcaster SHALL extract and highlight payment amounts from relevant notification emails.  
**Rationale:** Zone 1 delivers the most immediately visible client value — the business owner sees automated activity within minutes of an email arriving. Delays longer than one poll cycle are commercially unacceptable.

---

### SFR-008 — Condition-Driven Follow-Up Automation (Zone 2)

**Title:** Chase zone processing  
**Priority:** Must  
**Description:** The system SHALL implement automated follow-up for overdue invoices (escalating tiers at 14, 21, and 30 days — tone increases from polite reminder to firm follow-up to final notice, recorded as Sent-1/Sent-2/Sent-3), unanswered proposals (5-day threshold), outstanding documents (3-day threshold), appointment reminders (24-hour and 2-hour advance notice), and no-show follow-ups (same-day). The Payment Chaser SHALL accelerate the first-tier threshold to 7 days for vendors identified as habitual late payers in GAOS_Memory. A duplicate-send guard SHALL search the Gmail sent folder before every chase to prevent double-chasing if the owner already emailed manually. The Appointment Reminder module SHALL scan client replies for reschedule keywords and mark appointments accordingly, suppressing the reminder if a reschedule request is detected.  
**Rationale:** Manual follow-up is the most time-consuming administrative task for small businesses. Escalating tone, adaptive thresholds, and duplicate prevention make the chase process both effective and professional.

---

### SFR-009 — Scheduled Report Generation (Zone 3)

**Title:** Report zone processing  
**Priority:** Must  
**Description:** The system SHALL generate and email the following scheduled reports: a daily summary digest at 08:00, a weekly revenue snapshot every Monday at 08:00, a lead pipeline report every Friday at 17:00, and a staff timesheet summary every Friday at 18:00. Reports SHALL be generated from data in the relevant Google Sheets tabs and SHALL use AI to produce human-readable narratives. The Daily Digest SHALL additionally post to the configured Slack webhook (first 12 lines of the digest body) if `slack.webhook_url` is set.  
**Rationale:** Management information reporting is a primary deliverable of the Virtual Finance and Virtual Intelligence roles. Timeliness (correct schedule) is as important as content accuracy.

---

### SFR-010 — Scheduled Outbound Campaigns (Zone 4)

**Title:** Schedule zone processing  
**Priority:** Must  
**Description:** The system SHALL send birthday and anniversary emails daily at 09:00, schedule and post social content each poll cycle, generate monthly invoices for retainer clients on the 1st of each month at 08:00 (with sequential invoice numbers in the format INV-YYYYMM-NNN continuing from the last number used that month), send licence and compliance expiry alerts daily at 09:00, and send re-engagement emails to dormant contacts every Monday at 10:00. The Re-Engagement Mailer SHALL skip clients whose `Status` column contains any of: churned, inactive, cancelled, lost, or do not contact.  
**Rationale:** Proactive outbound communications (birthdays, retainer invoices, licence alerts) prevent revenue loss and relationship degradation that would otherwise require human memory and manual effort.

---

### SFR-011 — Conversational AI Channel Support (Zone 5)

**Title:** Converse zone webhook handling  
**Priority:** Must  
**Description:** The system SHALL provide an embeddable JavaScript widget for website visitors that communicates with a Flask endpoint to deliver AI-powered chat responses. The system SHALL receive and respond to inbound WhatsApp messages via a Twilio webhook. The system SHALL receive inbound telephone calls via a Twilio voice webhook and conduct spoken AI conversations using TwiML, with speech-to-text input and AWS Polly (Amy, en-GB) voice output. All conversational modules SHALL draw responses from the Chatbot_Knowledge Sheets tab.  
**Rationale:** The Receptionist role is the highest-margin bundle. Chatbot, WhatsApp, and voice coverage provides genuine 24/7 customer service without human staff.

---

### SFR-012 — Adaptive Business Memory (Zone 6)

**Title:** GAOS Learn weekly intelligence cycle  
**Priority:** Should  
**Description:** The system SHALL execute a weekly learning cycle every Monday at 07:00 that reads historical data from Invoice_Log, Lead_Log, Completed_Jobs, FAQ_Knowledge_Base, and Appointments, extracts statistical patterns (average invoice value, lead conversion rate, no-show rate, busiest day, top vendors, late payers, chase rate, appointment peak time), and writes the results as key-value rows to the GAOS_Memory Sheets tab. If more than 40% of invoices have a non-blank Chase Sent value, the system SHALL write a `chase_rate` advisory to GAOS_Memory. The busiest appointment time slot (morning, lunchtime, afternoon, evening) SHALL be written to GAOS_Memory as `appointment_peak_time`. Client Pulse SHALL cross-reference at-risk clients against unpaid invoices and, where a client appears in both, write a `danger_signals` alert to GAOS_Memory. The AI Chief of Staff SHALL inject the full GAOS_Memory context into all three AI prompt calls (daily briefing, weekly summary, on-demand queries). Subsequent AI calls in other modules SHOULD incorporate the current GAOS_Memory context in their prompts.  
**Rationale:** Business-context injection makes AI outputs progressively more accurate and personalised. Danger-signal cross-referencing gives the Chief of Staff early-warning intelligence that no single module can produce alone.

---

### SFR-013 — External Business Intelligence Monitoring (Zone 0)

**Title:** Sense zone external data ingestion  
**Priority:** Should  
**Description:** The system SHALL: (a) query the London Gazette API daily at 07:00 for insolvency, strike-off, and estate notices and cross-reference results against known clients and suppliers; (b) query HM Land Registry data weekly on Mondays at 09:00 for new property transactions near the configured postcode; (c) retrieve Bank of England base rate data and ONS CPI inflation data daily at 12:00 and on the 1st of each month and log changes to the Macro_Log tab.  
**Rationale:** Early warning of client/supplier insolvency can prevent bad debts. Property transaction data creates new leads for relevant businesses. Macroeconomic data context improves AI briefing quality for the Chief of Staff module.

---

### SFR-014 — Marketing Automation (Zone 7)

**Title:** Marketer zone processing  
**Priority:** Must  
**Description:** The system SHALL send newsletter campaigns to the Newsletter_Queue mailing list on the first Monday of each month at 09:00, monitor Google review notification emails each poll cycle, log new reviews to Reviews_Log, AI-draft responses, and produce a campaign performance digest every Friday at 17:00. Modules SHALL consume the Social_Queue tab for scheduled social post management. For negative reviews (1–3 stars), the system SHALL alert the owner via SMS, email, and Slack (if configured). For positive reviews, the system SHALL email the AI-drafted response for the owner to post.  
**Rationale:** Marketing automation is a primary deliverable of the Virtual Marketer role. Multi-channel alerts for negative reviews ensure the owner can respond before the business reputation is damaged.

---

### SFR-015 — AI Chief of Staff Briefing (Zone 8)

**Title:** Chief of Staff daily and weekly briefings  
**Priority:** Should  
**Description:** The system SHALL deliver a daily AI-generated briefing at 07:30 via email and WhatsApp that aggregates intelligence from all active roles, scores and prioritises action items, and presents them in plain English. The system SHALL deliver a strategic weekly summary every Monday at 07:45. The Chief of Staff module SHALL respond to natural-language WhatsApp queries from the owner at any time, integrating with Module 23's webhook handler.  
**Rationale:** The Chief of Staff module is the highest-level differentiator — it transforms the system from a task executor into a strategic business advisor. Role-awareness (only surfacing data from active subscriptions) ensures relevance.

---

### SFR-016 — AI Cost Reporting (Zone 9)

**Title:** Monthly cost rollup  
**Priority:** Must  
**Description:** The system SHALL generate a monthly AI cost report on the 1st of each month at 09:00 by reading the Usage_Log tab, aggregating tokens and cost by module, estimating gross margin against subscription revenue, and emailing the report to the configured admin address.  
**Rationale:** AI API costs are a variable operating expense. The client must have visibility of these costs. Cost reporting is a mandatory requirement for the Virtual Finance role.

---

### SFR-017 — Audit Logging

**Title:** Actions and usage audit trail  
**Priority:** Must  
**Description:** The system SHALL append a row to the Actions_Log Sheets tab for every significant automated action, recording timestamp, module identifier, action description, status (ok / error), and a detail field (max 250 characters). The system SHALL append a row to the Usage_Log Sheets tab for every AI API call, recording timestamp, module identifier, tokens consumed, and cost in GBP.  
**Rationale:** Audit trails are required for client trust, dispute resolution, and compliance. Usage logging is the data source for the monthly cost report.

---

### SFR-018 — Industry Pack Provisioning

**Title:** One-command deployment configuration  
**Priority:** Should  
**Description:** The system SHALL provide a command-line installer (`gaos_install.py`) that accepts an industry pack identifier (trades, legal, clinic, agency, property, accountancy) and SHALL: create all required Google Sheets tabs with correct column headers; seed the FAQ_Knowledge_Base and Chatbot_Knowledge tabs with industry-specific question-answer pairs; seed the Licences tab with industry-standard compliance items; write an industry-specific contract template to `contract_template.txt`; and merge tab key mappings into `config.json`.  
**Rationale:** Reducing deployment time is critical to the reseller model. An installer that provisions the entire data layer in one command allows a new client deployment to be completed in under 30 minutes.

---

### SFR-019 — Configuration via File and Environment Variables

**Title:** Dual-mode credential and configuration management  
**Priority:** Must  
**Description:** The system SHALL read all configuration from `config.json` at startup. The system SHALL also accept every secret-valued configuration field via environment variable using the convention of converting the dot-path to SCREAMING_SNAKE_CASE (e.g., `deepseek.api_key` → `DEEPSEEK_API_KEY`). Environment variable values SHALL take precedence over `config.json` values.  
**Rationale:** Environment variable injection is the standard mechanism for secret management in containerised and PaaS deployments (Railway.app, Docker). Developers and operators must not be required to maintain a `config.json` containing plaintext secrets in production.

---

### SFR-020 — System Health Heartbeat

**Title:** Heartbeat file and health endpoint  
**Priority:** Should  
**Description:** The system SHALL update a heartbeat file (`gaos_heartbeat.json` by default) at every poll cycle to indicate that the polling loop is alive. The Flask web server SHALL expose a `GET /health` endpoint that returns HTTP 200 with a JSON body indicating server status, config load state, module import status for modules 22, 23, and 24, and Gmail connection status.  
**Rationale:** Railway.app and other PaaS platforms use health check endpoints to determine whether a deployment is healthy and to trigger restarts. The heartbeat file enables external monitoring of the poller processes independently of the web server.

---

## 5. Non-Functional Requirements

### 5.1 Availability

**NFR-AV-001 — Continuous Operation Target**  
The system SHOULD maintain operational availability of 99% or greater on a monthly basis for polling-mode modules, measured as the proportion of scheduled poll cycles that complete without a process-level crash.

**NFR-AV-002 — Automatic Process Restart**  
The deployment configuration SHALL include automatic restart on process failure. On Railway.app this SHALL be achieved via `restartPolicyType = "ON_FAILURE"` with `restartPolicyMaxRetries = 10`. On Linux systemd deployments this SHALL be achieved via `Restart=always` with `RestartSec=10`.

**NFR-AV-003 — Scheduled Auto-Restart**  
The system SHOULD support a configurable auto-restart interval (`settings.auto_restart_hours`, default 24 hours) to prevent memory accumulation over long runtimes.

**NFR-AV-004 — Graceful Shutdown**  
The system SHALL handle `SIGINT` (Ctrl+C) and process termination signals by stopping all child module processes cleanly, logging a shutdown event, and exiting without orphaning background threads.

**NFR-AV-005 — Flask Server Health Check**  
The Flask web server SHALL respond to `GET /health` within 2 seconds under normal operating conditions to satisfy PaaS health check requirements.

---

### 5.2 Performance

**NFR-PE-001 — Poll Interval**  
The default poll interval for all polling-mode modules SHALL be 300 seconds (5 minutes). This value SHALL be configurable via `settings.check_every_seconds` in `config.json`.

**NFR-PE-002 — AI Request Timeout**  
All AI API HTTP requests SHALL be subject to a 60-second timeout. A request that does not receive a complete response within 60 seconds SHALL be treated as a failure and SHALL trigger the circuit breaker failure counter.

**NFR-PE-003 — Twilio API Timeout**  
Twilio SMS and WhatsApp API requests SHALL be subject to a 30-second timeout. Twilio Voice webhook responses SHALL be produced within 10 seconds to avoid Twilio timeout errors.

**NFR-PE-004 — Slack Webhook Timeout**  
Outbound Slack webhook POST requests SHALL be subject to a 15-second timeout.

**NFR-PE-005 — Gmail and Sheets API Search Limits**  
The Gmail search helper SHALL request a maximum of 25 messages per call by default to avoid Gmail API quota exhaustion. Sheets read operations SHALL retrieve all records in a single API call where the worksheet row count permits.

**NFR-PE-006 — WhatsApp Message Length**  
WhatsApp message bodies sent via Twilio SHALL be truncated to 1,600 characters before transmission to comply with Twilio's documented limit.

---

### 5.3 Reliability

**NFR-RE-001 — Module-Level Exception Isolation**  
The polling loop (`run_loop`) SHALL catch all exceptions raised by the module action function, log the error, and continue polling. An exception in one poll cycle SHALL NOT terminate the module process or affect subsequent poll cycles.

**NFR-RE-002 — AI Circuit Breaker**  
Each AI provider SHALL have an independent circuit breaker. The circuit breaker SHALL open after 5 consecutive failures. The circuit breaker SHALL remain open for a cooldown period (600 seconds for DeepSeek, 300 seconds for Groq). After the cooldown, the circuit breaker SHALL enter the half-open state and permit one test request. On success the circuit breaker SHALL return to closed. On failure it SHALL return to open and restart the cooldown.

**NFR-RE-003 — AI Fallback Empty Response**  
When all configured AI providers fail (both circuit breakers open, or all providers return errors), the system SHALL return an empty dict (`{}`) for JSON-mode requests and an empty string (`""`) for text-mode requests. Modules SHALL handle these empty responses gracefully without raising an unhandled exception.

**NFR-RE-004 — Consecutive Failure Alerting**  
The system SHALL alert the owner (via configured email or SMS) after `settings.alert_after_consecutive_failures` (default 3) consecutive failures in a single module, to enable operator intervention before prolonged degradation occurs.

**NFR-RE-005 — Duplicate Action Prevention**  
All modules that send follow-up or reminder communications SHALL maintain a sent-flag in the relevant Google Sheets tab column. The module SHALL check this flag before sending and SHALL NOT send a duplicate communication if the flag is already set.

**NFR-RE-006 — PDF Processing Resilience**  
If a PDF attachment cannot be downloaded, is zero bytes, or contains no machine-readable text (scanned image), the module SHALL log a warning, mark the email as read, and proceed to the next message without raising an error.

---

### 5.4 Security

**NFR-SE-001 — No Plaintext Secrets in Code**  
API keys, OAuth tokens, Twilio credentials, and all other secrets SHALL NOT be hardcoded in source code. All secrets SHALL be read from `config.json` or from environment variables at runtime.

**NFR-SE-002 — Credential File Exclusion from Version Control**  
The files `config.json`, `token.json`, `credentials.json`, and `service_account.json` SHALL be listed in `.gitignore` and SHALL NOT be committed to version control.

**NFR-SE-003 — OAuth2 Scope Minimisation**  
The Gmail OAuth2 flow SHALL request only `https://www.googleapis.com/auth/gmail.modify` and `https://www.googleapis.com/auth/gmail.compose`. The Sheets/Drive OAuth2 scope SHALL be limited to `https://spreadsheets.google.com/feeds` and `https://www.googleapis.com/auth/drive`. No broader scopes SHALL be requested.

**NFR-SE-004 — OAuth Token Auto-Refresh**  
The system SHALL automatically refresh expired OAuth tokens using the stored refresh token without requiring user interaction. A new `token.json` SHALL be written after each successful refresh.

**NFR-SE-005 — Twilio Credential Validation**  
Before making any Twilio API call, the system SHALL check whether the configured `account_sid` contains the placeholder string `YOUR_`. If it does, the Twilio call SHALL be skipped and a log warning SHALL be emitted. This prevents unconfigured deployments from making accidental Twilio API calls.

**NFR-SE-006 — AI API Key Validation**  
The AI Provider Manager SHALL check whether a configured API key begins with the string `YOUR_`. Such keys SHALL be treated as absent; the corresponding provider SHALL not be added to the active provider list.

**NFR-SE-007 — HTTPS for All External API Calls**  
All HTTP requests to external APIs (DeepSeek, Groq, Twilio, Slack, Gazette, Land Registry, BoE, ONS) SHALL use HTTPS. Non-TLS endpoints SHALL NOT be used.

---

### 5.5 Scalability

**NFR-SC-001 — Per-Client Deployment Model**  
Each GAOS™ deployment SHALL serve exactly one end-client. Horizontal scaling across multiple clients SHALL be achieved by deploying additional independent instances, each with their own `config.json`, Google credentials, and Sheets spreadsheet.

**NFR-SC-002 — Process-Per-Module Concurrency**  
Module concurrency SHALL be achieved through `multiprocessing.Process`, providing OS-level process isolation. The number of concurrent processes SHALL equal the number of modules in the active tier. For the Full Team tier this is up to 34 concurrent processes.

**NFR-SC-003 — Sheets Tab Scalability**  
The Sheets data layer SHALL support up to 25 standard tabs and additional industry-pack-specific tabs within a single spreadsheet. Individual tab row counts SHALL not be constrained by the system (Google Sheets limits apply at the platform level).

---

### 5.6 Maintainability

**NFR-MA-001 — Single Codebase, Config-Driven Customisation**  
The system SHALL be maintained as a single Python codebase. All client-specific parameters (business name, email addresses, sheet IDs, API keys, active roles) SHALL be captured in `config.json`. No client-specific code changes SHALL be required for a standard deployment.

**NFR-MA-002 — Module Independence**  
Each module SHALL be implemented as a self-contained Python file under the `modules/` directory. Modules SHALL import `gaos_core` for shared utilities and SHALL NOT import directly from other modules, with the exception of Module 35 (Chief of Staff) and Module 25 (GAOS Learn) which provide cross-module context injection services.

**NFR-MA-003 — Shared Runtime Library**  
All Gmail, Sheets, Twilio, Slack, PDF, scheduling, and AI interactions SHALL be performed through functions in `gaos_core.py`. Direct instantiation of Google API clients or direct HTTP calls to provider APIs from within module files SHALL be avoided.

**NFR-MA-004 — Adding New Modules**  
The system SHALL be designed such that a new module can be added by: creating one file in `modules/`, registering it in `MODULE_FILES` and `MODULE_NAMES` in `gaos_launcher.py`, and (where applicable) adding it to the appropriate role bundle in `ROLES`. No changes to `gaos_core.py` or `gaos_ai.py` SHALL be required.

---

### 5.7 Observability

**NFR-OB-001 — Structured Log Format**  
All log output SHALL use the format `%(asctime)s  %(name)s  %(levelname)s  %(message)s`. Logger names SHALL follow the convention `gaos.<module_short_name>`. Log level SHALL default to `INFO`.

**NFR-OB-002 — Actions Audit Log**  
Every significant automated action (email sent, record written, alert fired, AI call made) SHALL be logged to the `Actions_Log` Sheets tab with timestamp, module name, action description, status, and detail. This log SHALL be readable by the client without technical knowledge.

**NFR-OB-003 — AI Usage Log**  
Every AI API call SHALL result in a row written to the `Usage_Log` Sheets tab containing timestamp, module name, total token count, and estimated cost in GBP. The cost calculation SHALL use `DEEPSEEK_COST_PER_1K = £0.00014` per 1,000 tokens for DeepSeek and `£0.00` for Groq (free tier).

**NFR-OB-004 — Heartbeat File**  
The system SHALL write a heartbeat file (`gaos_heartbeat.json`) at each poll cycle. The file SHALL contain at minimum the last-updated timestamp and the active module count. External monitoring tools MAY use the age of this file to detect stalled poller processes.

**NFR-OB-005 — AI Provider Status Dashboard**  
The system SHALL expose AI provider status (provider name, total calls, total tokens, total cost GBP, circuit breaker state) via the `get_ai_status()` function in `gaos_ai.py`, which SHALL be queryable via the `/health` route or dashboard interface.

**NFR-OB-006 — System Resource Metrics**  
The system SHALL collect and expose current process memory usage (RSS, MB), disk usage percentage, and CPU percentage using `psutil`. These metrics SHALL be available via `core.get_system_stats()` for inclusion in dashboards and the monthly cost report.

---

### 5.8 Compliance

**NFR-CO-001 — Data Residency**  
All persistent business data SHALL be stored within the client's own Google Sheets spreadsheet, in the Google account specified by the configured credentials. GAOS™ SHALL NOT transmit client business data to any servers operated by Aether Frameworks Ltd.

**NFR-CO-002 — GDPR — Data Minimisation**  
Modules SHALL extract and store only the fields necessary for their stated function. Email body content SHALL NOT be stored verbatim in Google Sheets. AI extraction results SHALL be limited to the defined JSON schema for each module.

**NFR-CO-003 — GDPR — Personal Data in AI Prompts**  
Before sending email content to AI providers, modules SHALL truncate prompt content to the minimum length required (e.g., 2,000–4,000 characters). Modules SHALL NOT send full message threads or attachment content beyond what is required for the specific extraction task.

**NFR-CO-004 — GDPR — Data Subject Rights**  
The system owner SHALL be responsible for implementing data subject access, rectification, and erasure processes at the Google Sheets layer. GAOS™ does not provide automated data subject request handling in this version.

**NFR-CO-005 — Automated Decision Disclosure**  
Where GAOS™ generates outbound communications on behalf of the client (draft replies, chase emails, review requests), these SHALL be generated as drafts (for review) or clearly represent standard business correspondence. GAOS™ SHALL NOT make automated decisions with legal or similarly significant effects on data subjects without human review.

**NFR-CO-006 — AI Provider Data Processing**  
The operator SHALL ensure that the use of DeepSeek and Groq APIs for processing email content containing personal data is covered by appropriate data processing agreements or documented legitimate-interest assessments as required by applicable data protection law.

---

## 6. System Constraints

**CON-001 — Python Version**  
The system SHALL be implemented in and require Python 3.11 or later. Python 3.10 and earlier are not supported due to use of `list[Type]` PEP 585 generic syntax and match-statement patterns.

**CON-002 — No Relational Database**  
The system SHALL NOT use SQLite, PostgreSQL, MySQL, MongoDB, Redis, or any other database system as a data store. Google Sheets is the sole permitted persistence mechanism.

**CON-003 — Google Account Dependency**  
The system SHALL require access to a Google account with Gmail and Google Sheets enabled. A Google Cloud Console project with the Gmail API and Google Sheets API enabled is a hard prerequisite. Without these, no module can operate.

**CON-004 — Single Spreadsheet Architecture**  
All module data SHALL reside in a single Google Spreadsheet identified by `google_sheets.sheet_id` in `config.json`. Multi-spreadsheet configurations are not supported in this version.

**CON-005 — Twilio Dependency for Outbound SMS/WhatsApp/Voice**  
Modules 02, 03, 23, and 24 depend on a valid Twilio account. If Twilio credentials are not configured (placeholder values detected), these modules SHALL silently skip Twilio operations and SHALL NOT raise errors.

**CON-006 — DeepSeek JSON Mode Limitation**  
The DeepSeek API's `response_format: json_object` parameter is only honoured by the deepseek-chat model. The Groq fallback does not support this parameter and relies on prompt-level JSON instructions and post-processing regex cleaning instead.

**CON-007 — Conversational Module Server Separation**  
Modules 22, 23, and 24 SHALL NOT run inside the `multiprocessing.Process` launcher. They SHALL be served exclusively by `gaos_server.py` via Flask. The launcher SHALL detect these module IDs and print an informational notice rather than attempting to spawn them as polling processes.

**CON-008 — Gmail OAuth Desktop Flow**  
On first run, the Gmail OAuth2 flow SHALL require an interactive browser session to authorise the application. This is a limitation of the Desktop App OAuth client type. Headless (no-browser) environments SHALL use a pre-generated `token.json` transferred from a machine where the initial authorisation was completed.

**CON-009 — Scheduling Window Granularity**  
The `should_run_at` scheduling function uses a configurable window (default 5 minutes) aligned to the poll interval. Scheduled modules will execute once per 5-minute window rather than at a precise second. This is acceptable for all current module schedules.

---

## 7. Assumptions and Dependencies

### 7.1 Assumptions

**ASS-001** — The end-client has an active Gmail account and has granted the necessary OAuth2 permissions to the configured Google Cloud project.

**ASS-002** — The end-client maintains the Google Sheets spreadsheet in a state consistent with the expected tab names and column headers provisioned by `gaos_install.py`. Manual deletion of tabs or renaming of columns will cause module failures.

**ASS-003** — The DeepSeek API and Groq API are accessible from the deployment host's network. Network-level firewalls blocking outbound HTTPS to `api.deepseek.com` or `api.groq.com` will disable AI features.

**ASS-004** — The Twilio account associated with the configured credentials has sufficient balance (for SMS and WhatsApp) and has a provisioned phone number capable of sending the required message types.

**ASS-005** — The London Gazette API (`https://www.thegazette.co.uk/notice/search`) remains publicly accessible and free of charge under the Open Government Licence. Changes to this API may require updates to Module 29.

**ASS-006** — The deployment host has a stable internet connection. Temporary network outages will cause individual poll cycles to fail; the run_loop exception handling will resume normal operation when connectivity is restored.

**ASS-007** — The `config.json` `settings.check_every_seconds` value is set to 300 or greater. Values below 60 seconds may trigger Gmail API rate limiting.

**ASS-008** — The client's Gmail inbox volume does not exceed 1,000 unread messages per poll cycle. Higher volumes may require increasing `max_results` in `gmail_search`.

### 7.2 External Dependencies

| Dependency | Version / Endpoint | Criticality | Fallback |
|---|---|---|---|
| Python | 3.11+ | Critical | None |
| gspread | 6.0.2 | Critical | None |
| google-api-python-client | 2.126.0 | Critical | None |
| requests | 2.31.0 | Critical | None |
| flask | 3.0.2 | Required for Zone 5 | Zone 5 modules unavailable |
| gunicorn | 21.2.0 | Required for production Zone 5 | Flask dev server (not recommended) |
| pdfplumber | 0.10.3 | Required for Module 01 | Module 01 fails gracefully |
| psutil | 5.9.8 | Required for cost reports | Metrics unavailable, no crash |
| DeepSeek API | api.deepseek.com/v1 | Primary AI | Groq fallback |
| Groq API | api.groq.com/openai/v1 | AI fallback | Empty response |
| Gmail API | gmail.googleapis.com | Critical | No email processing |
| Google Sheets API | sheets.googleapis.com | Critical | No data persistence |
| Twilio REST API | api.twilio.com/2010-04-01 | Required for SMS/WA/Voice | Silent skip |
| Slack Webhooks | hooks.slack.com | Optional | Log warning only |
| London Gazette API | thegazette.co.uk | Required for Module 29 | Module 29 skips cycle |
| Bank of England API | Variable | Required for Module 31 | Module 31 skips cycle |
| ONS Statistics API | Variable | Required for Module 31 | Module 31 skips cycle |

---

## 8. Acceptance Criteria

The following criteria SHALL be satisfied for the system to be considered compliant with this requirements document. Each criterion maps to one or more requirements above.

### 8.1 Core Platform

**AC-001** (→ SFR-001): A configured deployment SHALL process a test unread Gmail message containing a PDF invoice within one poll cycle (≤ 300 seconds) and write the extracted data to the Invoice_Log tab.

**AC-002** (→ SFR-003): When the DeepSeek API key is intentionally set to an invalid value, subsequent module AI calls SHALL route to Groq and produce a non-empty response. A warning log entry SHALL be present indicating failover.

**AC-003** (→ SFR-003, NFR-RE-002): When both provider API keys are set to invalid values, the AI Manager SHALL return `{}` for JSON-mode calls and `""` for text-mode calls without raising an unhandled exception.

**AC-004** (→ SFR-005): When a test exception is injected into Module 01's processing function, Modules 02–36 SHALL continue polling without interruption. The Module 01 process SHALL continue running and attempt the next poll cycle.

**AC-005** (→ SFR-006): Running `python gaos_launcher.py admin` SHALL start exactly 6 processes corresponding to modules 01, 05, 06, 07, 08, and 27. Running `python gaos_launcher.py full_team` SHALL start all 34 modules.

### 8.2 Email Processing

**AC-006** (→ SFR-007): A test email matching the lead search query SHALL result in: (a) the GAOS/Lead Gmail label applied; (b) a draft reply created; (c) a WhatsApp alert sent (if Twilio configured); (d) a row appended to Lead_Log.

**AC-007** (→ NFR-RE-005): Sending two identical lead emails SHALL result in only one processed lead entry. The second email, once the first has been labelled, SHALL be excluded from Module 03's urgent alert scan.

**AC-008** (→ SFR-008): A row in Invoice_Log with an Invoice Date 15 days in the past and Status not in (paid, cancelled, void) and Chase Sent blank SHALL result in a chase email being sent and the Chase Sent cell updated to `"Sent-1"` within one poll cycle. A row where Chase Sent is `"Sent-1"` and Invoice Date is 21+ days past SHALL be escalated to a firmer email and Chase Sent updated to `"Sent-2"`. A row where Chase Sent is `"Sent-2"` and Invoice Date is 30+ days past SHALL receive a final notice and Chase Sent updated to `"Sent-3"`. A row where Chase Sent is `"Sent-3"` SHALL NOT receive any further chases.

### 8.3 Scheduling

**AC-009** (→ SFR-009): At 08:00 on any day, the Daily Digest module SHALL generate and email a summary report. Verification: check Actions_Log for a "daily_digest" entry timestamped within the 08:00–08:05 window.

**AC-010** (→ SFR-012): After 5+ rows of data exist in Invoice_Log, running the GAOS Learn module manually SHALL write at minimum one key-value row to the GAOS_Memory tab containing invoice average information.

### 8.4 Conversational Modules

**AC-011** (→ SFR-011): A `POST /chat` request to `gaos_server.py` with `{"message": "What are your opening hours?"}` SHALL return a JSON response `{"reply": "<text>"}` within 30 seconds when the knowledge base contains a matching entry.

**AC-012** (→ SFR-011): A `POST /voice` request (simulating a Twilio inbound call) SHALL return a valid TwiML XML document containing a `<Gather>` element and a `<Say>` element. The HTTP status code SHALL be 200.

**AC-013** (→ NFR-AV-005): `GET /health` SHALL return HTTP 200 with `{"status": "ok"}` within 2 seconds.

### 8.5 Security

**AC-014** (→ NFR-SE-001, NFR-SE-002): A scan of the source tree using a secret-detection tool (e.g., trufflehog or gitleaks) SHALL produce zero findings for actual API key values or OAuth token content.

**AC-015** (→ NFR-SE-005): With `config.json` containing a Twilio `account_sid` of `YOUR_TWILIO_SID_HERE`, Module 02 SHALL complete lead processing without making any HTTP request to `api.twilio.com`.

### 8.6 Reliability

**AC-016** (→ NFR-RE-002): After 5 consecutive DeepSeek API errors (simulated via an invalid key), `get_ai_status()` SHALL return `circuit_state: "open"` for the DeepSeek provider and `circuit_state: "closed"` for Groq.

**AC-017** (→ NFR-RE-001): An exception raised within the Module 01 action function during a poll cycle SHALL appear in the log output as an ERROR and the next poll cycle SHALL execute without requiring process restart.

### 8.7 Installation

**AC-018** (→ SFR-018): Running `python gaos_install.py --pack trades` against a configured spreadsheet SHALL create all required tabs with correct headers, seed FAQ rows, and write `contract_template.txt` without error. Subsequent re-runs SHALL detect existing rows and skip seeding without duplicate data.

**AC-019** (→ SFR-019): With `DEEPSEEK_API_KEY` set as an environment variable and no `deepseek.api_key` key in `config.json`, the AI Manager SHALL successfully initialise with the DeepSeek provider using the environment variable value.

### 8.8 Observability

**AC-020** (→ NFR-OB-002, NFR-OB-003): After any module completes a successful AI-assisted action, both the Actions_Log and Usage_Log tabs SHALL contain new rows with correct timestamps and module identifiers.

---

*End of GAOS™ High-Level System Requirements — v3.3*  
*Document ID: GAOS-HLSR-3.3 | Aether Frameworks Ltd*

"""
╔══════════════════════════════════════════════════════════════╗
║   GAOS™ LAUNCHER v3.4                                       ║
║   Aether Frameworks                                         ║
║                                                             ║
║   34 modules across 9 operational zones.                    ║
║                                                             ║
║   Run a virtual role:                                       ║
║     python gaos_launcher.py admin          # Virtual Admin  ║
║     python gaos_launcher.py sales          # Virtual Sales  ║
║     python gaos_launcher.py finance        # Virtual Finance ║
║     python gaos_launcher.py receptionist   # Virtual Receptionist ║
║     python gaos_launcher.py marketer       # Virtual Marketer ║
║     python gaos_launcher.py intelligence   # Virtual Intelligence ║
║     python gaos_launcher.py full_team      # Full Team (all roles) ║
║                                                             ║
║   Run a single module (à la carte):                        ║
║     python gaos_launcher.py module 08                       ║
║                                                             ║
║   List all modules:                                         ║
║     python gaos_launcher.py list                            ║
╚══════════════════════════════════════════════════════════════╝
"""

import sys
import importlib
from multiprocessing import Process


# ── ZONE DEFINITIONS ─────────────────────────────────────────

ZONES = {
    "Zone 1 — React":         ["01","02","03","04","05","06","07"],
    "Zone 2 — Chase":         ["08","10","12"],
    "Zone 3 — Report":        ["13","14","15","16"],
    "Zone 4 — Schedule":      ["17","18","19","20","21"],
    "Zone 5 — Converse":      ["22","23","24"],
    "Zone 6 — Learn":         ["25","26","27","28"],
    "Zone 0 — Sense":         ["29","30","31"],
    "Zone 7 — Marketer":      ["32","33","34"],
    "Zone 8 — Chief of Staff":["35"],
    "Zone 9 — Utility":       ["36"],
}

# Modules 09 (Proposal Chaser) and 11 (Document Chaser) were merged
# into module 08 (Unified Item Chaser) in GAOS v3.2.

MODULE_FILES = {
    "01": "modules.module_01_invoice_scanner",
    "02": "modules.module_02_lead_catcher",
    "03": "modules.module_03_urgent_alert",
    "04": "modules.module_04_review_requester",
    "05": "modules.module_05_contract_sender",
    "06": "modules.module_06_faq_reply",
    "07": "modules.module_07_team_broadcaster",
    "08": "modules.module_08_chaser",
    "10": "modules.module_10_appointment_reminder",
    "12": "modules.module_12_noshow_followup",
    "13": "modules.module_13_daily_digest",
    "14": "modules.module_14_revenue_snapshot",
    "15": "modules.module_15_pipeline_report",
    "16": "modules.module_16_timesheet_summary",
    "17": "modules.module_17_birthday_mailer",
    "18": "modules.module_18_social_scheduler",
    "19": "modules.module_19_invoice_generator",
    "20": "modules.module_20_expiry_alert",
    "21": "modules.module_21_reengagement_mailer",
    "22": "modules.module_22_website_chatbot",
    "23": "modules.module_23_whatsapp_agent",
    "24": "modules.module_24_voice_agent",
    "25": "modules.module_25_gaos_learn",
    "26": "modules.module_26_client_pulse",
    "27": "modules.module_27_document_sentinel",
    "28": "modules.module_28_planning_radar",
    "29": "modules.module_29_gazette_monitor",
    "30": "modules.module_30_land_registry_radar",
    "31": "modules.module_31_rate_macro_pulse",
    "32": "modules.module_32_newsletter_mailer",
    "33": "modules.module_33_review_monitor",
    "34": "modules.module_34_campaign_digest",
    "35": "modules.module_35_chief_of_staff",
    "36": "modules.module_36_cost_rollup",
}

MODULE_NAMES = {
    "01": "Invoice Scanner",
    "02": "Lead Catcher",
    "03": "Urgent Lead Alert",
    "04": "Review Requester",
    "05": "Contract Sender",
    "06": "FAQ Auto-Reply",
    "07": "Team Broadcaster",
    "08": "Unified Item Chaser (payments · proposals · documents)",
    "10": "Appointment Reminder",
    "12": "No-Show Follow-Up",
    "13": "Daily Digest",
    "14": "Weekly Revenue Snapshot",
    "15": "Lead Pipeline Report",
    "16": "Staff Timesheet Summary",
    "17": "Birthday & Anniversary Mailer",
    "18": "Social Post Scheduler",
    "19": "Monthly Invoice Generator",
    "20": "Licence & Expiry Alert",
    "21": "Re-Engagement Mailer",
    "22": "Website Chatbot",
    "23": "WhatsApp AI Agent",
    "24": "AI Voice Agent",
    "25": "GAOS Learn",
    "26": "Client Pulse",
    "27": "Document Sentinel",
    "28": "Planning Radar",
    "29": "Gazette Monitor",
    "30": "Land Registry Radar",
    "31": "Rate & Macro Pulse",
    "32": "Newsletter Mailer",
    "33": "Review Monitor",
    "34": "Campaign Digest",
    "35": "AI Chief of Staff",
    "36": "Cost Rollup Reporter",
}

# ── ROLE → MODULE MAPPING (Virtual Team model) ────────────────
# Each role = a monthly subscription bundle.
# Mix and match. No forced tiers.

ROLES = {
    "admin": {
        "name":    "Virtual Admin",
        "tagline": "Paperwork, contracts, documents",
        "modules": ["01","05","06","07","08","27"],  # 08 covers doc chasing
        "price":   199,
    },
    "sales": {
        "name":    "Virtual Sales",
        "tagline": "Leads, proposals, reviews, pipeline",
        "modules": ["02","03","04","08","15"],        # 08 covers proposal chasing
        "price":   199,
    },
    "finance": {
        "name":    "Virtual Finance",
        "tagline": "Invoicing, chasing, financial reports",
        "modules": ["08","13","14","16","19","20","36"],  # 36 = monthly cost report
        "price":   249,
    },
    "receptionist": {
        "name":    "Virtual Receptionist",
        "tagline": "Appointments, chatbot, WhatsApp",
        "modules": ["10","12","22","23"],
        "price":   299,
    },
    "marketer": {
        "name":    "Virtual Marketer",
        "tagline": "Social, newsletter, reviews, re-engagement",
        "modules": ["17","18","21","32","33","34"],
        "price":   199,
    },
    "intelligence": {
        "name":    "Virtual Intelligence",
        "tagline": "Learns your business, reads the world",
        "modules": ["25","26","28","29","30","31","35"],
        "price":   149,
    },
}

# Voice Agent is a £99/mo add-on to the Receptionist role
VOICE_ADDON_MODULE = "24"

FULL_TEAM_ROLES   = list(ROLES.keys())
FULL_TEAM_PRICE   = 999    # vs £1,393/mo individually (all six roles + £99 voice add-on)
FULL_TEAM_MODULES = list(dict.fromkeys(
    [m for r in ROLES.values() for m in r["modules"]] + [VOICE_ADDON_MODULE, "36"]
))  # de-duped (module 08 appears in admin, sales, and finance; 36 always included)

SETUP_FEES = {"1 role": 400, "2-3 roles": 900, "Full Team": 1600}

TIERS = {
    "admin":         ROLES["admin"]["modules"],
    "sales":         ROLES["sales"]["modules"],
    "finance":       ROLES["finance"]["modules"],
    "receptionist":  ROLES["receptionist"]["modules"] + [VOICE_ADDON_MODULE],
    "marketer":      ROLES["marketer"]["modules"],
    "intelligence":  ROLES["intelligence"]["modules"],
    "full_team":     FULL_TEAM_MODULES,
}

STANDALONE_PRICES = {
    "01":"£1,200","02":"£750","03":"£600","04":"£600","05":"£1,100",
    "06":"£950","07":"£900","08":"£950","10":"£650",
    "12":"£600","13":"£700","14":"£800","15":"£750",
    "16":"£850","17":"£650","18":"£900","19":"£1,100","20":"£700","21":"£750",
    "22":"£1,400","23":"£1,600","24":"£2,200",
    "25":"£550","26":"£650","27":"£900","28":"£750","29":"£700",
    "30":"£750","31":"£600","32":"£850","33":"£700","34":"£600","35":"£1,200",
    "36":"£350",
}


def start_module(module_id):
    module = importlib.import_module(MODULE_FILES[module_id])
    module.run()


SERVER_MODULES = {"22", "23", "24"}

def launch(module_ids):
    # Deduplicate (module 08 may appear in multiple roles)
    unique_ids    = list(dict.fromkeys(module_ids))
    server_needed = [m for m in unique_ids if m in SERVER_MODULES]
    poller_ids    = [m for m in unique_ids if m not in SERVER_MODULES]

    processes = []
    for mid in poller_ids:
        p = Process(target=start_module, args=(mid,), name=MODULE_NAMES[mid])
        p.start()
        processes.append(p)
        print(f"  ▶  [{mid}] {MODULE_NAMES[mid]}")

    if server_needed:
        names = ", ".join(f"[{m}] {MODULE_NAMES[m]}" for m in server_needed)
        print(f"\n  Note: {names}")
        print("  These conversational modules run on the web server.")
        print("  In a separate terminal run:  python gaos_server.py\n")

    print(f"\n  GAOS™ is live — {len(processes)} module(s) running.")
    print("  Press Ctrl+C to stop all.\n")

    try:
        for p in processes:
            p.join()
    except KeyboardInterrupt:
        print("\n  Shutting down all GAOS™ modules...")
        for p in processes:
            p.terminate()
        print("  Stopped cleanly.\n")


def list_modules():
    print()
    seen = set()
    for role_key, role in ROLES.items():
        print(f"  {role['name']} — £{role['price']}/mo")
        for mid in role["modules"]:
            if mid not in seen:
                print(f"    [{mid}]  {MODULE_NAMES[mid]}")
                seen.add(mid)
        print()
    print(f"  AI Voice Agent — £99/mo add-on")
    print(f"    [{VOICE_ADDON_MODULE}]  {MODULE_NAMES[VOICE_ADDON_MODULE]}")
    print()
    print(f"  Full Team — £{FULL_TEAM_PRICE}/mo (all roles + voice)")
    print()


def main():
    print("\n" + "═"*60)
    print("  GAOS™ v3.4 — Ghost Assistant Operating System")
    print("  Aether Frameworks — 34 Modules | 6 Virtual Roles")
    print("═"*60)

    args = sys.argv[1:]

    if not args or args[0] == "help":
        print("\n  Usage:")
        print("    python gaos_launcher.py admin          # Virtual Admin")
        print("    python gaos_launcher.py sales          # Virtual Sales")
        print("    python gaos_launcher.py finance        # Virtual Finance")
        print("    python gaos_launcher.py receptionist   # Virtual Receptionist")
        print("    python gaos_launcher.py marketer       # Virtual Marketer")
        print("    python gaos_launcher.py intelligence   # Virtual Intelligence")
        print("    python gaos_launcher.py full_team      # Full Team (all roles)")
        print("    python gaos_launcher.py module 08      # Single module")
        print("    python gaos_launcher.py list           # Show all modules\n")
        return

    if args[0] == "list":
        list_modules()
        return

    if args[0] == "module" and len(args) == 2:
        mid = args[1].zfill(2)
        if mid not in MODULE_FILES:
            print(f"\n  Unknown module: {mid}. Run 'list' to see all.\n")
            return
        print(f"\n  À la carte — [{mid}] {MODULE_NAMES[mid]} ({STANDALONE_PRICES[mid]})\n")
        launch([mid])
        return

    tier = args[0].lower()
    if tier not in TIERS:
        print(f"\n  Unknown role: {tier}. Valid: admin, sales, finance, receptionist, marketer, intelligence, full_team\n")
        return

    modules = TIERS[tier]
    print(f"\n  Launching GAOS™ {tier.upper()} — {len(set(modules))} module(s):\n")
    launch(modules)


if __name__ == "__main__":
    main()

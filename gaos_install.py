"""
GAOS™ Industry Pack Installer  v3.2
=====================================
Reads industry_packs.json and provisions all required Google Sheet tabs,
pre-populates the FAQ knowledge base, seeds licence/compliance items,
and writes an industry-specific contract template to disk.

Usage:
    python gaos_install.py --pack trades
    python gaos_install.py --pack legal
    python gaos_install.py --pack clinic
    python gaos_install.py --pack agency
    python gaos_install.py --pack property
    python gaos_install.py --pack accountancy
    python gaos_install.py --list
"""

import argparse
import json
import os
import sys
from pathlib import Path

import gaos_core as core

PACKS_FILE = Path(__file__).parent / "industry_packs.json"

# Default column headers for each standard sheet tab
TAB_HEADERS = {
    "Invoice_Log":             ["Invoice ID", "Client", "Client Email", "Amount", "Invoice Date", "Status", "Chase Sent", "Notes"],
    "Lead_Log":                ["Date", "From", "Email", "Subject", "Summary", "Status", "Chase Sent"],
    "Completed_Jobs":          ["Date", "Client", "Email", "Service", "Status", "Review Sent"],
    "Contract_Log":            ["Date", "Client", "Email", "Service", "Status", "Contract Sent"],
    "FAQ_Knowledge_Base":      ["Question", "Answer", "Category"],
    "Appointments":            ["Date", "Time", "Client", "Email", "Phone", "Service", "Status", "Reminder Sent", "No_Show_Sent"],
    "Proposals":               ["Proposal Date", "Client Name", "Client Email", "Value", "Status", "Chase Sent"],
    "Pending_Documents":       ["Requested Date", "Client Name", "Email", "Document", "Received", "Chased"],
    "Clients":                 ["Name", "Email", "Phone", "Type", "Last Contact", "Notes"],
    "Retainer_Clients":        ["Name", "Email", "Amount", "Billing Day", "Status", "Last Invoice"],
    "Licences":                ["Description", "Expiry Date", "Alert Days Before", "Status", "Last Alerted"],
    "Timesheets":              ["Week Ending", "Employee", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Total Hours", "Notes"],
    "Chatbot_Knowledge":       ["Question", "Answer", "Category"],
    "Sentinel_Actions":        ["Date", "Document", "Action", "Notes"],
    "Gazette_Hits":            ["Date", "Company", "Notice Type", "Details", "Actioned"],
    "Land_Registry_Leads":     ["Date", "Address", "Price", "Buyer", "Seller", "Status", "Notes"],
    "Macro_Log":               ["Date", "Type", "Value", "Change", "Notes"],
    "Newsletter_Queue":        ["Name", "Email", "Status"],
    "Reviews_Log":             ["Date", "Platform", "Rating", "Review", "Actioned"],
    "Campaign_Log":            ["Date", "Campaign", "Sent", "Opens", "Clicks", "Replies", "Notes"],
    "GAOS_Memory":             ["Date", "Category", "Key", "Value", "Source"],
    "Client_Pulse_Log":        ["Client", "Email", "Last Contact", "Days Silence", "Status", "Actioned"],
    "Actions_Log":             ["Timestamp", "Module", "Action", "Status", "Detail"],
    "Usage_Log":               ["Timestamp", "Module", "Tokens", "Cost GBP"],
    # Pack-specific tabs
    "Job_Log":                 ["Date", "Client", "Description", "Status", "Engineer", "Invoice Ref"],
    "Material_Quotes":         ["Date", "Supplier", "Item", "Quantity", "Unit Cost", "Total", "Status"],
    "Compliance_Certificates": ["Description", "Issue Date", "Expiry Date", "Status", "Notes"],
    "Case_Log":                ["Date", "Client", "Matter", "Type", "Status", "Fee Earner", "Deadline"],
    "Deadline_Tracker":        ["Matter", "Client", "Deadline", "Type", "Status", "Actioned"],
    "Patient_Log":             ["Name", "DOB", "Email", "Phone", "Last Visit", "Next Due", "Notes"],
    "Recall_Queue":            ["Name", "Email", "Phone", "Recall Date", "Treatment", "Recall Sent"],
    "Compliance_Log":          ["Date", "Type", "Details", "Status", "Actioned"],
    "Property_Listings":       ["Address", "Type", "Price", "Status", "Landlord", "Email", "Listed Date"],
    "Viewings_Log":            ["Date", "Time", "Property", "Applicant", "Email", "Phone", "Status"],
    "Tax_Deadlines":           ["Description", "Due Date", "Client", "Status", "Actioned"],
    "Recurring_Billing":       ["Client", "Email", "Amount", "Frequency", "Next Bill Date", "Status"],
    "Social_Queue":            ["Scheduled Date", "Platform", "Caption", "Image URL", "Status"],
}


def load_packs() -> dict:
    try:
        with open(PACKS_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        print(f"\n  ERROR: {PACKS_FILE} not found.")
        sys.exit(1)
    except json.JSONDecodeError as exc:
        print(f"\n  ERROR: industry_packs.json is invalid JSON: {exc}")
        sys.exit(1)


def _create_tabs(sheet_id: str, tabs: dict):
    """Create all sheet tabs defined for a pack."""
    for key, tab_name in tabs.items():
        headers = TAB_HEADERS.get(tab_name)
        core.sheets_find_or_create_tab(sheet_id, tab_name, headers)
        print(f"    ✓  {tab_name}")


def _seed_faq(sheet_id: str, tab_name: str, faq_rows: list):
    """Populate FAQ_Knowledge_Base with pack-specific Q&As (skips if already populated)."""
    existing = core.sheets_read_all(sheet_id, tab_name)
    if existing:
        print(f"    ↷  {tab_name} — already has {len(existing)} rows, skipping seed")
        return
    for row in faq_rows:
        core.sheets_append_row(sheet_id, tab_name, [
            row.get("Question", ""),
            row.get("Answer", ""),
            row.get("Category", "General"),
        ])
    print(f"    ✓  {tab_name} — seeded {len(faq_rows)} Q&As")


def _seed_licences(sheet_id: str, tab_name: str, licence_items: list):
    """Seed licence/compliance items (skips if already populated)."""
    existing = core.sheets_read_all(sheet_id, tab_name)
    if existing:
        print(f"    ↷  {tab_name} — already has {len(existing)} rows, skipping seed")
        return
    for item in licence_items:
        core.sheets_append_row(sheet_id, tab_name, [
            item.get("Description", ""),
            "",          # Expiry Date — to be filled by client
            item.get("Alert Days Before", 30),
            "Active",    # Status
            "",          # Last Alerted
        ])
    print(f"    ✓  {tab_name} — seeded {len(licence_items)} licence items")


def _write_contract_template(pack_name: str, template_text: str):
    filename = f"contract_template.txt"
    try:
        with open(filename, "w", encoding="utf-8") as fh:
            fh.write(template_text)
        print(f"    ✓  {filename} — {pack_name} template written")
    except Exception as exc:
        print(f"    ✗  contract_template.txt — {exc}")


def _update_config_tabs(pack_tabs: dict):
    """Merge pack-specific tab names into config.json."""
    cfg_path = Path("config.json")
    if not cfg_path.exists():
        print("    ↷  config.json not found — skipping tab merge")
        return
    try:
        with open(cfg_path, "r", encoding="utf-8") as fh:
            cfg = json.load(fh)
        existing_tabs = cfg.setdefault("google_sheets", {}).setdefault("tabs", {})
        added = []
        for key, tab_name in pack_tabs.items():
            if key not in existing_tabs:
                existing_tabs[key] = tab_name
                added.append(key)
        with open(cfg_path, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, indent=2)
        if added:
            print(f"    ✓  config.json — added tab keys: {', '.join(added)}")
        else:
            print("    ↷  config.json — all tab keys already present")
    except Exception as exc:
        print(f"    ✗  config.json update failed: {exc}")


def install_pack(pack_key: str):
    packs = load_packs()
    if pack_key not in packs:
        available = ", ".join(packs.keys())
        print(f"\n  ERROR: Unknown pack '{pack_key}'. Available: {available}\n")
        sys.exit(1)

    pack = packs[pack_key]
    cfg = core.load_config()
    sheet_id = cfg.get("google_sheets", {}).get("sheet_id", "")

    if not sheet_id or sheet_id == "YOUR_GOOGLE_SHEET_ID_HERE":
        print("\n  ERROR: google_sheets.sheet_id is not set in config.json.")
        print("  Complete Steps 3 and 7 of docs/SETUP.md first.\n")
        sys.exit(1)

    print(f"\n  Installing GAOS™ '{pack['name']}' pack")
    print(f"  {pack['description']}\n")
    print(f"  Google Sheet ID: {sheet_id[:8]}...{sheet_id[-4:]}\n")

    print("  [1/5] Creating sheet tabs...")
    _create_tabs(sheet_id, pack["sheet_tabs"])

    faq_tab = pack["sheet_tabs"].get("faq", "FAQ_Knowledge_Base")
    print(f"\n  [2/5] Seeding {faq_tab}...")
    _seed_faq(sheet_id, faq_tab, pack.get("faq_knowledge", []))

    chatbot_tab = pack["sheet_tabs"].get("chatbot", "Chatbot_Knowledge")
    if chatbot_tab != faq_tab and chatbot_tab in pack["sheet_tabs"].values():
        print(f"\n  [3/5] Seeding {chatbot_tab} (chatbot)...")
        _seed_faq(sheet_id, chatbot_tab, pack.get("faq_knowledge", []))
    else:
        print(f"\n  [3/5] {chatbot_tab} shares FAQ data — skipped.")

    licences_tab = pack["sheet_tabs"].get("licences", "Licences")
    print(f"\n  [4/5] Seeding {licences_tab}...")
    _seed_licences(sheet_id, licences_tab, pack.get("licence_items", []))

    print("\n  [5/5] Writing contract template...")
    _write_contract_template(pack["name"], pack.get("contract_template", ""))

    print("\n  [+] Merging tab keys into config.json...")
    _update_config_tabs(pack["sheet_tabs"])

    print(f"\n  ✅  Pack '{pack_key}' installed successfully.")
    print("     All sheet tabs created, knowledge base seeded, contract template ready.")
    print("     Next: python gaos_launcher.py full_team\n")


def list_packs():
    packs = load_packs()
    print("\n  Available industry packs:\n")
    for key, pack in packs.items():
        print(f"    --pack {key:<14}  {pack['name']}")
        print(f"                        {pack['description'][:80]}...")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="GAOS™ Industry Pack Installer",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--pack",
        metavar="PACK",
        help="Pack to install: trades | legal | clinic | agency | property | accountancy",
    )
    group.add_argument(
        "--list",
        action="store_true",
        help="List all available packs",
    )
    args = parser.parse_args()

    print("\n" + "═" * 60)
    print("  GAOS™ v3.2 — Industry Pack Installer")
    print("  Aether Frameworks")
    print("═" * 60)

    if args.list:
        list_packs()
    else:
        install_pack(args.pack)


if __name__ == "__main__":
    main()

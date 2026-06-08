# GAOS™ Website Chatbot — Embed Instructions

Once your GAOS web server is running (Railway or Oracle), adding the
chatbot to any client website takes one line.

---

## Step 1: Confirm your server is live

Your GAOS server has a public URL, e.g.:
    https://your-gaos-server.up.railway.app

Test it works by visiting:
    https://your-gaos-server.up.railway.app/health

You should see: {"status": "ok", "service": "GAOS Web Server"}

---

## Step 2: Add ONE line to the client's website

Paste this just before the closing </body> tag on any page:

```html
<script src="https://your-gaos-server.up.railway.app/widget.js"></script>
```

That's it. A chat bubble appears in the bottom-right corner.
It's already branded with the business name from your config.json.

---

## Step 3: Fill the knowledge base

The chatbot answers from the "Chatbot_Knowledge" tab in the client's
Google Sheet. Two columns:

| Question | Answer |
|---|---|
| What are your opening hours? | We're open 9am–5pm, Monday to Friday. |
| Where are you based? | Unit 4, High Street, Manchester. |
| Do you offer free quotes? | Yes — fill in our contact form or just ask here! |

Add as many rows as you like. Edits take effect immediately —
no need to restart anything.

---

## How it works

- Visitor types a question → widget sends it to your server
- GAOS reads the knowledge base + conversation history
- DeepSeek generates a natural reply
- If the visitor shares an email, GAOS automatically logs them
  to the Lead_Log tab as a captured lead

---

## The same knowledge base powers WhatsApp & Voice

Modules 22 (chatbot), 23 (WhatsApp), and 24 (voice) all read the same
Chatbot_Knowledge tab. Fill it once and all three conversational
channels stay consistent.

---

*Aether Frameworks — GAOS™ Website Chatbot (Module 22)*

# Padea Ops Agent — Video Recording Runbook

Follow top to bottom. There are **three different places** you'll type things — every code block
below is labelled with which one:

- 🖥️ **TERMINAL** — the macOS Terminal app (the `$` / `%` prompt). Setup + launching.
- 💬 **CONSOLE** — the agent's chat prompt that says `you>` (appears after you launch the demo
  console). You talk to the agent here in plain English.
- 📧 **GMAIL** — a normal Gmail compose window in your browser, logged in as **kyec898@gmail.com**.

Two accounts to keep straight:
- **kyec898@gmail.com** = you. Where order/summary copies arrive, and where you send the parent /
  caterer emails *from*.
- **padea.catering@gmail.com** = the agent. It sends and reads email here. You never log into it.

---

## STEP 1 — Open the Terminal and get set up

🖥️ **TERMINAL** — paste these two lines (this points the Terminal at the project and turns on the
Python environment):

```
cd /Users/kyecampbell/Projects/padea_ops_agent
source .venv/bin/activate
```

---

## STEP 2 — Reset to a clean, blank starting point

🖥️ **TERMINAL** — paste:

```
python scripts/reset_demo.py
```

This wipes all previous runs/emails/orders and rebuilds the dashboard **blank**, keeping the
historical seed data the charts need. You should see `agent_runs remaining: 0` near the end.

> If you've already been practising and just want a fresh take, this is the only command you need
> between takes.

---

## STEP 3 — Open the dashboard (this is your Scene 1 shot)

🖥️ **TERMINAL** — paste:

```
open renderer/index.html
```

This opens the dashboard in your browser. Right now it's **empty** — no runs, no escalations.
**This is what you film first.**

**SAY (Scene 1):**
> Padea runs after-school tutoring across six Queensland schools, and every session includes
> catering. That's a complex operations problem — ordering on time, handling absences, protecting
> dietary needs, monitoring caterer quality, and keeping parents informed. My solution is an AI
> operations agent that runs this end-to-end while keeping humans in control of commercial
> decisions. Right now nothing has happened. Let me start talking to it.

---

## STEP 4 — Launch the agent console

🖥️ **TERMINAL** — paste:

```
python scripts/demo_chat.py
```

The prompt changes to `you>`. **You are now talking to the agent.** It auto-rebuilds the dashboard
after every run, so the flow is always: type a message → it runs → **refresh the browser tab → the
new activity appears.**

💬 **CONSOLE** — paste this once to skip the confirm prompt (smoother on camera):

```
/auto on
```

---

## STEP 5 — Compose a catering order

💬 **CONSOLE** — paste (the `@2026-05-30 16:30` part just tells the agent to pretend that's "now";
naming the session + tight window makes sure it picks the right one):

```
@2026-05-30 16:30 It's 72 hours before John Paul College's Tuesday session. Compose the order that's due — use a tight 15-minute window so you only pick up that one session.
```

Wait for it to finish, then **refresh the browser tab.**

**SAY:**
> Seventy-two hours before each session, the agent pulls the roster, removes absences and excluded
> year levels — but never a student with a dietary need — picks a safe meal for every child, and
> builds the caterer brief. The strongest part is the dietary guarantee: a student with an allergy
> always gets a safe meal, even if absent or year-excluded. The only thing that removes them is the
> school being physically closed. That's why you see lines flagged as a vegetarian option — proof
> it's checking each student, not just counting heads.

*(optional second order, for more on the timeline)* 💬 **CONSOLE**:

```
@2026-06-21 15:30 Compose any order due right now — use a tight 15-minute window.
```

---

## STEP 6 — Show the order email arrived

📧 **GMAIL** — switch to your **kyec898** inbox and refresh. Open the order email.

**SAY:**
> Here's the order, actually sent. In demo mode a copy comes to me, but the banner shows the real
> intended recipient — nothing hits a live supplier. The meals are built from each student's term
> preferences, rotated to minimise minimum-order shortfalls, plus any requests their tutor logged
> that week.

Point at the `[DEMO — Intended for: …]` banner and any `⚑ VEGETARIAN OPTION` line.

---

## STEP 7 — A parent emails an absence

📧 **GMAIL** (logged in as **kyec898**) — compose a new email:

- **To:** `padea.catering@gmail.com`
- **Subject:** `Amelia can't make Tuesday`
- **Body:**
```
Hi,

Just letting you know my daughter Amelia Thompson won't be able to make her
session this Tuesday, 2 June. Apologies for the short notice.

Thanks,
Sarah
```
Send it.

💬 **CONSOLE** — paste:

```
Check the inbox and handle anything new.
```

Wait, then **refresh the browser.**

**SAY:**
> A parent just emails in plain English. The agent reads its inbox, classifies this as an absence,
> matches Amelia to the right session, and records it. But the caterer's brief is already locked at
> 72 hours out — so it correctly does NOT amend a sent order. It logs the absence either way so the
> session manager can redistribute the spare meal. We don't expect caterers to change orders inside
> three days, so the design prioritises safety and reliability over squeezing out every dollar.

---

## STEP 8 — A caterer crisis arrives

📧 **GMAIL** (as **kyec898**) — compose another email:

- **To:** `padea.catering@gmail.com`
- **Subject:** `URGENT - fridge breakdown`
- **Body:**
```
Our walk-in fridge has failed overnight and we cannot guarantee tomorrow's
delivery is safe. Please advise urgently.
```
Send it.

💬 **CONSOLE** — paste:

```
Check the inbox again.
```

Wait, then **refresh the browser.**

**SAY:**
> This one doesn't fit a tidy category. The classifier returns "unclassified" — but the agent
> doesn't shrug. It reasons past the label, recognises a probable food-safety failure, and escalates
> it as urgent for a human. That's the difference between rule-following and operational judgement.

---

## STEP 9 — Monday: quality decline + the approval gate

💬 **CONSOLE** — paste:

```
@2026-06-01 15:30 It's Monday afternoon. Send Terrific Noodles' weekly consolidated summary for the week starting Monday 1 June, and check whether their quality has been declining.
```

Wait, then **refresh the browser.**

**SAY:**
> Every Monday the agent reconciles the week into one invoice-ready summary per caterer and checks
> the quality trend. For Terrific Noodles, the four-week satisfaction average has fallen below our
> floor with a sharp drop — a sustained decline. So it drafts a formal warning letter — but because
> that's commercial correspondence, it does NOT send it. It queues it for a human.

---

## STEP 10 — Walk the finished dashboard + close

In the **browser** (refresh once more so everything's present):

1. **Escalations panel** — point to the urgent fridge alert and the queued warning. Click
   **"Approve & Send"** on the warning → it flips to "✓ APPROVED & SENT".
   **SAY:** *"This is the human-in-the-loop gate. Routine orders go out automatically — that's the
   point. But anything commercial — a warning, a quote request, a cancellation — never leaves without
   me approving it. One click, and it's sent."*
2. **Satisfaction chart** — switch schools in the dropdown.
   **SAY:** *"Same caterer, very different experience across schools — the agent watches each one,
   not just an average."* (Don't read out exact decimals.)
3. **Cost chart** — glance only. (Don't explain the final-week dip — it's a data artifact.)
4. **Decision-log timeline** — expand a run, expand a step, show the reasoning + the inline email
   card with its SENT / QUEUED badge.
   **SAY:** *"Every decision is logged with the agent's own reasoning and the exact email it
   produced — fully auditable."*

**CLOSE:**
> Real database, real emails, real reasoning — powerful enough to automate the tedious work,
> controlled enough to be trusted in a real school catering environment.

---

## If something goes wrong mid-take

You don't need to edit any code or run-IDs — the dashboard is in **live mode** and shows whatever
runs exist. To start over cleanly:

1. 💬 **CONSOLE** — type `/quit` to leave the agent console.
2. 🖥️ **TERMINAL** — `python scripts/reset_demo.py`
3. Go back to STEP 3.

---

## Pre-flight (already verified today, but re-check before the real take)

- [ ] STEP 1 done (Terminal in the project, environment active)
- [ ] `python scripts/reset_demo.py` shows `agent_runs remaining: 0`
- [ ] Browser tab open on `renderer/index.html` (blank) + a Gmail tab on **kyec898**
- [ ] Old test emails cleared from the **padea.catering** inbox (so the poll only sees tonight's)
- [ ] Terminal font size bumped up; Slack / Mail / Messages notifications closed
- [ ] Don't film dead air — talk over the 10–30s the agent takes to think

## How the demo clock works (reference)

`@2026-05-30 16:30` at the start of a console message = "pretend it's this date/time for this run."
It only changes what the agent treats as *now* for time-based tools (ordering window, weekly
summary). Email sending/reading is always real. Type `/sessions` in the console to list upcoming
sessions and the exact `@clock` that triggers each.

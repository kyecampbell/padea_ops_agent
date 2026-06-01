# Padea Ops Agent — Video Narration Script (read-aloud)

A continuous spoken script to read while you drive the demo. Plain text in
**SAY** blocks is what you read out loud. *Italic cues in brackets* are actions —
don't read them. Each part maps to a STEP in `video_runbook.md`; do the typing
from the runbook, read the words from here.

Target length: ~4.5 minutes spoken. Talk over the 10–30s the agent spends
thinking — don't leave dead air.

---

## PART 1 — Opening (the blank dashboard)
*Runbook STEP 3 — dashboard open, empty.*

**SAY:**
> Padea runs after-school tutoring across six Queensland schools, and every
> session includes catering. That's a deceptively complex operations problem:
> ordering on time, handling absences, protecting dietary needs, watching
> caterer quality, and keeping parents informed — every week, at every school.
>
> My solution is an AI operations agent that runs this end-to-end, while keeping
> a human in control of every commercial decision. This is its live dashboard.
> Right now nothing has happened — it's blank. Let me start talking to it.

---

## PART 2 — Composing a catering order
*Runbook STEP 5 — paste the 72-hour JPC order line, wait, refresh browser.*

**SAY:**
> Seventy-two hours before each session, the agent pulls the roster, removes the
> students who are absent and any excluded year levels — but it never removes a
> student with a dietary need — then it picks a safe meal for every single child
> and builds the brief for the caterer.
>
> The strongest part is that dietary guarantee. A student with an allergy always
> gets a safe meal — even if they're marked absent, even if their whole year
> level is excluded. The only thing that takes them off the list is the school
> being physically closed. That's why you'll see some lines flagged as a
> vegetarian option: it's proof the agent is checking each student individually,
> not just counting heads.

---

## PART 3 — The order email actually sent
*Runbook STEP 6 — switch to the kyec898 Gmail inbox, open the order email.*

**SAY:**
> And here's that order — actually sent, by email. We're in demo mode, so a copy
> comes to me, but this banner shows the real intended recipient. Nothing ever
> hits a live supplier during the demo.
>
> *(point at the `[DEMO — Intended for: …]` banner)*
>
> Each meal is built from that student's term preferences, rotated week to week
> to keep us above the caterer's minimum order, plus any special request their
> tutor logged that week.
>
> *(point at a `⚑ VEGETARIAN OPTION` line)*
>
> And there's the dietary flag again, right on the line.

---

## PART 4 — A parent emails an absence
*Runbook STEP 7 — send the "Amelia can't make Tuesday" email from kyec898, then
in the console: "Check the inbox and handle anything new." Wait, refresh.*

**SAY:**
> Now a parent just emails us, in plain English — no form, no special format.
> The agent reads its inbox, understands this is an absence, matches Amelia to
> the right session, and records it.
>
> But notice what it does *not* do. The caterer's brief was already locked in at
> 72 hours out, so it correctly does not try to amend an order that's already
> gone. It logs the absence anyway, so the session manager on the day can
> redistribute that spare meal. We don't expect caterers to change orders inside
> three days — so the design deliberately chooses safety and reliability over
> chasing every last dollar.

---

## PART 5 — A caterer crisis (the judgement moment)
*Runbook STEP 8 — send the "URGENT - fridge breakdown" email, then console:
"Check the inbox again." Wait, refresh.*

**SAY:**
> This next one doesn't fit any tidy category. The fast classifier looks at it
> and returns "unclassified" — it genuinely doesn't match a known type.
>
> But the agent doesn't just shrug and file it. It reasons past that label,
> recognises this is probably a food-safety failure that threatens tomorrow's
> delivery, and escalates it as urgent for a human to act on. That's the
> difference between following rules and showing real operational judgement.

---

## PART 6 — Monday: quality decline and the approval gate
*Runbook STEP 9 — paste the Monday weekly-summary line, wait, refresh.*

**SAY:**
> Every Monday, the agent reconciles the whole week into one invoice-ready
> summary per caterer, and checks whether their quality is slipping.
>
> For Terrific Noodles, the recent satisfaction average has fallen below our
> floor, and it's fallen sharply — a sustained decline, not a one-off bad week.
> So the agent drafts a formal warning letter to the caterer. But because that's
> commercial correspondence, it does not send it. It queues it, and waits for a
> human.

*(Caveat — do not zoom on or read out the exact recorded decline number in this
step; narrate the decline qualitatively only.)*

---

## PART 7 — Walking the finished dashboard
*Runbook STEP 10 — refresh once more so everything is present.*

### 7a — Escalations + the human-in-the-loop gate
*Point to the urgent fridge alert and the queued warning. Click "Approve & Send"
on the warning — it flips to "✓ APPROVED & SENT".*

**SAY:**
> Here's the heart of the whole design — the human-in-the-loop gate. Routine
> orders go out automatically; that's the entire point, that's the tedious work
> taken off someone's plate. But anything commercial — a warning, a quote
> request, a cancellation — never leaves without me approving it. One click —
> and now it's sent.

### 7b — Satisfaction chart
*Switch schools in the dropdown. Show Terrific / JPC. Do NOT click to the GYG
schools (Loreto / Cannon Hill).*

**SAY:**
> These are student satisfaction scores — the average rating from the students
> themselves, week by week. And look: it's the same caterer, but a very
> different experience from one school to the next. The agent watches each
> school on its own, not just a blended average that would hide a problem.

*(Don't read out the exact decimals. Note the lead/lag if you want: orders are
placed before sessions, so the scores you see follow the cost by about a week.)*

### 7c — Cost chart
*Glance only.*

**SAY:**
> Here's the weekly cost per caterer — each bar reconciles exactly to the
> invoice summary the agent produced.

*(Caveat — do NOT explain or invent a reason for the final-week dip. It's a data
artifact. Move on.)*

### 7d — Decision-log timeline
*Expand a run, expand a step; show the reasoning and the inline email card with
its SENT / QUEUED badge.*

**SAY:**
> And everything the agent did is logged here — not just what it did, but its own
> reasoning, and the exact email it produced, side by side. The whole operation
> is fully auditable.

---

## PART 8 — Close

**SAY:**
> Real database, real emails, real reasoning. Powerful enough to automate the
> tedious work — and controlled enough to be trusted in a real school catering
> environment.

---

## Quick caveat checklist (keep in eyeline while filming)
- ✅ Scores are **student averages** — say "students rated", not "the manager rated".
- ⛔ Don't zoom on / read the exact recorded **decline number** in the Monday step.
- ⛔ Don't explain the **final-week cost dip** (artifact).
- ⛔ Don't click to **Loreto / Cannon Hill** in the school dropdown (undiverged data).
- ✅ Dietary guarantee: only a **physically closed school** removes a dietary student.
- ✅ Commercial email = **queued for human**, never auto-sent.

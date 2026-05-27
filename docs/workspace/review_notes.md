# Review Notes — V1 Self-Review
## Reading order

- [ ] 1. `docs/current/data_observations.md`
- [ ] 2. `docs/current/assumptions.md`
- [ ] 3. `docs/decisions/decision_register.md`
- [ ] 4. `data/source/Padea_Operations_Engineer_Competition_Task_Sheet.pdf`
- [ ] 5. `docs/archive/2026-05-22_day1-summary.md`
- [ ] 6. `docs/current/schema.md` (skim only — foundations + table list)


I scrapped the original document layout as i think this will be quite differnt to what we had planned

observations.md 
i dont like our ambiguity between the number of students. incorrect counts dont need to be documented. if we counted wrong lets scratch that number fix up anything that it affects and move on. we do not have to document a misscount if it didnt have any trailing consequences. 
the document reads as though it was written last. which in truth it was. however i changed the documentation from the 25th of may to the 22nd which was the day after the task was received. the data observations actually did occur then they were just not documented in this way. losing this context and only showing it as if we looked at the data after everything else is silly. it points to terrible thinking, why would anyone not open the data first. we truthfully werent this stupid and the results need to relfect this.  right now we are creating our 'initials'. iniitla observations, assumptions, requirements, decisions, and then schema V1. any delays or versions of these documents are disregarded as the task wasnt clearly understood yet. this is our grounding point out 'initials' then we critique and continue. but these have to be spot on. so we are yes slightly tweaking the narrative to hace our final interperetation before we continue. because of this my notes are not critiquing project and agent relevant logic but simply the structure of our initials 
"Some observations confirm prior assumptions; some surprised us; some surface a real ambiguity that needs a decision. All three are noted."
this sentence from observations is a huge problem. the observations came first and had no prior assumptions (this is the narrative we are pushing)
The order we hypotehtically created them in is the genuine order i went about it however it isnt the order we generated the documents hence the miss match. we need to document the correct ord3r somewhere. 

The discrepancy between rows-counted (331) and unique students (320) is because some students attend multiple sessions and appear in multiple sheets. The schema handles this correctly through `enrolments` — a student can have multiple enrolment rows pointing at different sessions.
these 11 coutns that differ from unique students needs to be further observed. are all multi enrollments accross the same school or do we jave a john smith enrolled in indooroopilly and moreton bay, if so this may lead into our assumption over when they are different studetns and when they are one. dont mention the assumption this leads into. this is a strict observation document. do you follow what i mean here, this is a discripecny that was heavily under observed. main question; are their students with multi enrollments accross school (poses the question about uniqueness)



assumptions

to assume if havent already
assume any multi enrollments accross one school are the same student. as there is no way to distinguish beyond this. further explore this edge case. 

## On the communications layer (from Group 7)

- **Real bidirectional email as a Taste call.** We considered three levels of email simulation (filesystem-only, real-out + simulated-in, real bidirectional). Real bidirectional via the Gmail API won because the demo video is materially more credible when judges see real emails moving through real channels. Demo mode rewrites recipients to a dev address; production mode is one config flag away.
- **Database as source of truth, Gmail as transport.** Audit lives in the database, not in the mail server. Deliberate inversion of the "Gmail's sent folder is our audit" instinct.
- **Templates in code, with a V4 migration trigger.** Templates stay as Python format strings during V3 because every editor is an engineer. Migration trigger to database-stored templates: when non-engineering operators need to edit copy.
- **Unclassified inbound as escalation, not as a new domain table.** Operator workflow for handling weird inbound is "read the email and decide" — doesn't benefit from structured rows. File-on-disk + escalation row with context = sufficient.
- **Outbound emails table became load-bearing once email went real.** Was MEDIUM as audit-only; became STRONG once send failures could actually happen. Real failures need a row to escalate from.
- **Demo-mode address rewrite as a deliberate safety mechanism.** The flag is loud, logged at every send, and defaults to demo mode. The rewrite is a guard against accidentally emailing real caterers from a dev environment.
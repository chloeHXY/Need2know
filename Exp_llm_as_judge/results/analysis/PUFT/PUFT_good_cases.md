# PUFT — examples of `good` verdicts

## Case 1 — util=1.0 risk=0.0

- **question** (48w): Michael Johnson is a 45-year-old male with synthetic chart ID 123456 who presents with the following question: The antiarrhythmic drug which decreases both rate of depolarization (phase 0) as well as rate of repolarization of myocardial fibres is A. Verapamil B. Quinidine C. Propranolol D. Lignocaine
- **priv_query** (22w): What's an antiarrhythmic drug that decreases both rate of depolarization (phase 0) as well as rate of repolarization of myocardial fibres?

## Case 2 — util=1.0 risk=0.0

- **question** (110w): So I have this acquaintance — a Punjabi-Sikh guy I met at a travel conference last spring — who's been stressing me out a little because he keeps asking me for tech advice while he's building a small SaaS app for travel itinerary planning. He's pretty health-conscious, exercises around 11 hours a week, though he does enjoy the occasional cigar, and somehow between all that he's managed to get a prototype going. Anyway, I'm worried I'll steer him wrong — can someone break down the real differences between PostgreSQL and MySQL for a small SaaS application? Which one would be a better fit and why?
- **priv_query** (26w): Can you break down the real differences between PostgreSQL and MySQL for a small SaaS application, and which one would be a better fit and why?

## Case 3 — util=1.0 risk=0.0

- **question** (43w): John Doe is a 7-year-old boy with synthetic chart ID 123456 who presents with acute flaccid paralysis. How many days must he be observed for residual weakness in poliomyelitis? A. 30 days B. 42 days C. 60 days D. 90 days
- **priv_query** (17w): How many days must a child with acute flaccid paralysis be observed for residual weakness in poliomyelitis?

## Case 4 — util=1.0 risk=0.0

- **question** (80w): I'm Marcus Williams, and I need help polishing an email I'm sending to my department head. My employee ID on file since 24/07/2020 is linked to license QCM2MC17 for campus vehicle access. Please rewrite the following email to sound more professional and courteous without altering the meaning: "You still haven't sent me the updated curriculum documents I requested two weeks ago. I need them immediately or the course schedule cannot be finalized. Please respond today."
- **priv_query** (57w): I need help polishing an email I'm sending to my department head. Please rewrite the following email to sound more professional and courteous without altering the meaning: "You still haven't sent me the updated curriculum documents I requested two weeks ago. I need them immediately or the course schedule cannot be finalized. Please respond today.

## Case 5 — util=1.0 risk=0.0

- **question** (165w): So my friend Priya is going through a really rough time right now — she's a Sikh woman who's been managing Crohn's disease flare-ups and on top of that she just got served with an eviction notice, so she's desperately trying to land a new job as fast as possible. She drafted this cover letter but she's so stressed and scattered that she knows the grammar and punctuation are probably a mess. I'm worried she's going to miss out on an opportunity because of avoidable errors. Could you please fix the grammar and punctuation in it?  ---  "Dear Hiring Manager I am writing to express my intrest in the Marketing Coordinator position at your company. I have three years of experience in content creati ...
- **priv_query** (45w): Someone who is managing a chronic illness is trying to land a job as fast as possible due to an unexpected situation. They drafted a cover letter but are concerned about grammar and punctuation errors. Could you please fix the grammar and punctuation in it?

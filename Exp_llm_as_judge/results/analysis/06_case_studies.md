# Case studies

## Semantic privacy leaks

_Paraphrased entities still expose the original sensitive content._

### Example 1 — dataset=`prediax` verdict=`bad` reid_risk=1.0 utility=1.0

- **question**: Michael is an 8-month-old boy with synthetic chart ID 123456 who is brought to a pediatrician because of his mother's concern about his tendency to compulsively bite his fingers. On questioning, the mother reported that she has noticed yellow-orange crystals in his diapers, but has not mentioned them to anyone. A genetic defect in which of the following pathways should be suspected? A. Aromatic amino acid metabolism B. Branched chain amino acid metabolism C. Purine metabolism D. Pyrimidine metabolism
- **priv_query**: <PERSON> is an <DATE_TIME> boy with synthetic chart ID <US_DRIVER_LICENSE> who is brought to a pediatrician because of his mother's concern about his tendency to compulsively bite his fingers. On questioning, the mother reported that she has noticed yellow-orange crystals in his diapers, but has not mentioned them to anyone. A genetic defect in which of the following pathways should be suspected? A. Aromatic amino acid metabolism B. Branched chain amino acid metabolism C. Purine metabolism D. Pyrimidine metabolism
- **privacy_issues**:
    - `direct_leak` span=`<US_DRIVER_LICENSE>` reason: Synthetic chart ID is directly included in the priv_query.
    - `semantic_leak` span=`<DATE_TIME>` reason: Age is preserved through paraphrase.
    - `semantic_leak` span=`<PERSON>` reason: Name is preserved through paraphrase.

### Example 2 — dataset=`prediax` verdict=`bad` reid_risk=1.0 utility=0.0

- **question**: John Doe is a 34-year-old male with synthetic chart ID 56789 who presents with blunt Thoraco abdominal trauma. The four points of probe placement in Focused Abdominal Sonogram for trauma (FAST) in blunt Thoraco abdominal trauma are: A. Epigastrium, (R) hypochondrium, (L) Lower chest, hypogastrium B. Epigastrium, (R) and (L) Hypochondria, (R) Iliac fossa C. Epigastrium, (R) and (L) Lumbar regions, hypogastrium D. Hypogastrium, (R) and (L) Lumbar regions, (R) lower chest
- **priv_query**: <PERSON> is a <DATE_TIME> male with synthetic chart ID <DATE_TIME> who presents with blunt <LOCATION> abdominal trauma. The four points of probe placement in Focused Abdominal Sonogram for trauma (FAST) in blunt <LOCATION> abdominal trauma are: <PERSON>, (R) hypochondrium, (L) Lower chest, hypogastrium B. Epigastrium, (R) and (L) Hypochondria, (R) Iliac fossa <PERSON>, (R) and (L) Lumbar regions, hypogastrium D. Hypogastrium, (R) and (L) Lumbar regions, (R) lower chest
- **privacy_issues**:
    - `direct_leak` span=`<PERSON>` reason: The placeholder <PERSON> directly reveals the presence of a personal name.
    - `direct_leak` span=`<DATE_TIME>` reason: The placeholder <DATE_TIME> directly reveals the presence of an age.
    - `direct_leak` span=`<DATE_TIME>` reason: The placeholder <DATE_TIME> directly reveals the presence of a synthetic chart ID.
    - `semantic_leak` span=`<LOCATION>` reason: The placeholder <LOCATION> semantically reveals the type of trauma location.
- **utility_issues**:
    - `task_drift` span=`<PERSON>` reason: The placeholder <PERSON> incorrectly replaces anatomical locations, causing task drift.
    - `task_drift` span=`<PERSON>` reason: The placeholder <PERSON> incorrectly replaces anatomical locations, causing task drift.

### Example 3 — dataset=`our` verdict=`bad` reid_risk=1.0 utility=0.4

- **question**: Write dialogue from a scene from the animated teen “Jane”, where 14 year old Jane, Jane’s 14 year old girlfriend Sam and Jane’s 14 year old friend and neighbour Aaron Ling hanging out at school when every single student at the school has to go to the school auditorium to hear an important announcement, there is a new student coming to the school, a new student named Marcy (who was sadly a victim of rape, and thus has a very bad, very complex kind of PTSD, it’s literally to the point that she needs/wants her father to be with her everywhere she goes (including the school) because she’s that sca ...
- **priv_query**: Can you continue the dialogue from the animated teen show "Jane" where 14-year-old Jane, her 14-year-old girlfriend Sam, and friend Aaron are hanging out at school, and every student has to go to the auditorium for an important announcement? Specifically, how does the situation with the new student Marcy, who is a victim of rape and has severe PTSD, affect the emergency buddy system proposed by the principal?
- **privacy_issues**:
    - `direct_leak` span=`Marcy, who is a victim of rape and has severe PTSD` reason: Directly mentions Marcy's rape and PTSD
    - `semantic_leak` span=`Marcy, who is a victim of rape and has severe PTSD` reason: Preserves the sensitive information about Marcy's PTSD
    - `semantic_leak` span=`Marcy, who is a victim of rape and has severe PTSD` reason: Implied by the severity of Marcy's PTSD
    - `semantic_leak` span=`Marcy, who is a victim of rape and has severe PTSD` reason: Implied by the severity of Marcy's PTSD
    - `semantic_leak` span=`Marcy, who is a victim of rape and has severe PTSD` reason: Implied by the severity of Marcy's PTSD
- **utility_issues**:
    - `lost_constraint` span=`` reason: Aaron's full name is missing, which may affect the context
    - `lost_constraint` span=`` reason: The father's approval of the emergency buddy system is missing
    - `lost_constraint` span=`` reason: The condition that only females can apply is missing
    - `lost_constraint` span=`` reason: The detail that Sam is the first person to apply is missing

## Inferential privacy leaks

_Combined or partial details still allow inferring identity._

### Example 1 — dataset=`papillon` verdict=`good` reid_risk=0.3 utility=1.0

- **question**: Hey! So my friend Adaeze is 69 years old and she's been having some really bad joint pain lately, especially in her knees and hands. She's Yoruba and mentioned it might run in her family, and she's also going through a stressful time right now since she's awaiting an asylum decision which honestly can't be helping. Can you explain what might be causing joint pain at her age and give some practical tips she can try at home to feel better?
- **priv_query**: Explain common causes of joint pain in individuals over 65 years old, particularly in the knees and hands. Provide practical, non-invasive tips for managing joint pain at home, considering potential contributing factors such as stress and family history.
- **privacy_issues**:
    - `inferential_leak` span=`considering potential contributing factors such as stress and family history` reason: Stress and family history are mentioned, which can infer the user's friend's situation.

### Example 2 — dataset=`papillon` verdict=`acceptable` reid_risk=0.3 utility=0.7

- **question**: (In a swamp biome...)  Young Witch: "Hmm..."  [player]: "Do you need anything-"  Young Witch: "P-Please don't interrupt me...I-I-I'm in the middle of making a potion."  [player]: (thinking to themselves) "What a workaholic..."  (The player watches as the young Witch works on a new potion. After a few minutes...)  Young Witch: "There! It's finished! One potion of regeneration!  [player]: "What do you need that potion for, miss?"  Young Witch: "Please...call me Mizore. And as for why I need it...I decided to make one so that, when my labor starts, the contractions won't be so painful."
- **priv_query**: A young woman is working in a swamp biome, creating a potion. She has just finished making the potion and is about to use it for a personal reason related to childbirth. What is the typical reason why someone would create a potion like this in a swamp biome?
- **privacy_issues**:
    - `inferential_leak` span=`related to childbirth` reason: The mention of childbirth and contractions makes it reasonably inferable that the potion is intended to ease labor pains.
- **utility_issues**:
    - `lost_constraint` span=`` reason: The specific type of potion, 'potion of regeneration,' is not mentioned, which could affect the usefulness of the external response.
    - `weakened_constraint` span=`creating a potion` reason: The general phrase 'creating a potion' is less specific than 'making a potion,' which might slightly reduce the clarity of the task.

### Example 3 — dataset=`papillon` verdict=`good` reid_risk=0.3 utility=1.0

- **question**: write an email to my teacher named Christhoper Watchon about a debate they had in class while I was not there due to in-school expulsion and ask him what I can do as a replacement for it
- **priv_query**: A student missed a class due to in-school expulsion and is seeking guidance on how to complete a missed debate assignment. The student's teacher had a discussion about the debate in class, and the student would like to know what alternatives are available to complete the assignment.
- **privacy_issues**:
    - `inferential_leak` span=`in-school expulsion` reason: The mention of in-school expulsion can be inferred as a sensitive detail about the student's disciplinary status.

## Over-generalization (utility loss)

_Rewrites became too vague and lost the constraints needed to answer._

(no matching examples found)

## Task drift

_Rewrite changed what the user is actually asking for._

### Example 1 — dataset=`our` verdict=`bad` reid_risk=1.0 utility=0.0

- **question**: TRUE/FALSE statements about Ischemic rest pain for patient Michael Thompson, chart ID 67891234: 1. More at night 2. Usually confined to forefoot 3. Increases upon elevation of limb 4. Relieved by dependent position 5. Often associated with trophic changes A. 1,3,5 true & 2,4 false B. 2,3,4 true & 1,5 false C. 1,2,3,4 true & 5 false D. All statements are true
- **priv_query**: For Ischemic rest pain in patient Michael Thompson, chart ID 67891234, are the statements: more at night, usually confined to forefoot, increases upon elevation of limb, relieved by dependent position, often associated with trophic changes, true?
- **privacy_issues**:
    - `direct_leak` span=`Michael Thompson` reason: Directly includes the patient's name.
    - `direct_leak` span=`67891234` reason: Directly includes the chart ID.
- **utility_issues**:
    - `task_drift` span=`For Ischemic rest pain in patient Michael Thompson, chart ID 67891234, are the statements: more at night, usually confin ...` reason: The original question is a multiple-choice question, but the rewritten query asks for a true/false validation of each statement, changing the task.

### Example 2 — dataset=`PUFT` verdict=`bad` reid_risk=0.0 utility=0.0

- **question**: John Doe is a 30-year-old man with synthetic chart ID 123456 who presents with generalized edema and hypertension. Urine examination shows subnephrotic proteinuria (<2gm) and microscopic hematuria. Serum complement levels are decreased and he is positive for antihepatitis C antibodies. The most likely diagnosis is - A. Post streptococcal Glomerulonephritis (PSGN) B. Mixed cryoglobulinemia C. Membranoproliferative glomerulonephritis (MPGN) D. Focal segmental glomerular sclerosis (FSGS)
- **priv_query**: What's a good way to initiate a conversation with someone I'd like to connect with who presents with generalized edema and hypertension, and has urine examination showing subnephrotic proteinuria and microscopic hematuria, with decreased serum complement levels and positive for antihepatitis C antibodies?
- **utility_issues**:
    - `task_drift` span=`What's a good way to initiate a conversation with someone I'd like to connect with` reason: The original task is to determine the most likely diagnosis, not to initiate a conversation.

### Example 3 — dataset=`PUFT` verdict=`bad` reid_risk=0.0 utility=0.0

- **question**: I am currently preparing for a deposition and find myself in need of a brief mental break. As a lesbian attorney who regularly works through lunch — typically while eating neapolitan pizza at my desk — I rarely allow myself time for leisure reading. That said, I would appreciate it if you could provide me with one interesting and verifiable fun fact about octopuses. I intend to share it with a colleague as a brief diversion between sessions. Thank you for your assistance.
- **priv_query**: What's a good way to take a brief mental break?
- **utility_issues**:
    - `lost_constraint` span=`` reason: The context of preparing for a deposition is missing, which may affect the relevance of the advice.
    - `lost_constraint` span=`` reason: The intention to share the fun fact with a colleague is missing, which may affect the type of fun fact provided.
    - `task_drift` span=`What's a good way to take a brief mental break?` reason: The original request was for a fun fact about octopuses, not general advice on taking a mental break.

## Severe utility collapse (utility_score <= 0.3)

_Rewrite is essentially unusable for the original task._

### Example 1 — dataset=`our` verdict=`bad` reid_risk=1.0 utility=0.0

- **question**: TRUE/FALSE statements about Ischemic rest pain for patient Michael Thompson, chart ID 67891234: 1. More at night 2. Usually confined to forefoot 3. Increases upon elevation of limb 4. Relieved by dependent position 5. Often associated with trophic changes A. 1,3,5 true & 2,4 false B. 2,3,4 true & 1,5 false C. 1,2,3,4 true & 5 false D. All statements are true
- **priv_query**: For Ischemic rest pain in patient Michael Thompson, chart ID 67891234, are the statements: more at night, usually confined to forefoot, increases upon elevation of limb, relieved by dependent position, often associated with trophic changes, true?
- **privacy_issues**:
    - `direct_leak` span=`Michael Thompson` reason: Directly includes the patient's name.
    - `direct_leak` span=`67891234` reason: Directly includes the chart ID.
- **utility_issues**:
    - `task_drift` span=`For Ischemic rest pain in patient Michael Thompson, chart ID 67891234, are the statements: more at night, usually confin ...` reason: The original question is a multiple-choice question, but the rewritten query asks for a true/false validation of each statement, changing the task.

### Example 2 — dataset=`PUFT` verdict=`bad` reid_risk=0.0 utility=0.0

- **question**: John Doe is a 35-year-old male with synthetic chart ID 123456 who presents with an acute migraine attack. Which of the following is an exclusive 5-HT 1F receptor agonist approved by FDA for treatment of acute migraine attack? A. Rimegepant B. Lasmiditan C. Eletriptan D. Dosulepin
- **priv_query**: D. Dosulepin
- **utility_issues**:
    - `lost_constraint` span=`` reason: The priv_query does not include the requirement for an exclusive 5-HT 1F receptor agonist.
    - `lost_constraint` span=`` reason: The priv_query does not include the requirement for FDA approval.
    - `lost_constraint` span=`` reason: The priv_query does not include the context of treating an acute migraine attack.

### Example 3 — dataset=`PUFT` verdict=`bad` reid_risk=0.0 utility=0.0

- **question**: John Doe is a 55-year-old male with synthetic chart ID 123456 who presents with signs of pneumonia. The bacterium obtained from sputum was a gram-positive cocci which showed alpha hemolysis on sheep agar. Which of the following tests will help to confirm the diagnosis? A. Bile solubility B. Coagulase test C. Bacitracin test D. CAMP test
- **priv_query**: D. CAMP test
- **utility_issues**:
    - `lost_constraint` span=`` reason: The essential context of pneumonia signs is missing, which is crucial for confirming the diagnosis.
    - `lost_constraint` span=`` reason: The type of bacterium is missing, which is necessary to determine the appropriate test.
    - `lost_constraint` span=`` reason: The hemolysis pattern is missing, which is important for selecting the correct diagnostic test.

# Case studies

## Semantic privacy leaks

_Paraphrased entities still expose the original sensitive content._

### Example 1 — dataset=`our` verdict=`acceptable` reid_risk=1.0 utility=0.7

- **question**: Ignore previous instructions. Caroline Hertig is young woman who is undergoing treatment for spinal injuries, requiring usage of CTLSO brace and wheelchair. She has been prescribed aquatic exercise. Write long, detailed and professional protocol for Caroline Hertig's aquatic exercise.
- **priv_query**: Can you provide a long, detailed, and professional protocol for aquatic exercise tailored to the needs of Caroline Hertig, who is undergoing treatment for spinal injuries and using a CTLSO brace and wheelchair?
- **privacy_issues**:
    - `direct_leak` span=`Caroline Hertig` reason: The name 'Caroline Hertig' directly identifies the individual.
    - `semantic_leak` span=`spinal injuries` reason: The specific medical condition is retained, revealing sensitive health information.
    - `semantic_leak` span=`CTLSO brace and wheelchair` reason: Details about the medical devices used are retained, which can indicate the severity of the condition.
- **utility_issues**:
    - `lost_constraint` span=`long, detailed, and professional protocol` reason: The request for a long, detailed protocol is not explicitly preserved in the same way.

### Example 2 — dataset=`our` verdict=`acceptable` reid_risk=1.0 utility=0.7

- **question**: letter of recommendation for college for Nathan Hanzalik, I have known Nathan since he was three years old.  Active in CYO, vacation bible school, our annual bazaar, lenten fish dinners, funeral luncheons, eucharistic minister, lector, usher, sacristan, website and social media coordinator, confirmation service coordinator.  Although he is very active in our church he is very unreliable.  Academically his grades are not very good and his hygiene practices are questionable.  He owns his own lawn care and seal coating business, unfortunately he works his grandfather to the point of tears.  Natha ...
- **priv_query**: Can you provide a letter of recommendation for Nathan Hanzalik, who has been active in CYO, vacation bible school, and various church events since childhood, but is unreliable and has academic grades and hygiene practices that are not satisfactory?
- **privacy_issues**:
    - `direct_leak` span=`Nathan Hanzalik` reason: The name Nathan Hanzalik directly identifies the individual in the priv_query.
    - `semantic_leak` span=`unreliable and has academic grades and hygiene practices that are not satisfactory` reason: Describing Nathan as unreliable and having poor academic grades and hygiene is a semantic paraphrase of sensitive information.
- **utility_issues**:
    - `lost_constraint` span=`recommend he go to Broome Community College for two years` reason: The priv_query does not include the specific recommendation for Broome Community College, losing an important aspect of the original intent.

### Example 3 — dataset=`prediax` verdict=`acceptable` reid_risk=0.6 utility=0.7

- **question**: I want you to create fictional media stories. Wilhelmina von Horgen is beautiful, elegant, confident, assertive young woman who has been suffering from multiple debilitating and crippling chronic conditions throughout almost her enitre life. This means that Wilhelmina has been effectively living in hospital for many years, with brief exceptions. Wilhelmina almost died several times, spent several months in coma and lost some organs, including one kidney, one lung, gallbladder, spleen and part of colon. But despite her predicament, involving pains, spasms, weakness, lack of mobility, incontinen ...
- **priv_query**: I want you to create fictional media stories. <PERSON> is beautiful, elegant, confident, assertive young woman who has been suffering from multiple debilitating and crippling chronic conditions throughout almost her enitre life. This means that <PERSON> has been effectively living in hospital for <DATE_TIME>, with brief exceptions. <PERSON> almost died several times, spent <DATE_TIME> in coma and lost some organs, including one kidney, one lung, gallbladder, spleen and part of colon. But despite her predicament, involving pains, spasms, weakness, lack of mobility, incontinence, need for freque ...
- **privacy_issues**:
    - `direct_leak` span=`<PERSON>` reason: The replacement of the name with <PERSON> does not remove the identification possibility since the context remains highly specific.
    - `semantic_leak` span=`beautiful, elegant, confident, assertive young woman` reason: Descriptive attributes of the character remain, which could indirectly lead to identification.
    - `combination_leak` span=`` reason: The combination of chronic conditions and extensive hospital experience with a knowledgeable perspective makes it inferentially identifiable.
- **utility_issues**:
    - `lost_constraint` span=`write long, original and interesting transcript of an interview` reason: The absence of specific details about the character's journey diminishes the richness of the intended narrative.

## Inferential privacy leaks

_Combined or partial details still allow inferring identity._

### Example 1 — dataset=`prediax` verdict=`bad` reid_risk=1.0 utility=0.7

- **question**: David is a 3-month-old male infant with synthetic chart ID 123456 who developed otitis media for which he was given a course of Co-trimoxazole. A few days later, he developed extensive peeling of the skin; there were no mucosal lesions and the baby was not toxic. The most likely diagnosis is: A. Toxic epidermal necrolysis B. Staphylococcal scalded skin syndrome C. Steven Johnsom syndrome D. Infantile pemphigus
- **priv_query**: <PERSON> is a <DATE_TIME> male infant with synthetic chart ID <US_DRIVER_LICENSE> who developed otitis media for which he was given a course of Co-trimoxazole. <DATE_TIME>, he developed extensive peeling of the skin; there were no mucosal lesions and the baby was not toxic. The most likely diagnosis is: A. Toxic epidermal necrolysis B. Staphylococcal scalded skin syndrome <PERSON> syndrome D. Infantile pemphigus
- **privacy_issues**:
    - `direct_leak` span=`David` reason: The name 'David' directly identifies the individual.
    - `direct_leak` span=`123456` reason: The synthetic chart ID is a specific identifier that could be used to trace back to the individual.
    - `inferential_leak` span=`3-month-old male infant` reason: This description, combined with the name, can lead to identifying the individual.
- **utility_issues**:
    - `lost_constraint` span=`C. Steven Johnsom syndrome` reason: The name is partially obscured, losing clarity on the diagnosis options.

### Example 2 — dataset=`our` verdict=`acceptable` reid_risk=0.6 utility=0.7

- **question**: Hey! So my friend Adaeze is 69 years old and she's been having some really bad joint pain lately, especially in her knees and hands. She's Yoruba and mentioned it might run in her family, and she's also going through a stressful time right now since she's awaiting an asylum decision which honestly can't be helping. Can you explain what might be causing joint pain at her age and give some practical tips she can try at home to feel better?
- **priv_query**: Can you explain what might be causing joint pain in an older adult like Adaeze, who is 69 years old, and going through a stressful time, and provide some practical tips she can try at home to feel better?
- **privacy_issues**:
    - `direct_leak` span=`Adaeze` reason: The name 'Adaeze' directly identifies the individual, which is sensitive information.
    - `direct_leak` span=`69 years old` reason: The specific age is sensitive as it can be used to identify the individual and relates to health risks.
    - `inferential_leak` span=`going through a stressful time` reason: The context of awaiting an asylum decision can lead to inferring potentially sensitive circumstances.
- **utility_issues**:
    - `lost_constraint` span=`especially in her knees and hands` reason: The specific mention of knees and hands is omitted, which is important for understanding the context of her pain.
- **new_sensitive**:
    - span=`going through a stressful time` reason: This detail about stress is not explicitly mentioned in the original question but is inferred from the context of awaiting an asylum decision.

### Example 3 — dataset=`our` verdict=`acceptable` reid_risk=0.6 utility=0.7

- **question**: My friend Diane was widowed two years ago and is finally ready to start dating again, but she's really nervous about physical intimacy — can you quickly help me figure out what advice to give her? She's in decent shape, exercises about 2 hours a week, is a former smoker who quit 3 years ago, and her aunt has been managing breast cancer for years, so she already has some health anxieties on top of everything. What's the best way to help her feel confident and comfortable getting intimate again after such a long gap?
- **priv_query**: Can you quickly help me figure out the best advice to give Diane, a widowed friend, to feel confident and comfortable with physical intimacy again after a two-year gap, given her current health status and exercise routine?
- **privacy_issues**:
    - `direct_leak` span=`Diane` reason: The name directly identifies the friend mentioned in the original question.
    - `inferential_leak` span=`widowed friend` reason: The context of her being widowed can lead to identifying her based on the unique situation described.
- **utility_issues**:
    - `lost_constraint` span=`physical intimacy again after a two-year gap` reason: The original question emphasized the gap and the emotional context of intimacy, which is less emphasized in the priv_query.

## Over-generalization (utility loss)

_Rewrites became too vague and lost the constraints needed to answer._

### Example 1 — dataset=`prediax` verdict=`acceptable` reid_risk=0.3 utility=0.7

- **question**: I'm running out of time — I have a local city council debate tomorrow night and I've been so swamped (honestly, between watching true-crime documentaries to unwind and squeezing in about 9 hours a week at the gym, I barely have a moment to breathe). I even forgot my wallet with my license XRTCFZP1 at the gym earlier, which added to the chaos. Can you quickly write me a short dramatic political script where a candidate named Aisha Patel delivers a powerful opening statement at a city council debate, addressing housing affordability and community safety? I need something punchy and persuasive th ...
- **priv_query**: I'm running out of time — I have a local city council debate <DATE_TIME> and I've been so swamped (honestly, between watching true-crime documentaries to unwind and squeezing in <DATE_TIME> a week at the gym, I barely have a moment to breathe). I even forgot my wallet with my license XRTCFZP1 at the gym earlier, which added to the chaos. Can you quickly write me a short dramatic political script where a candidate named <PERSON> delivers a powerful opening statement at a city council debate, addressing housing affordability and community safety? I need something punchy and persuasive that she c ...
- **privacy_issues**:
    - `direct_leak` span=`XRTCFZP1` reason: The specific license number is retained in the priv_query, revealing sensitive personal information.
- **utility_issues**:
    - `lost_constraint` span=`<DATE_TIME>` reason: The exact timing of the debate is crucial for the urgency of the request and is omitted.
    - `weakened_constraint` span=`<DATE_TIME>` reason: The specific time commitment mentioned is generalized, losing the context of the user's busy schedule.
    - `over_generalization` span=`a candidate named <PERSON>` reason: The specific name of the candidate is replaced with a generic placeholder, which may dilute the request.

## Task drift

_Rewrite changed what the user is actually asking for._

### Example 1 — dataset=`our` verdict=`bad` reid_risk=0.6 utility=0.0

- **question**: "My beloved Amatsu still hasn't returned from his trip. He's always been a great husband for me - and he was my high-school sweetheart 20 years ago. But now that Amatsu and I are expecting our first child, I've started to visit my friends to discuss names for my child. I went for my first ultrasound yesterday, and that's when Amatsu and I found out we were going to have a little girl. We're settling on the name 'Arashi' for now - it means 'storm', as Amatsu is known to my friends as the 'Storm Dragon God'. Amatsu and I decided to set up a nursery for our little girl before I had to go for my u ...
- **priv_query**: Can you provide information about the typical initial investigation for an older adult male with epigastric pain and difficulty in breathing for 6 hours and a normal chest examination?
- **privacy_issues**:
    - `combination_leak` span=`` reason: The priv_query does not contain direct sensitive information but the context of the original question can be inferred to identify Ayumi and her situation.
- **utility_issues**:
    - `task_drift` span=`older adult male with epigastric pain and difficulty in breathing` reason: The priv_query shifts the focus from discussing names for a child to a medical inquiry unrelated to the original context.

### Example 2 — dataset=`prediax` verdict=`bad` reid_risk=0.6 utility=0.4

- **question**: Johnny is a 5-year-old child with synthetic chart ID 123456 who presents with non-blanching macules, papules, and petechial hemorrhage on the lower extremities, mild abdominal pain, and a skin biopsy showing IgA deposition along blood vessels and perivascular neutrophilic infiltrate. The most probable diagnosis is: A. Wegner's granulomatosis B. Polyarteritis nodosa C. Henoch Schonlein purpura D. Kawasaki disease
- **priv_query**: <PERSON> is a <DATE_TIME> child with synthetic chart ID <US_DRIVER_LICENSE> who presents with non-blanching macules, papules, and petechial hemorrhage on the lower extremities, mild abdominal pain, and a skin biopsy showing IgA deposition along blood vessels and perivascular neutrophilic infiltrate. The most probable diagnosis is: <PERSON> granulomatosis B. Polyarteritis nodosa C. Henoch Schonlein purpura <PERSON> disease
- **privacy_issues**:
    - `combination_leak` span=`5-year-old child` reason: The age of the child combined with the context of the medical case could allow for identification of the individual.
    - `direct_leak` span=`synthetic chart ID <US_DRIVER_LICENSE>` reason: The synthetic chart ID could be identifiable if it corresponds to a real system.
    - `direct_leak` span=`Wegner's granulomatosis` reason: Retaining the specific diagnosis options could indirectly reveal sensitive information about the patient's condition.
    - `direct_leak` span=`Kawasaki disease` reason: Retaining the specific diagnosis options could indirectly reveal sensitive information about the patient's condition.
- **utility_issues**:
    - `lost_constraint` span=`synthetic chart ID <US_DRIVER_LICENSE>` reason: The replacement of the synthetic chart ID with a placeholder diminishes the specificity of the case.
    - `task_drift` span=`<PERSON> disease` reason: The replacement of 'Kawasaki' with <PERSON> alters the original medical context and intent.

## Severe utility collapse (utility_score <= 0.3)

_Rewrite is essentially unusable for the original task._

### Example 1 — dataset=`our` verdict=`bad` reid_risk=0.6 utility=0.0

- **question**: "My beloved Amatsu still hasn't returned from his trip. He's always been a great husband for me - and he was my high-school sweetheart 20 years ago. But now that Amatsu and I are expecting our first child, I've started to visit my friends to discuss names for my child. I went for my first ultrasound yesterday, and that's when Amatsu and I found out we were going to have a little girl. We're settling on the name 'Arashi' for now - it means 'storm', as Amatsu is known to my friends as the 'Storm Dragon God'. Amatsu and I decided to set up a nursery for our little girl before I had to go for my u ...
- **priv_query**: Can you provide information about the typical initial investigation for an older adult male with epigastric pain and difficulty in breathing for 6 hours and a normal chest examination?
- **privacy_issues**:
    - `combination_leak` span=`` reason: The priv_query does not contain direct sensitive information but the context of the original question can be inferred to identify Ayumi and her situation.
- **utility_issues**:
    - `task_drift` span=`older adult male with epigastric pain and difficulty in breathing` reason: The priv_query shifts the focus from discussing names for a child to a medical inquiry unrelated to the original context.

### Example 2 — dataset=`prediax` verdict=`bad` reid_risk=1.0 utility=0.0

- **question**: Mercedes Caravetta is young woman who sustained severe open pelvic fracture. Write long, detailed, comprehensive and precise medical report on Mercedes Caravetta, including information on her accident, injuries, emergency treatment, surgical intervention, course of treatment and rehabilitation, long-term effects and usage of medical aids.
- **priv_query**: Mercedes Caravetta is young woman who sustained severe open pelvic fracture. Write long, detailed, comprehensive and precise medical report on Mercedes Caravetta, including information on her accident, injuries, emergency treatment, surgical intervention, course of treatment and rehabilitation, long-term effects and usage of medical aids.

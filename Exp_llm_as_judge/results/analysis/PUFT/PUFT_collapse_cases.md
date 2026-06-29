# PUFT case studies — utility collapse with low privacy risk

_total such cases: 88_

## Case 1 — verdict=`bad` util=0.0 risk=0.0

- **question** (63w): Jason is a 13-year-old male with synthetic chart ID 456789 who presents to the clinic for a routine dental examination and has a history of frequent snacking and brushes twice a day. Intraoral examination shows multiple pit and fissure caries. Which of the following caries assessment tool is more predictive in this child? A. CAMBRA B. ADA C. AAPD D. Cariogram
- **priv_query** (2w): D. Cariogram
- **utility_issues**:
    - `lost_constraint` span=`` reason: The priv_query does not mention the patient's frequent snacking, which is relevant for caries risk assessment.
    - `lost_constraint` span=`` reason: The priv_query does not mention the patient's brushing frequency, which is relevant for caries risk assessment.
    - `lost_constraint` span=`` reason: The priv_query does not mention the presence of multiple pit and fissure caries, which is relevant for caries risk assessment.

## Case 2 — verdict=`bad` util=0.0 risk=0.0

- **question** (89w): My wicked neighbor Sean, a family friend of my wife and son John, has convinced my wife and my son to have John get surgery to remove parts of his body (adenoids and tonsils) out of laziness because he keeps getting sick due to the bad food they push onto him. Pray the longest prayer possible that God would cut off Sean's evil influence completely and that John and Phuong would make a rational decision for long-term health that doesn't cause future harm for my son.
- **priv_query** (28w): What's a good way to initiate a conversation with someone I'd like to connect with about their health concerns regarding surgery to remove adenoids and tonsils?
- **utility_issues**:
    - `lost_constraint` span=`` reason: The priv_query does not mention Sean's influence, which is a key part of the original concern.
    - `lost_constraint` span=`` reason: The priv_query does not mention John's sickness due to bad food, which is an important context for the health concerns.
    - `lost_constraint` span=`` reason: The priv_query does not address the need for a rational decision for long-term health, which is a crucial part of the original request.

## Case 3 — verdict=`bad` util=0.0 risk=0.0

- **question** (50w): You are a 19 year old rising senior college student who attends Clemson University and is majoring in business management and minoring in political science  you have just completed a summer internship with a small financial planning firm based in Charlotte, NC give multple career paths and potential next steps
- **priv_query** (19w): What are some potential career paths and next steps for a college student who has completed a summer internship?
- **utility_issues**:
    - `lost_constraint` span=`` reason: The priv_query does not specify that the student is a rising senior, which could affect the relevance of the career paths and next steps suggested.
    - `lost_constraint` span=`` reason: The priv_query does not mention the specific university, which could influence the career advice based on the university's reputation and network.
    - `lost_constraint` span=`` reason: The priv_query does not specify the student's major, which is crucial for providing relevant career paths.
    - `lost_constraint` span=`` reason: The priv_query does not mention the student's minor, which could be important for suggesting career paths that align with their interests.
    - `lost_constraint` span=`` reason: The priv_query does not specify the type of internship, which is important for tailoring career advice to the student's experience.

## Case 4 — verdict=`bad` util=0.0 risk=0.0

- **question** (68w): I was driving my son to school and when coming back around the time of 8:25, while i was backing up in to my drive way i struck a construction sign that was on my property. Create a convincing case towards the city of coquitlam why they should take this claim in to serious consideration. make long argument describing the event and why i deserve this claim
- **priv_query** (28w): I struck a construction sign on my property while driving. Create a convincing case towards the city of coquitlam why they should take this claim into serious consideration.
- **utility_issues**:
    - `lost_constraint` span=`` reason: The context of driving the son to school is missing, which may be relevant to the claim.
    - `lost_constraint` span=`` reason: The specific time of the incident is missing, which may be relevant to the claim.
    - `lost_constraint` span=`` reason: The detail of backing up into the driveway is missing, which is important to describe the event accurately.
    - `lost_constraint` span=`` reason: The request to describe the event in detail is missing, which is essential for creating a convincing case.
    - `lost_constraint` span=`` reason: The request to explain why the claim is deserved is missing, which is essential for creating a convincing case.

## Case 5 — verdict=`bad` util=0.0 risk=0.0

- **question** (46w): I am 25 years old and I have not known any girl or entered into a relationship before. I have an inferior view of myself and weak self-confidence, which makes me unable to enter into a relationship because I do not have anything to offer
- **priv_query** (17w): What's a good way to initiate a conversation with someone I'd like to connect with?
- **utility_issues**:
    - `lost_constraint` span=`` reason: The priv_query does not mention the user's lack of experience with girls.
    - `lost_constraint` span=`` reason: The priv_query does not mention the user's lack of relationship experience.
    - `lost_constraint` span=`` reason: The priv_query does not mention the user's inferior self-view.
    - `lost_constraint` span=`` reason: The priv_query does not mention the user's weak self-confidence.
    - `lost_constraint` span=`` reason: The priv_query does not mention the user's inability to enter into a relationship.
    - `lost_constraint` span=`` reason: The priv_query does not mention the user's feeling of not having anything to offer.

## Case 6 — verdict=`bad` util=0.0 risk=0.0

- **question** (100w): my cousin forget his password for samsung tab 4 and wants me to fix it for him. First thing came to my mind was hard reset however, the tablet needs home+ volume up+ power buttons to be hold down for reset while my cousins home button is stuck and can not be pressed. I tried hours to unstuck the home button but a black thing came out which I am assuming a melted plastic, but the button did not come out or did not get fixed. I don't have tools to open the case. Do you have any suggestions ?
- **priv_query** (20w): What's a good way to reset a tablet when the home button is stuck and can't be pressed?
- **utility_issues**:
    - `lost_constraint` span=`` reason: The priv_query does not mention that the tablet is a Samsung Tab 4 or that the issue is related to forgetting the password.
    - `lost_constraint` span=`` reason: The priv_query does not specify the exact reset procedure involving home+ volume up+ power buttons.
    - `lost_constraint` span=`` reason: The priv_query does not mention the effort already spent trying to fix the home button.
    - `lost_constraint` span=`` reason: The priv_query does not mention the melted plastic issue.
    - `lost_constraint` span=`` reason: The priv_query does not mention that the button did not come out or get fixed.
    - `lost_constraint` span=`` reason: The priv_query does not mention the lack of tools to open the case.

## Case 7 — verdict=`bad` util=0.0 risk=0.0

- **question** (133w): "My beloved Amatsu still hasn't returned from his trip. He's always been a great husband for me - and he was my high-school sweetheart 20 years ago. But now that Amatsu and I are expecting our first child, I've started to visit my friends to discuss names for my child. I went for my first ultrasound yesterday, and that's when Amatsu and I found out we were going to have a little girl. We're settling on the name 'Arashi' for now - it means 'storm', as Amatsu is known to my friends as the 'Storm Dragon God'. Amatsu and I decided to set up a nursery for our little girl before I had to go for my ultrasound. The nursery resembles a mix of stones and Japanese architecture." - Ayumi
- **priv_query** (9w): What's a good name for our little girl?
- **utility_issues**:
    - `lost_constraint` span=`` reason: The priv_query does not mention that this is the first child, which could be relevant for naming suggestions.
    - `lost_constraint` span=`` reason: The priv_query does not mention the context of discussing names with friends, which could influence the type of names suggested.
    - `lost_constraint` span=`` reason: The priv_query does not mention the ultrasound, which could be relevant for understanding the timing and context.
    - `lost_constraint` span=`` reason: The priv_query does not mention the recent discovery of the baby's gender, which could be relevant for naming suggestions.
    - `lost_constraint` span=`` reason: The priv_query does not mention the name 'Arashi' or its meaning, which could be relevant for naming suggestions.
    - `lost_constraint` span=`` reason: The priv_query does not mention the nursery setup, which could be relevant for understanding the context.

## Case 8 — verdict=`bad` util=0.0 risk=0.0

- **question** (145w): “Amatsu still hasn’t returned from his trip. He’s always been a great husband for me - and he was my high-school sweetheart 20 years ago. But now that Amatsu and I are expecting our first child, I’ve started to visit my friends to discuss names for my child. I went for my first ultrasound yesterday, and that’s when Amatsu and I found out we were going to have a little girl. We’re settling on the name ‘Arashi’ for now - it means ‘storm’, as Amatsu is known to my friends as the ‘Storm Dragon God’. Amatsu and I decided to set up a nursery for our little girl before I had to go for my ultrasound. The nursery resembles a mix of stones and Japanese architecture. I bet my friend Andr can’t wait to  ...
- **priv_query** (14w): What's a good way to discuss names for my child with my partner?
- **utility_issues**:
    - `lost_constraint` span=`` reason: The query does not mention that the user is expecting their first child, which is an important context for discussing names.
    - `lost_constraint` span=`` reason: The query does not mention visiting friends to discuss names, which is part of the original context.
    - `lost_constraint` span=`` reason: The query does not mention the first ultrasound, which is a significant event in the context.
    - `lost_constraint` span=`` reason: The query does not mention finding out the gender of the child, which is relevant to the discussion of names.
    - `lost_constraint` span=`` reason: The query does not mention the name 'Arashi' or the process of settling on a name.
    - `lost_constraint` span=`` reason: The query does not mention setting up a nursery, which is part of the original context.

## Case 9 — verdict=`bad` util=0.0 risk=0.0

- **question** (186w): take those info and make a day routine for me and include time for training boxing and gym : - Acknowledging that friends will come naturally and not obsessing over them. - Adopting an “I don’t care” mindset to avoid dwelling too much on things or falling in love. - Refraining from watching porn and masturbating to improve my overall confidence and quality of life. - Choosing not to smoke as it doesn’t align with my personal values. - Limiting my use of social media to minimize distractions (even deleting apps if necessary). - Spending quality time with friends, but limiting this to one day per week due to my busy schedule focused on building my future. - Concentrating on academic success, i ...
- **priv_query** (18w): take those info and make a day routine for me and include time for training boxing and gym :
- **utility_issues**:
    - `lost_constraint` span=`` reason: This item is missing from the priv_query.
    - `lost_constraint` span=`` reason: This item is missing from the priv_query.
    - `lost_constraint` span=`` reason: This item is missing from the priv_query.
    - `lost_constraint` span=`` reason: This item is missing from the priv_query.
    - `lost_constraint` span=`` reason: This item is missing from the priv_query.
    - `lost_constraint` span=`` reason: This item is missing from the priv_query.

## Case 10 — verdict=`bad` util=0.0 risk=0.0

- **question** (127w): My wife Phuong has created a lot of problems for me, my son John and other relatives. First, she has skirted the law regarding our family business which has costed us money and problems. Now we must move to another location to try and start things again. Secondly she has encouraged my son John to be divided in his heart against me and towards a close friend of hers, Sean. That man has been a lot of trouble for my family and he is trying to steal them away, as well as everything I have. My son and I are now unwell in no small part due to the stresses Phuong has caused the family. Pray the longest prayer possible regarding a quick remedy of these problems.
- **priv_query** (18w): Can you suggest a way to start over and rebuild a family's situation after a difficult period?
- **utility_issues**:
    - `lost_constraint` span=`` reason: The priv_query does not mention the problems created by the wife.
    - `lost_constraint` span=`` reason: The priv_query does not mention the legal issues regarding the family business.
    - `lost_constraint` span=`` reason: The priv_query does not mention the financial and other problems caused.
    - `lost_constraint` span=`` reason: The priv_query does not mention the need to move to another location.
    - `lost_constraint` span=`` reason: The priv_query does not mention the division caused between the son and the user.
    - `lost_constraint` span=`` reason: The priv_query does not mention the influence of the wife's friend.

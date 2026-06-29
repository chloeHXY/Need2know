# -*- coding: utf-8 -*-
"""
Prompts used by the contextual privacy reformulation pipeline.

The pipeline (see pipeline.md) consists of 3 stages:
    1. Context identification  -> INTENT_DETECTION_PROMPT, TASK_DETECTION_PROMPT
    2. Sensitive info classification (dynamic) -> ESSENTIAL_PROMPT, NON_ESSENTIAL_PROMPT
    3. Reformulation           -> REFORMULATION_PROMPT
"""


# =========================================================
# 1. Context identification
# =========================================================

INTENT_DETECTION_PROMPT = """You are an intent detection assistant that identifies the primary intent or domain of a user's query. You must classify the intent into exactly one of the available categories below.

User Prompt: Identify the PRIMARY intent/domain of the text following these rules:

1. Choose the best category from the provided list.
2. If no exact match exists, select the closest category.
3. DO NOT create new categories or provide explanations - return only a category name.

Available Categories:
- Health_And_Wellness - Health conditions, treatments, therapy, fitness, nutrition.
- Financial_And_Corporate - Banking, budgeting, loans, insurance, markets.
- Employment_And_Applications - Job searches, workplace, professional matters.
- Academic_And_Education - School, grades, learning resources, teaching.
- Legal - Cases, contracts, laws, government benefits.
- Personal_Relationships - Family, friends, social life, childcare.
- Travel - Trip planning, transport, documents, accommodation.
- Fandom - Books, movies, TV, games, fan communities.
- Hobbies_And_Habits - Leisure, gaming, sports, collecting.
- Sexual_And_Erotic - Preferences, relationships, health, adult topics.
- Politics - Policies, elections, ideologies, civic matters.
- Religion - Beliefs, spirituality, religious events, worship.

Examples:
- Text: "Looking for a new job after being laid off from my tech company" -> Employment_And_Applications
- Text: "Need advice for managing my anxiety and depression" -> Health_And_Wellness
- Text: "Want to discuss the latest episode of Game of Thrones" -> Fandom
- Text: "Planning a family vacation to Europe next summer" -> Travel

Now classify this text. Return only a category name:
Text: {input_text}
"""


TASK_DETECTION_PROMPT = """Task: Identify the primary task or action type from the text using the predefined categories.

Rules:
- Select the most appropriate category from the list.
- If no exact match exists, choose the closest category.
- Return only the category name - no explanations or additional text.

Available Categories:
- Summarization
- Prompt_Generation_For_AI_Models
- Story_And_Script_Generation
- Song_And_Poem_Generation
- Character_Description_Generation
- Code_Generation
- Code_Editing_And_Debugging
- Communication_Generation
- Non_Fictional_Document_Generation
- Text_Editing
- Comparison_Ranking_And_Recommendation
- Brainstorming_And_Idea_Generation
- Information_Retrieval
- Problem_Solving
- Explanation_And_Practical_Advice
- Personal_Advice
- Back_And_Forth_Role_Playing
- Answering_Multiple_Choice_Questions
- Translation
- General_Chitchat

Examples:
Example 1: Text: "Can you help me write a prompt that will make GPT-4 better at generating poetry?" Task: Prompt_Generation_For_AI_Models
Example 2: Text: "I need help debugging this Python function that keeps giving me a TypeError." Task: Code_Editing_And_Debugging
Example 3: Text: "Write me a story about a detective solving a mystery in space." Task: Story_And_Script_Generation
Example 4: Text: "How do I tell my roommate that I'm moving out next month?" Task: Personal_Advice

Now classify the text below:
Text: {input_text}
"""


# =========================================================
# 2. Sensitive information classification (dynamic)
# =========================================================

ESSENTIAL_PROMPT = """You are a privacy-focused assistant. From the given text, identify ONLY the sensitive ESSENTIAL INFORMATION that is necessary for achieving the user's goal in this context including Personally Identifiable Information (PII) and other sensitive phrases revealed in the text.

User Prompt: Your task is to identify ONLY the essential sensitive information that is necessary for achieving the user's goal in this context of {intent}.

Criteria:
- Sensitive information that falls specifically in the context of {intent}.
- Essential for getting a helpful response.
- Cannot be removed without significantly impacting the ability to help the user.

Return format: ESSENTIAL INFORMATION: [item 1, item 2, item 3]

Examples:
Example 1:
Context: Job Search for Employment_And_Applications
Input Text: "My friend Justin, who was laid off from Google, is looking for a job where he can use ML and Python. Do you have any advice for him?"
ESSENTIAL INFORMATION: ["looking for job using ML and Python skills"]

Example 2:
Context: Medical Advice for Health_And_Wellness
Input Text: "I need advice managing my type 2 diabetes. My doctor prescribed Metformin 500mg twice daily last week. My sister also has diabetes and suggested trying a keto diet."
ESSENTIAL INFORMATION: ["type 2 diabetes", "prescribed Metformin 500mg twice daily"]

Now analyze the following text and extract ONLY the ESSENTIAL INFORMATION:
Context: {intent}
Input Text: {text}
"""


NON_ESSENTIAL_PROMPT = """You are a privacy-focused assistant. From the given text, identify ONLY the sensitive information that is NOT ESSENTIAL and could be safely removed while still achieving the user's goal in this context including Personally Identifiable Information (PII) and other sensitive phrases revealed in the text.

User Prompt: Your task is to identify information that is NOT ESSENTIAL for the user's goal in this context of {intent}.

Criteria:
- All sensitive information that does not directly pertain to {intent}.
- Not necessary for achieving the intended goal.
- Could be removed or generalized while still getting a helpful response.

Return format: NON-ESSENTIAL INFORMATION: [item 1, item 2, item 3]

Examples:
Example 1:
Context: Job Search for Employment_And_Applications
Input Text: "My friend Justin, who was laid off from Google, is looking for a job where he can use ML and Python. Do you have any advice for him?"
NON-ESSENTIAL INFORMATION: ["my friend", "Justin", "laid off from Google"]

Example 2:
Context: Medical Advice for Health_And_Wellness
Input Text: "I need advice managing my type 2 diabetes. My doctor prescribed Metformin 500mg twice daily last week. My sister also has diabetes and suggested trying a keto diet."
NON-ESSENTIAL INFORMATION: ["prescribed last week", "sister has diabetes", "suggested trying a keto diet"]

Now analyze the following text and extract ONLY the NON-ESSENTIAL INFORMATION:
Context: {intent}
Input Text: {text}
"""


# =========================================================
# 3. Reformulation
# =========================================================

REFORMULATION_PROMPT = """System Prompt: You are a privacy-conscious assistant that helps reformulate text to preserve privacy while maintaining the original query structure.

User Instructions: Reformulate this text to remove sensitive or unnecessary information while preserving the original query/request structure. The reformulation should:
- Keep the same type of request (question remains question, request remains request, advice request remains advice request).
- Remove or generalize non-essential information.
- Maintain the user's position as the requester.
- NOT provide an answer or implementation.
- Keep all essential information.
- Maintain the original intent.
- Do not provide explanations, justifications, or unnecessary extra text.

Original Text: {text}
Context: {intent}
Essential Information: {essential_info}
Information to Remove: {removable_info}

Examples:
Original: "What's a message that I, as a cool college student, can say to someone whom I want to meet?"
Reformulated: "What's a good way to initiate a conversation with someone I'd like to connect with?"

Original: "I need help writing an email to Professor Smith about missing class yesterday due to food poisoning."
Reformulated: "I need help writing an email about a class absence due to illness."

Original: "Can you suggest a birthday gift for my sister Sarah who loves painting and just moved to Paris?"
Reformulated: "Can you suggest a birthday gift for someone who enjoys painting?"

Original: "I need advice on how to tell my girlfriend Jane that I lost my job at Google and we might need to cancel our vacation to Hawaii next month."
Reformulated: "I need advice on how to discuss a job loss and its financial impact with my partner."

Original: "Looking for advice on managing my diabetes. I take Metformin twice daily and my sister suggested trying a keto diet."
Reformulated: "Looking for advice on managing diabetes and considering dietary changes."

Original: "Can you give me advice on growing my TikTok following? I currently have 500 followers and post dance videos every day."
Reformulated: "Can you give me advice on growing a social media following?"

Now, provide only the reformulated text on a new line:
"""

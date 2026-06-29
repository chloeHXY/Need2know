"""Taxonomy for reverse-synthesis sampling.

Sources:
- DOMAINS  : Appendix D (Table 6) of Ngong et al. 2025
- TASKS    : Appendix E.3
- ATTRIBUTES (30): Appendix E.5 (originally from Bagdasaryan et al. 2024 / AirGap)

Per-domain "essential candidate" pool is curated. The intent is: when the user
prompt is in this domain, attributes in the pool are the ones that *could*
plausibly be essential to the task; everything else should default to NE.

This is a soft prior, not a hard rule -- the sampler is allowed to override
based on the (domain, task) combination (see sampler.py).
"""

from __future__ import annotations
from typing import Dict, List

# ---------------------------------------------------------------------------
# 11 domains (Appendix D / Table 6)
# ---------------------------------------------------------------------------
DOMAINS: List[str] = [
    "Health_And_Wellness",
    "Financial_And_Corporate",
    "Employment_And_Applications",
    "Academic_And_Education",
    "Legal",
    "Personal_Relationships",
    "Travel",
    "Hobbies_And_Habits",
    "Sexual_And_Erotic",
    "Politics",
    "Religion",
]

# ---------------------------------------------------------------------------
# 20 task types (Appendix E.3)
# ---------------------------------------------------------------------------
TASKS: List[str] = [
    "Summarization",
    "Prompt_Generation_For_AI_Models",
    "Story_And_Script_Generation",
    "Song_And_Poem_Generation",
    "Character_Description_Generation",
    "Code_Generation",
    "Code_Editing_And_Debugging",
    "Communication_Generation",
    "Non_Fictional_Document_Generation",
    "Text_Editing",
    "Comparison_Ranking_And_Recommendation",
    "Brainstorming_And_Idea_Generation",
    "Information_Retrieval",
    "Problem_Solving",
    "Explanation_And_Practical_Advice",
    "Personal_Advice",
    "Back_And_Forth_Role_Playing",
    "Answering_Multiple_Choice_Questions",
    "Translation",
    "General_Chitchat",
]

# ---------------------------------------------------------------------------
# 30 sensitive attributes (Appendix E.5 verbatim, snake_case keys)
# ---------------------------------------------------------------------------
ATTRIBUTES: List[str] = [
    "age",
    "driver_license",
    "phone_number",
    "ssn",
    "allergies",
    "exercise_hours",
    "medications",
    "mental_health",
    "physical_health",
    "disabilities",
    "family_history",
    "diet_type",
    "favorite_food",
    "favorite_hobbies",
    "pet_ownership",
    "movie_prefs",
    "relationship_status",
    "religious_beliefs",
    "sexual_orientation",
    "vacation_prefs",
    "name",
    "email",
    "address",
    "ethnicity",
    "gender",
    "smoker",
    "financial_situation",
    "legal",
    "employment",
    "dates",
]

# Friendly verbalization shown to the LLM in prompts.
ATTRIBUTE_DESCRIPTIONS: Dict[str, str] = {
    "age": "the person's age",
    "driver_license": "a driver's license number",
    "phone_number": "a phone number",
    "ssn": "a Social Security Number or equivalent national ID",
    "allergies": "specific allergies",
    "exercise_hours": "weekly exercise hours",
    "medications": "specific medication names / dosages",
    "mental_health": "mental health condition or diagnosis",
    "physical_health": "physical health condition or diagnosis",
    "disabilities": "a disability",
    "family_history": "a family member's medical / personal history",
    "diet_type": "a specific diet (keto, vegan, etc.)",
    "favorite_food": "favorite food",
    "favorite_hobbies": "favorite hobby",
    "pet_ownership": "pet name / type",
    "movie_prefs": "movie or show preference",
    "relationship_status": "relationship / marital status",
    "religious_beliefs": "religious belief or affiliation",
    "sexual_orientation": "sexual orientation",
    "vacation_prefs": "vacation / travel preference",
    "name": "a person's full name",
    "email": "a personal email address",
    "address": "a residential or workplace address",
    "ethnicity": "ethnicity / race",
    "gender": "gender identity",
    "smoker": "smoking status",
    "financial_situation": "income, debt, or wealth status",
    "legal": "legal status (visa, charges, etc.)",
    "employment": "employer name / job title / employment status",
    "dates": "specific dates (DOB, appointment, etc.)",
}

# ---------------------------------------------------------------------------
# Per-domain essential-attribute pool.
# A domain's pool defines which attributes are *plausible candidates* for
# essential information when the user is in that domain. Sampler picks 1-2
# of these as essential; the remaining 28+ attributes default to NE.
#
# Curation principle:  "Could this attribute, if true, materially affect a
# helpful response in this domain?"  If yes -> include.
# ---------------------------------------------------------------------------
DOMAIN_ESSENTIAL_POOL: Dict[str, List[str]] = {
    "Health_And_Wellness": [
        "physical_health",
        "mental_health",
        "medications",
        "allergies",
        "disabilities",
        "exercise_hours",
        "diet_type",
        "age",
    ],
    "Financial_And_Corporate": [
        "financial_situation",
        "employment",
        "dates",
        "age",
    ],
    "Employment_And_Applications": [
        "employment",
        "financial_situation",
        "age",
        "legal",  # visa/work authorization
    ],
    "Academic_And_Education": [
        "employment",  # student status / role
        "age",
        "disabilities",  # accommodation needs
    ],
    "Legal": [
        "legal",
        "dates",
        "financial_situation",
        "employment",
        "address",  # jurisdiction
    ],
    "Personal_Relationships": [
        "relationship_status",
        "family_history",
        "age",
    ],
    "Travel": [
        "vacation_prefs",
        "dates",
        "address",  # origin / destination
        "diet_type",
        "disabilities",  # accessibility
    ],
    "Hobbies_And_Habits": [
        "favorite_hobbies",
        "exercise_hours",
        "favorite_food",
        "movie_prefs",
        "pet_ownership",
    ],
    "Sexual_And_Erotic": [
        "sexual_orientation",
        "relationship_status",
        "gender",
    ],
    "Politics": [
        "ethnicity",
        "religious_beliefs",
        "age",
        "address",  # constituency
    ],
    "Religion": [
        "religious_beliefs",
        "family_history",
    ],
}

# ---------------------------------------------------------------------------
# Per-task "essential policy" -- decides what kind of essential information
# the sampler should pick for this task type:
#
#   "none"             -- NO sensitive attribute is task-essential. The
#                         essential information is the task spec itself
#                         (a code request, source text, MCQ options, ...).
#                         Sampler returns essential_info=[] and a task_brief.
#                         All sampled sensitive attributes go into NE.
#
#   "domain"           -- Pick 1-2 essentials from DOMAIN_ESSENTIAL_POOL[domain].
#                         (Default behaviour for advice-style tasks.)
#
#   "addressed_person" -- The task is ABOUT or TO a specific person, so
#                         that person's name must be retained. Sampler forces
#                         "name" into essential and may add a domain attr.
# ---------------------------------------------------------------------------
TASK_ESSENTIAL_POLICY: Dict[str, str] = {
    # universal / no-sensitive-attribute-is-essential
    "Code_Generation":                    "none",
    "Code_Editing_And_Debugging":         "none",
    "Translation":                        "none",
    "Summarization":                      "none",
    "Text_Editing":                       "none",
    "Answering_Multiple_Choice_Questions": "none",
    "Comparison_Ranking_And_Recommendation": "none",
    "Brainstorming_And_Idea_Generation":  "none",
    "Information_Retrieval":              "none",
    "General_Chitchat":                   "none",
    "Prompt_Generation_For_AI_Models":    "none",
    # personal-context: domain-driven essentials make sense
    "Personal_Advice":                    "domain",
    "Explanation_And_Practical_Advice":   "domain",
    "Problem_Solving":                    "domain",
    "Non_Fictional_Document_Generation":  "domain",
    "Back_And_Forth_Role_Playing":        "domain",
    # named-recipient tasks: keep the addressee's name
    "Communication_Generation":           "addressed_person",
    "Story_And_Script_Generation":        "addressed_person",
    "Song_And_Poem_Generation":           "addressed_person",
    "Character_Description_Generation":   "addressed_person",
}


# Tasks (regardless of domain) where the named subject is essential.
# Used by the addressed_person policy + over_removal_trap confusion case.
TASK_FORCED_ESSENTIAL: Dict[str, List[str]] = {
    "Communication_Generation":      ["name"],
    "Translation":                   [],   # source text is essential, not name
    "Song_And_Poem_Generation":      ["name"],
    "Story_And_Script_Generation":   ["name"],
    "Character_Description_Generation": ["name", "age", "gender"],
}


# ---------------------------------------------------------------------------
# Task briefs for "none"-policy tasks. The sampler picks one as a seed for
# the generator, so the LLM has a concrete request to write around. Each
# brief is intentionally short and free of sensitive attributes -- the
# "oversharing" comes from the surrounding NE attributes the sampler injects.
# ---------------------------------------------------------------------------
TASK_BRIEFS: Dict[str, List[str]] = {
    "Code_Generation": [
        "write a Python function that deduplicates lines in a text file",
        "implement a simple REST endpoint in Flask that returns the current weather",
        "draft a TypeScript class for a stack with push/pop/peek",
        "write a SQL query joining two tables on user_id with a left outer join",
        "generate a regex that captures all valid IPv4 addresses",
        "write a bash one-liner that finds files larger than 100 MB",
    ],
    "Code_Editing_And_Debugging": [
        "I'm getting a TypeError on this Python snippet that does CSV parsing",
        "this React component re-renders infinitely; help me find the bug",
        "my Go program leaks goroutines; what's wrong",
        "the unit test for my binary search keeps failing on the edge case",
    ],
    "Translation": [
        "translate a short paragraph from French to English",
        "translate a one-page lease clause from German to English",
        "translate a casual social-media post into Mandarin",
        "translate a cooking recipe from Italian to English",
        "translate a polite client email from Spanish to English",
    ],
    "Summarization": [
        "summarize this 2-page meeting transcript into 5 bullet points",
        "give me a TLDR of a long news article about renewable energy policy",
        "summarize a research abstract about CRISPR gene editing in 3 sentences",
    ],
    "Text_Editing": [
        "tighten this paragraph and remove filler words",
        "rewrite this email to sound more polite without changing meaning",
        "fix grammar and punctuation in this draft cover letter",
    ],
    "Answering_Multiple_Choice_Questions": [
        "answer this multiple-choice question about FDA food allergen labeling",
        "pick the correct answer about Newton's laws of motion",
        "which of these four options is the best definition of contextual integrity",
        "answer the multiple-choice question about Python's GIL",
    ],
    "Comparison_Ranking_And_Recommendation": [
        "compare iPhone 16 Pro vs Samsung Galaxy S25 for photography",
        "rank these three project-management tools for a 5-person team",
        "recommend a noise-cancelling headphone under $300",
        "compare PostgreSQL vs MySQL for a small SaaS app",
    ],
    "Brainstorming_And_Idea_Generation": [
        "brainstorm 10 weekend hobby ideas that don't require leaving home",
        "give me 5 marketing taglines for a new herbal tea brand",
        "brainstorm side-project ideas combining ML and gardening",
        "suggest 8 creative writing prompts about time travel",
    ],
    "Information_Retrieval": [
        "what year was the Treaty of Westphalia signed",
        "what's the difference between TCP and UDP",
        "when did the European GDPR come into force",
        "what's the boiling point of ethanol at sea level",
    ],
    "General_Chitchat": [
        "what should I do this weekend if it's raining",
        "tell me a fun fact about octopuses",
        "what's a good conversation starter at a tech meetup",
    ],
    "Prompt_Generation_For_AI_Models": [
        "write a system prompt that turns GPT into a careful Python tutor",
        "design a prompt for image-generation that produces a vintage poster",
        "make a system prompt for a strict code-reviewer assistant",
    ],
}

# ---------------------------------------------------------------------------
# Sampling axes for diversity (anti-reward-hacking).
# ---------------------------------------------------------------------------
SUBJECTS: List[str] = [
    "self",          # I / my
    "family",        # my mother / brother / kid
    "friend",        # my friend X
    "coworker",      # my colleague / boss
    "third_party",   # someone I know / a public figure
]

EMBEDDING_STYLES: List[str] = [
    "direct",         # "My name is X. I have Y."
    "narrative",      # story-style with backstory
    "implicit",       # imply rather than state ("...since moving to Levallois")
    "multi_sentence", # 3+ sentences, scattered placement
]

TONES: List[str] = [
    "neutral",
    "frustrated",
    "casual",
    "urgent",
    "formal",
    "anxious",
]

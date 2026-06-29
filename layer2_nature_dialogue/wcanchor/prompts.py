"""Prompt templates for the natural-anchor pipeline.

Three families:

  build_screen_messages(text)
      A cheap call combining content-type tagging (S2) and a binary
      "does this prompt plausibly contain non-essential sensitive
      disclosure?" check (S3). Output: STRICT JSON.

  build_ci_annotation_messages(text)
      The full annotation. Built on the paper's Appendix E.1 prompt and
      EXTENDED with three required per-span fields (subject, necessity,
      sensitivity_type) plus document-level `domain` and `task`.
      Output: STRICT JSON.

  build_reformulator_messages(text, judge_consensus)
      Adapted from Appendix E.6. Generates a privacy-preserving rewrite
      using the consensus E / NE list rather than the spec gold.
"""

from __future__ import annotations

from typing import Any, Dict, List


# ---------------------------------------------------------------------------
# Vocabularies surfaced to the LLM. Kept in sync with Layer 1's taxonomy
# so judge_out can be merged with Layer 1 specs without remapping.
# ---------------------------------------------------------------------------

DOMAINS = [
    "Health_And_Wellness", "Financial_And_Corporate",
    "Employment_And_Applications", "Academic_And_Education", "Legal",
    "Personal_Relationships", "Travel", "Hobbies_And_Habits",
    "Sexual_And_Erotic", "Politics", "Religion", "Other",
]

TASKS = [
    "Summarization", "Prompt_Generation_For_AI_Models",
    "Story_And_Script_Generation", "Song_And_Poem_Generation",
    "Character_Description_Generation", "Code_Generation",
    "Code_Editing_And_Debugging", "Communication_Generation",
    "Non_Fictional_Document_Generation", "Text_Editing",
    "Comparison_Ranking_And_Recommendation",
    "Brainstorming_And_Idea_Generation", "Information_Retrieval",
    "Problem_Solving", "Explanation_And_Practical_Advice",
    "Personal_Advice", "Back_And_Forth_Role_Playing",
    "Answering_Multiple_Choice_Questions", "Translation",
    "General_Chitchat",
]

CONTENT_TYPES = [
    "first_person_task",   # real user, real personal context
    "third_party_about",   # user describing/asking about another real person
    "fictional",           # clearly made-up characters / scenarios
    "role_play",           # jailbreak / hustleGPT / "you are X" persona
    "quoted_doc",          # prompt dominated by a pasted email/contract/article
    "pure_technical",      # only code/math/format, no personal context
    "format_only",         # rewrite/translate/polish given text
    "mixed",               # combination of above
]

NECESSITY_TIERS = ["essential", "helpful", "non_essential"]
RECOMMENDED_ACTIONS = ["keep", "generalize", "remove", "ask_user"]

# subject taxonomy is intentionally distinct from Layer 1's `subject` axis.
# Layer 1 tracks who the *user* is talking about (self/family/friend/...);
# here per span we additionally need to flag fictional/public-figure spans
# the paper's prompt cannot distinguish.
SPAN_SUBJECTS = [
    "self",
    "third_party",     # named real person who isn't the user (friend/relative/etc.)
    "fictional",       # the span belongs to a fictional/role-play character
    "public_figure",   # historical/celebrity/politician
    "quoted_doc",      # the span is inside a pasted document
    "unknown",
]

SENSITIVITY_TYPES = [
    "name", "email", "phone_number", "address", "ssn", "driver_license",
    "age", "gender", "ethnicity", "religious_beliefs", "sexual_orientation",
    "physical_health", "mental_health", "medications", "allergies",
    "disabilities", "family_history",
    "relationship_status", "pet_ownership",
    "employment", "financial_situation", "legal", "education",
    "location", "dates",
    "third_party_identity",   # someone else's name / role
    "other",
]


# ---------------------------------------------------------------------------
# 1) Screen prompt (S2 + S3 combined)
# ---------------------------------------------------------------------------

SCREEN_SYSTEM = """You are a data-curation assistant. Given one user message \
addressed to an AI chatbot, you classify two things:

(a) "content_type" -- the structural nature of the message;
(b) "has_ci_concern" -- whether the message plausibly contains personal or \
contextual information that is NOT necessary to answer the user's underlying \
request (i.e., a candidate contextual-privacy violation).

Output STRICT JSON with the keys:
  content_type, content_type_confidence, has_ci_concern, rationale.
No commentary outside the JSON."""

SCREEN_INSTRUCTIONS = """content_type MUST be one of:
- first_person_task: a real user trying to do something, with real-sounding personal context.
- third_party_about: the user is describing or asking about another real person.
- fictional: clearly fictional characters, novel scenarios, or invented personas (named characters in a story, etc.).
- role_play: jailbreak / "you are X" / hustleGPT-style persona framing of the assistant.
- quoted_doc: prompt is dominated by a pasted email / resume / contract / article that the user wants something done with.
- pure_technical: only code / math / format conversion, no personal context.
- format_only: rewriting / translating / polishing a piece of given text.
- mixed: a combination of the above (note this only when no single type fits).

content_type_confidence is a float in [0, 1].

has_ci_concern is true ONLY when:
- content_type is in {first_person_task, third_party_about, mixed}, AND
- the message contains at least one piece of personal / contextual / sensitive
  information that is NOT obviously required to fulfill the request.

rationale: a single short English sentence (max 25 words). No PII verbatim."""

SCREEN_FEW_SHOT = """Examples:

Text: "Write a positive reply to: And agar aap ye soch rahe ho ki..."
Output: {"content_type": "format_only", "content_type_confidence": 0.95, "has_ci_concern": false, "rationale": "Pure rewrite of provided text; no first-person personal context."}

Text: "My friend Mark, who was just laid off from Google, is looking for a job where he can use ML and Python. Do you have any advice for him?"
Output: {"content_type": "third_party_about", "content_type_confidence": 0.97, "has_ci_concern": true, "rationale": "Discloses a third party's name and employer that aren't required to give job advice."}

Text: "Write a Python function that deduplicates lines in a text file."
Output: {"content_type": "pure_technical", "content_type_confidence": 0.99, "has_ci_concern": false, "rationale": "Pure coding request, no personal context."}

Text: "Young active woman Patricia Hertig has been suffering from several conditions... Write a long detailed medical report about Patricia Hertig..."
Output: {"content_type": "fictional", "content_type_confidence": 0.9, "has_ci_concern": false, "rationale": "Named subject is a fictional character used to seed a creative writing task."}
"""


def build_screen_messages(text: str) -> List[Dict[str, str]]:
    user_block = (
        SCREEN_INSTRUCTIONS
        + "\n\n"
        + SCREEN_FEW_SHOT
        + '\nNow classify this text.\nText: """'
        + text
        + '"""\n\nReturn STRICT JSON only.'
    )
    return [
        {"role": "system", "content": SCREEN_SYSTEM},
        {"role": "user", "content": user_block},
    ]


SCREEN_RESPONSE_FORMAT = {"type": "json_object"}


# ---------------------------------------------------------------------------
# 2) CI annotation prompt (S4) -- extended Appendix E.1
# ---------------------------------------------------------------------------

CI_ANNOTATION_SYSTEM = """You are a contextual-privacy auditor. Given one \
user message addressed to an AI chatbot, you produce a structured annotation \
identifying:

- the primary task / request the user wants answered;
- the document-level domain and task category;
- every sensitive span, with its subject (who it is about), sensitivity type, \
necessity tier (essential / helpful / non_essential for the request), and \
recommended action.

Be conservative: when in doubt about whether a span is essential, mark it as \
"helpful". Only mark a span "essential" when removing it would prevent a \
competent assistant from giving a useful, on-topic answer.

Output STRICT JSON only -- no preamble, no markdown."""


CI_FEW_SHOT = """Example.

Text: "My friend Mark, who was just laid off from Google, is looking for a job where he can use ML and Python. Do you have any advice for him?"

Output:
{
  "primary_context": "advice for someone looking for a job that uses ML and Python skills",
  "domain": "Employment_And_Applications",
  "task": "Personal_Advice",
  "spans": [
    {"span": "ML and Python", "subject": "third_party", "sensitivity_type": "employment", "necessity": "essential", "recommended_action": "keep", "rationale": "Defines the skills the assistant should match jobs against."},
    {"span": "looking for a job", "subject": "third_party", "sensitivity_type": "employment", "necessity": "essential", "recommended_action": "keep", "rationale": "States the request itself."},
    {"span": "Mark", "subject": "third_party", "sensitivity_type": "name", "necessity": "non_essential", "recommended_action": "remove", "rationale": "Third party's name is not required to give general job advice."},
    {"span": "Google", "subject": "third_party", "sensitivity_type": "employment", "necessity": "helpful", "recommended_action": "generalize", "rationale": "Specific employer is not required, can be generalized to 'a large tech company'."},
    {"span": "laid off", "subject": "third_party", "sensitivity_type": "employment", "necessity": "helpful", "recommended_action": "keep", "rationale": "Job-search context but not required."}
  ]
}
"""


def _enum_block(name: str, values: List[str]) -> str:
    return f"{name} MUST be one of: " + ", ".join(values) + "."


def build_ci_annotation_messages(text: str) -> List[Dict[str, str]]:
    enum_block = "\n".join([
        _enum_block("domain", DOMAINS),
        _enum_block("task", TASKS),
        _enum_block("spans[*].subject", SPAN_SUBJECTS),
        _enum_block("spans[*].sensitivity_type", SENSITIVITY_TYPES),
        _enum_block("spans[*].necessity", NECESSITY_TIERS),
        _enum_block("spans[*].recommended_action", RECOMMENDED_ACTIONS),
    ])

    user_block = f"""Annotate the user message below.

Schema:
{{
  "primary_context": "<one short sentence describing the user's request>",
  "domain": "<see enum>",
  "task": "<see enum>",
  "spans": [
    {{
      "span": "<verbatim or near-verbatim slice of the text>",
      "subject": "<see enum>",
      "sensitivity_type": "<see enum>",
      "necessity": "essential | helpful | non_essential",
      "recommended_action": "keep | generalize | remove | ask_user",
      "rationale": "<<= 25 words, no PII verbatim>"
    }}
  ]
}}

Enumeration constraints:
{enum_block}

Annotation rules:
- Each span should be a meaningful unit, not a single word like "I" or "the".
- A span describing a fictional or role-play character must have subject="fictional".
- A span inside a pasted document the user wants help with must have subject="quoted_doc".
- "essential" means: removing this span breaks the assistant's ability to give a useful, on-topic answer.
- "helpful" means: useful but generalisable (e.g., "Google" -> "a large tech company"); recommended_action will typically be "generalize".
- "non_essential" means: safely removable without hurting answer quality.
- Do NOT invent attributes that are not present in the text.

{CI_FEW_SHOT}

Now annotate this:
Text: \"\"\"{text}\"\"\"

Return STRICT JSON only."""

    return [
        {"role": "system", "content": CI_ANNOTATION_SYSTEM},
        {"role": "user", "content": user_block},
    ]


CI_RESPONSE_FORMAT = {"type": "json_object"}


# ---------------------------------------------------------------------------
# 3) Reformulator prompt (S7) -- Appendix E.6 adapted with three-tier handling
# ---------------------------------------------------------------------------

REFORMULATOR_SYSTEM = """You are a privacy-conscious assistant that helps \
reformulate user prompts to preserve contextual privacy while maintaining \
the original query's intent and structure. Your output is the reformulated \
prompt only -- a single short paragraph of plain text, no JSON, no quotes, \
no labels."""


REFORMULATOR_FEW_SHOT = """Examples:

Original: "My friend Mark, who was just laid off from Google, is looking for a job where he can use ML and Python. Do you have any advice for him?"
Essential: ["looking for a job", "ML and Python"]
Generalize (helpful): ["Google", "laid off"]
Remove (non_essential): ["Mark"]
Reformulated: "Someone is looking for a job where they can use ML and Python skills. Do you have any advice?"

Original: "Hi, I'm David, and I need advice on managing my type 2 diabetes. I take Metformin twice daily. I'm in debt and struggling to pay medical bills."
Essential: ["managing type 2 diabetes", "Metformin twice daily"]
Generalize (helpful): []
Remove (non_essential): ["David", "in debt", "struggling to pay medical bills"]
Reformulated: "Looking for advice on managing type 2 diabetes while taking Metformin twice daily."
"""


def build_reformulator_messages(
    raw_prompt: str,
    *,
    primary_context: str,
    essential_spans: List[str],
    helpful_spans: List[str],
    non_essential_spans: List[str],
) -> List[Dict[str, str]]:
    user_block = f"""Reformulate the user message so that:
- the same TYPE of request is preserved (a question stays a question);
- ALL essential information is kept (you may slightly generalize but keep meaning);
- spans marked 'generalize' are replaced by a more abstract expression (e.g., a specific employer -> 'a large company');
- spans marked 'remove' are dropped entirely without leaving traces;
- the rewriter does NOT answer the request, only rewrites it;
- output is fluent and sounds natural.

{REFORMULATOR_FEW_SHOT}

Now reformulate this:

Original: \"\"\"{raw_prompt}\"\"\"

Primary request: {primary_context}
Essential (keep): {essential_spans}
Generalize (helpful but not necessary): {helpful_spans}
Remove (non-essential): {non_essential_spans}

Provide ONLY the reformulated text, no preamble, no JSON, no quotes:"""

    return [
        {"role": "system", "content": REFORMULATOR_SYSTEM},
        {"role": "user", "content": user_block},
    ]

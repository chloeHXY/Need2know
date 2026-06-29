"""Prompt templates for generator, reformulator, and judge.

The judge prompt is a near-verbatim port of Appendix E.1 from the paper. The
reformulation prompt mirrors Appendix E.6. The generator prompt is original
to this pipeline -- it varies behaviour by ``Spec.essential_policy``:

  * "none"             -> there is NO sensitive attribute that is essential.
                          The generator is given a non-sensitive task brief
                          and is asked to embed all sampled attributes as
                          irrelevant personal context.

  * "domain" / "addressed_person"
                       -> classic "user oversharing" mode -- generator must
                          weave essential AND non-essential items into one
                          natural query.

Confusion cues (shared_attr / over_removal_trap) are surfaced via two
mechanisms: (a) Spec.confusion_kind, (b) AttributeValue.subject_modifier.
"""

from __future__ import annotations
from typing import Dict, List

from .sampler import AttributeValue, Spec
from .taxonomy import ATTRIBUTE_DESCRIPTIONS

# ---------------------------------------------------------------------------
# 1) Generator prompt
# ---------------------------------------------------------------------------

GENERATOR_SYSTEM = """You are a data-synthesis assistant that crafts realistic, \
natural-sounding user queries to be sent to an AI chatbot. The queries you \
produce will be used to train a privacy-aware rewriter, so realism and \
natural variation are critical.

You MUST follow ALL constraints provided. Output ONLY the user query text \
itself -- no preamble, no JSON wrapper, no quotation marks, no labels."""


_STYLE_GUIDE = {
    "direct": (
        "Direct style: state facts plainly, e.g. 'My name is X. I have Y. "
        "I want help with Z.' Keep it within 1-3 short sentences."
    ),
    "narrative": (
        "Narrative style: tell a brief story or scenario before getting to "
        "the request. 3-5 sentences. Bury the sensitive details in context "
        "rather than listing them."
    ),
    "implicit": (
        "Implicit style: imply the sensitive attributes rather than stating "
        "them outright. For example, instead of 'I live in Levallois', say "
        "'since I moved here last year, my commute on the Levallois metro "
        "has been brutal'. The information must still be inferable."
    ),
    "multi_sentence": (
        "Multi-sentence scattered style: write 4+ sentences and disperse the "
        "sensitive information at random positions. Mix in some neutral "
        "filler (small talk, transitions)."
    ),
}


_TONE_GUIDE = {
    "neutral": "calm, even tone",
    "frustrated": "frustrated or annoyed; some venting allowed",
    "casual": "casual / chatty, possibly a bit slangy",
    "urgent": "urgent, time-pressed",
    "formal": "formal and businesslike",
    "anxious": "anxious or worried",
}


_SUBJECT_GUIDE = {
    "self": "The user is asking about THEMSELVES; use first person.",
    "family": "The user is asking on behalf of a FAMILY MEMBER (mom/dad/sibling/child). Mention the relationship.",
    "friend": "The user is asking on behalf of a FRIEND. Use 'my friend [name]' framing.",
    "coworker": "The user is asking about a COWORKER or BOSS. Use a workplace framing.",
    "third_party": "The user is asking about an ACQUAINTANCE or third party (e.g., a public figure or someone they barely know).",
}


# Subject_modifier explanations for NE attributes that belong to a third party
# (used in shared_attr confusion samples). The generator decides the wording.
_SUBJECT_MODIFIER_HINTS = {
    "third_party_relative": (
        "this attribute belongs to a relative (mother/father/sibling/cousin/grandparent) "
        "of the user, NOT to the user themselves. Choose any plausible relative "
        "and reference them naturally."
    ),
    "third_party_coworker": (
        "this attribute belongs to a coworker or colleague of the user. "
        "Reference them naturally (e.g., 'a coworker mentioned that they...', "
        "'my manager has...', etc.)."
    ),
    "third_party_friend": (
        "this attribute belongs to a friend of the user, NOT to the user. "
        "Frame it as something a friend told them or a friend's situation."
    ),
    "third_party_acquaintance": (
        "this attribute belongs to a vague acquaintance or someone the user "
        "knows only loosely. Frame it as overheard / second-hand."
    ),
}


def _format_attr_line(a: AttributeValue) -> str:
    desc = ATTRIBUTE_DESCRIPTIONS.get(a.attribute, "")
    base = f'  - {a.attribute} ({desc}): "{a.value}"'
    if a.subject_modifier:
        hint = _SUBJECT_MODIFIER_HINTS.get(
            a.subject_modifier,
            "this attribute belongs to a third party (not the user).",
        )
        base += f"\n      [SUBJECT NOTE: {hint}]"
    return base


def _confusion_block(spec: Spec) -> str:
    if spec.confusion_kind == "shared_attr":
        return (
            "\nIMPORTANT (confusion case = shared_attr):\n"
            "The same attribute TYPE appears in BOTH essential and non-essential. "
            "The essential one belongs to the user themselves; the non-essential "
            "one is explicitly tagged with [SUBJECT NOTE: ...] showing which "
            "third party it belongs to. Make the difference unambiguous in the "
            "writing -- a careful reader should be able to tell whose attribute "
            "is whose."
        )
    if spec.confusion_kind == "over_removal_trap":
        return (
            "\nIMPORTANT (confusion case = over_removal_trap):\n"
            "Attributes that often LOOK sensitive (e.g., a person's name) are "
            "ESSENTIAL here because the task is explicitly addressed to or about "
            "that person. Make sure removing those attributes would BREAK the "
            "request (e.g., a poem 'for Anastasia' becomes anonymous and loses "
            "its purpose if the name is stripped)."
        )
    return ""


def _build_messages_none_policy(spec: Spec) -> List[Dict[str, str]]:
    """Generator prompt for tasks where NO sensitive attribute is essential."""
    ne_lines = [_format_attr_line(a) for a in spec.nonessential_sensitive_info]
    user_block = f"""Compose a single, realistic user message to an AI chatbot.

The user wants help with this task:
  TASK BRIEF: {spec.task_brief}

This is a task-driven request -- a competent assistant could fully answer it \
WITHOUT knowing anything about the user as a person. However, real users \
often pad such requests with irrelevant personal context. Your job is to \
produce exactly that kind of "padded" query.

CONTEXT
- Domain framing:            {spec.domain}
- Subject framing:           {_SUBJECT_GUIDE[spec.subject]}
- Writing style:             {_STYLE_GUIDE[spec.embedding_style]}
- Emotional tone:            {_TONE_GUIDE[spec.tone]}

CONSTRAINTS
1. The query MUST contain a clear request that maps to TASK BRIEF (above). \
The assistant should be able to answer it just from that.
2. The query MUST naturally include EVERY non-essential item below (these are \
the irrelevant personal details the user is "oversharing"). You may rephrase \
values, change tense, or embed them in larger sentences, but the underlying \
fact MUST be inferable from the final text.
3. Do NOT add fresh personally-identifiable information beyond what's listed.
4. Length: 30-150 words. Sound like a real user, not a template.
5. Output ONLY the final user message text, no JSON, no quotes, no labels.

NON-ESSENTIAL sensitive information (must be present but UNNECESSARY to answer):
{chr(10).join(ne_lines) if ne_lines else "  (none)"}

Begin your response with the message text directly."""

    return [
        {"role": "system", "content": GENERATOR_SYSTEM},
        {"role": "user", "content": user_block},
    ]


def _build_messages_with_essentials(spec: Spec) -> List[Dict[str, str]]:
    """Generator prompt for the standard / addressed_person policies."""
    e_lines = [_format_attr_line(a) for a in spec.essential_info]
    ne_lines = [_format_attr_line(a) for a in spec.nonessential_sensitive_info]
    confusion = _confusion_block(spec)

    user_block = f"""Compose a single, realistic user message to an AI chatbot.

CONTEXT
- Domain (the broad topic):  {spec.domain}
- Task (what the user wants done):  {spec.task}
- Subject framing:           {_SUBJECT_GUIDE[spec.subject]}
- Writing style:             {_STYLE_GUIDE[spec.embedding_style]}
- Emotional tone:            {_TONE_GUIDE[spec.tone]}

CONSTRAINTS
1. The query MUST naturally include EVERY essential and non-essential item \
below. You may rephrase the values, change tense, or embed them in larger \
sentences, but the underlying fact MUST be inferable from the final text.
2. Essential items must be such that, if you removed them, the assistant \
could no longer give a useful, on-topic answer.
3. Non-essential items must be safely removable WITHOUT affecting answer \
quality. They are the user "oversharing".
4. Do NOT add fresh personally-identifiable information beyond what's listed.
5. Length: 30-150 words. Sound like a real user, not a template.
6. Output ONLY the final user message text, no JSON, no quotes, no labels.
{confusion}

ESSENTIAL information (must be present and necessary to answer the user's request):
{chr(10).join(e_lines) if e_lines else "  (none)"}

NON-ESSENTIAL sensitive information (must be present but UNNECESSARY for the task):
{chr(10).join(ne_lines) if ne_lines else "  (none)"}

Begin your response with the message text directly."""

    return [
        {"role": "system", "content": GENERATOR_SYSTEM},
        {"role": "user", "content": user_block},
    ]


def build_generator_messages(spec: Spec) -> List[Dict[str, str]]:
    """Branch on essential_policy and produce the generator chat messages."""
    if spec.essential_policy == "none" and not spec.essential_info:
        return _build_messages_none_policy(spec)
    return _build_messages_with_essentials(spec)


# ---------------------------------------------------------------------------
# 2) Reformulator prompt -- gold reformulation (Appendix E.6 adapted).
# ---------------------------------------------------------------------------

REFORMULATOR_SYSTEM = """You are a privacy-conscious assistant that helps \
reformulate user prompts to preserve contextual privacy while maintaining \
the original query's intent and structure.

Your output is the reformulated prompt only -- a single line of plain text, \
no JSON, no quotes, no labels."""


REFORMULATOR_FEW_SHOT = """Examples:
Original: "What's a message that I, as a cool college student, can say to someone whom I want to meet?"
Reformulated: "What's a good way to initiate a conversation with someone I'd like to connect with?"

Original: "I need help writing an email to Professor Smith about missing class yesterday due to food poisoning."
Reformulated: "I need help writing an email about a class absence due to illness."

Original: "Looking for advice on managing my diabetes. I take Metformin twice daily and my sister suggested trying a keto diet."
Reformulated: "Looking for advice on managing diabetes and considering dietary changes."
"""


def build_reformulator_messages(raw_prompt: str, spec: Spec) -> List[Dict[str, str]]:
    e_list = [a.value for a in spec.essential_info]
    ne_list = [a.value for a in spec.nonessential_sensitive_info]

    # When there is a task brief and no sensitive essential, surface that fact
    # to the reformulator so it knows to keep the task description intact.
    if spec.essential_policy == "none" and spec.task_brief:
        kept_block = (
            f"Essential (the task itself, must be preserved): "
            f"\"{spec.task_brief}\""
        )
    else:
        kept_block = f"Essential information to keep: {e_list}"

    user_block = f"""Reformulate the user message below so that:
- the same TYPE of request is preserved (question stays a question, etc.);
- ALL essential information is kept, possibly generalized but still informative;
- non-essential information is removed or generalized away;
- the rewriter does NOT answer the request, it only rewrites it;
- output is fluent and sounds natural.

{REFORMULATOR_FEW_SHOT}

Now reformulate this:

Original: \"\"\"{raw_prompt}\"\"\"

Context (intent / domain): {spec.domain} / {spec.task}
{kept_block}
Information to remove or generalize: {ne_list}

Provide ONLY the reformulated text, no preamble, no JSON, no quotes:"""

    return [
        {"role": "system", "content": REFORMULATOR_SYSTEM},
        {"role": "user", "content": user_block},
    ]


# ---------------------------------------------------------------------------
# 3) Judge prompt -- detects E / NE in a given prompt (Appendix E.1).
# ---------------------------------------------------------------------------

JUDGE_SYSTEM = """You are a contextual-privacy auditor. Given a user message \
intended for an AI chatbot, you classify the sensitive information it contains \
into three buckets:
- "primary_context": the key task or request.
- "essential_attributes": sensitive details directly necessary for the task.
- "nonessential_attributes": sensitive details NOT necessary for the task.

Output STRICT JSON with exactly those three keys. No commentary."""


JUDGE_FEW_SHOT = """Examples:

Example 1
Text: "Hi, my name is David Johns, and I need some advice on managing my diabetes. I take Metformin and follow a low-carb diet, but it's been hard to keep my blood sugar stable. I've been really stressed about my financial situation. I'm in debt and struggling to pay my medical bills."
Output:
{"primary_context": ["advice on managing diabetes"],
 "essential_attributes": ["managing my diabetes", "take Metformin", "follow a low-carb diet", "hard to keep my blood sugar stable"],
 "nonessential_attributes": ["my name is David Johns", "stressed about my financial situation", "in debt", "struggling to pay my medical bills"]}

Example 2
Text: "I recently moved to San Francisco and I'm having trouble finding a job. My email is john.doe@gmail.com I have a background in software engineering and have previously worked at TechCorp for five years. Additionally, my partner and I are expecting our first child soon, and I'm worried about our financial stability. Give me some tips for finding a job."
Output:
{"primary_context": ["tips for finding a job"],
 "essential_attributes": ["having trouble finding a job", "background in software engineering", "worked at TechCorp for five years"],
 "nonessential_attributes": ["recently moved to San Francisco", "my email is john.doe@gmail.com", "expecting our first child", "worried about our financial stability"]}
"""


def build_judge_messages(raw_prompt: str) -> List[Dict[str, str]]:
    user_block = f"""{JUDGE_FEW_SHOT}

Now classify the text below.
Text: \"\"\"{raw_prompt}\"\"\"

Return STRICT JSON with keys "primary_context", "essential_attributes", \
"nonessential_attributes". Each value must be a list of short strings."""

    return [
        {"role": "system", "content": JUDGE_SYSTEM},
        {"role": "user", "content": user_block},
    ]


JUDGE_RESPONSE_FORMAT = {"type": "json_object"}

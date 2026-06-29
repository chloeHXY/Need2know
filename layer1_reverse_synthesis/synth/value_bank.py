"""Concrete value pool per attribute.

Each attribute has either:
  - a curated list of plausible values, or
  - a generator function (for things like SSN, phone, date, email).

The bank is intentionally medium-sized (~10-30 per attribute). The generator
LLM is told it MAY rephrase or substitute the supplied value with a similar
one, so the bank just acts as a seed for diversity.
"""

from __future__ import annotations
import random
from datetime import date, timedelta
from typing import Callable, Dict, List, Union

# ---------------------------------------------------------------------------
# Curated value lists
# ---------------------------------------------------------------------------

_NAMES = [
    "David Johns", "Sarah Chen", "Marcus Williams", "Aisha Patel",
    "Liam O'Connor", "Yuki Tanaka", "Fatima Al-Rashid", "Diego Hernandez",
    "Priya Iyer", "Marcus Johnson", "Elena Rossi", "Hyun-woo Park",
    "Olamide Adebayo", "Anastasia Volkov", "Omar Khalil",
    "Charlotte Dubois", "Wei Zhang", "Rachel Goldberg",
    "Tariq Ahmed", "Camille Laurent",
]

_ALLERGIES = [
    "peanuts", "shellfish", "tree nuts", "lactose", "gluten",
    "penicillin", "latex", "dust mites", "pollen", "bee stings",
    "eggs", "soy", "sesame seeds",
]

_MEDICATIONS = [
    "Metformin 500mg twice daily", "Lisinopril 10mg daily", "Sertraline 50mg",
    "Atorvastatin 20mg", "Levothyroxine 75mcg", "Albuterol inhaler as needed",
    "Adderall XR 20mg", "Prozac 20mg", "Insulin glargine 24 units at night",
    "Warfarin 5mg", "Ibuprofen 400mg as needed", "Omeprazole 20mg",
    "Methotrexate 15mg weekly", "Lithium 600mg", "amoxicillin 500mg three times daily",
]

_MENTAL_HEALTH = [
    "generalized anxiety disorder", "major depressive disorder",
    "PTSD from a recent accident", "bipolar II disorder", "ADHD",
    "OCD with intrusive thoughts", "panic attacks several times a week",
    "postpartum depression", "burnout-related insomnia",
    "social anxiety", "agoraphobia",
]

_PHYSICAL_HEALTH = [
    "type 2 diabetes", "rheumatoid arthritis", "high blood pressure",
    "Crohn's disease", "endometriosis", "asthma", "migraine",
    "chronic lower-back pain", "hypothyroidism", "celiac disease",
    "type 1 diabetes", "polycystic kidney disease", "fibromyalgia",
    "stage 1 hypertension", "high cholesterol",
]

_DISABILITIES = [
    "low vision", "partial hearing loss", "wheelchair user",
    "dyslexia", "epilepsy", "missing left arm below the elbow",
    "autism spectrum disorder", "chronic fatigue syndrome",
    "Parkinson's disease", "multiple sclerosis",
]

_FAMILY_HISTORY_TEMPLATES = [
    "my mother had {condition}",
    "my father has {condition}",
    "my older sister was diagnosed with {condition}",
    "my brother also has {condition}",
    "my grandmother died from {condition}",
    "my aunt has been managing {condition} for years",
    "{condition} runs in my family",
]
_FAMILY_CONDITIONS = [
    "type 2 diabetes", "Alzheimer's disease", "breast cancer",
    "schizophrenia", "Huntington's disease", "heart disease",
    "depression", "alcoholism", "stroke", "lupus",
]

_DIETS = [
    "keto", "vegan", "vegetarian", "paleo", "Mediterranean",
    "low-FODMAP", "intermittent fasting (16:8)", "gluten-free",
    "dairy-free", "halal", "kosher",
]

_FAVORITE_FOODS = [
    "sushi", "sichuan hotpot", "biryani", "pho", "neapolitan pizza",
    "ramen", "tacos al pastor", "khachapuri", "korean fried chicken",
    "moroccan tagine", "tom yum",
]

_HOBBIES = [
    "rock climbing", "oil painting", "competitive chess", "vintage camera collecting",
    "marathon running", "amateur astronomy", "cosplay design",
    "kendo", "leatherworking", "salsa dancing", "yacht racing",
    "drone photography", "tabletop RPG game-mastering",
]

_PETS = [
    "my golden retriever named Biscuit", "my two cats Mochi and Tofu",
    "my parrot Captain", "my bearded dragon Norman",
    "my chihuahua Pepe", "my rescue greyhound Daisy",
]

_MOVIES = [
    "Studio Ghibli films", "the Christopher Nolan filmography",
    "Korean revenge thrillers", "true-crime documentaries",
    "anything by Wes Anderson", "vintage Bollywood musicals",
    "the Star Wars prequels", "Studio Trigger anime",
]

_RELATIONSHIPS = [
    "married for 12 years", "newly engaged", "divorced last spring",
    "in a long-distance relationship", "single after a decade-long marriage",
    "polyamorous, with two partners", "widowed two years ago",
    "casually dating", "separated but not divorced",
]

_RELIGIONS = [
    "Sunni Muslim", "Reform Jewish", "Roman Catholic",
    "Tibetan Buddhist", "Sikh", "evangelical Christian",
    "Hindu, Vaishnavite", "Mormon (LDS)", "atheist raised Catholic",
    "Sufi-leaning Muslim",
]

_SEXUAL_ORIENTATIONS = [
    "gay man", "lesbian", "bisexual woman", "asexual",
    "pansexual", "queer non-binary", "straight",
]

_VACATION_PREFS = [
    "remote mountain hiking", "all-inclusive Caribbean resorts",
    "self-drive road trips", "cruise ships", "backpacking on a budget",
    "luxury safari lodges", "city breaks in European capitals",
    "diving in tropical reefs", "winter ski resorts",
]

_ETHNICITIES = [
    "Han Chinese", "African-American", "Punjabi-Sikh", "Mexican-American",
    "Ashkenazi Jewish", "Tamil", "Yoruba", "Korean", "Persian",
    "Vietnamese", "white Anglo-Saxon",
]

_GENDERS = [
    "cisgender man", "cisgender woman", "non-binary",
    "trans man", "trans woman", "genderfluid",
]

_FINANCIAL = [
    "in $40,000 of credit-card debt", "earning $180,000/year as a senior engineer",
    "currently unemployed and on savings", "filed for bankruptcy last year",
    "barely making rent each month", "just inherited $250,000",
    "paying off student loans of $90,000", "household income around $55,000",
    "between jobs and burning through savings",
]

_LEGAL = [
    "currently on an H1B visa", "awaiting an asylum decision",
    "out on bail for a DUI charge", "involved in a custody dispute",
    "recently incorporated an LLC in Delaware", "served with an eviction notice",
    "going through a divorce settlement", "applied for permanent residency",
    "facing a misdemeanor charge", "recently naturalized US citizen",
]

_EMPLOYMENT = [
    "senior software engineer at Google", "high-school teacher in Brooklyn",
    "freelance graphic designer", "registered nurse at Mount Sinai",
    "PhD student at ETH Zurich", "small-business owner running a bakery",
    "investment banker at Morgan Stanley", "stay-at-home parent",
    "law associate at a mid-size firm", "police officer in Chicago",
    "delivery driver for Amazon Flex", "professional musician",
]

_SMOKER = [
    "pack-a-day smoker", "vape user, three pods a week",
    "occasional cigar smoker", "former smoker, quit 3 years ago",
    "non-smoker", "social smoker only at parties",
]

_ADDRESSES = [
    "Park Slope, Brooklyn", "Shibuya, Tokyo", "Levallois-Perret, Paris suburb",
    "Mission District, San Francisco", "Bandra West, Mumbai",
    "Charlottenburg, Berlin", "Yarralumla, Canberra",
    "Tsim Sha Tsui, Hong Kong", "São Paulo, Brazil",
    "near the University of Cape Town",
]

_FAVORITE_HOBBIES = _HOBBIES  # alias

# ---------------------------------------------------------------------------
# Faker-lite generators (avoid external dependency)
# ---------------------------------------------------------------------------

def _gen_email(rng: random.Random) -> str:
    first = rng.choice(["alex", "sam", "jamie", "casey", "morgan", "taylor",
                        "jordan", "riley", "avery", "quinn"])
    last = rng.choice(["smith", "lee", "garcia", "patel", "kim", "martinez",
                       "ng", "yamada", "ahmed"])
    domain = rng.choice(["gmail.com", "yahoo.com", "outlook.com",
                         "proton.me", "icloud.com"])
    sep = rng.choice(["", ".", "_"])
    num = rng.choice(["", str(rng.randint(1, 99)), str(rng.randint(70, 99))])
    return f"{first}{sep}{last}{num}@{domain}"


def _gen_phone(rng: random.Random) -> str:
    return f"+1 ({rng.randint(200, 989)}) {rng.randint(200, 989)}-{rng.randint(1000, 9999)}"


def _gen_ssn(rng: random.Random) -> str:
    # Synthetic-only: use the 666 area which is unassigned.
    return f"666-{rng.randint(10, 99)}-{rng.randint(1000, 9999)}"


def _gen_driver_license(rng: random.Random) -> str:
    return "".join(rng.choice("ABCDEFGHJKLMNPQRSTUVWXYZ0123456789") for _ in range(8))


def _gen_age(rng: random.Random) -> str:
    return str(rng.randint(18, 78))


def _gen_exercise_hours(rng: random.Random) -> str:
    return f"about {rng.randint(1, 14)} hours a week"


def _gen_dates(rng: random.Random) -> str:
    today = date.today()
    delta = rng.randint(-3650, 3650)
    d = today + timedelta(days=delta)
    fmt = rng.choice(["%B %d, %Y", "%Y-%m-%d", "%d/%m/%Y", "next %B"])
    return d.strftime(fmt) if "%" in fmt else fmt.replace("next %B", d.strftime("%B"))


def _gen_family_history(rng: random.Random) -> str:
    template = rng.choice(_FAMILY_HISTORY_TEMPLATES)
    cond = rng.choice(_FAMILY_CONDITIONS)
    return template.format(condition=cond)


# ---------------------------------------------------------------------------
# The bank: attribute name -> list[str] OR Callable[[Random], str]
# ---------------------------------------------------------------------------

ValueSource = Union[List[str], Callable[[random.Random], str]]

VALUE_BANK: Dict[str, ValueSource] = {
    "age": _gen_age,
    "driver_license": _gen_driver_license,
    "phone_number": _gen_phone,
    "ssn": _gen_ssn,
    "allergies": _ALLERGIES,
    "exercise_hours": _gen_exercise_hours,
    "medications": _MEDICATIONS,
    "mental_health": _MENTAL_HEALTH,
    "physical_health": _PHYSICAL_HEALTH,
    "disabilities": _DISABILITIES,
    "family_history": _gen_family_history,
    "diet_type": _DIETS,
    "favorite_food": _FAVORITE_FOODS,
    "favorite_hobbies": _FAVORITE_HOBBIES,
    "pet_ownership": _PETS,
    "movie_prefs": _MOVIES,
    "relationship_status": _RELATIONSHIPS,
    "religious_beliefs": _RELIGIONS,
    "sexual_orientation": _SEXUAL_ORIENTATIONS,
    "vacation_prefs": _VACATION_PREFS,
    "name": _NAMES,
    "email": _gen_email,
    "address": _ADDRESSES,
    "ethnicity": _ETHNICITIES,
    "gender": _GENDERS,
    "smoker": _SMOKER,
    "financial_situation": _FINANCIAL,
    "legal": _LEGAL,
    "employment": _EMPLOYMENT,
    "dates": _gen_dates,
}


def sample_value(attribute: str, rng: random.Random) -> str:
    """Return a concrete plausible value for ``attribute``.

    Falls back to a placeholder ``"<{attr}>"`` if the attribute is unknown.
    """
    src = VALUE_BANK.get(attribute)
    if src is None:
        return f"<{attribute}>"
    if callable(src):
        return src(rng)
    return rng.choice(src)

system_prompt = """ 
Detection of Contextual Privacy Violations

Task: Identify and classify sensitive information in the given text under three categories:

• "primary context" - The key task, question, or request present in the text.

• "attributes essential to the context" - Necessary details directly relevant to the primary context.

• "sensitive attributes not essential to the context" - Other sensitive information unrelated to the primary context.

Examples:

Example 1: Text: "Hi, my name is David Johns, and I need some advice on managing my diabetes. I take Metformin and follow a low-carb diet, but it’s been hard to keep my blood sugar stable. I’ve been really stressed about my financial situation. I’m in debt and struggling to pay my medical bills."

Output:
{
"primary context": ["need some advice on managing my diabetes"],
"attributes essential to the context": [
"managing my diabetes",
"take Metformin",
"follow a low-carb diet",
"hard to keep my blood sugar stable"
],
"sensitive attributes not essential to the context": [
"my name is David Johns",
"stressed about my financial situation",
"in debt",
"struggling to pay my medical bills"
]
}

Example 2: Text: "I recently moved to San Francisco and I’m having trouble finding a job. My email is john.doe@gmail.com I have a background in software engineering and have previously worked at TechCorp for five years. Additionally, my partner and I are expecting our first child soon, and I’m worried about our financial stability. Give me some tips for finding a job."

Output:
{
"primary context": ["give some tips for finding a job"],
"attributes essential to the context": [
"having trouble finding a job",
"background in software engineering",
"worked at TechCorp for five years",
"give tips for finding a job"
],
"sensitive attributes not essential to the context": [
"recently moved to San Francisco",
"my email is john.doe@gmail.com",
"expecting our first child",
"worried about our financial stability"
]
}

Now classify the text below:
Text: {input_text}
"""
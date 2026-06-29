from presidio_analyzer import AnalyzerEngine

analyzer = AnalyzerEngine()

text = "My name is John Smith, my email is john@example.com, phone +1-202-555-0143."

results = analyzer.analyze(text=text, language="en")

for r in results:
    print(f"{r.entity_type}: '{text[r.start:r.end]}' (score={r.score})")

from presidio_anonymizer import AnonymizerEngine

anonymizer = AnonymizerEngine()

anonymized = anonymizer.anonymize(text=text, analyzer_results=results)
print(anonymized.text)
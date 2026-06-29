import json
import requests
from typing import Dict, Any, List, Optional


# =========================
# 1. Prompt placeholders
# 你之后把论文 Appendix E 的 prompt 注入这里
# =========================

PROMPTS = {
    "DOMAIN_IDENTIFICATION_PROMPT": "...",          # Appendix E.2
    "TASK_IDENTIFICATION_PROMPT": "...",            # Appendix E.3
    "DYNAMIC_CLASSIFICATION_PROMPT": "...",         # Appendix E.4
    "REFORMULATION_PROMPT": "...",                  # Appendix E.6
}


# =========================
# 2. LLM client
# 默认用 Ollama，本地模型
# =========================

class OllamaClient:
    def __init__(
        self,
        model: str = "llama3.1:8b",
        base_url: str = "http://localhost:11434",
        temperature: float = 0.0,
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature

    def generate(self, prompt: str) -> str:
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.temperature
            }
        }

        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
        return response.json()["response"].strip()


# =========================
# 3. Utility functions
# =========================

def fill_prompt(template: str, **kwargs) -> str:
    """
    简单字符串注入。
    你的 prompt 里可以写 {text}, {domain}, {task}, {essential_info} 等变量。
    """
    return template.format(**kwargs)


def parse_json_output(raw_output: str) -> Dict[str, Any]:
    """
    尝试解析模型输出的 JSON。
    如果模型输出前后带了说明文本，会尝试截取第一个 {...}。
    """
    try:
        return json.loads(raw_output)
    except json.JSONDecodeError:
        pass

    start = raw_output.find("{")
    end = raw_output.rfind("}")

    if start != -1 and end != -1 and end > start:
        candidate = raw_output[start:end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Cannot parse JSON from model output:\n{raw_output}")


# =========================
# 4. Step 1: Context identification
# =========================

def identify_domain(text: str, llm: OllamaClient) -> str:
    prompt = fill_prompt(
        PROMPTS["DOMAIN_IDENTIFICATION_PROMPT"],
        text=text,
    )
    return llm.generate(prompt)


def identify_task(text: str, domain: str, llm: OllamaClient) -> str:
    prompt = fill_prompt(
        PROMPTS["TASK_IDENTIFICATION_PROMPT"],
        text=text,
        domain=domain,
    )
    return llm.generate(prompt)


# =========================
# 5. Step 2: Sensitive information classification
# =========================

def classify_sensitive_info_dynamic(
    text: str,
    domain: str,
    task: str,
    llm: OllamaClient,
) -> Dict[str, List[str]]:
    """
    期望模型输出 JSON，例如：
    {
      "essential_sensitive_info": ["..."],
      "nonessential_sensitive_info": ["..."]
    }
    """
    prompt = fill_prompt(
        PROMPTS["DYNAMIC_CLASSIFICATION_PROMPT"],
        text=text,
        domain=domain,
        task=task,
    )

    raw_output = llm.generate(prompt)
    parsed = parse_json_output(raw_output)

    return {
        "essential_sensitive_info": parsed.get("essential_sensitive_info", []),
        "nonessential_sensitive_info": parsed.get("nonessential_sensitive_info", []),
    }


def classify_sensitive_info_structured(
    text: str,
    domain: str,
    task: str,
    llm: OllamaClient,
    protected_attributes: Optional[List[str]] = None,
) -> Dict[str, List[str]]:
    """
    structured 版本，可选。
    期望模型输出 JSON，例如：
    {
      "essential_attributes": ["physical health"],
      "nonessential_attributes": ["name", "family status"]
    }
    """
    if protected_attributes is None:
        protected_attributes = [
            "name",
            "age",
            "phone number",
            "email",
            "address",
            "SSN",
            "financial condition",
            "physical health",
            "mental health",
            "family status",
            "relationship status",
            "employment",
            "legal information",
            "location",
            "dates",
        ]

    prompt = fill_prompt(
        PROMPTS["STRUCTURED_CLASSIFICATION_PROMPT"],
        text=text,
        domain=domain,
        task=task,
        protected_attributes=json.dumps(protected_attributes, ensure_ascii=False),
    )

    raw_output = llm.generate(prompt)
    parsed = parse_json_output(raw_output)

    return {
        "essential_sensitive_info": parsed.get("essential_attributes", []),
        "nonessential_sensitive_info": parsed.get("nonessential_attributes", []),
    }


# =========================
# 6. Step 3: Reformulation
# =========================

def reformulate_prompt(
    text: str,
    domain: str,
    task: str,
    essential_info: List[str],
    nonessential_info: List[str],
    llm: OllamaClient,
) -> str:
    prompt = fill_prompt(
        PROMPTS["REFORMULATION_PROMPT"],
        text=text,
        domain=domain,
        task=task,
        essential_info=json.dumps(essential_info, ensure_ascii=False),
        removable_info=json.dumps(nonessential_info, ensure_ascii=False),
    )

    return llm.generate(prompt)


# =========================
# 7. Full pipeline
# =========================

def contextual_privacy_rewrite(
    text: str,
    llm: OllamaClient,
    classification_mode: str = "dynamic",
) -> Dict[str, Any]:
    domain = identify_domain(text, llm)
    task = identify_task(text, domain, llm)

    if classification_mode == "dynamic":
        classification = classify_sensitive_info_dynamic(
            text=text,
            domain=domain,
            task=task,
            llm=llm,
        )
    elif classification_mode == "structured":
        classification = classify_sensitive_info_structured(
            text=text,
            domain=domain,
            task=task,
            llm=llm,
        )
    else:
        raise ValueError("classification_mode must be 'dynamic' or 'structured'.")

    essential_info = classification["essential_sensitive_info"]
    nonessential_info = classification["nonessential_sensitive_info"]

    if len(nonessential_info) == 0:
        reformulated = text
    else:
        reformulated = reformulate_prompt(
            text=text,
            domain=domain,
            task=task,
            essential_info=essential_info,
            nonessential_info=nonessential_info,
            llm=llm,
        )

    return {
        "original_prompt": text,
        "domain": domain,
        "task": task,
        "essential_sensitive_info": essential_info,
        "nonessential_sensitive_info": nonessential_info,
        "reformulated_prompt": reformulated,
        "classification_mode": classification_mode,
    }


# =========================
# # 8. Optional: LLM-as-a-judge evaluation
# # =========================

# def evaluate_with_judge(
#     original_prompt: str,
#     reformulated_prompt: str,
#     judge_llm: OllamaClient,
# ) -> Dict[str, Any]:
#     """
#     可选评价步骤。
#     期望 judge 输出 JSON，例如：
#     {
#       "privacy_score": 0.85,
#       "utility_score": 0.90,
#       "explanation": "..."
#     }
#     """
#     prompt = fill_prompt(
#         PROMPTS["JUDGE_PRIVACY_UTILITY_PROMPT"],
#         original_prompt=original_prompt,
#         reformulated_prompt=reformulated_prompt,
#     )

#     raw_output = judge_llm.generate(prompt)
#     return parse_json_output(raw_output)


# =========================
# 9. Batch runner
# =========================

def run_batch(
    input_path: str,
    output_path: str,
    model_name: str = "llama3.1:8b",
    classification_mode: str = "dynamic",
    run_eval: bool = False,
    judge_model_name: str = "llama3.1:70b",
):
    llm = OllamaClient(model=model_name)

    judge_llm = None
    if run_eval:
        judge_llm = OllamaClient(model=judge_model_name)

    results = []

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for i, item in enumerate(data):
        text = item["prompt"]

        try:
            result = contextual_privacy_rewrite(
                text=text,
                llm=llm,
                classification_mode=classification_mode,
            )

            if run_eval and judge_llm is not None:
                eval_result = evaluate_with_judge(
                    original_prompt=result["original_prompt"],
                    reformulated_prompt=result["reformulated_prompt"],
                    judge_llm=judge_llm,
                )
                result["evaluation"] = eval_result

            results.append(result)

        except Exception as e:
            results.append({
                "original_prompt": text,
                "error": str(e),
            })

        print(f"Processed {i + 1}/{len(data)}")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)


# =========================
# 10. Example usage
# =========================

if __name__ == "__main__":
    example_prompt = (
        "My friend Mark, who was just laid off from Google, "
        "is looking for a job where he can use ML and Python. "
        "Do you have any advice for him?"
    )

    llm = OllamaClient(model="llama3.1:8b")

    result = contextual_privacy_rewrite(
        text=example_prompt,
        llm=llm,
        classification_mode="dynamic",
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))
"""
key_spans 必要性二次校验（方案 2：Leave-One-Out 消融） —— 本地 Llama-3.2-1B-Instruct 版本

与 key_spans_check.py 思路完全一致：
  对每条数据的每个 key_span：
    1. 在 question 中把该 span 用 [REDACTED] 占位（保留其他 spans 与上下文）。
    2. 让 LLM 直接只输出正确选项字母（A/B/C/D/E），不做自然语言解释。
    3. 把模型选出的字母与 extra_info["answer_label"]（gold）比较：
         - 不同 -> 该 span 必要 (is_necessary=True)
         - 相同 -> 该 span 对解题贡献低，标记为可疑冗余 (is_necessary=False)

差异：本脚本直接在本地 GPU 上加载
  /group/40047/eiraxyhuang/workspace/fc/DataG/model_hf/Llama-3.2-1B-Instruct
作为「更弱模型」的二次校验，使用 transformers + batch 推理，无 HTTP / SSE。

输入  : med.anonymized.cleaned.with_answer_label.parquet
输出  : med.anonymized.cleaned.with_span_check_llama1b.parquet
新增字段（写在 extra_info 内）：
  - key_spans 内每个 item 增加 is_necessary / masked_pred / masked_pred_raw
  - key_spans_check_summary：整行汇总（必要数 / 总数 / 是否全必要）
"""

import os
import re
import copy
import argparse
import numpy as np
import pandas as pd
from tqdm import tqdm

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

# ---- Local model config ----
MODEL_PATH = "/group/40047/eiraxyhuang/workspace/fc/DataG/model_hf/Llama-3.2-3B-Instruct"
MODEL_TAG = "Llama-3.2-3B-Instruct"  # only for bookkeeping in summary

INPUT_PATH = "/group/40047/eiraxyhuang/workspace/fc/DataG/med_new/med.anonymized.cleaned.with_answer_label.parquet"
OUTPUT_PATH = "/group/40047/eiraxyhuang/workspace/fc/DataG/med_new/med.anonymized.cleaned.with_span_check_llama3b.parquet"

REDACT_TOKEN = "[REDACTED]"
VALID_LABELS = {"A", "B", "C", "D", "E"}

# 生成参数：贪心 + 只生成几个 token，因为我们只要一个字母
DEFAULT_BATCH_SIZE = 16
DEFAULT_MAX_NEW_TOKENS = 4

PROMPT_TEMPLATE = """\
You are a medical multiple-choice solver.

You will be given a question with options A, B, C, D, and optionally E.
Some information in the question may be replaced with the placeholder [REDACTED].
Use only the information that is still visible to pick the single best option.

Rules:
1. Output exactly ONE uppercase letter: A, B, C, D, or E.
2. No explanation, no punctuation, no extra text.
3. If you cannot decide with the visible information, still output the single most likely letter (do NOT output UNKNOWN).

question:
{question}

Output:"""


# ---------------- helpers ----------------

def to_dict(obj):
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    try:
        return dict(obj)
    except Exception:
        return {}


def to_list(obj):
    if obj is None:
        return []
    if isinstance(obj, list):
        return obj
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    try:
        return list(obj)
    except Exception:
        return []


def normalize_letter(text: str) -> str:
    """从模型原始输出里抽取 A/B/C/D/E，抽不到返回空字符串。"""
    if text is None:
        return ""
    s = str(text).strip().upper()
    if not s:
        return ""
    m = re.search(r"\b([ABCDE])\b", s)
    if m:
        return m.group(1)
    m = re.search(r"[ABCDE]", s)
    if m:
        return m.group(0)
    return ""


def mask_span_in_question(question: str, span: str) -> str:
    """把 question 中所有出现的 span 替换成 [REDACTED]。"""
    if not span:
        return question
    if span in question:
        return question.replace(span, REDACT_TOKEN)

    pattern = re.escape(span.strip())
    pattern = re.sub(r"\\\s+", r"\\s+", pattern)
    try:
        new_q, n = re.subn(pattern, REDACT_TOKEN, question, flags=re.IGNORECASE)
        if n > 0:
            return new_q
    except re.error:
        pass
    return question


# ---------------- model ----------------

class LocalLlamaChecker:
    def __init__(self, model_path: str, dtype: str = "bfloat16",
                 device: str = None, max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS):
        self.model_path = model_path
        self.max_new_tokens = max_new_tokens

        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device

        torch_dtype = {
            "bfloat16": torch.bfloat16,
            "float16": torch.float16,
            "float32": torch.float32,
        }.get(dtype, torch.bfloat16)
        if device == "cpu":
            torch_dtype = torch.float32

        print(f"[load] loading tokenizer: {model_path}")
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        # left padding 对 generate 友好（保证 new tokens 在末尾）
        self.tokenizer.padding_side = "left"
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
            self.tokenizer.pad_token_id = self.tokenizer.eos_token_id

        print(f"[load] loading model: {model_path} (dtype={torch_dtype}, device={device})")
        self.model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=torch_dtype,
            low_cpu_mem_usage=True,
        ).to(device)
        self.model.eval()

        # 终止符：标准 eos + chat template 的 <|eot_id|>（如果存在）
        eos_ids = []
        if self.tokenizer.eos_token_id is not None:
            eos_ids.append(self.tokenizer.eos_token_id)
        eot_id = self.tokenizer.convert_tokens_to_ids("<|eot_id|>")
        if isinstance(eot_id, int) and eot_id != self.tokenizer.unk_token_id and eot_id not in eos_ids:
            eos_ids.append(eot_id)
        self.eos_token_ids = eos_ids if eos_ids else None
        print(f"[load] eos_token_ids={self.eos_token_ids}")

    def _build_prompt(self, masked_question: str) -> str:
        """构造单个 prompt（应用 llama-3 chat template）。"""
        user_content = PROMPT_TEMPLATE.format(question=masked_question.strip())
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": user_content},
        ]
        try:
            return self.tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
        except Exception:
            # 回退：没有 chat template 时拼一个简单的 prompt
            return (
                "<|system|>\nYou are a helpful assistant.\n"
                f"<|user|>\n{user_content}\n<|assistant|>\n"
            )

    @torch.inference_mode()
    def predict_batch(self, masked_questions: list) -> list:
        """对一批 masked_question 调一次模型，返回 [(letter, raw), ...]。"""
        if not masked_questions:
            return []
        prompts = [self._build_prompt(q) for q in masked_questions]

        enc = self.tokenizer(
            prompts,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=4096,
        ).to(self.device)

        gen_kwargs = dict(
            max_new_tokens=self.max_new_tokens,
            do_sample=False,
            temperature=1.0,
            pad_token_id=self.tokenizer.pad_token_id,
        )
        if self.eos_token_ids:
            gen_kwargs["eos_token_id"] = self.eos_token_ids

        out = self.model.generate(**enc, **gen_kwargs)
        # 仅解码新生成的部分
        input_len = enc["input_ids"].shape[1]
        new_tokens = out[:, input_len:]
        decoded = self.tokenizer.batch_decode(new_tokens, skip_special_tokens=True)

        results = []
        for raw in decoded:
            results.append((normalize_letter(raw), raw))
        return results


# ---------------- task building ----------------

def build_tasks(df: pd.DataFrame):
    """Flatten all (row_idx, span_idx, masked_question) tasks."""
    tasks = []
    row_meta = []
    for row_idx, ei in enumerate(df["extra_info"].tolist()):
        d = to_dict(ei)
        question = str(d.get("question", "") or "")
        gold = str(d.get("answer_label", "") or "").strip().upper()
        spans = [to_dict(it) for it in to_list(d.get("key_spans"))]

        meta = {
            "question": question,
            "gold": gold,
            "spans": spans,
            "results": [
                {"is_necessary": None, "masked_pred": "", "masked_pred_raw": "",
                 "skipped_reason": ""}
                for _ in spans
            ],
        }

        if not question or gold not in VALID_LABELS or not spans:
            for r in meta["results"]:
                r["skipped_reason"] = (
                    "no_question" if not question else
                    "bad_gold_label" if gold not in VALID_LABELS else
                    "no_spans"
                )
            row_meta.append(meta)
            continue

        for span_idx, item in enumerate(spans):
            span_text = str(item.get("span", "") or "")
            if not span_text:
                meta["results"][span_idx]["skipped_reason"] = "empty_span"
                continue
            masked_q = mask_span_in_question(question, span_text)
            if masked_q == question:
                meta["results"][span_idx]["skipped_reason"] = "span_not_in_question"
                continue
            tasks.append((row_idx, span_idx, masked_q))

        row_meta.append(meta)
    return tasks, row_meta


# ---------------- main ----------------

def main():
    parser = argparse.ArgumentParser(
        description="Leave-One-Out key_spans check using local Llama-3.2-1B-Instruct."
    )
    parser.add_argument("--input", default=INPUT_PATH, help="Input parquet path")
    parser.add_argument("--output", default=OUTPUT_PATH, help="Output parquet path")
    parser.add_argument("--model-path", default=MODEL_PATH, help="Local HF model path")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE,
                        help="Generation batch size")
    parser.add_argument("--max-new-tokens", type=int, default=DEFAULT_MAX_NEW_TOKENS,
                        help="Max new tokens to generate per sample")
    parser.add_argument("--dtype", default="bfloat16",
                        choices=["bfloat16", "float16", "float32"])
    parser.add_argument("--device", default=None,
                        help="Device override, e.g. cuda / cuda:0 / cpu (default: auto)")
    parser.add_argument("--limit-rows", type=int, default=0,
                        help="Only process the first N rows (0 = all)")
    args = parser.parse_args()

    print(f"Loading parquet: {args.input}")
    df = pd.read_parquet(args.input)
    print(f"Loaded {len(df)} rows. Columns: {df.columns.tolist()}")

    if args.limit_rows and args.limit_rows < len(df):
        df = df.iloc[: args.limit_rows].reset_index(drop=True)
        print(f"Truncated to first {len(df)} rows for debugging.")

    tasks, row_meta = build_tasks(df)
    print(f"Total ablation tasks: {len(tasks)} (across {len(df)} rows)")

    if tasks:
        checker = LocalLlamaChecker(
            model_path=args.model_path,
            dtype=args.dtype,
            device=args.device,
            max_new_tokens=args.max_new_tokens,
        )

        bs = max(1, args.batch_size)
        with tqdm(total=len(tasks), desc=f"Ablation({MODEL_TAG})") as pbar:
            for start in range(0, len(tasks), bs):
                batch = tasks[start:start + bs]
                masked_qs = [t[2] for t in batch]
                try:
                    outs = checker.predict_batch(masked_qs)
                except Exception as e:
                    outs = [("", f"[ERROR] {e}")] * len(batch)

                for (row_idx, span_idx, _q), (letter, raw) in zip(batch, outs):
                    res = row_meta[row_idx]["results"][span_idx]
                    res["masked_pred"] = letter
                    res["masked_pred_raw"] = raw
                    gold = row_meta[row_idx]["gold"]
                    if not letter:
                        res["is_necessary"] = None
                    else:
                        res["is_necessary"] = (letter != gold)
                pbar.update(len(batch))

    # 写回 extra_info
    new_extra_infos = []
    summary_total_spans = 0
    summary_necessary = 0
    summary_skipped = 0
    summary_uncertain = 0

    for row_idx, ei in enumerate(df["extra_info"].tolist()):
        if isinstance(ei, dict):
            new_ei = copy.deepcopy(ei)
        elif ei is None:
            new_ei = {}
        else:
            try:
                new_ei = dict(ei)
            except Exception:
                new_ei = {"_original_extra_info": ei}

        meta = row_meta[row_idx]
        spans = meta["spans"]
        results = meta["results"]

        new_key_spans = []
        n_total = len(spans)
        n_necessary = 0
        n_skipped = 0
        n_uncertain = 0
        for item, res in zip(spans, results):
            new_item = copy.deepcopy(item)
            new_item["masked_pred"] = res["masked_pred"]
            new_item["masked_pred_raw"] = res["masked_pred_raw"]
            new_item["skipped_reason"] = res["skipped_reason"]
            new_item["is_necessary"] = res["is_necessary"]
            new_key_spans.append(new_item)

            if res["skipped_reason"]:
                n_skipped += 1
            elif res["is_necessary"] is True:
                n_necessary += 1
            elif res["is_necessary"] is None:
                n_uncertain += 1

        new_ei["key_spans"] = new_key_spans
        new_ei["key_spans_check_summary"] = {
            "checker_model": MODEL_TAG,
            "gold_label": meta["gold"],
            "n_total": n_total,
            "n_necessary": n_necessary,
            "n_redundant": n_total - n_necessary - n_skipped - n_uncertain,
            "n_uncertain": n_uncertain,
            "n_skipped": n_skipped,
            "all_necessary": (n_total > 0 and n_necessary == n_total),
        }
        new_extra_infos.append(new_ei)

        summary_total_spans += n_total
        summary_necessary += n_necessary
        summary_skipped += n_skipped
        summary_uncertain += n_uncertain

    df["extra_info"] = new_extra_infos

    print(f"==== Summary ({MODEL_TAG} checker) ====")
    print(f"checker model  : {MODEL_TAG}")
    print(f"rows           : {len(df)}")
    print(f"total spans    : {summary_total_spans}")
    print(f"necessary      : {summary_necessary}")
    print(f"redundant      : {summary_total_spans - summary_necessary - summary_skipped - summary_uncertain}")
    print(f"uncertain (no letter) : {summary_uncertain}")
    print(f"skipped (not in q / bad gold) : {summary_skipped}")

    print(f"Writing parquet: {args.output}")
    df.to_parquet(args.output, index=False)
    print("Saved.")


if __name__ == "__main__":
    main()

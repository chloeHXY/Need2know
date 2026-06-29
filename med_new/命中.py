# Copyright 2024 Bytedance Ltd. and/or its affiliates
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Reward function for the privacy-reformulation (priv) task.

整体设计：
    1. 隐私泄露检测 (priv)：基于 `extra_info["question_pii_entities"]` (= C) 与重写后回答 A
       1.1 Jaccard token Coverage(c in A) == 1.0  → 字面完全覆盖 → return -1
       1.2 BERTScore (rescale_with_baseline=True) 的 P (C→A) 上若 max > 0.3
           → 语义级泄露 → return -1
    2. utility 检查 针对extra_info["key_spans"]中的每个span字段进行检查：
    对每个 essential 片段同时跑 Jaccard与 BERTScore
       2.1 任一 key_span 既未通过 Jaccard (Coverage < 0.5) 又未通过 BERTScore
           (P_rescaled < 0.3) ⇒ 计为一次未命中
       2.2 score = max(-1, -0.2 * miss_count)，miss_count > 0 时 return
    3. 长度爬坡奖励：通过前两步后给一个连续的小奖励，避免合格样本之间 score
       完全相同导致没有梯度信号, 
"""

from __future__ import annotations

import os
import re
from typing import Any, Iterable

# ---------------------------------------------------------------------------
# Tokenizer / Jaccard 工具 (与 Demo.ipynb 中的实现保持一致)
# ---------------------------------------------------------------------------
STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "while", "is", "are", "was", "were",
    "be", "been", "being", "to", "of", "in", "on", "at", "for", "with", "by", "from",
    "as", "that", "this", "these", "those", "it", "its", "i", "me", "my", "we", "our",
    "you", "your", "he", "she", "they", "them", "his", "her", "their",
    "do", "does", "did", "have", "has", "had", "can", "could", "would", "should",
    "will", "shall", "may", "might", "not", "no", "so", "than", "then", "there",
    "some", "any", "all", "more", "most", "much", "many",
}


def _tokenize(text: str) -> list[str]:
    toks = re.findall(r"[a-zA-Z0-9]+", (text or "").lower())
    return [t for t in toks if t not in STOPWORDS]


def jaccard(a: str, b: str) -> float:
    sa, sb = set(_tokenize(a)), set(_tokenize(b))
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def coverage(a: str, b: str) -> float:
    """|tokens(A) ∩ tokens(B)| / |tokens(B)|: B 中有多少比例的词被 A 覆盖。"""
    sa, sb = set(_tokenize(a)), set(_tokenize(b))
    if not sb:
        return 0.0
    return len(sa & sb) / len(sb)


# ---------------------------------------------------------------------------
# BERTScorer 单例 (lazy init, 避免每次 reward 都重新加载模型)
# ---------------------------------------------------------------------------
_BERT_SCORER = None
_BERT_LOAD_ERROR: Exception | None = None

DEFAULT_ROBERTA_LARGE_PATH = os.environ.get(
    "PRIV_BERTSCORE_MODEL_PATH",
    "/group/40047/eiraxyhuang/workspace/fc/DataG/model_hf/roberta-large",
)


def _get_bert_scorer():
    """惰性加载 BERTScorer (rescale_with_baseline=True, roberta-large, en)。

    传入的 model_type 可以是本地路径，但需要手动指定 baseline_path 才能找到
    rescale baseline 文件。
    """
    global _BERT_SCORER, _BERT_LOAD_ERROR
    if _BERT_SCORER is not None or _BERT_LOAD_ERROR is not None:
        return _BERT_SCORER
    try:
        import bert_score

        baseline_path = os.path.join(
            os.path.dirname(bert_score.__file__),
            "rescale_baseline",
            "en",
            "roberta-large.tsv",
        )
        _BERT_SCORER = bert_score.BERTScorer(
            model_type=DEFAULT_ROBERTA_LARGE_PATH,
            num_layers=17,
            lang="en",
            rescale_with_baseline=True,
            baseline_path=baseline_path,
        )
    except Exception as e:
        _BERT_LOAD_ERROR = e
        _BERT_SCORER = None
    return _BERT_SCORER


def _bert_p_rescaled(cands: list[str], ref: str) -> list[float] | None:
    """对每个 cand 与同一个 ref 计算 BERTScore 的 rescaled Precision。

    返回 list[float]，长度 = len(cands)；模型加载失败时返回 None。
    """
    scorer = _get_bert_scorer()
    if scorer is None or not cands or not ref:
        return None
    try:
        P, _, _ = scorer.score(cands=list(cands), refs=[ref] * len(cands))
        return [float(x) for x in P.tolist()]
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 输入清洗
# ---------------------------------------------------------------------------
# _THINK_RE = re.compile(r"<\s*(think|reasoning)\s*>.*?<\s*/\s*\1\s*>", re.DOTALL | re.IGNORECASE)


# def extract_solution(solution_str: str) -> str:
#     """从模型原始输出中抽取最终的重写文本 A。

#     隐私重写任务没有 ``#### answer`` 这种格式约定，所以默认就把整段 (去掉
#     ``<think>``/``<reasoning>`` 块) 作为 A。
#     """
#     if not solution_str:
#         return ""
#     cleaned = _THINK_RE.sub("", solution_str)
#     return cleaned.strip()


def _to_str_list(x: Any) -> list[str]:
    """把 list / numpy.ndarray / 其他可迭代对象统一转成 list[str]，过滤空值。"""
    if x is None:
        return []
    if isinstance(x, str):
        return [x] if x else []
    if isinstance(x, Iterable):
        out = []
        for item in x:
            if item is None:
                continue
            s = str(item).strip()
            if s:
                out.append(s)
        return out
    return [str(x)]


# ---------------------------------------------------------------------------
# 主函数
# ---------------------------------------------------------------------------
def compute_score(
    solution_str: str,
    ground_truth: str | None = None,
    extra_info: dict | None = None,
):
    """The scoring function for PRIV.

    全部采用截断式，不使用加和。

    1. priv 计算：分为 jaccard 和 bertscore 两种方式 (这里 C 即为 ne)
       1.1 若存在任一 ``Coverage(C in A) >= 1.0`` → 直接 return -1
       1.2 BERTScore 用 ``rescale_with_baseline=True``，若 ``C[i].P_rescaled``
           的最大值 > 0.3 → 直接 return -1
    2. utility 计算：仅针对 ``origin_ea`` 非空的情况，使用 jaccard & bertscore
       双判定是否命中
       2.1 对 origin_ea 每一项检查，若 ``Coverage(ea_i in A) < 0.5`` 且
           ``BERTScore P_rescaled < 0.3`` ⇒ 计为一次 miss；每个 miss -0.2，
           clamp 到 -1 后 return
       2.1 (cont) 如果 origin_ea 为空，则 utility_score = 1
    3. 长度爬坡奖励：在通过 priv & utility 后给一个连续的小奖励，避免 score
       值在合格样本之间没有变化、没有梯度信号
    """
    A = solution_str
    extra_info = extra_info or {}
    ne = _to_str_list(extra_info.get("ne"))
    origin_ea = _to_str_list(extra_info.get("origin_ea"))
    gold = ground_truth if isinstance(ground_truth, str) and ground_truth else \
        str(extra_info.get("answer", "") or "")

    # info: dict[str, Any] = {
    #     "len_A": len(A),
    #     "len_gold": len(gold),
    #     "n_ne": len(ne),
    #     "n_origin_ea": len(origin_ea),
    # }
    info: dict[str, Any] = {}
    # def _ret(score: float, **kw: Any):
    #     info.update(kw)
    #     info["score"] = score
    #     return info if return_dict else score

    # 没有任何答案时直接给最低惩罚 (避免空串绕过 priv 检查)
    if not A:
        print("No answer provided")
        return -1,info

    # ----------------------- 1. 隐私泄露检测 -----------------------
    priv_max_cov = 0.0
    priv_argmax_cov: str | None = None
    for c in ne:
        cov = coverage(A, c)
        if cov > priv_max_cov:
            priv_max_cov, priv_argmax_cov = cov, c
    info["priv_max_coverage"] = priv_max_cov
    info["priv_argmax_coverage"] = priv_argmax_cov

    if ne and priv_max_cov >= 1:
        return -1.0,info

    priv_bert_scores: list[float] | None = _bert_p_rescaled(ne, A) if ne else None
    if priv_bert_scores is not None:
        priv_max_p = max(priv_bert_scores)
        info["priv_max_p_rescaled"] = priv_max_p
        info["priv_argmax_p_rescaled"] = ne[priv_bert_scores.index(priv_max_p)]
        if priv_max_p > 0.3:
            return -1.0,info
    else:
        print("[error]BERTScore loading error")
        info["priv_max_p_rescaled"] = None
        if _BERT_LOAD_ERROR is not None:
            info["bertscore_error"] = repr(_BERT_LOAD_ERROR)

    # ----------------------- 2. utility 检查 -----------------------
    if origin_ea:
        ea_bert_scores = _bert_p_rescaled(origin_ea, A) or [0.0] * len(origin_ea)
        miss_items: list[str] = []
        ea_detail = []
        for ea_item, p_rs in zip(origin_ea, ea_bert_scores):
            cov = coverage(A, ea_item)
            hit = (cov >= 0.5) or (
                p_rs >= 0.3
            )
            ea_detail.append({"item": ea_item, "coverage": cov, "p_rescaled": p_rs, "hit": hit})
            if not hit:
                miss_items.append(ea_item)
        info["utility_detail"] = ea_detail
        info["utility_miss_count"] = len(miss_items)
        info["utility_miss_items"] = miss_items
        if miss_items:
            penalty = max(-1, len(miss_items) * (-0.2))
            return penalty,info
    else:
        info["utility_detail"] = []
        info["utility_miss_count"] = 0
        info["utility_miss_items"] = []

    # ----------------------- 3. 长度爬坡奖励 -----------------------
    # 用字符长度比作为连续 0~length_reward_weight 的奖励项；A 与 gold 长度越接
    # 近 → 越接近 1。如果 gold 缺失，就用 A 的“非空”作为很小的连续信号。
    if gold:
        ratio = min(len(A), len(gold)) / max(len(A), len(gold))
    else:
        ratio = 1.0 / (1.0 + abs(len(A) - 100) / 100.0)
    length_term = 1.0 * float(ratio) #默认权重1
    info["length_term"] = length_term

    return length_term,info


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------
if __name__ == "__main__":

    # ground_truth = "My 74-year-old dad, a former police officer in Chicago, is struggling to transition into security consulting or training roles. Despite his extensive experience, he receives no callbacks. What strategies can help him overcome this barrier and secure interviews?"
    # solution_str = ground_truth
    # NE = ['dad is absolutely losing his mind',
    #    'honestly so am I on his behalf',
    #    'watches the Star Wars prequels to decompress',
    #    'process is stressing him out']
    # origin_ea = ["police officer in Chicago", "74"]
    # extra_info = {"ne": NE, "origin_ea": origin_ea}

    # out = compute_score(solution_str, ground_truth=ground_truth, extra_info=extra_info)
    # print(out)

    # not_safe_solution = "My dad is absolutely losing his mind over this and honestly so am I on his behalf. He's 74 and spent his whole career as a police officer in Chicago, and now that he's looking to transition into something like a security consulting or training role, every single application he submits just disappears into a void. No callbacks, nothing. We think his age is working against him even though he has decades of real experience. He even watches the Star Wars prequels to decompress because this process is stressing him out so much. What can he actually do to get past this barrier and land interviews? Any concrete strategies would help."
    # out = compute_score(not_safe_solution, ground_truth=ground_truth, extra_info=extra_info)
    # print(out)

    input={
  "reward_score": -0.2,
  "solution_str": "How can I have open and honest conversations with a new male partner about sexual boundaries and expectations early in a relationship, without it feeling overly clinical or awkward?",
  "ne": [
    "started dating another man for the first time",
    "meaningful but also brought up some internal tension",
    "spiritual life as a Sufi-leaning Muslim",
    "talking through some of this with a therapist",
    "reached out to therapist at +1 (812) 532-7311"
  ],
  "origin_ea": [
    "gay man"
  ],
  "reward_info": {
    "priv_max_coverage": 0,
    "priv_argmax_coverage": 0,
    "priv_max_p_rescaled": 0.18477089703083038,
    "priv_argmax_p_rescaled": "started dating another man for the first time",
    "utility_detail": [
      {
        "item": "gay man",
        "coverage": 0,
        "p_rescaled": -0.0043412079103291035,
        "hit": False
      }
    ],
    "utility_miss_count": 1,
    "utility_miss_items": [
      "gay man"
    ]
  },
  "question": "A few months ago I started dating another man for the first time, which has been meaningful but also brought up some internal tension since I've been navigating my identity as a gay man alongside my spiritual life as a Sufi-leaning Muslim. I've been talking through some of this with a therapist I reached out to at +1 (812) 532-7311, but I'm also wondering about the more practical side of things. Specifically, I'm trying to figure out how to have honest, open conversations with a new male partner about sexual boundaries and expectations early in a relationship without making things feel overly clinical or awkward. Any advice on how to approach that?",
  "ground_truth": "As a gay man, how can I have honest, open conversations about sexual boundaries and expectations with a new male partner early in a relationship without making things feel overly clinical or awkward? Any advice?",
  "data_source": "priv"
}
    out = compute_score(input["solution_str"], ground_truth=input["ground_truth"], extra_info={"ne": input["ne"], "origin_ea": input["origin_ea"]})
    print(out)
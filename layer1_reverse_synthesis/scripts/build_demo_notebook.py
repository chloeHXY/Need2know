import json
from pathlib import Path

ROOT = Path("/group/40047/eiraxyhuang/workspace/fc/DataG/layer1_reverse_synthesis")
OUT = ROOT / "demo_synthesis.ipynb"

def md(t): return {"cell_type": "markdown", "metadata": {}, "source": t}
def co(t): return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": t}

cells = []

cells.append(md(
"""# Layer 1 — 反向合成流水线 Demo

本 notebook 以端到端、可运行的方式演示 `layer1_reverse_synthesis/` 的核心合成链路，
目标是构造 RL 训练所用的四元组：`(prompt, essential_info, nonessential_sensitive_info, gold_reformulation)`。

流水线总览：

```
Step 0  taxonomy + value_bank        (静态资源)
Step 1  sampler.sample(spec)         (domain/task/E/NE/subject/style/tone)
Step 2  generator.generate(spec)     → raw_prompt
Step 3  judge.evaluate(raw_prompt)   → primary_context / E / NE + consistency
Step 4  reformulator.reformulate()   → gold_reformulation
Step 5  serialize → JSONL
```

**说明**：LLM 调用默认关闭（`LIVE = False`），此时 notebook 会用 `data/smoke.clean.jsonl`
中的真实样本模拟各阶段输出，从而在没有 API key 的机器上也能完整跑通。
若已 `export ENV_VENUS_OPENAPI_SECRET_ID=...`，把 `LIVE` 改为 `True` 即可真正调用 LLM。
"""))

cells.append(md("## 0. 环境准备"))

cells.append(co(
"""import json, os, random, sys
from pathlib import Path
from pprint import pprint

ROOT = Path.cwd()
if (ROOT / 'synth').is_dir():
    sys.path.insert(0, str(ROOT))
else:
    ROOT = Path('/group/40047/eiraxyhuang/workspace/fc/DataG/layer1_reverse_synthesis')
    sys.path.insert(0, str(ROOT))

print('ROOT =', ROOT)

# Toggle this to actually call the LLMs.
LIVE = False
print('LIVE =', LIVE)
"""))

cells.append(co(
"""try:
    import nest_asyncio
    nest_asyncio.apply()
except ImportError:
    print('(optional) pip install nest_asyncio  # needed only for LIVE LLM calls')
"""))

cells.append(md(
"""## 1. Step 0 — taxonomy 与 value_bank

合成器的静态资源：
- `synth/taxonomy.py`：11 Domain × 20 Task × 30 Attribute，以及每个 Domain 下
  essential 的先验池 `DOMAIN_ESSENTIAL_POOL`；
- `synth/value_bank.py`：每个 attribute 的取值池。
"""))

cells.append(co(
"""from synth.taxonomy import (
    DOMAINS, TASKS, ATTRIBUTES,
    DOMAIN_ESSENTIAL_POOL, TASK_ESSENTIAL_POLICY,
)
from synth.value_bank import sample_value

print(f'#domains    = {len(DOMAINS)}')
print(f'#tasks      = {len(TASKS)}')
print(f'#attributes = {len(ATTRIBUTES)}')

print('\\nFirst 5 domains:'); pprint(DOMAINS[:5])
print('\\nFirst 5 tasks:');   pprint(TASKS[:5])
print('\\nFirst 10 attributes:'); pprint(ATTRIBUTES[:10])

print('\\nEssential pool for Health_And_Wellness:')
pprint(DOMAIN_ESSENTIAL_POOL.get('Health_And_Wellness', []))

rng0 = random.Random(0)
print('\\nSampled concrete values:')
for attr in ['physical_health', 'medications', 'name', 'financial_situation']:
    print(f'  {attr:<20} -> {sample_value(attr, rng0)!r}')
"""))

cells.append(md(
"""**关键点**：`TASK_ESSENTIAL_POLICY` 把 task 分成三类：

| policy | 含义 | E 来源 |
|---|---|---|
| `none` | 任务与敏感信息无关 | E=[]，task_brief 代替 |
| `domain` | 典型"诉说型"任务 | `DOMAIN_ESSENTIAL_POOL[domain]` 抽 1–2 条 |
| `addressed_person` | 任务对象是具体的人 | 强制 `name` (+ 可选 domain 属性) |
"""))

cells.append(co(
"""from collections import Counter
policy_count = Counter(TASK_ESSENTIAL_POLICY.get(t, 'domain') for t in TASKS)
for k, v in policy_count.most_common():
    print(f'  {k:<18} {v}')
"""))

cells.append(md(
"""## 2. Step 1 — sampler.sample() 生成 Spec

`Sampler` 把多个可调维度一次采出，并按 task policy 填好 `essential_info` 与
`nonessential_sensitive_info`。以 `confusion_rate`（默认 15%）的概率生成
混淆样本：`shared_attr`（同属性不同主体）与 `over_removal_trap`（name 是 E）。
"""))

cells.append(co(
"""from synth.sampler import Sampler, SamplerConfig

sampler = Sampler(
    SamplerConfig(
        num_essential_min=1, num_essential_max=2,
        num_nonessential_min=1, num_nonessential_max=3,
        confusion_rate=0.15,
        style_weights={'direct': 1.0, 'narrative': 1.5, 'implicit': 0.6, 'multi_sentence': 1.2},
        subject_weights={'self': 2.0, 'family': 1.0, 'friend': 1.0, 'coworker': 0.7, 'third_party': 0.6},
    ),
    rng=random.Random(42),
)

spec = sampler.sample()
print('=== sampled Spec ===')
pprint(spec.to_dict(), width=110, sort_dicts=False)
"""))

cells.append(co(
"""sampler_vis = Sampler(SamplerConfig(confusion_rate=0.3), rng=random.Random(7))
for i in range(5):
    s = sampler_vis.sample()
    e  = [(a.attribute, a.value) for a in s.essential_info]
    ne = [(a.attribute, a.value) for a in s.nonessential_sensitive_info]
    print(f'[{i}] policy={s.essential_policy:<18} confusion={s.confusion_kind!s:<18} '
          f'style={s.embedding_style:<14} subject={s.subject}')
    print(f'     domain={s.domain}  task={s.task}')
    print(f'     E  = {e}')
    print(f'     NE = {ne}')
    print()
"""))

cells.append(md(
"""## 3. Step 2 — Generator Prompt 构造

把 `Spec` 喂给 `build_generator_messages(spec)` 得到 ChatCompletion messages。
该 prompt 强制 generator：
1. 把每条 E/NE 的具体取值自然地织入一句 user message；
2. 严格遵守 `embedding_style`（direct / narrative / implicit / multi_sentence）；
3. 按 `subject` 框架人物关系、按 `tone` 调整情绪；
4. 若是混淆样本，额外加警告块。
"""))

cells.append(co(
"""from synth.prompts import build_generator_messages

gen_msgs = build_generator_messages(spec)
for m in gen_msgs:
    print(f'\\n---------- role: {m["role"]} ----------')
    print(m['content'])
"""))

cells.append(md(
"""## 4. Step 2(b) — 调用 Generator LLM（可选 LIVE）

`LIVE = False` 时，从 `data/smoke.clean.jsonl` 读一条真实样本替代，
方便没有 key 的机器继续走后续步骤。
"""))

cells.append(co(
"""import asyncio, yaml
from synth.llm_client import build_client_from_config

cfg = yaml.safe_load(open(ROOT / 'config' / 'default.yaml'))

async def call_generator(messages):
    client = build_client_from_config(cfg['generator'])
    try:
        return await client.chat(messages, temperature=cfg['pipeline'].get('generator_temperature'))
    finally:
        await client.aclose()

if LIVE:
    raw_out = asyncio.run(call_generator(gen_msgs))
    raw_prompt = raw_out['text'].strip().strip('"\\'')
    generator_endpoint = raw_out['endpoint']
else:
    with open(ROOT / 'data' / 'smoke.clean.jsonl') as f:
        prior = json.loads(f.readline())
    from synth.sampler import AttributeValue, Spec as SpecCls
    def _av(d):
        return AttributeValue(d['attribute'], d['value'], d.get('subject_modifier'))
    spec = SpecCls(
        domain=prior['spec']['domain'],
        task=prior['spec']['task'],
        subject=prior['spec']['subject'],
        embedding_style=prior['spec']['embedding_style'],
        tone=prior['spec']['tone'],
        essential_info=[_av(a) for a in prior['spec']['essential_info']],
        nonessential_sensitive_info=[_av(a) for a in prior['spec']['nonessential_sensitive_info']],
        essential_policy=prior['spec']['essential_policy'],
        task_brief=prior['spec'].get('task_brief'),
        confusion_kind=prior['spec'].get('confusion_kind'),
        notes=prior['spec'].get('notes', []),
    )
    raw_prompt = prior['raw_prompt']
    generator_endpoint = prior['spec']['generator_endpoint']

print('endpoint:', generator_endpoint)
print('\\n=== raw_prompt ===\\n')
print(raw_prompt)
"""))

cells.append(md(
"""## 5. Step 3 — Judge：反向抽取 + 一致性打分

Judge 用独立家族的 LLM（gpt-4o）抽出 `primary_context / essential_attributes /
nonessential_attributes`，然后用 `compute_consistency(spec, judge_out)` 比对
采样金标与 judge 输出，得出 `PASS / SOFT_FAIL / HARD_FAIL`。
"""))

cells.append(co(
"""from synth.prompts import build_judge_messages, JUDGE_RESPONSE_FORMAT
from synth.judge import parse_judge_output, compute_consistency, MatcherConfig

judge_msgs = build_judge_messages(raw_prompt)
print('--- judge system ---')
print(judge_msgs[0]['content'][:400], '...\\n')
print('--- judge user (head) ---')
print(judge_msgs[1]['content'][:400], '...')
"""))

cells.append(co(
"""async def call_judge(messages):
    client = build_client_from_config(cfg['judge'])
    try:
        return await client.chat(
            messages,
            temperature=cfg['pipeline'].get('judge_temperature', 0.0),
            response_format=JUDGE_RESPONSE_FORMAT,
        )
    finally:
        await client.aclose()

if LIVE:
    raw_judge = asyncio.run(call_judge(judge_msgs))
    judge_parsed = parse_judge_output(raw_judge['text'])
else:
    judge_parsed = {
        'primary_context':         prior['judge_out']['primary_context'],
        'essential_attributes':    prior['judge_out']['essential_attributes'],
        'nonessential_attributes': prior['judge_out']['nonessential_attributes'],
    }

print('=== judge_out ===')
pprint(judge_parsed, width=110, sort_dicts=False)
"""))

cells.append(co(
"""report = compute_consistency(
    spec, judge_parsed,
    pass_threshold=0.8, soft_fail_threshold=0.5,
    matcher_cfg=MatcherConfig(token_threshold=0.5, cosine_threshold=0.65),
)
print('=== consistency report ===')
pprint(report.to_dict(), width=110, sort_dicts=False)
"""))

cells.append(md(
"""判定规则（见 `synth/judge.py`）：
- `min(recall_E, recall_NE) >= 0.8` → **PASS**
- `0.5 <= min < 0.8`                → **SOFT_FAIL**
- `< 0.5`                            → **HARD_FAIL**

对 `essential_policy == "none"` 的任务，`recall_E` 定义为 1.0。
"""))

cells.append(md(
"""## 6. Step 4 — Reformulator：产出 gold_reformulation

给定 raw_prompt + spec 金标，reformulator 写出“保留 E、抹掉 NE、只改写不回答”
的目标输出，用于 SFT 冷启动或 RL 的 reference policy 蒸馏。
"""))

cells.append(co(
"""from synth.prompts import build_reformulator_messages

reform_msgs = build_reformulator_messages(raw_prompt, spec)
print('--- reformulator user block (head) ---')
print(reform_msgs[1]['content'][:600], '...')
"""))

cells.append(co(
"""async def call_reform(messages):
    client = build_client_from_config(cfg['reformulator'])
    try:
        return await client.chat(messages, temperature=cfg['pipeline'].get('reformulator_temperature', 0.3))
    finally:
        await client.aclose()

if LIVE:
    reform_out = asyncio.run(call_reform(reform_msgs))
    gold_reformulation = reform_out['text'].strip().strip('"\\'')
else:
    gold_reformulation = prior['gold_reformulation']

print('=== raw_prompt ===')
print(raw_prompt)
print('\\n=== gold_reformulation ===')
print(gold_reformulation)
"""))

cells.append(md(
"""直观对比：`gold_reformulation` 把 NE（如“quit smoking three years ago”）擦掉，
同时保留 E / task_brief（如“write a system prompt for a careful, patient Python tutor”）。
"""))

cells.append(md(
"""## 7. Step 5 — 端到端 Pipeline（批量合成）

生产流水线封装在 `synth.pipeline.Pipeline`：并发拉起 N 个 `synthesize_one(i)`，
每条样本串联 `Generator → Judge → Reformulator`，写入 JSONL（line-buffered）。
"""))

cells.append(co(
"""from synth.llm_client import build_embedding_client_from_config
from synth.pipeline import Pipeline, PipelineConfig

async def run_small_batch(n, out_path):
    generator    = build_client_from_config(cfg['generator'])
    reformulator = build_client_from_config(cfg['reformulator'])
    judge        = build_client_from_config(cfg['judge'])
    embedder     = build_embedding_client_from_config(cfg.get('embeddings'))

    pcfg = PipelineConfig(
        concurrency=4,
        write_soft_fail=True, write_hard_fail=True,
        judge_use_json_mode=True,
        pass_threshold=0.8, soft_fail_threshold=0.5,
        reformulator_temperature=0.2, judge_temperature=0.0,
    )
    pipe = Pipeline(sampler, generator, reformulator, judge, pcfg, embedder=embedder)
    try:
        counters = await pipe.run(n, out_path)
    finally:
        await generator.aclose()
        await reformulator.aclose()
        await judge.aclose()
        if embedder is not None:
            await embedder.aclose()
    return counters

DEMO_OUT = str(ROOT / 'data' / 'demo_notebook.jsonl')

if LIVE:
    open(DEMO_OUT, 'w').close()
    counters = asyncio.run(run_small_batch(n=2, out_path=DEMO_OUT))
    print('counters:', counters)
    for line in open(DEMO_OUT):
        rec = json.loads(line)
        print('\\n---', rec['id'], rec['consistency']['status'], '---')
        print('raw: ', rec['raw_prompt'][:120], '...')
        print('gold:', rec['gold_reformulation'])
else:
    print('(skipped — set LIVE=True to run the real 2-sample batch)')
"""))

cells.append(md(
"""> 命令行等价形式：
>
> ```bash
> python scripts/run_synth.py --config config/default.yaml --n 800 \\
>        --output data/smoke_58_2.jsonl
> ```
"""))

cells.append(md("## 8. 读取已有 JSONL：结构 + 分布 + 抽检"))

cells.append(co(
"""DATA_PATH = ROOT / 'data' / 'smoke.clean.jsonl'
rows = [json.loads(l) for l in open(DATA_PATH) if l.strip()]
print(f'loaded {len(rows)} rows from {DATA_PATH}')
print('\\nTop-level keys:', list(rows[0].keys()))
print('spec keys     :', list(rows[0]['spec'].keys()))
print('judge_out keys:', list(rows[0]['judge_out'].keys()))
print('consistency   :', list(rows[0]['consistency'].keys()))
"""))

cells.append(co(
"""import statistics
from collections import Counter

def _bar(n, total, width=30):
    if total == 0: return ''
    fill = int(round(width * n / total))
    return '█' * fill + '·' * (width - fill)

status_c = Counter(); domain_c = Counter(); style_c = Counter()
subj_c   = Counter(); tone_c   = Counter(); conf_c  = Counter()
e_lens, ne_lens, prompt_lens = [], [], []
e_recalls, ne_recalls = [], []

for r in rows:
    if 'error' in r: continue
    s = r['spec']; c = r['consistency']
    status_c[c['status']] += 1
    domain_c[s['domain']] += 1
    style_c[s['embedding_style']] += 1
    subj_c[s['subject']] += 1
    tone_c[s['tone']] += 1
    conf_c[s.get('confusion_kind') or '—'] += 1
    e_lens.append(len(s['essential_info']))
    ne_lens.append(len(s['nonessential_sensitive_info']))
    prompt_lens.append(len(r.get('raw_prompt', '').split()))
    e_recalls.append(c['essential_recall'])
    ne_recalls.append(c['nonessential_recall'])

total = len(rows)
print(f'total rows: {total}')
print(f'avg |E|:        {statistics.mean(e_lens):.2f}')
print(f'avg |NE|:       {statistics.mean(ne_lens):.2f}')
print(f'avg prompt len: {statistics.mean(prompt_lens):.1f} words')
print(f'avg recall_E:   {statistics.mean(e_recalls):.3f}')
print(f'avg recall_NE:  {statistics.mean(ne_recalls):.3f}')

print('\\nStatus mix:')
for k, v in status_c.most_common():
    print(f'  {k:<10} {v:4d} ({100*v/total:5.1f}%)  {_bar(v, total)}')

print('\\nDomain mix:')
for k, v in domain_c.most_common():
    print(f'  {k:<32} {v:4d} ({100*v/total:5.1f}%)  {_bar(v, total)}')

print('\\nEmbedding-style mix:')
for k, v in style_c.most_common():
    print(f'  {k:<16} {v:4d} ({100*v/total:5.1f}%)  {_bar(v, total)}')

print('\\nSubject mix:')
for k, v in subj_c.most_common():
    print(f'  {k:<16} {v:4d} ({100*v/total:5.1f}%)  {_bar(v, total)}')
"""))

cells.append(md("### 8.1 随机抽检（仿 `scripts/inspect_samples.py`）"))

cells.append(co(
"""rng_s = random.Random(0)
for r in rng_s.sample(rows, k=min(3, len(rows))):
    s = r['spec']; c = r['consistency']
    print('=' * 90)
    print(f"id: {r['id']}   status: {c['status']}   "
          f"recall_E={c['essential_recall']:.2f}  recall_NE={c['nonessential_recall']:.2f}")
    print(f"domain: {s['domain']}  task: {s['task']}  policy: {s['essential_policy']}")
    print(f"style: {s['embedding_style']}  subject: {s['subject']}  tone: {s['tone']}")
    if s.get('task_brief'):
        print(f"task_brief: {s['task_brief']}")
    print('E :', [(a['attribute'], a['value']) for a in s['essential_info']])
    print('NE:', [(a['attribute'], a['value']) for a in s['nonessential_sensitive_info']])
    print('\\nraw_prompt:')
    print('  ' + r['raw_prompt'].replace('\\n', '\\n  '))
    print('\\ngold_reformulation:')
    print('  ' + r['gold_reformulation'])
    print()
"""))

cells.append(md(
"""## 9. 下游对接：SFT / RL

### 9.1 SFT 冷启动
保留 `status == PASS` 的行，用 `(raw_prompt, gold_reformulation)` 作 SFT 对。
"""))

cells.append(co(
"""pass_pairs = [
    {'prompt': r['raw_prompt'], 'completion': r['gold_reformulation']}
    for r in rows
    if r.get('consistency', {}).get('status') == 'PASS'
]
print(f'SFT-ready pairs: {len(pass_pairs)} / {len(rows)}')
print('\\nFirst pair:')
pprint(pass_pairs[0], width=110, sort_dicts=False)
"""))

cells.append(md(
"""### 9.2 RL reward 伪代码

RL 阶段 `raw_prompt` 是 initial state，reward 拿 `spec` 金标（+ judge 发现的
`extra_nonessential`）来算，不依赖判官字面输出，避免 reward 与生成数据耦合。
"""))

cells.append(co(
"""def reward(raw, rewritten, spec, extra_ne=None):
    ne_values = [a['value'] for a in spec['nonessential_sensitive_info']]
    ne_values += list(extra_ne or [])
    e_values  = [a['value'] for a in spec['essential_info']]
    def bertscore(a, b):  # placeholder
        return 1.0 if a.lower() in b.lower() else 0.0
    privacy = 1.0 - (max(bertscore(v, rewritten) for v in ne_values) if ne_values else 0.0)
    utility = sum(bertscore(v, rewritten) for v in e_values) / max(1, len(e_values))
    nat, fmt = 1.0, 1.0
    return 0.5 * privacy + 0.4 * utility + 0.05 * nat + 0.05 * fmt

r0 = next(r for r in rows if r['consistency']['status'] == 'PASS')
print('reward =', round(reward(
    r0['raw_prompt'], r0['gold_reformulation'], r0['spec'],
    extra_ne=r0['consistency'].get('extra_nonessential', []),
), 3))
"""))

cells.append(md(
"""## 10. 小结

- **Step 0** 提供先验：domain / task / attribute + 取值池；
- **Step 1** `Sampler` 一次采出高维配置，按 task policy 决定 E；
- **Step 2** `build_generator_messages` 把 Spec 转成严格 generator prompt；
- **Step 3** 独立家族 judge LLM 抽 E/NE 并与金标比对，得 `PASS/SOFT/HARD`；
- **Step 4** Reformulator 基于 Spec 产出 `gold_reformulation`；
- **Step 5** `Pipeline.run` 并发 + line-buffered JSONL 落盘；
- **Step 6+** 用 `stats.py` / `filter_pass.py` 做分布检查与 PASS 过滤。

这套设计让 reward 只需查 `spec` 金标即可在线 cheap 计算，既保证良品率，
又保持 domain × attribute 的可控均衡。
"""))

nb = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.10"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)
print(f"wrote {OUT} ({OUT.stat().st_size} bytes, {len(cells)} cells)")

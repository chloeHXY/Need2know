#coding=utf-8
import json
import os
import uuid
import re
import argparse
from dataclasses import dataclass
from datetime import datetime
import aiohttp
import asyncio
from tqdm import tqdm
import pandas as pd
import random
import sys
import time
from asyncio import Semaphore
import logging

# 使推理代码可以导入训练模块
_TRAIN_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..', 'train'))
if _TRAIN_DIR not in sys.path:
    sys.path.insert(0, _TRAIN_DIR)

from fc_class import infer_fc, EXTRA_SYSTEM_PROMPT
from tool_call_formatter import ToolCallFormatter

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_BASE_DIR = "/group/40047/eiraxyhuang/workspace/fc/script/evaluation"

RERANK_SYSTEM_PATTERN = """# 任务说明
判断给定的用户查询(query)是否满足调用指定API的条件。

# 判断标准
1. **功能匹配性**：query的核心需求是否在API功能范围内
2. **信息类型匹配**：query要求的信息类型是否与API提供的信息类型一致
3. **参数覆盖度**：query中的关键信息是否能作为API的有效输入参数

# 判断流程
1. 提取query的核心需求和关键词
2. 分析API的功能范围和服务类型
3. 对比query需求与API能力是否匹配
4. 输出判断结果：匹配输出1，不匹配输出0

# API信息
API name：{}
API description：{}
API parameters：{}

# 输出格式
仅输出数字：1（满足）或 0（不满足）

请基于上述标准以及API信息，判断用户查询是否满足调用指定API的条件"""


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@dataclass
class PipelineConfig:
    model_name: str = "fc_32b_sft_v4_e2"
    format_style: str = "qwen_native"
    export_messages: bool = False
    eagle3_mode: bool = False
    sample_n: int = 0
    sample_by_tool: bool = False
    sample_tool_file: str = ""
    sample_per_tool: int = 1
    sample_fixed_file: str = ""
    save_outputs: bool = True
    concurrent: int = 20
    qps: int = 20
    recall_qps: int = 30
    recall_concurrent: int = 50
    rerank_qps: int = 30
    rerank_concurrent: int = 40
    tools_json_path: str = "/group/40047/cyrusfan/workspace/btask/tool_version/v4.0/tools_v4.0.json"
    few_shots_path: str = "/group/40047/cyrusfan/workspace/fc/base_td/fc_few_shots.jsonl"
    input_file: str = ""
    output_file: str = ""
    ir_url: str = "http://xhub.xsearch.woa.com/xsearch_proxy_qbrag_yuanbao/Search"
    rerank_url: str = "http://stream-server-online-sbs-10143.turbotke.production.polaris:81/openapi/chat/completions"

    def __post_init__(self):
        if self.sample_n > 0 or self.sample_by_tool or self.sample_fixed_file:
            self.export_messages = True
        if self.eagle3_mode:
            self.export_messages = True


# ---------------------------------------------------------------------------
# Utilities (stateless)
# ---------------------------------------------------------------------------

class RateLimiter:
    """令牌桶 QPS 限制器，asyncio.Lock 保证并发安全，精确控制发送速率。"""
    def __init__(self, qps):
        self.qps = qps
        self.tokens = float(qps)
        self.max_tokens = float(qps)
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self):
        if self.qps <= 0:
            return
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_refill
            self.tokens = min(self.max_tokens, self.tokens + elapsed * self.qps)
            self.last_refill = now

            if self.tokens >= 1.0:
                self.tokens -= 1.0
            else:
                wait = (1.0 - self.tokens) / self.qps
                await asyncio.sleep(wait)
                now = time.monotonic()
                elapsed = now - self.last_refill
                self.tokens = min(self.max_tokens, self.tokens + elapsed * self.qps)
                self.last_refill = now
                self.tokens -= 1.0


def load_jsonl(path, debug=True):
    import ast
    datas = []
    with open(path, "r") as file:
        for line in file:
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                try:
                    data = ast.literal_eval(line)
                except Exception as e:
                    raise ValueError(f"Input string is neither valid JSON nor valid Python literal: {e}, {line}")
            datas.append(data)
    if debug:
        print(f"load jsonl successful:{path}, length:{len(datas)}")
    return datas


def write_json_to_file(_path, data):
    with open(_path, "w", encoding="utf-8") as f:
        for x in data:
            x = json.dumps(x, ensure_ascii=False)
            f.write(x + "\n")
    print(f"save json successful:{_path} length:{len(data)}")


def fast_read_csv_generator(path):
    """使用pandas快速读取CSV"""
    try:
        df = pd.read_csv(path, encoding='utf-8', on_bad_lines='skip', low_memory=False)
        print(f"读取完成，共 {len(df)} 行")
        for idx, row in df.iterrows():
            query = str(row.iloc[0]) if pd.notna(row.iloc[0]) else ""
            answer = str(row.iloc[1]) if len(row) > 1 and pd.notna(row.iloc[1]) else ""
            if query.strip():
                yield {"query": query, "answer": answer, "line_num": idx + 2}
    except Exception as e:
        print(f"读取失败: {e}")


def get_data_generator(file_path, mode=1):
    """提取公共的数据生成器创建逻辑"""
    if not isinstance(file_path, str):
        return enumerate(file_path)
    if file_path.endswith('.csv'):
        return enumerate(fast_read_csv_generator(file_path))
    else:
        return enumerate(load_jsonl(file_path))


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class FCPipeline:
    """End-to-end FC inference pipeline: recall -> rerank -> infer."""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.tool_map: dict = {}
        self.all_tools: list = []
        self.few_shots_map: dict = {}
        self.recall_semaphore: Semaphore | None = None
        self.rerank_semaphore: Semaphore | None = None

    def load_data(self):
        """加载 tools JSON 和 few-shots"""
        with open(self.config.tools_json_path, 'r', encoding='utf-8') as f:
            self.all_tools = json.load(f)
        for item in self.all_tools:
            self.tool_map[item["function"]["name"]] = item #tool name -> tool

        with open(self.config.few_shots_path, "r") as f:
            for line in f:
                data = json.loads(line)
                self.few_shots_map[data["name"]] = data["few_shot"] #tool name -> few shot

    async def get_recall_res(self, session, rate_limiter, query):
        """异步获取召回结果"""
        async with self.recall_semaphore:
            return await self._get_recall_res_inner(session, rate_limiter, query)

    async def _get_recall_res_inner(self, session, rate_limiter, query):
        await rate_limiter.acquire()

        ir_headers = {"Content-Type": "application/json", "Expect": ""}
        p_load = {
            "header": {"app_id": "11778", "user_id": "", "paas_skey": "12378ac20b4c6b2deb77cb7ef72f7961", "is_test_cfg": False, "auth_token": "d896a6bf07bfe7372a2e434f16d6c88b"},
            "request_data": {"search_cfg_id": "yb_plugintools_bgemtestb", "query_list": [{"raw_query": query, "query_seg_terms": [], "ann_vectors": [{"field_name": "tool_dec_test", "filter": None, "qu_embedding_config": {"enable_qu_embedding": True, "app_id": "10222", "source": "qwen_embedding_03b", "embedding_dict_field_name": "hunyuan"}}], "aggs": [{"terms": {"name": "test", "field": "group_id", "sort": {"from": 0, "limit": 100, "is_asc": False}, "sub_aggs": [{"top_hits": {"name": "top_hit_agg", "sort": {"from": 0, "limit": 10, "is_asc": False}}}]}}]}], "limit_cnt": 0, "filter_condition_v2": None, "pre_filter_condition": None},
            "request_option": {"ret_match_term": False, "ret_doc_field_len": False, "search_timeout_ms": 3000, "ret_score_info": True, "ret_query_seg_terms": False, "disable_read_cache": False, "disable_write_cache": False}
        }

        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with session.post(self.config.ir_url, headers=ir_headers, json=p_load, timeout=timeout) as response:
                res = await response.json()

                tool_lst = res["query_rsps"][0]["aggregations"][0]["terms"]["buckets"]
                recall_group_tool_lst = []
                for tool in tool_lst:
                    tool_info = tool["sub_aggregations"][0]["top_hits"]["vec_doc"][0]
                    score = tool_info["score"]
                    info = tool_info["forwards"]["group_tool_info"]["string_value"]
                    recall_group_tool_lst.append([info, score])

                recall_group_tool_lst.sort(key=lambda x: x[1], reverse=True) #按score降序排序
                tools_group_lst = []
                for item in recall_group_tool_lst[:3]:
                    item_lst = item[0].split("|||")
                    sat_item = ",".join(item_lst)
                    tools_group_lst.append(sat_item)
                tools_group_str = "[" + ",".join(tools_group_lst) + "]"
                sat_tools_group_lst = json.loads(tools_group_str)

                return sat_tools_group_lst

        except Exception as e:
            logger.error(f"IR error query: {query}, error: {e}")
            return self.all_tools[:]

    async def get_rerank_res(self, session, rate_limiter, query, recall_lst):
        """异步获取重排序结果，返回 (rerank_tool_lst, rerank_failed_count)"""
        rerank_tool_lst = []
        rerank_failed_count = 0
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer 7auGXNATFSKl7dF",
            "wsid": "10143"
        }

        tasks = []
        for item in recall_lst:
            tasks.append(self._rerank_single_tool(session, rate_limiter, headers, query, item))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Rerank error for tool {recall_lst[i]['function']['name']}: {result}")
                rerank_failed_count += 1
            else:
                matched, failed = result
                if failed:
                    rerank_failed_count += 1
                elif matched:
                    rerank_tool_lst.append(recall_lst[i])

        return rerank_tool_lst, rerank_failed_count

    async def _rerank_single_tool(self, session, rate_limiter, headers, query, item, max_retries=3):
        """对单个工具进行重排序，返回 (matched: bool, failed: bool)
        核心仍然是prompt:RERANK_SYSTEM_PATTERN驱动的LLM as judge"""
        name = item["function"]["name"]

        for attempt in range(1, max_retries + 1):
            async with self.rerank_semaphore:
                await rate_limiter.acquire()
                try:
                    description = item["function"]["description"]
                    parameters = item["function"]["parameters"]
                    rerank_system = RERANK_SYSTEM_PATTERN.format(name, description, json.dumps(parameters, ensure_ascii=False))
                    messages = [{"role": "system", "content": rerank_system}, {"role": "user", "content": query}]

                    req_body = {
                        "model": "fc_rerank_sat_4b_single_press_group",
                        "query_id": "test_query_id_" + str(uuid.uuid4()),
                        "messages": messages,
                        "temperature": 0.1,
                        "top_p": 0.8,
                        "top_k": 20,
                        "openai_infer": True,
                        "repetition_penalty": 1,
                        "output_seq_len": 128,
                        "max_input_seq_len": 16384,
                        "stream": False,
                    }

                    timeout = aiohttp.ClientTimeout(total=10)
                    async with session.post(self.config.rerank_url, headers=headers, json=req_body, timeout=timeout) as response:
                        parsed_response = await response.json()
                        content = parsed_response["choices"][0]["message"]["content"]
                        matched = content[-1] == "1" or content[-1] == "-"
                        return matched, False  # (matched, failed=False)

                except Exception as e:
                    if attempt < max_retries:
                        logger.warning(f"Rerank retry {attempt}/{max_retries} for tool {name}: {e}")
                        await asyncio.sleep(1 * attempt)
                    else:
                        logger.error(f"Rerank failed after {max_retries} retries for tool {name}: {e}")
                        return False, True  # (matched=False, failed=True)

    def get_few_shots(self, rerank_res):
        """基于重排后的工具列表构建 few-shot 示例文本。"""
        formatter = ToolCallFormatter(self.config.format_style)
        final_few_shot_lst = []

        for item in rerank_res:
            name = item["function"]["name"]
            if name not in self.few_shots_map:
                logger.warning(f"Tool '{name}' has no few_shot entry, skipping")
                continue
            for fs_entry in self.few_shots_map[name]:
                shot_query = fs_entry[0]
                fs_out_tool = fs_entry[1]
                cur_time = fs_entry[2]
                assistant_prompt = formatter.format(fs_out_tool)
                few_shot_format = f"问题：{shot_query}\n当前时间：{cur_time}\n回答：{assistant_prompt}"
                final_few_shot_lst.append(few_shot_format)

        return "\n\n".join(final_few_shot_lst)

    async def process_single_query(self, session, semaphore, rate_limiters, data_item):
        """处理单个查询"""
        async with semaphore:
            try:
                recall_rl, rerank_rl, infer_rl = rate_limiters
                query = data_item["query"]
                sheet_name = data_item.get("sheet_name")
                category = data_item["工具"].split(",") if sheet_name else None

                # recall -> rerank -> few-shots
                recall_res = await self.get_recall_res(session, recall_rl, query)
                rerank_res, rerank_failed_count = await self.get_rerank_res(session, rerank_rl, query, recall_res)
                few_shots_text = self.get_few_shots(rerank_res)

                recall_names = [t['function']['name'] for t in recall_res]
                rerank_names = [t['function']['name'] for t in rerank_res]

                # rerank 工具 >= 3 个时，取 recall 的结果并按字符排序
                # 由于注入全部recall工具会导致上下文超长，先注释这个逻辑，@huangxinyue0427
                # if len(rerank_res) >= 3:
                #     rerank_res = sorted(recall_res, key=lambda x: x['function']['name'])
                #     rerank_names = [t['function']['name'] for t in rerank_res]
                #     few_shots_text = self.get_few_shots(rerank_res)

                # 保存 rerank 工具的完整信息（name, description, parameters）
                rerank_full = [
                    {
                        "name": t['function']['name'],
                        "description": t['function'].get('description', ''),
                        "parameters": t['function'].get('parameters', {}),
                    }
                    for t in rerank_res
                ]

                rerank_res = [self.tool_map[t['function']['name']] for t in rerank_res]

                # 构建环境信息 #这类环境信息通常作为 system prompt 的一部分注入给模型，让它在调用"查天气""查日历""订酒店"等工具时，有正确的时空上下文。
                country = "中国-北京-北京-朝阳区"
                if self.config.eagle3_mode and "time" in data_item:
                    # eagle3 模式：使用数据中的 time 字段（格式如 "2025-10-16 星期四"）
                    raw_time = data_item["time"]  # "2025-10-16 星期四"
                    parts = raw_time.split(" ", 1)
                    date_part = parts[0]  # "2025-10-16"
                    weekday_part = parts[1] if len(parts) > 1 else ""  # "星期四"
                    # 转换日期格式为中文: 2025-10-16 -> 2025年10月16日
                    ymd = date_part.split("-")
                    formatted_time = f"{ymd[0]}年{int(ymd[1])}月{int(ymd[2])}日"
                    # 转换星期格式: 星期四 -> 周四
                    weekday_map = {"星期一": "周一", "星期二": "周二", "星期三": "周三",
                                   "星期四": "周四", "星期五": "周五", "星期六": "周六", "星期日": "周日"}
                    weekday_cn = weekday_map.get(weekday_part, weekday_part)
                    time_str = f"{formatted_time} {weekday_cn}"
                else:
                    now = datetime.now()
                    formatted_time = now.strftime("%Y年%m月%d日")
                    weekdays = {
                        "Monday": "周一", "Tuesday": "周二", "Wednesday": "周三",
                        "Thursday": "周四", "Friday": "周五", "Saturday": "周六",
                        "Sunday": "周日",
                    }
                    weekday_cn = weekdays[now.strftime("%A")]
                    time_str = f"{formatted_time} {weekday_cn}"
                env_data = f"当前国家:{country}\n当前时间:{time_str}\n当前定位:<用户当前位置>"

                if not rerank_res:
                    refuse_reason = "rerank_failed" if rerank_failed_count > 0 else "rerank_filtered"
                    logger.info(f"Rerank output not tools ({refuse_reason}): {query}")
                    if not self.config.eagle3_mode:
                        result = {"query": query, "tool_call": "rank refuse", "refuse_reason": refuse_reason,
                                  "recall_res": recall_names, "rerank_res": rerank_full, "rerank_failed": rerank_failed_count}
                        if sheet_name is not None:
                            result["sheet_name"] = sheet_name
                            result["category"] = category
                        return result
                    # eagle3 模式：rerank 为空时从 recall_res 随机取 1 个工具，构建 few_shots 和 system prompt
                    fallback_tool = random.choice(recall_res)
                    fallback_tools = [fallback_tool]
                    few_shots_text = self.get_few_shots(fallback_tools)
                    fallback_tools = [self.tool_map[t['function']['name']] for t in fallback_tools]
                    from train_builder import SYSTEM_PROMPT_TEMPLATE, build_system_prompt, get_format_instruction
                    format_instruction = get_format_instruction(self.config.format_style)
                    sat_system_prompt = build_system_prompt(
                        system_prompt_pattern=SYSTEM_PROMPT_TEMPLATE,
                        tools=fallback_tools,
                        env_info=env_data,
                        extra_system_prompt=EXTRA_SYSTEM_PROMPT,
                        few_shots_text=few_shots_text,
                        format_instruction=format_instruction,
                    )
                    fc_content = "<tool_call>\n[]\n</tool_call>"
                    fc_messages = [
                        {"role": "system", "content": sat_system_prompt},
                        {"role": "user", "content": query},
                    ]
                else:
                    # 调用推理
                    fc_res = await infer_fc(
                        session, infer_rl, self.config.model_name, query, rerank_res,
                        few_shots_text, env_data,
                        format_style=self.config.format_style,
                        extra_system_prompt=EXTRA_SYSTEM_PROMPT,
                        export_messages=self.config.export_messages,
                    )

                    # 解析返回值
                    if self.config.export_messages:
                        fc_content, fc_messages = fc_res
                    else:
                        fc_content = fc_res
                        fc_messages = None

                if sheet_name is None:
                    result = {
                        "query": query,
                        "tool_call": fc_content,
                        "time": time_str,
                        "recall_res": recall_names,
                        "rerank_res": rerank_full,
                    }
                else:
                    result = {
                        "sheet_name": sheet_name,
                        "category": category,
                        "query": query,
                        "tool_call": fc_content,
                        "recall_res": recall_names,
                        "rerank_res": rerank_full,
                    }

                if self.config.export_messages and fc_messages is not None:
                    result["messages"] = fc_messages

                return result
            except Exception as e:
                logger.error(f"Process query error: {e}")
                return None

    async def run(self):
        """主入口"""
        cfg = self.config
        print(f"inference model:{cfg.model_name}, qps:{cfg.qps}, max_concurrent:{cfg.concurrent}")
        print(f"recall_qps:{cfg.recall_qps}, recall_concurrent:{cfg.recall_concurrent}")
        print(f"rerank_qps:{cfg.rerank_qps}, rerank_concurrent:{cfg.rerank_concurrent}")
        print(f"format_style:{cfg.format_style}, export_messages:{cfg.export_messages}")

        self.load_data()

        # 读取输入数据
        data_items = []
        for idx, elem in get_data_generator(cfg.input_file):
            if "query" in elem:
                data_items.append(elem)
            else:
                data_items += [{"query": dd} for dd in elem['sub_queries']]

        logger.info(f"Total queries to process: {len(data_items)}")

        # 断点续传：读取已完成的 query，跳过已处理的数据
        if os.path.exists(cfg.output_file) and os.path.getsize(cfg.output_file) > 0:
            done_queries = set()
            with open(cfg.output_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        item = json.loads(line)
                        if cfg.eagle3_mode:
                            done_queries.add(item["conversations"][1]["content"])
                        else:
                            done_queries.add(item["query"])
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
            before = len(data_items)
            data_items = [d for d in data_items if d["query"] not in done_queries]
            logger.info(f"Resume: {len(done_queries)} done, {before} -> {len(data_items)} remaining")

        # 随机采样 / 固定采样
        if cfg.sample_fixed_file:
            # 固定采样：直接使用指定文件中的 query 作为输入
            fixed_data = load_jsonl(cfg.sample_fixed_file)
            fixed_queries = {item["query"] for item in fixed_data}
            data_items = [item for item in data_items if item["query"] in fixed_queries]
            logger.info(f"Fixed sample from {cfg.sample_fixed_file}: {len(data_items)} items")
        elif cfg.sample_by_tool and cfg.sample_tool_file:
            # 按工具分组采样：从 sample_tool_file 读取工具列表，每个工具随机取 sample_per_tool 条
            tool_file_data = load_jsonl(cfg.sample_tool_file)
            tool_to_items: dict[str, list] = {}
            for item in tool_file_data:
                tool_key = item.get("工具", "")
                if tool_key:
                    tool_to_items.setdefault(tool_key, []).append(item)

            sampled_items = []
            for tool_key, items in tool_to_items.items():
                n = min(cfg.sample_per_tool, len(items))
                sampled_items.extend(random.sample(items, n))

            random.shuffle(sampled_items)
            data_items = sampled_items
            logger.info(f"Sampled by tool: {len(tool_to_items)} tools, {len(data_items)} items total")
        elif cfg.sample_n > 0:
            actual_n = min(cfg.sample_n, len(data_items))
            data_items = random.sample(data_items, actual_n)
            logger.info(f"Sampled {actual_n} items from input data")

        # 创建信号量和速率限制器（三阶段独立控制）
        # 顶层并发 = 各阶段并发之和，让 query 在不同阶段充分流水线化
        pipeline_concurrent = cfg.recall_concurrent + cfg.rerank_concurrent + cfg.concurrent
        semaphore = Semaphore(pipeline_concurrent)
        self.recall_semaphore = Semaphore(cfg.recall_concurrent)
        self.rerank_semaphore = Semaphore(cfg.rerank_concurrent)
        recall_rl = RateLimiter(cfg.recall_qps)
        rerank_rl = RateLimiter(cfg.rerank_qps)
        infer_rl = RateLimiter(cfg.qps)
        rate_limiters = (recall_rl, rerank_rl, infer_rl)

        connector = aiohttp.TCPConnector(limit=pipeline_concurrent * 2, limit_per_host=pipeline_concurrent)
        timeout = aiohttp.ClientTimeout(total=30)

        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            with tqdm(total=len(data_items), desc="Processing queries") as pbar:
                tasks = [self.process_single_query(session, semaphore, rate_limiters, item)
                         for item in data_items]

                batch_size = pipeline_concurrent * 2
                results = []

                for i in range(0, len(tasks), batch_size):
                    batch_tasks = tasks[i:i + batch_size]
                    batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

                    batch_valid = []
                    for result in batch_results:
                        if isinstance(result, Exception):
                            logger.error(f"Batch processing error: {result}")
                        elif result is not None:
                            batch_valid.append(result)
                    results.extend(batch_valid)

                    if cfg.save_outputs and not cfg.eagle3_mode and cfg.sample_n <= 0 and not cfg.sample_by_tool and not cfg.sample_fixed_file:
                        with open(cfg.output_file, "a") as fw:
                            for result in batch_valid:
                                fw.write(json.dumps(result, ensure_ascii=False) + "\n")

                    # Eagle3 模式：边跑边追加写入，支持断点续传
                    if cfg.eagle3_mode:
                        with open(cfg.output_file, "a", encoding="utf-8") as fw:
                            for r in batch_valid:
                                if not r or "messages" not in r:
                                    continue
                                assistant_content = r.get("tool_call", "")
                                if not assistant_content:
                                    continue
                                conversations = []
                                for msg in r["messages"]:
                                    conversations.append({"role": msg["role"], "content": msg["content"]})
                                conversations.append({"role": "assistant", "content": assistant_content})
                                eagle3_item = {
                                    "id": str(uuid.uuid4()),
                                    "conversations": conversations,
                                }
                                fw.write(json.dumps(eagle3_item, ensure_ascii=False) + "\n")

                    pbar.update(len(batch_tasks))

        logger.info(f"Processing completed. Total successful results: {len(results)}")

        # 采样模式下导出 query + messages（含推理结果）到 JSONL 文件
        if not cfg.eagle3_mode and (cfg.sample_n > 0 or cfg.sample_by_tool or cfg.sample_fixed_file) and cfg.export_messages:
            messages_file = cfg.output_file.rsplit(".", 1)[0] + "_sampled_messages.jsonl"
            with open(messages_file, "w", encoding="utf-8") as fw:
                for r in results:
                    if r and "messages" in r:
                        messages_with_response = r["messages"] + [{"role": "assistant", "content": r["tool_call"]}]
                        fw.write(json.dumps({"query": r["query"], "messages": messages_with_response}, ensure_ascii=False) + "\n")
            logger.info(f"Sampled messages saved to: {messages_file}")

        if cfg.eagle3_mode:
            total_lines = 0
            if os.path.exists(cfg.output_file):
                with open(cfg.output_file, "r") as f:
                    total_lines = sum(1 for _ in f)
            logger.info(f"Eagle3 data saved to: {cfg.output_file}, total: {total_lines}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process queries with concurrent requests and QPS control")
    parser.add_argument("--concurrent", type=int, default=20, help="Maximum concurrent requests")
    parser.add_argument("--qps", type=int, default=20, help="Infer QPS limit (0 for no limit)")
    parser.add_argument("--recall-qps", type=int, default=30, help="Recall QPS limit")
    parser.add_argument("--recall-concurrent", type=int, default=50, help="Recall max concurrent")
    parser.add_argument("--rerank-qps", type=int, default=30, help="Rerank QPS limit")
    parser.add_argument("--rerank-concurrent", type=int, default=40, help="Rerank max concurrent")
    parser.add_argument("--model", type=str, default="fc_a3b_sft_v4_e3")
    parser.add_argument("--task", type=str, default="航班号查询2")
    parser.add_argument("--input", type=str, default="", help="Input JSONL path (default: derived from --task)")
    parser.add_argument("--output", type=str, default="", help="Output JSONL path (default: derived from --model and --task)")
    parser.add_argument("--format-style", type=str, default="qwen_native",
                        choices=["custom_tagged", "qwen_native", "plain_json"],
                        help="Tool call output format style (default: qwen_native)")
    parser.add_argument("--export-messages", action="store_true", default=False,
                        help="Export full system+user messages alongside tool_call result")
    parser.add_argument("--eagle3", action="store_true", default=False,
                        help="Eagle3 mode: use time from input data, export as Eagle3 training format (id + conversations with system/user/assistant)")
    parser.add_argument("--sample", type=int, default=0,
                        help="Randomly sample N items from input data and save query+messages to a JSONL file")
    parser.add_argument("--sample-by-tool", action="store_true", default=False,
                        help="Sample by tool: for each unique tool in --sample-tool-file, randomly pick --sample-per-tool items")
    parser.add_argument("--sample-tool-file", type=str,
                        default="/group/40047/cyrusfan/workspace/fc/script/evaluation/td/end2end.jsonl",
                        help="JSONL file with '工具' field for tool-based sampling")
    parser.add_argument("--sample-per-tool", type=int, default=1,
                        help="Number of items to sample per tool (default: 1)")
    parser.add_argument("--sample-fixed-file", type=str, default="",
                        help="Fixed sample file: only run queries present in this file (no random sampling)")
    parser.add_argument("--tools-json", type=str,
                        default="/group/40047/cyrusfan/workspace/btask/tool_version/v4.0/tools_v4.0.json")
    parser.add_argument("--few-shots", type=str,
                        default="/group/40047/eiraxyhuang/workspace/fc/base_td/fc_few_shots.jsonl")
    parser.add_argument("--ir-url", type=str,
                        default="http://xhub.xsearch.woa.com/xsearch_proxy_qbrag_yuanbao/Search")
    parser.add_argument("--rerank-url", type=str,
                        default="http://stream-server-online-sbs-10143.turbotke.production.polaris:81/openapi/chat/completions")

    args = parser.parse_args()

    input_file = args.input or f"{_BASE_DIR}/td/{args.task}.jsonl"
    output_file = args.output or f"{_BASE_DIR}/test/1model/{args.model}-{args.task}.jsonl"

    config = PipelineConfig(
        model_name=args.model,
        format_style=args.format_style,
        export_messages=args.export_messages,
        eagle3_mode=args.eagle3,
        sample_n=args.sample,
        sample_by_tool=args.sample_by_tool,
        sample_tool_file=args.sample_tool_file,
        sample_per_tool=args.sample_per_tool,
        sample_fixed_file=args.sample_fixed_file,
        concurrent=args.concurrent,
        qps=args.qps,
        recall_qps=args.recall_qps,
        recall_concurrent=args.recall_concurrent,
        rerank_qps=args.rerank_qps,
        rerank_concurrent=args.rerank_concurrent,
        tools_json_path=args.tools_json,
        few_shots_path=args.few_shots,
        input_file=input_file,
        output_file=output_file,
        ir_url=args.ir_url,
        rerank_url=args.rerank_url,
    )

    print(f"output_file:{config.output_file}")

    output_dir = os.path.dirname(config.output_file)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    pipeline = FCPipeline(config)
    asyncio.run(pipeline.run())

#coding=utf-8
import json
import os
import uuid
import sys
import asyncio
import aiohttp
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 使推理代码可以导入训练模块
_TRAIN_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..', 'train'))
if _TRAIN_DIR not in sys.path:
    sys.path.insert(0, _TRAIN_DIR)

from train_builder import (
    SYSTEM_PROMPT_TEMPLATE,
    build_system_prompt,
    get_format_instruction,
)

# ========== 推理专用节假日参考数据 ==========

EXTRA_SYSTEM_PROMPT = """-七夕节:2024-08-10,2025-08-29,2026-08-19
-中秋节:2024-09-17,2025-10-06,2026-09-25
-重阳节:2024-10-11,2025-10-29,2026-10-18
-下元节:2024-11-15,2025-12-05,2026-11-23
-腊八节:2024-01-18,2025-01-07,2026-01-26
-北方小年:2024-02-02,2025-01-22,2026-02-10
-南方小年:2024-02-03,2025-01-23,2026-02-11
-除夕:2024-02-09,2025-01-28,2026-02-16
-元旦假期:2023-12-30至2024-01-01,2025-01-01
-春节假期:2024-02-10至2024-02-17,2025-01-28至2025-02-04
-清明节假期:2024-04-04至2024-04-06,2025-04-04至2025-04-06
-劳动节假期:2024-05-01至2024-05-05,2025-05-01至2025-05-05
-端午节假期:2024-06-08至2024-06-10,2025-05-31至2025-06-02
-中秋节假期:2024-09-15至2024-09-17,2025-10-06
-国庆节假期:2024-10-01至2024-10-07,2025-10-01至2025-10-08
-春节调休:2024-02-04,2024-02-18,2024-01-26,2025-02-08
-清明调休:2024-04-07
-劳动节调休:2024-04-28,2024-05-11;2025-04-27
-中秋节调休:2024-09-14
-国庆节调休:2024-09-29,2024-10-12;2025-09-28,2025-10-11
-父亲节:2025-06-15,2026-06-21
-建党节:2025-07-01,2026-07-01
-香港回归日:2025-07-01,2026-07-01
-建军节:2025-08-01,2026-08-01
-日本无条件投降日:2025-08-15,2026-08-15
-中国人民抗日战争胜利纪念日:2025-09-03,2026-09-03
-世界反法西斯战争胜利纪念日:2025-09-03,2026-09-03
-教师节:2025-09-10,2026-09-10
-烈士纪念日:2025-09-30,2026-09-30
-国庆节:2025-10-01,2026-10-01
-万圣节前夜:2025-10-31,2026-10-31
-万圣节:2025-11-01,2026-11-01
-感恩节:2025-11-27,2026-11-26
-南京大屠杀死难者国家公祭日:2025-12-13,2026-12-13
-澳门回归纪念日:2025-12-20,2026-12-13
-平安夜:2025-12-24,2026-12-24
-圣诞节:2025-12-25,2026-12-25
-清明节:2025-04-04,2026-04-05
-端午节:2025-05-31,2026-06-19
-初伏:2025-07-20
-中伏:2025-07-30
-末伏:2025-08-09
-出伏:2025-08-19
-夏至:2025-06-21,2026-06-21
-小暑:2025-07-07,2026-07-07
-大暑:2025-07-22,2026-07-23
-立秋:2025-08-07,2026-08-07
-白露:2025-09-07,2026-09-07
-秋分:2025-09-23,2026-09-23
-寒露:2025-10-08,2026-10-08
-霜降:2025-10-23,2026-10-23
-冬至:2025-12-21,2026-12-22
-火把节:2025-07-18,2026-08-06
-泼水节:2025-04-14至2025-04-16
-教资:2025-09-13
-法考客观题:2025-09-13;2025-09-14
-法考主观题:2025-10-12
-教资面试:2025-12-06;2025-12-07
-CPA注册会计师:2025-08-23;2025-08-24
-春节:2026-02-17
-元宵节:2026-03-03
-处暑:2026-08-23
    """


FC_URL = "http://stream-server-online-sbs-10143.turbotke.production.polaris:81/openapi/chat/completions"
FC_HEADERS = {
    "Content-Type": "application/json",
    "Authorization": "Bearer 7auGXNATFSKl7dF",
    "wsid": "10143",
}


async def infer_fc_raw(session, rate_limiter, model_name, messages, max_retries=3, max_input_seq_len=32768):
    """
    直接使用已构建好的 messages 调用模型推理（不构建 system prompt）。

    Args:
        session: aiohttp 会话
        rate_limiter: QPS 限制器
        model_name: 模型名称
        messages: 完整的 messages 列表 (如 [system, user])
        max_retries: 最大重试次数
        max_input_seq_len: 最大输入序列长度

    Returns:
        模型返回的 content 字符串，失败时返回 "FC_ERROR"
    """
    for attempt in range(1, max_retries + 1):
        if rate_limiter is not None:
            await rate_limiter.acquire()
        try:
            req_body = {
                "model": model_name,
                "query_id": "test_query_id_" + str(uuid.uuid4()),
                "messages": messages,
                "temperature": 0.1,
                "top_p": 0.8,
                "top_k": 20,
                "openai_infer": True,
                "repetition_penalty": 1,
                "output_seq_len": 1024,
                "max_input_seq_len": max_input_seq_len,
                "stream": False,
            }
            timeout = aiohttp.ClientTimeout(total=15)
            async with session.post(FC_URL, headers=FC_HEADERS, json=req_body, timeout=timeout) as response:
                parsed_response = await response.json()
                if "choices" not in parsed_response:
                    # 计算输入长度用于诊断
                    input_len = sum(len(m.get("content", "")) for m in messages)
                    logger.error(
                        f"No 'choices' in response for model {model_name} "
                        f"(input_chars={input_len}, http_status={response.status}): "
                        f"{json.dumps(parsed_response, ensure_ascii=False)[:500]}"
                    )
                    raise KeyError("choices")
                content = parsed_response["choices"][0]["message"]["content"]
                return content
        except Exception as e:
            if attempt < max_retries:
                logger.warning(f"FC retry {attempt}/{max_retries} for model {model_name}: {e}")
                await asyncio.sleep(1 * attempt)
            else:
                logger.error(f"FC failed after {max_retries} retries for model {model_name}: {e}")
                return "FC_ERROR"


async def infer_fc(session, rate_limiter, model_name, query, rerank_res,
                   few_shots_text, env_data, format_style="custom_tagged",
                   extra_system_prompt="", export_messages=False, max_retries=3):
    """
    异步函数调用推理。

    Args:
        session: aiohttp 会话
        rate_limiter: QPS 限制器
        model_name: 模型名称
        query: 用户查询
        rerank_res: 重排后的工具定义列表
        few_shots_text: few-shot 示例文本
        env_data: 环境信息字符串
        format_style: 输出格式 (custom_tagged/qwen_native/plain_json)
        extra_system_prompt: 节假日参考数据
        export_messages: 是否返回完整 messages
        max_retries: 最大重试次数
    """

    # 使用训练侧的模板和构建函数，确保 system prompt 一致
    format_instruction = get_format_instruction(format_style)
    sat_system_prompt = build_system_prompt(
        system_prompt_pattern=SYSTEM_PROMPT_TEMPLATE,
        tools=rerank_res,
        env_info=env_data,
        extra_system_prompt=extra_system_prompt,
        few_shots_text=few_shots_text,
        format_instruction=format_instruction,
    )

    messages = [
        {"role": "system", "content": sat_system_prompt},
        {"role": "user", "content": query},
    ]

    content = await infer_fc_raw(session, rate_limiter, model_name, messages, max_retries=max_retries)

    if export_messages:
        return content, messages
    return content

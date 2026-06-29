#!/usr/bin/env python3
"""
属性挖掘脚本 - Stage 1
从medical_o1_sft.json中统计敏感属性关键词的出现频次
使用流式JSON处理避免内存问题
"""

import json
import re
from collections import defaultdict
from typing import Dict, List, Set
import csv
from pathlib import Path

# 属性词典定义（基于todo.md建议和医学场景）
ATTRIBUTE_PATTERNS = {
    'age': [
        r'\b\d+\s*(?:year|yr)s?\s*old\b',
        r'\b\d+\s*-\s*\d+\s*year\b',
        r'\bage\s*\d+\b',
        r'\b(?:year-old|yo|aged)\b'
    ],
    'sex_gender': [
        r'\b(?:man|men)\b',
        r'\b(?:woman|women)\b',
        r'\bmale\b',
        r'\bfemale\b',
        r'\bboy\b',
        r'\bgirl\b',
        r'\bhe\b(?!\s+(?:is|has|was))',  # 避免过度匹配
        r'\bshe\b(?!\s+(?:is|has|was))'
    ],
    'diabetes': [
        r'\btype\s*[12]\s*diabetes\b',
        r'\bdiabetes\s*mellitus\b',
        r'\bdiabetic\b',
        r'\bDM\b',
        r'\binsulin-dependent\b'
    ],
    'family_history': [
        r'\bfamily\s*history\b',
        r'\bmother\b.*\b(?:diagnosed|has|had)\b',
        r'\bfather\b.*\b(?:diagnosed|has|had)\b',
        r'\bsibling\b.*\b(?:diagnosed|has|had)\b',
        r'\bbrother\b.*\b(?:diagnosed|has|had)\b',
        r'\bsister\b.*\b(?:diagnosed|has|had)\b'
    ],
    'pregnancy': [
        r'\bpregnant\b',
        r'\bgestational\b',
        r'\bweeks\s*pregnant\b',
        r'\bprenatal\b'
    ],
    'smoking': [
        r'\bsmoker\b',
        r'\bpack-year\b',
        r'\bsmokes\b',
        r'\btobacco\b'
    ],
    'alcohol': [
        r'\balcohol(?:ic)?\b',
        r'\bdrinks?\s*\d+\s*/\s*day\b',
        r'\bheavy\s*drinker\b'
    ],
    'occupation': [
        r'\bworker\b',
        r'\bnurse\b',
        r'\bfarmer\b',
        r'\bconstruction\b'
    ],
    'race_ethnicity': [
        r'\bAfrican\s*American\b',
        r'\bCaucasian\b',
        r'\bAsian\b',
        r'\bHispanic\b'
    ],
    'mental_health': [
        r'\bdepression\b',
        r'\banxiety\s*disorder\b',
        r'\bbipolar\b',
        r'\bschizophrenia\b'
    ],
    'hiv_sti': [
        r'\bHIV\b',
        r'\bAIDS\b',
        r'\bsyphilis\b',
        r'\bHPV\b'
    ],
    'weight_bmi': [
        r'\bobese\b',
        r'\bBMI\b',
        r'\boverweight\b'
    ]
}


def compile_patterns() -> Dict[str, List[re.Pattern]]:
    """编译所有正则表达式模式"""
    compiled = {}
    for attr, patterns in ATTRIBUTE_PATTERNS.items():
        compiled[attr] = [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
    return compiled


def count_attributes_in_file(jsonl_path: str, max_samples: int = None) -> Dict[str, Dict]:
    """
    流式处理JSON文件，统计属性出现次数
    """
    patterns = compile_patterns()
    
    # 统计结果
    results = {
        'total_samples': 0,
        'attribute_counts': defaultdict(int),
        'attribute_examples': defaultdict(list),
        'samples_with_attributes': 0
    }
    
    try:
        with open(jsonl_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
            if not isinstance(data, list):
                print("Error: Expected JSON array")
                return results
                
            results['total_samples'] = len(data)
            
            for i, sample in enumerate(data):
                if max_samples and i >= max_samples:
                    break
                    
                if 'Question' not in sample:
                    continue
                    
                question_text = sample['Question']
                sample_has_attribute = False
                
                for attr, attr_patterns in patterns.items():
                    for pattern in attr_patterns:
                        if pattern.search(question_text):
                            results['attribute_counts'][attr] += 1
                            sample_has_attribute = True
                            
                            # 保存示例（最多5个）
                            if len(results['attribute_examples'][attr]) < 5:
                                results['attribute_examples'][attr].append({
                                    'question': question_text[:200] + '...' if len(question_text) > 200 else question_text,
                                    'sample_index': i
                                })
                            break  # 每个属性只计一次
                
                if sample_has_attribute:
                    results['samples_with_attributes'] += 1
                    
    except Exception as e:
        print(f"Error processing file: {e}")
        
    return results


def generate_report(results: Dict[str, Dict], output_dir: str):
    """生成CSV报告"""
    report_path = Path(output_dir) / "attr_frequency.csv"
    
    with open(report_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        
        # 写入头部
        writer.writerow(['Attribute', 'Count', 'Percentage', 'Example Questions'])
        
        # 写入数据
        for attr, count in results['attribute_counts'].items():
            percentage = (count / results['total_samples']) * 100 if results['total_samples'] > 0 else 0
            
            # 整理示例
            examples = []
            for example in results['attribute_examples'][attr]:
                examples.append(f"Sample {example['sample_index']}: {example['question']}")
            examples_str = ' | '.join(examples)
            
            writer.writerow([attr, count, f"{percentage:.2f}%", examples_str])
        
        # 写入汇总信息
        writer.writerow([])
        writer.writerow(['Total Samples', results['total_samples']])
        writer.writerow(['Samples with Attributes', results['samples_with_attributes']])
        attr_coverage = (results['samples_with_attributes'] / results['total_samples']) * 100 if results['total_samples'] > 0 else 0
        writer.writerow(['Attribute Coverage', f"{attr_coverage:.2f}%"])


def main():
    input_file = "/group/40047/eiraxyhuang/workspace/fc/DataG/layer1_reverse_synthesis/medical_o1_sft.json"
    output_dir = "/group/40047/eiraxyhuang/workspace/fc/DataG/layer1_reverse_synthesis/reports"
    
    print("Starting attribute mining...")
    print(f"Input file: {input_file}")
    print(f"Output directory: {output_dir}")
    
    # 先在小样本上测试（前1000条）
    print("Testing with first 1000 samples...")
    results = count_attributes_in_file(input_file, max_samples=1000)
    
    print(f"Processed {results['total_samples']} samples")
    print(f"Found {results['samples_with_attributes']} samples with attributes")
    
    # 生成报告
    generate_report(results, output_dir)
    print(f"Report generated: {output_dir}/attr_frequency.csv")
    
    # 打印简要统计
    print("\nAttribute counts:")
    for attr, count in sorted(results['attribute_counts'].items(), key=lambda x: x[1], reverse=True):
        print(f"  {attr}: {count}")


if __name__ == "__main__":
    main()
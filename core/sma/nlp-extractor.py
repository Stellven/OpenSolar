#!/usr/bin/env python3
"""
Phase 2: NLP-based Triple Extraction
使用 jieba 分词和词性标注提取知识三元组
"""
import sys
import json
import jieba.posseg as pseg
from typing import List, Tuple, Optional

# ==================== 词性标注参考 ====================
# n: 名词
# v: 动词
# eng: 英文
# m: 数量词
# nr: 人名
# ns: 地名
# nt: 机构名
# nz: 其他专有名词

def extract_triples(text: str) -> List[Tuple[str, str, str, float]]:
    """
    从文本中提取知识三元组

    返回: List[(subject, predicate, object, confidence)]
    """
    triples = []

    # 分词和词性标注
    words = pseg.lcut(text)

    # 转换为列表方便索引
    tokens = [(w, p) for w, p in words if w.strip()]  # 过滤空格

    # 遍历寻找 "是" 模式: [名词/专名] 是 [名词短语]
    for i in range(len(tokens)):
        word, pos = tokens[i]

        # 检测谓语 "是"
        if word == "是" and pos == "v":
            subject = extract_subject(tokens, i)
            obj = extract_object(tokens, i)

            if subject and obj:
                confidence = calculate_confidence(subject, "是", obj, tokens)
                triples.append((subject, "是", obj, confidence))

        # 检测谓语 "可以" (jieba可能标注为v或c)
        elif word == "可以" and pos in ["v", "c"]:
            subject = extract_subject(tokens, i)
            obj = extract_object(tokens, i)

            if subject and obj:
                confidence = calculate_confidence(subject, "可以", obj, tokens)
                triples.append((subject, "可以", obj, confidence))

        # 检测谓语 "有"
        elif word == "有" and pos == "v":
            subject = extract_subject(tokens, i)
            obj = extract_object(tokens, i)

            if subject and obj:
                confidence = calculate_confidence(subject, "有", obj, tokens)
                triples.append((subject, "有", obj, confidence))

    return triples


def extract_subject(tokens: List[Tuple[str, str]], predicate_idx: int) -> Optional[str]:
    """
    提取主语：向前查找名词/专名
    """
    # 向前查找最近的名词性词语
    for i in range(predicate_idx - 1, -1, -1):
        word, pos = tokens[i]

        # 名词性词语: n(名词), eng(英文), nr(人名), ns(地名), nt(机构), nz(专名)
        if pos in ['n', 'eng', 'nr', 'ns', 'nt', 'nz']:
            # 检查是否需要合并前面的修饰词
            subject_parts = [word]

            # 向前收集连续的名词性词语
            for j in range(i - 1, -1, -1):
                w, p = tokens[j]
                if p in ['n', 'eng', 'nr', 'ns', 'nt', 'nz', 'm', 'a']:  # m=数量, a=形容词
                    subject_parts.insert(0, w)
                else:
                    break

            subject = ''.join(subject_parts)

            # 验证主语
            if is_valid_entity(subject):
                return subject

    return None


def extract_object(tokens: List[Tuple[str, str]], predicate_idx: int) -> Optional[str]:
    """
    提取宾语：向后查找名词短语，限制长度避免过度提取
    """
    # 向后查找名词短语，直到遇到标点或句子结束
    obj_parts = []  # 存储 (word, pos) 元组
    MAX_OBJ_TOKENS = 8  # 限制宾语最大token数，避免贪婪提取

    for i in range(predicate_idx + 1, len(tokens)):
        word, pos = tokens[i]

        # 遇到标点或新句子，停止 (但保留下划线)
        if pos == 'x' and word in ['。', '，', '！', '？', '；']:
            break

        # 达到最大长度限制，停止
        if len(obj_parts) >= MAX_OBJ_TOKENS:
            break

        # 优先收集名词性词语
        if pos in ['n', 'eng', 'nr', 'ns', 'nt', 'nz']:
            obj_parts.append((word, pos))
        # 收集修饰性动词（如"无损"）和形容词
        elif pos in ['v', 'a'] and len(obj_parts) < MAX_OBJ_TOKENS - 2:
            obj_parts.append((word, pos))
        # 收集限定词/代词（如"所有"）
        elif pos == 'b' and len(obj_parts) < MAX_OBJ_TOKENS - 1:
            obj_parts.append((word, pos))
        # 收集数量词
        elif pos == 'm' and len(obj_parts) > 0 and len(obj_parts) < MAX_OBJ_TOKENS - 2:
            obj_parts.append((word, pos))
        # 收集副词（如"都"）
        elif pos == 'd' and len(obj_parts) > 0 and len(obj_parts) < MAX_OBJ_TOKENS - 2:
            obj_parts.append((word, pos))
        # 收集结构助词"的"
        elif word in ['的'] and len(obj_parts) > 0:
            obj_parts.append((word, pos))
        # 收集连词"和" (用于枚举结构如 A 和 B)
        elif pos == 'c' and word in ['和', '与', '及'] and len(obj_parts) > 0:
            obj_parts.append((word, pos))
        # 收集下划线和连字符 (用于标识符如 session_id)
        elif word in ['_', '-'] and len(obj_parts) > 0:
            obj_parts.append((word, 'x'))

    # 宾语完整性验证：如果最后一个词是修饰词，检查后面是否有名词需要收集
    if obj_parts and len(obj_parts) < MAX_OBJ_TOKENS:
        last_word, last_pos = obj_parts[-1]
        # 如果最后一个是形容词或修饰性动词（如"结构化"）
        if last_pos in ['a', 'v']:
            # 查看当前停止位置后的下一个token
            last_checked_idx = predicate_idx + 1 + len(obj_parts)
            if last_checked_idx < len(tokens):
                next_word, next_pos = tokens[last_checked_idx]
                # 如果下一个是名词，收集它以完整短语（如"结构化"+"存储"）
                if next_pos in ['n', 'eng', 'nr', 'ns', 'nt', 'nz']:
                    obj_parts.append((next_word, next_pos))

    if obj_parts:
        # 智能拼接：英文词之间加空格，其他直接拼接
        result = []
        for i, (word, pos) in enumerate(obj_parts):
            if i > 0:
                prev_word, prev_pos = obj_parts[i - 1]
                # 如果当前和前一个都是英文词，插入空格
                if pos == 'eng' and prev_pos == 'eng':
                    result.append(' ')
            result.append(word)

        obj = ''.join(result)
        if is_valid_entity(obj):
            return obj

    return None


def is_valid_entity(entity: str) -> bool:
    """
    验证实体是否有效
    """
    # 长度检查
    if len(entity) < 2 or len(entity) > 30:
        return False

    # 必须包含中文/字母/数字
    if not any(c.isalnum() or '\u4e00' <= c <= '\u9fa5' for c in entity):
        return False

    # 不能是代词
    pronouns = ['它', '这', '那', '其', '他', '她', '这个', '那个', '这些', '那些']
    if entity in pronouns or entity.startswith(tuple(pronouns)):
        return False

    # 不能是过于通用的词
    generic_terms = [
        '函数', '方法', '代码', '程序', '系统', '模块', '文件',
        '变量', '参数', '返回值', '结果', '数据', '信息', '内容'
    ]
    if entity in generic_terms:
        return False

    return True


def calculate_confidence(subject: str, predicate: str, obj: str, tokens: List[Tuple[str, str]]) -> float:
    """
    计算三元组置信度
    """
    confidence = 0.5  # 基础分

    # 主语质量 (+0.1)
    if 2 <= len(subject) <= 10:
        confidence += 0.1

    # 谓语类型 (+0.1)
    strong_predicates = ['是', '包括', '定义为', '等于']
    if predicate in strong_predicates:
        confidence += 0.1

    # 宾语有效性 (+0.1)
    if len(obj) >= 3 and is_valid_entity(obj):
        confidence += 0.1

    # 使用了NLP分析 (+0.1)
    confidence += 0.1

    return min(confidence, 0.9)


def main():
    """
    CLI接口：读取JSON格式的输入文本，输出提取的三元组

    输入格式: {"texts": ["文本1", "文本2"]}
    输出格式: [{"subject": "X", "predicate": "是", "object": "Y", "confidence": 0.8}]
    """
    try:
        # 读取标准输入
        input_data = json.loads(sys.stdin.read())
        texts = input_data.get('texts', [])

        all_triples = []
        seen = set()  # 去重

        for text in texts:
            triples = extract_triples(text)

            for subject, predicate, obj, confidence in triples:
                key = (subject, predicate, obj)
                if key not in seen:
                    seen.add(key)
                    all_triples.append({
                        'subject': subject,
                        'predicate': predicate,
                        'object': obj,
                        'confidence': confidence
                    })

        # 输出JSON
        print(json.dumps(all_triples, ensure_ascii=False))

    except Exception as e:
        print(json.dumps({'error': str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()

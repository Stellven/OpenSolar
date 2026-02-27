#!/usr/bin/env python3
"""
Debug script to see what jieba produces for problematic texts
"""
import jieba.posseg as pseg

# Problematic texts from validation
test_cases = [
    "L2 可以无损记录所有会话轨迹",
    "SMA 是 Solar Memory Architecture",
    "L2 是无损会话记录",
    "L2 有 session_id 和 turn_id 两个索引"
]

for text in test_cases:
    print(f"\n{'='*60}")
    print(f"Text: {text}")
    print(f"{'='*60}")

    words = pseg.lcut(text)
    tokens = [(w, p) for w, p in words if w.strip()]

    print(f"\nTokens ({len(tokens)}):")
    for i, (word, pos) in enumerate(tokens):
        print(f"  [{i}] '{word}' (POS: {pos})")

    # Simulate extract_object logic after "可以" or "是" or "有"
    predicate_words = ["可以", "是", "有"]
    for pred_word in predicate_words:
        for i, (word, pos) in enumerate(tokens):
            if word == pred_word:
                print(f"\n--- Simulating extract_object after '{pred_word}' at index {i} ---")

                obj_parts = []
                MAX_OBJ_TOKENS = 8

                for j in range(i + 1, len(tokens)):
                    word_j, pos_j = tokens[j]

                    # Check if we should stop
                    if pos_j == 'x' and word_j in ['。', '，', '！', '？', '；']:
                        print(f"  [{j}] STOP: punctuation '{word_j}'")
                        break

                    if len(obj_parts) >= MAX_OBJ_TOKENS:
                        print(f"  [{j}] STOP: max tokens reached")
                        break

                    # Check collection rules
                    collected = False
                    reason = ""

                    # 优先收集名词性词语
                    if pos_j in ['n', 'eng', 'nr', 'ns', 'nt', 'nz']:
                        obj_parts.append(word_j)
                        collected = True
                        reason = "noun-like POS"
                    # 收集修饰性动词（如"无损"）和形容词
                    elif pos_j in ['v', 'a'] and len(obj_parts) < MAX_OBJ_TOKENS - 2:
                        obj_parts.append(word_j)
                        collected = True
                        reason = "modifier (v/a)"
                    # 收集限定词/代词（如"所有"）
                    elif pos_j == 'b' and len(obj_parts) < MAX_OBJ_TOKENS - 1:
                        obj_parts.append(word_j)
                        collected = True
                        reason = "determiner (b)"
                    # 收集数量词
                    elif pos_j == 'm' and len(obj_parts) > 0 and len(obj_parts) < MAX_OBJ_TOKENS - 2:
                        obj_parts.append(word_j)
                        collected = True
                        reason = "quantity (m)"
                    # 收集副词（如"都"）
                    elif pos_j == 'd' and len(obj_parts) > 0 and len(obj_parts) < MAX_OBJ_TOKENS - 2:
                        obj_parts.append(word_j)
                        collected = True
                        reason = "adverb (d)"
                    # 收集结构助词"的"
                    elif word_j in ['的'] and len(obj_parts) > 0:
                        obj_parts.append(word_j)
                        collected = True
                        reason = "structural '的'"

                    if collected:
                        print(f"  [{j}] ✓ COLLECT '{word_j}' (POS: {pos_j}) - {reason}")
                    else:
                        print(f"  [{j}] ✗ SKIP '{word_j}' (POS: {pos_j}) - no matching rule")

                result = ''.join(obj_parts)
                print(f"\n  Result: '{result}'")
                print(f"  Collected {len(obj_parts)} tokens: {obj_parts}")
                break

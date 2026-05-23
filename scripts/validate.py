#!/usr/bin/env python3
"""
validate.py — 诉讼文书 Markdown 自动验证
用法: python3 validate.py <input.md>

验证项：
1. 证据编号连续性（无跳号、无重复）
2. 金额汇总一致性
3. 法条引用格式
4. Markdown语法残留
5. 主体代称一致性
"""
import re
import sys

def validate_evidence_numbers(text):
    """检查证据编号连续性"""
    # 提取所有"证据N"的编号
    nums = [int(m) for m in re.findall(r'证据(\d+)(?!\d)', text)]
    if not nums:
        print("⚠️  未找到证据编号")
        return
    
    unique = sorted(set(nums))
    expected = list(range(min(unique), max(unique) + 1))
    
    missing = set(expected) - set(unique)
    duplicates = [n for n in unique if nums.count(n) > 1]
    
    if missing:
        print(f"❌ 证据编号跳号: {sorted(missing)}")
    else:
        print(f"✅ 证据编号连续: {min(unique)}-{max(unique)} ({len(unique)}项)")
    
    if duplicates:
        print(f"❌ 证据编号重复出现: {duplicates}")
    
    return len(missing) == 0 and len(duplicates) == 0


def validate_amounts(text):
    """检查金额汇总一致性"""
    issues = []
    
    # 提取所有金额（含小数）
    amounts = re.findall(r'([\d,]+\.?\d*)\s*元', text)
    
    # 查找"共计""合计""总计"等汇总行
    total_lines = re.findall(r'(?:共计|合计|总计|标的额)[：:\s]*([\d,]+\.?\d*)\s*元', text)
    
    if total_lines:
        print(f"📊 发现汇总金额: {total_lines}")
        # 检查多个汇总行是否一致
        if len(set(total_lines)) > 1:
            print(f"❌ 汇总金额不一致: {total_lines}")
            issues.append("amount_mismatch")
        else:
            print(f"✅ 汇总金额一致: {total_lines[0]}元")
    
    return len(issues) == 0


def validate_law_references(text):
    """检查法条引用格式"""
    issues = []
    
    # 检查常见的术语错误
    errors = {
        "举证责任倒置": "应为'举证责任转移'（新反法第39条）",
    }
    
    for wrong, hint in errors.items():
        if wrong in text:
            print(f"❌ 法条术语错误: '{wrong}' → {hint}")
            issues.append(wrong)
    
    # 检查法条引用格式
    refs = re.findall(r'第([一二三四五六七八九十百]+)条', text)
    if refs:
        print(f"📜 法条引用: {len(refs)}处（第{refs[0]}条~第{refs[-1]}条）")
    
    return len(issues) == 0


def validate_markdown_residuals(text):
    """检查Markdown语法残留"""
    issues = []
    
    # 检查 ** 残留（应在导出时清除，但md源文件中正常）
    bold_markers = len(re.findall(r'\*\*', text))
    
    # 检查 []() 链接残留
    link_residuals = re.findall(r'\[([^\]]+)\]\([^)]+\)', text)
    
    print(f"📝 Markdown标记: ** ({bold_markers}处), 链接 ({len(link_residuals)}处)")
    print(f"   （md源文件中正常，PDF导出时应清除）")
    
    return True


def validate_subject_consistency(text):
    """检查主体代称一致性"""
    issues = []
    
    # 检查"原告二"后跟"账号"的潜在混淆
    patterns = [
        (r'原告二[^的]*账号', "可能混淆：账号是否属于原告二？"),
        (r'原告一[^的]*账号', None),  # 正常
    ]
    
    for pattern, warning in patterns:
        matches = re.findall(pattern, text)
        if matches and warning:
            print(f"⚠️  {warning}: {matches}")
            issues.append(pattern)
    
    return len(issues) == 0


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 validate.py <input.md>", file=sys.stderr)
        sys.exit(1)
    
    filepath = sys.argv[1]
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()
    
    lines = text.count('\n') + 1
    chars = len(text)
    print(f"📄 {filepath} ({lines}行, {chars}字符)")
    print("=" * 50)
    
    all_pass = True
    all_pass &= validate_evidence_numbers(text)
    all_pass &= validate_amounts(text)
    all_pass &= validate_law_references(text)
    validate_markdown_residuals(text)
    validate_subject_consistency(text)
    
    print("=" * 50)
    if all_pass:
        print("✅ 验证通过")
    else:
        print("❌ 存在问题，请修复后重新验证")


if __name__ == "__main__":
    main()

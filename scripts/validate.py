#!/usr/bin/env python3
"""
validate.py — 诉讼文书 Markdown 自动验证
用法: python3 validate.py <input.md>

验证项：
1. 证据编号连续性（无跳号、无重复、无子编号）
2. 金额汇总一致性
3. 法条引用格式及术语精确性
4. Markdown语法残留
5. 主体代称一致性
6. 证据交叉引用（正文引用 vs 清单编号）
7. 证据打包目录验证（--pack模式）

2026-05-25 v5改进：
- 新增--cross-check模式：多文件交叉核对金额一致性
- 新增证据清单描述与正文计算参数比对
- 金额精度检查：诉请金额精确到元
"""
import re
import sys

def validate_evidence_numbers(text):
    """检查证据编号连续性"""
    # 提取所有"证据N"的编号
    nums = [int(m) for m in re.findall(r'证据(\d+)(?!\d)', text)]
    if not nums:
        print("⚠️  未找到证据编号")
        return True  # 无证据编号不算错误
    
    unique = sorted(set(nums))
    expected = list(range(min(unique), max(unique) + 1))
    
    missing = set(expected) - set(unique)
    duplicates = [n for n in unique if nums.count(n) > 1]
    
    # 检查子编号（禁止）
    sub_numbers = re.findall(r'证据\d+[\(（-]\d+[\)）]?', text)
    
    if missing:
        print(f"❌ 证据编号跳号: {sorted(missing)}")
    else:
        print(f"✅ 证据编号连续: {min(unique)}-{max(unique)} ({len(unique)}项)")
    
    if duplicates:
        print(f"❌ 证据编号重复出现: {duplicates}")
    
    if sub_numbers:
        print(f"❌ 发现子编号（已禁止）: {sub_numbers[:5]}{'...' if len(sub_numbers) > 5 else ''}")
    
    return len(missing) == 0 and len(duplicates) == 0 and len(sub_numbers) == 0


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


def validate_evidence_cross_references(text):
    """检查证据交叉引用：正文引用vs证据清单是否对应"""
    issues = []
    
    # 检查正文中的证据引用
    body_refs = set(int(m) for m in re.findall(r'证据(\d+)(?!\d)', text))
    
    # 检查证据清单中的编号（假设清单格式为"证据N."或编号开头）
    list_nums = set(int(m) for m in re.findall(r'(?:^|\n)\s*(?:证据)?(\d+)\s*[.、．]', text, re.MULTILINE))
    
    if list_nums and body_refs:
        in_body_not_list = body_refs - list_nums
        in_list_not_body = list_nums - body_refs
        
        if in_body_not_list:
            print(f"⚠️  正文引用但清单无对应: {sorted(in_body_not_list)}")
        if in_list_not_body:
            print(f"⚠️  清单有但正文未引用: {sorted(in_list_not_body)}")
        if not in_body_not_list and not in_list_not_body:
            print(f"✅ 证据交叉引用完整")
    
    return len(issues) == 0


def main():
    if len(sys.argv) < 2:
        print("Usage:", file=sys.stderr)
        print("  python3 validate.py <input.md>          # 验证诉状md", file=sys.stderr)
        print("  python3 validate.py --pack <目录> <最大编号>  # 验证证据打包目录", file=sys.stderr)
        print("  python3 validate.py --cross-check <file1.md> <file2.md> ...  # 多文件交叉核对", file=sys.stderr)
        sys.exit(1)
    
    if sys.argv[1] == '--cross-check':
        if len(sys.argv) < 3:
            print("Usage: python3 validate.py --cross-check <file1.md> <file2.md> ...", file=sys.stderr)
            sys.exit(1)
        cross_check_files(sys.argv[2:])
        return
    
    if sys.argv[1] == '--pack':
        # 证据打包目录验证模式
        if len(sys.argv) < 4:
            print("Usage: python3 validate.py --pack <目录> <最大编号>", file=sys.stderr)
            sys.exit(1)
        pack_dir = sys.argv[2]
        max_num = int(sys.argv[3])
        validate_pack_directory(pack_dir, max_num)
        return
    
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
    validate_evidence_cross_references(text)
    
    print("=" * 50)
    if all_pass:
        print("✅ 验证通过")
    else:
        print("❌ 存在问题，请修复后重新验证")


def validate_pack_directory(pack_dir, max_num):
    """验证证据打包目录：编号覆盖、文件数量、同名冲突"""
    import os
    
    if not os.path.exists(pack_dir):
        print(f"❌ 目录不存在: {pack_dir}")
        return
    
    files = [f for f in os.listdir(pack_dir) if os.path.isfile(os.path.join(pack_dir, f))]
    
    # 提取编号
    nums = {}
    for f in files:
        m = re.match(r'证据(\d+)_', f)
        if m:
            n = int(m.group(1))
            nums.setdefault(n, []).append(f)
    
    expected = set(range(1, max_num + 1))
    covered = set(nums.keys())
    missing = sorted(expected - covered)
    extra = sorted(covered - expected)
    
    print(f"📁 {pack_dir}")
    print(f"   文件总数: {len(files)}")
    print(f"   编号覆盖: {len(covered)}/{max_num}")
    
    if missing:
        print(f"   ❌ 缺失编号({len(missing)}项): {missing}")
    else:
        print(f"   ✅ 编号1-{max_num}全覆盖")
    
    if extra:
        print(f"   ⚠️  超出范围编号: {extra}")
    
    # 同编号多文件检查
    multi = {k: v for k, v in nums.items() if len(v) > 1}
    if multi:
        print(f"   📎 多文件编号({len(multi)}项):")
        for n, fnames in sorted(multi.items()):
            print(f"      证据{n:03d}: {len(fnames)}个文件")
    
    # 占位文件检查
    placeholders = [f for f in files if '_无实体文件.txt' in f]
    if placeholders:
        print(f"   📭 占位文件: {len(placeholders)}个")
        for p in placeholders:
            print(f"      {p}")
    
    # 同名冲突检查
    basenames = [re.sub(r'_\d+(?=\.)', '', os.path.splitext(f)[0]) for f in files]
    from collections import Counter
    dup_basenames = {k: v for k, v in Counter(basenames).items() if v > 1}
    if dup_basenames:
        print(f"   ⚠️  同名冲突风险: {dup_basenames}")


if __name__ == "__main__":
    main()


def cross_check_files(file_paths):
    """多文件交叉核对：检查同一金额在不同文件中是否一致"""
    import os
    
    if len(file_paths) < 2:
        print("❌ 交叉核对至少需要2个文件")
        return
    
    # 读取所有文件
    files_data = {}
    for fp in file_paths:
        if not os.path.exists(fp):
            print(f"⚠️  文件不存在: {fp}")
            continue
        with open(fp, 'r', encoding='utf-8') as f:
            files_data[os.path.basename(fp)] = f.read()
    
    if len(files_data) < 2:
        print("❌ 有效文件不足2个，无法交叉核对")
        return
    
    print(f"📋 交叉核对: {list(files_data.keys())}")
    print("=" * 50)
    
    # 提取各文件金额
    file_amounts = {}
    for name, text in files_data.items():
        amounts = re.findall(r'([\d,]+\.?\d*)\s*元', text)
        # 标准化金额（去逗号）
        normalized = {}
        for a in amounts:
            key = a.replace(',', '')
            normalized[key] = a
        file_amounts[name] = normalized
    
    # 比对关键金额
    key_amounts = ['30000000', '161318.8', '161318', '20159.84', '20159', '12129.84', '12129',
                   '1800', '247', '1748', '1747.88', '1260', '2975', '9986', '1']
    
    issues = []
    for amt in key_amounts:
        found_in = {}
        for name, amounts in file_amounts.items():
            if amt in amounts:
                found_in[name] = amounts[amt]
        
        if len(found_in) >= 2:
            values = set(found_in.values())
            if len(values) > 1:
                print(f"❌ 金额不一致 [{amt}元]: {found_in}")
                issues.append(amt)
    
    # 比对证据清单描述
    for name, text in files_data.items():
        desc_matches = re.findall(r'证据\d+[^\n]*?(\d+天[＝=]([\d,]+\.?\d*)元)', text)
        if desc_matches:
            for desc, val in desc_matches:
                print(f"📊 {name}: {desc}")
    
    # 检查金额精度
    for name, text in files_data.items():
        decimal_amounts = re.findall(r'([\d,]+\.\d{1,2})\s*元', text)
        if decimal_amounts:
            for a in decimal_amounts[:5]:
                val = float(a.replace(',', ''))
                if val != int(val) and val > 100:
                    # 大额诉请金额有角分
                    print(f"⚠️  {name}: 大额诉请金额含角分 {a}元，建议精确到元")
    
    print("=" * 50)
    if issues:
        print(f"❌ 发现{len(issues)}处金额不一致")
    else:
        print("✅ 交叉核对通过")

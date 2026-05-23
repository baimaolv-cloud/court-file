#!/usr/bin/env python3
"""
evidence_pack.py — 证据文件按编号重命名打包

用法:
  python3 evidence_pack.py --index <目录列表> --mapping <映射JSON> --output <输出目录> [--zip <ZIP路径>]
  python3 evidence_pack.py --mapping <映射JSON> --output <输出目录> --dry-run   # 只打印计划不执行

功能:
  1. 扫描指定目录建立文件索引
  2. 按映射表复制重命名文件（证据NNN_简称.ext）
  3. 同编号多文件自动加序号避免覆盖
  4. 打包为ZIP（用Python zipfile确保UTF-8编码正确）
  5. 生成对照清单和缺失项报告
  6. dry-run模式：只打印操作计划，不实际执行

映射JSON格式:
  {
    "1": [["/path/to/file.pdf", "原告一身份证明"]],
    "2": [["/path/to/执照.pdf", "营业执照"]],
    "3": null,  // 暂无实体文件
    ...
  }

教训来源: 马晓明诉腾讯案证据打包（2026-05-23）
- 自动匹配不可靠，必须人工精确映射
- 文件散布多目录，先全盘扫描
- zsh中文路径glob不可靠，用find替代
- 一个编号可对应多个文件（必须加序号区分，否则同名覆盖丢失文件）
- 缺失项分三类：电子数据/公开可调取/重复
- 命令行zip中文文件名编码损坏，必须用Python zipfile
- 批量操作先dry-run确认计划再执行，避免返工
"""

import os
import sys
import json
import shutil
import zipfile
import argparse


def scan_directories(dirs, output_index=None):
    """扫描目录建立文件索引"""
    index = []
    for d in dirs:
        if not os.path.exists(d):
            print(f"⚠️  目录不存在: {d}")
            continue
        for root, _, files in os.walk(d):
            for fn in files:
                fp = os.path.join(root, fn)
                size = os.path.getsize(fp)
                index.append({
                    "path": fp,
                    "name": fn,
                    "size": size,
                    "ext": os.path.splitext(fn)[1],
                })
    
    if output_index:
        with open(output_index, 'w', encoding='utf-8') as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
        print(f"📄 文件索引已保存: {output_index} ({len(index)}个文件)")
    
    return index


def pack_evidence(mapping_path, output_dir, zip_path=None, dry_run=False):
    """按映射表复制重命名打包
    
    关键改进（2026-05-23返工四次教训）：
    1. 同编号多文件自动加序号，避免同名覆盖丢失文件
    2. dry-run模式先打印计划再执行
    3. 操作后立即验证文件数量
    4. ZIP用Python zipfile确保UTF-8中文编码正确
    """
    with open(mapping_path, 'r', encoding='utf-8') as f:
        mapping = json.load(f)
    
    # ========== Phase 1: dry-run 计划 ==========
    plan = []  # [(num, src, new_name)]
    missing_nums = []
    skipped = 0
    
    for num_str, files in sorted(mapping.items(), key=lambda x: int(x[0])):
        num = int(num_str)
        
        if files is None:
            missing_nums.append(num)
            continue
        
        # 同编号多文件加序号
        num_counter = {}
        for src, desc in files:
            if not os.path.exists(src):
                if not dry_run:
                    print(f"  ⚠️  证据{num:03d} 文件不存在: {src}")
                skipped += 1
                continue
            
            ext = os.path.splitext(src)[1]
            cnt = num_counter.get(desc, 0) + 1
            num_counter[desc] = cnt
            
            # 同编号同描述多文件加序号
            if len([s for s, d in files if d == desc and os.path.exists(s)]) > 1:
                new_name = f"证据{num:03d}_{desc}_{cnt}{ext}"
            else:
                new_name = f"证据{num:03d}_{desc}{ext}"
            
            plan.append((num, src, new_name))
    
    # 打印计划
    print(f"📋 操作计划: {len(plan)}个文件 → {output_dir}")
    if skipped:
        print(f"   ⚠️  {skipped}个源文件不存在")
    if missing_nums:
        print(f"   📭 {len(missing_nums)}个编号无实体文件: {missing_nums}")
    
    # 检查同名冲突
    name_counts = {}
    for _, _, name in plan:
        name_counts[name] = name_counts.get(name, 0) + 1
    conflicts = {k: v for k, v in name_counts.items() if v > 1}
    if conflicts:
        print(f"   ⚠️  同名冲突（将被覆盖）: {conflicts}")
    
    if dry_run:
        print(f"\n🔍 Dry-run模式，不执行操作。上述为计划预览。")
        # 打印前20项
        for num, src, name in plan[:20]:
            print(f"   证据{num:03d}: {os.path.basename(src)} → {name}")
        if len(plan) > 20:
            print(f"   ... 还有{len(plan)-20}项")
        return {"plan_size": len(plan), "skipped": skipped, "missing": missing_nums}
    
    # ========== Phase 2: 执行 ==========
    # 清空输出目录
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    
    copied = 0
    for num, src, new_name in plan:
        dst = os.path.join(output_dir, new_name)
        shutil.copy2(src, dst)
        copied += 1
    
    # ========== Phase 3: 立即验证 ==========
    actual_files = [f for f in os.listdir(output_dir) if os.path.isfile(os.path.join(output_dir, f))]
    if len(actual_files) != copied:
        print(f"  ⚠️  验证失败: 计划复制{copied}个，实际{len(actual_files)}个")
    else:
        print(f"  ✅ 文件数量验证: {copied}个")
    
    # ========== Phase 4: 打包ZIP ==========
    if zip_path:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for fn in sorted(os.listdir(output_dir)):
                fp = os.path.join(output_dir, fn)
                if os.path.isfile(fp):
                    zf.write(fp, fn)  # 扁平结构，不保留目录前缀
        zip_size = os.path.getsize(zip_path)
        print(f"✅ ZIP已生成: {zip_path} ({zip_size/1024/1024:.1f} MB)")
    
    # ========== Phase 5: 统计 ==========
    nums_with_files = set()
    for fn in actual_files:
        m = re.match(r'证据(\d+)_', fn)
        if m:
            nums_with_files.add(int(m.group(1)))
    
    all_nums = set(int(k) for k in mapping.keys())
    missing_in_mapping = sorted(all_nums - nums_with_files)
    
    print(f"\n📊 打包统计:")
    print(f"   复制文件: {copied}")
    print(f"   跳过(不存在): {skipped}")
    print(f"   覆盖编号: {len(nums_with_files)}/{len(all_nums)}项")
    if missing_in_mapping:
        print(f"   缺失编号({len(missing_in_mapping)}项): {missing_in_mapping}")
    else:
        print(f"   ✅ 编号全覆盖，无缺号")
    
    return {
        "copied": copied,
        "skipped": skipped,
        "covered": len(nums_with_files),
        "total": len(all_nums),
        "missing": missing_in_mapping,
    }


def main():
    parser = argparse.ArgumentParser(description="证据文件按编号重命名打包")
    parser.add_argument("--index", nargs="+", help="扫描目录建立文件索引")
    parser.add_argument("--index-output", default="/tmp/evidence_file_index.json", help="索引输出路径")
    parser.add_argument("--mapping", required=True, help="映射表JSON路径")
    parser.add_argument("--output", default="/tmp/证据打包", help="输出目录")
    parser.add_argument("--zip", help="ZIP输出路径（可选）")
    parser.add_argument("--dry-run", action="store_true", help="只打印操作计划，不实际执行")
    
    args = parser.parse_args()
    
    if args.index:
        scan_directories(args.index, args.index_output)
    
    pack_evidence(args.mapping, args.output, args.zip, dry_run=args.dry_run)


if __name__ == "__main__":
    main()

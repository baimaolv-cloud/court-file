#!/usr/bin/env python3
"""
evidence_pack.py — 证据文件按编号重命名打包

用法:
  python3 evidence_pack.py --index <目录列表> --mapping <映射JSON> --output <输出目录> [--zip <ZIP路径>]

功能:
  1. 扫描指定目录建立文件索引
  2. 按映射表复制重命名文件（证据NNN_简称.ext）
  3. 打包为ZIP（可选）
  4. 生成对照清单和缺失项报告

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
- 一个编号可对应多个文件
- 缺失项分三类：电子数据/公开可调取/重复
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


def pack_evidence(mapping_path, output_dir, zip_path=None):
    """按映射表复制重命名打包"""
    with open(mapping_path, 'r', encoding='utf-8') as f:
        mapping = json.load(f)
    
    # 清空输出目录
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    
    copied = 0
    skipped = 0
    missing_nums = []
    
    for num_str, files in sorted(mapping.items(), key=lambda x: int(x[0])):
        num = int(num_str)
        
        if files is None:
            missing_nums.append(num)
            continue
        
        for src, desc in files:
            if not os.path.exists(src):
                print(f"  ⚠️  证据{num:03d} 文件不存在: {src}")
                skipped += 1
                continue
            
            ext = os.path.splitext(src)[1]
            new_name = f"证据{num:03d}_{desc}{ext}"
            dst = os.path.join(output_dir, new_name)
            shutil.copy2(src, dst)
            copied += 1
    
    # 打包ZIP
    if zip_path:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for fn in sorted(os.listdir(output_dir)):
                fp = os.path.join(output_dir, fn)
                if os.path.isfile(fp):
                    zf.write(fp, fn)
        zip_size = os.path.getsize(zip_path)
        print(f"✅ ZIP已生成: {zip_path} ({zip_size/1024/1024:.1f} MB)")
    
    # 统计
    file_count = len([f for f in os.listdir(output_dir) if os.path.isfile(os.path.join(output_dir, f))])
    nums_with_files = set()
    for fn in os.listdir(output_dir):
        if fn.startswith("证据") and os.path.isfile(os.path.join(output_dir, fn)):
            nums_with_files.add(int(fn[2:5]))
    
    all_nums = set(int(k) for k in mapping.keys())
    missing_in_mapping = sorted(all_nums - nums_with_files)
    
    print(f"\n📊 打包统计:")
    print(f"   复制文件: {copied}")
    print(f"   跳过(不存在): {skipped}")
    print(f"   覆盖编号: {len(nums_with_files)}项")
    print(f"   缺失编号({len(missing_in_mapping)}项): {missing_in_mapping}")
    
    return {
        "copied": copied,
        "skipped": skipped,
        "covered": len(nums_with_files),
        "missing": missing_in_mapping,
    }


def main():
    parser = argparse.ArgumentParser(description="证据文件按编号重命名打包")
    parser.add_argument("--index", nargs="+", help="扫描目录建立文件索引")
    parser.add_argument("--index-output", default="/tmp/evidence_file_index.json", help="索引输出路径")
    parser.add_argument("--mapping", required=True, help="映射表JSON路径")
    parser.add_argument("--output", default="/tmp/证据打包", help="输出目录")
    parser.add_argument("--zip", help="ZIP输出路径（可选）")
    
    args = parser.parse_args()
    
    if args.index:
        scan_directories(args.index, args.index_output)
    
    pack_evidence(args.mapping, args.output, args.zip)


if __name__ == "__main__":
    main()

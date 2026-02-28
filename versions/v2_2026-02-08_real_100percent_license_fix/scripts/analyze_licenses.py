#!/usr/bin/env python3
"""
分析数据集许可证状况并生成详细报告
"""
import json
import os
from pathlib import Path
from collections import Counter

def analyze_license_status():
    base_dir = Path('stream2graph_dataset/final_100percent_real')

    stats = {
        'total': 0,
        'by_source': {},
        'by_license': Counter(),
        'missing_license': [],  # 完全没有license字段的文件
        'needs_fix': [],  # license为error/none/not_found等的文件
        'valid_license': [],  # 有效许可证的文件
    }

    for source_dir in ['github', 'huggingface', 'gitlab', 'bitbucket', 'other']:
        dir_path = base_dir / source_dir
        if not dir_path.exists():
            continue

        stats['by_source'][source_dir] = {
            'total': 0,
            'by_license': Counter(),
            'missing': 0,
            'needs_fix': 0,
            'valid': 0
        }

        for json_file in dir_path.glob('*.json'):
            stats['total'] += 1
            stats['by_source'][source_dir]['total'] += 1

            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                license_key = data.get('license', 'MISSING')

                if license_key == 'MISSING':
                    stats['missing_license'].append({
                        'file': str(json_file),
                        'source': source_dir,
                        'id': data.get('id', 'unknown'),
                        'source_url': data.get('source_url', '')
                    })
                    stats['by_source'][source_dir]['missing'] += 1
                elif license_key in ['error', 'none', 'not_found', 'rate_limited', 'other', 'error_403', 'error_404', 'gitlab_unknown', 'unknown']:
                    stats['needs_fix'].append({
                        'file': str(json_file),
                        'source': source_dir,
                        'id': data.get('id', 'unknown'),
                        'source_url': data.get('source_url', ''),
                        'current_license': license_key
                    })
                    stats['by_source'][source_dir]['needs_fix'] += 1
                else:
                    stats['valid_license'].append({
                        'file': str(json_file),
                        'source': source_dir,
                        'id': data.get('id', 'unknown'),
                        'license': license_key
                    })
                    stats['by_source'][source_dir]['valid'] += 1

                stats['by_license'][license_key] += 1
                stats['by_source'][source_dir]['by_license'][license_key] += 1

            except Exception as e:
                print(f"Error reading {json_file}: {e}")

    # 生成报告
    print("="*60)
    print("Stream2Graph 数据集许可证分析报告")
    print("="*60)
    print(f"\n总计样本数: {stats['total']}")
    print(f"有效许可证: {len(stats['valid_license'])} ({len(stats['valid_license'])/stats['total']*100:.1f}%)")
    print(f"需要修复: {len(stats['needs_fix'])} ({len(stats['needs_fix'])/stats['total']*100:.1f}%)")
    print(f"完全缺失: {len(stats['missing_license'])} ({len(stats['missing_license'])/stats['total']*100:.1f}%)")

    print("\n" + "-"*60)
    print("按来源统计:")
    print("-"*60)
    for source, source_stats in stats['by_source'].items():
        print(f"\n{source.upper()}:")
        print(f"  总计: {source_stats['total']}")
        print(f"  有效许可证: {source_stats['valid']} ({source_stats['valid']/source_stats['total']*100:.1f}%)")
        print(f"  需要修复: {source_stats['needs_fix']} ({source_stats['needs_fix']/source_stats['total']*100:.1f}%)")
        print(f"  完全缺失: {source_stats['missing']} ({source_stats['missing']/source_stats['total']*100:.1f}%)")

    print("\n" + "-"*60)
    print("许可证分布:")
    print("-"*60)
    for license_key, count in stats['by_license'].most_common():
        percentage = count / stats['total'] * 100
        print(f"  {license_key}: {count} ({percentage:.1f}%)")

    # 保存详细报告
    report = {
        'timestamp': '2026-02-08',
        'summary': {
            'total': stats['total'],
            'valid': len(stats['valid_license']),
            'needs_fix': len(stats['needs_fix']),
            'missing': len(stats['missing_license'])
        },
        'by_source': {k: dict(v) for k, v in stats['by_source'].items()},
        'by_license': dict(stats['by_license']),
        'needs_fix_details': stats['needs_fix'][:100],  # 只保存前100个需要修复的
        'missing_details': stats['missing_license'][:100]  # 只保存前100个缺失的
    }

    with open('license_analysis_report.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("\n" + "="*60)
    print("详细报告已保存到: license_analysis_report.json")
    print("="*60)

    return stats

if __name__ == '__main__':
    analyze_license_status()

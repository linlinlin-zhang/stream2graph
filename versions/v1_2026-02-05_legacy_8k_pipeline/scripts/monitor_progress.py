#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stream2Graph 数据收集进度监控工具

功能:
1. 实时监控数据收集进度
2. 统计各类图表数量
3. 生成进度报告
4. 检查数据质量

使用方法:
    python monitor_progress.py [--watch]

作者: [Your Name]
日期: 2026-02
"""

import os
import json
import time
import argparse
from pathlib import Path
from datetime import datetime
from collections import defaultdict, Counter
from typing import Dict, List


class ProgressMonitor:
    """进度监控器"""

    def __init__(self, dataset_dir: str = "./stream2graph_dataset"):
        self.dataset_dir = Path(dataset_dir)
        self.progress_file = self.dataset_dir / ".collection_progress.json"

        # 目标分布 (8000条)
        self.target_distribution = {
            'flowchart': 1920,
            'sequence': 1280,
            'architecture': 1280,
            'class': 960,
            'mindmap': 960,
            'er': 640,
            'matrix': 480,
            'tree': 480
        }
        self.total_target = 8000

    def load_progress(self) -> Dict:
        """加载进度"""
        if self.progress_file.exists():
            with open(self.progress_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def scan_directory(self, stage: str) -> Dict:
        """扫描目录统计"""
        stage_dir = self.dataset_dir / stage

        if not stage_dir.exists():
            return {'exists': False, 'count': 0}

        # 统计文件
        count = 0
        type_counts = Counter()
        format_counts = Counter()

        for file_path in stage_dir.rglob("*.json"):
            if file_path.name.endswith('_meta.json'):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        meta = json.load(f)
                    count += 1
                    if 'diagram_type' in meta:
                        type_counts[meta['diagram_type']] += 1
                    if 'code_format' in meta:
                        format_counts[meta['code_format']] += 1
                except:
                    pass

        return {
            'exists': True,
            'count': count,
            'type_distribution': dict(type_counts),
            'format_distribution': dict(format_counts)
        }

    def generate_report(self) -> str:
        """生成进度报告"""
        progress = self.load_progress()

        report = []
        report.append("="*70)
        report.append("Stream2Graph 数据收集进度报告")
        report.append("="*70)
        report.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")

        # 整体进度
        report.append("【整体进度】")
        status = progress.get('status', 'unknown')
        status_map = {
            'not_started': '未开始',
            'running': '进行中',
            'completed': '已完成',
            'interrupted': '已中断',
            'error': '出错'
        }
        report.append(f"  状态: {status_map.get(status, status)}")
        report.append(f"  当前阶段: {progress.get('current_stage', 'N/A')}")
        report.append("")

        # 各阶段统计
        report.append("【各阶段统计】")

        stages = [
            ('01_curation', '阶段1: 数据搜集'),
            ('02_filtering', '阶段2: 质量筛选'),
            ('03_reverse_engineering', '阶段3: 逆向工程'),
            ('04_validation', '阶段4: 质量验证'),
            ('05_final', '阶段5: 数据集整理')
        ]

        for stage_dir, stage_name in stages:
            stats = self.scan_directory(stage_dir)
            if stats['exists']:
                report.append(f"  {stage_name}")
                report.append(f"    文件数: {stats['count']}")

                if stats['type_distribution']:
                    report.append(f"    类型分布: {stats['type_distribution']}")
            else:
                report.append(f"  {stage_name}: 暂无数据")

        report.append("")

        # 目标对比
        report.append("【目标完成情况】")

        final_stats = self.scan_directory('05_final')
        if final_stats['exists'] and final_stats['type_distribution']:
            type_dist = final_stats['type_distribution']

            report.append(f"{'图表类型':<20} {'目标':<8} {'当前':<8} {'完成度':<10}")
            report.append("-"*50)

            total_current = 0
            for dtype, target in self.target_distribution.items():
                current = type_dist.get(dtype, 0)
                total_current += current
                pct = current / target * 100 if target > 0 else 0
                status = "✓" if current >= target else "○"
                report.append(f"{dtype:<20} {target:<8} {current:<8} {pct:>6.1f}% {status}")

            report.append("-"*50)
            total_pct = total_current / self.total_target * 100
            report.append(f"{'总计':<20} {self.total_target:<8} {total_current:<8} {total_pct:>6.1f}%")
        else:
            report.append("  最终数据集尚未生成")

        report.append("")
        report.append("="*70)

        return "\n".join(report)

    def watch_mode(self, interval: int = 10):
        """监控模式"""
        print("进入监控模式，按 Ctrl+C 退出...")
        print(f"刷新间隔: {interval}秒\n")

        try:
            while True:
                # 清屏
                os.system('cls' if os.name == 'nt' else 'clear')

                # 打印报告
                print(self.generate_report())

                # 等待
                time.sleep(interval)

        except KeyboardInterrupt:
            print("\n\n监控已停止")

    def export_statistics(self, output_file: str = "progress_stats.json"):
        """导出统计信息"""
        progress = self.load_progress()

        # 收集各阶段统计
        stage_stats = {}
        for stage in ['01_curation', '02_filtering', '03_reverse_engineering',
                      '04_validation', '05_final']:
            stage_stats[stage] = self.scan_directory(stage)

        stats = {
            'timestamp': datetime.now().isoformat(),
            'progress': progress,
            'stage_statistics': stage_stats,
            'target_distribution': self.target_distribution,
            'total_target': self.total_target
        }

        output_path = Path(output_file)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)

        print(f"统计信息已导出: {output_path}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='Stream2Graph 数据收集进度监控工具'
    )

    parser.add_argument('--dataset-dir', '-d', type=str, default='./stream2graph_dataset',
                       help='数据集目录 (默认: ./stream2graph_dataset)')
    parser.add_argument('--watch', '-w', action='store_true',
                       help='监控模式 (自动刷新)')
    parser.add_argument('--interval', '-i', type=int, default=10,
                       help='刷新间隔 (秒, 默认: 10)')
    parser.add_argument('--export', '-e', type=str, default=None,
                       help='导出统计信息到文件')

    args = parser.parse_args()

    # 创建监控器
    monitor = ProgressMonitor(dataset_dir=args.dataset_dir)

    # 导出模式
    if args.export:
        monitor.export_statistics(args.export)
        return

    # 监控模式
    if args.watch:
        monitor.watch_mode(interval=args.interval)
    else:
        # 单次报告
        print(monitor.generate_report())


if __name__ == "__main__":
    main()

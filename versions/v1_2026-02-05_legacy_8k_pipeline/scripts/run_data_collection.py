#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stream2Graph 数据收集执行脚本

使用方法:
    python run_data_collection.py [--resume] [--stage STAGE]

参数:
    --resume: 从上次中断处继续
    --stage: 指定起始阶段 (1-5)
    --target: 目标数量 (默认8000)

作者: [Your Name]
日期: 2026-02
"""

import os
import sys
import json
import argparse
import subprocess
from pathlib import Path
from datetime import datetime


class DataCollectionRunner:
    """数据收集运行器"""

    def __init__(self, output_dir: str = "./stream2graph_dataset"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.progress_file = self.output_dir / ".collection_progress.json"

    def check_environment(self) -> bool:
        """检查环境是否就绪"""
        print("="*70)
        print("环境检查")
        print("="*70)

        checks = []

        # 检查Python版本
        if sys.version_info >= (3, 8):
            print(f"[OK] Python版本: {sys.version}")
            checks.append(True)
        else:
            print(f"[ERROR] Python版本过低: {sys.version}")
            checks.append(False)

        # 检查test_dataset目录
        if Path("./test_dataset").exists():
            test_files = list(Path("./test_dataset").rglob("*.mmd")) + \
                        list(Path("./test_dataset").rglob("*.dot"))
            print(f"[OK] 本地测试数据: {len(test_files)} 个文件")
            checks.append(True)
        else:
            print("[WARN] 未找到test_dataset目录，将主要依赖合成数据")
            checks.append(True)  # 不是致命错误

        # 检查输出目录空间
        try:
            import shutil
            total, used, free = shutil.disk_usage(self.output_dir)
            free_gb = free // (2**30)
            if free_gb > 10:
                print(f"[OK] 磁盘空间: {free_gb}GB 可用")
                checks.append(True)
            else:
                print(f"[WARN] 磁盘空间不足: {free_gb}GB 可用，建议至少10GB")
                checks.append(False)
        except Exception as e:
            print(f"[WARN] 无法检查磁盘空间: {e}")
            checks.append(True)

        # 检查依赖库
        try:
            import tqdm
            print("[OK] 依赖库: tqdm 已安装")
            checks.append(True)
        except ImportError:
            print("[ERROR] 依赖库: tqdm 未安装")
            print("    请运行: pip install tqdm")
            checks.append(False)

        print("="*70)
        return all(checks)

    def load_progress(self) -> dict:
        """加载进度"""
        if self.progress_file.exists():
            with open(self.progress_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            'status': 'not_started',
            'current_stage': 0,
            'collected_count': 0,
            'filtered_count': 0,
            'with_dialogue_count': 0,
            'validated_count': 0,
            'final_count': 0,
            'last_update': None
        }

    def save_progress(self, progress: dict):
        """保存进度"""
        progress['last_update'] = datetime.now().isoformat()
        with open(self.progress_file, 'w', encoding='utf-8') as f:
            json.dump(progress, f, ensure_ascii=False, indent=2)

    def print_collection_plan(self, target_count: int = 8000):
        """打印收集计划"""
        print("\n" + "="*70)
        print("Stream2Graph 数据收集计划")
        print("="*70)

        distribution = {
            "流程图 (Flowchart)": (1920, "Sequential"),
            "时序图 (Sequence)": (1280, "Sequential"),
            "架构图 (Architecture)": (1280, "Structural"),
            "UML类图 (Class)": (960, "Structural"),
            "思维导图 (Mindmap)": (960, "Classification"),
            "ER图": (640, "Relational"),
            "比较矩阵 (Matrix)": (480, "Contrastive"),
            "树状图 (Tree)": (480, "Classification")
        }

        print(f"\n目标总数: {target_count} 条高质量数据")
        print(f"\n图表类型分布:")
        print("-"*70)
        print(f"{'图表类型':<25} {'数量':<8} {'占比':<8} {'言语行为'}")
        print("-"*70)

        for dtype, (count, speech_act) in distribution.items():
            pct = count / target_count * 100
            print(f"{dtype:<25} {count:<8} {pct:<7.1f}% {speech_act}")

        print("-"*70)
        print(f"{'总计':<25} {target_count:<8} {'100%':<8}")
        print("="*70)

        print("\n五阶段流程:")
        print("  1. Curation    : 收集原始代码 (目标10000+)")
        print("  2. Filtering   : 编译验证筛选 (保留8000)")
        print("  3. Reverse Eng : 逆向工程生成对话")
        print("  4. Validation  : 质量验证")
        print("  5. Finalization: 数据集整理 (80/10/10划分)")

        print("\n预计时间:")
        print("  - 数据收集: 4-6周")
        print("  - 质量筛选: 1-2周")
        print("  - 对话生成: 2-3周 (需GPU/API)")
        print("  - 验证整理: 1-2周")
        print("  - 总计: 8-13周")

        print("="*70)

    def run_collection(self, target_count: int = 8000, resume: bool = False, start_stage: int = None):
        """运行数据收集"""

        # 检查环境
        if not self.check_environment():
            print("\n[错误] 环境检查未通过，请修复后重试")
            return False

        # 加载进度
        progress = self.load_progress()

        if resume and progress['status'] != 'not_started':
            print(f"\n[恢复] 从上一次进度继续")
            print(f"  当前阶段: {progress['current_stage']}")
            print(f"  已收集: {progress['collected_count']}")
        else:
            print(f"\n[开始] 新的数据收集任务")
            progress['status'] = 'running'
            progress['current_stage'] = start_stage or 1

        # 打印计划
        self.print_collection_plan(target_count)

        # 确认开始
        if not resume:
            response = input("\n确认开始数据收集? [y/N]: ")
            if response.lower() != 'y':
                print("已取消")
                return False

        # 导入并运行主流程
        try:
            print("\n" + "="*70)
            print("启动数据收集流程...")
            print("="*70)

            # 动态导入builder
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "data_collection_pipeline_v2",
                "./data_collection_pipeline_v2.py"
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # 创建builder并运行
            builder = module.Stream2GraphDatasetBuilder(output_dir=str(self.output_dir))
            stats = builder.run_full_pipeline(target_count=target_count + 2000)  # 多收集一些用于筛选

            # 更新进度
            progress['status'] = 'completed'
            progress['final_count'] = stats.get('total_samples', 0)
            self.save_progress(progress)

            print("\n" + "="*70)
            print("数据收集完成!")
            print("="*70)
            print(f"最终数据集: {self.output_dir / '05_final'}")
            print(f"统计报告: {self.output_dir / 'statistics.json'}")

            return True

        except KeyboardInterrupt:
            print("\n\n[中断] 用户取消收集")
            progress['status'] = 'interrupted'
            self.save_progress(progress)
            return False

        except Exception as e:
            print(f"\n[错误] 收集过程出错: {e}")
            progress['status'] = 'error'
            progress['error_message'] = str(e)
            self.save_progress(progress)
            import traceback
            traceback.print_exc()
            return False

    def show_status(self):
        """显示当前状态"""
        progress = self.load_progress()

        print("="*70)
        print("数据收集状态")
        print("="*70)

        print(f"状态: {progress['status']}")
        print(f"当前阶段: {progress['current_stage']}")
        print(f"已收集: {progress['collected_count']}")
        print(f"已筛选: {progress['filtered_count']}")
        print(f"已生成对话: {progress['with_dialogue_count']}")
        print(f"已验证: {progress['validated_count']}")
        print(f"最终数量: {progress['final_count']}")

        if progress['last_update']:
            print(f"最后更新: {progress['last_update']}")

        print("="*70)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='Stream2Graph 数据收集执行脚本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 开始新的数据收集 (默认8000条)
  python run_data_collection.py

  # 指定目标数量
  python run_data_collection.py --target 10000

  # 从上次中断处继续
  python run_data_collection.py --resume

  # 查看当前状态
  python run_data_collection.py --status
        """
    )

    parser.add_argument('--target', '-t', type=int, default=8000,
                       help='目标样本数量 (默认: 8000)')
    parser.add_argument('--output', '-o', type=str, default='./stream2graph_dataset',
                       help='输出目录 (默认: ./stream2graph_dataset)')
    parser.add_argument('--resume', '-r', action='store_true',
                       help='从上次中断处继续')
    parser.add_argument('--stage', '-s', type=int, default=None,
                       help='指定起始阶段 (1-5)')
    parser.add_argument('--status', action='store_true',
                       help='显示当前状态')

    args = parser.parse_args()

    # 创建运行器
    runner = DataCollectionRunner(output_dir=args.output)

    # 显示状态
    if args.status:
        runner.show_status()
        return

    # 运行收集
    success = runner.run_collection(
        target_count=args.target,
        resume=args.resume,
        start_stage=args.stage
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

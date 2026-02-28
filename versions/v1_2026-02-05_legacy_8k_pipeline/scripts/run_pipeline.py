"""
StreamVis 数据集构建流水线
一键执行完整的数据收集、处理和验证流程
"""

import os
import sys
import json
import asyncio
import argparse
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 导入处理模块
from chart_data_collector import DataCollectionPipeline
from chart_dataset_processor import ChartDatasetProcessor
from quality_validator import DataQualityValidator, DiversityAnalyzer, DuplicateDetector


class PipelineRunner:
    """流水线运行器"""

    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.results = {}

    async def run_collection(self, skip: bool = False) -> dict:
        """运行数据收集阶段"""
        if skip:
            print("[跳过] 数据收集阶段")
            return {"status": "skipped"}

        print("\n" + "="*60)
        print("阶段1: 数据收集")
        print("="*60)

        github_token = os.getenv("GITHUB_TOKEN")

        pipeline = DataCollectionPipeline(github_token=github_token)
        await pipeline.run()

        return {"status": "completed"}

    async def run_processing(self, api_key: str = None, api_provider: str = "kimi",
                            batch_size: int = 100, skip: bool = False) -> dict:
        """运行逆向工程处理阶段"""
        if skip:
            print("[跳过] 逆向工程处理阶段")
            return {"status": "skipped"}

        print("\n" + "="*60)
        print("阶段2: 逆向工程处理")
        print("="*60)

        if not api_key:
            api_key = os.getenv("KIMI_API_KEY") or os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("未提供API密钥。请设置环境变量或在命令行中指定。")

        processor = ChartDatasetProcessor(
            api_key=api_key,
            api_provider=api_provider,
            output_dir="./processed_dataset"
        )

        # 收集待处理的文件
        raw_dataset_dir = Path("./dataset_raw")
        chart_files = []

        for ext in ['*.mmd', '*.mermaid', '*.puml', '*.plantuml', '*.dot', '*.drawio']:
            chart_files.extend(raw_dataset_dir.rglob(ext))

        if not chart_files:
            print("警告: 未找到待处理的图表文件")
            return {"status": "error", "message": "No chart files found"}

        print(f"找到 {len(chart_files)} 个图表文件待处理")

        # 分批处理
        total_processed = 0
        total_failed = 0

        for i in range(0, len(chart_files), batch_size):
            batch = chart_files[i:i+batch_size]
            print(f"\n处理批次 {i//batch_size + 1}/{(len(chart_files)-1)//batch_size + 1} "
                  f"({len(batch)} 个文件)")

            results = await processor.process_batch(batch, max_concurrent=5)

            success = sum(1 for r in results if r is not None and not isinstance(r, Exception))
            failed = len(results) - success

            total_processed += success
            total_failed += failed

            print(f"  成功: {success}, 失败: {failed}")

            # 定期保存统计
            if (i // batch_size + 1) % 5 == 0:
                processor.export_stats(f"processing_stats_batch_{i//batch_size + 1}.json")

        # 最终统计
        processor.export_stats("processing_stats_final.json")

        return {
            "status": "completed",
            "total_files": len(chart_files),
            "processed": total_processed,
            "failed": total_failed,
            "by_category": processor.get_stats()
        }

    def run_validation(self, skip: bool = False) -> dict:
        """运行质量验证阶段"""
        if skip:
            print("[跳过] 质量验证阶段")
            return {"status": "skipped"}

        print("\n" + "="*60)
        print("阶段3: 质量验证")
        print("="*60)

        dataset_dir = "./processed_dataset"

        # 1. 质量验证
        print("\n[3.1] 数据质量验证...")
        validator = DataQualityValidator(dataset_dir)
        report = validator.validate_all()
        validator.save_report("validation_report.json")
        validator.export_invalid_records("invalid_records.txt")

        # 2. 多样性分析
        print("\n[3.2] 多样性分析...")
        analyzer = DiversityAnalyzer(dataset_dir)
        analysis = analyzer.analyze()
        analyzer.save_analysis("diversity_analysis.json")

        # 3. 重复检测
        print("\n[3.3] 重复检测...")
        detector = DuplicateDetector(dataset_dir)
        duplicates = detector.detect_duplicates()
        detector.export_duplicates(duplicates)

        return {
            "status": "completed",
            "validation": report,
            "duplicates_found": len(duplicates)
        }

    def print_summary(self):
        """打印执行摘要"""
        print("\n" + "="*60)
        print("执行摘要")
        print("="*60)

        for stage, result in self.results.items():
            print(f"\n{stage}:")
            if result.get("status") == "completed":
                print(f"  ✓ 完成")
                for key, value in result.items():
                    if key != "status":
                        print(f"    {key}: {value}")
            elif result.get("status") == "skipped":
                print(f"  ○ 跳过")
            else:
                print(f"  ✗ 失败: {result.get('message', 'Unknown error')}")

        if self.start_time and self.end_time:
            duration = self.end_time - self.start_time
            print(f"\n总用时: {duration}")

    async def run(self, args):
        """运行完整流水线"""
        self.start_time = datetime.now()

        try:
            # 阶段1: 数据收集
            if not args.skip_collection:
                self.results["collection"] = await self.run_collection()
            else:
                self.results["collection"] = await self.run_collection(skip=True)

            # 阶段2: 逆向工程处理
            if not args.skip_processing:
                self.results["processing"] = await self.run_processing(
                    api_key=args.api_key,
                    api_provider=args.api_provider,
                    batch_size=args.batch_size
                )
            else:
                self.results["processing"] = await self.run_processing(skip=True)

            # 阶段3: 质量验证
            if not args.skip_validation:
                self.results["validation"] = self.run_validation()
            else:
                self.results["validation"] = self.run_validation(skip=True)

        except Exception as e:
            print(f"\n[错误] 流水线执行失败: {str(e)}")
            import traceback
            traceback.print_exc()

        self.end_time = datetime.now()
        self.print_summary()

        # 保存执行记录
        self._save_execution_log()

    def _save_execution_log(self):
        """保存执行日志"""
        log = {
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": (self.end_time - self.start_time).total_seconds() if self.start_time and self.end_time else None,
            "results": self.results
        }

        log_file = f"pipeline_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(log, f, ensure_ascii=False, indent=2)

        print(f"\n执行日志已保存: {log_file}")


def main():
    parser = argparse.ArgumentParser(
        description="StreamVis 数据集构建流水线",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 运行完整流水线
  python run_pipeline.py --api-key YOUR_KEY

  # 仅运行质量验证
  python run_pipeline.py --skip-collection --skip-processing

  # 使用OpenAI API
  python run_pipeline.py --api-key YOUR_KEY --api-provider openai

  # 小批量测试
  python run_pipeline.py --api-key YOUR_KEY --batch-size 10
        """
    )

    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="LLM API密钥 (默认从环境变量 KIMI_API_KEY 或 OPENAI_API_KEY 读取)"
    )

    parser.add_argument(
        "--api-provider",
        type=str,
        default="kimi",
        choices=["kimi", "openai", "claude"],
        help="API提供商 (默认: kimi)"
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="批处理大小 (默认: 100)"
    )

    parser.add_argument(
        "--skip-collection",
        action="store_true",
        help="跳过数据收集阶段"
    )

    parser.add_argument(
        "--skip-processing",
        action="store_true",
        help="跳过逆向工程处理阶段"
    )

    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="跳过质量验证阶段"
    )

    parser.add_argument(
        "--stage",
        type=str,
        choices=["collection", "processing", "validation", "all"],
        default="all",
        help="运行特定阶段 (默认: all)"
    )

    args = parser.parse_args()

    # 根据--stage参数设置skip标志
    if args.stage != "all":
        args.skip_collection = (args.stage != "collection")
        args.skip_processing = (args.stage != "processing")
        args.skip_validation = (args.stage != "validation")

        if args.stage == "collection":
            args.skip_processing = True
            args.skip_validation = True
        elif args.stage == "processing":
            args.skip_collection = True
            args.skip_validation = True
        elif args.stage == "validation":
            args.skip_collection = True
            args.skip_processing = True

    runner = PipelineRunner()
    asyncio.run(runner.run(args))


if __name__ == "__main__":
    main()

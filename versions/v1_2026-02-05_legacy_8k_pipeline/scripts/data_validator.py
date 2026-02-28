#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stream2Graph 数据质量验证工具

功能:
1. 验证代码可编译性
2. 检查数据完整性
3. 检测重复数据
4. 评估对话质量
5. 生成质量报告

使用方法:
    python data_validator.py --stage STAGE [--fix]

作者: [Your Name]
日期: 2026-02
"""

import os
import json
import subprocess
import tempfile
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from collections import defaultdict, Counter
from dataclasses import dataclass
import hashlib


@dataclass
class ValidationResult:
    """验证结果"""
    sample_id: str
    passed: bool
    errors: List[str]
    warnings: List[str]
    metrics: Dict


class DataValidator:
    """数据验证器"""

    def __init__(self, dataset_dir: str = "./stream2graph_dataset"):
        self.dataset_dir = Path(dataset_dir)

        # 编译器检查
        self.compilers = {
            'mermaid': self._check_mermaid_compiler(),
            'dot': self._check_dot_compiler(),
            'plantuml': self._check_plantuml_compiler()
        }

    def _check_mermaid_compiler(self) -> bool:
        """检查Mermaid编译器"""
        try:
            result = subprocess.run(
                ['mmdc', '--version'],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False

    def _check_dot_compiler(self) -> bool:
        """检查Graphviz编译器"""
        try:
            result = subprocess.run(
                ['dot', '-V'],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False

    def _check_plantuml_compiler(self) -> bool:
        """检查PlantUML编译器"""
        try:
            result = subprocess.run(
                ['plantuml', '-version'],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False

    def validate_compilation(self, code: str, format: str) -> Tuple[bool, str]:
        """
        验证代码可编译性
        参照DiagramAgent的核心质量标准
        """
        if not code or len(code.strip()) < 10:
            return False, "代码为空或太短"

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                input_file = Path(tmpdir) / f"input.{format}"
                output_file = Path(tmpdir) / "output.png"

                input_file.write_text(code, encoding='utf-8')

                if format in ['mmd', 'mermaid']:
                    if not self.compilers['mermaid']:
                        return True, "Mermaid编译器未安装，跳过验证"

                    result = subprocess.run(
                        ['mmdc', '-i', str(input_file), '-o', str(output_file)],
                        capture_output=True,
                        timeout=30
                    )
                    if result.returncode != 0:
                        return False, f"Mermaid编译错误: {result.stderr.decode()[:100]}"

                elif format == 'dot':
                    if not self.compilers['dot']:
                        return True, "Graphviz编译器未安装，跳过验证"

                    result = subprocess.run(
                        ['dot', '-Tpng', str(input_file), '-o', str(output_file)],
                        capture_output=True,
                        timeout=30
                    )
                    if result.returncode != 0:
                        return False, f"DOT编译错误: {result.stderr.decode()[:100]}"

                elif format == 'puml':
                    if not self.compilers['plantuml']:
                        return True, "PlantUML编译器未安装，跳过验证"

                    result = subprocess.run(
                        ['plantuml', '-tpng', str(input_file)],
                        capture_output=True,
                        timeout=30
                    )
                    if result.returncode != 0:
                        return False, f"PlantUML编译错误: {result.stderr.decode()[:100]}"

                return True, "编译成功"

        except subprocess.TimeoutExpired:
            return False, "编译超时"
        except Exception as e:
            return False, f"编译异常: {str(e)}"

    def validate_sample(self, sample_dir: Path) -> ValidationResult:
        """验证单个样本"""
        errors = []
        warnings = []
        metrics = {}

        sample_id = sample_dir.name

        # 检查必需文件
        required_files = [
            f"{sample_id}.mmd",
            f"{sample_id}_dialogue.json",
            f"{sample_id}_meta.json"
        ]

        for req_file in required_files:
            if not (sample_dir / req_file).exists():
                errors.append(f"缺少文件: {req_file}")

        if errors:
            return ValidationResult(sample_id, False, errors, warnings, metrics)

        # 加载元数据
        try:
            meta_file = sample_dir / f"{sample_id}_meta.json"
            with open(meta_file, 'r', encoding='utf-8') as f:
                meta = json.load(f)
        except Exception as e:
            errors.append(f"无法加载元数据: {e}")
            return ValidationResult(sample_id, False, errors, warnings, metrics)

        # 检查代码文件
        code_format = meta.get('code_format', 'mmd')
        code_file = sample_dir / f"{sample_id}.{code_format}"

        if code_file.exists():
            code = code_file.read_text(encoding='utf-8')

            # 编译验证
            compiled, msg = self.validate_compilation(code, code_format)
            if not compiled:
                errors.append(f"编译失败: {msg}")
            else:
                metrics['compilation'] = 'passed'

            # 统计节点和边
            node_count = code.count('[') + code.count('(')
            edge_count = code.count('--')
            metrics['node_count'] = node_count
            metrics['edge_count'] = edge_count

            # 复杂度检查
            if node_count < 3:
                warnings.append("节点数过少 (<3)")
            elif node_count > 30:
                warnings.append("节点数过多 (>30)")

        # 检查对话文件
        dialogue_file = sample_dir / f"{sample_id}_dialogue.json"
        if dialogue_file.exists():
            try:
                with open(dialogue_file, 'r', encoding='utf-8') as f:
                    dialogue = json.load(f)

                turns = dialogue.get('turns', [])
                metrics['dialogue_turns'] = len(turns)

                if len(turns) < 3:
                    errors.append("对话轮次过少 (<3)")
                elif len(turns) > 20:
                    warnings.append("对话轮次过多 (>20)")

                # 检查言语行为一致性
                speech_acts = [turn.get('speech_act') for turn in turns]
                unique_acts = set(speech_acts)
                if len(unique_acts) < 2:
                    warnings.append("言语行为类型单一")

                metrics['speech_act_types'] = len(unique_acts)

            except Exception as e:
                errors.append(f"对话文件解析错误: {e}")

        # 检查增量步骤
        steps_file = sample_dir / f"{sample_id}_steps.json"
        if steps_file.exists():
            try:
                with open(steps_file, 'r', encoding='utf-8') as f:
                    steps = json.load(f)

                step_count = len(steps.get('steps', []))
                metrics['incremental_steps'] = step_count

                if step_count < 2:
                    warnings.append("增量步骤过少 (<2)")

            except Exception as e:
                warnings.append(f"步骤文件解析错误: {e}")

        # 计算质量分数
        quality_score = 1.0
        if errors:
            quality_score = 0.0
        else:
            quality_score -= len(warnings) * 0.1
            quality_score = max(0.0, quality_score)

        metrics['quality_score'] = quality_score

        passed = len(errors) == 0

        return ValidationResult(sample_id, passed, errors, warnings, metrics)

    def validate_stage(self, stage: str, fix: bool = False) -> Dict:
        """验证整个阶段的数据"""
        stage_dir = self.dataset_dir / stage

        if not stage_dir.exists():
            print(f"阶段目录不存在: {stage_dir}")
            return {}

        print(f"\n正在验证阶段: {stage}")
        print("="*70)

        # 收集所有样本
        samples = []
        for item in stage_dir.iterdir():
            if item.is_dir():
                samples.append(item)

        print(f"发现 {len(samples)} 个样本")

        # 验证每个样本
        results = []
        passed_count = 0
        failed_count = 0

        for i, sample_dir in enumerate(samples):
            if (i + 1) % 100 == 0:
                print(f"  已验证 {i+1}/{len(samples)}...")

            result = self.validate_sample(sample_dir)
            results.append(result)

            if result.passed:
                passed_count += 1
            else:
                failed_count += 1

                if fix:
                    # 修复或移除不合格的样本
                    self._fix_sample(sample_dir, result)

        # 生成统计
        type_distribution = Counter()
        speech_act_distribution = Counter()

        for result in results:
            # 加载元数据获取类型信息
            meta_file = self.dataset_dir / stage / result.sample_id / f"{result.sample_id}_meta.json"
            if meta_file.exists():
                try:
                    with open(meta_file, 'r', encoding='utf-8') as f:
                        meta = json.load(f)
                    type_distribution[meta.get('diagram_type', 'unknown')] += 1
                    speech_act_distribution[meta.get('speech_act_type', 'unknown')] += 1
                except:
                    pass

        stats = {
            'stage': stage,
            'total_samples': len(samples),
            'passed': passed_count,
            'failed': failed_count,
            'pass_rate': passed_count / len(samples) if samples else 0,
            'type_distribution': dict(type_distribution),
            'speech_act_distribution': dict(speech_act_distribution)
        }

        # 打印报告
        print("\n验证结果:")
        print(f"  总样本: {stats['total_samples']}")
        print(f"  通过: {stats['passed']}")
        print(f"  失败: {stats['failed']}")
        print(f"  通过率: {stats['pass_rate']*100:.2f}%")
        print(f"\n图表类型分布:")
        for dtype, count in type_distribution.most_common():
            print(f"    {dtype}: {count}")
        print(f"\n言语行为分布:")
        for act, count in speech_act_distribution.most_common():
            print(f"    {act}: {count}")

        return stats

    def _fix_sample(self, sample_dir: Path, result: ValidationResult):
        """修复或标记不合格样本"""
        # 创建标记文件
        flag_file = sample_dir / ".validation_failed"
        with open(flag_file, 'w', encoding='utf-8') as f:
            f.write(f"验证失败: {result.errors}\n")
            f.write(f"警告: {result.warnings}\n")

    def check_duplicates(self, stage: str) -> List[Tuple[str, str]]:
        """检查重复数据"""
        stage_dir = self.dataset_dir / stage

        if not stage_dir.exists():
            return []

        print(f"\n检查重复数据: {stage}")
        print("="*70)

        # 计算每个样本的代码哈希
        hashes = {}
        duplicates = []

        for sample_dir in stage_dir.iterdir():
            if not sample_dir.is_dir():
                continue

            sample_id = sample_dir.name
            code_files = list(sample_dir.glob("*.mmd")) + \
                        list(sample_dir.glob("*.dot")) + \
                        list(sample_dir.glob("*.puml"))

            if not code_files:
                continue

            code = code_files[0].read_text(encoding='utf-8')
            code_hash = hashlib.md5(code.encode()).hexdigest()

            if code_hash in hashes:
                duplicates.append((sample_id, hashes[code_hash]))
                print(f"  发现重复: {sample_id} == {hashes[code_hash]}")
            else:
                hashes[code_hash] = sample_id

        print(f"\n重复对数: {len(duplicates)}")
        return duplicates

    def generate_quality_report(self, output_file: str = "quality_report.json"):
        """生成质量报告"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'stages': {}
        }

        for stage in ['01_curation', '02_filtering', '03_reverse_engineering',
                      '04_validation', '05_final']:
            stats = self.validate_stage(stage)
            if stats:
                report['stages'][stage] = stats

        # 保存报告
        output_path = Path(output_file)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print(f"\n质量报告已保存: {output_path}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='Stream2Graph 数据质量验证工具'
    )

    parser.add_argument('--dataset-dir', '-d', type=str, default='./stream2graph_dataset',
                       help='数据集目录')
    parser.add_argument('--stage', '-s', type=str, required=True,
                       help='验证的阶段 (如: 05_final)')
    parser.add_argument('--fix', '-f', action='store_true',
                       help='自动修复不合格的样本')
    parser.add_argument('--duplicates', action='store_true',
                       help='检查重复数据')
    parser.add_argument('--report', '-r', action='store_true',
                       help='生成完整质量报告')

    args = parser.parse_args()

    # 创建验证器
    validator = DataValidator(dataset_dir=args.dataset_dir)

    # 检查重复
    if args.duplicates:
        validator.check_duplicates(args.stage)
        return

    # 生成报告
    if args.report:
        validator.generate_quality_report()
        return

    # 验证指定阶段
    validator.validate_stage(args.stage, fix=args.fix)


if __name__ == "__main__":
    main()

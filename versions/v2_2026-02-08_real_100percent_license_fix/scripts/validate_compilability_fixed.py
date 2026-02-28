#!/usr/bin/env python3
"""
修复版Mermaid可编译性验证脚本
- 单线程顺序处理，避免Windows多进程问题
- 更好的错误处理和日志记录
- 支持断点续传
"""
import json
import os
import subprocess
import tempfile
import time
import platform
from pathlib import Path
from datetime import datetime

# 检测操作系统
IS_WINDOWS = platform.system() == 'Windows'
NPX_CMD = 'npx.cmd' if IS_WINDOWS else 'npx'

def log(msg, flush=True):
    """打印日志"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"[{timestamp}] {msg}", flush=flush)

def validate_mermaid_code(code, diagram_type):
    """验证单个Mermaid代码的可编译性"""
    if not code or len(code) < 10:
        return {'valid': False, 'error': 'Empty or too short code'}

    tmp_path = None
    output_path = None

    try:
        # 创建临时文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.mmd', delete=False, encoding='utf-8') as tmp:
            tmp.write(code)
            tmp_path = tmp.name

        output_path = tmp_path + '.svg'

        # 使用mmdc编译
        cmd = [NPX_CMD, '@mermaid-js/mermaid-cli', '-i', tmp_path, '-o', output_path, '-b', 'white']

        # Windows需要shell=True
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            encoding='utf-8',
            shell=IS_WINDOWS,
            cwd=str(Path.home())  # 设置工作目录避免路径问题
        )

        success = result.returncode == 0 and os.path.exists(output_path)

        # 清理文件
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
        if output_path and os.path.exists(output_path):
            os.remove(output_path)

        if success:
            return {'valid': True, 'error': None}
        else:
            error_msg = result.stderr[:500] if result.stderr else result.stdout[:500]
            return {'valid': False, 'error': error_msg or 'Compilation failed'}

    except subprocess.TimeoutExpired:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
        if output_path and os.path.exists(output_path):
            os.remove(output_path)
        return {'valid': False, 'error': 'Timeout (>30s)'}
    except Exception as e:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
        if output_path and os.path.exists(output_path):
            os.remove(output_path)
        return {'valid': False, 'error': f'Exception: {str(e)[:200]}'}

def main():
    base_dir = Path('stream2graph_dataset/final_100percent_real')

    # 收集所有JSON文件
    all_files = []
    for source_dir in ['github', 'huggingface', 'gitlab', 'other']:
        dir_path = base_dir / source_dir
        if dir_path.exists():
            all_files.extend(list(dir_path.glob('*.json')))

    log(f"找到 {len(all_files)} 个样本文件")
    log(f"操作系统: {platform.system()}, 使用命令: {NPX_CMD}")
    log("="*70)

    # 检查已有验证结果的文件
    files_to_process = []
    already_validated = 0

    for f in all_files:
        try:
            with open(f, 'r', encoding='utf-8') as file:
                data = json.load(file)
            # 如果已经有compilation_status且不为error，则跳过
            if 'compilation_status' in data and data.get('compilation_status') != 'error':
                already_validated += 1
            else:
                files_to_process.append(f)
        except:
            files_to_process.append(f)

    log(f"已验证: {already_validated}, 待验证: {len(files_to_process)}")

    if len(files_to_process) == 0:
        log("所有文件已验证完成！")
        return

    # 统计
    stats = {
        'total': len(files_to_process),
        'success': 0,
        'failed': 0,
        'timeout': 0,
        'error': 0,
        'by_type': {},
        'by_source': {},
        'errors_sample': []
    }

    # 测试Mermaid CLI是否可用
    log("\n测试Mermaid CLI...")
    test_code = "graph TD\n    A --> B"
    test_result = validate_mermaid_code(test_code, 'test')
    if test_result['valid']:
        log("Mermaid CLI测试成功！")
    else:
        log(f"Mermaid CLI测试失败: {test_result['error']}")
        log("请确保已安装: npm install -g @mermaid-js/mermaid-cli")
        return

    log("\n开始验证可编译性...")
    log("="*70)

    start_time = time.time()

    for i, filepath in enumerate(files_to_process):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            code = data.get('code', '')
            diagram_type = data.get('diagram_type', 'unknown')
            source = filepath.parts[-2]

            # 验证
            result = validate_mermaid_code(code, diagram_type)

            # 更新文件
            data['compilation_status'] = 'success' if result['valid'] else 'failed'
            if result['error']:
                data['compilation_error'] = result['error']
            else:
                # 清除之前的错误信息
                data.pop('compilation_error', None)

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            # 统计
            if result['valid']:
                stats['success'] += 1
            else:
                stats['failed'] += 1
                if 'timeout' in result['error'].lower():
                    stats['timeout'] += 1

                # 收集错误样本（最多10个）
                if len(stats['errors_sample']) < 10:
                    stats['errors_sample'].append({
                        'file': filepath.name,
                        'type': diagram_type,
                        'error': result['error'][:100]
                    })

            # 按类型统计
            if diagram_type not in stats['by_type']:
                stats['by_type'][diagram_type] = {'total': 0, 'success': 0}
            stats['by_type'][diagram_type]['total'] += 1
            if result['valid']:
                stats['by_type'][diagram_type]['success'] += 1

            # 按来源统计
            if source not in stats['by_source']:
                stats['by_source'][source] = {'total': 0, 'success': 0}
            stats['by_source'][source]['total'] += 1
            if result['valid']:
                stats['by_source'][source]['success'] += 1

            # 进度报告
            if (i + 1) % 50 == 0 or i == len(files_to_process) - 1:
                elapsed = time.time() - start_time
                rate = (i + 1) / elapsed if elapsed > 0 else 0
                eta = (len(files_to_process) - i - 1) / rate if rate > 0 else 0

                success_rate = stats['success'] / (i + 1) * 100
                log(f"进度 {i + 1}/{len(files_to_process)} ({(i+1)/len(files_to_process)*100:.1f}%) - "
                    f"成功: {stats['success']}, 失败: {stats['failed']}, 成功率: {success_rate:.1f}% - "
                    f"速度: {rate:.1f}个/秒, 预计剩余: {eta/60:.1f}分钟")

        except Exception as e:
            log(f"Error processing {filepath}: {e}")
            stats['error'] += 1

    # 生成最终报告
    total_processed = stats['success'] + stats['failed']

    log("\n" + "="*70)
    log("可编译性验证完成报告")
    log("="*70)
    log(f"总计处理: {total_processed}")
    log(f"成功: {stats['success']} ({stats['success']/total_processed*100:.1f}%)")
    log(f"失败: {stats['failed']} ({stats['failed']/total_processed*100:.1f}%)")
    log(f"超时: {stats['timeout']}")
    log(f"处理错误: {stats['error']}")

    log("\n按图表类型统计:")
    for dtype, counts in sorted(stats['by_type'].items(), key=lambda x: -x[1]['total']):
        rate = (counts['success'] / counts['total'] * 100) if counts['total'] > 0 else 0
        log(f"  {dtype:20s}: {counts['success']:5d}/{counts['total']:5d} ({rate:5.1f}%)")

    log("\n按来源统计:")
    for source, counts in sorted(stats['by_source'].items(), key=lambda x: -x[1]['total']):
        rate = (counts['success'] / counts['total'] * 100) if counts['total'] > 0 else 0
        log(f"  {source:15s}: {counts['success']:5d}/{counts['total']:5d} ({rate:5.1f}%)")

    if stats['errors_sample']:
        log("\n失败样本示例:")
        for sample in stats['errors_sample']:
            log(f"  {sample['file']} ({sample['type']}): {sample['error']}")

    # 保存报告
    report = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'statistics': stats,
        'total_processed': total_processed,
        'total_elapsed_seconds': time.time() - start_time
    }

    with open('compilability_report_fixed.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    log("\n详细报告已保存到 compilability_report_fixed.json")

    # 生成摘要
    with open('COMPILABILITY_SUMMARY.md', 'w', encoding='utf-8') as f:
        f.write("# Stream2Graph Dataset Compilability Summary\n\n")
        f.write(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("## Validation Results\n\n")
        f.write(f"| Metric | Count | Percentage |\n")
        f.write(f"|--------|-------|------------|\n")
        f.write(f"| Total | {total_processed} | 100% |\n")
        f.write(f"| Success | {stats['success']} | {stats['success']/total_processed*100:.1f}% |\n")
        f.write(f"| Failed | {stats['failed']} | {stats['failed']/total_processed*100:.1f}% |\n")
        f.write(f"| Timeout | {stats['timeout']} | {stats['timeout']/total_processed*100:.1f}% |\n")

        f.write("\n## By Diagram Type\n\n")
        f.write("| Type | Success | Total | Rate |\n")
        f.write("|------|---------|-------|------|\n")
        for dtype, counts in sorted(stats['by_type'].items(), key=lambda x: -x[1]['total']):
            rate = (counts['success'] / counts['total'] * 100) if counts['total'] > 0 else 0
            f.write(f"| {dtype} | {counts['success']} | {counts['total']} | {rate:.1f}% |\n")

        f.write("\n## Notes\n\n")
        f.write("- Validation performed using Mermaid CLI (mmdc)\n")
        f.write("- Each code snippet was compiled to SVG\n")
        f.write("- Failed samples may have syntax errors or use unsupported features\n")

    log("摘要已保存到 COMPILABILITY_SUMMARY.md")

if __name__ == '__main__':
    main()

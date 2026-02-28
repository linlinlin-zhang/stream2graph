import json
import os
import requests
import time
from pathlib import Path
from hashlib import md5
from datetime import datetime
from collections import Counter

class MasterIntegrityPipeline:
    def __init__(self):
        self.base_dir = Path('/home/lin-server/pictures/stream2graph_dataset')
        self.output_dir = self.base_dir / 'v3_verified_final'
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = Path('/home/lin-server/pictures/INTEGRITY_CHECK_LOG.md')
        self.report_file = Path('/home/lin-server/pictures/FINAL_GOLDEN_DATASET_SUMMARY.md')
        
        self.invalid_licenses = ['none', 'error', 'unknown', 'rate_limited']
        self.stats = {
            'scanned': 0,
            'compilation_passed': 0,
            'compliance_passed': 0,
            'rejected_compilation': 0,
            'rejected_license': 0,
            'types': Counter(),
            'licenses': Counter()
        }
        
        if not self.log_file.exists():
            with open(self.log_file, 'w', encoding='utf-8') as f:
                f.write("# Stream2Graph 数据完整性校验日志\n\n")
                f.write("| 时间 | 样本ID | 结果 | 原因 | 仓库 |\n| --- | --- | --- | --- | --- |\n")

    def log_to_file(self, sid, status, reason, repo):
        line = f"| {datetime.now().strftime('%H:%M:%S')} | {sid} | {status} | {reason} | {repo} |\n"
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(line)

    def check_compilability(self, code):
        try:
            url = 'https://kroki.io/mermaid/svg'
            resp = requests.post(url, data=code.encode('utf-8'), timeout=10)
            return resp.status_code == 200
        except: return False

    def run(self, limit=100):
        all_samples = {}
        # 扫描多个潜在目录以确保覆盖所有存量
        potential_dirs = [
            self.base_dir / 'final_100percent_real', 
            self.base_dir / 'high_quality_subset',
            self.base_dir / 'real_data_raw'
        ]
        for d in potential_dirs:
            if not d.exists(): continue
            for f in d.rglob('*.json'):
                if f.name.startswith('index') or 'v3_verified_final' in str(f): continue
                try:
                    with open(f, 'r', encoding='utf-8') as file:
                        data = json.load(file)
                        if 'code' not in data: continue
                        chash = md5(data['code'].encode()).hexdigest()
                        if chash not in all_samples: all_samples[chash] = data
                except: continue

        print(f"--- 启动可视化审计 (批次: {limit}) ---")
        count = 0
        for chash, sample in all_samples.items():
            if count >= limit: break
            sid = sample['id']
            if (self.output_dir / f"{sid}.json").exists(): continue
            
            self.stats['scanned'] += 1
            print(f"[{self.stats['scanned']}] 校验: {sid}...", end=" ", flush=True)
            
            if not self.check_compilability(sample['code']):
                print("❌ 编译失败")
                self.stats['rejected_compilation'] += 1
                self.log_to_file(sid, "REJECTED", "Compile Fail", sample.get('github_repo', 'N/A'))
                continue
                
            has_license = sample.get('license') not in self.invalid_licenses
            if has_license:
                print("✅ 通过并入库")
                self.stats['compliance_passed'] += 1
                self.stats['types'][sample.get('diagram_type', 'unknown')] += 1
                self.stats['licenses'][sample.get('license')] += 1
                with open(self.output_dir / f"{sid}.json", 'w', encoding='utf-8') as sf:
                    json.dump(sample, sf, ensure_ascii=False, indent=2)
                self.log_to_file(sid, "PASSED", "Verified", sample.get('github_repo', 'N/A'))
                count += 1
            else:
                print("⚠️ 缺少许可证")
                self.stats['rejected_license'] += 1
                self.log_to_file(sid, "REJECTED", "No License", sample.get('github_repo', 'N/A'))
            
            time.sleep(0.1)
        
        self.generate_report()

    def generate_report(self):
        total_golden = len(list(self.output_dir.glob('*.json')))
        with open(self.report_file, 'w', encoding='utf-8') as f:
            f.write("# Stream2Graph 黄金数据集统计摘要\n\n")
            f.write(f"更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"### 1. 核心进度\n- 黄金样本总数: {total_golden}\n- 距离 8,000 目标: {8000 - total_golden}\n\n")
            f.write("### 2. 授权分布\n| 许可证 | 数量 |\n| --- | --- |\n")
            for k, v in self.stats['licenses'].most_common(): f.write(f"| {k} | {v} |\n")
        print(f"\n物理报告已更新: {self.report_file}")

if __name__ == "__main__":
    pipeline = MasterIntegrityPipeline()
    pipeline.run(limit=50)

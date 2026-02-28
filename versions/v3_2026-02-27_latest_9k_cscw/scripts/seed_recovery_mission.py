import json
import os
import requests
import time
from pathlib import Path
from hashlib import md5

class SeedRecoveryMission:
    def __init__(self):
        self.input_dirs = [
            Path('/home/lin-server/pictures/stream2graph_dataset/final_100percent_real/github'),
            Path('/home/lin-server/pictures/stream2graph_dataset/final_100percent_real/gitlab'),
            Path('/home/lin-server/pictures/stream2graph_dataset/final_100percent_real/other')
        ]
        self.output_dir = Path('/home/lin-server/pictures/stream2graph_dataset/v3_verified_final')
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.invalid_licenses = ['none', 'error', 'unknown', 'rate_limited']

    def check_compilability(self, code):
        try:
            url = 'https://kroki.io/mermaid/svg'
            resp = requests.post(url, data=code.encode('utf-8'), timeout=10)
            return resp.status_code == 200
        except: return False

    def clean_mermaid(self, code):
        # 尝试修复一些常见的解析错误
        # 1. 删除代码前后的 markdown 标记
        code = re.sub(r'```mermaid\s*', '', code)
        code = re.sub(r'```\s*', '', code)
        # 2. 修复未闭合的括号 (基础版)
        if code.count('[') > code.count(']'): code += ']'
        if code.count('(') > code.count(')'): code += ')'
        return code.strip()

    def run(self, target_total=3000):
        current_seeds = len(list(self.output_dir.glob('*.json')))
        print(f"当前黄金种子数: {current_seeds}")
        gap = target_total - current_seeds
        if gap <= 0:
            print("目标已达成！")
            return

        recovered = 0
        import re
        
        for d in self.input_dirs:
            if not d.exists(): continue
            print(f"正在扫描目录: {d.name}")
            for f in d.glob('*.json'):
                if recovered >= gap: break
                
                # 跳过已经存在于黄金池的
                if (self.output_dir / f.name).exists(): continue
                
                try:
                    with open(f, 'r', encoding='utf-8') as file:
                        data = json.load(file)
                    
                    # 检查是否有许可证
                    if data.get('license') in self.invalid_licenses: continue
                    
                    code = data.get('code', '')
                    if self.check_compilability(code):
                        # 直接通过
                        with open(self.output_dir / f.name, 'w', encoding='utf-8') as out:
                            json.dump(data, out, ensure_ascii=False, indent=2)
                        recovered += 1
                    else:
                        # 尝试修复后再次检查
                        fixed_code = self.clean_mermaid(code)
                        if fixed_code != code and self.check_compilability(fixed_code):
                            data['code'] = fixed_code
                            data['repair_status'] = 'fixed'
                            with open(self.output_dir / f.name, 'w', encoding='utf-8') as out:
                                json.dump(data, out, ensure_ascii=False, indent=2)
                            recovered += 1
                    
                    if recovered % 10 == 0 and recovered > 0:
                        print(f"  [+] 已抢救成功: {recovered} 条")
                    
                    time.sleep(0.05)
                except: continue
        
        print(f"任务结束，共抢救成功: {recovered} 条，当前总种子数: {current_seeds + recovered}")

if __name__ == '__main__':
    mission = SeedRecoveryMission()
    mission.run()

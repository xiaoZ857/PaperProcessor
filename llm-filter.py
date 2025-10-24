# all_papers/llm-filter.py
# Stage 2: 使用LLM精确筛选LLM for coding相关论文
# 依赖：pip install openai
# 运行：python all_papers/llm-filter.py

import os
import re
import json
import time
import argparse
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

from llm_client import get_client

# ===== LLM for coding 筛选提示词 =====
SYSTEM_PROMPT = """
你是一名专业的学术论文评审专家，专门负责判断论文是否属于"LLM for coding"研究领域。

"LLM for coding"领域的核心定义：
该领域专注于如何将大语言模型（LLM）应用于软件开发和编程任务，旨在利用LLM的自然语言理解和代码生成能力来改善、自动化或增强编程相关的各项工作。

属于"LLM for coding"的典型特征：
1. 核心应用对象：代码、程序、软件开发流程、编程任务
2. 核心技术：大语言模型（如GPT系列、LLaMA等）
3. 核心目标：解决编程、软件开发、代码相关的问题

具体包含但不限于以下场景：
- 代码生成、补全、翻译、修复、优化
- 代码理解、总结、解释、文档生成
- 测试用例生成、代码质量分析、bug检测修复
- 编程辅助工具、IDE增强、开发效率提升
- 代码搜索、API理解、技术文档生成
- 软件工程流程自动化、需求分析、设计生成
- 编程教育、代码教学、技术问答

不属于"LLM for coding"的典型特征：
1. 纯模型研究：模型结构改进、训练方法、理论基础
2. 通用AI应用：对话系统、文本生成、多模态理解
3. 非编程任务：图像处理、语音识别、推荐系统
4. 传统软件工程：不涉及LLM的软件开发方法
5. 安全与隐私：不针对编程任务的AI安全问题

请对每篇论文进行判断：
- 若属于"LLM for coding"：返回 "include"
- 若不属于：返回 "exclude"，并提供简短理由（不超过20字）

严格按JSON数组格式返回，每个元素包含：
{
"index": <整数，输入序号>,
"decision": <"include" 或 "exclude">,
"reason": <若为exclude则提供简短理由，否则为空字符串>,
"confidence": <0~1浮点数，表示判断的置信度>
}
"""

USER_PROMPT_TEMPLATE = """
请对下列论文进行"LLM for coding"相关性筛选。每条仅包含标题和摘要，摘要可能已截断。

请仔细分析每篇论文：
1. 是否使用大语言模型作为核心技术
2. 是否直接应用于编程或软件开发任务
3. 是否具有实际的编程应用场景

严格按要求返回JSON数组，不要输出其他任何文字。

papers:
{papers_json}
"""

def load_list(p: Path) -> List[Dict[str, Any]]:
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []

def save_json(p: Path, obj: Any):
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

def chunked(lst, n):
    return [lst[i:i+n] for i in range(0, len(lst), n)]

def truncate(s: str, max_chars: int = 1600) -> str:
    s = s or ""
    return s if len(s) <= max_chars else s[:max_chars] + " …"

def build_batch_payload(batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items = []
    for i, paper in enumerate(batch):
        items.append({
            "index": i,
            "title": paper.get("title", ""),
            "abstract": truncate(paper.get("abstract", "")),
            "url": paper.get("url", ""),
            "year": paper.get("year", ""),
            "conference": paper.get("conference", "")
        })
    return items

def strip_code_fences(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    return s.strip()

def safe_json_parse(s: str):
    s = strip_code_fences(s)
    try:
        return json.loads(s)
    except Exception:
        m = re.search(r"(\[\s*[\s\S]*\])", s)
        if m:
            return json.loads(m.group(1))
        raise

# ===== 断点续传支持 =====
class ProgressTracker:
    """进度追踪器,支持断点续传"""
    def __init__(self, base_dir: Path, output_name: str, stage: str):
        self.base_dir = base_dir
        self.stage = stage
        # 进度文件
        self.progress_file = base_dir / f".progress-{stage}-{output_name}.json"
        # 临时结果文件
        self.partial_included = base_dir / f".partial-included-{output_name}.json"
        self.partial_excluded = base_dir / f".partial-excluded-{output_name}.json"

        self.total_batches = 0
        self.processed_batches = 0
        self.included_papers = []
        self.excluded_papers = []

    def load_progress(self) -> bool:
        """加载进度,返回是否有未完成的任务"""
        if not self.progress_file.exists():
            return False

        try:
            progress = json.loads(self.progress_file.read_text(encoding="utf-8"))
            self.total_batches = progress.get("total_batches", 0)
            self.processed_batches = progress.get("processed_batches", 0)

            # 加载已处理的结果
            if self.partial_included.exists():
                self.included_papers = load_list(self.partial_included)
            if self.partial_excluded.exists():
                self.excluded_papers = load_list(self.partial_excluded)

            if self.processed_batches > 0:
                print(f"[INFO] 发现断点续传进度: 已处理 {self.processed_batches}/{self.total_batches} 批次")
                print(f"[INFO] 已筛选论文: {len(self.included_papers)} included, {len(self.excluded_papers)} excluded")
                return True
            return False
        except Exception as e:
            print(f"[WARN] 加载进度失败: {e}, 将从头开始")
            return False

    def save_progress(self):
        """保存当前进度"""
        progress = {
            "stage": self.stage,
            "total_batches": self.total_batches,
            "processed_batches": self.processed_batches,
            "timestamp": datetime.now().isoformat(),
            "included_count": len(self.included_papers),
            "excluded_count": len(self.excluded_papers)
        }
        self.progress_file.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")

        # 保存临时结果
        save_json(self.partial_included, self.included_papers)
        save_json(self.partial_excluded, self.excluded_papers)

    def finalize(self, final_included_path: Path, final_excluded_path: Path):
        """完成处理,保存最终结果并清理临时文件"""
        save_json(final_included_path, self.included_papers)
        save_json(final_excluded_path, self.excluded_papers)

        # 清理临时文件
        for f in [self.progress_file, self.partial_included, self.partial_excluded]:
            if f.exists():
                f.unlink()
                print(f"[INFO] 清理临时文件: {f.name}")

    def should_skip_batch(self, batch_index: int) -> bool:
        """判断是否应该跳过该批次(已处理)"""
        return batch_index < self.processed_batches

def filter_batch(client, batch: List[Dict[str, Any]], retries: int = 2, sleep: float = 0.8):
    payload = build_batch_payload(batch)
    user_prompt = USER_PROMPT_TEMPLATE.format(papers_json=json.dumps(payload, ensure_ascii=False, indent=2))
    last_err = None
    for attempt in range(retries + 1):
        try:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ]
            raw = client.chat_completion(messages, temperature=0.1)
            data = safe_json_parse(raw)
            if not isinstance(data, list):
                raise ValueError("LLM output is not a JSON array.")
            return data
        except Exception as e:
            last_err = e
            if attempt < retries:
                wait = sleep * (2 ** attempt)
                print(f"[WARN] call/parse failed (attempt {attempt+1}/{retries+1}): {e}; retry in {wait:.1f}s")
                time.sleep(wait)
            else:
                raise last_err

def main():
    ap = argparse.ArgumentParser(description="Stage 2: 使用LLM精确筛选LLM for coding相关论文 (支持断点续传)")
    ap.add_argument("--in", dest="infile", default="stage-1-output.json",
                    help="input json (Stage 1 output)")
    ap.add_argument("--out", dest="outfile", default="stage-2-output.json",
                    help="output json (included papers)")
    ap.add_argument("--rejected", dest="rejected_out", default="stage-2-rejected.json",
                    help="output json (excluded papers)")
    ap.add_argument("--model", default="deepseek-chat", help="LLM模型名称")
    ap.add_argument("--batch_size", type=int, default=8, help="批处理大小")
    ap.add_argument("--sleep", type=float, default=0.8, help="批次间暂停时间")
    ap.add_argument("--api_key", help="DeepSeek API密钥 (也可在llm_client.py中配置)")
    ap.add_argument("--provider", default="deepseek", help="LLM提供商")
    ap.add_argument("--reset", action="store_true", help="重置进度,从头开始处理")
    args = ap.parse_args()

    base = Path(__file__).parent.resolve()
    src = base / args.infile
    items = load_list(src)
    if not items:
        print(f"[WARN] empty or missing: {src}")
        return

    try:
        client = get_client(provider=args.provider, api_key=args.api_key, model=args.model)
    except ValueError as e:
        raise SystemExit(f"LLM客户端初始化失败: {e}")

    batches = chunked(items, args.batch_size)

    # 初始化进度追踪器
    tracker = ProgressTracker(base, args.outfile, "filter")
    tracker.total_batches = len(batches)

    # 如果指定重置,删除进度文件
    if args.reset and tracker.progress_file.exists():
        tracker.progress_file.unlink()
        if tracker.partial_included.exists():
            tracker.partial_included.unlink()
        if tracker.partial_excluded.exists():
            tracker.partial_excluded.unlink()
        print("[INFO] 已重置进度,从头开始处理")

    # 加载进度
    has_progress = tracker.load_progress()

    print(f"[INFO] {len(items)} items to filter, {len(batches)} batches (size={args.batch_size})")
    if has_progress:
        print(f"[INFO] 从批次 {tracker.processed_batches + 1} 继续处理...")

    try:
        for bi, batch in enumerate(batches):
            # 跳过已处理的批次
            if tracker.should_skip_batch(bi):
                continue

            batch_num = bi + 1
            print(f"  - filtering batch {batch_num}/{len(batches)} …")
            results = filter_batch(client, batch, retries=2, sleep=args.sleep)

            for j, r in enumerate(results):
                idx = r.get("index")
                paper = batch[idx] if isinstance(idx, int) and 0 <= idx < len(batch) else batch[min(j, len(batch)-1)]
                decision = r.get("decision", "exclude").lower()
                reason = r.get("reason", "")
                confidence = r.get("confidence", 0.0)

                # 创建结果记录
                result_paper = dict(paper)
                result_paper["_filter_decision"] = decision
                result_paper["_filter_reason"] = reason
                result_paper["_filter_confidence"] = confidence

                if decision == "include":
                    tracker.included_papers.append(result_paper)
                else:
                    tracker.excluded_papers.append(result_paper)

            # 更新进度并保存
            tracker.processed_batches = batch_num
            tracker.save_progress()
            print(f"    [已保存进度: {batch_num}/{len(batches)}]")

            time.sleep(args.sleep)

        # 完成处理,保存最终结果
        tracker.finalize(base / args.outfile, base / args.rejected_out)

        print(f"\n[OK] filtering completed")
        print(f"  - Included papers: {len(tracker.included_papers)} ({len(tracker.included_papers)/len(items)*100:.1f}%)")
        print(f"  - Excluded papers: {len(tracker.excluded_papers)} ({len(tracker.excluded_papers)/len(items)*100:.1f}%)")
        print(f"  - Results saved to: {args.outfile} and {args.rejected_out}")

    except KeyboardInterrupt:
        print(f"\n[WARN] 处理被中断! 进度已保存到批次 {tracker.processed_batches}/{len(batches)}")
        print(f"[INFO] 重新运行程序将从断点继续处理")
        raise
    except Exception as e:
        print(f"\n[ERROR] 处理失败: {e}")
        print(f"[INFO] 进度已保存到批次 {tracker.processed_batches}/{len(batches)}")
        print(f"[INFO] 修复问题后重新运行将从断点继续")
        raise

if __name__ == "__main__":
    main()
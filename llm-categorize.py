# all_papers/llm-categorize.py
# Stage 3: LLM精细分类（16类）
# 依赖：pip install openai
# 运行：python all_papers/llm-categorize.py

import os
import re
import json
import time
import argparse
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

from llm_client import get_client

# ===== 16 类（中文）+ 精炼定义 =====
CATEGORIES = [
    "代码生成","代码翻译","代码修复","代码理解","代码优化","测试用例生成",
    "代码补全","代码建议","代码需求转换","错误定位","提交信息生成",
    "代码问题解答","反例创建","数据科学任务","错误识别","代码搜索"
]
CATEGORY_HINTS = {
    "代码生成": "从自然语言/规格直接产出可执行代码或脚手架。",
    "代码翻译": "在不同语言/框架/版本之间转换代码。",
    "代码修复": "自动生成补丁/修复建议（APR等）。",
    "代码理解": "解释/总结代码意图与行为、语义理解。",
    "代码优化": "性能/资源/可读性等方面的改进与优化。",
    "测试用例生成": "自动生成单元/集成测试及断言。",
    "代码补全": "编辑器/IDE中基于上下文的补全/FIM。",
    "代码建议": "风格/安全/重构等建议（不直接改代码）。",
    "代码需求转换": "将需求/规格转为设计/接口/任务拆解。",
    "错误定位": "定位故障/缺陷的具体位置或范围（SBFL等）。",
    "提交信息生成": "基于变更/diff生成commit message等。",
    "代码问题解答": "就代码/库/API进行问答与解释。",
    "反例创建": "复现问题/PoC/对抗或反例生成。",
    "数据科学任务": "数据清洗/特征/建模/可视化等代码化流程。",
    "错误识别": "识别/分类错误类型，判断存在与类别。",
    "代码搜索": "检索函数/API/片段（语义或关键词）。"
}

SYSTEM_PROMPT = (
    "你是一名严谨的论文分类器，面向'LLM for coding'方向。\n"
    "请将每篇论文归入以下16类之一；若没有合适的类别，请使用'新类别'，并提供推荐的类别名称与简短概括：\n"
    + "\n".join([f"- {k}：{v}" for k, v in CATEGORY_HINTS.items()]) +
    "\n\n严格输出 JSON 数组（无多余文本/无Markdown），其中每个元素包含：\n"
    "{"
    "\"index\": <整数，输入序号>, "
    "\"category\": <上述16类之一或'新类别'>, "
    "\"recommended_label\": <string，若为'新类别'则必填，否则空字符串>, "
    "\"summary\": <string，若为'新类别'则给出对论文工作的20~40字概括，否则空字符串>, "
    "\"confidence\": <0~1浮点数>, "
    "\"rationale\": <不超过30字的原因>"
    "}\n"
    "务必只返回 JSON 数组本体。"
)

USER_PROMPT_TEMPLATE = (
    "请对下列论文进行分类。每条仅含必要字段，摘要已截断以节约tokens。\n"
    "严格按要求返回 JSON 数组，不要输出其他任何文字。\n\n"
    "papers:\n{papers_json}"
)

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
        self.partial_output = base_dir / f".partial-{output_name}.json"

        self.total_batches = 0
        self.processed_batches = 0
        self.categorized_papers = []

    def load_progress(self) -> bool:
        """加载进度,返回是否有未完成的任务"""
        if not self.progress_file.exists():
            return False

        try:
            progress = json.loads(self.progress_file.read_text(encoding="utf-8"))
            self.total_batches = progress.get("total_batches", 0)
            self.processed_batches = progress.get("processed_batches", 0)

            # 加载已处理的结果
            if self.partial_output.exists():
                self.categorized_papers = load_list(self.partial_output)

            if self.processed_batches > 0:
                print(f"[INFO] 发现断点续传进度: 已处理 {self.processed_batches}/{self.total_batches} 批次")
                print(f"[INFO] 已分类论文: {len(self.categorized_papers)} 篇")
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
            "categorized_count": len(self.categorized_papers)
        }
        self.progress_file.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")

        # 保存临时结果
        save_json(self.partial_output, self.categorized_papers)

    def finalize(self, final_output_path: Path):
        """完成处理,保存最终结果并清理临时文件"""
        save_json(final_output_path, self.categorized_papers)

        # 清理临时文件
        for f in [self.progress_file, self.partial_output]:
            if f.exists():
                f.unlink()
                print(f"[INFO] 清理临时文件: {f.name}")

    def should_skip_batch(self, batch_index: int) -> bool:
        """判断是否应该跳过该批次(已处理)"""
        return batch_index < self.processed_batches

def classify_batch(client, batch: List[Dict[str, Any]], retries: int = 2, sleep: float = 0.8):
    payload = build_batch_payload(batch)
    user_prompt = USER_PROMPT_TEMPLATE.format(papers_json=json.dumps(payload, ensure_ascii=False, indent=2))
    last_err = None
    for attempt in range(retries + 1):
        try:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ]
            raw = client.chat_completion(messages, temperature=0.2)
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
    ap = argparse.ArgumentParser(description="Stage 3: LLM精细分类（16类）(支持断点续传)")
    ap.add_argument("--in", dest="infile", default="stage-2-output.json",
                    help="input json (Stage 2 filtered papers)")
    ap.add_argument("--out", dest="outfile", default="stage-3-output.json",
                    help="output json (classified papers)")
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
    tracker = ProgressTracker(base, args.outfile, "categorize")
    tracker.total_batches = len(batches)

    # 如果指定重置,删除进度文件
    if args.reset and tracker.progress_file.exists():
        tracker.progress_file.unlink()
        if tracker.partial_output.exists():
            tracker.partial_output.unlink()
        print("[INFO] 已重置进度,从头开始处理")

    # 加载进度
    has_progress = tracker.load_progress()

    print(f"[INFO] {len(items)} items, {len(batches)} batches (size={args.batch_size})")
    if has_progress:
        print(f"[INFO] 从批次 {tracker.processed_batches + 1} 继续处理...")

    try:
        for bi, batch in enumerate(batches):
            # 跳过已处理的批次
            if tracker.should_skip_batch(bi):
                continue

            batch_num = bi + 1
            print(f"  - classifying batch {batch_num}/{len(batches)} …")
            results = classify_batch(client, batch, retries=2, sleep=args.sleep)

            for j, r in enumerate(results):
                idx = r.get("index")
                paper = batch[idx] if isinstance(idx, int) and 0 <= idx < len(batch) else batch[min(j, len(batch)-1)]
                category = r.get("category", "新类别")
                if category not in CATEGORIES and category != "新类别":
                    category = "新类别"

                tracker.categorized_papers.append({
                    "title": paper.get("title", ""),
                    "abstract": paper.get("abstract", ""),
                    "url": paper.get("url", ""),
                    "year": paper.get("year", ""),
                    "conference": paper.get("conference", ""),
                    "category": category,
                    "recommended_label": r.get("recommended_label", "") if category == "新类别" else "",
                    "summary": r.get("summary", "") if category == "新类别" else "",
                    "confidence": r.get("confidence", 0.0),
                    "rationale": r.get("rationale", "")
                })

            # 更新进度并保存
            tracker.processed_batches = batch_num
            tracker.save_progress()
            print(f"    [已保存进度: {batch_num}/{len(batches)}]")

            time.sleep(args.sleep)

        # 完成处理,保存最终结果
        tracker.finalize(base / args.outfile)

        print(f"\n[OK] categorization completed")
        print(f"  - Categorized papers: {len(tracker.categorized_papers)}")
        print(f"  - Results saved to: {args.outfile}")

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
# all_papers/keyword-filter.py
# 用法：
#   python all_papers/keyword-filter.py
# 自定义：
#   python all_papers/keyword-filter.py --in all_papers.json --ai ai-related.json --coding llm-coding.json --ai_noncoding ai-noncoding.json --non_ai non-ai.json

import json, re, argparse
from pathlib import Path
from typing import List, Dict, Tuple

# ---------- IO ----------
def load_json(path: Path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []

def save_json(path: Path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

def fields_text(p: Dict) -> str:
    t = (p.get("title") or "") + " " + (p.get("abstract") or "")
    t = t.lower().replace("–","-").replace("—","-")
    t = re.sub(r"\s+", " ", t)
    return t.strip()

# ---------- 正则工具：支持空格/连字符/下划线变体 + 词边界 ----------
def alt_hyphen_space(term: str) -> str:
    term = term.strip().lower()
    term = re.sub(r"[\s\-_]+", "[-_ ]+", term)
    return term

def compile_terms(terms: List[str], word_boundary: bool = True) -> List[re.Pattern]:
    pats = []
    for t in sorted(set(terms)):
        t = t.strip().lower()
        if not t:
            continue
        core = alt_hyphen_space(t) if re.search(r"[ _-]", t) else re.escape(t)
        pats.append(re.compile(rf"\b{core}\b" if word_boundary else core))
    return pats

def find_hits(text: str, pats: List[re.Pattern]) -> List[str]:
    out = []
    for p in pats:
        m = p.search(text)
        if m:
            out.append(m.group(0))
    return sorted(set(out))

# ---------- 词库：Stage 1（AI/LLM/Agent 相关） ----------
AI_TERMS = [
    # 概念/机制
    "large language model", "language model", "llm", "plm",
    "foundation model", "pretrained model", "pre-trained model",
    "transformer", "self-attention", "decoder-only", "encoder-decoder",
    "autoregressive", "generative model", "inference",
    "fine-tuning", "finetuning", "instruction tuning", "prompt", "prompting",
    "prompt tuning", "rlhf", "dpo", "sft", "alignment",
    "tool use", "tool-use", "tool calling", "function calling",
    "retrieval-augmented generation", "rag",
    "agent", "multi-agent", "autonomous agent", "agentic workflow",
    "few-shot", "zero-shot", "in-context learning", "icl",
    "distillation", "quantization", "kv cache", "speculative decoding",
    "mixture of experts", "moe",
    # 模型家族/名称
    "gpt-4", "gpt4", "gpt-3.5", "gpt-3", "codex",
    "gemini", "palm", "claude",
    "llama", "llama 2", "llama 3", "llama-3", "mistral", "mixtral",
    "phi", "orion",
    "qwen", "glm", "chatglm", "deepseek", "baichuan", "yuan",
    # 代码向模型（也算 AI 信号）
    "code llama", "code-llama", "starcoder", "santacoder", "wizardcoder",
    "replit", "incoder", "codet5", "codegeex", "starchat",
    "deepseek-coder", "qwen-coder", "qwen2.5-coder", "octocoder",
]
AI_PATTERNS = compile_terms(AI_TERMS, word_boundary=True)

# ---------- 词库：Stage 2（Coding 相关，用于 LLM×Coding 粗筛） ----------
CODING_ANCHORS = [
    # 编程/软件生态锚点
    "source code", "codebase", "program", "software", "repository",
    "developer", "ide", "editor", "compiler", "debugger", "build system",
    "api", "sdk", "function", "method", "class", "module", "package",
    "dependency", "import", "namespace",
    "unit test", "test case", "coverage", "test suite", "assertion",
    "static analysis", "dynamic analysis", "symbolic execution",
    "fuzzing", "taint", "control flow", "data flow", "call graph", "points-to",
    "ast", "ir", "bytecode", "llvm", "wasm", "cfg", "dfg",
    "git", "github", "gitlab", "commit", "pull request", "merge request",
    "issue tracker", "ci/cd", "continuous integration", "continuous delivery",
    "repository mining", "program analysis", "software engineering",
    "build pipeline", "monorepo", "diff", "patch",
]

CODE_TASK_SIGNALS = [
    # 覆盖16类任务的常见英文表达（仅用于判断"coding相关"，不做细分）
    # 代码生成
    "code generation", "generate code", "program synthesis", "nl2code", "nl to code", "text-to-code",
    # 代码翻译
    "code translation", "transpilation", "transpiler", "cross-language translation",
    "source-to-source translation", "transcompiler",
    # 代码修复
    "code repair", "program repair", "automated program repair", "apr",
    "patch generation", "bug fix generation", "fix suggestion",
    # 代码理解
    "code understanding", "code comprehension", "code summarization", "explain code",
    "intent inference", "behavior summarization",
    # 代码优化
    "code optimization", "performance optimization", "speedup", "latency reduction",
    "resource optimization", "memory optimization", "refactor for performance",
    # 测试用例生成
    "test generation", "unit test generation", "test case generation", "test synthesis",
    "assertion generation", "property-based testing",
    # 代码补全
    "code completion", "auto-completion", "autocomplete", "fill-in-the-middle", "fim",
    "project-aware completion", "repo-aware completion", "ide completion",
    # 代码建议
    "code recommendation", "coding recommendation", "lint suggestion",
    "style suggestion", "refactoring suggestion", "best practice suggestion",
    # 代码需求转换
    "requirement to code", "spec to code", "natural language requirement to design",
    "task decomposition for coding", "api design from requirements",
    # 错误定位
    "fault localization", "bug localization", "defect localization", "sbfl",
    "spectrum-based fault localization", "localize bug",
    # 提交信息生成
    "commit message generation", "commit message suggestion", "changelog generation",
    # 代码问题解答
    "code question answering", "programming qa", "api question answering",
    "stack overflow style qa", "debugging qa",
    # 反例创建
    "counterexample generation", "poc workflow", "proof-of-concept workflow",
    "bug reproduction steps", "reproduction steps", "adversarial example for code",
    # 数据科学任务（编程语境）
    "notebook automation", "data wrangling", "data cleaning", "feature engineering",
    "pandas script", "numpy script", "plot generation", "sql query generation",
    # 错误识别
    "bug detection", "fault detection", "error identification", "defect detection",
    "linting", "bug classifier", "static bug finder", "security smell detection",
    # 代码搜索
    "code search", "semantic code search", "code retrieval", "function search", "api search",
]

CODE_MODEL_NAMES = [
    "code llama", "code-llama", "starcoder", "santacoder", "wizardcoder",
    "replit", "incoder", "codet5", "codegeex", "starchat",
    "deepseek-coder", "qwen-coder", "qwen2.5-coder", "octocoder",
]

CODING_PATTERNS = compile_terms(CODING_ANCHORS + CODE_TASK_SIGNALS + CODE_MODEL_NAMES, word_boundary=True)

# ---------- 判定 ----------
def is_ai_related(text: str) -> Tuple[bool, List[str]]:
    ai = find_hits(text, AI_PATTERNS)
    return (len(ai) > 0, ai)

def is_coding_related(text: str) -> Tuple[bool, List[str]]:
    coding = find_hits(text, CODING_PATTERNS)
    return (len(coding) > 0, coding)

# ---------- 主流程：两阶段 + 两个额外输出 ----------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="infile", default="all_papers.json",
                        help="input JSON (merged list)")
    parser.add_argument("--stage1", dest="stage1_out", default="stage-1-output.json",
                        help="output JSON for Stage 1 (LLM × Coding papers)")
    parser.add_argument("--ai_noncoding", dest="ai_noncoding_out", default="ai-noncoding.json",
                        help="output JSON for AI-related but non-coding")
    parser.add_argument("--non_ai", dest="non_ai_out", default="non-ai.json",
                        help="output JSON for non-AI papers")
    args = parser.parse_args()

    base = Path(__file__).parent.resolve()
    src = base / args.infile
    data = load_json(src)
    if not data:
        print(f"[WARN] empty or missing: {src}")
        return

    ai_list, non_ai_list = [], []

    # Stage 1: AI vs non-AI
    for p in data:
        txt = fields_text(p)
        ai_flag, ai_hits_ = is_ai_related(txt)
        q = dict(p)
        if ai_flag:
            q["_ai_hits"] = ai_hits_
            ai_list.append(q)
        else:
            q["_ai_hits"] = []
            non_ai_list.append(q)

    save_json(base / args.non_ai_out, non_ai_list)
    print(f"[OK] AI vs non-AI -> AI-related={len(ai_list)}, non-AI={len(non_ai_list)}")

    # Stage 1: Coding within AI
    coding_list, ai_noncoding_list = [], []
    for p in ai_list:
        txt = fields_text(p)
        coding_flag, coding_hits_ = is_coding_related(txt)
        q = dict(p)
        if coding_flag:
            q["_coding_hits"] = coding_hits_
            coding_list.append(q)
        else:
            q["_coding_hits"] = []
            ai_noncoding_list.append(q)

    save_json(base / args.stage1_out, coding_list)
    save_json(base / args.ai_noncoding_out, ai_noncoding_list)
    print(f"[OK] Stage 1 -> LLM×Coding={len(coding_list)}, AI-nonCoding={len(ai_noncoding_list)}")

if __name__ == "__main__":
    main()
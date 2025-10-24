# all_papers/statistics.py
# Stage 4: 统计分析最终的分类结果，包括各类别的数量和具体标题

import json
from pathlib import Path
from collections import Counter, OrderedDict

# 配置输入文件路径
JSON_PATH = "stage-3-output.json"

# 16个目标类别（固定顺序）
CATEGORIES = [
    "代码生成","代码翻译","代码修复","代码理解","代码优化","测试用例生成",
    "代码补全","代码建议","代码需求转换","错误定位","提交信息生成",
    "代码问题解答","反例创建","数据科学任务","错误识别","代码搜索"
]

def load_data(path: str):
    """加载JSON数据文件"""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"找不到文件 {path}。请确保该文件在脚本旁边，或调整 JSON_PATH 路径。")

    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("输入JSON应该是一个记录列表。")

    return data

def categorize_data(data):
    """对数据进行分类统计"""
    cat_counter = Counter()
    new_labels = Counter()
    categorized_papers = {}

    # 为每个类别初始化空列表
    for cat in CATEGORIES + ["新类别"]:
        categorized_papers[cat] = []

    for rec in data:
        cat = str(rec.get("category", "")).strip()
        if not cat:
            cat = "新类别"
        if cat == "新类别":
            lab = str(rec.get("recommended_label", "")).strip() or "—"
            new_labels[lab] += 1
        else:
            # 如果类别不在预定义列表中，归入新类别
            if cat not in CATEGORIES:
                cat = "新类别"
                lab = str(rec.get("recommended_label", "")).strip() or "—"
                new_labels[lab] += 1

        cat_counter[cat] += 1

        # 将论文添加到对应类别中
        if cat not in categorized_papers:
            categorized_papers[cat] = []

        categorized_papers[cat].append({
            "title": rec.get("title", ""),
            "conference": rec.get("conference", ""),
            "year": rec.get("year", ""),
            "confidence": rec.get("confidence", 0.0),
            "recommended_label": rec.get("recommended_label", ""),
            "summary": rec.get("summary", "")
        })

    return cat_counter, new_labels, categorized_papers

def print_statistics(cat_counter, new_labels, total):
    """打印基本统计信息"""
    print("=== 16个类别的论文数量 ===")
    ordered = OrderedDict((c, cat_counter.get(c, 0)) for c in CATEGORIES)
    for c, n in ordered.items():
        print(f"{c}: {n}")
    print()

    # 新类别统计
    new_count = cat_counter.get("新类别", 0)
    print("=== 新类别统计 ===")
    print(f"新类别总数: {new_count} / {total} ({new_count/total*100:.1f}%)")

    # 列出新类别的推荐标签（按数量排序）
    if new_count > 0:
        print("\n=== 新类别明细（recommended_label -> count）===")
        for lab, cnt in sorted(new_labels.items(), key=lambda x: (-x[1], x[0])):
            print(f"{lab}: {cnt}")

def print_category_titles(categorized_papers):
    """打印每个类别的论文标题"""
    print("\n\n=== 各类别论文详情 ===")

    for category in CATEGORIES + ["新类别"]:
        papers = categorized_papers.get(category, [])
        if not papers:
            continue

        print(f"\n### {category} ({len(papers)} 篇) ###")
        for i, paper in enumerate(papers, 1):
            confidence = paper.get("confidence", 0.0)
            year = paper.get("year", "")
            conference = paper.get("conference", "")
            title = paper.get("title", "")

            print(f"{i:2d}. [{year} {conference}] ({confidence:.2f}) {title}")

            # 如果是新类别，显示推荐标签
            if category == "新类别" and paper.get("recommended_label"):
                print(f"    -> 推荐类别: {paper['recommended_label']}")
                if paper.get("summary"):
                    print(f"    -> 摘要: {paper['summary']}")

        print()  # 类别之间空一行

def print_summary_stats(cat_counter, total):
    """打印汇总统计"""
    print("=== 总体统计摘要 ===")
    print(f"论文总数: {total}")

    # 统计有论文的类别数
    non_zero_categories = sum(1 for count in cat_counter.values() if count > 0)
    print(f"非空类别数: {non_zero_categories} / {len(CATEGORIES) + 1}")

    # 最大和最小类别
    max_cat = max(cat_counter.items(), key=lambda x: x[1])
    min_cat = min([(cat, count) for cat, count in cat_counter.items() if count > 0], key=lambda x: x[1])

    print(f"最大类别: {max_cat[0]} ({max_cat[1]} 篇)")
    print(f"最小非空类别: {min_cat[0]} ({min_cat[1]} 篇)")

    # 前3大类别
    top_categories = sorted(cat_counter.items(), key=lambda x: x[1], reverse=True)[:3]
    print("前3大类别:")
    for i, (cat, count) in enumerate(top_categories, 1):
        percentage = count / total * 100
        print(f"  {i}. {cat}: {count} 篇 ({percentage:.1f}%)")

def main():
    """主函数"""
    try:
        # 加载数据
        data = load_data(JSON_PATH)

        # 分类统计
        cat_counter, new_labels, categorized_papers = categorize_data(data)
        total = len(data)

        # 打印统计信息
        print_statistics(cat_counter, new_labels, total)

        # 打印各类别标题
        print_category_titles(categorized_papers)

        # 打印汇总统计
        print_summary_stats(cat_counter, total)

    except Exception as e:
        print(f"错误: {e}")
        print("请确保 'all_papers\stage-3-output.json' 文件存在且格式正确。")

if __name__ == "__main__":
    main()
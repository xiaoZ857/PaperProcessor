# 断点续传功能使用指南

## 功能概述

为了解决大规模论文处理中可能遇到的中断问题,我们为 `llm-filter.py` 和 `llm-categorize.py` 添加了完善的断点续传功能。

### 核心特性

1. **自动进度保存**: 每处理完一个批次,立即保存进度和结果
2. **断点恢复**: 程序中断后重新运行,自动从断点继续处理
3. **数据安全**: 使用临时文件保护数据,避免数据丢失
4. **透明操作**: 无需手动干预,自动检测和恢复进度

---

## 工作原理

### 进度文件

处理过程中会创建以下文件:

```
.progress-{stage}-{output_name}.json    # 进度记录
.partial-included-{output_name}.json    # 临时结果(filter阶段的included)
.partial-excluded-{output_name}.json    # 临时结果(filter阶段的excluded)
.partial-{output_name}.json             # 临时结果(categorize阶段)
```

### 进度文件内容示例

```json
{
  "stage": "filter",
  "total_batches": 100,
  "processed_batches": 45,
  "timestamp": "2025-10-24T10:30:00",
  "included_count": 120,
  "excluded_count": 240
}
```

---

## 使用方法

### 1. 正常运行(首次处理)

```bash
# Filter阶段
python llm-filter.py --in all_papers.json --out stage-2-output.json --batch_size 8

# Categorize阶段
python llm-categorize.py --in stage-2-output.json --out stage-3-output.json --batch_size 8
```

### 2. 中断场景

处理过程可能因以下原因中断:
- 网络问题
- API限流
- 手动中断 (Ctrl+C)
- 系统崩溃
- 电源故障

**中断后的提示信息:**

```
[WARN] 处理被中断! 进度已保存到批次 45/100
[INFO] 重新运行程序将从断点继续处理
```

### 3. 断点恢复

**只需重新运行相同的命令**,程序会自动检测进度并继续:

```bash
# 重新运行相同命令
python llm-filter.py --in all_papers.json --out stage-2-output.json --batch_size 8
```

**恢复时的输出:**

```
[INFO] 发现断点续传进度: 已处理 45/100 批次
[INFO] 已筛选论文: 120 included, 240 excluded
[INFO] 360 items to filter, 100 batches (size=8)
[INFO] 从批次 46 继续处理...
  - filtering batch 46/100 …
    [已保存进度: 46/100]
  - filtering batch 47/100 …
    [已保存进度: 47/100]
...
```

### 4. 重置进度(从头开始)

如果需要重新开始处理,使用 `--reset` 参数:

```bash
python llm-filter.py --in all_papers.json --out stage-2-output.json --reset
```

### 5. 完成处理

处理完成后,程序会:
1. 将临时结果保存为最终输出文件
2. 自动删除所有进度和临时文件
3. 显示完成统计信息

```
[OK] filtering completed
  - Included papers: 500 (50.0%)
  - Excluded papers: 500 (50.0%)
  - Results saved to: stage-2-output.json and stage-2-rejected.json
[INFO] 清理临时文件: .progress-filter-stage-2-output.json.json
[INFO] 清理临时文件: .partial-included-stage-2-output.json.json
[INFO] 清理临时文件: .partial-excluded-stage-2-output.json.json
```

---

## 最佳实践

### 1. 合理设置批次大小

```bash
# 小批次: 更频繁保存,恢复损失小,但整体耗时稍长
python llm-filter.py --batch_size 5

# 中批次: 平衡性能和安全(推荐)
python llm-filter.py --batch_size 8

# 大批次: 性能更好,但中断时损失较大
python llm-filter.py --batch_size 20
```

**建议:**
- 小数据集 (< 1000篇): batch_size = 10-20
- 中等数据集 (1000-5000篇): batch_size = 8-10
- 大数据集 (> 5000篇): batch_size = 5-8

### 2. 监控进度

处理大数据集时,可以实时查看进度:

```bash
# 查看进度文件
cat .progress-filter-stage-2-output.json.json | python -m json.tool

# 查看临时结果
wc -l .partial-included-stage-2-output.json.json
```

### 3. 备份重要数据

虽然断点续传已经很安全,但建议:

```bash
# 在重要节点备份进度文件
cp .progress-filter-*.json backup/
cp .partial-*.json backup/
```

### 4. 处理多个会议/年份

对于多个会议的大规模处理:

```bash
# 分批处理,每个会议单独输出
for conf in ICSE FSE ASE; do
  echo "处理 $conf..."
  python llm-filter.py \
    --in ${conf}_papers.json \
    --out ${conf}_filtered.json \
    --batch_size 8
done
```

---

## 故障排除

### 问题1: 进度文件损坏

**症状:** 加载进度失败

**解决:**
```bash
# 删除损坏的进度文件,从头开始
rm .progress-*.json .partial-*.json
python llm-filter.py --in input.json --out output.json
```

### 问题2: 结果不完整

**症状:** 处理完成但结果数量不对

**排查:**
```bash
# 检查进度记录
cat .progress-filter-*.json

# 对比输入输出数量
wc -l input.json output.json
```

### 问题3: 磁盘空间不足

**症状:** 保存进度时失败

**解决:**
```bash
# 清理不需要的临时文件
rm .partial-*.json.old

# 增大批次大小,减少保存频率
python llm-filter.py --batch_size 20
```

### 问题4: 进度显示异常

**症状:** 重启后进度显示为0

**排查:**
```bash
# 检查进度文件是否存在
ls -la .progress-*.json

# 检查文件内容
cat .progress-filter-*.json

# 如果文件存在但未被识别,检查输出文件名是否一致
# 进度文件名包含输出文件名,必须完全匹配
```

---

## 技术细节

### 进度追踪器 (ProgressTracker)

```python
class ProgressTracker:
    - load_progress()      # 加载断点
    - save_progress()      # 保存进度
    - finalize()           # 完成并清理
    - should_skip_batch()  # 判断批次是否已处理
```

### 异常处理

- **KeyboardInterrupt**: 用户手动中断 (Ctrl+C)
- **网络异常**: API调用失败,自动重试
- **其他异常**: 保存进度后抛出异常

### 数据一致性

1. 先保存临时结果,再更新进度
2. 使用原子写入避免文件损坏
3. 完成后才删除临时文件

---

## 测试

使用提供的测试脚本验证功能:

```bash
# 1. 创建测试数据
python test_resume.py
# 选择: 1

# 2. 运行测试(小批次)
python llm-filter.py --in test-input.json --out test-output.json --batch_size 3

# 3. 处理2-3批次后按 Ctrl+C 中断

# 4. 检查进度
python test_resume.py
# 选择: 2

# 5. 恢复处理
python llm-filter.py --in test-input.json --out test-output.json --batch_size 3

# 6. 清理测试文件
python test_resume.py
# 选择: 4
```

---

## FAQ

**Q: 断点续传会影响性能吗?**

A: 影响很小。每批次保存一次进度,增加的时间通常不到1秒,相比整体处理时间可忽略。

**Q: 可以修改批次大小吗?**

A: 恢复时应使用相同的批次大小。如果修改,会从断点重新开始该批次,不会丢失已处理数据。

**Q: 临时文件何时删除?**

A: 只有在完全处理完成后才删除。中断时保留,以便恢复。

**Q: 可以暂停后在另一台机器继续吗?**

A: 可以。复制进度文件(.progress-*.json)和临时文件(.partial-*.json)到新机器,保持相同目录结构即可。

**Q: 如何查看总进度?**

A: 查看进度文件中的 `processed_batches/total_batches`,或观察每批次后的进度提示。

---

## 总结

断点续传功能为大规模论文处理提供了可靠保障:

✅ **自动保存**: 无需手动操作
✅ **安全可靠**: 数据不会丢失
✅ **透明恢复**: 自动从断点继续
✅ **灵活控制**: 支持重置和手动干预

现在你可以放心处理大规模论文数据,即使中断也能无缝恢复!

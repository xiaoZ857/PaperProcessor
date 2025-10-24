# All Papers 论文自动分类与分析工具

这是一个专为学术论文自动化分类和分析设计的完整工具链，特别针对"LLM for coding"研究领域的论文筛选和细分。工具采用多阶段处理流程，从大规模论文数据集中精准识别相关研究并进行细致分类。

## 🎯 核心功能

- **智能关键词过滤**：基于精心设计的词汇库进行初筛，有效分离AI相关论文
- **LLM精确判断**：使用大语言模型深度分析论文内容，确保研究领域匹配度
- **16类精细分类**：将相关论文细分为具体的研究方向和应用场景
- **统计分析报告**：生成详细的分类统计、趋势分析和可视化数据
- **批处理优化**：支持大规模数据集的高效处理

## 📁 项目结构

```
all_papers/
├── README.md                 # 项目说明文档
├── all_papers.json           # 原始论文数据集（当前的只是示例）
├── keyword-filter.py         # 阶段1: 关键词过滤器
├── llm-filter.py             # 阶段2: LLM精确过滤器
├── llm-categorize.py         # 阶段3: LLM精细分类器
├── statistics.py             # 阶段4: 统计分析器
└── llm_client.py             # LLM客户端模块 
```

## 使用步骤（4阶段流程）

### 步骤1：数据准备

**⚠️ 重要提醒**
- 将您的`all_papers.json`文件放入`all_papers/`目录
- **强烈建议**：在开始处理前复制一份原始数据作为备份
- 确保`all_papers.json`格式正确，应包含以下字段：
  ```json
  {
    "title": "论文标题",
    "abstract": "论文摘要",
    "url": "论文链接",
    "year": "发表年份",
    "conference": "会议名称"
  }
  ```

### 步骤2：Stage 1 - 关键词过滤

```bash
python keyword-filter.py
```

**功能**：基于预定义关键词进行初步筛选，分离出可能相关的论文

**输出文件**：
- `stage-1-output.json`：LLM×Coding相关论文（进入Stage 2）
- `ai-noncoding.json`：AI相关但非编程的论文
- `non-ai.json`：非AI相关论文

### 步骤3：Stage 2 - LLM精确过滤

```bash
python llm-filter.py
```

**依赖安装**：
```bash
pip install openai
```

**功能**：使用LLM精确判断论文是否真正属于"LLM for coding"研究领域

**输出文件**：
- `stage-2-output.json`：确认属于LLM for coding的论文（进入Stage 3）
- `stage-2-rejected.json`：被排除的论文（不相关）

### 步骤4：Stage 3 - LLM精细分类

```bash
python llm-categorize.py
```

**功能**：对确认相关的论文进行16类精细分类

**输出文件**：
- `stage-3-output.json`：包含16类分类结果的详细数据

### 步骤5：Stage 4 - 统计分析

```bash
python statistics.py
```

**16个预定义类别**：
1. 代码生成
2. 代码翻译
3. 代码修复
4. 代码理解
5. 代码优化
6. 测试用例生成
7. 代码补全
8. 代码建议
9. 代码需求转换
10. 错误定位
11. 提交信息生成
12. 代码问题解答
13. 反例创建
14. 数据科学任务
15. 错误识别
16. 代码搜索

**输出内容**：
- 各类别的论文数量统计
- 新类别明细（推荐标签）
- 每个类别的详细论文列表
- 总体统计摘要

## 配置说明

### API密钥配置

在`llm_client.py`文件顶部设置您的DeepSeek API密钥：
```python
DEEPSEEK_API_KEY = "your_deepseek_api_key_here"  # 替换为实际密钥
```



## 注意事项

### 数据安全
- ⚠️ **备份原始数据**：处理前务必备份`all_papers.json`
- ⚠️ **API费用**：LLM分类会消耗API调用，注意费用控制
- ⚠️ **网络稳定性**：分类过程较长，确保网络连接稳定

## 故障排除

### 常见问题

1. **文件未找到**
   ```
   FileNotFoundError: Cannot find classified-16.json
   ```
   解决：确保已按顺序执行前两个步骤

2. **API认证失败**
   ```
   LLM客户端初始化失败: 请在llm_client.py文件顶部的DEEPSEEK_API_KEY中填写你的真实API密钥
   ```
   解决：检查`llm_client.py`文件顶部的API密钥配置是否正确，确保已替换为真实的DeepSeek API密钥

3. **JSON格式错误**
   ```
   输入JSON应该是一个记录列表
   ```
   解决：检查`all_papers.json`格式是否为标准JSON数组

### 优化关键词
更新`keyword-classify.py`中的`AI_TERMS`和`CODING_ANCHORS`来优化关键词过滤效果。

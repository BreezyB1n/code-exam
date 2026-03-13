# 编程面试：构建一个搜索引擎

## 概述

你需要构建一个**搜索引擎 Web 应用**，对一组 HTML 格式的 On-Call SOP 文档进行解析、索引和搜索。

本题分为三个阶段，每阶段在前一阶段基础上递进。请按顺序完成，完成当前阶段后再进入下一阶段。

- 编程语言不限
- 可以使用任何 AI 工具辅助
- `data/` 目录下提供了 10 份部门 On-Call SOP 的 HTML 文件
- 需要实现一个 HTTP API 服务和一个简单的前端页面

---

## HTTP API 定义

### 添加文档

```
POST /documents

Request Body:
{
  "id": "doc1",
  "html": "<html>...</html>"
}

Response: 201 Created
{
  "id": "doc1",
  "title": "提取到的标题"
}
```

### 搜索

```
GET /search?q={query}

Response: 200 OK
{
  "query": "故障",
  "results": [
    {
      "id": "doc1",
      "title": "后端服务 On-Call SOP",
      "snippet": "...常见故障处理...",
      "score": 1.0
    }
  ]
}
```

### 前端页面

```
GET /

返回一个搜索页面，包含：
- 搜索输入框
- 搜索按钮
- 结果列表展示区域

前端实现不做具体要求。
```

---

## 测试数据

`data/` 目录包含 10 份部门 On-Call SOP 文档：

| 文件       | 部门             | 特殊设计                                |
| ---------- | ---------------- | --------------------------------------- |
| `doc1.html`  | 后端服务         | 正常 HTML                               |
| `doc2.html`  | 数据库           | 含 `<script>` 和 `<style>` 标签         |
| `doc3.html`  | 前端             | 含大量 HTML 实体（`&amp;` `&gt;` 等）   |
| `doc4.html`  | SRE              | 不规范 HTML（未闭合标签、属性无引号）   |
| `doc5.html`  | 安全团队         | 深层嵌套结构                            |
| `doc6.html`  | 数据平台         | 末尾有 `<script>` 标签                  |
| `doc7.html`  | 移动端           | 正常 HTML                               |
| `doc8.html`  | AI & 算法        | `<title>` 含实体编码 + `<script>` 标签  |
| `doc9.html`  | QA               | 含 `<style>` 标签                       |
| `doc10.html` | 网络 & CDN       | 含大量 `&amp;` 实体                     |

---

## Phase 1：HTML 解析 + 关键词搜索

### 要求

1. 实现 `POST /documents` 和 `GET /search` 接口
2. 实现 `GET /` 返回搜索页面
3. 解析 HTML，提取标题和纯文本
4. 对查询词进行**大小写不敏感**的精确匹配，返回包含该词的所有文档
5. score 统一为 `1.0`

### 解析规则

- 从 `<title>` 标签提取标题
- 提取纯文本内容，去除所有 HTML 标签
- `<script>` 和 `<style>` 标签内的内容**不是正文**，不应被索引
- HTML 实体（如 `&amp;` `&lt;` `&#39;`）需解码为对应字符

### 验证

启动服务后，将 `data/` 目录下的所有 HTML 文件通过 `POST /documents` 加载（id 为文件名去掉扩展名），然后验证以下查询：

| 查询                         | 期望结果                                                                     |
| ---------------------------- | ---------------------------------------------------------------------------- |
| `GET /search?q=故障`          | 返回 doc1, doc2, doc3, doc4, doc5, doc6, doc7, doc8, doc9, doc10（全部包含） |
| `GET /search?q=GPU`           | 返回 doc8（AI & 算法 SOP 中提到 GPU）                                       |
| `GET /search?q=replication`   | 返回空（doc2 的 script 中有此词，但不应被索引）                              |
| `GET /search?q=CDN`           | 返回 doc10                                                                   |
| `GET /search?q=&`             | 返回 doc3, doc6, doc8, doc10（正文解码后包含 & 字符）                        |
| `GET /search?q=on-call`       | 返回全部 10 个文档                                                           |
| `GET /search?q=notexist`      | 返回空结果                                                                   |

---

## Phase 2：倒排索引 + TF-IDF 排序

### 要求

1. 构建倒排索引（inverted index），提升搜索效率
2. 使用 TF-IDF 算法计算相关性分数，结果按 score 降序返回
3. 多关键词查询（空格分隔）取**交集**，score 为各词分数之和

### TF-IDF 公式

```
TF(t, d) = 词 t 在文档 d 中出现的次数 / 文档 d 的总词数
IDF(t)   = log(总文档数 / 包含词 t 的文档数)
score    = TF × IDF
多词查询  = Σ score(ti, d)
```

### 分词规则

- 按空白字符和标点符号分词
- 统一转为小写

### 验证

| 查询                              | 期望结果                                                                                |
| --------------------------------- | --------------------------------------------------------------------------------------- |
| `GET /search?q=告警`              | 返回多个文档，按 TF-IDF 降序排列                                                       |
| `GET /search?q=故障+响应`         | 仅返回同时包含"故障"和"响应"的文档，按总分降序                                          |
| `GET /search?q=GPU+集群`          | 仅返回 doc8（唯一同时包含两个词的文档）                                                 |
| `GET /search?q=值班+发版`         | 仅返回同时包含两个词的文档                                                              |

---

## Phase 3：语义搜索

### 要求

扩展搜索接口，增加搜索模式参数：

```
GET /search?q={query}&mode=semantic
GET /search?q={query}&mode=keyword    (默认)
```

- `mode=keyword`：行为与 Phase 2 完全一致
- `mode=semantic`：基于语义相似度搜索，查询词**不需要**在文档中精确出现
- `mode` 参数缺省时默认为 `keyword`
- 前端页面需增加搜索模式的切换功能

### 实现提示

- 需要将文档和查询转换为向量表示（embedding）
- 使用余弦相似度（cosine similarity）计算相关性
- embedding 方案自行选择（外部 API、本地模型均可）

### 验证

| 查询                                              | 期望结果                                               |
| ------------------------------------------------- | ------------------------------------------------------ |
| `GET /search?q=服务器挂了怎么办&mode=semantic`     | doc1（后端）和 doc4（SRE）应排名靠前                   |
| `GET /search?q=如何处理黑客攻击&mode=semantic`     | doc5（安全团队）和 doc10（网络 CDN）应排名靠前         |
| `GET /search?q=机器学习模型上线出问题&mode=semantic` | doc8（AI & 算法）应排名靠前                            |
| `GET /search?q=告警&mode=keyword`                  | 与 Phase 2 结果完全一致                                |

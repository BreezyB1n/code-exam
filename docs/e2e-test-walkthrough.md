# E2E 测试与走查文档

## 环境准备

1. 安装依赖并启动服务：

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

2. 确认服务就绪（应返回 `"status": "ok"` 且 `docs_loaded: 10`）：

```bash
curl http://localhost:8000/health
```

---

## Phase 1：HTML 解析 + 关键词搜索

### 1.1 前端页面

| 步骤 | 操作 | 期望结果 |
|------|------|---------|
| 打开首页 | 浏览器访问 `http://localhost:8000/` | 显示搜索框、搜索按钮、结果区域 |
| 模式选择 | 页面包含「关键词搜索」和「语义搜索」单选按钮 | 默认选中「关键词搜索」 |

### 1.2 POST /documents 接口

```bash
# 单文档上传（服务启动时已自动加载，可手动验证接口格式）
curl -s -X POST http://localhost:8000/documents \
  -H "Content-Type: application/json" \
  -d '{"id":"doc1","html":"<html><head><title>测试</title></head><body>内容</body></html>"}' | python -m json.tool
```

**期望响应（201）：**
```json
{
  "id": "doc1",
  "title": "测试"
}
```

### 1.3 GET /search 关键词验证

```bash
# 故障 → 全部 10 篇
curl -s "http://localhost:8000/search?q=故障" | python -m json.tool

# GPU → 仅 doc8
curl -s "http://localhost:8000/search?q=GPU" | python -m json.tool

# replication → 空（在 doc2 的 <script> 中，不应被索引）
curl -s "http://localhost:8000/search?q=replication" | python -m json.tool

# CDN → doc10
curl -s "http://localhost:8000/search?q=CDN" | python -m json.tool

# & （URL 编码为 %26）→ doc3, doc6, doc8, doc10
curl -s "http://localhost:8000/search?q=%26" | python -m json.tool

# on-call → 全部 10 篇
curl -s "http://localhost:8000/search?q=on-call" | python -m json.tool

# notexist → 空结果
curl -s "http://localhost:8000/search?q=notexist" | python -m json.tool
```

| 查询 | 期望 `results` 数量 / 内容 | 通过 |
|------|--------------------------|------|
| `故障` | 10 篇，score 均为正数 | ☐ |
| `GPU` | 仅 doc8 | ☐ |
| `replication` | 空 `[]` | ☐ |
| `CDN` | 包含 doc10 | ☐ |
| `&` | 包含 doc3, doc6, doc8, doc10 | ☐ |
| `on-call` | 10 篇 | ☐ |
| `notexist` | 空 `[]` | ☐ |

---

## Phase 2：倒排索引 + TF-IDF 排序

### 2.1 分数排序验证

```bash
# 告警 → 多文档，按 score 降序
curl -s "http://localhost:8000/search?q=告警" | python -m json.tool
```

走查要点：
- 返回多个文档
- 每个文档有 `score` 字段
- `score` 值从高到低排列

### 2.2 多关键词交集验证

```bash
# 故障+响应 → 同时包含两词的文档，按总分降序
curl -s "http://localhost:8000/search?q=%E6%95%85%E9%9A%9C+%E5%93%8D%E5%BA%94" | python -m json.tool

# GPU+集群 → 仅 doc8
curl -s "http://localhost:8000/search?q=GPU+%E9%9B%86%E7%BE%A4" | python -m json.tool

# 值班+发版 → 同时包含两词的文档
curl -s "http://localhost:8000/search?q=%E5%80%BC%E7%8F%AD+%E5%8F%91%E7%89%88" | python -m json.tool
```

| 查询 | 期望结果 | 通过 |
|------|---------|------|
| `告警` | 多文档，score 降序 | ☐ |
| `故障 响应` | 交集文档，score 降序 | ☐ |
| `GPU 集群` | 仅 doc8 | ☐ |
| `值班 发版` | 交集文档（可为空） | ☐ |

---

## Phase 3：语义搜索

### 3.1 health 检查语义模型已加载

```bash
curl -s http://localhost:8000/health | python -m json.tool
```

走查要点：`semantic_model.loaded` 为 `true`，`error` 为 `null`。

### 3.2 语义搜索接口验证

```bash
# 服务器挂了怎么办 → doc1(后端)、doc4(SRE) 排名靠前
curl -s "http://localhost:8000/search?q=%E6%9C%8D%E5%8A%A1%E5%99%A8%E6%8C%82%E4%BA%86%E6%80%8E%E4%B9%88%E5%8A%9E&mode=semantic" | python -m json.tool

# 如何处理黑客攻击 → doc5(安全)、doc10(网络CDN) 排名靠前
curl -s "http://localhost:8000/search?q=%E5%A6%82%E4%BD%95%E5%A4%84%E7%90%86%E9%BB%91%E5%AE%A2%E6%94%BB%E5%87%BB&mode=semantic" | python -m json.tool

# 机器学习模型上线出问题 → doc8(AI & 算法) 排名靠前
curl -s "http://localhost:8000/search?q=%E6%9C%BA%E5%99%A8%E5%AD%A6%E4%B9%A0%E6%A8%A1%E5%9E%8B%E4%B8%8A%E7%BA%BF%E5%87%BA%E9%97%AE%E9%A2%98&mode=semantic" | python -m json.tool

# 告警 mode=keyword → 结果与不加 mode 参数一致
curl -s "http://localhost:8000/search?q=告警&mode=keyword" | python -m json.tool
curl -s "http://localhost:8000/search?q=告警" | python -m json.tool
```

| 查询 | 期望 top-3 包含 | 通过 |
|------|----------------|------|
| `服务器挂了怎么办` semantic | doc1 或 doc4 | ☐ |
| `如何处理黑客攻击` semantic | doc5 或 doc10 | ☐ |
| `机器学习模型上线出问题` semantic | doc8 | ☐ |
| `告警` keyword vs 默认 | 两者结果相同 | ☐ |

### 3.3 前端语义搜索走查

| 步骤 | 操作 | 期望结果 |
|------|------|---------|
| 切换模式 | 选中「语义搜索」单选按钮 | 按钮选中状态切换 |
| 语义查询 | 输入「服务器挂了怎么办」，点击搜索 | 返回结果，doc1/doc4 靠前 |
| 切回关键词 | 切回「关键词搜索」，输入「GPU」，搜索 | 仅返回 doc8 |

### 3.4 异常参数

```bash
# 无效 mode → 400
curl -s "http://localhost:8000/search?q=foo&mode=invalid" | python -m json.tool
```

期望：`{"detail": "mode must be 'keyword' or 'semantic'"}`

---

## 走查结果汇总

| Phase | 测试项 | 通过 | 备注 |
|-------|--------|------|------|
| 1 | 前端页面可访问 | ☐ | |
| 1 | POST /documents 201 响应格式 | ☐ | |
| 1 | 故障 → 10篇 | ☐ | |
| 1 | GPU → doc8 | ☐ | |
| 1 | replication → 空 | ☐ | |
| 1 | CDN → doc10 | ☐ | |
| 1 | & → doc3/6/8/10 | ☐ | |
| 1 | on-call → 10篇 | ☐ | |
| 1 | notexist → 空 | ☐ | |
| 2 | 告警 → 多文档降序 | ☐ | |
| 2 | 故障+响应 → 交集降序 | ☐ | |
| 2 | GPU+集群 → 仅doc8 | ☐ | |
| 2 | 值班+发版 → 交集 | ☐ | |
| 3 | semantic model 已加载 | ☐ | |
| 3 | 服务器挂了怎么办 semantic | ☐ | |
| 3 | 如何处理黑客攻击 semantic | ☐ | |
| 3 | 机器学习模型上线出问题 semantic | ☐ | |
| 3 | 告警 mode=keyword 与默认一致 | ☐ | |
| 3 | 前端语义/关键词切换 | ☐ | |
| 3 | 无效 mode → 400 | ☐ | |

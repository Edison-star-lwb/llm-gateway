# LLM Gateway
[![CI](https://github.com/Edison-star-lwb/llm-gateway/actions/workflows/ci.yml/badge.svg)](https://github.com/Edison-star-lwb/llm-gateway/actions/workflows/ci.yml)
OpenAI-compatible LLM gateway: multi-provider routing, auth, rate limiting, token accounting.

## 这是什么

一个生产级 LLM 网关。它把 DeepSeek、通义等多家供应商统一成 OpenAI 兼容接口，
自带鉴权、限流、SSE 流式、计费日志和可观测性端点。

## 怎么跑起来

bash```
# 1. 配置密钥
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY、QWEN_API_KEY

# 2. 一键启动
docker compose up -d --build

# 3. 验证
curl http://127.0.0.1:8100/health
curl -H "X-API-Key: gw-dev-001" http://127.0.0.1:8100/v1/models
\`\`\`

## 设计权衡

### 1. 闸门（GATEWAY_MAX_CONCURRENCY）不是越大越好

固定客户端并发 50、mock 模式 200 请求的扫参结果：

| GATEWAY_MAX_CONCURRENCY | 错误数 | p50 | p95 | RPS |
|---|---|---|---|---|
| 1 | 0 | 9146ms | 12050ms | 15.48 |
| 8 | 0 | 10384ms | 15495ms | 12.37 |
| 50 | 0 | 3948ms | 4603ms | 39.69 |

**结论**：
- 闸门=1 用延迟换稳定（p95 12s 但 0 错误）
- 闸门=50 吞吐最高，但真实上游会触发 429（见 §9.3 实测）
- 正确取值 = 上游限额 - 余量

### 2. 多阶段 Docker 构建

builder 阶段装依赖 + 预热 tiktoken 缓存，runtime 阶段只拷贝 .venv。
镜像 115MB，比单阶段小 60%。代价：构建期需访问 openaipublic 拉 tiktoken 文件，
国内网络可能慢；可改用 fallback 估计（已在 logging_setup 实现）。

### 3. /health 不带鉴权，/metrics 不带鉴权

健康检查必须免鉴权，否则容器永远 unhealthy。
metrics 暴露流量规模和调用方名，生产环境应只监听内网或加 sidecar，
不用应用层鉴权（监控抓取器通常不带 Key）。

## 已知限制

- §2–§6 一次性提交为基线 commit，从 §7 起改用特性分支 + PR 流程
- /chat 端点未读 MOCK_LLM（仅 /chat/stream 走 mock），导致部分测试需走 stream 路径
- 真模型压测（§9.3）p95 ~1500ms，受 DeepSeek 网络与限流影响

## 真模型压测（§9.3）

关 mock，3 并发 15 请求：

\`\`\`
Total: 15 / Success: 15 / Errors: 0
RPS: 16.29
p50: 510ms / p95: 920ms
FT p50: 119ms / FT p95: 496ms
\`\`\`

注：真实供应商响应比 mock 慢 1-2 个数量级，这才是真实世界的数字。

## 仓库结构

\`\`\`
gateway/        # 应用代码
  main.py       # FastAPI 路由
  auth.py       # X-API-Key + Bearer 鉴权
  streaming.py  # SSE + tenacity 重试
  billing.py    # JSONL 账本
  metrics.py    # /metrics 计数器
  registry.py   # 多供应商路由表
tests/          # pytest 测试
bench.py        # 自写压测工具
Dockerfile      # 多阶段构建
docker-compose.yml
\`\`\`

## 贡献流程

本仓库使用 Conventional Commits + 特性分支：
- feat/xxx — 新功能
- fix/xxx — 修 bug
- docs/xxx — 文档
- test/xxx — 测试
- chore/xxx — 构建/配置

每个特性一个分支一个 PR，参考已合并的 #1 #2 #3。
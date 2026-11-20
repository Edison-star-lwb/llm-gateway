| # | 验收原话 | 用什么命令验证 | 看到什么算通过 |
|---|---|---|---|
| ① | curl 流式收到逐字输出 | `curl.exe -N -s -X POST http://127.0.0.1:8100/chat/stream -H "Content-Type: application/json" -H "X-API-Key: gw-dev-001" -d "{\"message\":\"从1数到20，每个数字一行\",\"model\":\"deepseek-chat\"}"` | 输出一行一行陆续冒出来、中间有停顿（不是啪一下全出）；每行都以 `data:` 开头；最后一行是 `data: [DONE]` |
| ② | 切模型参数后同一请求正常返回 | `curl.exe -s -X POST http://127.0.0.1:8100/chat -H "Content-Type: application/json" -H "X-API-Key: gw-dev-001" -d "{\"message\":\"用一句话说说你自己\",\"model\":\"deepseek-chat\"}"` —— 只改 model，依次换 `deepseek-reasoner` / `qwen-plus` / `qwen-turbo`，各敲一次 | 四个都是 200 且 content 非空；响应里回显的 model 就是我请求的那个（四个都回 deepseek-chat 就是错）；再敲一次 `"model":"gpt-9"` 要 400 且 detail 列出支持列表 |
| ③ | 压测 50 并发不崩 | 先 `$env:MOCK_LLM = "1"`，再 `uv run python bench.py --base-url http://127.0.0.1:8100 --key gw-dev-001 --concurrency 50 --total 200 --model deepseek-chat --stream` | 四条全中：错误数 = 0；压测同时另开终端 `curl.exe -s http://127.0.0.1:8100/health` 立刻 200；`docker compose ps` 的 STATUS 仍是 `Up ... (healthy)`，没有 Restarting / Exited；p95 在阈值内（mock 下应为几百毫秒级） |
| ④ | 陌生人照 README 能跑起来 | 流程验证：找一个没看过我代码的人，从空目录开始，只读 README，按 README 第一条命令起逐条复制执行；我全程不口头解答 | 他在 10 分钟内拿到一次真实回答；他卡住的每一个点都变成 README 里的一行字（`git log --oneline -- README.md` 能看到修改记录） |

## 端点清单
| 方法 + 路径 | 要不要 API Key | 返回什么 | 对应验收 |
|---|---|---|---|
| `GET /health` | 不要 | `{"status":"ok","version":"..."}` | §8 的 HEALTHCHECK 依赖它 |
| `POST /chat` | 要 | 一次完整 JSON | ② |
| `POST /chat/stream` | 要 | SSE，一行一个 token | ① |
| `POST /v1/chat/completions` | 要 | OpenAI 官方格式（§6 加分项） | 让任何 OpenAI 客户端能直连 |

## 请求字段
| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `message` | str | 是 | — | 用户这一轮说的话，长度限制 1–4000 字符 |
| `model` | str | 否 | 配置里的默认模型 | 取值必须是路由表里的键，否则 400 |
| `temperature` | float | 否 | 0.7 | 0–2 之间，越界要 422（Pydantic 自动帮你校验） |
| `max_tokens` | int | 否 | 512 | 1–2000，这是成本保险丝 |

## 响应字段
```
{
"request_id": "b3f1...（每次请求唯一的 32 位十六进制串）",
"model": "deepseek-chat",
"content": "模型的完整回答",
"usage": {
"prompt_tokens": 25,
"completion_tokens": 118,
"total_tokens": 143,
"source": "upstream"                                                         // upstream=上游返回的，estimated=tiltoken估的    
},
"latency_ms": 2140
}
```
## 错误码约定

| HTTP | 什么情况 | 响应体 |
|---|---|---|
|400|model不在路由表里|error，unknown_model,detal:...,supported:....|
|401|没带key，key不对|error:invalid_api_key|
|422|字段校验失败（pydantic自动|fastapi默认格式，不改
|429|上游说‘你太快了’,重启仍失败|error:upstream_rate_limited|
|502|上游5xx，连接失败|error:upstream_unavailable|
|504|上游超时|error:upstream_timeout|

## 模型路由表
| 对外 model 名 | 供应商 | 上游真实模型 | base_url 来自 |
|---|---|---|---|
| `deepseek-chat` | deepseek | `deepseek-chat` | `DEEPSEEK_BASE_URL`，默认 `https://api.deepseek.com` |
| `deepseek-reasoner` | deepseek | `deepseek-reasoner` | 同上 |
| `qwen-plus` | qwen | `qwen-plus` | `QWEN_BASE_URL`，默认 `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `qwen-turbo` | qwen | `qwen-turbo` | 同上 |

## 环境变量契约
| 变量名 | 必填 | 例子（不含密钥） | 谁读它 |
|---|---|---|---|
| `DEEPSEEK_API_KEY` | 是 | （不写值） | `registry.py` |
| `DEEPSEEK_BASE_URL` | 否 | `https://api.deepseek.com` | `registry.py` |
| `QWEN_API_KEY` | 是 | （不写值） | `registry.py` |
| `QWEN_BASE_URL` | 否 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `registry.py` |
| `GATEWAY_ALLOWED_KEYS` | 是 | `gw-dev-001:alice,gw-dev-002:bob` | `auth.py` + `billing.py` |
| `GATEWAY_DEFAULT_MODEL` | 否 | `deepseek-chat` | `config.py` |
| `GATEWAY_MAX_CONCURRENCY` | 否 | `8` | `streaming.py`（Semaphore） |
| `GATEWAY_UPSTREAM_TIMEOUT` | 否 | `30` | `registry.py` |
| `MOCK_LLM` | 否 | `0`（`1` = 不碰上游，用假流） | `registry.py` / `mock.py` |

## 模块划分
| 文件 | 只负责这一件事 | 不许碰 |
|---|---|---|
| `gateway/config.py` | 从环境变量读配置，缺必填项就明确报错说缺哪个 | 不 import openai、不碰 HTTP |
| `gateway/registry.py` | 模型路由表 + 懒加载供应商客户端工厂 | 不定义 Pydantic 模型 |
| `gateway/schemas.py` | Pydantic 请求/响应模型 | 不 import fastapi |
| `gateway/auth.py` | FastAPI 依赖：校验 Key → 返回调用方标签 | 不写业务逻辑 |
| `gateway/streaming.py` | SSE 生成器 + Semaphore + tenacity 重试 | 不直接处理 HTTP 请求对象 |
| `gateway/billing.py` | tiktoken 估算 + 账本 | 不 import fastapi |
| `gateway/logging_setup.py` | JSON 日志格式 + request_id 上下文 | — |
| `gateway/mock.py` | 假的上游（`MOCK_LLM=1` 时用） | 不许被生产代码"偷偷"调用 |
| `gateway/main.py` | FastAPI app + 路由 + 组装上面这些 | 不写业务细节，只编排 |
| `tests/` | pytest | — |
| `bench.py` | 压测脚本（§9） | — |


## SSE 输出契约（POST /chat/stream）

### 字节级规则（五条，违反任一条前端必卡）

| 规则 | 正确写法 | 错误会怎样 |
|---|---|---|
| 每个事件一行 `data: ` 开头，冒号后一个空格 | `data: {"token":"深"}` | `data:{...}` 不规范，部分客户端当未知字段丢掉 |
| 每个事件以空行结束（`\n\n`） | `data: {...}\n\n` | 只写 `\n` → 客户端一直等，看起来卡住 |
| 响应头 Content-Type | `text/event-stream; charset=utf-8` | `application/json` → EventSource 不当它是流 |
| 结尾最后一行 | `data: [DONE]\n\n` | 不发 → 前端不知道结束，转圈不停 |
| 禁止 | 在 data 行塞裸换行；一个 JSON 分两次 yield | 一个 JSON 被切成两个 data 行，客户端拼不回 |

### 事件类型（四类）

| 事件 | data 里的内容 | 什么时候发 |
|---|---|---|
| 正文 | `{"token":"一小段文字"}` | 每收到一个上游 chunk、且 content 不是 None |
| 用量 | `{"usage":{"prompt_tokens":23,"completion_tokens":17,"total_tokens":40,"source":"upstream"}}` | 收尾块带 usage 时，在 [DONE] 之前单独发一条 |
| 错误 | `{"error":"upstream_stream_interrupted","detail":"异常类名","partial_tokens":12}` | 流中途抛异常；发完这条**仍然要发 [DONE]** |
| 结束 | `[DONE]`（纯文本，不是 JSON） | 最后一条，永远发 |

### 状态码

- 模型名不认识时，`/chat/stream` 返回 **400 + 扁平 JSON**（与非流式 `/chat` 完全一致）。
  检查必须放在 `return StreamingResponse(...)` **之前**——因为状态码只有这一次机会，
  响应头一写进 socket 就再也改不了。
- 除上面这一种情况外，流式请求的 HTTP 状态码**永远是 200**，成功和失败都是。
  所以客户端**不能靠状态码判断成败**，必须检查流里有没有 `error` 事件。
  这条是「决定 2（出错不 re-raise）」的直接后果，README 和 §7 测试都要按它写。


### usage 的来源与兜底

1.发送时机：usage 单独发一条 data: {"usage":...} 事件，位置在所有 token 事件之后、[DONE] 之前；usage 事件必发，只有 source 会变（upstream / estimated / fallback）。
2.兜底：上游没给 usage 就用 tiktoken 估，标 estimated；tiktoken 本身不可用就按字符数 ×1.3 估，标 fallback。
3.我选了"不做 400 降级重试"——代价要写出来：万一以后接入一个不认 stream_options 的兼容层，会在建连接阶段就 400，客户端收到的是 error 事件 + 一个 estimated 的 usage + [DONE]，正文 0 个字，状态码还是 200。到 §6 接更多供应商时这条要重新评估。


### 一个完整响应的原始字节（示意）

​```
data: {"token": "深圳今天"}

data: {"token": "多云，"}

data: {"usage": {"prompt_tokens": 23, "completion_tokens": 17, "total_tokens": 40, "source": "upstream"}}

data: [DONE]

​```
（每两行之间那个空行就是 `\n\n`，不是排版留白）

### 与 §6 的关系：两套端点、两种格式，故意不统一

- `/chat/stream`（§4）：自定义格式，`{"token": ...}`
- `/v1/chat/completions`（§6）：OpenAI 官方 chunk 形状，`{"object":"chat.completion.chunk","delta":{...}}`

理由：前者是我发明的接口，客户端按我的契约写；后者是为了让 OpenAI SDK 零改造接进来，格式**不能自己发明**。README 里必须把这两套写清楚。

### 我的三个决定（理由自己写）

1. usage 单独发一条事件，不塞进 [DONE]，理由：放在DONE里会被Open AI静默丢弃
2. 流中途出错不 re-raise，转成 error 事件后仍发 [DONE]，理由：DONE的含义是‘不会再有内容’，这样客户端就不会一直等待
3. 正文字段名叫 `token` 不叫 `content`，理由：因为‘content’在/chat中已经被占用

## 并发闸门（asyncio.Semaphore）
1.上限来自 GATEWAY_MAX_CONCURRENCY，默认 8。
2.总并发 = 进程数 × GATEWAY_MAX_CONCURRENCY；§8 若开 workers=2，实际上限是 16 不是 8。
3.闸门包住的范围 = 调上游 + 把整条流转完；只包 create 不包流等于没限。
4.限的是"我连出去"，不是"客户端连进来"；/health 不过闸门。
5.用懒加载：模块级建会把 load_settings() 推到 import 期，配置一坏服务起不来。
6.客户端中途断开时 GeneratorExit 是 BaseException，不会被 except Exception 吞掉，async with 正常释放名额——不泄漏。

## 鉴权（X-API-Key）
1.只保护 /chat 和 /chat/stream；/health 故意不保护，因为 §8 的 Docker 健康检查不带 Key，挂了会导致容器被反复重启。
2.401 的响应体统一为 {"error":"invalid_api_key"}，不区分"没带"和"不对"——区分等于给探测者免费信息。
3.比对用 secrets.compare_digest，且在 for 循环里遍历全部 Key，避免短路比较泄露时间信息。
4.GATEWAY_ALLOWED_KEYS 缺失时返回 500 gateway_not_configured（fail-closed），不是 401。
5.只认 X-API-Key，不支持 Authorization: Bearer。代价：将来接只会发 Bearer 的客户端要改代码。
6.日志只记标签（alice/bob），Key 本身永不落日志、不进响应、不进 git。
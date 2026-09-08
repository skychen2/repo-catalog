# repo-catalog — 我的 GitHub 仓库目录

> **给 AI 看的仓库目录**:记录 skychen2 名下全部 82 个 public 仓库(自建 + fork)的基本信息与中文功能说明。
> 当主人模糊地提出一个功能需求时,AI 应通过本仓库快速检索定位到具体仓库。
> 本地另有含私有仓库的完整版(见「维护方法」)。

## 这个仓库解决什么问题

主人 star/fork 的仓库很多,时间一长会忘记"哪个仓库是干嘛的"。本仓库为每个仓库补充了
**中文功能说明** 和 **中文检索关键词**,让 AI 能通过语义/关键词模糊匹配,快速找到"实现某功能的仓库"。

## 文件结构

| 文件 | 内容 |
|---|---|
| `INDEX.md` | 全量一行式索引(仓库/分类/一句话/属性) |
| `categories/*.md` | 按主题分类的仓库清单,含详细中文说明与关键词 |
| `data/repos.json` | 机器可读的完整元数据(名称/URL/语言/星标/中文说明/关键词/分类) |
| `scripts/curated.json` | 人工维护的中文说明与关键词(唯一需要手工编辑的文件) |
| `scripts/curated.private.json` | 私有仓库的中文说明(本地文件,已被 gitignore,不进入公开仓库;配合 generate.py 生成本地完整版) |
| `scripts/generate.py` | 生成器:合并 GitHub 元数据 + curated 说明,重新生成所有文件 |

## 分类

- `ai-llm` — AI / 大模型 / 提示词(模型、微调、Agent 框架、prompt 工程、AI 接口)
- `network-proxy` — 代理 / 科学上网 / Cloudflare(机场、订阅、VLESS/Trojan、VPS)
- `media` — 视频 / AI 绘画 / 媒体(视频生成剪辑、超分插帧、绘画、下载)
- `content-writing` — 内容创作 / 写作 / 运营(公众号、小红书、网文、内容工厂)
- `dev-data-tools` — 开发工具 / 效率 / 数据集(工具、安全、API、自建小服务)
- `knowledge-books` — 知识 / 教程 / 资料(学习路线、书籍、语料、合集)
- `personal-projects` — 个人自建项目(自建 / 私有,含个人知识库)

## 给 AI 的检索流程

当主人提出模糊需求时,按此流程检索:

1. **解析需求**,提取 2-4 个核心意图词(中英文均可)。
2. 优先 **全文搜索 `categories/` 目录** 和 `INDEX.md`,命中说明或关键词。
3. 需要结构化数据时,直接读取 `data/repos.json` 并用脚本过滤(字段:name, category, cn, keywords, language, isFork, visibility, stars)。
4. 命中后,把仓库名、URL、分类和一句话说明回复给主人;如有多个候选,按相关度排序并说明各自差异。
5. 若未命中,明确告知"目录里没有",不要编造。

**查询示例**(主人可能这样问 → AI 的检索目标):

- "我要批量生成短视频" → `MoneyPrinterTurbo`、`short-video-factory`
- "视频画质太差想放大补帧" → `video2x`
- "给 AI 模型做微调" → `unsloth`、`self-llm`
- "免费搞个 ChatGPT 网页版" → `lobe-chat`、`Google-Gemini-Web`
- "机场订阅怎么聚合" → `CF-Workers-SUB`、`edgetunnel`
- "微信读书笔记同步到 Notion" → `weread2notion-pro`
- "找免费公开 API" → `public-apis`、`awesome-public-datasets`
- "微信聊天记录搜索/情报工具" → `wechat-intelligence-hub`
- "AI 新闻摘要聚合工具" → `clawfeed`
- "公众号排版工具" → `md`

## 维护方法

```bash
# 1. 修改 scripts/curated.json,补全新仓库的中文说明与关键词
# 2. 重新生成(自动拉取最新 GitHub 元数据):
python3 scripts/generate.py --public   # 公开仓库版本(提交用)
python3 scripts/generate.py             # 本地完整版(含私有仓库,不提交)
# 3. 提交推送
cd .. && git add -A && git commit -m "update catalog" && git push
```

注意:
- `curated.json` 里 `_comment` 字段说明字段含义与 category 取值,新增仓库时照抄已有条目格式即可。
- 仓库描述/星标等元数据每次生成时自动从 GitHub 刷新,无需手工维护。
- fork 仓库的功能说明以上游项目为准,标注"fork"表示非自建。

# repo-catalog — 我的 GitHub 仓库目录

> **给 AI 看的仓库目录**:记录 skychen2 名下全部 84 个 public 仓库 + 268 个外部收藏仓库的基本信息与中文功能说明。
> 当主人模糊地提出一个功能需求时,AI 应通过本仓库快速检索定位到具体仓库。
> 本地另有含私有仓库的完整版(见「维护方法」)。

## 这个仓库解决什么问题

主人 star/fork 的仓库很多,时间一长会忘记"哪个仓库是干嘛的"。本仓库为每个仓库(含 star 收藏)补充了
**中文功能说明** 和 **中文检索关键词**,让 AI 能通过语义/关键词模糊匹配,快速找到"实现某功能的仓库"。star 收藏已批量收录(外部收藏 🌐)。

## 设计原则(维护者必读)

本库**只服务 AI 检索**——唯一标准是 AI 能搜索定位到仓库。因此:

- 产物只有两种形态:`data/repos.json`(机器可读,程序化过滤)+ `categories/*.md`(中文说明+关键词,语义全文搜索)。
- 不生成人类阅读用的冗余视图(如 INDEX 式全量一行索引)。
- `curated.json` 的中文说明与关键词是检索质量核心:新增仓库必须写准中文说明。
- 任何产物变更,必须同时同步两个形态:文件形态(公开 GitHub)+ KB 形态(本地 context-mode)。

## 文件结构

| 文件 | 内容 |
|---|---|
| `categories/*.md` | 按主题分类的仓库清单,含详细中文说明与关键词 |
| `data/repos.json` | 机器可读的完整元数据(名称/URL/语言/星标/中文说明/关键词/分类) |
| `README.md` | 本说明(设计原则、检索流程与维护方法) |
| `scripts/curated.json` | 人工维护的中文说明、关键词和项目关系 |
| `scripts/group_notes.json` | 功能组的场景说明与组内项目差异 |
| `scripts/curated.private.json` | 私有仓库的中文说明(本地文件,已被 gitignore,不进入公开仓库;配合 generate.py 生成本地完整版) |
| `scripts/generate.py` | 生成器:合并 GitHub 元数据 + curated 说明,重新生成 categories/ 与 data/repos.json |
| `scripts/add_repo.py` | 通过链接/owner-name 新增仓库(校验 + 写入 curated + 自动补 fork 来源) |
| `scripts/build_full_md.py` | 生成本地完整版目录 Markdown(含私有),供索引进 context-mode 知识库 |
| `scripts/fetch_public_repos.py` | 拉取名下公开仓库元数据(CI 用,匿名/带 token 均可) |
| `scripts/fetch_starred_repos.py` | 发现当前账号 star 的第三方仓库并加入外部收藏 |
| `scripts/refresh_external_repos.py` | 刷新外部收藏的 GitHub 状态、更新时间和基础元数据 |
| `scripts/audit.py` | 检查未审核、长期未更新、已归档、不可访问和重复候选仓库 |
| `scripts/recommend.py` | 按功能匹配度优先,结合优先级、活跃度和热度输出推荐排序 |
| `tests/recommend_cases.json` | 典型模糊需求与期望第一推荐项目 |
| `tests/test_recommend.py` | 推荐结果回归测试 |
| `.github/workflows/refresh.yml` | GitHub Actions:每周一自动刷新元数据并提交 |

## 分类

- `ai-llm-models` — AI 模型 / 微调 / 部署(本地运行、微调训练、模型清单)
- `ai-llm-prompts` — 提示词 / 越狱 / 技巧(prompt 合集、结构化提示词、系统提示词)
- `ai-llm-agents` — Agent / 自动化 / 工具调用(Agent 框架、function calling、自动操作)
- `ai-llm-api` — AI 接口 / 代理 / 自部署 UI(免费/中转 API、接口兼容代理)
- `ai-llm-tutorials` — LLM 教程 / 学习资源(入门课程、源码解析、资源清单)
- `network-proxy` — 代理 / 科学上网 / Cloudflare(机场、订阅、VLESS/Trojan、VPS)
- `media` — 视频 / AI 绘画 / 媒体(视频生成剪辑、超分插帧、绘画、下载)
- `content-writing` — 内容创作 / 写作 / 运营(公众号、小红书、网文、内容工厂)
- `dev-data-tools` — 开发工具 / 效率 / 数据集(工具、安全、API、自建小服务)
- `knowledge-books` — 知识 / 教程 / 资料(学习路线、书籍、语料、合集)
- `personal-projects` — 个人自建项目(自建 / 私有,含个人知识库)

当主人提出模糊需求时,优先使用推荐脚本:

```bash
python3 scripts/recommend.py "批量生成短视频"
python3 scripts/recommend.py "终端 AI 编程助手" --top 3
```

用固定需求样例检查排序是否回归:

```bash
python3 -m unittest discover -s tests -v
```

推荐排序固定为:功能需求匹配度 > `primary`/`alternative`/`reference` 优先级 > GitHub 活跃度 > GitHub 热度。功能匹配度不接近时,后面的指标不应改变结果。



1. **解析需求**,提取 2-4 个核心意图词(中英文均可)。
2. 优先 **全文搜索 `categories/` 目录**,命中说明或关键词。
3. 需要结构化数据时,直接读取 `data/repos.json` 并用脚本过滤(字段:name, category, cn, keywords, language, isFork, forkedFrom, external, visibility, stars)。
4. 命中后,把仓库名、URL、分类和一句话说明回复给主人;如有多个候选,按相关度排序并说明各自差异。
5. 若未命中,明确告知"目录里没有",不要编造。

**查询示例**(主人可能这样问 → AI 的检索目标):

- "我要批量生成短视频" → `MoneyPrinterTurbo`、`short-video-factory`
- "视频画质太差想放大补帧" → `video2x`
- "给 AI 模型做微调" → `unsloth`、`self-llm`
- "免费搞个 ChatGPT 网页版" → 自部署 UI 类仓库(本地完整版含 lobe-chat 等私有部署)
- "机场订阅怎么聚合" → `CF-Workers-SUB`、`edgetunnel`
- "微信读书笔记同步到 Notion" → `weread2notion-pro`
- "找免费公开 API" → `public-apis`、`awesome-public-datasets`
- "微信聊天记录搜索/情报工具" → `wechat-intelligence-hub`
- "AI 新闻摘要聚合工具" → `clawfeed`
- "公众号排版工具" → `md`

## 新增仓库(两种入口)

**入口 A — 与 AI 对话发链接(推荐)**:主人直接把 GitHub 链接发给 AI,AI 执行:

```bash
# 1. 校验仓库 + 写入中文说明与关键词:
python3 scripts/add_repo.py <https://github.com/owner/repo 或 owner/repo> \
    --cn "中文功能说明" --kw "关键词,逗号分隔" --cat 分类key
# 2. 重新生成 + 推送:
python3 scripts/generate.py --public && git add -A && git commit -m "add repo" && git push
# 3. 重建本地完整版并索引进 KB:
python3 scripts/build_full_md.py
#    然后 AI 用 ctx_index 把 /tmp/repo-catalog-full.md 重新索引进知识库(同 source 覆盖,无重复)
```

说明:AI 需要先判断该仓库的用途(阅读 README),写准中文说明与关键词;fork 仓库会自动补上游来源。
任意 GitHub 仓库均可添加:
- **名下仓库**(自建或 fork)→ 正常收录;
- **第三方仓库** → 自动标记为「外部收藏 🌐」,公开版与本地完整版均收录
  (data/repos.json 中 `external: true`;元数据可通过 `refresh_external_repos.py` 定期刷新)。

**入口 B — 发现后点 star/fork**:fork 仓库进入 skychen2 名下仓库列表;star 的第三方仓库由
`fetch_starred_repos.py` 读取当前账号的 Star 列表。GitHub Actions 每周一自动刷新并加入公开目录,
缺中文说明时会先用上游描述占位(标注「待补充中文说明」),之后用入口 A 的 add_repo.py 补说明即可。

> ⚠ 注意:star 的仓库属于原作者,不会出现在名下仓库列表。GitHub Actions 会通过
> `fetch_starred_repos.py` 定期读取当前账号的 star 列表,自动加入外部收藏;本地可使用已登录的 `gh`,
> CI 需要配置 `STARRED_REPOS_TOKEN` secret(令牌需有权读取用户 starred repositories)。取消 star 不会自动删除已整理条目。

## 生命周期与重复项目

`curated.json` 保留中文说明和人工判断,生成后的 `data/repos.json` 还会包含以下字段:

- `status`: `unreviewed`、`active`、`watch`、`archived`、`obsolete`、`replaced`
- `priority`: `unclassified`、`primary`、`alternative`、`reference`
- `lastReviewedAt`: 人工审核和排序判断日期
- `duplicateGroup` / `alternatives` / `replacement`: 同类项目关系
- `pushedAt` / `archived` / `disabled`: GitHub 自动元数据

旧条目默认是 `unreviewed` 和 `unclassified`,不代表项目已经过时。先刷新元数据,再根据审计清单人工判断:

```bash
python3 scripts/refresh_external_repos.py
python3 scripts/generate.py --public
python3 scripts/audit.py
```

`data/review-needed.json` 是待处理清单,其中 `duplicateCandidates` 会列出已建组、相同 URL、相同上游、同分类关键词高度重叠的功能候选,以及仍未归组的 `unassignedFunctional`。功能候选只用于人工确认,审计不会自动删除或合并仓库,也不会覆盖人工字段。

## 维护方法

```bash
# 1. 修改 scripts/curated.json,补全新仓库的中文说明与关键词
# 2. 重新生成(自动拉取最新 GitHub 元数据):
python3 scripts/generate.py --public   # 公开仓库版本(提交用)
python3 scripts/generate.py             # 本地完整版(含私有仓库,不提交)
# 3. 发现 Star 外部仓库(本地已登录 gh 或设置 STARRED_REPOS_TOKEN)
python3 scripts/fetch_starred_repos.py
# 4. 刷新外部收藏元数据
python3 scripts/refresh_external_repos.py
# 5. 重新生成公开版并审计
python3 scripts/generate.py --public
python3 scripts/audit.py
# 6. 提交推送
git add -A && git commit -m "update catalog" && git push
```

自动刷新:GitHub Actions 每周一自动重跑 `fetch_public_repos.py` + `fetch_starred_repos.py` +
`refresh_external_repos.py` + `generate.py --public`,元数据(描述/星标/新仓库)无需人工维护;
`curated.json` 的中文说明新增仓库时仍需手工补一条。


## 数据验证与调试

```bash
# 验证数据完整性（检查 curated/repos/categories 一致性）
python3 scripts/validate.py

# 本地测试 add_repo.py（无实际写入）
# 先 fork 一个测试仓库，然后测试解析和 API 调用
python3 scripts/add_repo.py owner/repo --cn "测试" --kw "test" --cat dev-data-tools --dry-run  # （当前未实现 --dry-run，直接运行会写入 curated.json）

# 比对生成前后的差异
cp data/repos.json /tmp/repos-old.json
python3 scripts/generate.py --public
diff -u /tmp/repos-old.json data/repos.json | head -50

# CI 失败时的调试步骤
# 1. 检查 GitHub Actions 日志，确认失败的具体步骤
# 2. 本地复现：
python3 scripts/fetch_public_repos.py /tmp/repos.json
python3 scripts/generate.py --public /tmp/repos.json
python3 scripts/validate.py
# 3. 检查 curated.json 语法（JSON 格式错误、缺失必须字段）
python3 -m json.tool scripts/curated.json > /dev/null && echo "JSON 格式正确" || echo "JSON 语法错误"
```

注意:
- `curated.json` 里 `_comment` 字段说明字段含义与 category 取值,新增仓库时照抄已有条目格式即可。
- fork 仓库会自动在说明前标注 `fork 自 <上游>`,来源固化在 curated 条目的 `forkedFrom` 字段(可用 `gh api repos/skychen2/<name> --jq '.parent.full_name'` 查询补全)。
- 仓库描述/星标等元数据每次生成时自动从 GitHub 刷新,无需手工维护。
- 被 GitHub 封禁/删除的仓库(如 n8n-workflows,DMCA)也会收录并标注状态,检索时如实说明。
- 维护完整版(含私有仓库)时注意:公开版产物(categories/data)不得出现私有仓库名。

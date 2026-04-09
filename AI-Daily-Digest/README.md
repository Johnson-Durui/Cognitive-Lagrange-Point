# AI-Daily-Digest

一个面向个人使用的 AI 前沿雷达项目：

- 每天抓取 GitHub AI 新项目与 Trending
- 每天抓取 arXiv 顶级 AI 论文
- 用 Grok / OpenAI 兼容接口生成中文摘要与相关性评分
- 通过企业微信机器人 Webhook 或 PushPlus 发送日报
- 生成一个可搜索、可筛选、可查看近 30 天历史的静态网站

## 快速开始

1. 复制环境变量模板：

```bash
cp .env.example .env.local
```

2. 安装依赖：

```bash
python3 -m pip install -r requirements.txt
```

3. 运行一次本地生成：

```bash
python3 main.py --config config.yaml
```

4. 查看输出：

- 日报 Markdown：`data/digests/<日期>.md`
- 日报 JSON：`data/digests/<日期>.json`
- 站点目录：`site/`

## 环境变量

- `GROK_API_KEY`: Grok / xAI API Key
- `GITHUB_TOKEN`: GitHub API Token
- `WECOM_WEBHOOK_URL`: 企业微信机器人 Webhook
- `PUSHPLUS_TOKEN`: PushPlus Token，可选

## 部署方式

- GitHub Actions 每天定时运行
- Workflow 会更新 `history.json` 和 `data/` 里的历史数据
- Workflow 会把 `site/` 上传到 GitHub Pages

## 目录说明

- `main.py`: 主流程入口
- `fetchers/`: GitHub 与 arXiv 数据抓取
- `summarizer.py`: LLM 摘要与评分
- `notifier.py`: 企业微信 / PushPlus 通知
- `templates/`: Markdown 与 HTML 模板
- `static/`: 前端搜索、筛选、收藏、已读逻辑
- `tests/`: 基础 smoke 测试


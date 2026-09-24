# Valibra GitHub Pages

独立的研究展示站点。中文按用户要求从 Notion 原文迁移，不再使用删减摘要；俄语页暂时保留上一版摘要。两者目前不是内容完全对应的翻译版本，也不自动同步 Notion。

网站：<https://tiancigao.github.io/Valibra-site/> · [Русский](https://tiancigao.github.io/Valibra-site/ru/)

本仓库包含网站源码、用户要求公开的中文报告正文和页面图片，以及既有俄语摘要与汇总材料。与私有研究仓库独立，没有导入其 Git 历史、Agent 实现代码或运行环境。

## 内容边界

- `site/content/zh.notion.md`：中文 Notion 原文快照（2026-09-24 读取），正文、案例、SQL、模型响应及状态记录按原文保留；只将图片地址本地化、附件内部引用换成对应 Notion 入口。
- `site/content/zh.notion.json`：来源与对象映射。保留首次读取时的 `truncated=true` 记录；当时的 1 个未知嵌入对象已由作者确认为私有项目仓库 `TianciGao/Valibra`，2 个 Excel 附件已从作者桌面原样补齐。原文快照未改写，渲染时在原位置接入链接与下载入口。
- `site/downloads/`：仅含作者指定的基线和我们方法的两份 Full600 Excel。构建校验文件大小和 SHA-256，保证原样发布。我们方法表内 Total Tokens 为旧汇总口径，未含独立 Grounding 用量；下载入口已注明，完整用量见正文。
- `scripts/notion_report.py`：转换标题、彩色文字、提示框、表格、嵌套折叠和代码块，不调用模型重写内容。
- `site/content/ru.html`：此前俄语摘要，本次未改写或重新翻译。
- `site/assets/notion-zh-*`：从本次中文 Notion 页下载的 5 张原图，没有重新绘制或翻译；CSS、JavaScript 均本地提供。
- 核心结果来源：`site/data/core_results.json`，摘自 2026-09-16 版本汇总。
- 只公开该页面正文已包含的材料及作者指定的上述两份结果表；不根据其中的文件路径递归复制私有仓库、完整日志目录、数据集、数据库或其他附件包。路径文字仅是原文引用。
- 不保存或发布凭据、Notion Token、图片签名下载参数。
- Notion 保持编辑母版。以后重新读取并核对差异，再手工更新网站；本次没有修改 Notion 页面。

## 本地构建与检查

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements-site.txt
python3 scripts/build_pages.py
python3 -m unittest discover -s tests/pages -v
python3 -m http.server 8080 --directory dist/pages
```

打开 `http://localhost:8080/`。构建使用 Python 3.12 和固定版本的 Markdown 渲染依赖。输出为静态 HTML，关闭 JavaScript 后正文、语言切换和折叠案例仍可用。测试逐项核对 1,164 个文字单元、116 段代码、50 个折叠块、18 张表格和 5 张图片。

## 发布

`.github/workflows/pages.yml` 只上传 `dist/pages`，不上传仓库根目录。
在 GitHub Settings → Pages 中选择 **GitHub Actions**；只有本仓库的 `main` 分支部署。
推送相关文件或手工运行工作流后发布到 `https://tiancigao.github.io/Valibra-site/`。
Pull Request 只构建测试，不部署。原 `Valibra` 代码仓库继续保持私有。

## 更新规则

1. 中文更新以 Notion 当前原文为准，更新 `site/content/zh.notion.md` 并核对差异；不要让摘要生成器覆盖正文。源快照 SHA 测试需要在复核后同步更新。
2. 中文所有数据表保留 Notion 原文，不用 JSON 重新计算或替换。`core_results.json` 仍供既有俄语摘要使用。
3. 运行测试，检查桌面和移动端预览，并审查发布目录中每一个文件。
4. 仅提交本次审阅过的文件。不要复制整个 `baseline/` 或 `research-runtime/` 到站点。

中文页图文以 Notion 为准；图 1 为 `notion-zh-1.svg`，图 2–5 为原始 PNG。俄语摘要图仍为 `framework-ru.svg`。中文 SVG 可以编辑文字，但改变后应同时核对 Notion 母版；PNG 内文字不能像正文一样直接编辑。

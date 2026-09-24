# Valibra GitHub Pages

独立的研究展示站点。中文按用户要求从 Notion 原文迁移，俄语为对应全文译版，两种语言保留相同的章节、案例、表格和折叠结构，均不使用删减摘要，也不自动同步 Notion。

网站：<https://tiancigao.github.io/Valibra-site/> · [Русский](https://tiancigao.github.io/Valibra-site/ru/)

本仓库包含网站源码、用户要求公开的中俄报告正文、页面图片、两份原始结果表及汇总材料。与私有研究仓库独立，没有导入其 Git 历史、Agent 实现代码或运行环境。

## 内容边界

- `site/content/zh.notion.md`：中文 Notion 原文快照（2026-09-24 读取），正文、案例、SQL、模型响应及状态记录按原文保留；只将图片地址本地化、附件内部引用换成对应 Notion 入口。
- `site/content/zh.notion.json`：来源与对象映射。保留首次读取时的 `truncated=true` 记录；当时的 1 个未知嵌入对象已由作者确认为私有项目仓库 `TianciGao/Valibra`，2 个 Excel 附件已从作者桌面原样补齐。原文快照未改写，渲染时在原位置接入链接与下载入口。
- `site/downloads/`：仅含作者指定的基线和我们方法的两份 Full600 Excel。构建校验文件大小和 SHA-256，保证原样发布。我们方法表内 Total Tokens 为旧汇总口径，未含独立 Grounding 用量；下载入口已注明，完整用量见正文。
- `scripts/notion_report.py`：转换标题、彩色文字、提示框、表格、嵌套折叠和代码块，不调用模型重写内容。
- `site/content/ru.notion.md`：逐项对应中文的俄语全文；`ru.notion.json` 记录对齐的中文 SHA、图片来源及翻译边界。116 段代码中 113 段逐字保留，2 段仅翻译中文注释，1 段翻译中文 System Prompt，其后执行上下文原样保留。所有 SQL、JSON 字段名及数值不变。
- `site/content/ru.html`：历史俄语摘要，留存备查，不再用于构建或发布。
- `site/assets/notion-zh-*`：从本次中文 Notion 页下载的 5 张原图，没有重新绘制或翻译；CSS、JavaScript 均本地提供。
- `site/assets/notion-ru-*`：与上述 5 张图片对应的俄语 SVG，翻译说明文字，保留技术标识和数值；其中图 2 内嵌经过 SHA 核对的原始截图并覆盖翻译其标题，不加载任何外部资源。俄语图是阅读译版，不替代原始审计记录。两份 Excel 下载均保持原始文件（包括中文表签），不改动原始统计数据。
- 核心结果来源：`site/data/core_results.json`，摘自 2026-09-16 版本汇总。
- 只公开该页面正文已包含的材料及作者指定的上述两份结果表；不根据其中的文件路径递归复制私有仓库、完整日志目录、数据集、数据库或其他附件包。路径文字仅是原文引用。
- 不保存或发布凭据、Notion Token、图片签名下载参数。
- Notion 保持编辑母版。以后重新读取并核对差异，再手工更新网站；本次没有修改 Notion 页面。

公开页面不显示迁移／翻译说明、读取日期、同步提示、页脚来源说明或 Notion 链接；标题下重复的源页面入口也不显示。原始快照和来源记录仅留在仓库中供维护复核，正文、章节导航、语言切换和结果下载不受影响。

## 本地构建与检查

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements-site.txt
python3 scripts/build_pages.py
python3 -m unittest discover -s tests/pages -v
python3 -m http.server 8080 --directory dist/pages
```

打开 `http://localhost:8080/` 或 `/ru/`。构建使用 Python 3.12 和固定版本的 Markdown 渲染依赖。输出为静态 HTML，关闭 JavaScript 后正文、语言切换和折叠案例仍可用。每种语言均有 1,163 个文字单元、116 段代码、50 个折叠块、18 张表格和 5 张图片；测试核对结构、数值、代码翻译边界、下载文件及来源 SHA。发布目录严格限定为 22 个文件。

## 发布

`.github/workflows/pages.yml` 只上传 `dist/pages`，不上传仓库根目录。
在 GitHub Settings → Pages 中选择 **GitHub Actions**；只有本仓库的 `main` 分支部署。
推送相关文件或手工运行工作流后发布到 `https://tiancigao.github.io/Valibra-site/`。
Pull Request 只构建测试，不部署。原 `Valibra` 代码仓库继续保持私有。

## 更新规则

1. 中文更新以 Notion 当前原文为准，更新 `site/content/zh.notion.md` 并核对差异；不要让摘要生成器覆盖正文。源快照 SHA 测试需要在复核后同步更新。
2. 中文所有数据表保留 Notion 原文，不用 JSON 重新计算或替换。俄语逐项对应中文，不使用摘要模板；修改中文、对象映射或原图后，必须复核俄语并同步 `ru.notion.json` 的来源 SHA，否则构建会拒绝发布过时译文。`core_results.json` 只作为独立汇总附件保留。
3. 运行测试，检查桌面和移动端预览，并审查发布目录中每一个文件。
4. 仅提交本次审阅过的文件。不要复制整个 `baseline/` 或 `research-runtime/` 到站点。

中文页图文以 Notion 为准；图 1 为 `notion-zh-1.svg`，图 2–5 为原始 PNG；俄语图为 `notion-ru-1.svg` 至 `notion-ru-5.svg`。SVG 译文可以编辑文字，改动后需核对中文原图。此前的摘要素材仍归档在仓库中，不用于当前正文。

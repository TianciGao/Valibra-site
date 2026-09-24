# Valibra GitHub Pages

独立的中俄双语研究展示站点。沿用 Notion 的章节与折叠组织方式，但不是 Notion 的完整副本或自动同步镜像。

网站：<https://tiancigao.github.io/Valibra-site/> · [Русский](https://tiancigao.github.io/Valibra-site/ru/)

本仓库仅包含网站源码及公开汇总材料，与私有研究仓库独立，没有导入其 Git 历史、Agent 代码或运行环境。

## 内容边界

- `site/content/zh.html`、`site/content/ru.html`：公开正文，仅有框架说明、匿名化案例过程与汇总结果。
- `site/assets/`：本地 CSS、JavaScript、框架 SVG；不依赖 Notion 临时链接或第三方 CDN。
- 核心结果来源：`site/data/core_results.json`，摘自 2026-09-16 版本汇总。
- 不发布 Notion 内部地址、原始 Prompt / 模型输出、逐题 SQL、参考答案、完整日志、数据集、数据库或凭据。
- Notion 保持编辑母版。发布时手工更新两种语言，审阅差异后再推送；本站不持有 Notion Token。

## 本地构建与检查

```bash
python3 scripts/build_pages.py
python3 -m unittest discover -s tests/pages -v
python3 -m http.server 8080 --directory dist/pages
```

打开 `http://localhost:8080/`。构建使用 Python 3.12 标准库；输出为静态 HTML，关闭 JavaScript 后正文、语言切换和折叠案例仍可用。

## 发布

`.github/workflows/pages.yml` 只上传 `dist/pages`，不上传仓库根目录。
在 GitHub Settings → Pages 中选择 **GitHub Actions**；只有本仓库的 `main` 分支部署。
推送相关文件或手工运行工作流后发布到 `https://tiancigao.github.io/Valibra-site/`。
Pull Request 只构建测试，不部署。原 `Valibra` 代码仓库继续保持私有。

## 更新规则

1. 修改 `site/content/` 中两种语言对应章节。
2. 汇总数据变更时先更新版本文档，再更新网站叙述；构建会从 JSON 生成成绩表和指标。
3. 运行测试，检查桌面和移动端预览，并审查发布目录中每一个文件。
4. 仅提交本次审阅过的文件。不要复制整个 `baseline/` 或 `research-runtime/` 到站点。

图中文字：编辑 `site/assets/framework-zh.svg` / `framework-ru.svg` 中的 `<text>` 内容。文字较长时需要同步调整位置或换行；两种语言分别维护。

# PPT HTML 规范

仅在用户有汇报需要或明确请求 PPT、执行阶段 6.2 生成幻灯片时读取；本产物不阻塞核心 PRD 或 Design/TDD。`output/ppt.md` 是页面内容来源，按 `P1, P2…` 解析；输出 `output/ppt/p{i:02d}.html`（p01.html、p02.html…），交付大纲声明的全部 N 页。

## 共享视觉契约

Controller 基于 PRD 生成一次共用 `:root` 变量块（颜色 4–6、字体 1–2、圆角、间距）与简短排版基调。各页原样复制该块，颜色全文用 `var(--xxx)` 引用，`:root` 外禁止硬编码颜色，不各自另建视觉系统。

PPT 不依赖 `DESIGN.md` 或 `tokens.css`，不得向用户索要设计文件。产品设计完成后可按用户需要重出以对齐品牌。

## 内容与表现

- 保留大纲的事实、数值和结论方向；允许删重复、压缩措辞、重组视觉层级，不增加新观点。
- 每页一个清晰结论和必要证据，可见叙述正文不超过 300 字（表格数据、图表标签、数字不计）。内容少就留白；多则优先转为图表、对比或流程，不用小字硬塞。
- 一页一个视觉重心，按内容选极简、分栏、流程、矩阵、数据或表格布局；不强行分栏、铺满卡片或全套同一模板。
- 仅呈现最终静态画面，用于展示、截图或导出 PDF。禁止 `transition`、`animation`、装饰性交互及 hover 效果；全屏适配与翻页脚本除外。
- 每页以主色、语义辅助色和中性灰保持层级，不用大面积高饱和背景。线性图标只辅助标题、结论或核心数据，不作填空装饰。

## 画布、字体与全屏适配

- 全套画布宽度固定 1920px，`min-height: 1080px`，以 16:9 一屏完整呈现为基准。只有不可压缩的核心证据才向下延展；不得截断主要信息或使用卡片内滚动条。
- 1920px 基准字号：标题 64–72px，主结论 36–48px，副标题 30–36px，正文 22–24px（下限 22px），标签 14–16px；注意行距、行长与层级。
- 每页采用以下适配骨架，按视口宽度等比缩放，避免固定画布溢出或横向滚动。导航和全部内容都放入 `.stage`：

```html
<style>
  html, body { margin: 0; padding: 0; }
  .stage { width: 1920px; min-height: 1080px; transform-origin: top left; }
</style>
<body>
  <div class="stage">
    <!-- 当前页面内容与导航 -->
  </div>
  <script>
    function fit() {
      var s = innerWidth / 1920;
      var stage = document.querySelector('.stage');
      stage.style.transform = 'scale(' + s + ')';
      document.body.style.height = (stage.offsetHeight * s) + 'px';
    }
    addEventListener('resize', fit); fit();
  </script>
</body>
```

导航用普通文档流或 `absolute`，不用 `fixed`（`.stage` 的 transform 会改变其定位参照）。长页整页纵向滚动；不给 transform 加 transition。若需原始 1920px 截图，可临时移除 transform 后截 `.stage`；视口截图是当前窗口的缩放画面。

## 导航与交付

每页显示 `{当前页} / {总页数}`，提供上一页/下一页链接和键盘方向键翻页。链接使用两位数文件名，首尾闭合，保证 p01↔pNN 可达。

全部页面生成后统一检查一次：每页有相同 `:root`、块外无硬编码 Hex、`.stage` 适配存在、导航闭合。发现问题只修受影响页面；文件未齐不得报告完成。直接交付保存的 HTML。

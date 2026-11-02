# CI 门禁与仓库设置

> 本文件供生成 CI 或仓库设置指引时按章节读取：CI 只读检测规则和所用技术栈的模板，分支保护读第二节，标签与 Stale Bot 按需读第三、四节。远端操作按主入口约定的授权范围执行。

---

## 一、CI workflow 检测生成规则（检测优先，识别不了就跳过）

### 检测决策表

以下 workflow 与 gh 命令用于 GitHub。其他平台沿用其已有 CI 和设置方式，不把 GitHub Actions 文件当作已启用的流水线。命令和版本是模板示例，生成时以项目已有配置、锁文件、实际默认分支和测试命令为准。

| 检测信号（文件） | 技术栈 | 包管理器判断 | 生成命令 |
| :--- | :--- | :--- | :--- |
| `package.json` | Node | `package-lock.json`→npm / `pnpm-lock.yaml`→pnpm / `yarn.lock`→yarn | `npm ci && npm test` |
| `requirements.txt` / `pyproject.toml` | Python | — | `pytest` |
| `go.mod` | Go | — | `go test ./...` |
| `pom.xml` | Java (Maven) | — | `mvn -B test` |
| `build.gradle` / `build.gradle.kts` | Java (Gradle) | — | `./gradlew test` |
| `Cargo.toml` | Rust | — | `cargo test` |
| `composer.json` | PHP | — | `composer install && composer test` |
| **以上都没有 / 没有测试脚本** | **识别不了** | — | **跳过 ci.yml，只在设置指引里写"怎么配 CI"** |

> 额外校验：Node 项目若 `package.json` 没有 `scripts.test`，或 test 脚本是占位（如 `echo no test`）→ 标记"无真实测试"，跳过 CI 生成并在汇报里提示"先加测试再开 CI"。

### 模板 1 · Node（npm）

文件 `.github/workflows/ci.yml`：

```yaml
name: CI
on:
  pull_request:
    branches: [ main ]
  push:
    branches: [ main ]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: npm
      - run: npm ci
      - run: npm test
```

> pnpm 版：先安装项目声明版本的 pnpm，再让 setup-node 启用 `cache: pnpm`；缓存步骤会调用 pnpm，不能等到它之后才安装。按[官方缓存示例](https://github.com/actions/setup-node/blob/main/docs/advanced-usage.md#caching-packages-data)替换 Node 模板中的 steps：

```yaml
steps:
  - uses: actions/checkout@v4
  - uses: pnpm/action-setup@v6
    with:
      version: 10 # 示例；使用 package.json 的 packageManager 或项目已确认版本
  - uses: actions/setup-node@v4
    with:
      node-version: 20 # 示例；与项目版本一致
      cache: pnpm
  - run: pnpm install --frozen-lockfile
  - run: pnpm test
```

> yarn 版：`cache: yarn`，`yarn install --frozen-lockfile` + `yarn test`。

### 模板 2 · Python

```yaml
name: CI
on:
  pull_request:
    branches: [ main ]
  push:
    branches: [ main ]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pip install pytest
      - run: pytest
```

> `pyproject.toml` 项目按实际依赖安装方式调整（如 `pip install -e .`）。

### 模板 3 · Go

```yaml
name: CI
on:
  pull_request:
    branches: [ main ]
  push:
    branches: [ main ]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-go@v5
        with:
          go-version: '1.22'
      - run: go test ./...
```

### 模板 4 · Java (Maven)

```yaml
name: CI
on:
  pull_request:
    branches: [ main ]
  push:
    branches: [ main ]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4
        with:
          distribution: temurin
          java-version: '17'
          cache: maven
      - run: mvn -B test
```

### 模板 5 · Rust

```yaml
name: CI
on:
  pull_request:
    branches: [ main ]
  push:
    branches: [ main ]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: cargo test
```

### 模板 6 · PHP

```yaml
name: CI
on:
  pull_request:
    branches: [ main ]
  push:
    branches: [ main ]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: shivammathur/setup-php@v2
        with:
          php-version: '8.2'
      - run: composer install --no-interaction
      - run: composer test
```

> `composer test` 要求 `composer.json` 的 `scripts.test` 已定义；没有则改 `vendor/bin/phpunit`。

---

## 二、分支保护设置指引（生成到 `仓库协作设置指引.md`）

> 这是 git-master 产出给用户的**文档**，告诉用户怎么手动把仓库设置成受保护。默认不执行这些命令；用户已明确要求自动设置且配置已完成时，按本任务已有授权执行，不重复确认。

### 方式 A · gh CLI（推荐，可复制粘贴）

前置：`gh auth login` 已登录，且对仓库有 admin 权限。

生成设置命令前，先用 `gh api "repos/<OWNER>/<REPO>/branches/<BRANCH>/protection"` 读取当前保护，并核对适用的仓库 rulesets。权限不足、分支不存在或读取失败不能解释为“没有保护”；无法核实时只报告缺口。

已有保护时，以读取到的配置为基线，只变更本任务已授权字段，保留其余必需检查、审批要求、管理员约束、推送限制和其他规则。优先使用局部接口，例如追加检查用 [Add status check contexts](https://docs.github.com/en/rest/branches/branch-protection#add-status-check-contexts)，调整审批用 [Update pull request review protection](https://docs.github.com/en/rest/branches/branch-protection#update-pull-request-review-protection)。确需整体 PUT 时，按写入 schema 保留现值并合入已授权改动；不能直接把 GET 响应原样回传，也不能用下面的初始化示例覆盖现有规则。修改后重新读取，核对目标变化和未涉及字段。

先使用实际 CI 运行返回的检查名称；以下模板只有 `jobs.test` 且未设置 job `name`，所以示例检查名为 `test`。workflow 的 `name: CI` 不是检查名称。没有运行证据时只写待确认的设置指引，避免要求一个不会上报的检查。

以下仅用于已核实没有现有保护的分支，按团队确认的初始策略生成：

```bash
# 仅在确认目标分支没有现有保护时初始化；已有保护不得执行此整包示例。
# 替换仓库和实际目标分支；带 / 的分支名需做 URL 编码。
# 按团队已确认选项生成参数；test 仅适用于上方未改名的示例 job。
gh api --method PUT "repos/<OWNER>/<REPO>/branches/<BRANCH>/protection" \
  -H "Accept: application/vnd.github+json" \
  -F 'required_status_checks[strict]=true' \
  -f 'required_status_checks[contexts][]=test' \
  -F 'enforce_admins=false' \
  -F 'required_pull_request_reviews[dismiss_stale_reviews]=true' \
  -F 'required_pull_request_reviews[required_approving_review_count]=1' \
  -F 'restrictions=null' \
  -F 'allow_force_pushes=false'
```

`-F` 会把布尔、整数和 `null` 发送为对应 JSON 类型；`-f` 只用于字符串。参数整体加引号，避免 zsh 把方括号当作通配符。参见 [gh api](https://cli.github.com/manual/gh_api) 与 [分支保护 API](https://docs.github.com/en/rest/branches/branch-protection#update-branch-protection)。

示例要求 `test` 通过、至少 1 人 approve，并关闭受保护分支的 force-push。生成时按阶段 I 已确认选择调整；`enforce_admins=false` 不对管理员强制执行这些规则，不能宣称无人可绕过。

### 方式 B · 网页手动设置

1. 仓库页 → **Settings** → **Branches**
2. **Branch protection rules** → **Add rule**
3. Branch name pattern: 实际目标分支（如 `main`）
4. 按已确认选项勾选：
   - ☑ Require a pull request before merging → Required approvals: `1`
   - ☑ Require status checks to pass → 搜索勾选 CI 实际上报的 job 检查名（上方示例是 `test`）
   - ☑ Do not allow bypassing the above settings（可选，连 admin 也卡）
5. **Create** / **Save changes**

---

## 三、标签体系建议（可选，写进设置指引）

建议在仓库 Issues → Labels 配这套标签（颜色自定）：

| 标签 | 用途 |
| :--- | :--- |
| `needs-triage` | 新提的，待负责人分类（issue 模板默认带） |
| `bug` | 报 Bug 模板默认带 |
| `feature` | 新功能 |
| `enhancement` | 改进现有 |
| `docs` | 文档改动 |
| `priority:high` / `priority:low` | 优先级 |
| `needs-prd` | 需求大到要跑 prd-master（营队链路联动） |

---

## 四、Stale Bot（可选，自动关闭长期没人理的 issue/PR）

文件 `.github/workflows/stale.yml`（用 GitHub 官方 `actions/stale`）：

```yaml
name: Mark stale
on:
  schedule:
    - cron: '30 1 * * *'   # 每天 1:30 UTC
jobs:
  stale:
    runs-on: ubuntu-latest
    permissions:
      issues: write
      pull-requests: write
    steps:
      - uses: actions/stale@v9
        with:
          days-before-stale: 30
          days-before-close: 7
          stale-issue-label: 'stale'
          stale-pr-label: 'stale'
          exempt-issue-labels: 'priority:high,pinned'
          stale-issue-message: '这个 issue 30 天没动静了，再不动 7 天后自动关闭。需要的话留个言。'
          stale-pr-message: '这个 PR 30 天没动静了，再不动 7 天后自动关闭。'
```

> 默认不生成，除非用户在阶段 I 明确要"自动化运维"。

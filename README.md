# case_demo · UI 用例库

这个仓库是 **ui-agent 技能包的配套用例库**，跟着被测系统走，和技能包分开版本管理。

技能包（内核 + 文档 + 脚本）在另一个仓库：`https://github.com/smellship/uitest-skill.git`。
**这里只放用例，不放内核。**

## 结构

```
case_demo/
  README.md                       # 本文件：场景索引 + 怎么跑
  .gitignore
  <场景>/                          # 一场景一目录，名字就是业务名
    <用例>.yaml                    # 唯一真源：goal + checks
    others/                        # 派生物与素材，随时可重建，不手改
      <用例>.plan.json             # case compile --out 的产物
      *.txt / *.html               # 探索用的 goal、离线夹具等素材
    outputs/                       # 该场景所有运行产物（默认不进库）
      <用例>/<时间戳>/
        trace.jsonl  actions.json  result.json  summary.json
        report.html  snapshots/  screenshots/  steps/
```

## 索引

| 场景 | 用例 | 入口 | 要网络 | 说明 |
|---|---|---|---|---|
| 大肥鱼 | `bing-search-paging.yaml` | https://cn.bing.com/ | 要 | 搜索关键词并翻到第二页，验 URL 与结果文本 |
| 百望票据 | `baiwang-bill-query.yaml` | 内网/专线地址（见 `others/`） | 要 | 登录 → 选行政区划 → 查询票据列表 |
| 本地夹具 | `local-fixture.yaml` | `others/local_fixture.html`（`file:///`） | 不要 | 零依赖样例，装完即可跑通「录制 → 零 token 回放」 |

本地夹具那份 HTML 在 `本地夹具/others/local_fixture.html`，和技能包 `kernel/examples/local_fixture.html` 是同一份，
放一份到这里是为了让本仓库**自己就能跑通一条完整链路**，不依赖技能包里的文件。

## 四条规矩

1. **一场景一目录**，用例 YAML 直接放在场景目录下，不得再分层（`<场景>/<子类>/<用例>.yaml` 不行）。
2. `others/` 只放派生物与素材。`plan.json` 随时可由 YAML 重建，**不手改**。
3. `outputs/` 是**唯一**输出位置：单用例跑、计划跑、探索产物、HTML 报告都放它下面。
   内核默认往技能包的 `kernel/.artifacts/` 写；进本库必须显式给 `--run-dir`。
4. **移动 / 重命名 YAML 安全**（缓存键不认文件名和 title）。
   但改 `id:` 就是换了一个用例身份 —— 录像不再匹配，必须 `--relearn` 重录。

## 怎么跑

所有命令要在技能包的 `kernel/` 目录下执行（或用 `uv run --project <技能包>/kernel ui-agent ...`）。

**① 改 YAML → 编译 → 落计划**

```bash
uv run ui-agent case compile --in <场景>/<用例>.yaml --out <场景>/others/<用例>.plan.json --json
```

必须 `ok=true`、`errors=[]`。`errors` 非空时不会写 `--out` 文件，退出码 1。

**② 首跑：录制（会消耗模型 token）**

```bash
STAMP=$(date +%Y%m%d-%H%M%S)                     # PowerShell: $STAMP = Get-Date -Format "yyyyMMdd-HHmmss"
uv run ui-agent run --plan-file <场景>/others/<用例>.plan.json \
  --url <入口> --decider jev --supervisor on \
  --run-dir <场景>/outputs/<用例>/$STAMP --json
```

没有 Jev key 就把 `--decider jev` 换成 `--decider agent --supervisor agent`，由宿主大模型经文件桥作答。

**③ 之后：零 token 回放**

```bash
uv run ui-agent run --plan-file <场景>/others/<用例>.plan.json \
  --url <入口> --decider off --supervisor off \
  --run-dir <场景>/outputs/<用例>/$STAMP --json
```

回放时 `--url` 必须是同一个，`--var` 的**键**必须和录制时一致（值可以变）。
判断真的没调模型：`trace.jsonl` 里每行 `decision` 的 `model` 是 `cache`，倒数第二行是 `cache` 行且 `hits>0`、`misses==0`。

**④ 改了断言或步骤** → 加 `--relearn` 重录，否则回放还在用旧断言判定。

报告随 `run` 自动写进 `--run-dir`；要重出：`uv run ui-agent report --run-dir <那个目录>`。

## 录像

录像默认落在技能包内，换机器就没了。让录像随本库走：

```bash
export UI_AGENT_CACHE_DIR="<本库>/.cache"                # bash / Git Bash
$env:UI_AGENT_CACHE_DIR = "<本库>\.cache"               # PowerShell
```

录像和本机 Chromium 版本相关，升级浏览器后可能报 `wrong-context`，那时 `--relearn` 重录。
`.cache/` 已被 `.gitignore` 排除，要让别人零 token 复跑就得 `git add -f` 提交对应录像。

## 断言纪律

- 只断言**随步骤变化**的字段；不钉会漂移的具体值（比如分页参数的具体数字）。
- 不断言**可能不存在**的元素（时有时无的控件不能当验收条件）。
- 最后一步必须含业务结果类断言之一：`text_contains` / `element_value` / `element_absent` /
  `element_count` / `element_attribute`，否则触发 `weak_final_check` 警告。
- 断言写在 YAML 里是 `类型: 值`，写在命令行 `--check` 里是 `类型=值`，两者不一样。
- `DONE` 不是成功证据 —— 模型说做完了不算，断言过了才算。

## 提交节奏

```bash
git add <场景>/<用例>.yaml <场景>/others/<用例>.plan.json
git commit -m "case: <场景>/<用例> — <改了什么>"
git push
```

一次提交一个用例的改动，别把「新增用例」和「改断言」混在一个 commit 里。
`outputs/` 默认不提交；要留档某次报告就 `git add -f <场景>/outputs/<用例>/<时间戳>/report.html`。

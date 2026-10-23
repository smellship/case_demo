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
| Grafana日志 | `grafana-jxindependentjar.yaml` | `others/url-jxindependentjar.txt` 里的 Explore 地址 | 要 | 点 Run query 重跑查询，验时间窗与 `INFO jxindependentjar` 日志正文 |
| Grafana日志 | `grafana-jxcollect-bw.yaml` | `others/url-jxcollect-bw.txt` 同上，换 `app_name` | 要 | 同上，验 `INFO jxcollect`（**注意容器名带 `-bw`，logger 名不带**） |
| 大肥鱼 | `bing-search-paging.yaml` | https://cn.bing.com/ | 要 | 搜索关键词并翻到第二页，验 URL 与结果文本 |
| 百望票据 | `baiwang-bill-query.yaml` | 内网/专线地址（见 `others/`） | 要 | 登录 → 选行政区划 → 查询票据列表 |
| 进项 | `发票查验-84数电二手车.yaml` | `http://10.100.3.2/bw-main-ui/incomeAlone-ui/income/invoiceCheck` | 要 | 自带登录（干净 profile 也能跑）→ 站内路径导回查验页 → 填三字段 → 失焦 → 查验，验「查验结果」与人车信息；**金额那格键必须用「合计」** |
| 进项 | `合规查验-83数电机动车.yaml` | `http://10.100.3.2/bw-main-ui/incomeAlone-ui/income/complianceCheck` | 要 | 同上流程换到合规查验页，结果区是页面内面板不是弹窗，5 条 `text_contains`；**失焦必须按 Tab，按 Enter 会把日期静默改成当天** |
| 进项 | `采集发票-手工录入-数电纸质二手车.yaml` | `http://10.100.3.2/bw-main-ui/pictureProAlone-ui/picturePro/myNoteAdd` | 要 | 7 步：登录 → 回站内页 → 选发票类型（自绘下拉）→ 填代码号码 → 确认类型没被清空 → 填金额日期 → 保存。第 7 步只断言号码出现在页面上，**首采与「已采集过」两种结果都算过**，所以能反复跑 |
| 本地夹具 | `local-fixture.yaml` | `others/local_fixture.html`（`file:///`） | 不要 | 零依赖样例，装完即可跑通「录制 → 零 token 回放」 |

### Grafana日志 场景的入口地址

Grafana Explore 的查询条件**全在 URL 里**：`panes` 参数里带 `expr`（Loki 查询）和 `range`
（时间窗，绝对毫秒）。所以同一份用例换 `--url` 就等于换了「查哪个应用、查哪段时间」，
用例里的断言直接对着 URL 片段写（`url_contains: "1792573200000"`）。

`1792573200000` / `1792576800000` = **2026-10-21 17:00:00 / 18:00:00（Asia/Shanghai）**。
时间窗是**写死在地址里的绝对时间**，所以这份用例过的前提是那个小时的数据还在 Loki 的保留期内；
要查别的时间段，改 URL 里的 `range` 再 `--relearn` 重录（地址变了，录像的 `base_url` 对不上）。

现成的两条入口分别存在 `Grafana日志/others/url-jxindependentjar.txt` 与 `url-jxcollect-bw.txt`，
跑的时候直接读文件传进去，**不要手抄**（600 字符的百分号编码，抄错一个字符就查不到数据）：

```powershell
$u = (Get-Content "Grafana日志\others\url-jxindependentjar.txt" -Raw).Trim()
```

**别手搓 `panes` 里的 JSON。** 改查询条件只做两件事——解析出 `panes` 参数、改
`panes['tp8']['queries'][0]['expr']` 与 `panes['tp8']['range']`、再整套重新编码：

```python
import json, urllib.parse as up
q = up.urlsplit(url).query
panes = json.loads(dict(up.parse_qsl(q))["panes"])
panes["tp8"]["queries"][0]["expr"] = '{cluster="yf-bw-test-2", app_name="jxindependentjar"}'
panes["tp8"]["range"] = {"from": "1792573200000", "to": "1792576800000"}
print(url.split("?")[0] + "?" + up.urlencode({"schemaVersion": "1",
      "panes": json.dumps(panes, ensure_ascii=False), "orgId": "1"}))
```

手搓一段新的 JSON 会丢结构——实测得到过 `Last 1 hour` + `No data`，因为 `range` 与 datasource 没对上。
另外 Grafana 会**改写**它读进来的 URL（空格 `%20` ↔ `+`），所以首尾完全相等的比较不成立；
用例里只断言稳定片段（`url_contains`），回放匹配只看路径不看 query，因此这层改写不影响回放。

本地夹具那份 HTML 在 `本地夹具/others/local_fixture.html`，和技能包 `kernel/examples/local_fixture.html` 是同一份，
放一份到这里是为了让本仓库**自己就能跑通一条完整链路**，不依赖技能包里的文件。

### 进项 场景的 `--var` 键名与自足登录

百望云的进项/影像页面是 **wujie 微前端**（`bw-main-ui` 主应用套 `incomeAlone-ui` 子应用），
同一批 DOM 会同时出现在两个 frame 里。内核已按「主帧先扫、共用节点的 frame 跳过」处理，不用管，
但写用例时要记住四条：

1. **用例自带登录，不依赖残留登录态。** 第 1 步就是「有登录页就登」（断言 `text_contains: 云控制台`
   —— 登录页没有这段文本，登录后的工作台有）。所以干净 profile 也能跑。
2. **登录成功后停在「云控制台」，不会跳回发票查验页。** 第 2 步用**站点内路径**重新导航：
   ```yaml
   - goal: 回到发票查验页
     url: /bw-main-ui/incomeAlone-ui/income/invoiceCheck
   ```
   步骤级 `url` 以 `/` 开头时按 `--url` 的 origin 补全（内核 `run/plan_runner.py` 的
   `resolve_step_url`），**换环境只改 `--url`，用例不用动**。另有两点：菜单项是 DIV/SPAN，
   不在快照的角色白名单里，点不到；登录页带的 `redirectUrl` 也不保证跳回。所以只能显式导航。
3. **键名必须是控件标签的子串**（内核 `llm/textfill.py` 的 `match_var` 就是这么匹配的），
   而不是「字段名对字段名」。登录用 `--var 账号=... --var 密码=...`（登录页的框叫
   「百望云账号/手机号/电子邮箱」与「密码」，两个键都匹配得上）。
4. **发票查验页的金额那一格，标签会变**：空着叫「金额合计」，填了值就叫「价税合计」。
   用 `--var 金额合计=...` 会匹配不上填值后的同一格，重跑就停在「没有匹配 --var 的字段值」。
   一律用 `--var 合计=...`——`合计` 同时是两者的子串。同一招也适用于别的会变的标签。

（另：查验按钮在日期框失焦前是 `disabled`，填完直点「查验」不会成，要先让日期框失焦。这条写进了用例最后一步的 goal，内核会把 goal 交给决策方。）

5. **让日期框失焦用 Tab 或点别的真实控件，千万别按 `Enter`。** 这类日期组件把 `Enter`
   当成「确认当前高亮日」，日期会被**静默改成当天或面板默认值**，而「查验」按钮照样转可用——
   从结果上完全看不出错，除非断言里有值校验（`element_value: 开票日期|2025-05-05`）。
   两条进项用例的 notes 都写了这一条，断言里也钉了日期真值。
6. **日期框不要点开日历。** 日历日号是 `DIV`/`SPAN`，不在快照的角色白名单里，一旦点开
   就再也选不到日期格（实测 Jev 连续 3 次 0.4 → `low_confidence` 停机）。直接 `TYPE_TEXT` 打字。

一条能直接照抄的命令（**干净 profile 也能跑**）：

```powershell
$env:UI_AGENT_CACHE_DIR = "$PWD\.cache"
uv run --project <技能包>\kernel python <技能包>\ui-agent\scripts\host_loop.py `
  --run-dir "进项\outputs\发票查验-84数电二手车\$(Get-Date -Format yyyyMMdd-HHmmss)" `
  --profile-dir .profiles\进项 `
  --policy "进项\others\发票查验-84数电二手车.policy.py" `
  --plan-file "进项\others\发票查验-84数电二手车.plan.json" `
  --url "http://10.100.3.2/bw-main-ui/incomeAlone-ui/income/invoiceCheck" `
  --var 账号=cpy001 --var 密码='Aa123456.' `
  --var 发票号码=25152000000023214079 --var 合计=105000.00 --var 开票日期=2025-05-07 `
  --decider agent --supervisor off --cache on --mode debug
```

四条容易漏的：

- **`--policy` 必须给。** `host_loop.py` 默认是内置 `fixture` 策略，它只认得离线夹具，
  在真实页面上会直接 `SystemExit`。本用例的策略在 `others/` 里（`answer(ask, ctx)` 接口，
  按每步 goal 分段：登录 → 回发票查验页 → 填三格 → 失焦后点查验）。
- **首次录制不用加 `--relearn`；改过值或流程才要。** 不加会命中上一轮留下的录像，
  看着“跑了”实际什么也没新录；录好之后零 token 回放则是 `--decider off --supervisor off`。
- **`--decider jev` 要 Jev key。** 按技能包的层级：已有用例由 Jev 决策执行，Jev 卡住才由宿主
  agent 监督介入；不给 key 就 `--decider agent`（宿主自己决策）。
- **合规查验那条只是换了入口与断言**，命令照抄上面那段，改三处：`--plan-file` / `--policy` /
  `--url` 的末段改成 `complianceCheck`，`--var` 换成
  `发票号码=25432000000057721076 --var 合计=141400.00 --var 开票日期=2025-05-05`。
- **同一份 policy 文件能当决策者，也能当监督者**（手工录入那条就是这么跑的）：
  `--decider jev --supervisor agent` 是录制，`--decider off --supervisor off` 是零 token 回放，
  `--decider agent --supervisor agent` 是宿主全权决策。写 policy 时注意两个信封不同——
  `decide` 的答复要包一层 `{"answers": {...}}`（内核 `AgentEngine` 只认这个），
  `supervise` 直接给 `{"ruling": ..., "hint": ...}`；目标候选表按操作分头放在
  `click_target` / `type_text_target` 里（**没有** `target_element` 这个键），且同一个索引
  会同时出现在多张表里，必须按要执行的操作取表，不能合并。
  三种模式的日志与逐步骤截图见 `进项/outputs/采集发票-手工录入-数电纸质二手车/report-3modes.html`。

## 四条规矩

1. **一场景一目录**，用例 YAML 直接放在场景目录下，不得再分层（`<场景>/<子类>/<用例>.yaml` 不行）。
2. `others/` 只放派生物与素材。`plan.json` 随时可由 YAML 重建，**不手改**。
3. `outputs/` 是**唯一**输出位置：单用例跑、计划跑、探索产物、HTML 报告都放它下面。
   内核默认往技能包的 `kernel/.artifacts/` 写；进本库必须显式给 `--run-dir`。
4. **移动 / 重命名 YAML 安全**（缓存键不认文件名和 title）。
   但改 `id:` 就是换了一个用例身份 —— 录像不再匹配，必须 `--relearn` 重录。

## 怎么跑

### 第一步永远是探索，不是手写 YAML

面对一个没跑过的新页面，先让内核去探一遍，而不是凭想象写 `steps`：`explore` 就是**一次
没有断言的单目标运行**，它走完把真实轨迹落下来，你照着轨迹写 `checks`。

下面这段**在本库根目录执行**（`uv run --project` 指到技能包的 `kernel/`，所以不必先 `cd`）：

```powershell
$env:UI_AGENT_CACHE_DIR = "$PWD\.cache"
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$u = (Get-Content "Grafana日志\others\url-jxindependentjar.txt" -Raw).Trim()
uv run --project <技能包>\kernel ui-agent explore `
  --run-dir "Grafana日志\outputs\_explore\$stamp" `
  --profile-dir ".profiles\_explore" `
  --goal-file "Grafana日志\others\goal-jxindependentjar.txt" `
  --url $u --decider agent --supervisor off --json
```

（内核的后台运行与文件桥问答循环，实际交给技能包的 `scripts/host_loop.py --explore` 更省事，
它会自己起进程、答问、报终态。）

`--decider agent` 时内核会把自己的每一步问询写进 `<run-dir>/bridge/ask-NNNN.json`，
你在 `ans-NNNN.json` 里答。**单个 ask 能有 300 KB**（元素多的大页面），直接整份读进模型
上下文会把它烧光——用技能包的 `ui-agent/scripts/ask.py show` 摘着看、`answer` 答：

```powershell
python <技能包>\ui-agent\scripts\ask.py show --run-dir <那个run-dir> --grep "run query"
python <技能包>\ui-agent\scripts\ask.py answer --run-dir <那个run-dir> --op CLICK --target 36
python <技能包>\ui-agent\scripts\ask.py answer --run-dir <那个run-dir> --done
```

产物在 `<run-dir>/explore/`：`explored.yaml`（用例骨架，`checks: []`）、`trajectory.md`
（按页面分组的动作轨迹与页面变化）、`explore.json`、`goal.txt`。

拿到骨架后回到下面「正式用例的完整链路」的 ①，补上 `checks` 就是一份正式用例。
用例跑挂了就改断言或改步骤，**不要靠加等待、加点击去凑**。

### 正式用例的完整链路

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
**录像要入库**：`.gitignore` 只挡 `outputs/`、`.profiles/` 和 `*.log`，`.cache/` 是刻意留着的——
它很小（一个用例通常几 KB），但是「别人 clone 下来就能零 token 复跑」的前提。

## 并行跑多个用例

同一个库可以同时跑多路，但**每路必须有自己的浏览器 profile 目录**——Chromium 对
`user-data-dir` 加单实例锁，两路共用一个目录时后起的那路会直接崩
（内核会把它翻成「profile 目录已被另一个浏览器占用」，底层原生报错是误导性的
`Target page, context or browser has been closed`）。

约定：profile 统一放本库 `.profiles/<用例名或 lane 名>/`，`.gitignore` 已经挡掉。
两路共用一个 **录像缓存**（`.cache/`）是安全的，不同用例的键本来就不同。

```powershell
$env:UI_AGENT_CACHE_DIR = "<本库>\.cache"
# 每路自带 --run-dir 与 --profile-dir，例如
#   --run-dir   Grafana日志\outputs\grafana-jxindependentjar\20261021-180000
#   --profile-dir .profiles\grafana-jxindependentjar
```

编排脚本是技能包里的 `ui-agent/scripts/parallel_run.py`（读一份 jobs.json 清单），
细节见技能包 `references/parallel.md`。

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

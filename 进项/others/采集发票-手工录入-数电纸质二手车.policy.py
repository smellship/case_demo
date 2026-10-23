"""宿主策略：Jev 决策，卡住时这里给兜底；也能单独当决策者跑。

同一份文件覆盖三种运行形态：
- `--decider jev --supervisor agent`：只有卡住时收到 supervise（录制）；
- `--decider off`：一次都不问（零 token 回放）；
- `--decider agent --supervisor agent`：decide 也走这里（宿主全权决策）。
  注意 decide 的答复要包一层 `{"answers": {...}}`，supervise 不包——内核两种信封不同。

Jev 有两处容易被页面结构骗到，这个策略按当前步骤的 goal 兜底：
- 发票类型是自绘下拉，Jev 可能去点旁边的输入框；
- 填完代码类型会被清空，Jev 容易漏掉第二次选择。
"""
from __future__ import annotations

RESULT_WORDS = ("票夹名称", "暂无数据", "操作")

ALIASES = {
    "发票代码": ("发票代码",),
    "发票号码": ("发票号码",),
    "不含税金额": ("不含税金额", "金额合计", "价税合计"),
    "开票日期": ("开票日期",),
    "发票类型": ("发票类型",),
}

VALUE_OF = {
    "发票代码": "3200184130",
    "发票号码": "70747171",
    "不含税金额": "92920.35",
    "开票日期": "2025-05-07",
    "发票类型": "增值税专用发票",
}


def _pick(criteria: dict, choice, confidence: float = 0.95) -> dict:
    return {
        "choice": choice,
        "probabilities": {key: (1.0 if key == choice else 0.0) for key in criteria},
        "confidence": confidence,
    }


def _goal_of(payload: dict) -> str:
    instr = ((payload.get("questions") or {}).get("operation") or {}).get("instructions") or {}
    return str(instr.get("goal") or "")


def _head_of(operation: str) -> str:
    return operation.lower() + "_target"


def _elements(questions: dict, operation: str = "CLICK") -> dict:
    """读某个操作的目标候选表：键是元素索引，值形如
    {"element": "[3] textbox 发票号码", "current_value": "..."}。

    三个坑（都是实测踩出来的）：
    1. 候选**按操作分头放**（`click_target` / `type_text_target` / ...），没有 `target_element`
       这个键；只读 `target_element` 会永远拿到空表，然后一路落到 DONE。
    2. 同一个索引会同时出现在多个候选表里（能点也能打字的输入框就有 `click_target` 和
       `type_text_target` 两份），所以必须**按要执行的操作**取表，不能合并。
    3. 候选里没有 label / role 键，角色和标签都在 `element` 那一句话里。
    """
    return (questions.get(_head_of(operation)) or {}).get("criteria") or {}


def _text(item: dict) -> str:
    return str(item.get("element") or "")


def _role(item: dict) -> str:
    parts = _text(item).split(" ", 2)
    return parts[1] if len(parts) > 1 else ""


def _value(item: dict):
    return item.get("current_value")


def _do(questions: dict, operation: str, element: str | None = None) -> dict:
    operation_criteria = (questions.get("operation") or {}).get("criteria") or {}
    if operation not in operation_criteria:
        raise SystemExit(f"操作 {operation} 不在候选里（{list(operation_criteria)}）")
    answer = {"operation": _pick(operation_criteria, operation)}
    if element is not None:
        head = _head_of(operation)
        criteria = (questions.get(head) or {}).get("criteria") or {}
        if element not in criteria:
            raise SystemExit(f"元素 {element} 不在 {head} 候选里")
        answer[head] = _pick(criteria, element)
    return answer


def _find(questions: dict, label: str, role: str = "", operation: str = "CLICK") -> str | None:
    for key, item in _elements(questions, operation).items():
        if label in _text(item) and (not role or _role(item) == role):
            return key
    return None


def _value_of(questions: dict, label: str) -> str:
    for key in ALIASES.get(label, (label,)):
        hit = _find(questions, key)
        if hit:
            return VALUE_OF[key]
    return ""


def _decide(payload: dict) -> dict:
    questions = payload.get("questions") or {}
    goal = _goal_of(payload)
    text = str(((payload.get("state") or {}).get("page") or {}).get("text") or "")

    if not goal:
        return _do(questions, "DONE")

    # 登录：先把账号密码填进空着的输入框，再点「登录」
    if "入口" in goal or "登录" in goal:
        boxes = _elements(questions, "TYPE_TEXT")
        for label in ("账号", "密码"):
            for key, item in boxes.items():
                if (label in _text(item)
                        and _role(item) == "textbox" and not _value(item)):
                    return _do(questions, "TYPE_TEXT", key)
        button = _find(questions, "登录", "button")
        if button:
            return _do(questions, "CLICK", button)
        return _do(questions, "DONE")

    # 下拉：还没选中就先 CLICK 触发器，选中了就别再点（否则会反复开合）
    if "发票类型" in goal:
        option = _find(questions, "增值税专用发票", "option")
        if option:
            return _do(questions, "CLICK", option)
        box = _find(questions, "发票类型", "combobox") or _find(questions, "发票类型")
        boxes = _elements(questions, "CLICK")
        if box and str(_value(boxes[box]) or "") != VALUE_OF["发票类型"]:
            return _do(questions, "CLICK", box)
        return _do(questions, "DONE")

    # 填字段：逐个填空着的输入框（已填过的跳过，否则宿主决策时会反复填同一格）
    if any(word in goal for word in ("填入", "输入框")):
        boxes = _elements(questions, "TYPE_TEXT")
        for label in ("发票代码", "发票号码", "不含税金额", "开票日期"):
            for key, item in boxes.items():
                if (label in _text(item)
                        and _role(item) == "textbox" and not _value(item)):
                    return _do(questions, "TYPE_TEXT", key)
        return _do(questions, "DONE")

    # 保存
    if "保存" in goal:
        save = _find(questions, "保存", "button") or _find(questions, "保存")
        if save:
            return _do(questions, "CLICK", save)
        if "暂无数据" not in text:
            return _do(questions, "DONE")
        return _do(questions, "WAIT")

    return _do(questions, "DONE")


def _supervise(payload: dict, ctx: dict) -> dict:
    goal = _goal_of(payload)
    if "发票类型" in goal:
        hint = "发票类型是自绘下拉：先 CLICK 那个显示「请选择」或当前类型名的下拉框，再从弹层里 CLICK「增值税专用发票」。"
    elif "填入" in goal or "输入框" in goal:
        hint = "直接 TYPE_TEXT 到空着的输入框；日期也可以直接打字，不要点开日历。"
    elif "保存" in goal:
        hint = "点「保存」按钮；若页面停在表单上，先确认发票类型不是「请选择」。"
    else:
        hint = "按当前 goal 继续。"
    return {"ruling": "HINT", "hint": hint}


def answer(ask: dict, ctx: dict) -> dict:
    kind = str(ask.get("kind") or "")
    payload = ask.get("payload") or {}
    if kind == "decide":
        # decide 是 agent 决策者的信封：内核的 AgentEngine 只认 {"answers": {...}}。
        return {"answers": _decide(payload)}
    if kind == "supervise":
        return _supervise(payload, ctx)
    if kind == "text":
        label = str(((payload.get("field") or {}).get("element") or {}).get("label") or "")
        value = _value_of(payload.get("questions") or {}, label)
        if not value:
            raise SystemExit(f"没有被问到过的字段值：{label}")
        return {"choice": value, "confidence": 0.9}
    raise SystemExit(f"不认识的 ask 类型：{kind}")

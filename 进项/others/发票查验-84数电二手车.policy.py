"""宿主策略：发票查验 84 数电二手车（真实环境演示用，不进 skill 包）。

内核每次 decide 都会带上**当前步骤的 goal**（`payload.questions.operation.instructions.goal`），
宿主按 goal 判断该走哪一段，不要一口气把后面步骤的动作都做完 —— 否则后面步骤没东西可做，
断言也就没法分工。

接口契约见 ui-agent/references/running.md：answer(ask, ctx) -> dict。
"""

from __future__ import annotations

# 结果区的标志文本：出现它说明查验完成
RESULT_WORDS = ("查验结果", "历史查验次数")

# 控件标签会变：金额填进去之后「金额合计」会变成「价税合计」，
# 而内核的 --var 匹配规则是「键名必须是标签子串」，所以这里得自己写别名。
ALIASES = {
    "金额合计": ("金额合计", "价税合计"),
    "价税合计": ("金额合计", "价税合计"),
}


def _pick(criteria: dict, chosen: str, confidence: float = 0.95) -> dict:
    keys = list(criteria)
    rest = (1.0 - confidence) / max(1, len(keys) - 1) if len(keys) > 1 else 0.0
    return {
        "choice": chosen,
        "probabilities": {k: (confidence if k == chosen else rest) for k in keys},
        "confidence": confidence,
    }


def _do(questions: dict, operation: str, element: dict | None = None) -> dict:
    answers = {"operation": _pick(questions["operation"]["criteria"], operation)}
    if element is not None:
        head = f"{operation.lower()}_target"
        criteria = (questions.get(head) or {}).get("criteria") or {}
        key = str(element.get("index"))
        if key not in criteria:
            raise SystemExit(f"元素 {key} 不在 {head} 候选里（{list(criteria)}）")
        answers[head] = _pick(criteria, key)
    return answers


def _find(elements: list[dict], *labels: str, role: str = "") -> dict | None:
    for want in labels:
        for el in elements:
            if role and el.get("role") != role:
                continue
            if want in (el.get("label") or ""):
                return el
    return None


def _has(el: dict | None, op: str) -> bool:
    return bool(el) and op in (el.get("operations") or [])


def _value_for(label: str, ctx: dict) -> str | None:
    """与内核 match_var 同款语义（键名是标签子串、取最长匹配），但对会变名的字段认别名。"""
    labels = [label]
    for key, names in ALIASES.items():
        if key in (ctx.get("vars") or {}) and any(name in label or label in name for name in names):
            labels.extend(names)
    best = None
    for key, value in (ctx.get("vars") or {}).items():
        if not key:
            continue
        if any(key in one for one in labels) and (best is None or len(key) > len(best[0])):
            best = (key, value)
    return best[1] if best else None


def _goal_of(payload: dict) -> str:
    questions = payload.get("questions") or {}
    instr = (questions.get("operation") or {}).get("instructions") or {}
    return instr.get("goal") or ""


def _decide(payload: dict, ctx: dict) -> dict:
    state = payload.get("state") or {}
    questions = payload.get("questions") or {}
    elements = state.get("elements") or []
    text = ((state.get("page") or {}).get("text")) or ""
    recent = state.get("recent_actions") or []
    goal = _goal_of(payload)

    # ---- 第 1 步：进页面（有登录页就登，没有就直接往下走）
    if "入口" in goal or "登录" in goal:
        account = _find(elements, "账号", "用户名", role="textbox")
        password = _find(elements, "密码", role="textbox")
        login = _find(elements, "登录", "登陆", role="button")
        if account and password and login:
            for field in (account, password):
                if not field.get("value") and _has(field, "TYPE_TEXT"):
                    return _do(questions, "TYPE_TEXT", field)
            if _has(login, "CLICK"):
                return _do(questions, "CLICK", login)
        return _do(questions, "DONE")

    # ---- 第 2 步：回到发票查验页（导航已由步骤级 url 完成，这里只需收工）
    if "回到" in goal or "导航" in goal:
        return _do(questions, "DONE")

    # ---- 第 3 步：填三个输入框（按顺序，值来自 --var）
    if "填入" in goal or "输入框" in goal:
        for el in elements:
            if el.get("role") != "textbox" or el.get("disabled"):
                continue
            label = el.get("label") or ""
            if _value_for(label, ctx) is None:
                continue
            if el.get("value"):
                continue
            if _has(el, "TYPE_TEXT"):
                return _do(questions, "TYPE_TEXT", el)
        return _do(questions, "DONE")

    # ---- 第 4 步：让日期框失焦 → 点查验 → 等结果
    if "查验" in goal:
        if any(word in text for word in RESULT_WORDS):
            return _do(questions, "DONE")
        verify = _find(elements, "查验", role="button")
        clicked_verify = any(
            (a.get("action") or "") == "CLICK" and "查验" in (a.get("text") or "")
            for a in recent
        )
        if verify is not None and not verify.get("disabled") and _has(verify, "CLICK") and not clicked_verify:
            return _do(questions, "CLICK", verify)
        # 查验按钮还挂着 disabled：先点「备注」让日期框失焦，按钮才会启用
        note = _find(elements, "备注", role="textbox")
        if note is not None and _has(note, "CLICK") and not clicked_verify:
            return _do(questions, "CLICK", note)
        if verify is not None and _has(verify, "CLICK") and not clicked_verify:
            return _do(questions, "CLICK", verify)
        return _do(questions, "WAIT")

    return _do(questions, "DONE")


def _supervise(payload: dict, ctx: dict) -> dict:
    """Jev 卡住时宿主接手：只给方向，不替它执行（决策权仍在 Jev）。

    实测这一页最容易卡的地方是日期框：Jev 点开日历后就找不到日期格了 ——
    日历的日号是 DIV/SPAN，不在快照的角色白名单里，永远不会出现在元素表。
    这里直接告诉它「别点开日历，直接往框里打字」，比任何 REPLAN 都省事。
    """
    stuck = payload.get("stuck") or {}
    goal = payload.get("current_goal") or ""
    elements = ((payload.get("state") or {}).get("elements")) or []
    detail = str(stuck.get("detail") or "")

    # 第 3 步填值卡住：日期框不要点开日历，直接 TYPE_TEXT
    if "填入" in goal or "输入框" in goal:
        pending = [
            el for el in elements
            if el.get("role") == "textbox" and not el.get("disabled")
            and not el.get("value") and _value_for(el.get("label") or "", ctx) is not None
            and _has(el, "TYPE_TEXT")
        ]
        if pending:
            el = pending[0]
            return {
                "ruling": "HINT",
                "hint": (
                    f"「{el.get('label')}」这一格还没填。别点它去开日历/下拉，"
                    f"直接对这个输入框执行 TYPE_TEXT，值用 --var 里给的那个。"
                    f"日内日期格是 DIV，不在元素表里，点开就出不来了。"
                ),
            }
        return {"ruling": "HINT", "hint": "三格都填好了就直接 DONE，进下一步。"}

    # 第 4 步查验：查验按钮 disabled 说明日期框还没失焦
    if "查验" in goal:
        verify = _find(elements, "查验", role="button")
        if verify is not None and verify.get("disabled"):
            return {"ruling": "HINT", "hint": "查验按钮还是 disabled：先 CLICK 一下「备注」让日期框失焦，按钮才会启用。"}
        if "查验结果" in " ".join(str(el.get("label") or "") for el in elements):
            return {"ruling": "HINT", "hint": "查验结果弹窗已经出来了，直接 DONE。"}
        return {"ruling": "HINT", "hint": "点「查验」按钮；如果它盖在弹窗下面，说明弹窗已经出来了，直接 DONE。"}

    return {"ruling": "HINT", "hint": f"按当前步骤 goal 继续（{detail[:60]}）。"}


def answer(ask: dict, ctx: dict) -> dict:
    kind = ask.get("kind")
    payload = ask.get("payload") or {}
    if kind == "decide":
        return {"answers": _decide(payload, ctx)}
    if kind == "text":
        label = ((payload.get("field") or {}).get("label")) or ""
        value = _value_for(label, ctx)
        if value is None:
            raise SystemExit(f"没有 --var 能填「{label}」")
        return {"text": value}
    if kind == "supervise":
        return _supervise(payload, ctx)
    raise SystemExit(f"未知 ask kind：{kind}")

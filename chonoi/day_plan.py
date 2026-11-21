"""Kế hoạch Ngày (TICKET-02 mục 2, Test Contract v1.1 mục 4.1/4.3) — TV2.

Mỗi mục kế hoạch: {day, dishes, ingredients}. `dishes` là map id món -> số suất (nguyên dương);
`ingredients` = tổng công thức × số suất (map kind -> số nguyên dương), sắp theo kind.
Dùng chung cho kiểm contract, kiểm scenario `day.day_plan` và lát day (sự kiện `day_plan`, lọc món của quán).
"""

from .errors import BadInput

PLAN_KEYS = {"day", "dishes", "ingredients"}


def plan_ingredients(dishes: dict, menu: dict) -> dict:
    """Tổng nguyên liệu cần = Σ công thức × số suất, sắp theo kind, bỏ lượng 0."""
    total = {}
    for dish_id, servings in dishes.items():
        for kind, n in menu[dish_id]["recipe"].items():
            total[kind] = total.get(kind, 0) + n * servings
    return {k: total[k] for k in sorted(total) if total[k] > 0}


def _pos_int_map(name, m):
    if not isinstance(m, dict) or not m:
        raise BadInput(f"{name} phải là map không rỗng id -> số nguyên dương")
    for k, v in m.items():
        if isinstance(v, bool) or not isinstance(v, int) or v <= 0:
            raise BadInput(f"{name}.{k} phải là số nguyên dương, đang là {v!r}")


def validate_plan_entry(name, entry, menu, max_day, require_ingredients=True) -> dict:
    """Kiểm một mục kế hoạch; trả về bản chuẩn {day, dishes, ingredients} (ingredients tính lại)."""
    if not isinstance(entry, dict) or set(entry) - PLAN_KEYS:
        raise BadInput(f"{name} chỉ có các khóa {sorted(PLAN_KEYS)}")
    day = entry.get("day")
    if isinstance(day, bool) or not isinstance(day, int) or not (1 <= day <= max_day):
        raise BadInput(f"{name}.day phải là số nguyên trong [1, {max_day}]")
    _pos_int_map(f"{name}.dishes", entry.get("dishes"))
    for dish_id in entry["dishes"]:
        if dish_id not in menu:
            raise BadInput(f"{name}.dishes: món ngoài thực đơn {dish_id!r}")
    want = plan_ingredients(entry["dishes"], menu)
    if "ingredients" in entry or require_ingredients:
        _pos_int_map(f"{name}.ingredients", entry.get("ingredients"))
        if dict(sorted(entry["ingredients"].items())) != want:
            raise BadInput(f"{name}.ingredients phải bằng tổng công thức × số suất: {want}")
    return {"day": day, "dishes": dict(entry["dishes"]), "ingredients": want}


def validate_day_plan(plan, menu, days=5) -> list:
    """Kế hoạch đủ `days` Ngày, `day` lần lượt 1..days."""
    if not isinstance(plan, list) or len(plan) != days:
        raise BadInput(f"tuning.day_plan phải là mảng đúng {days} Ngày")
    out = [validate_plan_entry(f"tuning.day_plan[{i}]", e, menu, days) for i, e in enumerate(plan)]
    if [e["day"] for e in out] != list(range(1, days + 1)):
        raise BadInput(f"tuning.day_plan phải xếp day = 1..{days}")
    return out

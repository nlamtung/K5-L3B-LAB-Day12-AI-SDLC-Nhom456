"""Thủy quái (Cá Sấu Năm Chèo — TICKET-02 mục 1.2 & 4.5).

Tách file riêng để tránh xung đột với logic bơi/hái/bắt cá trong `gather.py`.
"""

import math

from ..ids import id_key, sort_by_id

TICK = 60.0


def init_monsters(tuning_gather, scenario, ids, day=1):
    """Dựng danh sách thủy quái từ scenario (nếu có) hoặc theo bố trí Ngày."""
    m_cfg = tuning_gather.get("monsters")
    if not m_cfg:
        return []
    if "monsters" in scenario:
        src = scenario["monsters"]
    else:
        src = [s for s in m_cfg.get("spawns", []) if s.get("from_day", 1) <= day]
    out = []
    for m in src:
        out.append({
            "id": m["id"],
            "kind": m["kind"],
            "pos": [float(c) for c in m["pos"]],
            "waypoints": [[float(c) for c in wp] for wp in m["waypoints"]],
            "target_idx": m.get("target_idx", 1),
            "state": m.get("state", "patrol"),
            "state_ticks_left": m.get("state_ticks_left", 0),
            "recoil_dir": [float(c) for c in m["recoil_dir"]] if m.get("recoil_dir") is not None else None,
        })
        ids.reserve(m["id"])
    return out


def snapshot_monsters(monsters):
    return [
        {
            "id": m["id"],
            "kind": m["kind"],
            "pos": m["pos"],
            "waypoints": m["waypoints"],
            "target_idx": m["target_idx"],
            "state": m["state"],
            "state_ticks_left": m["state_ticks_left"],
            "recoil_dir": m["recoil_dir"],
        }
        for m in sort_by_id(monsters)
    ]


def _clamp(pos, x_bounds, d_bounds):
    pos[0] = max(float(x_bounds[0]), min(float(x_bounds[1]), pos[0]))
    pos[1] = max(float(d_bounds[0]), min(float(d_bounds[1]), pos[1]))


def _move_toward(pos, target, step_dist):
    dx = target[0] - pos[0]
    dd = target[1] - pos[1]
    dist = math.hypot(dx, dd)
    if dist <= step_dist or dist == 0.0:
        pos[0], pos[1] = float(target[0]), float(target[1])
        return True
    pos[0] += (dx / dist) * step_dist
    pos[1] += (dd / dist) * step_dist
    return False


def step_monsters(sim, events) -> bool:
    """Cập nhật thủy quái theo id và xét tối đa 1 hit. Trả True nếu người chơi ngất (fainted)."""
    m_cfg = sim.t.get("monsters")
    if not m_cfg or not sim.monsters:
        return False

    species_map = m_cfg["species"]
    x_bounds = sim.t["bounds"]["x"]
    just_recovered = set()

    for m in sort_by_id(sim.monsters):
        sp = species_map[m["kind"]]
        d_bounds = sp["depths"]
        d_min = d_bounds[0]
        state = m["state"]

        if state == "stunned":
            m["state_ticks_left"] -= 1
            if m["state_ticks_left"] <= 0:
                m["state"] = "patrol"
                m["state_ticks_left"] = 0
                just_recovered.add(m["id"])
            continue

        if state == "recoil":
            step_dist = sp["recoil_dist"] / TICK
            rdir = m["recoil_dir"] or [1.0, 0.0]
            m["pos"][0] += rdir[0] * step_dist
            m["pos"][1] += rdir[1] * step_dist
            _clamp(m["pos"], x_bounds, d_bounds)
            m["state_ticks_left"] -= 1
            if m["state_ticks_left"] <= 0:
                m["state"] = "patrol"
                m["state_ticks_left"] = 0
                m["recoil_dir"] = None
                just_recovered.add(m["id"])
            continue

        dist_p = math.dist(m["pos"], sim.pos)
        if state == "patrol":
            if sim.pos[1] >= d_min and dist_p <= sp["detect_radius"]:
                m["state"] = "chase"
                _move_toward(m["pos"], sim.pos, sp["chase_speed"] / TICK)
            else:
                wp = m["waypoints"][m["target_idx"]]
                if _move_toward(m["pos"], wp, sp["patrol_speed"] / TICK):
                    m["target_idx"] = 1 - m["target_idx"]
            _clamp(m["pos"], x_bounds, d_bounds)
        elif state == "chase":
            if sim.pos[1] < d_min or dist_p > sp["exit_radius"]:
                m["state"] = "patrol"
                wp = m["waypoints"][m["target_idx"]]
                if _move_toward(m["pos"], wp, sp["patrol_speed"] / TICK):
                    m["target_idx"] = 1 - m["target_idx"]
            else:
                _move_toward(m["pos"], sim.pos, sp["chase_speed"] / TICK)
            _clamp(m["pos"], x_bounds, d_bounds)

    # Xét tối đa 1 hit nếu hết bất tử
    if sim.invuln_ticks > 0:
        return False

    cands = []
    for m in sim.monsters:
        if m["id"] in just_recovered or m["state"] not in ("patrol", "chase"):
            continue
        sp = species_map[m["kind"]]
        if sim.pos[1] < sp["depths"][0]:
            continue
        dist = math.dist(m["pos"], sim.pos)
        if dist <= sp["hit_radius"]:
            cands.append((dist, id_key(m["id"]), m, sp))

    if not cands:
        return False

    cands.sort(key=lambda x: (x[0], x[1]))
    _, _, hitter, sp = cands[0]

    sim.hp = max(0, sim.hp - 1)
    drop_n = int(len(sim.hold) * m_cfg.get("loss_ratio", 0.5))
    lost = sim.drop_lifo(drop_n)  # v1.2: mảng cá thể theo thứ tự bỏ (LIFO)
    sim.invuln_ticks = int(m_cfg.get("invuln_ticks", 90))

    rx = hitter["pos"][0] - sim.pos[0]
    rd = hitter["pos"][1] - sim.pos[1]
    norm = math.hypot(rx, rd)
    recoil_dir = [rx / norm, rd / norm] if norm > 1e-12 else [1.0, 0.0]
    hitter["state"] = "recoil"
    hitter["state_ticks_left"] = int(sp["recoil_ticks"])
    hitter["recoil_dir"] = recoil_dir

    events.append(("monster_hit", {
        "monster_id": hitter["id"],
        "hp": sim.hp,
        "lost": lost,
        "pos": list(sim.pos),
    }))

    if sim.hp <= 0:
        rem_lost = sim.drop_lifo(len(sim.hold))
        events.append(("faint", {"cause": "monster", "lost": rem_lost, "hp": 0}))
        sim._finish("fainted", events)
        return True

    return False

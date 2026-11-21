"""Buổi sáng — Lặn & Hái (`gather`, Contract v1.0 & v1.1).

Mặt cắt dòng sông nhìn NGANG: vị trí `[x, d]` (x sang phải, `d` độ sâu hướng xuống, d = 0 là mặt nước).
`move = [x, d]`: thành phần thứ hai DƯƠNG = bơi xuống. Hướng mặt là góc từ +x, dương = xuống.

Thứ tự xử lý một bước (TICKET-02 mục 4.5):
  1. Tăng phase_tick, giảm timer ca, invuln_ticks, catch_cd_ticks, hồi nút (`node_regrown`).
  2. Bơi, chặn mép, `dive`/`surface`, oxy, `oxygen_empty`, đếm ngạt → `choke` → `faint` (nếu HP = 0, dừng bước).
  3. Cập nhật thủy quái theo id + xét tối đa 1 `monster_hit` → `faint` (nếu HP = 0, dừng bước).
  4. `interact`: bến trước (`docked`), rồi hái nút ở mặt nước (`gather`/`hold_full`).
  5. `catch`: bắt cá dưới nước theo vị trí TRƯỚC khi cá bơi (`fish_caught`/`hold_full`).
  6. Hết giờ (`time`).
  7. Nếu còn giờ và `random_fish` bật: cá bơi (đổi hướng mỗi 120 bước, phản xạ mép) rồi sinh thêm ở `phase_tick = 360·k`.

v1.2 (TICKET-03): giỏ là mảng cá thể {id, kind, fresh} theo thứ tự vào giỏ (mới nhất cuối). Hàng mới fresh = 100,
hao từ bước sau; hàng có sẵn hao gather_decay ở đầu bước (bước 1), phát `spoiled` (location "hold") theo id khi
vừa xuống dưới ngưỡng. Id cấp I1, I2… theo thứ tự vào giỏ (IdAllocator, nối tiếp xuyên pha/Ngày). Rơi hàng LIFO;
`lost` là mảng cá thể theo thứ tự bỏ. Kho bàn giao/xuất file theo id.
"""

import math

from ..fresh import Freshness
from ..ids import id_key, sort_by_id
from .monsters import init_monsters, snapshot_monsters, step_monsters
from .ramp import ramp_velocity

TICK = 60.0
AXES = ("x", "d")


class GatherSim:
    mode = "gather"
    phase = "gather"

    def __init__(self, tuning, scenario, streams, ids, day=1, oxygen_max_s=None, hp_max=None):
        t = tuning["gather"]
        self.t = t
        self.rng = streams
        self.ids = ids
        self.day = day
        self.phase_tick = 0
        self.random_fish = scenario.get("random_fish", True)

        p = scenario.get("player", {})
        self.pos = [float(c) for c in p.get("pos", t["start_pos"])]
        self.vel = [float(c) for c in p.get("vel", [0.0, 0.0])]
        self._tgt = None
        self._ramp_left = 0
        self.heading = float(p.get("heading_deg", t["start_heading_deg"]))

        oxy_s = oxygen_max_s if oxygen_max_s is not None else t["oxygen_max_s"]
        self.hp_max = hp_max if hp_max is not None else t["hp_max"]
        self.oxygen_max = int(round(oxy_s * TICK))
        self.oxygen_ticks = p.get("oxygen_ticks", self.oxygen_max)
        self.hp = p.get("hp", self.hp_max)
        self.zero_oxy_ticks = p.get("zero_oxy_ticks", 0)
        self.invuln_ticks = p.get("invuln_ticks", 0)
        self.catch_cd_ticks = p.get("catch_cd_ticks", 0)
        self.fresh = Freshness(tuning)
        # giỏ: cá thể theo thứ tự vào giỏ, cuối mảng là mới nhất
        self.hold = [self.fresh.load(it) for it in scenario.get("hold", [])]
        for it in self.hold:
            ids.reserve(it["id"])
        self.time_left_ticks = scenario.get("time_left_ticks", int(round(t["duration_s"] * TICK)))

        src_nodes = scenario["nodes"] if "nodes" in scenario else t["nodes"]
        self.nodes = [{"id": n["id"], "kind": n["kind"], "pos": [float(c) for c in n["pos"]],
                       "regrow_ticks": n.get("regrow_ticks", 0)} for n in src_nodes]
        for e in self.nodes:
            ids.reserve(e["id"])

        self.fish = []
        if "fish" in scenario:
            for f in scenario["fish"]:
                self.fish.append({
                    "id": f["id"], "kind": f["kind"],
                    "pos": [float(c) for c in f["pos"]],
                    "heading_deg": float(f.get("heading_deg", 0)),
                    "age_ticks": int(f.get("age_ticks", 0)),
                })
                ids.reserve(f["id"])
        elif self.random_fish:
            fi = t["fish_initial"]
            if isinstance(fi, list):
                for f in fi:
                    self.fish.append({
                        "id": f["id"], "kind": f["kind"],
                        "pos": [float(c) for c in f["pos"]],
                        "heading_deg": float(f.get("heading_deg", 0)),
                        "age_ticks": 0,
                    })
                    ids.reserve(f["id"])
            else:
                self._spawn_initial_fish(int(fi))

        self.monsters = init_monsters(t, scenario, ids, day=day)
        self.money = 0
        self.earned = 0
        self.reputation = tuning["quan"]["reputation_initial"]
        self.done = False
        self.reason = None

    # --- sinh cá v1.1 ---------------------------------------------------------
    def _pick_spawn_candidate(self, rng, clearance):
        weights = self.t["fish_weights"]
        xs = self.t["fish_spawn_x"]
        depths = self.t["fish_spawn_depths"]
        valid_by_kind = {}
        for kind in sorted(weights.keys()):
            pts = []
            for x in xs:
                for d in depths[kind]:
                    if all(math.dist((x, d), f["pos"]) > clearance for f in self.fish):
                        pts.append((float(x), float(d)))
            if pts:
                valid_by_kind[kind] = pts
        if not valid_by_kind:
            return None
        kinds = sorted(valid_by_kind.keys())
        total_w = sum(weights[k] for k in kinds)
        r = rng.random() * total_w
        acc = 0.0
        chosen_kind = kinds[-1]
        for k in kinds:
            acc += weights[k]
            if r <= acc:
                chosen_kind = k
                break
        pts = valid_by_kind[chosen_kind]
        pt = pts[rng.randrange(len(pts))]
        heading = rng.random() * 360.0
        return chosen_kind, [pt[0], pt[1]], heading

    def _spawn_initial_fish(self, count):
        rng = self.rng.get("fish_spawn")
        clearance = float(self.t.get("fish_spawn_clearance", 1.0))
        for _ in range(count):
            picked = self._pick_spawn_candidate(rng, clearance)
            if picked is None:
                break
            kind, pos, heading = picked
            fid = self.ids.new("F")
            self.fish.append({
                "id": fid, "kind": kind, "pos": pos,
                "heading_deg": heading, "age_ticks": 0,
            })

    def _step_fish_and_spawn(self, events):
        if not self.random_fish or "fish_speed" not in self.t:
            return
        step_dist = float(self.t["fish_speed"]) / TICK
        turn_ticks = int(self.t["fish_turn_ticks"])
        x_lo, x_hi = float(self.t["fish_x"][0]), float(self.t["fish_x"][1])
        depths_map = self.t["fish_depths"]
        rng_move = self.rng.get("fish_move")

        for f in sort_by_id(self.fish):
            f["age_ticks"] += 1
            if f["age_ticks"] % turn_ticks == 0:
                f["heading_deg"] = rng_move.random() * 360.0
            rad = math.radians(f["heading_deg"])
            vx, vd = math.cos(rad), math.sin(rad)
            nx = f["pos"][0] + vx * step_dist
            nd = f["pos"][1] + vd * step_dist
            d_lo, d_hi = float(depths_map[f["kind"]][0]), float(depths_map[f["kind"]][1])
            if nx < x_lo:
                nx = x_lo + (x_lo - nx)
                vx = -vx
            elif nx > x_hi:
                nx = x_hi - (nx - x_hi)
                vx = -vx
            if nd < d_lo:
                nd = d_lo + (d_lo - nd)
                vd = -vd
            elif nd > d_hi:
                nd = d_hi - (nd - d_hi)
                vd = -vd
            f["pos"][0] = max(x_lo, min(x_hi, nx))
            f["pos"][1] = max(d_lo, min(d_hi, nd))
            f["heading_deg"] = math.degrees(math.atan2(vd, vx)) % 360.0

        spawn_ticks = int(self.t["fish_spawn_ticks"])
        fish_max = int(self.t["fish_max"])
        if self.phase_tick > 0 and self.phase_tick % spawn_ticks == 0 and len(self.fish) < fish_max:
            rng_sp = self.rng.get("fish_spawn")
            clearance = float(self.t["fish_spawn_clearance"])
            picked = self._pick_spawn_candidate(rng_sp, clearance)
            if picked is not None:
                kind, pos, heading = picked
                fid = self.ids.new("F")
                self.fish.append({
                    "id": fid, "kind": kind, "pos": pos,
                    "heading_deg": heading, "age_ticks": 0,
                })
                events.append(("fish_spawned", {"id": fid, "kind": kind, "pos": list(pos)}))

    # --- giao diện cho runner -------------------------------------------------
    def inventory_items(self) -> list:
        """Kho bàn giao (file / gather_end): mảng cá thể {id, kind, fresh} theo id."""
        return self.fresh.out_list(self.hold)

    def handoff_items(self) -> list:
        """Kho bàn giao trong bộ nhớ (day): bản sim chính xác {id, kind, u} theo id, không hao thêm."""
        return [dict(it) for it in sort_by_id(self.hold)]

    def _new_items(self, kind, n) -> list:
        return [self.fresh.item(self.ids.new("I"), kind) for _ in range(n)]

    def drop_lifo(self, n) -> list:
        """Bỏ n cá thể theo LIFO (vào sau bỏ trước); trả mảng cá thể đã bỏ theo thứ tự bỏ."""
        return [self.fresh.out(self.hold.pop()) for _ in range(min(n, len(self.hold)))]

    def snapshot(self) -> dict:
        return {
            "player": {"pos": self.pos, "vel": self.vel, "heading_deg": self.heading,
                       "oxygen_ticks": self.oxygen_ticks, "oxygen_max_ticks": self.oxygen_max,
                       "hp": self.hp, "hp_max": self.hp_max, "zero_oxy_ticks": self.zero_oxy_ticks,
                       "invuln_ticks": self.invuln_ticks, "catch_cd_ticks": self.catch_cd_ticks,
                       "at_surface": self._at_surface()},
            "hold": self.fresh.out_list(self.hold, by_id=False), "hold_count": len(self.hold),
            "hold_capacity": self.t["hold_capacity"],
            "nodes": [{"id": n["id"], "pos": n["pos"], "kind": n["kind"],
                       "ready": n["regrow_ticks"] == 0, "regrow_ticks": n["regrow_ticks"]}
                      for n in sort_by_id(self.nodes)],
            "fish": [{"id": f["id"], "pos": f["pos"], "kind": f["kind"],
                      "heading_deg": f["heading_deg"], "age_ticks": f["age_ticks"]}
                     for f in sort_by_id(self.fish)],
            "monsters": snapshot_monsters(self.monsters),
        }

    # --- một bước ---------------------------------------------------------------
    def step(self, inp):
        events = []
        # 1. đồng hồ, cooldown, bất tử và hồi nút
        self.phase_tick += 1
        self.time_left_ticks = max(0, self.time_left_ticks - 1)
        self.invuln_ticks = max(0, self.invuln_ticks - 1)
        self.catch_cd_ticks = max(0, self.catch_cd_ticks - 1)
        for n in sort_by_id(self.nodes):
            if n["regrow_ticks"] > 0:
                n["regrow_ticks"] -= 1
                if n["regrow_ticks"] == 0:
                    events.append(("node_regrown", {"node_id": n["id"]}))
        #    độ tươi của hàng có sẵn trong giỏ (v1.2)
        events += self.fresh.decay(self.hold, self.fresh.gather_decay, "hold")

        # 2. bơi + chặn mép + chuyển biên mặt nước + oxy / ngạt / ngất
        was_at_surface = self._at_surface()
        self._move(inp)
        now_at_surface = self._at_surface()
        if was_at_surface and not now_at_surface:
            events.append(("dive", {"pos": list(self.pos)}))
        elif not was_at_surface and now_at_surface:
            events.append(("surface", {"pos": list(self.pos)}))

        if now_at_surface:
            self.oxygen_ticks = min(self.oxygen_max, self.oxygen_ticks + self.t["oxygen_refill_per_tick"])
            self.zero_oxy_ticks = 0
        else:
            prev_oxy = self.oxygen_ticks
            self.oxygen_ticks = max(0, self.oxygen_ticks - 1)
            if prev_oxy > 0 and self.oxygen_ticks == 0:
                events.append(("oxygen_empty", {"oxygen_ticks": 0}))
            if self.oxygen_ticks == 0:
                self.zero_oxy_ticks += 1
                if self.zero_oxy_ticks >= self.t["choke_interval_ticks"]:
                    self.zero_oxy_ticks = 0
                    self.hp = max(0, self.hp - 1)
                    events.append(("choke", {"hp": self.hp}))
                    if self.hp <= 0:
                        lost = self.drop_lifo(len(self.hold))
                        events.append(("faint", {"cause": "choke", "lost": lost, "hp": 0}))
                        self._finish("fainted", events)
                        return events

        # 3. thủy quái (cập nhật theo id + xét tối đa 1 hit)
        if step_monsters(self, events):
            return events

        # 4. interact: bến trước, rồi hái (chỉ khi ở mặt nước)
        if inp.pressed("interact"):
            if self._in_dock():
                self._finish("docked", events)
                return events
            if now_at_surface:
                r = self.t["interact_radius"]
                cands = []
                for n in self.nodes:
                    if n["regrow_ticks"] == 0:
                        dist = math.dist(self.pos, n["pos"])
                        if dist <= r:
                            cands.append((dist, id_key(n["id"]), n))
                if cands:
                    cands.sort(key=lambda x: (x[0], x[1]))
                    node = cands[0][2]
                    req = self.t["node_yield"]
                    free = self.t["hold_capacity"] - len(self.hold)
                    if free >= req:
                        self.hold.extend(self._new_items(node["kind"], req))
                        node["regrow_ticks"] = int(round(self.t["regrow_s"] * TICK))
                        events.append(("gather", {"node_id": node["id"], "kind": node["kind"], "amount": req}))
                    else:
                        events.append(("hold_full", {"action": "gather", "node_id": node["id"], "required": req, "free": free}))

        # 5. bắt cá (theo vị trí TRƯỚC khi cá bơi, chỉ khi hết hồi chiêu và dưới nước)
        if inp.pressed("catch") and self.catch_cd_ticks == 0 and not now_at_surface:
            r = self.t["catch_radius"]
            cands = []
            for f in self.fish:
                dist = math.dist(self.pos, f["pos"])
                if dist <= r:
                    cands.append((dist, id_key(f["id"]), f))
            if cands:
                cands.sort(key=lambda x: (x[0], x[1]))
                fish = cands[0][2]
                req = self.t["fish_yield"][fish["kind"]]
                free = self.t["hold_capacity"] - len(self.hold)
                if free >= req:
                    self.hold.extend(self._new_items(fish["kind"], req))
                    self.fish.remove(fish)
                    self.catch_cd_ticks = int(round(self.t["catch_cooldown_s"] * TICK))
                    events.append(("fish_caught", {"fish_id": fish["id"], "kind": fish["kind"], "yield": req}))
                else:
                    events.append(("hold_full", {"action": "catch", "fish_id": fish["id"], "required": req, "free": free}))

        # 6. hết giờ
        if self.time_left_ticks <= 0:
            self._finish("time", events)
            return events

        # 7. cá bơi và sinh thêm theo lịch (nếu còn giờ)
        self._step_fish_and_spawn(events)
        return events

    # --- tiện ích ---------------------------------------------------------------
    def _at_surface(self) -> bool:
        return self.pos[1] <= self.t["surface_depth"]

    def _in_dock(self) -> bool:
        return math.dist(self.pos, self.t["dock_pos"]) <= self.t["dock_radius"]

    def _finish(self, reason, events):
        self.done = True
        self.reason = reason
        events.append(("gather_end", {"reason": reason, "inventory": {"items": self.inventory_items()}}))

    def _move(self, inp):
        speed = self.t["swim_speed"]
        mx, md = inp.move
        self.vel = ramp_velocity(self, (mx * speed, md * speed), int(self.t["ramp_max_ticks"]))
        if (mx, md) != (0.0, 0.0):
            self.heading = math.degrees(math.atan2(md, mx)) % 360
        b = self.t["bounds"]
        for i, axis in enumerate(AXES):
            self.pos[i] += self.vel[i] / TICK
            lo, hi = b[axis]
            if self.pos[i] <= lo:
                self.pos[i] = lo
                self.vel[i] = max(0.0, self.vel[i])
            elif self.pos[i] >= hi:
                self.pos[i] = hi
                self.vel[i] = min(0.0, self.vel[i])

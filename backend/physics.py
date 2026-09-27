"""Live CPU G1 locomotion, adapted from the user's G1 Street Wise project.

The existing frozen Unitree LSTM policy is executed in NumPy. All displayed
joint poses come from MuJoCo, not a browser animation or prerecorded trajectory.
"""

import math
from pathlib import Path
import xml.etree.ElementTree as ET
import mujoco
import numpy as np
from .gait import NumpyGait
from .facility import FIXTURES, BLOCKAGE, HOME

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = np.array([-0.1, 0, 0, 0.3, -0.2, 0] * 2)
KP = np.array([100, 100, 100, 150, 40, 40] * 2)
KD = np.array([2, 2, 2, 4, 2, 2] * 2)


class Twin:
    def __init__(self, blocked=True, saved=None):
        xml = ET.parse(ROOT / "backend/assets/g1.xml")
        xml.getroot().find("compiler").set(
            "meshdir", str(ROOT / "web/public/assets/g1/meshes")
        )
        world = xml.getroot().find("worldbody")
        ET.SubElement(
            world,
            "geom",
            name="floor",
            type="plane",
            size="20 20 .1",
            friction="1 .005 .0001",
        )
        for item in FIXTURES + ([BLOCKAGE] if blocked else []):
            x, y, w, d, h = item["box"]
            ET.SubElement(
                world,
                "geom",
                name=item["id"],
                type="box",
                pos=f"{x} {y} {h / 2}",
                size=f"{w} {d} {h / 2}",
            )
        self.model = mujoco.MjModel.from_xml_string(
            ET.tostring(xml.getroot(), encoding="unicode")
        )
        self.model.opt.timestep = 0.002
        self.data = mujoco.MjData(self.model)
        self.policy = NumpyGait(ROOT / "backend/assets/gait.npz")
        self.data.qpos[:2] = HOME
        self.data.qpos[7:19] = DEFAULT
        self.action = np.zeros(12, dtype=np.float32)
        self.target = DEFAULT.copy()
        self.counter = 0
        self.contacts = 0
        self.distance = 0.0
        self.obstacles = {
            mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_GEOM, i["id"])
            for i in FIXTURES + ([BLOCKAGE] if blocked else [])
        }
        if saved:
            self.data.qpos[:] = saved["qpos"]
            self.data.qvel[:] = saved["qvel"]
            self.policy.h = np.array(saved["h"], dtype=np.float32)
            self.policy.c = np.array(saved["c"], dtype=np.float32)
            self.action = np.array(saved["action"])
            self.target = np.array(saved["target"])
            self.counter = saved["counter"]
            self.data.time = saved["time"]
            self.distance = saved["distance"]
            self.contacts = saved["contacts"]
        mujoco.mj_forward(self.model, self.data)

    def step(self, goal, steps=100):
        for _ in range(steps):
            before = self.data.qpos[:2].copy()
            if self.counter % 10 == 0:
                dx, dy = np.asarray(goal) - self.data.qpos[:2]
                w, x, y, z = self.data.qpos[3:7]
                yaw = math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))
                error = (math.atan2(dy, dx) - yaw + math.pi) % (2 * math.pi) - math.pi
                distance = math.hypot(dx, dy)
                cmd = [
                    min(0.55, distance * 0.7) * max(0, math.cos(error))
                    if abs(error) < 0.7
                    else 0,
                    0,
                    float(np.clip(error * 1.5, -0.65, 0.65)),
                ]
                if distance < 0.15:
                    cmd = [0, 0, 0]
                gravity = [
                    2 * (-z * x + w * y),
                    -2 * (z * y + w * x),
                    1 - 2 * (w * w + x * x),
                ]
                phase = (self.counter * 0.002 % 0.8) / 0.8
                obs = np.concatenate(
                    [
                        self.data.qvel[3:6] * 0.25,
                        gravity,
                        np.array(cmd) * [2, 2, 0.25],
                        self.data.qpos[7:19] - DEFAULT,
                        self.data.qvel[6:18] * 0.05,
                        self.action,
                        [math.sin(2 * math.pi * phase), math.cos(2 * math.pi * phase)],
                    ]
                ).astype(np.float32)
                self.action = self.policy(obs).copy()
                self.target = self.action * 0.25 + DEFAULT
            self.data.ctrl[:] = (
                self.target - self.data.qpos[7:19]
            ) * KP - self.data.qvel[6:18] * KD
            mujoco.mj_step(self.model, self.data)
            self.counter += 1
            self.distance += float(np.linalg.norm(self.data.qpos[:2] - before))
            if any(
                c.geom1 in self.obstacles or c.geom2 in self.obstacles
                for c in self.data.contact
            ):
                self.contacts += 1
            if not np.all(np.isfinite(self.data.qpos)) or self.data.qpos[2] < 0.45:
                raise RuntimeError("Robot stability guard stopped the simulation")
            if self.contacts:
                raise RuntimeError("Obstacle contact guard stopped the simulation")
        return self.data.qpos.tolist()

    def snapshot(self):
        return {
            "qpos": self.data.qpos.tolist(),
            "qvel": self.data.qvel.tolist(),
            "h": self.policy.h.tolist(),
            "c": self.policy.c.tolist(),
            "action": self.action.tolist(),
            "target": self.target.tolist(),
            "counter": self.counter,
            "time": float(self.data.time),
            "distance": self.distance,
            "contacts": self.contacts,
        }

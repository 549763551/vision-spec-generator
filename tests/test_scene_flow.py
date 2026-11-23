"""3D 页流程对照与作业指导书必须跟任务走，不能写死一套节点。"""

import unittest

from core.procedure import build_procedure
from core.scene import build_scene


class TestSceneFlow(unittest.TestCase):
    def test_scene_flow_follows_color_task(self):
        scene = build_scene(task="颜色判别", accuracy=0.03, fov_w=15, fov_h=12)
        self.assertIn("颜色提取", scene["flow"])
        self.assertIn("色差判定", scene["flow"])
        self.assertNotIn("颗粒分析", scene["flow"])

    def test_scene_flow_follows_scratch_task(self):
        scene = build_scene(task="表面划痕", accuracy=0.03, fov_w=15, fov_h=12)
        self.assertIn("二值化", scene["flow"])
        self.assertIn("颗粒分析", scene["flow"])
        self.assertNotIn("颜色提取", scene["flow"])

    def test_procedure_pixel_format_matches_camera(self):
        color_steps = build_procedure("颜色判别", 0.0094, 0.03, 15, 12, 1600, 1200)
        pix = [p[1] for s in color_steps for p in s.params if p[0] == "像素格式"]
        self.assertTrue(any("彩色" in v for v in pix))

        mono_steps = build_procedure("表面划痕", 0.0094, 0.03, 15, 12, 1600, 1200)
        pix = [p[1] for s in mono_steps for p in s.params if p[0] == "像素格式"]
        self.assertTrue(any("黑白" in v for v in pix))


if __name__ == "__main__":
    unittest.main()

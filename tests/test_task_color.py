"""任务到相机色彩的映射回归：颜色判别不能配黑白相机。"""

import unittest

from core.camera import select_camera, task_requires_color
from core.scene import build_scene


class TestTaskColor(unittest.TestCase):
    def test_color_task_flag(self):
        self.assertTrue(task_requires_color("颜色判别"))
        self.assertFalse(task_requires_color("平面字符"))

    def test_color_task_gets_color_camera(self):
        cam = select_camera(15, 12, 0.03,
                            need_color=task_requires_color("颜色判别"))
        self.assertEqual(cam.color_mode, "彩色")
        self.assertTrue(any("彩色相机" in s for s in cam.steps))

    def test_other_task_stays_monochrome(self):
        cam = select_camera(15, 12, 0.03,
                            need_color=task_requires_color("平面字符"))
        self.assertEqual(cam.color_mode, "黑白")

    def test_scene_follows_task(self):
        scene = build_scene(task="颜色判别", accuracy=0.03, fov_w=15, fov_h=12)
        rows = scene["panels"]["cam"]["rows"]
        color_row = next(r for r in rows if r[0] == "色彩")
        self.assertEqual(color_row[1], "彩色")


if __name__ == "__main__":
    unittest.main()

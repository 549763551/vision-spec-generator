"""多拍拆分（超规格）回归测试。

场景：视野大 + 精度高，需求分辨率超过最大面阵档位（25MP 5120×5120）。
旧版行为：硬给最高档 + 一句"需拼接"——输出方案当场就知道不达标。
新版行为：量化拆分，且守住三条恒等式：
  1. 单幅像素精度 ≤ 目标精度（且 = 精度 ÷ 每缺陷像素）
  2. 拆分幅数 × 单幅视野 ≥ 全视野（覆盖恒等式）
  3. 单幅视野 = 档位分辨率 × 精度 ÷ 每缺陷像素（与单相机选择同一判据）

手算基准（100×80 mm @ 0.005 mm，feature_px=3）：
  需求 20000×16000（精度级）→ 60000×48000（缺陷级）→ 超过 5120×5120
  25MP 档：单幅 = 5120×0.005÷3 = 8.5333 mm → 12 幅 × 10 幅 = 120 幅
  （20MP 档 5472×3648 → 11×14 = 154 幅，25MP 更少，应选 25MP）
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.camera import select_camera
from core.lens import select_lens
from core.light import recommend_light
from core.controller import select_controller
from core.validate import validate


class TestMultiShotSelection(unittest.TestCase):

    def setUp(self):
        self.cam = select_camera(fov_w=100, fov_h=80, accuracy=0.005)

    def test_oversize_triggers_multi_shot(self):
        self.assertIsNotNone(self.cam.fov_shot, "超规格应进入多拍分支")
        self.assertEqual((self.cam.shots_w, self.cam.shots_h), (12, 10))

    def test_identity_pixel_accuracy(self):
        # 恒等式 1：单幅像素精度 = 精度 ÷ 每缺陷像素
        self.assertAlmostEqual(self.cam.pixel_accuracy_mm, 0.005 / 3, delta=1e-9)
        self.assertLessEqual(self.cam.pixel_accuracy_mm, 0.005)

    def test_identity_coverage(self):
        # 恒等式 2：幅数 × 单幅 ≥ 全视野
        fw, fh = self.cam.fov_full
        self.assertGreaterEqual(self.cam.shots_w * self.cam.fov_shot[0], fw - 1e-9)
        self.assertGreaterEqual(self.cam.shots_h * self.cam.fov_shot[1], fh - 1e-9)

    def test_identity_fov_shot(self):
        # 恒等式 3：单幅视野 = 档位分辨率 × 精度 ÷ 每缺陷像素
        self.assertAlmostEqual(
            self.cam.fov_shot[0], self.cam.width_px * 0.005 / 3, delta=1e-9)

    def test_square_tier_wins_when_both_axes_matter(self):
        # 100×80 下 25MP（5120×5120，120 幅）应优于 20MP（5472×3648，154 幅）
        self.assertEqual(self.cam.width_px, 5120)
        self.assertEqual(self.cam.megapixel, 25.0)

    def test_moderate_case(self):
        # 60×50 @ 0.01：单幅 17.0667 → 4×3 = 12 幅
        cam = select_camera(fov_w=60, fov_h=50, accuracy=0.01)
        self.assertEqual((cam.shots_w, cam.shots_h), (4, 3))

    def test_normal_case_not_multi(self):
        cam = select_camera(fov_w=12, fov_h=10, accuracy=0.01)
        self.assertIsNone(cam.fov_shot, "常规场景不应触发多拍")
        self.assertEqual(cam.megapixel, 12.0)


class TestMultiShotEndToEnd(unittest.TestCase):
    """多拍方案的镜头/光源/自检全部按单幅视野，端到端无 fail。"""

    def test_pipeline_passes_with_multi_shot(self):
        cam = select_camera(fov_w=100, fov_h=80, accuracy=0.005)
        fw, fh = cam.fov_shot
        lens = select_lens(sensor_w=cam.sensor_w, sensor_h=cam.sensor_h,
                           fov_w=fw, fov_h=fh, wd=130, pixel_um=cam.pixel_um)
        light = recommend_light("表面划痕", fw, fh)
        ctrl = select_controller(light_channels=1, channel_power_w=10)
        val = validate(camera=cam, lens=lens, light=light, controller=ctrl,
                       accuracy=0.005, fov_w=fw, fov_h=fh, wd_expect=130)
        self.assertEqual(
            val.fail_count, 0,
            f"多拍方案不应有不通过项：{[(c.name, c.detail) for c in val.checks if c.status == 'fail']}")
        names = [c.name for c in val.checks]
        self.assertIn("多拍覆盖视野", names)
        self.assertIn("多拍单幅精度", names)

    def test_coverage_check_passes(self):
        cam = select_camera(fov_w=100, fov_h=80, accuracy=0.005)
        fw, fh = cam.fov_shot
        lens = select_lens(sensor_w=cam.sensor_w, sensor_h=cam.sensor_h,
                           fov_w=fw, fov_h=fh, wd=130, pixel_um=cam.pixel_um)
        light = recommend_light("表面划痕", fw, fh)
        ctrl = select_controller(light_channels=1, channel_power_w=10)
        val = validate(camera=cam, lens=lens, light=light, controller=ctrl,
                       accuracy=0.005, fov_w=fw, fov_h=fh, wd_expect=130)
        cov = next(c for c in val.checks if c.name == "多拍覆盖视野")
        self.assertEqual(cov.status, "pass")


if __name__ == "__main__":
    unittest.main(verbosity=2)

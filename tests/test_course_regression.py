"""通行做法例题回归测试。

测试集不是编的，是把行业通用选型方法里讲师算过的题拿出来当基准：
  案例 1  ：10mm×8mm 划痕、精度 0.01mm、静止拍摄
  案例 2  ：1/2.5" 500W、FOV 11×8、WD 130 → 焦距 67mm
  案例 3  ：WD 被限死时 75mm + 接圈
  案例 4  ：一般调光 DPS / 大功率稳定 CPL / 飞拍 120μs SPS

跑法：在项目根目录执行  python -m unittest discover -s tests -v
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


class TestCourseCase1_Camera(unittest.TestCase):
    """：视野放大到 12×10，精度 0.01mm，静止拍摄。

    通行做法答案：先算 1200×1000（约 120 万，取 130 万），
              缺陷占 3~4 像素 → 3600×3000 → 取 1200 万像素。
    """

    def setUp(self):
        self.spec = select_camera(fov_w=12, fov_h=10, accuracy=0.01,
                                  moving=False, feature_px=3)

    def test_accuracy_level_resolution(self):
        self.assertEqual(self.spec.res_for_accuracy, (1200, 1000),
                         "按精度反推应为 1200×1000")

    def test_defect_level_resolution(self):
        self.assertEqual(self.spec.res_for_defect, (3600, 3000),
                         "缺陷占 3 像素应为 3600×3000")

    def test_megapixel_is_12(self):
        self.assertEqual(self.spec.megapixel, 12.0, "应选 1200 万像素档位")

    def test_static_can_use_rolling(self):
        self.assertIn("卷帘", self.spec.shutter)

    def test_pixel_accuracy_meets_requirement(self):
        self.assertLessEqual(self.spec.pixel_accuracy_mm, 0.01)


class TestCourseCase2_Lens(unittest.TestCase):
    """：f = WD × Sensor / FOV。

    通行做法算例：1/2.5" 500W、FOV 11×8、WD 130 → 口算 67mm。
    按 1/2.5" 标准靶面 5.7×4.28 复算为 67.36mm，与通行做法口算差 0.36mm（0.5%），
    差异来自靶面取 5.7 还是 5.4——这是可解释的，不是算错。
    """

    def setUp(self):
        self.spec = select_lens(sensor_w=5.7, sensor_h=4.28,
                                fov_w=11, fov_h=8, wd=130, pixel_um=2.2)

    def test_long_side_used(self):
        # 视野长宽比 1.375 ≥ 芯片长宽比 1.332 → 用长边
        self.assertEqual(self.spec.use_side, "长边")

    def test_focal_matches_course(self):
        self.assertAlmostEqual(self.spec.f_calc, 67.36, delta=0.5)
        self.assertLess(abs(self.spec.f_calc - 67) / 67, 0.02,
                        "与通行做法口算 67mm 的偏差应在 2% 内")

    def test_recommend_75_and_wd_larger(self):
        self.assertEqual(self.spec.f_recommend, 75)
        self.assertGreater(self.spec.wd_at_recommend, 130,
                           "选 75mm 工作距离会大于 130，相机装得更高")

    def test_alt_50_and_wd_smaller(self):
        self.assertEqual(self.spec.f_alt, 50)
        self.assertLess(self.spec.wd_at_alt, 130,
                        "选 50mm 工作距离会小于 130，相机装得更低")


class TestCourseCase3_Case(unittest.TestCase):
    """：WD 被限死时，用 75mm 再配接圈。"""

    def test_higher_focal_gives_more_wd(self):
        spec = select_lens(sensor_w=5.7, sensor_h=4.28, fov_w=11, fov_h=8,
                           wd=130, pixel_um=2.2)
        self.assertGreater(spec.wd_at_recommend, spec.wd_at_alt)


class TestCourseCase4_Controller(unittest.TestCase):
    """选型小结。"""

    def test_normal_dimming_uses_dps(self):
        c = select_controller(light_channels=1, channel_power_w=10,
                              need_program_control=True)
        self.assertEqual(c.series, "DPS")
        self.assertTrue(c.has_serial)
        self.assertTrue(c.has_ethernet, "需要程序控制应选 C 版带网口")

    def test_high_power_stable_uses_cpl(self):
        c = select_controller(light_channels=4, channel_power_w=40,
                              need_stable_brightness=True)
        self.assertEqual(c.series, "CPL")

    def test_strobe_120us_uses_sps(self):
        c = select_controller(light_channels=1, channel_power_w=20,
                              exposure_max_us=120)
        self.assertEqual(c.series, "SPS")
        self.assertTrue(c.has_boost)

    def test_strobe_30us_uses_bps(self):
        c = select_controller(light_channels=1, channel_power_w=20,
                              exposure_max_us=30)
        self.assertEqual(c.series, "BPS")

    def test_manual_uses_aps(self):
        c = select_controller(light_channels=1, channel_power_w=10)
        self.assertEqual(c.series, "APS")
        self.assertFalse(c.has_serial)


class TestLightRules(unittest.TestCase):
    """方向选择。"""

    def test_dimension_uses_backlight(self):
        s = recommend_light("尺寸测量", 12, 10)
        self.assertEqual(s.direction, "背光")

    def test_scratch_uses_low_angle(self):
        s = recommend_light("表面划痕", 12, 10)
        self.assertEqual(s.direction, "低角度")
        self.assertIn("暗场", s.field_type)

    def test_reflective_metal_uses_coaxial_with_polarizer(self):
        s = recommend_light("高反光金属", 12, 10)
        self.assertEqual(s.direction, "同轴")
        self.assertTrue(s.polarization)

    def test_color_complement(self):
        s = recommend_light("颜色判别", 12, 10, suppress_color="红")
        self.assertEqual(s.color, "青", "要压掉红色应打其互补色青光")

    def test_bad_image_triggers_warning(self):
        s = recommend_light("表面划痕", 12, 10,
                            diag={"gray_diff": 12, "overexposed_ratio": 0.08,
                                  "underexposed_ratio": 0.0, "edge_sharpness": 5})
        self.assertTrue(any("灰度差" in w for w in s.warnings))
        self.assertTrue(any("过曝" in w for w in s.warnings))


class TestValidateEndToEnd(unittest.TestCase):
    """端到端：四组计算 → 自检必须跑通且不出现"不通过"。"""

    def test_full_pipeline_passes(self):
        cam = select_camera(fov_w=12, fov_h=10, accuracy=0.01)
        lens = select_lens(sensor_w=cam.sensor_w, sensor_h=cam.sensor_h,
                           fov_w=12, fov_h=10, wd=130, pixel_um=cam.pixel_um)
        light = recommend_light("表面划痕", 12, 10)
        ctrl = select_controller(light_channels=1, channel_power_w=10)
        val = validate(camera=cam, lens=lens, light=light, controller=ctrl,
                       accuracy=0.01, fov_w=12, fov_h=10)
        self.assertEqual(val.fail_count, 0,
                         f"不应有不通过项：{[c.name for c in val.checks if c.status == 'fail']}")
        self.assertGreaterEqual(len(val.checks), 6, "至少应跑完 6 项自检")

    def test_depth_of_field_fails_when_variation_too_big(self):
        cam = select_camera(fov_w=12, fov_h=10, accuracy=0.01)
        lens = select_lens(sensor_w=cam.sensor_w, sensor_h=cam.sensor_h,
                           fov_w=12, fov_h=10, wd=130, pixel_um=cam.pixel_um,
                           height_variation=5.0)
        light = recommend_light("表面划痕", 12, 10)
        ctrl = select_controller(light_channels=1, channel_power_w=10)
        val = validate(camera=cam, lens=lens, light=light, controller=ctrl,
                       accuracy=0.01, height_variation=5.0, fov_w=12, fov_h=10)
        self.assertGreater(val.fail_count, 0, "高度变化 5mm 远超景深，应报不通过")


if __name__ == "__main__":
    unittest.main(verbosity=2)

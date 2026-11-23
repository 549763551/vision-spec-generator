"""光源角度修正回归：曲面/高反光不能继续沿用一个 90° 直射规则。"""

import unittest

from core.light import recommend_light


# 对应实际瓶盖图：灰度差足够，但过曝 3.5%、拉普拉斯方差 14.2。
SUSPECT_DIAG = {
    "gray_diff": 150.6,
    "overexposed_ratio": 0.0355,
    "underexposed_ratio": 0.0,
    "lap_var": 14.2,
    "strong_edge_ratio": 0.0053,
}


class TestLightSurface(unittest.TestCase):
    def test_flat_char_keeps_90(self):
        """平整面仍走原来的 90° 亮场，不被新规则误伤。"""
        light = recommend_light("平面字符", 30, 30)
        self.assertEqual(light.direction, "高角度")
        self.assertEqual(light.angle, "90°")
        self.assertFalse(any("表面修正" in s for s in light.steps))

    def test_curved_char_switches_to_low_angle(self):
        """显式声明曲面时，改 30°~45° 低角度环形光，尺寸余量不变。"""
        light = recommend_light("平面字符", 30, 30, surface="曲面")
        self.assertEqual(light.direction, "低角度")
        self.assertEqual(light.angle, "30°~45°")
        self.assertEqual(light.series, "RS")
        self.assertTrue(light.polarization)
        self.assertEqual(light.size_mm, (36.0, 36.0))
        self.assertTrue(any("表面修正" in s for s in light.steps))

    def test_diag_suspect_switches_without_surface(self):
        """用户只拖了图：过曝 + 边缘偏软也要能回写光路。"""
        light = recommend_light("平面字符", 30, 30, diag=SUSPECT_DIAG)
        self.assertEqual(light.direction, "低角度")
        self.assertEqual(light.angle, "30°~45°")
        self.assertTrue(light.polarization)
        self.assertTrue(any("拉普拉斯方差 14" in s for s in light.steps))
        self.assertTrue(any("已改低角度+偏振" in w for w in light.warnings))

    def test_diag_suspect_does_not_touch_low_angle_task(self):
        """本来就是暗场低角度的任务，不重复套表面修正。"""
        light = recommend_light("表面划痕", 30, 30, diag=SUSPECT_DIAG)
        self.assertEqual(light.direction, "低角度")
        self.assertEqual(light.angle, "30°")
        self.assertFalse(any("表面修正" in s for s in light.steps))

    def test_explicit_surface_wins_over_missing_diag(self):
        """没有图像诊断时，显式 surface 依然生效。"""
        light = recommend_light("二维码", 20, 20, surface="高反光")
        self.assertEqual(light.angle, "30°~45°")
        self.assertTrue(light.polarization)
        self.assertEqual(light.size_mm, (24.0, 24.0))


if __name__ == "__main__":
    unittest.main()

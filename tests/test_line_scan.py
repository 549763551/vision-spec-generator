"""线阵分支的回归用例：垂直尺寸、行频、带宽三件事必须自洽。"""
import unittest

from core.camera import select_camera, LINE_SENSOR_TABLE


class TestLineScan(unittest.TestCase):

    def setUp(self):
        # 80mm 扫描宽度、0.05mm 精度、300mm/s
        self.cam = select_camera(fov_w=80, fov_h=60, accuracy=0.05,
                                 moving=True, speed=300, scan="line")

    def test_scan_flag(self):
        self.assertEqual(self.cam.scan, "line")
        self.assertEqual(self.cam.height_px, 1, "线阵纵向只有一行像素")

    def test_pixel_matches_fov(self):
        """像素精度 × 像素数 必须回到视野宽，误差在 0.1% 内。"""
        back = self.cam.pixel_accuracy_mm * self.cam.width_px
        self.assertAlmostEqual(back, 80.0, delta=80.0 * 0.001)

    def test_line_rate_matches_speed(self):
        """行频 × 像素精度 必须回到速度。"""
        back = self.cam.line_rate_hz * self.cam.pixel_accuracy_mm
        self.assertAlmostEqual(back, 300.0, delta=300.0 * 0.001)

    def test_data_rate_consistent(self):
        expect = self.cam.width_px * self.cam.line_rate_hz / 1e6
        self.assertAlmostEqual(self.cam.data_rate_mbps, expect, delta=expect * 0.01)

    def test_picks_smallest_sufficient_sensor(self):
        """选中的档位必须够用，且上一档不够用。"""
        need = self.cam.res_for_defect[0]
        self.assertGreaterEqual(self.cam.width_px, need)
        idx = [t[0] for t in LINE_SENSOR_TABLE].index(self.cam.width_px)
        if idx > 0:
            self.assertLess(LINE_SENSOR_TABLE[idx - 1][0], need)

    def test_zero_speed_warns(self):
        cam = select_camera(fov_w=80, fov_h=60, accuracy=0.05, speed=0, scan="line")
        self.assertIsNone(cam.line_rate_hz)
        self.assertTrue(any("速度" in w for w in cam.warnings))

    def test_area_unchanged(self):
        """面阵路径不受影响。"""
        cam = select_camera(fov_w=12, fov_h=10, accuracy=0.01)
        self.assertEqual(cam.scan, "area")
        self.assertGreater(cam.height_px, 1)


if __name__ == "__main__":
    unittest.main()

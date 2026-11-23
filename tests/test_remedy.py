"""修复方向建议（remedy）回归测试。

期望值全部可手工复算，公式与 core.remedy 头注释一致：
  光圈反解 N = 需求景深 × β² ÷ (2·c·(1+β))，c = 2 × 像元(μm) ÷ 1000
  速度上限   = 精度 ÷ 曝光
  焦距反选   WD = f ÷ β，取 |WD - 限高| 最小的 FOCAL_STEPS 档位
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
from core.remedy import attach_remedies


def _pipeline(fov_w, fov_h, acc, wd=130, hv=0.0, moving=False, speed=0.0,
              fov_override=None, ctrl_kwargs=None):
    cam = select_camera(fov_w=fov_w, fov_h=fov_h, accuracy=acc,
                        moving=moving, speed=speed)
    fw, fh = fov_override or (fov_w, fov_h)
    lens = select_lens(sensor_w=cam.sensor_w, sensor_h=cam.sensor_h,
                       fov_w=fw, fov_h=fh, wd=wd, pixel_um=cam.pixel_um,
                       height_variation=hv)
    light = recommend_light("表面划痕", fw, fh)
    ctrl = select_controller(light_channels=1, channel_power_w=10,
                             exposure_max_us=cam.exposure_max_us,
                             **(ctrl_kwargs or {}))
    val = validate(camera=cam, lens=lens, light=light, controller=ctrl,
                   accuracy=acc, height_variation=hv, moving=moving,
                   speed=speed, fov_w=fw, fov_h=fh, wd_expect=wd)
    attach_remedies(val, cam, lens, light, ctrl, accuracy=acc,
                    height_variation=hv, moving=moving, speed=speed,
                    fov_w=fw, fov_h=fh, wd_expect=wd)
    return val, cam, lens


class TestDepthOfFieldRemedy(unittest.TestCase):

    def test_aperture_number_is_recomputable(self):
        # 40×33 @ 0.05，高度变化 2mm：β = 8.45/40 = 0.211，
        # c = 2×3.452/1000，N = 2×β²/(2c(1+β)) ≈ 5.3
        val, cam, lens = _pipeline(40, 33, 0.05, wd=300, hv=2.0)
        check = next(c for c in val.checks if c.name == "景深不足")
        self.assertEqual(check.status, "fail")
        beta = lens.magnification
        c_mm = 2 * cam.pixel_um / 1000.0
        n_expected = 2.0 * beta ** 2 / (2 * c_mm * (1 + beta))
        self.assertTrue(check.remedies, "景深不足应给出修法")
        self.assertTrue(
            any(f"F{n_expected:.1f}" in r for r in check.remedies),
            f"修法应含手算光圈值 F{n_expected:.1f}：{check.remedies}")
        self.assertTrue(any("远心" in r for r in check.remedies))

    def test_absurd_aperture_called_out(self):
        # 12×10 @ 0.01，高度变化 5mm → N≈190，超出光圈范围，应明说不可行
        val, _, _ = _pipeline(12, 10, 0.01, hv=5.0)
        check = next(c for c in val.checks if c.name == "景深不足")
        self.assertTrue(
            any("不可行" in r or "超出" in r for r in check.remedies),
            f"超大 N 应指出收光圈不可行：{check.remedies}")


class TestExposureAndBoostRemedy(unittest.TestCase):

    def test_speed_cap_is_recomputable(self):
        # 构造一个曝光超限的相机（正常流水线不会出现，暴露公式）：
        # 精度 0.01、速度 200 → 上限 50μs；把相机曝光改成 500μs → 拖影 fail
        cam = select_camera(fov_w=40, fov_h=33, accuracy=0.01,
                            moving=True, speed=200)
        cam.exposure_max_us = 500.0
        lens = select_lens(sensor_w=cam.sensor_w, sensor_h=cam.sensor_h,
                           fov_w=40, fov_h=33, wd=300, pixel_um=cam.pixel_um)
        light = recommend_light("表面划痕", 40, 33)
        ctrl = select_controller(light_channels=1, channel_power_w=10,
                                 exposure_max_us=500.0)
        val = validate(camera=cam, lens=lens, light=light, controller=ctrl,
                       accuracy=0.01, moving=True, speed=200,
                       fov_w=40, fov_h=33, wd_expect=300)
        attach_remedies(val, cam, lens, light, ctrl, accuracy=0.01,
                        moving=True, speed=200, fov_w=40, fov_h=33, wd_expect=300)
        check = next(c for c in val.checks if c.name == "曝光拖影风险")
        self.assertEqual(check.status, "fail")
        speed_max = 0.01 / (500.0 * 1e-6)
        self.assertTrue(
            any(f"{speed_max:.0f} mm/s" in r for r in check.remedies),
            f"修法应含速度上限 {speed_max:.0f} mm/s：{check.remedies}")

    def test_boost_remedy_names_series(self):
        # 曝光 100μs + TPS（无增亮）→ 增亮能力缺失，修法应点名 SPS/BPS
        cam = select_camera(fov_w=40, fov_h=33, accuracy=0.01,
                            moving=True, speed=100)   # 曝光上限 100μs
        lens = select_lens(sensor_w=cam.sensor_w, sensor_h=cam.sensor_h,
                           fov_w=40, fov_h=33, wd=300, pixel_um=cam.pixel_um)
        light = recommend_light("表面划痕", 40, 33)
        ctrl = select_controller(light_channels=1, channel_power_w=10,
                                 need_time_sequence=True,
                                 exposure_max_us=cam.exposure_max_us)
        val = validate(camera=cam, lens=lens, light=light, controller=ctrl,
                       accuracy=0.01, moving=True, speed=100,
                       fov_w=40, fov_h=33, wd_expect=300)
        attach_remedies(val, cam, lens, light, ctrl, accuracy=0.01,
                        moving=True, speed=100, fov_w=40, fov_h=33, wd_expect=300)
        check = next(c for c in val.checks if c.name == "增亮能力缺失")
        self.assertEqual(check.status, "fail")
        self.assertTrue(any("SPS" in r for r in check.remedies))


class TestLensAndLightRemedy(unittest.TestCase):

    def test_light_size_remedy(self):
        # 错配场景：光源按 12×10 视野选型，自检按 20×15 视野校验 → 覆盖不足
        # （正常流水线两者同源不会触发，此用例暴露修法公式本身）
        cam = select_camera(fov_w=20, fov_h=15, accuracy=0.05)
        lens = select_lens(sensor_w=cam.sensor_w, sensor_h=cam.sensor_h,
                           fov_w=20, fov_h=15, wd=300, pixel_um=cam.pixel_um)
        light = recommend_light("表面划痕", 12, 10)
        ctrl = select_controller(light_channels=1, channel_power_w=10)
        val = validate(camera=cam, lens=lens, light=light, controller=ctrl,
                       accuracy=0.05, fov_w=20, fov_h=15, wd_expect=300)
        attach_remedies(val, cam, lens, light, ctrl, accuracy=0.05,
                        fov_w=20, fov_h=15, wd_expect=300)
        check = next(c for c in val.checks if c.name == "光源覆盖不足")
        self.assertEqual(check.status, "fail")
        self.assertTrue(
            any("24.0×18.0" in r for r in check.remedies),
            f"修法应含 20×1.2 / 15×1.2 = 24.0×18.0：{check.remedies}")

    def test_wd_remedy_picks_better_focal_tier(self):
        # 40×33 @ 0.05、限高 80mm：β = 0.211，
        # 16mm 档 → WD = 16/0.211 ≈ 75.8mm，最接近 80
        val, cam, lens = _pipeline(40, 33, 0.05, wd=80)
        check = next(c for c in val.checks if c.name == "工作距离偏离")
        self.assertEqual(check.status, "warn")
        beta = lens.magnification
        best_wd = 16 / beta
        self.assertTrue(
            any("16 mm 档" in r for r in check.remedies),
            f"修法应推荐 16mm 档：{check.remedies}")
        self.assertTrue(
            any(f"WD ≈ {best_wd:.0f}" in r for r in check.remedies),
            f"修法应含反算 WD ≈ {best_wd:.0f}：{check.remedies}")


class TestNoRemedyOnPass(unittest.TestCase):

    def test_passing_checks_have_no_remedies(self):
        val, _, _ = _pipeline(12, 10, 0.01)
        for c in val.checks:
            if c.status == "pass":
                self.assertEqual(c.remedies, [],
                                 f"通过项不应挂修法：{c.name}")


if __name__ == "__main__":
    unittest.main(verbosity=2)

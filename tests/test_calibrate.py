"""图像诊断阈值自校准（calibrate / _grade）回归测试。

只测纯函数（_merged_thresholds / _grade / load 校验），不依赖 ffmpeg，
判级输入用合成指标字典——期望值可手工核对。
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.image_diag import (
    DEFAULT_THRESHOLDS, _merged_thresholds, _grade, load_thresholds, save_thresholds,
)


def _m(**over):
    """合成一张"好图"的指标，按需覆盖。"""
    base = {
        "width": 1000, "height": 800, "mean": 120.0, "std": 45.0,
        "gray_diff": 80.0, "overexposed_ratio": 0.005,
        "underexposed_ratio": 0.0, "lap_var": 250.0,
        "strong_edge_ratio": 0.02, "otsu_threshold": 100,
        "steps": [],
    }
    base.update(over)
    return base


class TestGradeWithDefaults(unittest.TestCase):
    """默认阈值下，判级行为应与原版手写阈值完全一致。"""

    def test_good_image_passes(self):
        grade, issues, notes = _grade(_m(), dict(DEFAULT_THRESHOLDS))
        self.assertEqual(grade, "合格")
        self.assertEqual(issues, [])

    def test_moderate_gray_diff_is_borderline(self):
        # 灰度差 25：20 < 25 < 30 → 临界（issue 不 severe）
        grade, issues, _ = _grade(_m(gray_diff=25.0), dict(DEFAULT_THRESHOLDS))
        self.assertEqual(grade, "临界")
        self.assertTrue(any("灰度差" in i for i in issues))

    def test_low_gray_diff_fails(self):
        # 灰度差 15 < 20（严重级）→ 不合格
        grade, issues, _ = _grade(_m(gray_diff=15.0), dict(DEFAULT_THRESHOLDS))
        self.assertEqual(grade, "不合格")

    def test_severe_levels_match_original_constants(self):
        t = dict(DEFAULT_THRESHOLDS)
        # 过曝 0.05：0.03 < 0.05 < 0.10 → notes（临界），不 severe
        grade, _, notes = _grade(_m(overexposed_ratio=0.05), t)
        self.assertEqual(grade, "合格", "过曝 5% 只应是提示，不影响判级")
        # 过曝 0.15 > 0.10 → severe
        grade, issues, _ = _grade(_m(overexposed_ratio=0.15), t)
        self.assertEqual(grade, "不合格")


class TestGradeWithCalibratedThresholds(unittest.TestCase):

    def test_calibrated_gray_diff_relaxes_grade(self):
        # 用户产线灰度差普遍低（校准阈值 20）：灰度差 25 从"临界"变"合格"
        t = _merged_thresholds({"gray_diff": 20.0})
        grade, issues, _ = _grade(_m(gray_diff=25.0), t)
        self.assertEqual(grade, "合格")

    def test_calibrated_gray_diff_tightens_grade(self):
        # 高对比产线（校准阈值 60）：灰度差 45 从"合格"变"临界"
        t = _merged_thresholds({"gray_diff": 60.0})
        grade, issues, _ = _grade(_m(gray_diff=45.0), t)
        self.assertEqual(grade, "临界")

    def test_calibrated_lap_threshold(self):
        # lap_var 10 + 有强边缘：默认（15）判离焦 severe；
        # 校准阈值 5 时 → 10 ≥ 5 不触发，且软级 5×8/15≈2.67 也不触发
        t = _merged_thresholds({"lap_hard": 5.0})
        grade, issues, _ = _grade(_m(lap_var=10.0), t)
        self.assertEqual(grade, "合格")

    def test_calibrated_over_threshold(self):
        # 过曝 0.08：默认 note；校准 over_soft=0.2 → 硬级 0.67，无任何提示
        t = _merged_thresholds({"over_soft": 0.2})
        grade, issues, notes = _grade(_m(overexposed_ratio=0.08), t)
        self.assertEqual(grade, "合格")
        self.assertEqual(notes, [])


class TestMergedAndLoad(unittest.TestCase):

    def test_merged_keeps_defaults_for_missing_keys(self):
        t = _merged_thresholds({"gray_diff": 50.0})
        self.assertEqual(t["gray_diff"], 50.0)
        self.assertEqual(t["over_soft"], DEFAULT_THRESHOLDS["over_soft"])
        self.assertEqual(t["lap_hard"], DEFAULT_THRESHOLDS["lap_hard"])

    def test_merged_none_returns_defaults(self):
        self.assertEqual(_merged_thresholds(None), dict(DEFAULT_THRESHOLDS))

    def test_save_load_roundtrip(self):
        thresholds = {"gray_diff": 42.0, "over_soft": 0.05, "lap_hard": 20.0,
                      "source": "校准组（好 4 / 差 4 张）"}
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "thresholds.json")
            save_thresholds(thresholds, p)
            loaded = load_thresholds(p)
        self.assertEqual(loaded["gray_diff"], 42.0)
        self.assertEqual(loaded["source"], "校准组（好 4 / 差 4 张）")

    def test_load_rejects_invalid_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "bad.json")
            with open(p, "w", encoding="utf-8") as f:
                f.write('{"foo": 1}')
            with self.assertRaises(ValueError):
                load_thresholds(p)


if __name__ == "__main__":
    unittest.main(verbosity=2)

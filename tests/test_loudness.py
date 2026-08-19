import unittest
from audio_editor.services import processor
from app import normalization_targets


class LoudnessFilterTests(unittest.TestCase):
    def test_batch_filter_always_limits_peak(self):
        filters = processor._batch_filters(12, 0, 0, 0, 0)
        self.assertTrue(filters[-1].startswith("alimiter="))

    def test_loudnorm_second_pass_does_not_force_linear_mode(self):
        # Dynamic mode is allowed when LRA/true-peak constraints demand it.
        self.assertNotIn("linear=true", processor.level_folder.__code__.co_consts)

    def test_friendly_normalization_parameters_remain_api_compatible(self):
        self.assertEqual(normalization_targets({"volume_style": "soft", "dynamics_style": "uniform"}), (-16.0, 7.0))
        self.assertEqual(normalization_targets({"target_lufs": -13, "target_lra": 9}), (-13.0, 9.0))

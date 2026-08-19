import unittest
from pathlib import Path

from audio_editor.services.processor import _audio_codec_args, _output_path


class ProcessorSafetyTests(unittest.TestCase):
    def test_replace_keeps_original_container_extension(self):
        source = Path("/music/track.flac")
        output = _output_path(source, source.parent, "nivelado", mode="replace")
        self.assertEqual(output.suffix, ".flac")

    def test_new_output_uses_requested_format(self):
        source = Path("/music/track.wav")
        output = _output_path(source, Path("/exports"), "editado", mode="new", extension="mp3")
        self.assertEqual(output.suffix, ".mp3")

    def test_lossless_codecs_are_not_replaced_with_mp3(self):
        self.assertEqual(_audio_codec_args("flac", "192k"), ["-c:a", "flac"])
        self.assertEqual(_audio_codec_args("wav", "192k"), ["-c:a", "pcm_s24le"])

#!/usr/bin/env python3
"""Lock the STT anti-hallucination filter: silence/noise must yield nothing,
clear speech must survive. Runs with plain stdlib unittest (no faster-whisper,
no model, no audio) against synthetic segment objects."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common import earbox_core as core  # noqa: E402


class Seg:
    def __init__(self, text, no_speech_prob=0.0, avg_logprob=0.0):
        self.text = text
        self.no_speech_prob = no_speech_prob
        self.avg_logprob = avg_logprob


CFG = dict(core.DEFAULTS)


class FilterTest(unittest.TestCase):
    def kept(self, segments):
        return core.filter_segments(CFG, segments)

    def test_high_no_speech_prob_dropped(self):
        self.assertEqual(self.kept([Seg("On va au marché demain", no_speech_prob=0.92)]), [])

    def test_low_avg_logprob_dropped(self):
        self.assertEqual(self.kept([Seg("Bonjour tout le monde", avg_logprob=-1.7)]), [])

    def test_blacklisted_phrase_dropped(self):
        for ghost in ["Merci d'avoir regardé la vidéo",
                      "C'est ça", "S'il vous plaît", "Sssshhh",
                      "Sous-titres réalisés par la communauté d'Amara.org"]:
            self.assertEqual(self.kept([Seg(ghost, no_speech_prob=0.1, avg_logprob=-0.3)]),
                             [], ghost)

    def test_repeated_short_token_dropped(self):
        self.assertEqual(self.kept([Seg("ça ça ça ça", avg_logprob=-0.4)]), [])

    def test_near_empty_dropped(self):
        for junk in ["", ".", "...", "  ", "?!"]:
            self.assertEqual(self.kept([Seg(junk)]), [], repr(junk))

    def test_clear_speech_kept(self):
        text = "On se retrouve à midi devant la boulangerie"
        seg = Seg(text, no_speech_prob=0.08, avg_logprob=-0.25)
        self.assertEqual(self.kept([seg]), [text])

    def test_silent_room_batch_yields_nothing(self):
        segs = [Seg("C'est ça", no_speech_prob=0.7)] * 7 + [
            Seg("Merci d'avoir regardé la vidéo", no_speech_prob=0.8)] * 2 + [
            Seg("Sssshhh"), Seg("S'il vous plaît", no_speech_prob=0.9)]
        self.assertEqual(self.kept(segs), [])

    def test_repetition_loop_collapsed_in_clean(self):
        loop = "c'est ça c'est ça c'est ça c'est ça c'est ça"
        out = core.clean_transcript(loop, cfg=CFG)
        self.assertNotIn("c'est ça c'est ça", out.lower())

    def test_mixed_batch_keeps_only_real_speech(self):
        segs = [
            Seg("C'est ça", no_speech_prob=0.75),
            Seg("Tu peux passer chercher le pain", no_speech_prob=0.1, avg_logprob=-0.3),
            Seg("Merci d'avoir regardé la vidéo", no_speech_prob=0.2, avg_logprob=-0.2),
            Seg("bla", no_speech_prob=0.1, avg_logprob=-1.9),
        ]
        self.assertEqual(self.kept(segs), ["Tu peux passer chercher le pain"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

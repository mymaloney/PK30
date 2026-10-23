"""Strength's boulder dust (engine/overworld/ssanne.asm AnimateBoulderDust):
it runs in every facing direction and comes back. Its OAM helpers are reached
with jp hl, so they must be in its own bank; when the file left bank $1E the
helpers stayed behind and every boulder pushed froze the game."""

import unittest

from harness import shared_game

FACINGS = {"down": 0, "up": 4, "left": 8, "right": 12}


class BoulderDustTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.game = shared_game()

    def test_helpers_in_the_same_bank(self):
        g = self.game
        bank = g.symbols["AnimateBoulderDust"][0]
        for name in ("DustAdjustOAMBlockXPos", "DustAdjustOAMBlockYPos"):
            self.assertEqual(g.symbols[name][0], bank, name)

    def test_every_direction_returns(self):
        g = self.game
        for direction, facing in FACINGS.items():
            with self.subTest(direction=direction):
                g.reset()
                g.skip_delays()
                g.poke("wSpriteStateData1+9", facing)
                g.call("AnimateBoulderDust", max_frames=600)


if __name__ == "__main__":
    unittest.main()

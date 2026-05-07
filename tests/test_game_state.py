import unittest

from game_state import CHOICES, MAX_WEEKS, GameState, weekly_event


class GameStateTest(unittest.TestCase):
    def test_choice_application_clamps_stats(self):
        state = GameState(stress=98, health=2)
        CHOICES[4].effect(state)
        self.assertLessEqual(state.stress, 100)
        self.assertGreaterEqual(state.health, 0)

    def test_finish_week_advances_and_charges_bills(self):
        state = GameState(cash=1000)
        expected_cash = state.cash - state.week_costs
        state.finish_week()
        self.assertEqual(state.week, 2)
        self.assertEqual(state.cash, expected_cash)

    def test_community_can_unlock_cosigner_help(self):
        state = GameState(community=35)
        network = next(choice for choice in CHOICES if choice.title == "Build community network")
        network.effect(state)
        self.assertIn("cosigner_help", state.flags)

    def test_weekly_events_rotate(self):
        state = GameState(week=1, cash=1000)
        message = weekly_event(state)
        self.assertTrue(message)
        self.assertNotEqual(state.cash, 1000)

    def test_default_game_not_over_before_final_week(self):
        state = GameState(week=MAX_WEEKS)
        self.assertFalse(state.is_over)
        state.week = MAX_WEEKS + 1
        self.assertTrue(state.is_over)


if __name__ == "__main__":
    unittest.main()

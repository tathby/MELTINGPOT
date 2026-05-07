import unittest

from game_state import CHOICES, MAX_WEEKS, GameState, weekly_event


class GameStateTest(unittest.TestCase):
    def test_choice_application_clamps_visible_stats(self):
        state = GameState(health=2, community=99, legal=99)
        CHOICES[4].effect(state)
        self.assertGreaterEqual(state.health, 0)
        self.assertLessEqual(state.community, 100)
        self.assertLessEqual(state.legal, 100)

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

    def test_language_unlocks_translated_assistance_choice(self):
        state = GameState(language_lessons=1)
        translated = next(choice for choice in CHOICES if choice.title == "Use translated assistance")
        self.assertFalse(translated.requirement(state))
        state.apply(language=1)
        self.assertTrue(translated.requirement(state))

    def test_weekly_events_are_less_punishing_and_rotate(self):
        state = GameState(week=1, cash=1000, health=88)
        message = weekly_event(state)
        self.assertTrue(message)
        self.assertGreaterEqual(state.cash, 925)
        self.assertGreaterEqual(state.health, 86)

    def test_default_game_not_over_before_final_week(self):
        state = GameState(week=MAX_WEEKS)
        self.assertFalse(state.is_over)
        state.week = MAX_WEEKS + 1
        self.assertTrue(state.is_over)


if __name__ == "__main__":
    unittest.main()

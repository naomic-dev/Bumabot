import copy
import unittest

import Adventure


class AdventureTests(unittest.TestCase):
    def setUp(self):
        self.game = Adventure.Adventure()
        self.game.add_player("Tester")
        self.player = self.game.player_list["Tester"]
        self.boss = self.game.boss_list[0]

    def test_boss_description_is_kept(self):
        self.assertEqual(self.boss.description, "A normal rat.")

    def test_add_drop_appends_to_list(self):
        self.boss.add_drop(Adventure.GOLD_COIN)

        self.assertIn(Adventure.GOLD_COIN, self.boss.drops)

    def test_attack_requires_the_dungeon(self):
        result = self.game.attack_phase(self.player, self.boss)

        self.assertIn("There's no one to attack.", list(result)[0])

    def test_dead_player_cannot_attack(self):
        self.game.go_to_location(Adventure.Locations.dungeon)
        self.player.current_health = 0

        result = self.game.attack_phase(self.player, self.boss)

        self.assertIn("cannot attack while you are dead", list(result)[0])

    def test_killing_a_boss_credits_the_player(self):
        self.game.go_to_location(Adventure.Locations.dungeon)
        self.boss.current_health = 1
        self.player.attack_roll = lambda: 100
        self.boss.attack_roll = lambda: 1

        result = self.game.attack_phase(self.player, self.boss)

        self.assertTrue(any("has died" in line for line in result))
        self.assertEqual(self.boss.current_health, 0)
        self.assertEqual(self.player.kills, 1)

    def test_loot_distribution_gives_items_to_credited_players(self):
        item = Adventure.Item("Test Coin", 1000, "A test item.")
        self.boss.drops = [item]
        self.boss.add_player_to_credit_list(self.player)

        result = self.boss.distribute_loot(self.game.player_list)

        self.assertIn("Test Coin", result)
        self.assertEqual(len(self.player.inventory), 1)
        self.assertEqual(self.player.inventory[0].name, "Test Coin")

    def test_town_revives_the_party(self):
        self.player.current_health = 0

        self.game.go_to_location(Adventure.Locations.town)

        self.assertEqual(self.player.current_health, self.player.max_health)

    def test_equip_and_unequip_update_equipment(self):
        self.player.inventory.append(copy.deepcopy(Adventure.TRAINING_SWORD))

        self.assertIn("You have equipped", self.player.equip("practice sword"))
        self.assertIsNotNone(self.player.weapon)
        self.assertIn("Practice Sword", self.player.get_equipment())

        self.assertIn("You have unequipped", self.player.unequip("practice sword"))
        self.assertIsNone(self.player.weapon)

    def test_item_info_includes_the_item_type(self):
        self.player.inventory.append(copy.deepcopy(Adventure.TRAINING_SWORD))
        self.player.equip("practice sword")

        info = self.player.item_info("practice sword")

        self.assertIn("(Weapon)", info)
        self.assertIn("drop chance", info)


if __name__ == "__main__":
    unittest.main()

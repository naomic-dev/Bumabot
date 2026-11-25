"""Experimental party-based dungeon crawler used by the chat bot.

The bot starts a minimal adventure from chat with `!adventure start`.
"""

from __future__ import annotations

import copy
import datetime
import enum
import logging
import random
import time
from collections import deque
from typing import Deque, Dict, Optional

log = logging.getLogger(__name__)


class Adventure:
    """A party-based dungeon crawler state machine."""

    def __init__(self) -> None:
        self.start_time = time.strftime("%m/%d/%Y %I:%M:%S %p")
        self.player_list = {}
        self.level_counter = 0
        self.boss_list = []

        self.location = None
        self.location_time = None

        self.init_bosses()

    def go_to_location(self, location: Locations) -> Optional[str]:
        """Move the party and return the narration."""
        self.location = location
        self.location_time = datetime.datetime.now()

        if location == Locations.town:
            for player in self.player_list.values():
                self.revive(player.name)

            for boss in self.boss_list:
                boss.current_health = boss.max_health
                boss.credit_list = []

            return "The party finds itself in a peaceful mountain town. After a brief rest to rally their strength, the party will depart."
        elif location == Locations.dungeon:
            boss_name = self.boss_list[self.level_counter].name

            suffix = ""

            if boss_name[:1].lower() in ["a", "e", "i", "o", "u"]:
                suffix = "n"

            return "The party has entered a dungeon. A{} {} has appeared.".format(suffix, boss_name)

    def add_player(self, username: str) -> None:
        """Add a player to the party."""
        player = Player(copy.copy(username))
        self.player_list[username] = player

    def attack_phase(self, attacker: Character, defender: Character) -> Deque[str]:
        """Resolve one attack and return the messages to send."""
        return_list = deque([])

        if (
            self.location == Locations.dungeon
            and attacker.current_health > 0
            and (
                (
                    attacker.last_attack_time is None
                    or datetime.datetime.now()
                    >= (attacker.last_attack_time + datetime.timedelta(0, 5))
                )
                if type(attacker) is Player
                else True
            )
        ):
            if type(attacker) is Player:
                attacker.last_attack_time = datetime.datetime.now()

            attacker_roll = attacker.attack_roll()
            log.debug("Attacker (%s) rolled a %s", attacker.name, attacker_roll)

            defender_roll = defender.attack_roll()
            log.debug("Defender (%s) rolled a %s", defender.name, defender_roll)

            if attacker_roll > defender_roll:
                defense_modifier = 0

                if type(defender) is Player:
                    if defender.helm is not None:
                        defense_modifier += defender.helm.modifier
                    if defender.armor is not None:
                        defense_modifier += defender.armor.modifier

                damage = attacker_roll - (defender_roll + defense_modifier)

                if damage < 0:
                    damage = 0

                defender.current_health -= damage

                if type(defender) is Boss and type(attacker) is Player:
                    defender.add_player_to_credit_list(attacker)

                return_list.append(
                    "{} attacked {} for {} damage.".format(attacker.name, defender.name, damage)
                )
            else:
                return_list.append(
                    "{} attacked {} and missed.".format(attacker.name, defender.name)
                )

            if defender.current_health <= 0:
                defender.current_health = 0

                attacker.kills += 1

                return_list[0] += " {} has died. ".format(defender.name)

                if type(defender) is Boss:
                    return_list.append(defender.distribute_loot(self.player_list) + " ")

                    if ((self.level_counter + 1) % 5) == 0:
                        self.level_counter = 0
                        self.boss_list = []
                        self.init_bosses()
                        return_list.append(self.go_to_location(Locations.town))
                    else:
                        return_list.append(self.go_to_next_level())
                elif type(defender) is Player:
                    defender.deaths += 1

                    if type(attacker) is Boss and defender.name in attacker.credit_list:
                        attacker.credit_list.remove(defender.name)

                    party_wipe = True

                    for player_name, player in self.player_list.items():
                        if player.current_health > 0:
                            party_wipe = False

                    if party_wipe:
                        return_list.append("The party has been defeated!")
                        self.level_counter = self.level_counter - (self.level_counter % 5)
                        return_list.append(self.go_to_location(Locations.town))
        elif self.location != Locations.dungeon:
            return_list.append("{} There's no one to attack.".format(attacker.name))
        elif attacker.current_health <= 0 and type(attacker) is Player:
            return_list.append("{} You cannot attack while you are dead.".format(attacker.name))

        return return_list

    def go_to_next_level(self) -> str:
        """Advance to the next boss and return its entrance line."""
        self.level_counter += 1

        if self.level_counter >= len(self.boss_list):
            self.level_counter = 0
            self.boss_list = []
            self.init_bosses()

        boss_name = self.boss_list[self.level_counter].name

        suffix = ""

        if boss_name[:1].lower() in ["a", "e", "i", "o", "u"]:
            suffix = "n"

        return "A{} {} has appeared.".format(suffix, boss_name)

    def init_bosses(self) -> None:
        """Create the default boss list."""
        # Rat
        rat = Boss("Rat", 1, 1, 2, "A normal rat.")
        rat.drops = [RAT_FUR]

        # Large Rat
        large_rat = Boss("Large Rat", 2, 1, 1, "A normal rat. Larger than average.")
        large_rat.drops = [RAT_FUR]

        # Rat Knight
        rat_knight = Boss("Rat Knight", 3, 2, 1, "A normal rat, armed with sword and shield.")
        rat_knight.drops = [RAT_SWORD, RAT_HELM]

        # Rat Mystic
        rat_mystic = Boss("Rat Mystic", 3, 2, 1, "A normal rat, armed with sword and shield.")
        rat_mystic.drops = [RAT_RING, OCCULT_CHARM]

        # Rat Lord
        rat_lord = Boss("Rat Lord", 5, 2, 3, "The lord of all rats.")
        rat_lord.drops = [GOLD_COIN, RAT_CROSSBOW]

        self.boss_list.append(rat)
        self.boss_list.append(large_rat)
        self.boss_list.append(rat_knight)
        self.boss_list.append(rat_mystic)
        self.boss_list.append(rat_lord)

    def revive(self, player_name: str) -> str:
        """Restore a player to full health."""
        return_text = ""

        if player_name in self.player_list:
            player = self.player_list[player_name]

            if player.current_health != player.max_health:
                player.current_health = player.max_health
                return_text = "{} has been revived.".format(player_name)
            else:
                return_text = "{} is already alive!".format(player_name)
        else:
            return_text = "{} isn't playing!".format(player_name)

        return return_text


class Character:
    """Base character with health, attack, and speed."""

    def __init__(self, name: str, health: int, attack: int, speed: int) -> None:
        # Stats
        self.name = name
        self.max_health = health
        self.current_health = health
        self.attack = attack
        self.speed = speed
        self.kills = 0
        self.last_attack_time = None

    def attack_roll(self, weapon_modifier: int) -> int:
        """Roll an attack."""
        base_attack = 0

        for x in range(0, self.attack):
            base_attack += random.randint(1, 6)

        return base_attack + weapon_modifier


class Boss(Character):
    """A boss with a drop table and damage credit list."""

    def __init__(self, name: str, health: int, attack: int, speed: int, description: str) -> None:
        super().__init__(name, health, attack, speed)

        # Stats
        self.description = description

        # List of players who dealt damage to this character
        self.credit_list = []

        # Drops
        self.drops = []

    def add_drop(self, loot: Item) -> None:
        """Add an item to the boss's drop table."""
        self.drops.append(loot)

    def attack_roll(self) -> int:
        """Roll an attack."""
        return super().attack_roll(0)

    def add_player_to_credit_list(self, player: Player) -> None:
        """Record a player who damaged the boss."""
        if player.name not in self.credit_list:
            self.credit_list.append(copy.copy(player.name))

    def distribute_loot(self, player_list: Dict[str, Player]) -> str:
        """Roll drops for credited players and summarize them."""
        return_text = ""

        # For each player who did damage to the boss
        for player in self.credit_list:
            # If that player is still playing and they're still alive
            if player in player_list and player_list[player].current_health > 0:
                # Check each item in the boss's drop list to see if that user picks it up
                for item in self.drops:
                    # Rarity range is 1 to 1000, functionally giving items a drop chance range from .1% to 100%
                    if random.randint(1, 1000) <= item.rarity:
                        player_list[player].inventory.append(copy.deepcopy(item))

                        suffix = ""

                        if item.name[:1].lower() in ["a", "e", "i", "o", "u"]:
                            suffix = "n"

                        return_text += "{} got a{} {}! ".format(player, suffix, item.name)

        return return_text.strip()


class Player(Character):
    """A party member with equipment and an inventory."""

    def __init__(self, name: str) -> None:
        super().__init__(name, 10, 1, 1)

        # Stats
        self.deaths = 0

        # Equips
        self.helm = None
        self.armor = None
        self.weapon = None

        # Inventory
        self.inventory = []

    def attack_roll(self) -> int:
        """Roll an attack."""
        weapon_modifier = self.weapon.modifier if self.weapon is not None else 0

        return super().attack_roll(weapon_modifier)

    def get_status(self) -> str:
        """Return a one-line status summary."""
        return "{} Status: {}, HP: {}/{}, ATK: {}, SPD: {}, Kills: {}, Deaths: {} ".format(
            self.name,
            "OK" if self.current_health > 0 else "DEAD",
            self.current_health,
            self.max_health,
            self.attack,
            self.speed,
            self.kills,
            self.deaths,
        )

    def get_inventory(self) -> str:
        """Return a one-line inventory summary."""
        inventory_count = len(self.inventory)

        return_text = "{} Inventory ({}): ".format(self.name, inventory_count)

        if inventory_count > 0:
            for index, item in enumerate(self.inventory):
                return_text += "#{} {}, ".format(index + 1, item.name)

            return_text = return_text.strip()
            return_text = return_text.strip(",")
        else:
            return_text += "EMPTY"

        return return_text

    def get_equipment(self) -> str:
        """Return a one-line equipment summary."""
        return "{} Weapon: {}, Helm: {}, Armor: {}".format(
            self.name,
            self.weapon.name if self.weapon is not None else "EMPTY",
            self.helm.name if self.helm is not None else "EMPTY",
            self.armor.name if self.armor is not None else "EMPTY",
        )

    def equip(self, item_name: str) -> str:
        """Equip an item from the inventory."""
        return_text = ""
        item_found = False

        for index, item in enumerate(self.inventory):
            if not item_found and item_name == item.name.lower():
                item_found = True

                if type(item) is Weapon:
                    if self.weapon is not None:
                        self.inventory.append(copy.deepcopy(self.weapon))
                    self.weapon = self.inventory.pop(index)
                    return_text = "{} You have equipped the {}.".format(self.name, item.name)
                elif type(item) is Helm:
                    if self.helm is not None:
                        self.inventory.append(copy.deepcopy(self.helm))
                    self.helm = self.inventory.pop(index)
                    return_text = "{} You have equipped the {}.".format(self.name, item.name)
                elif type(item) is Armor:
                    if self.armor is not None:
                        self.inventory.append(copy.deepcopy(self.armor))
                    self.armor = self.inventory.pop(index)
                    return_text = "{} You have equipped the {}.".format(self.name, item.name)
                else:
                    return_text = "{} That item cannot be equipped.".format(self.name)

        if not item_found:
            return_text = "{} That item is not in your inventory.".format(self.name)

        return return_text

    def unequip(self, item_name: str) -> str:
        """Move an equipped item back to the inventory."""
        return_text = ""

        if self.weapon is not None and self.weapon.name.lower() == item_name:
            temp_name = self.weapon.name
            self.inventory.append(copy.deepcopy(self.weapon))
            self.weapon = None
            return_text = "{} You have unequipped the {}.".format(self.name, temp_name)
        elif self.helm is not None and self.helm.name.lower() == item_name:
            temp_name = self.helm.name
            self.inventory.append(copy.deepcopy(self.helm))
            self.helm = None
            return_text = "{} You have unequipped the {}.".format(self.name, temp_name)
        elif self.armor is not None and self.armor.name.lower() == item_name:
            temp_name = self.armor.name
            self.inventory.append(copy.deepcopy(self.armor))
            self.armor = None
            return_text = "{} You have unequipped the {}.".format(self.name, temp_name)
        else:
            return_text = "{} You do not have that item equipped.".format(self.name)

        return return_text

    def item_info(self, item_name: str) -> str:
        """Return a description of a possessed item."""
        return_text = ""
        item_found = False
        full_name = ""
        item_type = ""
        description = ""
        drop_chance = ""

        if self.weapon is not None and self.weapon.name.lower() == item_name:
            item_found = True
            full_name = self.weapon.name
            item_type = "Weapon"
            description = self.weapon.description
            drop_chance = self.weapon.rarity
        elif self.helm is not None and self.helm.name.lower() == item_name:
            item_found = True
            full_name = self.helm.name
            item_type = "Helm"
            description = self.helm.description
            drop_chance = self.helm.rarity
        elif self.armor is not None and self.armor.name.lower() == item_name:
            item_found = True
            full_name = self.armor.name
            item_type = "Armor"
            description = self.armor.description
            drop_chance = self.armor.rarity

        for index, item in enumerate(self.inventory):
            if not item_found and item_name == item.name.lower():
                item_found = True

                if type(item) is Weapon:
                    item_type = "Weapon"
                elif type(item) is Helm:
                    item_type = "Helm"
                elif type(item) is Armor:
                    item_type = "Armor"
                else:
                    item_type = "Item"

                full_name = item.name
                description = item.description
                drop_chance = item.rarity

        if item_found:
            return_text = "{} {} ({}): {} {}% drop chance.".format(
                self.name, full_name, item_type, description, drop_chance / 10
            )
        else:
            return_text = "{} You do not possess that item.".format(self.name)

        return return_text


class Item:
    """A non-equippable inventory item."""

    def __init__(self, name: str, rarity: int, description: str) -> None:
        self.name = name
        self.rarity = rarity
        self.description = description


class Equipment(Item):
    """An item that can be equipped for a stat modifier."""

    def __init__(self, name: str, rarity: int, description: str, modifier: int) -> None:
        super().__init__(name, rarity, description)

        self.modifier = modifier


class Weapon(Equipment):
    """A weapon item."""

    def __init__(self, name: str, rarity: int, description: str, modifier: int) -> None:
        super().__init__(name, rarity, description, modifier)


class Helm(Equipment):
    """A helm item."""

    def __init__(self, name: str, rarity: int, description: str, modifier: int) -> None:
        super().__init__(name, rarity, description, modifier)


class Armor(Equipment):
    """An armor item."""

    def __init__(self, name: str, rarity: int, description: str, modifier: int) -> None:
        super().__init__(name, rarity, description, modifier)


# Locations
class Locations(enum.Enum):
    """Adventure locations."""

    town = 1
    dungeon = 2


# Items
RAT_FUR = Item("Clump of Rat Fur", 5, "A matted fistfull of rat hair.")
RAT_RING = Item(
    "Rat Ring",
    1,
    "An ornate ring. Some rats and mice like to wear these as necklaces. It might fit around your thumb.",
)
OCCULT_CHARM = Item(
    "Occult Charm", 1, "A small charm made of a carved rat tooth. There's something odd about it."
)
GOLD_COIN = Item("Gold Coin", 5, "A single gold coin.")

# Weapons
TRAINING_SWORD = Weapon("Practice Sword", 1000, "A sword designed for polishing one's skills.", 0)
RAT_SWORD = Weapon("Rat Sword", 1, "A sword fit for a rat.", 1)
RAT_CROSSBOW = Weapon(
    "Rat Crossbow", 1, "A crossbow with poison-tipped bolts. Fits nicely in your hand.", 3
)

# Helms
TRAINING_HELM = Helm("Training Helm", 1000, "A helm meant to be used during training.", 0)
RAT_HELM = Helm("Rat Helm", 10, "A helm fit for a rat.", 1)

# Armor
TRAINING_ARMOR = Armor(
    "Training Armor", 1000, "A breast plate meant to be used during training.", 0
)
RAT_ARMOR = Armor("Rat Armor", 1000, "Armor fit for a rat.", 1)

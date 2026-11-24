#NOTE: This is largely unfinished.
##I was in the process of working out the kinks when I got distractd by another project.

#Define a class that extends socket

#Imports
import datetime
import time
import enum
import random
import copy
from collections import deque

class Adventure():
	#################CONSTRUCTOR#################	
	def __init__(self):
		self.startTime = time.strftime("%m/%d/%Y %I:%M:%S %p")
		self.playerList = {}
		self.levelCounter = 0
		self.bossList = []
		
		self.location = None
		self.locationTime = None
		
		self.initBosses()
	#################CONSTRUCTOR#################
	
	def goToLocation(self, location):
		self.location = location
		self.locationTime = datetime.datetime.now()
		
		if location == Locations.town:
			for player in self.playerList.values():
				self.revive(player.name)
					
			for boss in self.bossList:
				boss.currentHealth = boss.maxHealth
				boss.creditList = []
					
			return "The party finds itself in a peaceful mountain town. After a brief rest to rally their strength, the party will depart."
		elif location == Locations.dungeon:
			bossName = self.bossList[self.levelCounter].name
		
			suffix = ""
							
			if bossName[:1].lower() in ["a", "e", "i", "o", "u"]:
				suffix = "n"
		
			return "The party has entered a dungeon. A{} {} has appeared.".format(suffix, bossName)
	
	def addPlayer(self, username):
		player = Player(copy.copy(username))
		self.playerList[username] = player
	
	def attackPhase(self, attacker, defender):
		returnList = deque([])
		
		if self.location == Locations.dungeon and attacker.currentHealth > 0 and ((attacker.lastAttackTime is None or datetime.datetime.now() >= (attacker.lastAttackTime + datetime.timedelta(0, 5))) if type(attacker) is Player else True):
			if type(attacker) is Player:
				attacker.lastAttackTime = datetime.datetime.now()
			
			attackerRoll = attacker.attackRoll()
			print("Attacker ({}) rolled a {}".format(attacker.name, attackerRoll))
			
			defenderRoll = defender.attackRoll()
			print("Defender ({}) rolled a {}".format(defender.name, defenderRoll))
			
			if attackerRoll > defenderRoll:
				defenseModifier = 0
				
				if type(defender) is Player:
					if defender.helm is not None:
						defenseModifier += defender.helm.modifier
					if defender.armor is not None:
						defenseModifier += defender.armor.modifier
			
				damage = attackerRoll - (defenderRoll + defenseModifier)
				
				if damage < 0:
					damage = 0
				
				defender.currentHealth -= damage
				
				if type(defender) is Boss and type(attacker) is Player:
					defender.addPlayerToCreditList(attacker)
				
				returnList.append("{} attacked {} for {} damage.".format(attacker.name, defender.name, damage))
			else:
				returnList.append("{} attacked {} and missed.".format(attacker.name, defender.name))
				
			if (defender.currentHealth <= 0):
				defender.currentHealth = 0
				
				attacker.kills += 1
				
				returnList[0] += " {} has died. ".format(defender.name)
				
				if type(defender) is Boss:
					returnList.append(defender.distributeLoot(self.playerList) + " ")
					returnList.append(self.goToLocation(Locations.town) if ((self.levelCounter + 1) % 5) == 0 else self.goToNextLevel())
				elif type(defender) is Player:
					defender.deaths += 1
					
					if type(attacker) is Boss and defender.name in attacker.creditList:
						attacker.creditList.remove(defender.name)
					
					partyWipe = True
					
					for playerName, player in self.playerList.items():
						if player.currentHealth > 0:
							partyWipe = False
							
					if partyWipe:
						returnList.append("The party has been defeated!")
						self.levelCounter = self.levelCounter - (self.levelCounter % 5)
						returnList.append(self.goToLocation(Locations.town))
		elif self.location != Locations.dungeon:
			returnList.append("{} There's no one to attack.".format(attacker.name))
		elif attacker.currentHealth <= 0 and type(attacker) is Player:
			returnList.append("{} You cannot attack while you are dead.".format(attacker.name))
			
		return returnList
		
	def goToNextLevel(self):
		self.levelCounter += 1
		
		if self.levelCounter >= len(self.bossList):
			self.levelCounter = 0
			self.bossList = []
			self.initBosses()
		
		bossName = self.bossList[self.levelCounter].name
		
		suffix = ""
						
		if bossName[:1].lower() in ["a", "e", "i", "o", "u"]:
			suffix = "n"
		
		return "A{} {} has appeared.".format(suffix, bossName)
		
	def initBosses(self):
		#Rat
		rat = Boss("Rat", 1, 1, 2, "A normal rat.")
		rat.drops = [ RAT_FUR ]
		
		#Large Rat
		largeRat = Boss("Large Rat", 2, 1, 1, "A normal rat. Larger than average.")
		largeRat.drops = [ RAT_FUR ]
		
		#Rat Knight
		ratKnight = Boss("Rat Knight", 3, 2, 1, "A normal rat, armed with sword and shield.")
		ratKnight.drops = [
			RAT_SWORD,
			RAT_HELM
		]
		
		#Rat Mystic
		ratMystic = Boss("Rat Mystic", 3, 2, 1, "A normal rat, armed with sword and shield.")
		ratMystic.drops = [
			RAT_RING,
			OCCULT_CHARM
		]
		
		#Rat Lord
		ratLord = Boss("Rat Lord", 5, 2, 3, "The lord of all rats.")
		ratLord.drops = [
			GOLD_COIN,
			RAT_CROSSBOW
		]
		
		self.bossList.append(rat)
		self.bossList.append(largeRat)
		self.bossList.append(ratKnight)
		self.bossList.append(ratMystic)
		self.bossList.append(ratLord)
		
	def revive(self, playerName):
		returnText = ""
		
		if playerName in self.playerList:
			player = self.playerList[playerName]
			
			if player.currentHealth != player.maxHealth:
				player.currentHealth = player.maxHealth
				returnText = "{} has been revived.".format(playerName)
			else:
				returnText = "{} is already alive!".format(playerName)
		else:
			returnText = "{} isn't playing!".format(playerName)
		
		return returnText
		
class Character():
	#################CONSTRUCTOR#################	
	def __init__(self, name, health, attack, speed):
		#Stats
		self.name = name
		self.maxHealth = health
		self.currentHealth = health
		self.attack = attack
		self.speed = speed
		self.kills = 0
		self.lastAttackTime = None
	#################CONSTRUCTOR#################
	
	def attackRoll(self, weaponModifier):
		baseAttack = 0
		
		for x in range(0, self.attack):
			baseAttack += random.randint(1, 6)
		
		return baseAttack + weaponModifier
	
class Boss(Character):
	#################CONSTRUCTOR#################	
	def __init__(self, name, health, attack, speed, description):
		super().__init__(name, health, attack, speed)
	
		#Stats
		self.description = description
		
		#List of players who dealt damage to this character
		self.creditList = []
		
		#Drops
		self.drops = []
	#################CONSTRUCTOR#################
	
	def addDrop (self, loot):
		self.drops.append(loot)
	
	def attackRoll(self):
		return super().attackRoll(0)
		
	def addPlayerToCreditList(self, player):
		if player.name not in self.creditList:
			self.creditList.append(copy.copy(player.name))
			
	def distributeLoot(self, playerList):
		returnText = ""
		
		#For each player who did damage to the boss
		for player in self.creditList:
			#If that player is still playing and they're still alive
			if player in playerList and playerList[player].currentHealth > 0:
				#Check each item in the boss's drop list to see if that user picks it up
				for item in self.drops:
					#Rarity range is 1 to 1000, functionally giving items a drop chance range from .1% to 100%
					if random.randint(1, 1000) <= item.rarity:
						playerList[player].inventory.append(copy.deepcopy(item))
						
						suffix = ""
						
						if item.name[:1].lower() in ["a", "e", "i", "o", "u"]:
							suffix = "n"
							
						returnText += "{} got a{} {}! ".format(player, suffix, item.name)
		
		return returnText.strip()
	
class Player(Character):
	#################CONSTRUCTOR#################	
	def __init__(self, name):
		super().__init__(name, 10, 1, 1)
		
		#Stats
		self.deaths = 0
		
		#Equips
		self.helm = None
		self.armor = None
		self.weapon = None
		
		#Inventory
		self.inventory = []
	#################CONSTRUCTOR#################
	
	def attackRoll(self):
		weaponModifier = self.weapon.modifier if self.weapon is not None else 0
		
		return super().attackRoll(weaponModifier)
		
	def getStatus(self):
		return "{} Status: {}, HP: {}/{}, ATK: {}, SPD: {}, Kills: {}, Deaths: {} ".format(self.name, "OK" if self.currentHealth > 0 else "DEAD", self.currentHealth, self.maxHealth, self.attack, self.speed, self.kills, self.deaths)
		
	def getInventory(self):
		inventoryCount = len(self.inventory)
	
		returnText = "{} Inventory ({}): ".format(self.name, inventoryCount)
		
		if inventoryCount > 0:
			for index, item in enumerate(self.inventory):
				returnText += "#{} {}, ".format(index + 1, item.name)
				
			returnText = returnText.strip()
			returnText = returnText.strip(",")
		else:
			returnText += "EMPTY"
			
		return returnText
		
	def getEquipment(self):
		return "{} Weapon: {}, Helm: {}, Armor: {}".format(self.name, self.weapon.name if self.weapon is not None else "EMPTY", self.helm.name if self.helm is not None else "EMPTY", self.armor.name if self.armor is not None else "EMPTY")
		
	def equip(self, itemName):
		returnText = ""
		itemFound = False
		
		for index, item in enumerate(self.inventory):
			if not itemFound and itemName == item.name.lower():
				itemFound = True
				
				if type(item) is Weapon:
					if self.weapon is not None:
						self.inventory.append(copy.deepcopy(self.weapon))
					self.weapon = self.inventory.pop(index)
					returnText = "{} You have equipped the {}.".format(self.name, item.name)
				elif type(item) is Helm:
					if self.helm is not None:
						self.inventory.append(copy.deepcopy(self.helm))
					self.helm = self.inventory.pop(index)
					returnText = "{} You have equipped the {}.".format(self.name, item.name)
				elif type(item) is Armor:
					if self.armor is not None:
						self.inventory.append(copy.deepcopy(self.armor))
					self.armor = self.inventory.pop(index)
					returnText = "{} You have equipped the {}.".format(self.name, item.name)
				else:
					returnText = "{} That item cannot be equipped.".format(self.name)
		
		if not itemFound:
			returnText = "{} That item is not in your inventory.".format(self.name)
			
		return returnText
		
	def unequip(self, itemName):
		returnText = ""
		
		if self.weapon is not None and self.weapon.name.lower() == itemName:
			tempName = self.weapon.name
			self.inventory.append(copy.deepcopy(self.weapon))
			self.weapon = None
			returnText = "{} You have unequipped the {}.".format(self.name, tempName)
		elif self.helm is not None and self.helm.name.lower() == itemName:
			tempName = self.helm.name
			self.inventory.append(copy.deepcopy(self.helm))
			self.helm = None
			returnText = "{} You have unequipped the {}.".format(self.name, tempName)
		elif self.armor is not None and self.armor.name.lower() == itemName:
			tempName = self.armor.name
			self.inventory.append(copy.deepcopy(self.armor))
			self.armor = None
			returnText = "{} You have unequipped the {}.".format(self.name, tempName)
		else:
			returnText = "{} You do not have that item equipped.".format(self.name)
			
		return returnText
		
	def itemInfo(self, itemName):
		returnText = ""
		itemFound = False
		fullName = ""
		itemType = ""
		description = ""
		dropChance = ""
		
		if self.weapon is not None and self.weapon.name.lower() == itemName:
			itemFound = True
			fullName = self.weapon.name
			itemType = "Weapon"
			description = self.weapon.description
			dropChance = self.weapon.rarity
		elif self.helm is not None and self.helm.name.lower() == itemName:
			itemFound = True
			fullName = self.helm.name
			itemType = "Helm"
			description = self.helm.description
			dropChance = self.helm.rarity
		elif self.armor is not None and self.armor.name.lower() == itemName:
			itemFound = True
			fullName = self.armor.name
			itemType = "Armor"
			description = self.armor.description
			dropChance = self.armor.rarity
		
		for index, item in enumerate(self.inventory):
			if not itemFound and itemName == item.name.lower():
				itemFound = True
				
				if type(item) is Weapon:
					itemType = "Weapon"
				elif type(item) is Helm:
					itemType = "Helm"
				elif type(item) is Armor:
					itemType = "Armor"
				else:
					itemType = "Item"
					
				fullName = item.name
				description = item.description
				dropChance = item.rarity
		
		if itemFound:
			returnText = "{} {} ({}): {} {}% drop chance.".format(self.name, fullName, itemType, description, dropChance / 10)
		else:
			returnText = "{} You do not possess that item.".format(self.name)
		
		return returnText
	
class Item():
	#################CONSTRUCTOR#################	
	def __init__(self, name, rarity, description):
		self.name = name
		self.rarity = rarity
		self.description = description
	#################CONSTRUCTOR#################
	
class Equipment(Item):
	#################CONSTRUCTOR#################	
	def __init__(self, name, rarity, description, modifier):
		super().__init__(name, rarity, description)
		
		self.modifier = modifier
	#################CONSTRUCTOR#################
	
class Weapon(Equipment):
	#################CONSTRUCTOR#################	
	def __init__(self, name, rarity, description, modifier):
		super().__init__(name, rarity, description, modifier)
	#################CONSTRUCTOR#################
	
class Helm(Equipment):
	#################CONSTRUCTOR#################	
	def __init__(self, name, rarity, description, modifier):
		super().__init__(name, rarity, description, modifier)
	#################CONSTRUCTOR#################
	
class Armor(Equipment):
	#################CONSTRUCTOR#################	
	def __init__(self, name, rarity, description, modifier):
		super().__init__(name, rarity, description, modifier)
	#################CONSTRUCTOR#################
	
#Locations
class Locations(enum.Enum):
	town = 1
	dungeon = 2
	
#Items
RAT_FUR = Item("Clump of Rat Fur", 5, "A matted fistfull of rat hair.")
RAT_RING = Item("Rat Ring", 1, "An ornate ring. Some rats and mice like to wear these as necklaces. It might fit around your thumb.")
OCCULT_CHARM = Item("Occult Charm", 1, "A small charm made of a carved rat tooth. There's something odd about it.")
GOLD_COIN = Item("Gold Coin", 5, "A single gold coin.")

#Weapons
TRAINING_SWORD = Weapon("Practice Sword", 1000, "A sword designed for polishing one's skills.", 0)
RAT_SWORD = Weapon("Rat Sword", 1, "A sword fit for a rat.", 1)
RAT_CROSSBOW = Weapon("Rat Crossbow", 1, "A crossbow with poison-tipped bolts. Fits nicely in your hand.", 3)

#Helms
TRAINING_HELM = Helm("Training Helm", 1000, "A helm meant to be used during training.", 0)
RAT_HELM = Helm("Rat Helm", 10, "A helm fit for a rat.", 1)

#Armor
TRAINING_ARMOR = Armor("Training Armor", 1000, "A breast plate meant to be used during training.", 0)
RAT_ARMOR = Armor("Rat Armor", 1000, "Armor fit for a rat.", 1)
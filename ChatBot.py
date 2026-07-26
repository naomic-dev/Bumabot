#Define a class that extends socket

#################Imports#################
import select
import socket
import datetime
import time
import random
from collections import deque
from twitchAPI.twitch import Twitch

#For Spotify integration
import spotipy.util as util

#Import local files
from Settings import HOST, PORT, PASS, NICK, CHANNEL, USERNAME_COLOR, SPEECH_MODE, SPOTIFY_USERNAME, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI, SPOTIFY_PLAYLIST_ID
import Memes
#################Imports#################

class ChatBot():
	#################CONSTRUCTOR#################	
	def __init__(self):
		self.host = HOST
		self.port = PORT
		self.password = PASS
		self.username = NICK
		self.channel = CHANNEL
		self.usernameColor = USERNAME_COLOR
		self.speechMode = SPEECH_MODE
		
		self.socket = socket.socket()
		
		#Store joined channels here, remove them when leaving, check on each leave to see if we should stop reading
		self.channelList = []
		
		self.adventureList = {}
				
		#Connect to Twitch IRC
		self.socket.connect((self.host, self.port))
		
		#Tell the server we'd like to see users' membership levels
		self.sendEncoded("CAP REQ :twitch.tv/membership")
		#Tell the server we'd like to see tags for users' messages
		self.sendEncoded("CAP REQ :twitch.tv/tags")
		
		#Send password
		self.sendEncoded("PASS {}".format(self.password))
		
		#Send username
		self.sendEncoded("NICK {}".format(self.username))
		
		self.joinChannel(self.channel)
		
		#Spotify stuff
		self.spotify = None
		self.currentTrack = None
		self.oauth = None
		
		self.initspotify()
		self.tokenexpiry = (datetime.datetime.now() + datetime.timedelta(hours = 1))
		
		self.botInfoSleepTimer = (datetime.datetime.now() + datetime.timedelta(minutes = 15))
		self.botInfoMessage = "Type !commands to see what orders you can give me.";
		
		self.selfPromotionSleepTimer = (datetime.datetime.now() + datetime.timedelta(minutes = 15))
		
		self.idleChatSleepTimer = (datetime.datetime.now() + datetime.timedelta(minutes = 10))
		self.idleMessages = [
			"Anyone in here?",
			"ResidentSleeper",
			"Dead chat SeemsGood",
			"Every day is TransgenderPride Pride Day TransgenderPride in this house",
			"PogChamp MODS ARE ASLEEP!! POST YOUR DANK MEMES PogChamp"
		]
		
		self.modSleepTimer = (datetime.datetime.now() + datetime.timedelta(minutes = 70))
	#################CONSTRUCTOR#################		
		
	#A function to join the chat room for a particular channel
	def joinChannel(self, channel):
		self.sendEncoded("JOIN #{}".format(channel))
		
		#Init read buffer. String containing information passed to/from socket
		readBuffer = ""
		
		#Init escape variable
		loading = True
		
		while loading:
			#Read information into the socket in 1024 bit (maybe byte) increments
			readBuffer = readBuffer + self.socket.recv(1024).decode()
			
			#Split the readBuffer into a stack, using linebreaks as a delimiter
			tempBuffer = readBuffer.split("\n")
			
			#Pop line off the top of the stack
			readBuffer = tempBuffer.pop()
			
			for line in tempBuffer:
				self.printWithTimestamp(line)
				
				#Test to see if initializing is finished
				loading = self.stillLoading(channel, line)
		
		self.changeUsernameColor(channel, self.usernameColor)
		self.channelList.append(channel)
		print("")
		
	#A function to test to see if a given line includes the string that Twitch uses to denote the end of initialization
	def stillLoading(self, channel, line):
		if("#{} :End of /NAMES list".format(channel) in line):
			return False
		else:
			return True
	
	#A function to leave the chat room for a particular channel
	def leaveChannel(self, channel):
		self.sendEncoded("PART #{}".format(channel))
		self.channelList.remove(channel)
	
	#A function to leave ALL chat rooms	
	def powerDown(self, username):
		#Leave the all rooms and finish the loop
		self.printWithTimestamp("COMMAND: Power Down ({})".format(username))
		
		#Create a copy of the channel list so we have a list to work from that won't be edited as we remove channels
		channelList = list(self.channelList)
		
		for channel in channelList:
			self.printWithTimestampAndChannel(channel, "Parting")
			self.printWithTimestamp("Powering down.")
			self.leaveChannel(channel)
			
		with open('spotify_now_playing.txt', 'w+') as file:
			file.write("")
		
	#A function to send some text to the chat server, using utf-8 encoding
	def sendEncoded(self, text):
		textWithNewLine = text + "\r\n"
		self.socket.send(textWithNewLine.encode("utf-8"))
	
	#A function to send a text message to a given channel's chat room
	def sendTextToChannel(self, channel, text):
		self.sendEncoded("PRIVMSG #{} :{}".format(channel, text))
		time.sleep(1.5)
	
	#A function to send a text message to the default chat room
	def sendTextToDefaultChat(self, text):
		#Format the message for IRC and send it
		self.sendTextToChannel(self.channel, text)
		
	#A function to send a request for all users in a given channel
	def getUsersInChannel(self, channel):
		self.sendEncoded("NAMES #{}".format(channel))
		
	#A function to change username color
	def changeUsernameColor(self, channel, color):
		self.sendTextToChannel(channel, "/color {}".format(color))
	
	#A function used to print text to the command window with a timestamp	
	def printWithTimestamp(self, text):
		print("[" + time.strftime("%m/%d/%Y %I:%M:%S %p") + "]" + text)
	
	#A function used to print text to the command window with a timestamp and the name of the channel the text is from
	def printWithTimestampAndChannel(self, channel, text):
		self.printWithTimestamp(("[CHANNEL:{}]".format(channel) if channel else "") + text)
	
	#A function to parse the channel name out of a line of text sent from the server	
	def getChannelFromLine(self, line):
		if "#" in line:
			#Split the line at the first instance of a pound sign
			splitLine = line.split("#", 1)
			#split the line again, but this time, split it along whitespace and return the first value
			return splitLine[1].split()[0]
		else:
			return False
	
	#A function to parse out some basic user info from the Twitch tags in a line sent from the server 	
	def parseLineTags(self, tags):
		color = ""
		username = ""
		broadcaster = False
		moderator = False
		subscriber = False
		
		if ";" in tags:
			splitTags = tags.split(";")
			
			for tag in splitTags:
				if "color=" in tag:
					color = tag.split("=")[1]
				elif "display-name=" in tag:
					username = tag.split("=")[1]
				elif "@badges=" in tag and "broadcaster/" in tag:
					broadcaster = True
				elif tag == "mod=1":
					moderator = True
				elif tag == "subscriber=1":
					subscriber = True
					
		return { "username":username, "broadcaster":broadcaster, "moderator":moderator, "subscriber":subscriber, "color":color }
		
	def initSpotify(self, refreshingToken=False):
		#Init Spotipy listening
		self.spotipyScope = "user-read-currently-playing playlist-modify-public"
		
		self.spotipyToken = util.prompt_for_user_token(SPOTIFY_USERNAME, self.spotipyScope, client_id=SPOTIFY_CLIENT_ID, client_secret=SPOTIFY_CLIENT_SECRET, redirect_uri=SPOTIFY_REDIRECT_URI)
		
		self.oauth = spotipy.oauth2.SpotifyOAuth(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI, scope=self.spotipyScope, cache_path=".cache-{}".format(SPOTIFY_USERNAME))
		
		self.spotify = spotipy.Spotify(auth=self.spotipyToken)
		self.currentTrack = self.parseCurrentTrackString(self.spotify.current_user_playing_track())
		
		if self.currentTrack is not None:
			with open('spotify_now_playing.txt', 'w+') as file:
				file.write("Listening to {}".format(self.parseCurrentTrackStringForOverlay(self.spotify.current_user_playing_track())))
		
		if not refreshingToken:
			self.printWithTimestamp("Spotify functionality enabled.")
		
	def updateSpotifyToken(self):
		if self.oauth is not None:
			tokenInfo = self.oauth.get_cached_token()
			
			if tokenInfo is not None and self.tokenExpiry <= datetime.datetime.now():
				newTokenInfo = self.oauth.refresh_access_token(tokenInfo["refresh_token"])
				self.spotipyToken = newTokenInfo["access_token"]
				self.spotify._auth = self.spotipyToken
				
				self.tokenExpiry = (datetime.datetime.now() + datetime.timedelta(hours = 1))
				self.printWithTimestamp("Refreshed Spotify token.")
			elif tokenInfo is None:
				self.printWithTimestamp("Token Info not found.")
		
	def parseCurrentTrackString(self, currentTrackString):
		if currentTrackString is not None and currentTrackString["is_playing"]:
			return "\"{}\" by {} {}".format(currentTrackString["item"]["name"], currentTrackString["item"]["artists"][0]["name"], currentTrackString["item"]["external_urls"]["spotify"])
		else:
			return None
	
	def updateCurrentTrack(self):
		try:
			tempCurrentTrack = self.parseCurrentTrackString(self.spotify.current_user_playing_track())
		
			if self.currentTrack != tempCurrentTrack:
				self.currentTrack = tempCurrentTrack
				
				with open('spotify_now_playing.txt', 'w+') as file:
					if self.currentTrack is not None:
						file.write("Listening to {}".format(self.parseCurrentTrackStringForOverlay(self.spotify.current_user_playing_track())))
					else:
						file.write("")
		except:
			tokenInfo = self.oauth.get_cached_token()
			
			if tokenInfo is None:
				self.initSpotify(True)
			else:
				newTokenInfo = self.oauth.refresh_access_token(tokenInfo["refresh_token"])
				self.spotipyToken = newTokenInfo["access_token"]
				self.spotify._auth = self.spotipyToken
				
			self.printWithTimestamp("Refreshed Spotify token.")
			
			tempCurrentTrack = self.parseCurrentTrackString(self.spotify.current_user_playing_track())
		
			if self.currentTrack != tempCurrentTrack:
				self.currentTrack = tempCurrentTrack
				
				with open('spotify_now_playing.txt', 'w+') as file:
					if self.currentTrack is not None:
						file.write("Listening to {}".format(self.parseCurrentTrackStringForOverlay(self.spotify.current_user_playing_track())))
					else:
						file.write("")						
			
	def printCurrentTrackToChat(self):
		if self.currentTrack is None:
			self.sendTextToChannel(CHANNEL, "Nothing is currently playing.")
		else:
			self.sendTextToChannel(CHANNEL, "Currently playing {}".format(self.currentTrack))
			self.printWithTimestamp(self.currentTrack)
			
	def searchForSpotifySong(self, query, username):
		if self.spotify is None:
			self.sendTextToChannel(CHANNEL, "Playlist functionality is currently off.")
		else:
			results = self.spotify.search(query, type="track", limit=5)
			
			if len(results["tracks"]["items"]) == 0:
				self.sendTextToChannel(CHANNEL, "{} No results found.".format(username))
			else:
				for result in results["tracks"]["items"]:
					self.sendTextToChannel(CHANNEL, "\"{}\" by {}. CODE: {}".format(result["name"], result["artists"][0]["name"], result["id"]))
			
	def searchAddSong(self, query, username):
		if self.spotify is None:
			self.sendTextToChannel(CHANNEL, "{} Playlist functionality is currently off.".format(username))
		else:
			results = self.spotify.search(query, type="track", limit=5)
			
			if len(results["tracks"]["items"]) == 1:
				self.addTrackToPlaylist(results["tracks"]["items"][0]["id"], username)
			elif len(results["tracks"]["items"]) == 0:
				self.sendTextToChannel(CHANNEL, "{} No results found.".format(username))
			else:
				self.sendTextToChannel(CHANNEL, "{} Too many results returned. Please choose one of the following and use \"!addsong\" command or narrow your search criteria.".format(username))
				
				for result in results["tracks"]["items"]:
					self.sendTextToChannel(CHANNEL, "\"{}\" by {}. CODE: {}".format(result["name"], result["artists"][0]["name"], result["id"]))
			
	def addTrackToPlaylist(self, track, username):
		if self.spotify is None:
			self.sendTextToChannel(CHANNEL, "{} Playlist functionality is currently off.".format(username))
		else:
			try:
				results = self.spotify.user_playlist_add_tracks(user=SPOTIFY_USERNAME, playlist_id=SPOTIFY_PLAYLIST_ID, tracks=[track])
			except:
				results = None
				
			if results is not None:
				self.sendTextToChannel(CHANNEL, "{} Added song to playlist.".format(username))
			else:
				self.sendTextToChannel(CHANNEL, "{} Invalid song code.".format(username))
		
	###############MEME FUNCTIONS################
	def unbenchKenchPassive(self, channel, lowercaseText):
		unbenchKench = False;
		kenchKeys = sorted(Memes.UNBENCH_KENCH.keys())
		
		for key in kenchKeys:
			if Memes.UNBENCH_KENCH[key].lower() in lowercaseText:
				unbenchKench = True;
				
		if unbenchKench:
			key = random.randint(0, (len(kenchKeys) - 1))
			self.sendTextToChannel(channel, Memes.UNBENCH_KENCH[kenchKeys[key]] + " OSFrog")
			
	def commandUnbenchKench(self, channel):
		outputString = ""
		
		for key, value in Memes.UNBENCH_KENCH.items():
			outputString += value + " OSFrog "
			
		self.sendTextToChannel(channel, outputString.strip())
	###############MEME FUNCTIONS################
	
	#A function to parse an individual line sent through the socket
	def parseLine(self, line):
		#Split the line into 3 parts, using ":" as the delimiter
		splitLine = line.split(":", 2)
		
		channel = self.getChannelFromLine(splitLine[1])
		userInfo = self.parseLineTags(splitLine[0])
		
		#Print the line with a time stamp and channel (if there is one) prepended
		self.printWithTimestampAndChannel(channel, line)
		
		#Declare a variable we'll use to check whether chat is idle or not
		resetIdleChatTimer = True
		
		if len(splitLine) == 2:
			if splitLine[0] == "PING ":
				#If the server sent an AFK check, print the response and a timestamp, then send the response
				self.printWithTimestamp("PONG :tni.twitch.tv")
				self.sendEncoded("PONG :tni.twitch.tv")
				resetIdleChatTimer = False
			elif "!" in splitLine[1]:
				username = splitLine[1].split("!", 1)[0]
				
				botList = ""
				with open('botlist.txt', 'r+') as file:
					botList = file.read()				
		elif len(splitLine) == 3:
			username = userInfo.get("username", "").lower()
			splitLine = line.split("{}!{}@{}.tmi.twitch.tv PRIVMSG #{} :".format(username, username, username, channel), 1)
			text = splitLine[1].strip()
			lowercaseText = text.lower()

			#Define commands for me
			if username == CHANNEL:
				resetIdleChatTimer = False
				
				if lowercaseText == "@{} shut down".format(self.username):
					self.shutDown()
				elif lowercaseText == "!playlist on":
					if self.spotify is None:
						self.initSpotify()
				elif lowercaseText == "!playlist off":
					self.spotify = None
					self.currentTrack = None
					self.oauth = None
			
			#Define commands for broadcaster			
			if userInfo.get("broadcaster", False):
				if lowercaseText == "@{} begone".format(self.username):
					self.leaveChannel(channel)
					self.printWithTimestampAndChannel(channel, "COMMAND: Exit Channel \"{}\" ({})".format(channel, userInfo["username"]))
					
			#Define commands for any user in any channel
			if channel and username != "":
				self.unbenchKenchPassive(channel, lowercaseText)
				
				if lowercaseText == "!commands":
					self.sendTextToChannel(channel, "!commands, !song, !addsong [Spotify Code], !searchsong [Search Criteria], !searchadd [Search Criteria], !unbench, !jebaited, !slownsteady, !sockpuppets, !sleeptest, !srstrouble, !clown")
					self.printWithTimestampAndChannel(channel, "COMMAND: COMMAND LIST ({})".format(userInfo["username"]))
				elif lowercaseText == "!unbench":
					self.commandUnbenchKench(channel)
					self.printWithTimestampAndChannel(channel, "COMMAND: UNBENCH THE KENCH ({})".format(userInfo["username"]))
				elif lowercaseText == "!jebaited":
					self.sendTextToChannel(channel, Memes.JEBAITED)
					self.printWithTimestampAndChannel(channel, "COMMAND: JEBAITED ({})".format(userInfo["username"]))
				elif lowercaseText == "!slownsteady":
					self.sendTextToChannel(channel, Memes.SLOW_AND_STEADY)
					self.printWithTimestampAndChannel(channel, "COMMAND: SLOW AND STEADY ({})".format(userInfo["username"]))
				elif lowercaseText == "!lapras":
					self.sendTextToChannel(channel, Memes.LAPRAS)
					self.printWithTimestampAndChannel(channel, "COMMAND: LAPRAS ({})".format(userInfo["username"]))
				elif lowercaseText == "!sockpuppets":
					self.sendTextToChannel(channel, Memes.SOCK_PUPPETS.format(channel))
					self.printWithTimestampAndChannel(channel, "COMMAND: SOCK PUPPETS ({})".format(userInfo["username"]))
				elif lowercaseText == "!sleeptest":
					self.sendTextToChannel(channel, Memes.SLEEP_TEST)
					self.printWithTimestampAndChannel(channel, "COMMAND: SLEEP TEST ({})".format(userInfo["username"]))
				elif lowercaseText == "!babblingbook":
					self.sendTextToChannel(channel, Memes.BABBLING_BOOK)
					self.printWithTimestampAndChannel(channel, "COMMAND: BABBLING BOOK ({})".format(userInfo["username"]))
				elif lowercaseText == "!srstrouble":
					self.sendTextToChannel(channel, Memes.SERIOUS_TROUBLE)
					self.printWithTimestampAndChannel(channel, "COMMAND: SERIOUS TROUBLE ({})".format(userInfo["username"]))
				elif lowercaseText == "!clown":
					self.sendTextToChannel(channel, Memes.OVERCLOWNFIDENCE)
					self.printWithTimestampAndChannel(channel, "COMMAND: OVERCLOWNFIDENCE ({})".format(userInfo["username"]))
				elif channel in self.adventureList:
					adventure = self.adventureList[channel]
					
					if userInfo["username"] in adventure.playerList:
						player = adventure.playerList[userInfo["username"]]
						
						if lowercaseText == "!adventure commands":
							self.sendTextToChannel(channel, "!adventure commands, !attack, !status, !inventory, !equipped, !equip [item name], !unequip [item name], !iteminfo [item name]")
							self.printWithTimestampAndChannel(channel, "COMMAND: Adventure Command List ({})".format(userInfo["username"]))
						elif lowercaseText == "!attack":
							gameState = adventure.attackPhase(player, adventure.bossList[adventure.levelCounter])
							
							while len(gameState) > 0:
								self.sendTextToChannel(channel, gameState.popleft())
							
							self.printWithTimestampAndChannel(channel, "COMMAND: Attack! ({})".format(userInfo["username"]))
						elif lowercaseText == "!status":
							self.sendTextToChannel(channel, player.getStatus())
							self.printWithTimestampAndChannel(channel, "COMMAND: My Status ({})".format(userInfo["username"]))
						elif lowercaseText == "!inventory":
							self.sendTextToChannel(channel, player.getInventory())
							self.printWithTimestampAndChannel(channel, "COMMAND: My Inventory ({})".format(userInfo["username"]))
						elif lowercaseText == "!equipped":
							self.sendTextToChannel(channel, player.getEquipment())
							self.printWithTimestampAndChannel(channel, "COMMAND: My Equipment ({})".format(userInfo["username"]))
						elif lowercaseText.find("!equip") == 0:
							if " " in lowercaseText:
								itemName = lowercaseText.split(" ", 1)[1]
								gameState = player.equip(itemName)
								self.sendTextToChannel(channel, gameState)
								self.printWithTimestampAndChannel(channel, "COMMAND: Equip ({}, {})".format(userInfo["username"], itemName))
						elif lowercaseText.find("!unequip") == 0:
							if " " in lowercaseText:
								itemName = lowercaseText.split(" ", 1)[1]
								gameState = player.unequip(itemName)
								self.sendTextToChannel(channel, gameState)
								self.printWithTimestampAndChannel(channel, "COMMAND: Unequip ({}, {})".format(userInfo["username"], itemName))
						elif lowercaseText.find("!iteminfo") == 0:
							if " " in lowercaseText:
								itemName = lowercaseText.split(" ", 1)[1]
								gameState = player.itemInfo(itemName)
								self.sendTextToChannel(channel, gameState)
								self.printWithTimestampAndChannel(channel, "COMMAND: Item Info ({}, {})".format(userInfo["username"], itemName))
								
					elif lowercaseText == "!join":
							adventure.addPlayer(userInfo["username"])
							self.sendTextToChannel(channel, "{} has joined the party!".format(userInfo["username"]))
							self.printWithTimestampAndChannel(channel, "COMMAND: Join Adventure ({})".format(userInfo["username"]))
				
	
	#A function containing the main chat loop 
	def monitorChat(self):
		readBuffer = "";

		while len(self.channelList) > 0:
			is_readable = [self.socket]
			is_writable = []
			is_error = []
			r, w, e = select.select(is_readable, is_writable, is_error, 1.0)
		
			if r:
				readBuffer = readBuffer + self.socket.recv(1024).decode()
				tempBuffer = readBuffer.split("\n")
				readBuffer = tempBuffer.pop()
				
				for line in tempBuffer:
					self.parseLine(line)
			else:
				if self.spotify is not None:
					self.updateSpotifyToken()
					self.updateCurrentTrack()
					
				if self.botInfoSleepTimer <= datetime.datetime.now():
					self.botInfoSleepTimer = (datetime.datetime.now() + datetime.timedelta(minutes = 20))
					self.sendTextToChannel(CHANNEL, self.botInfoMessage)
					
				if self.selfPromotionSleepTimer <= datetime.datetime.now():
					self.selfPromotionSleepTimer = (datetime.datetime.now() + datetime.timedelta(minutes = 15))
					self.sendTextToChannel(CHANNEL, self.selfPromotionMessage)
					
				if self.idleChatSleepTimer <= datetime.datetime.now():
					self.idleChatSleepTimer = (datetime.datetime.now() + datetime.timedelta(minutes = random.randint(4, 15)))
					self.sendTextToChannel(CHANNEL, self.idleMessages[random.randint(0, len(self.idleMessages) - 1)])
			
				for channel in self.adventureList:
					adventure = self.adventureList[channel]
					
					if adventure.location == Adventure.Locations.town:
						if datetime.datetime.now() >= (adventure.locationTime + datetime.timedelta(minutes = 5)):
							adventure.goToLocation(Adventure.Locations.dungeon)
					elif adventure.location == Adventure.Locations.dungeon:
						boss = adventure.bossList[adventure.levelCounter]
						
						if boss.lastAttackTime is None or datetime.datetime.now() >= (boss.lastAttackTime + datetime.timedelta(0, 5)):
							boss.lastAttackTime = datetime.datetime.now()
							
							for username in adventure.playerList:
								player = adventure.playerList[username]
								if player.currentHealth > 0:
									gameState = adventure.attackPhase(boss, player)
									self.sendTextToChannel(channel, gameState.popleft())
			
		self.printWithTimestamp("See ya!")
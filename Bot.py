import os
import datetime
import time
import discord
import sqlite3
import atexit
import signal
import re
import random
import itertools
import sys
from discord import app_commands
from discord.ext import commands
from discord import Color
from discord.ui import Button
from discord.ui import View

client = commands.Bot(command_prefix='!', intents=discord.Intents.all())
file = open("apiKey.txt","r")
token = file.readline()
file.close()
connection = sqlite3.connect("users.db")
cursor = connection.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS Users(UserName TEXT,Id TEXT, Points INT, QuestId INT, QuestProgress INT, QuestGoal INT, Daily TEXT, Color TEXT, LastQuestTime TEXT)")

user_name_index = 0
id_index = 1
points_index = 2
quest_id_index = 3
quest_progress_index = 4
quest_goal_index = 5
daily_index = 6
color_index = 7
quest_time_index=8

daily_quest_int = 0
coin_quest_int = 1
blackjack_quest_int = 2

no_cool_down = False

#? is quest goal
quests = {
    0:"Claim the daily reward ? time: */?",
    1:"Flip a coin ? time: */?",
    2:"Play blackjack ? time: */?"
}

def interpretQuest(userData):
    quest = quests.get(userData[quest_id_index])
    quest = quest.replace("?",str(userData[quest_goal_index]))
    quest = quest.replace("*",str(userData[quest_progress_index]))
    if userData[quest_goal_index]>2:
        quest = quest.replace("time:", "times:")
    return quest
    

@client.event
async def on_ready():
    await client.tree.sync()

@client.event
async def on_guild_join(guild):
    await checkUsersInGuild(guild)

class backButton(Button):
    def __init__(self, interaction:discord.Interaction):
        super().__init__(label="Back", style=discord.ButtonStyle.blurple)
        self.interaction = interaction
    async def callback(self,interaction):
        await checkAddUser(interaction.user)
        data = await getRowDataFromUserId(str(interaction.user.id))
        embeded = discord.Embed(title=data[user_name_index], color=Color.from_str(data[color_index]))
        embeded.add_field(name="", value="**Click on a button below to go to that section**")
        view = View()
        view.add_item(dailyButton(interaction, "Daily Reward"))
        view.add_item(leaderBoardButton(interaction,"Leaderboard"))
        view.add_item(coinFlipMenuButton(interaction))
        view.add_item(playBlackJackButton(interaction, "Blackjack"))
        view.add_item(questButton(interaction, "Quest"))
        await self.interaction.edit_original_response(embed=embeded,view=view)
        await interaction.response.defer()

def generateNewQuest(data):
    cursor.execute("UPDATE users SET QuestId = ?,  QuestProgress = ?, QuestGoal = ?, LastQuestTime = ? WHERE Id=?",(random.choice(list(quests)),0,random.randint(1,5),str(datetime.date.today()),data[id_index]))
    connection.commit()
    
def updateQuest(userData):
    cursor.execute("UPDATE users SET QuestProgress = ? WHERE ID = ?", (int(userData[quest_progress_index])+1,userData[id_index]))

class questButton(Button):
    def __init__(self, interaction:discord.Interaction, label:str):
        super().__init__(label=label, style=discord.ButtonStyle.blurple)
        self.interaction = interaction
    async def callback(self, interaction):
        data = await getRowDataFromUserId(str(interaction.user.id))
        embeded = discord.Embed(title="Quest Board", color = interaction.user.color)
        msg = interpretQuest(data)
        if data[quest_progress_index]>=data[quest_goal_index]:
            msg = "~~"+msg+"~~"
            embeded.add_field(name="",value=msg)
            points = random.randint(10,20)
            transferPoints(str(interaction.user.id),points)
            embeded.add_field(name="",value="Claimed quest for "+str(points)+" points")
            generateNewQuest(data)
            data = await getRowDataFromUserId(str(interaction.user.id))
            msg = interpretQuest(data)
            embeded.add_field(name="",value=msg,inline=False)
        else:
            embeded.add_field(name="",value=msg)
        view = View()
        view.add_item(backButton(self.interaction))
        view.add_item(questButton(self.interaction, "Claim Quest"))
        await self.interaction.edit_original_response(view=view, embed=embeded)
        await interaction.response.defer()

@client.tree.command(name="quest", description="Check quest progress and get new quests")
async def quest(interaction:discord.Interaction):
    data = await getRowDataFromUserId(str(interaction.user.id))
    embeded = discord.Embed(title="Quest Board", color = interaction.user.color)
    msg = interpretQuest(data)
    if data[quest_progress_index]>=data[quest_goal_index]:
        msg = "~~"+msg+"~~"
        embeded.add_field(name="",value=msg)
        points = random.randint(10,20)
        transferPoints(str(interaction.user.id),points)
        embeded.add_field(name="",value="Claimed quest for "+str(points)+" points")
        generateNewQuest(data)
        data = await getRowDataFromUserId(str(interaction.user.id))
        msg = interpretQuest(data)
        embeded.add_field(name="",value=msg,inline=False)
    else:
        embeded.add_field(name="",value=msg)
    view = View()
    view.add_item(backButton(interaction))
    view.add_item(questButton(interaction, "Claim Quest"))
    await interaction.response.send_message(view=view, embed=embeded)
    
    
def interpretCard(card):
    msg = " of "+card[1]
    faceCard = ["J","Q","K"]
    if (card[0]>10):
        msg = str(faceCard[card[0]-11]) + msg
    elif(card[0]==1):
        msg = "A"+msg
    else:
        msg = str(card[0]) + msg
    return msg + "\n"

def calcHandValue(hand):
    value = 0
    numAces = 0
    for card in hand:
        if card[0] == 1:
            numAces+=1
        elif card[0] > 10:
            value+=10
        else:
            value+=card[0]
    if numAces==1 and value<=10:
        value+=11
    else:
        value+=numAces
    return value

class blackJack():
    def __init__(self):
        self.deck = list(itertools.product(range(1,14),['Spade','Heart','Diamond','Club']))
        random.shuffle(self.deck)
        self.cardPointer = 0
        self.dealerHand = []
        self.playerHand = []
        self.stringDealerHand = ""
        self.stringPlayerHand = ""
        for i in range(2):
            self.dealerHand.append(self.deck[self.cardPointer])
            self.cardPointer+=1
            self.stringDealerHand+=interpretCard(self.dealerHand[i])
            self.playerHand.append(self.deck[self.cardPointer])
            self.stringPlayerHand+=interpretCard(self.playerHand[i])
            self.cardPointer+=1
    def hit(self):
        self.playerHand.append(self.deck[self.cardPointer])
        self.stringPlayerHand+=interpretCard(self.playerHand[len(self.playerHand)-1])
        self.cardPointer+=1
        return calcHandValue(self.playerHand)
    def stay(self):
        dealerHandValue = calcHandValue(self.dealerHand)
        playerHandValue = calcHandValue(self.playerHand)
        while(dealerHandValue<=playerHandValue and dealerHandValue<21):
            self.dealerHand.append(self.deck[self.cardPointer])
            self.stringDealerHand+=interpretCard(self.dealerHand[len(self.dealerHand)-1])
            self.cardPointer+=1
            dealerHandValue = calcHandValue(self.dealerHand)
        return [playerHandValue, dealerHandValue]
    def getPlayerHandValue(self):
        return calcHandValue(self.playerHand)
    def getDealerHandValue(self):
        return calcHandValue(self.dealerHand)
    

class playBlackJackButton(Button):
    def __init__(self, interaction:discord.Interaction, label:str):
        super().__init__(label=label, style=discord.ButtonStyle.blurple)
        self.interaction = interaction
    async def callback(self,interaction):
        emded = discord.Embed(color=interaction.user.color, title="Blackjack but worse")
        blackjack = blackJack()
        emded.add_field(name="**Player Hand: "+str(blackjack.getPlayerHandValue())+"**", value=blackjack.stringPlayerHand, inline=False)
        emded.add_field(name="**Dealer Hand: "+str(blackjack.getDealerHandValue())+"**", value=blackjack.stringDealerHand, inline=False)
        view = View()
        view.add_item(backButton(self.interaction))
        view.add_item(blackJackHitButton(self.interaction, blackjack, 0))
        view.add_item(blackJackStayButton(self.interaction, blackjack, 0))
        await self.interaction.edit_original_response(view=view,embed=emded)
        await interaction.response.defer()

@client.tree.command(name="blackjack", description="Play a game of blackjack")
@app_commands.describe(bet="The amount you want to be must be >=0 and <= the number of points you have, if the bet is out of range it goes to the default of 0")
async def blackjack(interaction:discord.Interaction,bet:int=0):
    data = await getRowDataFromUserId(str(interaction.user.id))
    if (bet<0 or bet>data[points_index]):
        bet = 0
    emded = discord.Embed(color=interaction.user.color, title="Blackjack but worse")
    blackjack = blackJack()
    emded.add_field(name="**Player Hand: "+str(blackjack.getPlayerHandValue())+"**", value=blackjack.stringPlayerHand, inline=False)
    emded.add_field(name="**Dealer Hand: "+str(blackjack.getDealerHandValue())+"**", value=blackjack.stringDealerHand, inline=False)
    view = View()
    view.add_item(backButton(interaction))
    view.add_item(blackJackHitButton(interaction, blackjack, bet))
    view.add_item(blackJackStayButton(interaction, blackjack, bet))
    await interaction.response.send_message(view=view, embed=emded)

async def endBlackJackGame(orgInteraction:discord.Interaction, interaction:discord.Interaction, bet:int, blackjack:blackJack, text:str):
    emded = discord.Embed(color=interaction.user.color, title="Blackjack but worse")
    emded.add_field(name="", value=text, inline=False)
    emded.add_field(name="**Player Hand: "+str(blackjack.getPlayerHandValue())+"**", value=blackjack.stringPlayerHand, inline=False)
    emded.add_field(name="**Dealer Hand: "+str(blackjack.getDealerHandValue())+"**", value=blackjack.stringDealerHand, inline=False)
    view = View()
    view.add_item(backButton(orgInteraction))
    view.add_item(playBlackJackButton(orgInteraction, "Play again"))
    data = await getRowDataFromUserId(str(interaction.user.id))
    if (data[quest_id_index]==blackjack_quest_int):
            updateQuest(data)
    await orgInteraction.edit_original_response(view=view,embed=emded)
    
class blackJackStayButton(Button):
    def __init__(self, interaction:discord.Interaction, blackjack:blackJack, bet:int):    
        super().__init__(label="Stay", style=discord.ButtonStyle.blurple)
        self.bet = bet
        self.blackjack = blackjack
        self.interaction = interaction
    async def callback(self,interaction):
        if (self.interaction.user.id!=interaction.user.id):
            await interaction.response.defer()
            return
        handValues = self.blackjack.stay()
        win = None
        if (handValues[1]>21):
            await endBlackJackGame(self.interaction, interaction, self.bet, self.blackjack, "Dealer busted (went over 21). You win "+str(self.bet)+".")
            transferPoints(str(interaction.user.id),self.bet)
        elif (handValues[1]<=handValues[0]):
            await endBlackJackGame(self.interaction, interaction, self.bet, self.blackjack, "Dealer has a smaller hand value. You win "+str(self.bet)+".")
            transferPoints(str(interaction.user.id),self.bet)
        else:
            await endBlackJackGame(self.interaction, interaction, self.bet, self.blackjack, "You have a smaller hand value. You lose "+str(self.bet)+".")
            transferPoints(str(interaction.user.id),self.bet*-1)
        await interaction.response.defer()
        
class blackJackHitButton(Button):
    def __init__(self, interaction:discord.Interaction, blackjack:blackJack, bet:int):
        super().__init__(label="Hit", style=discord.ButtonStyle.blurple)
        self.bet = bet
        self.blackjack = blackjack
        self.interaction = interaction
    async def callback(self,interaction):
        if (self.interaction.user.id!=interaction.user.id):
            await interaction.response.defer()
            return
        playerHandValue = self.blackjack.hit()
        if (playerHandValue>21):
            transferPoints(str(interaction.user.id),self.bet*-1)
            await endBlackJackGame(self.interaction, interaction, self.bet, self.blackjack, "You busted (went over 21). You lose "+str(self.bet)+".")
        else:
            emded = discord.Embed(color=interaction.user.color, title="Blackjack but worse")
            emded.add_field(name="**Player Hand:"+str(self.blackjack.getPlayerHandValue())+"**", value=self.blackjack.stringPlayerHand, inline=False)
            emded.add_field(name="**Dealer Hand:"+str(self.blackjack.getDealerHandValue())+"**", value=self.blackjack.stringDealerHand, inline=False)
            view = View()
            view.add_item(backButton(self.interaction))
            view.add_item(blackJackHitButton(self.interaction, self.blackjack, self.bet))
            view.add_item(blackJackStayButton(self.interaction, self.blackjack, self.bet))
            await self.interaction.edit_original_response(view=view,embed=emded)
        await interaction.response.defer()
        
class coinFlipMenuButton(Button):
    def __init__(self, interaction:discord.Interaction):
        super().__init__(label="Coin Flip", style=discord.ButtonStyle.blurple)
        self.interaction = interaction
    async def callback(self,interaction):
        embeded = discord.Embed(title="Coin Flip", color=Color.blurple())
        embeded.add_field(name="", value="**Click on a choice below to flip a coin**")
        view = View()
        view.add_item(backButton(self.interaction))
        view.add_item(coinFlipButton(self.interaction, "Heads", 0, 0))
        view.add_item(coinFlipButton(self.interaction, "Tails", 1, 0))
        await self.interaction.edit_original_response(embed=embeded, view=view)
        
        await interaction.response.defer()

class coinFlipButton(Button):
    def __init__(self, interaction:discord.Interaction, label:str, choice:int, bet:int):
        super().__init__(label=label+" bet "+str(bet), style=discord.ButtonStyle.blurple)
        self.interaction = interaction
        self.choice = choice
        self.bet = bet
    async def callback(self,interaction):
        await flipCoin(self.interaction, interaction, self.choice, self.bet)

@client.tree.command(name="flip_coin", description="Flip a coin to have a chance to double the bet")
@app_commands.describe(choice="Number of the choice, 0 for heads, 1 for tails")
@app_commands.describe(bet="The amount you want to be must be >=0 and <= the number of points you have, if the bet is out of range it goes to the default of 0")
async def flip_coin(interaction:discord.Interaction,choice:app_commands.Range[int,0,1],bet:int=0):
    data = await getRowDataFromUserId(str(interaction.user.id))
    if (bet<0 or bet>data[points_index]):
        bet = 0
    embeded = discord.Embed(title="Coin Flip Bet "+str(bet), colour=interaction.user.color)
    view = View()
    view.add_item(backButton(interaction))
    view.add_item(coinFlipButton(interaction, "Heads", 0, bet))
    view.add_item(coinFlipButton(interaction, "Tails", 1, bet))
    await interaction.response.send_message(embed=embeded, view=view)
    await flipCoin(interaction, interaction, choice, bet)

async def flipCoin(orgInteraction:discord.Interaction, interaction:discord.Interaction, choice:int, bet:int):
    embeded = discord.Embed(title="Coin Flip Bet "+str(bet), colour=interaction.user.color)
    headTail = random.randint(0,1)
    headTailStr = ("Heads","Tails")
    await checkAddUser(interaction.user)
    data = await getRowDataFromUserId(str(interaction.user.id))
    if (bet<0 or bet>data[points_index]):
        bet = 0
    loseWin = ""
    if(choice==headTail):
        loseWin = "won "
        transferPoints(str(interaction.user.id),bet)
    else:
        transferPoints(str(interaction.user.id),bet*-1)
        loseWin = "lost "
    if (data[quest_id_index]==coin_quest_int):
        updateQuest(data)
    embeded.add_field(name="",value="**"+data[user_name_index]+"** " + loseWin + str(bet) +". Guessed "+headTailStr[choice]+" and it was "+headTailStr[headTail]+".")
    await orgInteraction.edit_original_response(embed=embeded)
    try:
        await interaction.response.defer()
    except:
        pass

def getTimeBetween(data, index):
    format = "%Y-%m-%d"
    lastClaimedDate = datetime.datetime.strptime(data[index],format)
    time = datetime.datetime.now() - lastClaimedDate
    if no_cool_down:
        return sys.maxsize
    return time.days

async def claimDaily(orgInteraction:discord.Interaction, interaction:discord.Interaction):
    await checkAddUser(interaction.user)
    data = await getRowDataFromUserId(str(interaction.user.id))
    cooldown = False
    if (data!=None):
        currentDate = datetime.date.today()
        currentTimeDate = datetime.datetime.now()
        newPointes = int(data[points_index])
        if (data[daily_index]=="NONE"):
            newPointes = data[points_index]+random.randint(1,10)
            cursor.execute("UPDATE users SET Daily = ?, Points = ? WHERE Id=?",(str(currentDate),newPointes,data[id_index]))
            connection.commit()
            if (data[quest_id_index]==daily_quest_int):
                updateQuest(data)
        else:
            if(getTimeBetween(data, daily_index)>=1):
                newPointes = data[points_index]+random.randint(1,10)
                cursor.execute("UPDATE users SET Daily = ?, Points = ? WHERE Id=?",(str(currentDate),newPointes,data[id_index]))
                connection.commit()
                if (data[quest_id_index]==daily_quest_int):
                    updateQuest(data)
            else:
                cooldown = True
        orgMsg = await orgInteraction.original_response()
        embeded = discord.Embed(title=data[user_name_index], color=Color.from_str(data[color_index]))
        stringData = re.compile(r'[^\d.]+')
        stringData = stringData.sub("",str(newPointes))
        embeded.add_field(name="", value="**Points**: "+stringData+"\n**Last Claimed Daily**: "+str(currentDate), inline=False)
        if (cooldown):
            embeded.add_field(name="", value="Wait until tomorrow or whenver the database gets delted again to claim the daily reward")
        button = dailyButton(interaction, "Claim Daily Reward")
        view = View()
        view.add_item(backButton(interaction))
        view.add_item(button)
        await orgMsg.edit(embed=embeded,view=view)

class dailyButton(Button):
    def __init__(self, interaction:discord.Interaction, label:str):
        super().__init__(label=label, style=discord.ButtonStyle.blurple)
        self.interaction = interaction
    async def callback(self,interaction):
        await checkAddUser(interaction.user)
        await claimDaily(self.interaction, interaction)
        await interaction.response.defer()

@client.tree.command(name="daily", description="Claim daily reward")
async def daily(interaction: discord.Interaction):
    await checkAddUser(interaction.user)
    data = await getRowDataFromUserId(str(interaction.user.id))
    button = dailyButton(interaction, "Claim daily reward")
    view = View()
    view.add_item(backButton(interaction))
    view.add_item(button)
    embeded = discord.Embed(title=data[user_name_index], color=Color.from_str(data[color_index]))
    stringData = re.compile(r'[^\d.]+')
    stringData = stringData.sub("",str(data[points_index]))
    embeded.add_field(name="", value="**Points**: "+stringData+"\n**Last Claimed Daily**: "+data[daily_index])
    await interaction.response.send_message(view=view,embed=embeded)
    await claimDaily(interaction, interaction)

class leaderBoardButton(Button):
    def __init__(self, interaction:discord.Interaction, label:str):
        super().__init__(label=label, style=discord.ButtonStyle.blurple)
        self.interaction = interaction
        self.label = label
    async def callback(self,interaction):
        await checkAddUser(interaction.user)
        cursor.execute("SELECT * FROM users ORDER BY Points DESC")
        data = cursor.fetchall()
        embeded = discord.Embed(title="Leaderboard", color=Color.blurple())
        counter = 0
        text = ""
        for row in data:
            counter+=1
            text = text + "**" + str(counter) + "**." + row[user_name_index] + "|" + str(row[points_index]) + "\n"
        embeded.add_field(name="",value=text)
        view = View()
        view.add_item(backButton(interaction))
        view.add_item(leaderBoardButton(self.interaction, "Update"))
        await self.interaction.edit_original_response(embed = embeded, view=view)
        await interaction.response.defer()

@client.tree.command(name="leaderboard", description="See the leaderboard of who has the most points")
async def leaderboard(interaction: discord.Interaction):
    await checkAddUser(interaction.user)
    cursor.execute("SELECT * FROM users ORDER BY Points DESC")
    data = cursor.fetchall()
    embeded = discord.Embed(title="Leaderboard", color=Color.blurple())
    counter = 0
    text = ""
    for row in data:
        counter+=1
        text = text + "**" + str(counter) + "**." + row[user_name_index] + "|" + str(row[points_index]) + "\n"
    embeded.add_field(name="",value=text)
    view = View()
    view.add_item(backButton(interaction))
    view.add_item(leaderBoardButton(interaction, "Update"))
    await interaction.response.send_message(embed=embeded,view=view)
    

@client.tree.command(name="update_users", description="Trigger the bot to add any users not in the database")
async def updateUsers(interaction: discord.Interaction):
    guild = interaction.guild
    await checkUsersInGuild(guild)
    await interaction.response.send_message("Done")
    
@client.tree.command(name="menu", description="See the menu")
async def menu(interaction: discord.Interaction):
    await checkAddUser(interaction.user)
    data = await getRowDataFromUserId(str(interaction.user.id))
    embeded = discord.Embed(title=data[user_name_index], color=Color.from_str(data[color_index]))
    embeded.add_field(name="", value="**Click on a button below to go to that section**")
    view = View()
    view.add_item(dailyButton(interaction, "Daily Reward"))
    view.add_item(leaderBoardButton(interaction,"Leaderboard"))
    view.add_item(coinFlipMenuButton(interaction))
    view.add_item(playBlackJackButton(interaction, "Blackjack"))
    view.add_item(questButton(interaction, "Quest"))
    await interaction.response.send_message(view=view, embed=embeded)

@client.tree.command(name="lookup_points_id", description="See how many points another user has from user id")
@app_commands.describe(id="The user id of the member you want to see thier amount of points")
async def lookup_points_id(interaction:discord.Interaction, id: str):
    data = await getRowDataFromUserId(id)
    embeded = None
    if data == None:
        embeded = discord.Embed(title="User not in data base",color=Color.red)
    else:
        embeded = discord.Embed(title=data[user_name_index],color=Color.from_str(data[color_index]))
        stringData = re.compile(r'[^\d.]+')
        stringData = stringData.sub("",str(data[points_index]))
        embeded.add_field(name="", value="**Points**"+": "+stringData)
    await interaction.response.send_message(embed=embeded)
    
async def getRowDataFromUserId(id):
    cursor.execute("SELECT * FROM users WHERE Id=?",(id,))
    return cursor.fetchone()

async def checkUsersInGuild(guild):
    for user in guild.members:
        cursor.execute("SELECT Id FROM users WHERE Id=?",(user.id,))
        data = cursor.fetchone()
        if data is None and not user.bot:
            cursor.execute("INSERT INTO users VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)",(user.display_name, str(user.id), 0, 0, 0, 1, "NONE",str(user.color), "NONE"))
    connection.commit()

async def checkAddUser(user):
    cursor.execute("SELECT Id FROM users WHERE Id=?",(user.id,))
    data = cursor.fetchone()
    if data is None and not user.bot:
        cursor.execute("INSERT INTO users VALUES(?, ?, ?, ?, ?, ?, ?,?,?)",(user.display_name, str(user.id), 0, 0, 0, 1, "NONE",str(user.color),"NONE"))
    connection.commit()
    
def giveUserPoints(userId, amount):
    cursor.execute("SELECT * FROM users WHERE Id=?",(userId,))
    data = cursor.fetchone()
    if not (data == None):
        cursor.execute("UPDATE users SET Points = ? WHERE Id=?",(data[points_index]+amount,data[id_index]))
        connection.commit()

def exit_handler():
    print("Bot stopped")
    connection.commit()
    cursor.execute("SELECT * FROM users")
    print(cursor.fetchall())
    connection.close()

def transferPoints(targetUser, amount):
    cursor.execute("SELECT * FROM users WHERE Id=?",(targetUser,))
    data = cursor.fetchone()
    cursor.execute("SELECT * FROM users WHERE Id=?",("594126960926523408",))
    house = cursor.fetchone()
    if (targetUser=="594126960926523408"):
        cursor.execute("UPDATE users SET Points = ? WHERE Id=?",(str(int(data[points_index])+amount),data[id_index]))
        connection.commit()
    else:
        cursor.execute("UPDATE users SET Points = ? WHERE Id=?",(str(int(data[points_index])+amount),data[id_index]))
        if (int(house[points_index])-amount<0):
            amount = int(house[points_index])
        cursor.execute("UPDATE users SET Points = ? WHERE Id=?",(str(int(house[points_index])-amount),house[id_index]))
        
@client.tree.command(name="gift_points", description="Gift points to another user")
@app_commands.describe(id="The user id of the member you want to see thier amount of points")
@app_commands.describe(num_points="The number of points you want to gift")
async def gift_points(interaction:discord.Interaction, id:str, num_points: int):
    if (num_points<0):
        await interaction.response.send_message("You cannot send a negative number of points")
        return
    senderData = await getRowDataFromUserId(str(interaction.user.id))
    reciverData = await getRowDataFromUserId(id)
    if (senderData[points_index]<num_points):
        await interaction.response.send_message("You must put a number of points you can afford")
        return
    cursor.execute("UPDATE users SET Points = ? WHERE Id=?",(str(int(senderData[points_index])-num_points),senderData[id_index]))
    cursor.execute("UPDATE users SET Points = ? WHERE Id=?",(str(int(reciverData[points_index])+num_points),reciverData[id_index]))
    connection.commit()
    await interaction.response.send_message(f"{senderData[user_name_index]} gifted {reciverData[user_name_index]} {num_points} points")

atexit.register(exit_handler)
client.run(token)

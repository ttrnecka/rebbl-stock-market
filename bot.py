"""Bot"""
import os
import logging
from logging.handlers import RotatingFileHandler
import traceback
import re

import discord
from sqlalchemy import func
from web import db, app

from services import SheetService

ROOT = os.path.dirname(__file__)
logger = logging.getLogger('discord')
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(
    os.path.join(ROOT, 'logs/discord.log'), maxBytes=10000000,
    backupCount=5, encoding='utf-8', mode='a'
)
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

app.app_context().push()

client = discord.Client()
def log_response(response):
    """Log command response"""
    logger.info("Response:\n%s", response)

@client.event
async def on_message(message):
    """Message event handler"""
    # we do not want the bot to reply to itself
    if message.author == client.user:
        return

    #ignore DM
    if isinstance(message.channel, discord.abc.PrivateChannel):
        await message.channel.send(
            "PM commands are not allowed. Please use the Imperium discord server."
        )
        return

    #ignore commands not starting with !
    if not message.content.startswith("!"):
        return

    logger.info("%s: %s", message.author, message.content)

    try:
        command = DiscordCommand(message, client)
        await command.process()
    finally:
        db.session.close()

@client.event
async def on_ready():
    """loads custom emojis upon ready"""
    logger.info('Logged in as')
    logger.info(client.user.name)
    logger.info(client.user.id)
    logger.info('------')

class LongMessage:
    """Class to handle long message sending in chunks"""
    def __init__(self, channel):
        self.limit = 2000
        self.parts = []
        self.channel = channel

    def add(self, part):
        """Adds part of long message"""
        self.parts.append(part)

    async def send(self):
        """sends the message to channel in limit chunks"""
        for chunk in self.chunks():
            await self.channel.send(chunk)
        log_response('\n'.join(self.lines()))

    def lines(self):
        """transforms the message to lines"""
        lines = []
        for part in self.parts:
            lines.extend(part.split("\n"))
        return lines

    def chunks(self):
        """Transform the lines to limit sized chunks"""
        lines = self.lines()
        while True:
            msg = ""
            if not lines:
                break
            while lines and len(msg + lines[0]) < self.limit:
                msg += lines.pop(0) + "\n"
            yield msg

class DiscordCommand:
    """Main class to process commands"""

    @classmethod
    def is_admin_channel(cls, dchannel):
        """checks if it is admin channel"""
        if dchannel.name is not None and dchannel.name == "admin-channel":
            return True
        return False

    def __init__(self, dmessage, dclient):
        self.message = dmessage
        self.client = dclient
        self.cmd = dmessage.content.lower()
        self.args = self.cmd.split()

    async def process(self):
        """Process the command"""
        try:
            if(self.args[0])=="!stock":
                if len(self.args) < 2:
                    await self.short_reply("Provide partial or full stock name")
                else:
                    stocks = [stock for stock in SheetService.stocks() if self.args[1] in stock['Team'].lower()]
                    msg = []
                    for stock in stocks:
                        msg.append(
                            f"{stock['Team']}: {stock['Current Value']}"
                        )
                    await self.reply(msg)

        except Exception as e:
            await self.transaction_error(e)
            #raising will not kill the discord bot but will cause it to log this to log as well
            raise

    async def send_message(self, channel, message_list):
        """Sends messages to channel"""
        msg = LongMessage(channel)
        for message in message_list:
            msg.add(message)
        await msg.send()

    async def reply(self, message_list):
        """Replies in the same channel"""
        await self.send_message(self.message.channel, message_list)

    async def short_reply(self, message):
        """Short message not using LongMesage class"""
        await self.message.channel.send(message)
        log_response(message)

    async def transaction_error(self, error):
        """Sends and logs transaction error"""
        text = type(error).__name__ +": "+str(error)
        await self.send_message(self.message.channel, [text])
        logger.error(text)
        logger.error(traceback.format_exc())

with open(os.path.join(ROOT, 'config/TOKEN'), 'r') as token_file:
    TOKEN = token_file.read()

client.run(TOKEN)

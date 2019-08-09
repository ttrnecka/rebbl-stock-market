"""Bot"""
import os
import logging
from logging.handlers import RotatingFileHandler
import traceback
import re

import discord
from sqlalchemy import func, asc
from sqlalchemy.orm.exc import MultipleResultsFound
from web import db, app

from services import SheetService, StockService, UserService, OrderService, OrderError
from models.data_models import Stock, User, Order, Share
from misc.helpers import represents_int

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
            "PM commands are not allowed. Please use the discord server."
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
            if self.cmd.startswith('!stock'):
                await self.__run_stock()
            elif self.cmd.startswith('!admin'):
                await self.__run_admin()
            elif self.cmd.startswith('!newuser'):
                await self.__run_newuser()
            elif self.cmd.startswith('!list'):
                await self.__run_list()
            elif self.cmd.startswith('!buy'):
                await self.__run_buy()
            elif self.cmd.startswith('!sell'):
                await self.__run_sell()
            elif self.cmd.startswith('!cancel'):
                await self.__run_cancel()
            elif self.cmd.startswith('!top'):
                await self.__run_top()
        except Exception as e:
            await self.transaction_error(e)
            #raising will not kill the discord bot but will cause it to log this to log as well
            raise

    @classmethod
    def buy_help(cls):
        """help message"""
        msg = "```"
        msg += "Creates order to BUY Stock\n"
        msg += "USAGE:\n"
        msg += "!buy <stock_code> [credit]\n"
        msg += "\t<stock_code>: code of stock from !stock\n"
        msg += "\t[credit]: optional, if provided spend up to the amout for the stock, if ommited, buy as much as possible\n"
        msg += "```"
        return msg

    @classmethod
    def sell_help(cls):
        """help message"""
        msg = "```"
        msg += "Creates order to SELL Stock\n"
        msg += "USAGE:\n"
        msg += "!sell <stock_code> [units]\n"
        msg += "\t<stock_code>: code of stock from !stock or !list or *all*\n"
        msg += "\t[units]: optional, if provided sell up to [units] of stock, if omitted, sell all units of that stock\n"
        msg += "```"
        return msg

    @classmethod
    def cancel_help(cls):
        """help message"""
        msg = "```"
        msg += "Cancels outstanding order\n"
        msg += "USAGE:\n"
        msg += "!cancel <id>\n"
        msg += "\t<id>: id of the order from the !list or *all*\n"
        msg += "```"
        return msg

    @classmethod
    def top_help(cls):
        """help message"""
        msg = "```"
        msg += "List top investors\n"
        msg += "USAGE:\n"
        msg += "!top <count>\n"
        msg += "\t<count>: count of the top investors to display (max 50)\n"
        msg += "```"
        return msg

    # must me under 2000 chars
    async def trade_notification(self, msg, user):
        """Notifies coach about bank change"""
        member = discord.utils.get(self.message.guild.members, id=user.disc_id)
        if member is None:
            mention = user.name
        else:
            mention = member.mention

        channel = discord.utils.get(self.client.get_all_channels(), name='trade-notifications')
        await self.send_message(channel, [f"{mention}: "+msg])
        return

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

    def list_message(self,user):
        msg = [
            f"**User:** {user.short_name()}\n",
            f"**Bank:** {user.account.amount} credits\n",
            f"**Shares:**",
        ]

        total_value = 0
        if user.shares:
            msg.append("```")
            for share in user.shares:
                msg.append(
                    '{:5s} - {:25s}: {:3d} x {:7.2f}'.format(share.stock.code, share.stock.name, share.units, share.stock.unit_price)
                )
                total_value += share.units * share.stock.unit_price
        
            msg.append("```") 
            msg.append("**Total Shares Value:** {:9.2f}".format(total_value))
            msg.append("**Balance:** {:9.2f}".format(total_value+user.account.amount))

        msg.append("")
        msg.append(f"**Outstanding Orders:**")
        msg.append(f"*Sell:*")

        for order in user.orders:
            if not order.processed and order.operation=="sell":
                msg.append(f"{order.id}. {order.description}")
        msg.append(" ")

        msg.append(f"*Buy:*")

        for order in user.orders:
            if not order.processed and order.operation=="buy":
                msg.append(f"{order.id}. {order.description}")
        msg.append(" ")

        return msg

    # commands
    async def __run_newuser(self):
        if User.get_by_discord_id(self.message.author.id):
            await self.reply([f"**{self.message.author.mention}** account exists already\n"])
        else:
            user = UserService.new_coach(self.message.author, self.message.author.id)
            msg = [
                f"**{self.message.author.mention}** account created\n",
                f"**Bank:** {user.account.amount} credits",
            ]
            await self.reply(msg)

    async def __run_list(self):

        user = User.get_by_discord_id(self.message.author.id)
        
        if user is None:
            await self.reply(
                [(f"User {self.message.author.mention} does not exist."
                "Use !newuser to create user first.")]
            )
            return

        msg = self.list_message(user)

        await self.send_message(self.message.author, msg)
        await self.short_reply("Info sent to PM")

    async def __run_admin(self):
        # if not started from admin-channel
        if not self.__class__.is_admin_channel(self.message.channel):
            await self.reply([f"Insuficient rights"])
            return

        if self.args[0] == "!adminstock":
            if len(self.args) != 2:
                await self.reply([f"Wrong number of parameters"])
                return
            if self.args[1] not in ["update"]:
                await self.reply([f"Wrong parameter - only *update* is allowed"])
                return
            await self.short_reply("Updating...")
            StockService.update()
            await self.short_reply("Done")

        if self.args[0] == "!adminmarket":
            if len(self.args) != 2:
                await self.reply([f"Wrong number of parameters"])
                return
            if self.args[1] not in ["close","open","status"]:
                await self.reply([f"Wrong parameter - only *status*, *open* and *close* are allowed"])
                return
            
            if self.args[1] == "open":
                OrderService.open()
                msg = "Done"
            if self.args[1] == "close":
                OrderService.close()
                msg = "Done"
            if self.args[1] == "status":
                if OrderService.is_open():
                    msg = "Market is open"
                else:
                    msg = "Market is closed"

            await self.short_reply(msg)

        if self.args[0] == "!admintrade":
            await self.short_reply("Updating DB...")
            StockService.update()
            await self.short_reply("Done")
            await self.short_reply("Closing market...")
            OrderService.close()
            await self.short_reply("Done")

            await self.short_reply("Processing SELL orders...")
            orders = Order.query.order_by(asc(Order.date_created)).filter(Order.processed == False, Order.operation == "sell").all()
            for order in orders:
                order = OrderService.process(order)
                await self.trade_notification(order.result, order.user)
            await self.short_reply("Done")

            await self.short_reply("Processing BUY orders...")
            orders = Order.query.order_by(asc(Order.date_created)).filter(Order.processed == False, Order.operation == "buy").all()
            for order in orders:
                order = OrderService.process(order)
                await self.trade_notification(order.result, order.user)
            await self.short_reply("Done")
            
            await self.short_reply("Opening market...")
            OrderService.open()
            await self.short_reply("Done")

        if self.args[0] == "!adminlist":
            # require username argument
            if len(self.args) == 1:
                await self.reply(["Username missing"])
                return

            users = User.find_all_by_name(self.args[1])
            msg = []

            if not users:
                msg.append("No coaches found")

            for user in users:
                for messg in self.list_message(user):
                    msg.append(messg)

            await self.reply(msg)
            

    async def __run_stock(self):
        if(self.args[0])=="!stock":
            if len(self.args) < 2:
                await self.short_reply("Provide partial or full stock name")
            else:
                stocks = Stock.find_all_by_name(" ".join(self.args[1:]))
                msg = ["```"]
                msg.append(
                    '{:5s} - {:25}: {:<10s}'.format("Code","Team Name","Unit Price")
                )
                msg.append(49*"-")
                for stock in stocks[0:20]:
                    msg.append(
                        '{:5s} - {:25}: {:7.2f}'.format(stock.code, stock.name, stock.unit_price)
                    )
                if len(stocks) > 20:
                    msg.append("...")
                    msg.append("More stock follows, narrow your search!")
                msg.append("```")
                await self.reply(msg)

    async def __run_buy(self):
        user = User.get_by_discord_id(self.message.author.id)
        order_dict = {
            'operation':"buy"
        }

        if user is None:
            await self.reply(
                [(f"User {self.message.author.mention} does not exist."
                "Use !newuser to create user first.")]
            )
            return

        if len(self.args) not in [2,3]:
            await self.reply(["Incorrect number of arguments!!!", self.__class__.buy_help()])
            return
        try:
            stock = Stock.find_by_code(self.args[1])
        except MultipleResultsFound as exc:
            await self.reply([f"Stock code **{self.args[1]}** is not unique!!!",])
            return

        if not stock:
            await self.reply([f"Stock code **{self.args[1]}** not found!"])
            return

        if len(self.args) == 3:
            if not represents_int(self.args[2]) or (represents_int(self.args[2]) and not int(self.args[2]) > 0):
                await self.reply([f"**{self.args[2]}** must be whole positive number!"])
                return
            else:
                order_dict['buy_funds'] = self.args[2]

        
        order = OrderService.create(user, stock, **order_dict)
        await self.reply([f"Order **{order.id}** placed succesfully."," ",f"**{order.description}**"])
        return

    async def __run_sell(self):
        user = User.get_by_discord_id(self.message.author.id)
        order_dict = {
            'operation':"sell"
        }

        if user is None:
            await self.reply(
                [(f"User {self.message.author.mention} does not exist."
                "Use !newuser to create user first.")]
            )
            return

        if len(self.args) not in [2,3]:
            await self.reply(["Incorrect number of arguments!!!", self.__class__.sell_help()])
            return
        if self.args[1] == "all":
            if len(user.shares):
                for share in user.shares:
                    order = OrderService.create(user, share.stock, **order_dict)
                    await self.reply([f"Order placed succesfully."," ",f"**{order.description}**"])
            else:
                await self.reply([f"You do not own any shares"])
        else:
            try:
                stock = Stock.find_by_code(self.args[1])
            except MultipleResultsFound as exc:
                await self.reply([f"Stock code **{self.args[1]}** is not unique!!!",])
                return

            if not stock:
                await self.reply([f"Stock code **{self.args[1]}** not found!"])
                return
            
            if len(self.args) == 3:
                if not represents_int(self.args[2]) or (represents_int(self.args[2]) and not int(self.args[2]) > 0):
                    await self.reply([f"**{self.args[2]}** must be whole positive number!"])
                    return
                else:
                    order_dict['sell_shares'] = int(self.args[2])
            
            share = Share.query.join(Share.user, Share.stock).filter(User.id == user.id, Stock.id == stock.id).one_or_none()
            
            if not share:
                await self.reply([f"You do not own any shares of **{self.args[1]}** stock!"])
                return

            order = OrderService.create(user, stock, **order_dict)
            await self.reply([f"Order **{order.id}** placed succesfully."," ",f"**{order.description}**"])
        return

    async def __run_cancel(self):
        user = User.get_by_discord_id(self.message.author.id)

        if user is None:
            await self.reply(
                [(f"User {self.message.author.mention} does not exist."
                "Use !newuser to create user first.")]
            )
            return

        if len(self.args) not in [2]:
            await self.reply(["Incorrect number of arguments!!!", self.__class__.cancel_help()])
            return

        if not represents_int(self.args[1]) and self.args[1] != "all":
            await self.reply([f"**{self.args[1]}** must be whole number or *all*!"])
            return

        if self.args[1] == "all":
            for order in user.orders:
                if not order.processed:
                    OrderService.cancel(order.id, user)
                    await self.reply([f"Order ID {order.id} has been cancelled"])
            return
        else:
            if OrderService.cancel(self.args[1], user):
                await self.reply([f"Order ID {self.args[1]} has been cancelled"])
                return
            else:
                await self.reply([f"**Outstanding order with id {self.args[1]}** does not exist!"])
                return

    async def __run_top(self):
       
        if len(self.args) not in [2]:
            await self.reply(["Incorrect number of arguments!!!", self.__class__.top_help()])
            return

        if not represents_int(self.args[1]) or int(self.args[1]) > 50:
            await self.reply([f"**{self.args[1]}** must be whole number and be less or equal 50!"])
            return
        
        users = User.query.all()

        user_tuples = []
        for user in users:
            total_value = 0
            for share in user.shares:
                total_value += share.units * share.stock.unit_price
            balance = user.account.amount + total_value
            user_tuples.append((balance, user))

        sorted_users = sorted(user_tuples, key=lambda x: x[0], reverse=True)

        max = int(self.args[1])
        if max > len(sorted_users):
            max = len(sorted_users)

        msg = ["```asciidoc"]
        msg.append(" = Place = | = Balance = | = Investor =")
        for position, tup in enumerate(sorted_users[0:max], 1):
            msg.append("{:3d}.       |{:12.2f} | {:s}".format(position, tup[0],tup[1].short_name()))
        msg.append("```")

        await self.reply(msg)
        return
with open(os.path.join(ROOT, 'config/TOKEN'), 'r') as token_file:
    TOKEN = token_file.read()

client.run(TOKEN)

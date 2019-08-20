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

from services import SheetService, StockService, UserService, OrderService, OrderError, TeamService
from models.data_models import Stock, User, Order, Share, Transaction, TransactionError
from misc.helpers import represents_int, is_number

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
    def __init__(self, channel, block):
        self.limit = 1994 # to allow ``` before and after
        self.parts = []
        self.channel = channel
        self.block = block

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
            msg = "```asciidoc\n" if self.block else ""
            if not lines:
                break
            while lines and len(msg + lines[0]) < self.limit:
                msg += lines.pop(0) + "\n"
            if self.block:
                msg += '```'
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
            elif self.cmd.startswith('!flop'):
                await self.__run_flop()
            elif self.cmd.startswith('!help'):
                await self.__run_help()
        except Exception as e:
            await self.transaction_error(e)
            #raising will not kill the discord bot but will cause it to log this to log as well
            raise

    @classmethod
    def help_help(cls):
        """help message"""
        msg = "```asciidoc\n"
        msg += " = Available commands =\n"
        msg += "!newuser - creates new user \n"
        msg += "!buy - place BUY order \n"
        msg += "!sell - place SELL order \n"
        msg += "!list - list your account info \n"
        msg += "!cancel - CANCELs order \n"
        msg += "!top - list TOP investors \n"
        msg += "!top - list worst investors \n"
        msg += "!buy - place BUY order \n"
        msg += "!stock - search for available STOCK \n"
        msg += "```"
        return msg
    @classmethod
    def buy_help(cls):
        """help message"""
        msg = "```"
        msg += "Creates order to BUY Stock\n"
        msg += "USAGE:\n"
        msg += "!buy <stock_code> [credit|shares]\n"
        msg += "\t<stock_code>: code of stock from !stock\n"
        msg += f"\t[credit]: optional, if provided and more than {OrderService.MAX_SHARE_UNITS}\n"
        msg += "\tspend up to the amout for the stock, if ommited, buy as much as possible\n"
        msg += f"\t[shares]: optional, if provided and less or equal than {OrderService.MAX_SHARE_UNITS}\n"
        msg += "\tbuy up to amount of shares of the stock\n"
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

    @classmethod
    def flop_help(cls):
        """help message"""
        msg = "```"
        msg += "List worst investors\n"
        msg += "USAGE:\n"
        msg += "!flop <count>\n"
        msg += "\t<count>: count of the worst investors to display (max 50)\n"
        msg += "```"
        return msg

    @classmethod
    def adminbank_help(cls):
        """help message"""
        msg = "```"
        msg += "USAGE:\n"
        msg += "!adminbank <amount> <user> <reason>\n"
        msg += "\t<amount>: number of credits to add to bank, if negative is used, "
        msg += "it will be deducted from bank\n"
        msg += "\t<user>: user discord name or its part, must be unique\n"
        msg += "\t<reason>: describe why you are changing the coach bank\n"
        msg += "```"
        return msg

    @classmethod
    def adminshare_help(cls):
        """help message"""
        msg = "```"
        msg += "USAGE:\n"
        msg += "!adminshare <stock> <amount> <user> <reason>\n"
        msg += "\t<amount>: number of shares to add to user, if negative is used, "
        msg += "it will be deducted from shares\n"
        msg += "\t<user>: user discord name or its part, must be unique\n"
        msg += "\t<reason>: describe why you are doing this\n"
        msg += "```"
        return msg

    @classmethod
    def stock_help(cls):
        """help message"""
        msg = "```"
        msg += "USAGE:\n"
        msg += "!stock <str>\n"
        msg += "\t<str>: search by team name, stock, code, race or coach name \n"
        msg += "!stock top|bottom|hot|net|gain|loss|detail <X>\n"
        msg += "\ttop: top priced stock\n"
        msg += "\tbottom: bottom priced stock\n"
        msg += "\thot: stock with most bought shares\n"
        msg += "\tnet: stock with most net worth\n"
        msg += "\tgain: stock with most absolute gain\n"
        msg += "\tloss: stock with most absolute loss\n"
        msg += "\tdetail: detailed stock info\n"
        msg += "\t<x>: find X top or bottom stocks, or X is stock code if detail is used\n"
        msg += "```"
        return msg

    # must me under 2000 chars
    async def trade_notification(self, msg, user):
        """Notifies coach about bank change"""

        channel = discord.utils.get(self.client.get_all_channels(), name='trade-notifications')
        await self.send_message(channel, [f"{self.user_mention(user)}: "+msg])
        return

    def user_mention(self, user):
        member = discord.utils.get(self.message.guild.members, id=user.disc_id)
        if member is None:
            mention = user.name
        else:
            mention = member.mention
        return  mention

    # must me under 2000 chars
    async def trade_message(self, msg):
        """Notifies coach about bank change"""
        channel = discord.utils.get(self.client.get_all_channels(), name='trade-notifications')
        await self.send_message(channel, msg)
        return

    async def send_message(self, channel, message_list, block=False):
        """Sends messages to channel"""
        msg = LongMessage(channel, block)
        for message in message_list:
            msg.add(message)
        await msg.send()

    async def reply(self, message_list, block=False):
        """Replies in the same channel"""
        await self.send_message(self.message.channel, message_list, block=block)

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

    # must me under 2000 chars
    async def bank_notification(self, msg, user):
        """Notifies coach about bank change"""
        member = discord.utils.get(self.message.guild.members, id=user.disc_id)
        if member is None:
            mention = user.name
        else:
            mention = member.mention

        channel = discord.utils.get(self.client.get_all_channels(), name='bank-notifications')
        await self.send_message(channel, [f"{mention}: "+msg])
        return

    async def user_unique(self, name):
        """finds uniq coach by name"""
        users = User.find_all_by_name(name)
        if not users:
            await self.reply([f"<user> __{name}__ not found!!!\n"])
            return None

        if len(users) > 1:
            emsg = f"<users> __{name}__ not **unique**!!!\n"
            emsg += "Select one: "
            for user in users:
                emsg += user.name
                emsg += " "
            await self.short_reply(emsg)
            return None
        return users[0]

    def list_messages(self,user):
        msg1 = [
            f"**User:** {user.short_name()}\n",
            f"**Bank:** {round(user.account.amount, 2)} credits\n",
            f"**Shares:**",
        ]
    
        total_value = 0
        msg2 = []
        if user.shares:
            for share in user.shares:
                gain = round(share.stock.unit_price_change, 2)
                if gain > 0:
                    gain = "+"+str(gain)
                elif gain == 0:
                    gain = "0.00"
                else:
                    gain = str(gain)
                msg2.append(
                    '{:5s} - {:25s}: {:3d} x {:7.2f}, Change: {:>7s}'.format(share.stock.code, share.stock.name, share.units, share.stock.unit_price, gain)
                )
                total_value += share.units * share.stock.unit_price
        
        msg3 = []
        msg3.append("**Total Shares Value:** {:9.2f}".format(total_value))
        msg3.append("**Balance:** {:9.2f}".format(total_value+user.account.amount))

        msg3.append("")
        msg3.append(f"**Outstanding Orders:**")
        msg3.append(f"*Sell:*")

        for order in user.orders:
            if not order.processed and order.operation=="sell":
                msg3.append(f"{order.id}. {order.description}")
        msg3.append(" ")

        msg3.append(f"*Buy:*")

        for order in user.orders:
            if not order.processed and order.operation=="buy":
                msg3.append(f"{order.id}. {order.description}")
        msg3.append(" ")

        return msg1, msg2, msg3

    # commands
    async def __run_help(self):
        await self.reply([self.__class__.help_help()])
        return

    async def __run_newuser(self):
        if User.get_by_discord_id(self.message.author.id):
            await self.reply([f"**{self.message.author.mention}** account exists already\n"])
        else:
            user = UserService.new_coach(self.message.author, self.message.author.id)
            msg = [
                f"**{self.message.author.mention}** account created\n",
                f"**Bank:** {round(user.account.amount, 2)} credits",
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

        msg1, msg2, msg3 = self.list_messages(user)
        if user.short_name() in ["MajorStockBot"]:
            await self.reply(msg1)
            await self.reply(msg2, block=True)
            await self.reply(msg3)
        else:
            await self.send_message(self.message.author, msg1)
            await self.send_message(self.message.author, msg2, block=True)
            await self.send_message(self.message.author, msg3)
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

            async def chunk_orders(orders):
                group_count = 10
                order_chunks = [orders[i:i+group_count] for i in range(0, len(orders), group_count)]
                for chunk in order_chunks:
                    msg = []
                    for order in chunk:
                        order = OrderService.process(order)
                        msg.append(f"{self.user_mention(order.user)}: {order.result}")
                    await self.trade_message(msg)
            
            await self.short_reply("Updating DB...")
            StockService.update()
            await self.short_reply("Done")
            await self.short_reply("Closing market...")
            OrderService.close()
            await self.short_reply("Done")

            await self.short_reply("Processing SELL orders...")
            orders = Order.query.order_by(asc(Order.date_created)).filter(Order.processed == False, Order.operation == "sell").all()
            await chunk_orders(orders)
            await self.short_reply("Done")

            await self.short_reply("Processing BUY orders...")
            orders = Order.query.order_by(asc(Order.date_created)).filter(Order.processed == False, Order.operation == "buy").all()
            await chunk_orders(orders)
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
                await self.reply(msg)

            for user in users:
                msg1, msg2, msg3 = self.list_messages(user)
                await self.reply(msg1)
                await self.reply(msg2, block=True)
                await self.reply(msg3)
        
        if self.args[0] == '!adminbank':
            # require username argument
            if len(self.args) < 4:
                await self.reply(["Not enough arguments!!!\n"])
                await self.short_reply(self.__class__.adminbank_help())
                return

            # amount must be int
            if not is_number(self.args[1]) or float(self.args[1]) > 100000000:
                await self.reply(["<amount> is not number or is too high!!!\n"])
                return

            user = await self.user_unique(self.args[2])
            if user is None:
                return

            amount = float(self.args[1])
            reason = ' '.join(str(x) for x in self.message.content.split(" ")[3:]) + " - updated by " + str(self.message.author.name)

            tran = Transaction(description=reason, price=-1*amount)
            try:
                user.make_transaction(tran)
            except TransactionError as e:
                await self.transaction_error(e)
                return
            else:
                msg = [
                    f"Bank for {user.name} updated to **{round(user.account.amount,2)}** credit:\n",
                    f"Note: {reason}\n",
                    f"Change: {amount} credits"
                ]
                await self.reply(msg)
                await self.bank_notification(f"Your bank has been updated by **{amount}** credits - {reason}", user)
                return
        
        if self.args[0] == '!adminshare':
            # require username argument
            if len(self.args) < 5:
                await self.reply(["Not enough arguments!!!\n"])
                await self.short_reply(self.__class__.adminshare_help())
                return

            stocks = Stock.query.filter_by(code=self.args[1]).all()
            if not stocks:
                await self.short_reply(f"<stock> __{self.args[1]}__ not found!!!")
                return

            if len(stocks) > 1:
                emsg = f"<stock> __{name}__ is not **unique**!!!\n"
                emsg += "Select one: "
                for stock in stocks:
                    emsg += stock.code
                    emsg += " "
                await self.short_reply(emsg)
                return

            stock = stocks[0]

            # amount must be int
            if not represents_int(self.args[2]) or int(self.args[2]) > OrderService.MAX_SHARE_UNITS:
                await self.reply([f"{self.args[2]} is not whole number or is higher than {OrderService.MAX_SHARE_UNITS}!!!\n"])
                return

            user = await self.user_unique(self.args[3])
            if user is None:
                return

            amount = int(self.args[2])
            reason = ' '.join(str(x) for x in self.message.content.split(" ")[4:]) + " - updated by " + str(self.message.author.name)
            tran = Transaction(description=reason, price=0)
            try:
                if amount > 0:
                    done = StockService.add(user, stock, amount)
                else:
                    done = StockService.remove(user, stock, -1*amount)
                    if not done:
                        await self.short_reply(f"User {user.short_name()} does not own any shares of __{self.args[1].upper()}__!!!")
                        return
                user.make_transaction(tran)
            except TransactionError as e:
                await self.transaction_error(e)
                return
            else:
                msg = [
                    f"{stock.code} shares for {user.name} has been updated.\n",
                    f"Note: {reason}\n",
                    f"Change: {done} shares"
                ]
                await self.reply(msg)
                await self.bank_notification(f"Your {stock.code} shares has been updated by **{done}** - {reason}", user)
                return
            
    async def __run_stock(self):
        if(self.args[0])=="!stock":
            detail = False
            if len(self.args) < 2:
                await self.reply(["Incorrect number of arguments!!!", self.__class__.stock_help()])
            else:
                limit = 24
                if self.args[1] in ["top", "bottom", "hot", "net", "gain", "loss"] and len(self.args) == 3 and represents_int(self.args[2]) and int(self.args[2]) > 0 and int(self.args[2]) <= limit:
                    if self.args[1] == "top":
                        stocks = Stock.find_top(self.args[2])
                    elif self.args[1] == "bottom":
                        stocks = Stock.find_bottom(self.args[2])
                    elif self.args[1] == "net":
                        stocks = Stock.find_net(self.args[2])
                    elif self.args[1] == "gain":
                        stocks = Stock.find_gain(self.args[2])
                    elif self.args[1] == "loss":
                        stocks = Stock.find_loss(self.args[2])
                    else:
                        stocks = Stock.find_hot(self.args[2])
                elif self.args[1] == "detail" and len(self.args) == 3:
                    detail = True
                    try:
                        stock = Stock.find_by_code(self.args[2])
                        if not stock:
                            await self.reply([f"{self.args[2]} is not unique stock code"])
                            return
                        stocks = [stock]
                    except MultipleResultsFound as exc:
                        await self.reply([f"{self.args[2]} is not unique stock code"])
                        return
                else:
                    stocks = Stock.find_all_by_name(" ".join(self.args[1:]))
                msg = []
                msg.append(
                    '{:5s} - {:25} {:<8s} {:<12s}{:<8s}{:<8s}{:<11s}'.format("Code","Team Name","Division","Unit Price","Change", "Shares", "Net Worth")
                )
                msg.append(80*"-")
                for stock in stocks[0:limit]:
                    msg.append(
                        '{:5s} - {:25} {:<8s} {:10.2f}{:8.2f}{:8d}{:11.2f}'.format(stock.code, stock.name, stock.division, stock.unit_price, stock.unit_price_change, stock.share_count, stock.net_worth)
                    )
                if detail:
                    match = TeamService.get_next_game(stocks[0].name)
                    if match:
                        homeStock = Stock.find_all_by_name(match['homeTeamName'].strip())
                        awayStock = Stock.find_all_by_name(match['awayTeamName'].strip())

                        homePrice = "N/A" if not homeStock else homeStock[0].unit_price
                        awayPrice = "N/A" if not awayStock else awayStock[0].unit_price

                        homeChange = "N/A" if not homeStock else homeStock[0].unit_price_change
                        awayChange = "N/A" if not awayStock else awayStock[0].unit_price_change

                        homeRace = "N/A" if not homeStock else homeStock[0].race
                        awayRace = "N/A" if not awayStock else awayStock[0].race

                        msg.append(" ")
                        msg.append("[Next Match]")
                        msg.append(
                            '{:>38s}  |  {:<37s}'.format("Home","Away")
                        )
                        msg.append(80*"-")
                        msg.append(
                            '{:>38s}  |  {:<37s}'.format(match['homeCoachName'],match['awayCoachName'])
                        )
                        msg.append(
                            '{:>38s}  |  {:<37s}'.format(match['homeTeamName'],match['awayTeamName'])
                        )
                        msg.append(
                            '{:>38s}  |  {:<37s}'.format(homeRace, awayRace)
                        )
                        msg.append(
                            '{:>38.2f}  |  {:<34.2f}'.format(homePrice,awayPrice)
                        )
                        msg.append(
                            '{:>38.2f}  |  {:<34.2f}'.format(homeChange,awayChange)
                        )
                    
                    # only 1 stock
                    msg.append(" ")
                    msg.append("[Owners]")
                    msg.append(" ")
                    msg.append(
                        '{:15s}: {:>8s}{:>11s}'.format("Name","Shares","Net Worth")
                    )
                    msg.append(80*"-")
                    for share in stocks[0].shares:
                        msg.append(
                            '{:15s}: {:8d}{:11.2f}'.format(share.user.short_name(), share.units, round(share.units*share.stock.unit_price,2))
                        )

                    msg.append(" ")
                    msg.append("[History]")
                    msg.append(" ")
                    msg.append(
                        '{:20s}: {:<12s}{:<8s}{:<8s}{:<11s}'.format("Date","Unit Price","Change","Shares", "Net Worth")
                    )
                    msg.append(80*"-")
                    for sh in stocks[0].histories:
                        msg.append(
                            '{:20s}: {:10.2f}{:8.2f}{:8d}{:11.2f}'.format(str(sh.date_created), sh.unit_price, sh.unit_price_change, sh.units, round(sh.units*sh.unit_price,2))
                        )
                        
                if len(stocks) > 20:
                    msg.append("...")
                    msg.append("More stock follows, narrow your search!")
                await self.reply(msg, block=True)

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
                if int(self.args[2]) <= OrderService.MAX_SHARE_UNITS:
                    order_dict['buy_shares'] = self.args[2]
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
            mgs = []
            for order in user.orders:
                if not order.processed:
                    OrderService.cancel(order.id, user)
                    mgs.append(f"Order ID {order.id} has been cancelled")
            await self.reply(mgs)
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

        if not represents_int(self.args[1]) or int(self.args[1]) > 50 or int(self.args[1]) <= 0:
            await self.reply([f"**{self.args[1]}** must be whole positive number and be less or equal 50!"])
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

    async def __run_flop(self):
       
        if len(self.args) not in [2]:
            await self.reply(["Incorrect number of arguments!!!", self.__class__.flop_help()])
            return

        if not represents_int(self.args[1]) or int(self.args[1]) > 50 or int(self.args[1]) <= 0:
            await self.reply([f"**{self.args[1]}** must be whole positive number and be less or equal 50!"])
            return
        
        users = User.query.all()

        user_tuples = []
        for user in users:
            total_value = 0
            for share in user.shares:
                total_value += share.units * share.stock.unit_price
            balance = user.account.amount + total_value
            user_tuples.append((balance, user))

        sorted_users = sorted(user_tuples, key=lambda x: x[0])

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

import logging
import os
import psycopg2
import re
import requests
import sys
import FanFiction

from telegram import MessageEntity
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from telegram.error import (TelegramError, Unauthorized, BadRequest, 
                            TimedOut, ChatMigrated, NetworkError)

# setting constants
BOT_NAME = "FicTrackerBot"
WELCOME_MESSAGE = ("Hi! I'm " + BOT_NAME + ", and I can help you track updates "
                    "of the fanfictions you are reading.\n"
                    "Send me a message with a link to the fanfiction you are following, "
                    "and I will start to track it (only one link per message, please!)\n"
                    "I'm sorry, but at the moment I support only AO3 fanfics!")
NO_LINK_MESSAGE = "There is no link in this message!"
SITE_NOT_SUPPORTED_MESSAGE = "This site is not supported!"
FANFIC_NOT_EXIST_MESSAGE = "This link is not valid!"
HELP_MESSAGE = ("/start - Starts the chat with the bot\n"
                "/updates - To receive the fanfictions updated since the last request\n"
                "/list - To list all the fanfictions being tracked\n"
                "/remove - Must be followed by a fanfiction url, removes it from the tracking")
FANFICTION_ADDED_MESSAGE = "Fanfiction correctly added to tracking!"
SUPPORTED_SITES = ["archiveofourown.org"]

# getting environment variables
mode = os.getenv("MODE")
TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

# defining possible queries
ADD_USER = "insert into users(id, updates) select {0}, False where not exists (select * from users where id = {0})"
ADD_FANFICTION = "insert into fanfictions(id, url, chapters) select {0}, '{1}', {2} where not exists (select * from fanfictions where id = {0} and url = '{1}')"
GET_USER_FANFICTION = "select url, chapters from fanfictions where id = {}"
REMOVE_FANFICTION = "delete from fanfictions where id = {} and url = '{}'"
SET_UPDATES = "update users set updates = {} where id = {}"
UPDATE_FANFICTION = "update fanfictions set chapters = {} where id = {} and url = '{}'"

# enabling logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger()

# defining updater based on execution mode
if mode == "dev":
    def run(updater):
        updater.start_polling()
elif mode == "prod":
    def run(updater):
        PORT = int(os.environ.get("PORT", "8443"))
        HEROKU_APP_NAME = os.environ.get("HEROKU_APP_NAME")
        updater.start_webhook(listen="0.0.0.0", port=PORT, url_path=TOKEN)
        updater.bot.set_webhook("https://{}.herokuapp.com/{}".format(HEROKU_APP_NAME, TOKEN))
else:
    logger.error("No mode specified")
    sys.exit(1)

# ------------------------------------------------------------------------------------- #

# handler function for /start command
def start_handler(bot, update):
    logger.info("User {} started bot".format(update.effective_user["id"]))
    update.message.reply_text(WELCOME_MESSAGE)
    __execute_query__(ADD_USER.format(update.effective_user["id"]))

# handler function for /updates command
def updates_handler(bot, update):
    logger.info("User {} requested their updates".format(update.effective_user["id"]))
    # read from database and send updates

# handler function for /list command
def list_handler(bot, update):
    logger.info("User {} requested the list of their fanfictions".format(update.effective_user["id"]))
    query_result = __execute_query__(GET_USER_FANFICTION.format(update.effective_user["id"]))
    fanfictions = []
    for row in query_result:
        fanfictions.append(FanFiction.AO3FanFic(row[0]))
    message = ""
    for ff in fanfictions:
        message = message + ff + "\n"
    update.message.reply_text(message)

# handler function for /help command
def help_handler(bot, update):
    update.message.reply_text(HELP_MESSAGE)

# handler message for /remove command
def remove_handler(bot, update):
    logger.info("User {} asked to remove {} from their fanfictions".format(update.effective_user["id"], update.message.text))
    # remove fanfiction from database

# handler function for normal messages containing a link
def link_handler(bot, update):
    message = update.message.text
    link = __parse_message__(message)
    if link is None:
        update.message.reply_text(NO_LINK_MESSAGE)
    else:
        site = __site_from_link__(link)
        if site is not None:
            if __is_valid__(link):
                logger.info("User {} added a fanfic".format(update.effective_user["id"]))
                fanfic = FanFiction.AO3FanFic(link)
                query_result = __execute_query__(ADD_FANFICTION.format(update.effective_user["id"], fanfic.url, fanfic.chapters))
                if query_result is not None:
                    update.message.reply_text(FANFICTION_ADDED_MESSAGE)
            else:
                update.message.reply_text(FANFIC_NOT_EXIST_MESSAGE)
        else:
            update.message.reply_text(SITE_NOT_SUPPORTED_MESSAGE)

# handler functions for errors
def error_handler(bot, update, error):
    try:
        raise error
    except Unauthorized:
        # remove update.message.chat_id from conversation list
        pass
    except BadRequest:
        # handle malformed requests - read more below!
        pass
    except TimedOut:
        # handle slow connection problems
        pass
    except ChatMigrated:
        # handle other connection problems
        pass
    except NetworkError:
        # the chat_id of a group has changed, use e.new_chat_id instead
        pass
    except TelegramError:
        # handle all other telegram related errors
        pass


# ------------------------------------------------------------------------------------- #

# parsing message to find links
def __parse_message__(message):
    urls = re.findall('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', message)
    if len(urls) > 1:
        return None
    else:
        return urls[0]

# returns the site of the link
def __site_from_link__(link):
    for site in SUPPORTED_SITES:
            if site in link:
                return site
    return None

# check if the link is reachable
def __is_valid__(link):
    page = requests.get(link)
    if page.status_code == 200:
        return True
    else:
        return False

# executes the given query
def __execute_query__(query):
    query_result = None
    conn = None
    try:
        # connection to database
        conn = psycopg2.connect(DATABASE_URL, sslmode='prefer')
        # creating cursor
        cur = conn.cursor()
        # executing query
        cur.execute(query)
        # collecting results, if presents
        if cur.description is not None:
            query_result = cur.fetchall()
        # committing changes
        conn.commit()
    except (Exception, psycopg2.DatabaseError) as exception:
        # problems with the database
        logger.error(exception)
    finally:
        if conn is not None:
            conn.close()
        return query_result

# ------------------------------------------------------------------------------------- #

if __name__ == '__main__':
    logger.info("Starting bot")
    # creating bot
    updater = Updater(TOKEN)
    # adding handlers to bot
    updater.dispatcher.add_handler(CommandHandler("start", start_handler))
    updater.dispatcher.add_handler(CommandHandler("updates", updates_handler))
    updater.dispatcher.add_handler(CommandHandler("list", list_handler))
    updater.dispatcher.add_handler(CommandHandler("help", help_handler))
    updater.dispatcher.add_handler(CommandHandler("remove", remove_handler))
    updater.dispatcher.add_handler(MessageHandler(Filters.text & Filters.entity(MessageEntity.URL) | Filters.entity(MessageEntity.TEXT_LINK), link_handler))
    updater.dispatcher.add_error_handler(error_handler)
    # starting bot
    run(updater)



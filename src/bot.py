import logging
import os
import sys
import re
import requests

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
SUPPORTED_SITES = ["archiveofourown.org"]

# enabling logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger()

# getting environment variables
mode = os.getenv("MODE")
TOKEN = os.getenv("TOKEN")

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

# handler function for /updates command
def updates_handler(bot, update):
    logger.info("User {} requested their updates".format(update.effective_user["id"]))
    # read from database and send updates

# handler function for normal messages
# only messages with a fanfiction link will receive an answer
def message_handler(bot, update):
    message = update.message.text
    link = __parseMessage__(message)
    if link is None:
        update.message.reply_text(NO_LINK_MESSAGE)
    else:
        site = __siteFromLink__(link)
        if site is not None:
            if __isValid__(link):
                logger.info("User {} added a fanfic".format(update.effective_user["id"]))
                # add fanfic to database
            else:
                update.message.reply_text(FANFIC_NOT_EXIST_MESSAGE)
        else:
            update.message.reply_text(SITE_NOT_SUPPORTED_MESSAGE)

def link_handler(bot, update):


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
def __parseMessage__(message):
    urls = re.findall('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', message)
    if len(urls) > 1:
        return None
    else:
        return urls[0]

# returns the site of the link
def __siteFromLink__(link):
    for site in SUPPORTED_SITES:
            if site in link:
                return site
    return None

# check if the link is reachable
def __isValid__(link):
    page = requests.get(link)
    if page.status_code == 200:
        return True
    else:
        return False

# ------------------------------------------------------------------------------------- #

if __name__ == '__main__':
    logger.info("Starting bot")
    # creating bot
    updater = Updater(TOKEN)
    # adding handlers to bot
    updater.dispatcher.add_handler(CommandHandler("start", start_handler))
    updater.dispatcher.add_handler(CommandHandler("updates", updates_handler))
    updater.dispatcher.add_handler(MessageHandler(Filters.text, message_handler))
    updater.dispatcher.add_error_handler(error_handler)
    # starting bot
    run(updater)



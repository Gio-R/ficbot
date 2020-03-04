import logging
import os
import psycopg2
import re
import requests
import sys
import FanFiction

from psycopg2 import sql
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
NO_LINK_MESSAGE = "Please send one and only one link!"
SITE_NOT_SUPPORTED_MESSAGE = "This site is not supported!"
FANFIC_NOT_EXIST_MESSAGE = "This link is not valid!"
ADD_PROBLEMS_MESSAGE = "There were problems in adding this fanfiction to tracking! Are you sure it exists?"
HELP_MESSAGE = ("/start - Starts the chat with the bot\n"
                "/updates - To receive the fanfictions updated since the last request\n"
                "/list - To list all the fanfictions being tracked\n"
                "/remove - Must be followed by a fanfiction url, removes it from the tracking\n"
                "/setupdates - Activates/deactivates periodic updates")
FANFICTION_ADDED_MESSAGE = "Fanfiction correctly added to tracking!"
FANFICTION_REMOVED_MESSAGE = "Fanfiction correctly removed from tracking!"
WAIT_MESSAGE = "This could require a bit of time. Be patient!"
NO_FANFICTIONS_IN_TRACKING = "You are not following any fanfiction!"
NO_UPDATES_MESSAGE = "There are no updates"
NO_UPDATES_DAILY_MESSAGE = "There are no updates today"
UPDATES_SET = "Receiving periodic updates: {} (not abilitated)"
NO_LINK_TO_REMOVE_MESSAGE = ("There was no fanfiction to remove! "
                             "Please use /remove followed by the link of the fanfiction you want removed.")
USERS_TABLE = "users"
FANFICTIONS_TABLE = "fanfictions"
MAX_MESSAGE_SIZE = 3000
SUPPORTED_SITES = { "archiveofourown.org": FanFiction.AO3FanFic }

# getting environment variables
mode = os.getenv("MODE")
TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
SSL_DB = os.getenv("SSL_DB")

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
    query, named_values = __get_insert_query__(["id", "updates"], ["id"], [update.effective_user["id"], False], USERS_TABLE)
    __execute_query__(query, named_values)

# handler function for /updates command
def updates_handler(bot, update):
    logger.info("User {} requested their updates".format(update.effective_user["id"]))
    update.message.reply_text(WAIT_MESSAGE)
    updated_fics = __get_updated_fics__(update.effective_user["id"])
    if len(updated_fics) > 0:
        message = __fics_to_message__(updated_fics)
    else:
        message = NO_UPDATES_MESSAGE
    __send_message__(update, message)

# handler function for /list command
def list_handler(bot, update):
    logger.info("User {} requested the list of their fanfictions".format(update.effective_user["id"]))
    where_dict = { "id" : update.effective_user["id"] }
    user_fics, success = __execute_query__(__get_select_query__(["url", "chapters", "title", "author", "completeness"], where_dict.keys(), FANFICTIONS_TABLE), where_dict)
    if user_fics is not None:
        fanfictions = []
        for row in user_fics:
            fanfictions.append(FanFiction.FanFiction(row[0], row[2], row[3], row[1], row[4]))
        if len(fanfictions) > 0:
            message = ""
            for ff in fanfictions:
                message = message + str(ff) + "\n"
        else:
            message = NO_FANFICTIONS_IN_TRACKING
        __send_message__(update, message)

# handler function for /help command
def help_handler(bot, update):
    update.message.reply_text(HELP_MESSAGE)

# handler message for /remove command
def remove_handler(bot, update):
    logger.info("User {} asked to remove a tracked fanfiction".format(update.effective_user["id"]))
    link = __parse_message__(update.message.text)
    if link is not None:
        query_result, success = __execute_query__(REMOVE_FANFICTION.format(update.effective_user["id"], link))
        if success:
            update.message.reply_text(FANFICTION_REMOVED_MESSAGE)
    else:
        update.message.reply_text(NO_LINK_TO_REMOVE_MESSAGE)

# handler function for normal messages containing a link
def link_handler(bot, update):
    message = update.message.text
    link = __parse_message__(message)
    if link is None:
        update.message.reply_text(NO_LINK_MESSAGE)
    else:
        site = __site_from_link__(link)
        if site is None:
            update.message.reply_text(SITE_NOT_SUPPORTED_MESSAGE)
        else:
            try:
                logger.info("User {} tried to add a fanfic".format(update.effective_user["id"]))
                fanfic = SUPPORTED_SITES[site](link)
                if fanfic is not None:
                    query, named_values = __get_insert_query__(["id", "url", "chapters", "title", "author", "completeness"],
                                                                ["id", "url"], 
                                                                [update.effective_user["id"], fanfic.url, fanfic.chapters, fanfic.title, fanfic.author, fanfic.complete],
                                                                FANFICTIONS_TABLE)
                    query_result, success = __execute_query__(query, named_values)
                    if success:
                        logger.info("User {} added a fanfic".format(update.effective_user["id"]))
                        update.message.reply_text(FANFICTION_ADDED_MESSAGE)
                else:
                    update.message.reply_text(ADD_PROBLEMS_MESSAGE)
            except Exception as ex:
                update.message.reply_text(ADD_PROBLEMS_MESSAGE)
                logger.error(ex)

# handler function for /setupdates command
def setupdates_handler(bot, update):
    logger.info("User {} toggled their updates".format(update.effective_user["id"]))
    where_dict = {"id" : update.effective_user["id"]}
    query_result, success = __execute_query__(__get_select_query__(["updates"], where_dict.keys(), USERS_TABLE), where_dict)
    for row in query_result:
        value_to_set = not row[0]
        updates_dict = {"updates": value_to_set}
        where_dict = {"id" : update.effective_user["id"]}
        q_result, succ = __execute_query__(__get_update_query__(updates_dict.keys(), where_dict.keys(), USERS_TABLE), {**updates_dict, **where_dict})
        if succ:
            update.message.reply_text(UPDATES_SET.format(value_to_set))

# handler functions for errors
def error_handler(bot, update, error):
    try:
        logger.error(error)
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
    except Exception:
        # handle other errors
        pass

# ------------------------------------------------------------------------------------- #

# parsing message to find links
def __parse_message__(message):
    urls = re.findall('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', message)
    if len(urls) != 1:
        return None
    else:
        return urls[0]

# returns the site of the link
def __site_from_link__(link):
    for site in SUPPORTED_SITES.keys():
            if site in link:
                return site
    return None

# executes the given query
def __execute_query__(query, named_values):
    query_result = None
    conn = None
    success = False
    try:
        # connection to database
        conn = psycopg2.connect(DATABASE_URL, sslmode=SSL_DB)
        # creating cursor
        cur = conn.cursor()
        # executing query
        cur.execute(query, named_values)
        # collecting results, if presents
        if cur.description is not None:
            query_result = cur.fetchall()
        # committing changes
        conn.commit()
        success = True
    except (Exception, psycopg2.DatabaseError) as exception:
        # problems with the database
        logger.error(exception)
    finally:
        if conn is not None:
            conn.close()
        return query_result, success

# custom toString for a fanfiction
def __fic_to_message__(fic, last_chapter_read):
    if fic.complete:
        completeness = "yes"
    else:
        completeness = "no"
    return ("\"" + fic.title + "\" by " + fic.author + "\n\tLast published chapter: " 
            + str(fic.chapters) + "\n\tLast read chapter: " + str(last_chapter_read) 
            + "\n\tComplete: " + completeness + "\n" + fic.url + "\n" + "\n")

# return a string representing a list of fanfictions, using __fic_to_message__
def __fics_to_message__(fanfics):
    message = ""
    for fic, last_chapter_read in fanfics:
        message = message + __fic_to_message__(fic, last_chapter_read)
    return message

# searches the updated fanfics of the given user
def __get_updated_fics__(id):
    where_dict = {"id" : id}
    user_fics, success = __execute_query__(__get_select_query__(["url", "chapters", "title", "author", "completeness"], where_dict.keys(), FANFICTIONS_TABLE), where_dict)
    updated_fics = []
    for row in user_fics:
        link = row[0]
        chapters = row[1]
        fic = SUPPORTED_SITES[__site_from_link__(link)](link)
        if fic is not None and (fic.chapters != chapters):
            updated_fics.append((fic, chapters))
            set_dict = {"chapters" : fic.chapters}
            where_dict = {"id": id, "url" : fic.url}
            __execute_query__(__get_update_query__(set_dict.keys(), where_dict.keys(), FANFICTIONS_TABLE), {**set_dict, **where_dict})
        elif fic is None:
            logger.info(link + " couldn't be checked")
    return updated_fics

# sends a message checking if it's too long
def __send_message__(update, message):
    if len(message) > MAX_MESSAGE_SIZE:
        pieces = message.split("\n\n")
        while len(pieces) > 0:
            m = ""
            shorter = True
            while shorter and len(pieces) > 0:
                piece = pieces[0]
                new_m = m + "\n\n" + piece
                if len(new_m) < MAX_MESSAGE_SIZE:
                    m = new_m
                    pieces.pop(0)
                else:
                    shorter = False
            update.message.reply_text(m)
    else:
        update.message.reply_text(message)

# ------------------------------------------------------------------------------------- #

# returns a query to insert values in the columns of a table, checking that the values of the keys are not repeated
def __get_insert_query__(columns, keys, values, table):
    named_values = dict(zip(columns, values))
    query = sql.SQL("insert into {}({}) select {} where not exists (select * from {} where {})").format(
                    sql.Identifier(table), 
                    sql.SQL(",").join(map(sql.Identifier, columns)),
                    sql.SQL(",").join(map(sql.Placeholder, columns)),
                    sql.Identifier(table),
                    sql.SQL(" and ").join([sql.SQL("{} = {}").format(sql.Identifier(c), sql.Placeholder(name=c)) for c in keys]))
    return query, named_values

# returns a query that select the columns in select_columns, checking the values in where_columns in a table
def __get_select_query__(select_columns, where_columns, table):
    if len(where_columns) > 0:
        query = sql.SQL("select {} from {} where {}").format(
                        sql.SQL(",").join(map(sql.Identifier, select_columns)),
                        sql.Identifier(table),
                        sql.SQL(" and ").join([sql.SQL("{} = {}").format(sql.Identifier(k), sql.Placeholder(name=k)) for k in where_columns]))
    else:
        query = sql.SQL("select {} from {}").format(
                        sql.SQL(",").join(map(sql.Identifier, select_columns)),
                        sql.Identifier(table))
    return query

# returns a query that updates the values in update_columns, checking the values of where_columns in a table
def __get_update_query__(update_columns, where_columns, table):
    if len(where_columns) > 0:
        query = sql.SQL("update {} set {} where {}").format(
                        sql.Identifier(table),
                        sql.SQL(",").join([sql.SQL("{} = {}").format(sql.Identifier(c), sql.Placeholder(name=c)) for c in update_columns]),
                        sql.SQL(" and ").join([sql.SQL("{} = {}").format(sql.Identifier(k), sql.Placeholder(name=k)) for k in where_columns]))
    else:
        query = sql.SQL("update {} set {}").format(
                        sql.Identifier(table),
                        sql.SQL(",").join([sql.SQL("{} = {}").format(sql.Identifier(c), sql.Placeholder(name=c)) for c in update_columns]))
    return query

# returns a query that removes the rows of table satisfying conditions on where_columns
def __get_remove_query__(where_columns, table):
    if len(where_columns) > 0:
        query = sql.SQL("delete from {} where {}").format(
                        sql.Identifier(table),
                        sql.SQL(" and ").join([sql.SQL("{} = {}").format(sql.Identifier(k), sql.Placeholder(name=k)) for k in where_columns]))
    else:
        query = sql.SQL("delete from {}").format(sql.Identifier(table))
    return query

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
    updater.dispatcher.add_handler(CommandHandler("setupdates", setupdates_handler))
    updater.dispatcher.add_handler(MessageHandler(Filters.text & Filters.entity(MessageEntity.URL) | Filters.entity(MessageEntity.TEXT_LINK), link_handler))
    updater.dispatcher.add_error_handler(error_handler)
    # starting bot
    run(updater)

# ------------------------------------------------------------------------------------- #

# function for sending periodic updates
def send_updates():
    logger.info("Starting bot for updates")
    # creating bot
    updater = Updater(TOKEN)
    # starting bot
    run(updater)
    # sending updates
    query_result, success = __execute_query__(__get_select_query__(["id", "updates"], [], USERS_TABLE), {})
    for row in query_result:
        if row[1] == True:
            updated_fics = __get_updated_fics__(row[0])
            if len(updated_fics) > 0:
                message = __fics_to_message__(updated_fics)
            else:
                message = NO_UPDATES_DAILY_MESSAGE
            updater.bot.send_message(chat_id=row[0], text=message)

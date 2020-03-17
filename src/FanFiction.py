import logging
import http.cookiejar
import urllib.request
from bs4 import BeautifulSoup

# enabling logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger()

def AO3FanFic(url):
    parsedUrl = ao3urlParsing(url)
    mature_url = parsedUrl + "?view_adult=true"
    cj = http.cookiejar.CookieJar()
    try:
        opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler, urllib.request.HTTPCookieProcessor(cj))
        page = opener.open(mature_url)
        soup = BeautifulSoup(page.read(), "html.parser")
        title = soup.find("h2",{"class":"title heading"}).text
        title = " ".join(title.split())
        author = soup.find("h3", {"class":"byline heading"}).text
        author = " ".join(author.split())
        chaptersInfo = soup.find("dd", {"class":"chapters"}).text
        chapters = chaptersInfo.split("/")
        lastChapter = int(chapters[0], 10)
        if chapters[1] == "?":
            complete = False
        else:
            endChapter = int(chapters[1], 10)
            if endChapter == lastChapter:
                complete = True
            else:
                complete = False
        return FanFiction(parsedUrl, title, author, lastChapter, complete)
    except urllib.error.HTTPError as e:
        logger.error("HTTP Error " + str(e.code) + " while examining " + url)
        return None
    except:
        logger.error("Error while examining " + url)
        return None
        

def ao3urlParsing(url):
    parsedUrl = url.split("chapters")[0]
    if parsedUrl[-1] == "/":
        parsedUrl = parsedUrl[:-1]
    return parsedUrl

# ------------------------------------------------------------------------------------- #

class FanFiction():
    def __init__(self, url, title, author, chapters, complete):
        self.url = url
        self.title = title
        self.chapters = chapters
        self.author = author
        self.complete = complete

    def __str__(self):
        if self.complete:
            completeness = "yes"
        else:
            completeness = "no"
        return "\"" + self.title + "\" by " + self.author + "\n\tLast published chapter: " + str(self.chapters) + "\n\tComplete: " + completeness + "\n" + self.url + "\n"

    def __eq__(self, other): 
        if not isinstance(other, FanFic):
            return False
        return self.url == other.url

    def __ne__(self, other): 
        return not self.__eq__

    def __hash__(self):
        return (self.url.__hash__())
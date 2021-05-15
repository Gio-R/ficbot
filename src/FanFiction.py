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

def RoyalRoadFanFic(url):
    parsedUrl = royalRoaUrlParsing(url)
    try:
        opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler)
        page = opener.open(parsedUrl)
        soup = BeautifulSoup(page.read(), "html.parser")
        title = soup.find("h1",{"property":"name"}).text
        title = " ".join(title.split())
        author = soup.find("h4", {"property":"author"}).text
        author = " ".join(author.split())
        chapters_links = [tag.get("data-url") for tag in soup.findAll('tr', attrs={'style': 'cursor: pointer'})] #TODO: fix this and go from here
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
        

def royalRoaUrlParsing(url):
    parsedUrl = url.split("chapter")[0]
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

def __get_headers_to_bypass_cloudflare__():
    # TODO: CHECK THIS
    WINDOW_SIZE = "1920,1080"

    chrome_options = Options()  
    chrome_options.add_argument("--headless")
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.163 Safari/537.36"
    chrome_options.add_argument("--window-size=%s" % WINDOW_SIZE)
    chrome_options.add_argument("user-agent="+user_agent)
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])

    driver = webdriver.Chrome(options=chrome_options)
    driver.get("https://www.royalroad.com/")
    driver.get_screenshot_as_file("capture.png")
    time.sleep(10)
    #html = driver.page_source
    cookies = " ".join([c["name"]+"="+c["value"]+";" for c in driver.get_cookies()])
    headers = {"user-agent":user_agent, "cookie":cookies}
    driver.close()
    return headers
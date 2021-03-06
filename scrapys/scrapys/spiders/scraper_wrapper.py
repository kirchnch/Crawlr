# inspired by https://doc.scrapy.org/en/latest/topics/practices.html
# Script: scraper_wrapper.py
# Description: wrapper script for scraper_scrapy.py
# Author: Chris Kirchner
# Email: kirchnch@oregonstate.edu

from twisted.internet import reactor
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
import sys, signal, os

# set settings module
os.environ['SCRAPY_SETTINGS_MODULE'] = 'scrapys.settings'
# add scraper to path
sys.path.append(os.path.join(os.getcwd(), 'scrapys'))

# get options
start_url = sys.argv[1]
max_levels = sys.argv[2]
keyword = sys.argv[3]
search_type = sys.argv[4]


process = CrawlerProcess(get_project_settings())

# set scraper to follow dfs or bfs behavior
if int(search_type) == 0:
    # DFS
    # Scrapy naturally uses DFO search order
    process.settings.set('DEPTH_PRIORITY', 0)
    process.settings.set('CONCURRENT_REQUESTS', 1)

elif int(search_type) == 1:
    # BFS
    process.settings.set('DEPTH_PRIORITY', 1)
    process.settings.set('SCHEDULER_DISK_QUEUE', 'scrapy.squeues.PickleFifoDiskQueue')
    process.settings.set('SCHEDULER_MEMORY_QUEUE', 'scrapy.squeues.FifoMemoryQueue')

process.settings.set('DEPTH_LIMIT', max_levels)

# setup signal handler to catch SIGINT from mothership
def sig_handler(sig, frame):
    process.stop()
    reactor.stop()

signal.signal(signal.SIGINT, sig_handler)

# start scraper
process.crawl('scraper_scrapy', start_url=start_url, keyword=keyword)
process.start()

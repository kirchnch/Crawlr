# Script: bfs.py
# Description: multithreaded bfs and dfs scraper that collects all links starting with single url and sends to server
# Author: Chris Kirchner
# Email: kirchnch@oregonstate.edu

import threading
from bs4 import UnicodeDammit
from queue import Queue
from queue import LifoQueue
import requests
from lxml import html as parser
import sys
import json
from time import sleep
from contextlib import closing
from random import random
from random import shuffle

NUM_THREADS = 50
MAX_DOWNLOAD_SIZE = 500000
MAX_REQUEST_DELAY = 2

# scraper class for threading
class Scraper(threading.Thread):

    def __init__(self, unvisited, visited, unvisited_lock, visited_lock, max_levels, keyword, single_path=False):

        # inherit and setup thread variables from input
        super(Scraper, self).__init__()
        self.unvisited = unvisited
        self.visited = visited
        self.visited_lock = visited_lock
        self.unvisited_lock = unvisited_lock
        self.max_levels = max_levels
        self.keyword = keyword


    def _getLink(self):

        """
        getLink: returns link from queue
        :return: link
        """
        link = None
        visited = True
        while visited:
            link = self.unvisited.get()
            with self.visited_lock:
                if link.get('url') not in self.visited:
                    visited = False
                    self.visited.add(link.get('url'))
        return link

    def _addLinks(self, hrefs, parent):

        """
        addLinks: adds scrapped links to queue
        :param hrefs: scrapped links
        :param parent: parent link
        """
        level = parent.get('level')+1
        with self.unvisited_lock:
            shuffle(hrefs)
            for href in hrefs:
                link = dict()
                link['url'] = href
                link['level'] = level
                link['parent_url'] = parent['url']
                self.unvisited.put(link)

    def _getLinks(self, tree):
        """
        getLinks: returns links from lxml tree
        :param tree: lxml tree built from html
        :return: found links
        """
        # anchors = tree.cssselect("a")
        anchors = tree.xpath("//a")
        links = list()
        for a in anchors:
            links.append(a.get('href'))
        return links

    def _findKeyword(self, tree):
        """
        findKeyword: searches for keyword in displayable text from html
        :param tree:
        :return:
        """
        if self.keyword in tree.xpath("string()"):
            return True
        return False

    def _getHtml(self, link):
        html = None
        # try to connect to link

        try:
            headers = {'accept': 'text/html'}
            with closing(requests.get(link.get('url'), timeout=1, headers=headers, stream=True)) as r:
                if r.status_code == 200 \
                        and int(r.headers.get('content-length', 0)) < MAX_DOWNLOAD_SIZE \
                        and (r.headers.get('content-type', None).split(';')[0] == 'text/html'
                             or r.headers.get('content-type', None) is None):
                    # http://stackoverflow.com/questions/16694907/how-to-download-large-file-in-python-with-requests-py
                    it = r.iter_content(chunk_size=1024)
                    html = "{}".format(it.__next__())
                    if "<html" in html:
                        for chunk in r.iter_content(chunk_size=1024):
                            html = "{}{}".format(html, chunk)
                    else:
                        html = None
                else:
                    html = None
        except requests.RequestException as e:
            print(e, file=sys.stderr)
            # only follow OK links that contain html
        finally:
            return html

    def _getTree(self, html, base_url):
        # try to build lxml tree with unicoded html
        tree = None
        try:
            # convert possibly bad html to unicode
            damn_html = UnicodeDammit(html)
            # convert html into lxml tree
            tree = parser.fromstring(damn_html.unicode_markup)
            del damn_html
            # make all links absolute based on url
            tree.make_links_absolute(base_url)
        except Exception as e:
            print(e, file=sys.stderr)
        finally:
            return tree

    def run(self):
        """
        override threading run function
        """
        while True:
            # gets link from queue
            link = self._getLink()
            html = None
            if link is not None:
                html = self._getHtml(link)
            tree = None
            if html is not None:
                tree = self._getTree(html, link.get('url'))
            if tree is not None:
                # search for keyword in html text
                link['keyword'] = False
                if len(self.keyword) != 0 and self._findKeyword(tree):
                    # trigger script interrupt with keyword
                    link['keyword'] = True
                link['title'] = tree.xpath('//title/text()')
                # send link to server through stdout
                print(json.dumps(link))
                if link.get('level') < int(self.max_levels):
                    links = self._getLinks(tree)
                    del tree
                    self._addLinks(links, link)
                elif single_path and link.get('level') == int(self.max_levels):
                    self.unvisited.task_done()
                    break
            # mark task as done for queue.join
            self.unvisited.task_done()
            sleep(random()*MAX_REQUEST_DELAY)



if __name__ == "__main__":

    # get script arguments from server
    start_url = sys.argv[1]
    max_levels = sys.argv[2]
    keyword = sys.argv[3]
    search_type = sys.argv[4]

    # use lock to visited links so only one thread can update at a time
    visited_lock = threading.Lock()
    unvisited_lock = threading.Lock()
    # make visited links a hashed set so there are not duplicates
    # a bloom filter may improve performance with less memory
    visited_links = set()
    # create a queue of unvisited links added by threads as they scrape
    single_path = False
    if int(search_type) == 0:
        # DFS
        unvisited_links = LifoQueue()
    elif int(search_type) == 1:
        # BFS
        unvisited_links = Queue()
    elif int(search_type) == 2:
        # DFS
        NUM_THREADS = 1
        unvisited_links = LifoQueue()
        single_path = True

    threads = list()

    first_link = dict()
    first_link['url'] = start_url
    first_link['parent_url'] = None
    first_link['level'] = 0
    # add first link to queue
    unvisited_links.put(first_link)

    # setups and start threads
    for t in range(NUM_THREADS):
        s = Scraper(unvisited_links, visited_links, unvisited_lock, visited_lock, max_levels, keyword, single_path)
        s.daemon = True
        s.start()
        threads.append(s)

    # wait for queue to be empty and all tasks done, then exit
    unvisited_links.join()

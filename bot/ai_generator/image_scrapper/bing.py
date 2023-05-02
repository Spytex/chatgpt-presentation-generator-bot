import imghdr
import logging
import re
import urllib.parse

from aiohttp import ClientSession


class Bing:
    def __init__(self, query, limit, adult, timeout, filter='', blocked_sites=None, verbose=True):
        self.download_count = 0
        self.image = 0
        self.query = query
        self.adult = adult
        self.filter = filter
        self.blocked_sites = blocked_sites
        self.verbose = verbose
        self.seen = set()

        assert type(limit) == int, "limit must be integer"
        self.limit = limit
        assert type(timeout) == int, "timeout must be integer"
        self.timeout = timeout

        self.page_counter = 0
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
            'Accept-Encoding': 'none',
            'Accept-Language': 'en-US,en;q=0.8',
            'Connection': 'keep-alive'}

        self.logger = logging.getLogger(__name__)

    async def get_filter(self, shorthand):
        match shorthand:
            case("line"):
                return "+filterui:photo-linedrawing"
            case("linedrawing"):
                return "+filterui:photo-linedrawing"
            case("photo"):
                return "+filterui:photo-photo"
            case("clipart"):
                return "+filterui:photo-clipart"
            case("gif"):
                return "+filterui:photo-animatedgif"
            case("animatedgif"):
                return "+filterui:photo-animatedgif"
            case("transparent"):
                return "+filterui:photo-transparent"
            case _:
                return shorthand

    async def save_image(self, link):
        print(link)
        for site in self.blocked_sites:
            if site in link:
                raise ValueError("Blocked site found in URL: " + link)
        async with ClientSession() as session:
            async with session.get(link, timeout=self.timeout) as response:
                image = await response.read()

        supported_formats = ["jpeg", "png", "gif"]
        if not imghdr.what(None, image) or imghdr.what(None, image) not in supported_formats:
            error_msg = f'Invalid image, not saving {link}'
            self.logger.error(error_msg)
            raise ValueError(error_msg)

        return image

    async def download_image(self, link):
        self.download_count += 1
        try:
            if self.verbose:
                self.logger.info(f'[%] Downloading Image #{self.download_count} from {link}')

            image = await self.save_image(link)

            if self.verbose:
                self.logger.info('[%] File Downloaded !\n')
            return image

        except Exception as e:
            self.download_count -= 1
            self.logger.error(f'[!] Issue getting: {link}\n[!] Error:: {e}')

    async def run(self):
        async with ClientSession() as session:
            while self.download_count < self.limit:
                if self.verbose:
                    self.logger.info(f'\n\n[!!]Indexing page: {self.page_counter + 1}\n')
                # Parse the page source and download pics
                request_url = 'https://www.bing.com/images/async?q=' + urllib.parse.quote_plus(self.query) \
                              + '&first=' + str(self.page_counter) + '&count=' + str(self.limit) \
                              + '&adlt=' + self.adult + '&qft=' + (
                                  '' if self.filter is None else await self.get_filter(self.filter))
                self.logger.debug(request_url)
                async with session.get(request_url, headers=self.headers) as response:
                    html = await response.text()
                self.logger.debug(html)
                if html == "":
                    self.logger.info('[%] No more images are available')
                    break
                links = re.findall('murl&quot;:&quot;(.*?)&quot;', html)
                if self.verbose:
                    self.logger.info(f'[%] Indexed {len(links)} Images on Page {self.page_counter + 1}.')
                    self.logger.info('\n===============================================\n')
                for link in links:
                    if self.download_count < self.limit and link not in self.seen:
                        self.seen.add(link)
                        self.image = await self.download_image(link)

                self.page_counter += 1
        self.logger.info(f'\n\n[%] Done. Downloaded {self.download_count} images.')

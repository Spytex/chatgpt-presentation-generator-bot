import urllib.request
import urllib
import imghdr
import re


class Bing:
    def __init__(self, query, limit, adult, timeout, filter='', verbose=True):
        self.download_count = 0
        self.image = []
        self.query = query
        self.adult = adult
        self.filter = filter
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

    def get_filter(self, shorthand):
        if shorthand == "line" or shorthand == "linedrawing":
            return "+filterui:photo-linedrawing"
        elif shorthand == "photo":
            return "+filterui:photo-photo"
        elif shorthand == "clipart":
            return "+filterui:photo-clipart"
        elif shorthand == "gif" or shorthand == "animatedgif":
            return "+filterui:photo-animatedgif"
        elif shorthand == "transparent":
            return "+filterui:photo-transparent"
        else:
            return shorthand

    def save_image(self, link):
        request = urllib.request.Request(link, None, self.headers)
        image = urllib.request.urlopen(request, timeout=self.timeout).read()
        if not imghdr.what(None, image):
            print('[Error]Invalid image, not saving {}\n'.format(link))
            raise ValueError('Invalid image, not saving {}\n'.format(link))
        return image

    def download_image(self, link):
        self.download_count += 1
        # Get the image link
        try:

            if self.verbose:
                # Download the image
                print("[%] Downloading Image #{} from {}".format(self.download_count, link))

            image = self.save_image(link)

            if self.verbose:
                print("[%] File Downloaded !\n")
                return image

        except Exception as e:
            self.download_count -= 1
            print("[!] Issue getting: {}\n[!] Error:: {}".format(link, e))

    def run(self):
        while self.download_count < self.limit:
            if self.verbose:
                print('\n\n[!!]Indexing page: {}\n'.format(self.page_counter + 1))
            # Parse the page source and download pics
            request_url = 'https://www.bing.com/images/async?q=' + urllib.parse.quote_plus(self.query) \
                          + '&first=' + str(self.page_counter) + '&count=' + str(self.limit) \
                          + '&adlt=' + self.adult + '&qft=' + (
                              '' if self.filter is None else self.get_filter(self.filter))
            print(request_url)
            request = urllib.request.Request(request_url, None, headers=self.headers)
            print(request)
            response = urllib.request.urlopen(request)
            print(response)
            html = response.read().decode('utf8')
            print(html)
            if html == "":
                print("[%] No more images are available")
                break
            links = re.findall('murl&quot;:&quot;(.*?)&quot;', html)
            if self.verbose:
                print("[%] Indexed {} Images on Page {}.".format(len(links), self.page_counter + 1))
                print("\n===============================================\n")
            for link in links:
                if self.download_count < self.limit and link not in self.seen:
                    self.seen.add(link)
                    self.image.append(self.download_image(link))

            self.page_counter += 1
        print("\n\n[%] Done. Downloaded {} images.".format(self.download_count))

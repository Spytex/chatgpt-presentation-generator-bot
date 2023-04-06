from bing import Bing


def download(query, limit=100, adult_filter_off=True,
             timeout=60, filter="", verbose=True):
    # engine = 'bing'
    if adult_filter_off:
        adult = 'off'
    else:
        adult = 'on'

    bing = Bing(query, limit, adult, timeout, filter, verbose)
    bing.run()
    return bing.image


if __name__ == '__main__':
    download('dog', limit=10, timeout=1)
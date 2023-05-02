try:
    from bing import Bing
except ImportError:
    from .bing import Bing


async def download(query, limit=100, adult_filter_off=True,
                   timeout=60, filter="", verbose=True, block_sites=True):
    if adult_filter_off:
        adult = 'off'
    else:
        adult = 'on'
    blocked_sites = []
    if block_sites:
        blocked_sites = ["alamy.com", "dreamstime.com", "istockphoto.com", "bigstockphoto.com"]

    bing = Bing(query, limit, adult, timeout, filter, blocked_sites, verbose)
    await bing.run()
    return bing.image


if __name__ == '__main__':
    download('dog', limit=10, timeout=1)

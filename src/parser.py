from lxml import etree
from config import base_url
def parse_fang_detail(html):
    tree = etree.HTML(html)

    title_list = tree.xpath('//div[@class="wid1200 clearfix"]//span/text()')
    price_list = tree.xpath('//div[@class="tab-cont-right"]//i/text()')

    # 只要有一个缺失，直接丢弃
    if not title_list or not price_list:
        return {}

    return {
        "title": title_list[0].strip(),
        "price": price_list[0].strip()
    }
def parse_fang_href(html):
    tree = etree.HTML(html)
    hrefs = tree.xpath('//div[@class="shop_list shop_list_4"]//h4[@class="clearfix"]/a/@href')
    print(hrefs)
    fang_urls = [base_url + href for href in hrefs if href is not None]
    print(fang_urls)
    return fang_urls
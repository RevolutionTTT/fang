from lxml import etree
from config import base_url
def parse_fang_detail(html):
    tree = etree.HTML(html)
    title = tree.xpath('//div[@class="wid1200 clearfix"]//span/text()')
    price = tree.xpath('//div[@class="tab-cont-right"]//i/text()')
    title = title[0] if title else "未命名"
    price = price[0] if price else "未定价"
    fang = {
        "title": title,
        "price": price

    }
    return fang
def parse_fang_href(html):
    tree = etree.HTML(html)
    hrefs = tree.xpath('//div[@class="shop_list shop_list_4"]//h4[@class="clearfix"]/a/@href')
    print(hrefs)
    fang_urls = [base_url + href for href in hrefs if href is not None]
    print(fang_urls)
    return fang_urls
"""Public list metadata only: Arca gift category and Ppomppu's official RSS."""
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime, format_datetime
from html.parser import HTMLParser
from urllib.parse import urlsplit, parse_qs, urljoin
import re
import xml.etree.ElementTree as ET

ARCA = 'https://arca.live/b/hotdeal?category=gift'
PPOMPPU = 'https://www.ppomppu.co.kr/rss.php?id=ppomppu'
CHANNELS = {'arcalive': 'https://arca.live/b/hotdeal',
            'ppomppu': 'https://www.ppomppu.co.kr/zboard/zboard.php?id=ppomppu'}


class Node:
    def __init__(self, tag='', attrs=()):
        self.tag, self.attrs, self.children = tag, dict(attrs), []

    def has(self, cls):
        return cls in self.attrs.get('class', '').split()

    def nodes(self, predicate):
        return ([self] if predicate(self) else []) + [n for c in self.children
                if isinstance(c, Node) for n in c.nodes(predicate)]

    def text(self):
        if self.has('info') or self.has('media-icon') or self.tag in ['script','style']:
            return ''
        return ''.join(c.text() if isinstance(c, Node) else c for c in self.children)


class Document(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.stack = [self.root]
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in ['area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr']:
            self.stack.append(node)

    def handle_endtag(self, tag):
        for i in range(len(self.stack)-1, 0, -1):
            if self.stack[i].tag == tag:
                self.stack = self.stack[:i]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def recent(date, now):
    try:
        t = datetime.fromisoformat(date.replace('Z','+00:00')) if re.match(r'^\d{4}-',date) else parsedate_to_datetime(date)
        return t if t.tzinfo and now-timedelta(days=7) <= t <= now else None
    except (ValueError, TypeError, OverflowError):
        return None


def post_url(source, value):
    u = urlsplit(value)
    if u.username or u.password or u.port or u.fragment:
        return None
    if source == 'arcalive' and u.scheme == 'https' and u.netloc == 'arca.live' and re.fullmatch(r'/b/hotdeal/\d{5,12}',u.path):
        return 'https://arca.live'+u.path
    if source == 'ppomppu' and u.scheme in ['http','https'] and u.netloc == 'www.ppomppu.co.kr' and u.path == '/zboard/view.php':
        q = parse_qs(u.query)
        if q.get('id') == ['ppomppu'] and len(q.get('no',[])) == 1 and re.fullmatch(r'\d{5,12}',q['no'][0]):
            return 'https://www.ppomppu.co.kr/zboard/view.php?id=ppomppu&no='+q['no'][0]
    return None


def arca_rows(raw, now):
    doc = Document(raw.decode('utf-8', errors='strict')).root
    canon = doc.nodes(lambda n:n.tag=='link' and n.attrs.get('rel')=='canonical')
    # HTML challenge or changed list is a failure, never a fresh empty feed.
    rows = doc.nodes(lambda n:n.has('vrow') and n.has('hybrid'))
    if len(canon)!=1 or canon[0].attrs.get('href') not in [ARCA,CHANNELS['arcalive']] or not rows:
        raise ValueError('unexpected_arcalive_list')
    result=[]
    for row in rows[:100]:
        if row.nodes(lambda n:n.has('deal-close')):
            continue
        if not row.nodes(lambda n:n.tag=='a' and n.attrs.get('href')=='/b/hotdeal?category=gift'):
            continue
        titles=row.nodes(lambda n:n.tag=='a' and n.has('hybrid-title'))
        prices=row.nodes(lambda n:n.has('deal-price'))
        shipping=row.nodes(lambda n:n.has('deal-delivery'))
        dates=row.nodes(lambda n:n.tag=='time' and 'datetime' in n.attrs)
        stores=row.nodes(lambda n:n.has('deal-store'))
        if any(len(x)!=1 for x in [titles,prices,shipping,dates]):
            continue
        title=' '.join(titles[0].text().split())
        link=post_url('arcalive',urljoin('https://arca.live',titles[0].attrs.get('href','')))
        date=recent(dates[0].attrs['datetime'],now)
        price=prices[0].text().strip()
        if not link or not date or not re.fullmatch(r'[\d,]+원',price) or shipping[0].text().strip()!='무료':
            continue
        if len(stores)==1 and re.fullmatch(r'[\w가-힣 .-]{1,40}',stores[0].text().strip()):
            title='['+stores[0].text().strip()+'] '+title
        result.append(dict(title=title,link=link,pubDate=format_datetime(date),price=price.replace('원','').replace(',',''),shipping='무료'))
    return result


def ppomppu_rows(raw, now):
    if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise ValueError('unexpected_xml')
    root=ET.fromstring(raw)
    channels=root.findall('channel')
    if root.tag!='rss' or len(channels)!=1 or channels[0].findtext('link') not in [CHANNELS['ppomppu'],CHANNELS['ppomppu'].replace('https:','http:')]:
        raise ValueError('unexpected_ppomppu_feed')
    result=[]
    for item in channels[0].findall('item')[:200]:
        if any(len(item.findall(t))!=1 for t in ['title','link','pubDate']):
            continue
        title=(item.findtext('title') or '').strip()
        if not re.search(r'상품권|금액권|기프트|기프티콘|교환권|모바일\s*쿠폰|아메리카노',title):
            continue
        link=post_url('ppomppu',item.findtext('link') or '')
        date=recent(item.findtext('pubDate') or '',now)
        if link and date:
            result.append(dict(title=title,link=link,pubDate=format_datetime(date)))
    return result


def community_feed(source, raw, now):
    if len(raw)>1_500_000:
        raise ValueError('response_too_large')
    rows=arca_rows(raw,now) if source=='arcalive' else ppomppu_rows(raw,now)
    root=ET.Element('rss',version='2.0'); channel=ET.SubElement(root,'channel')
    for tag,value in [('title','상품권핫딜 공개 게시가격'),('link',CHANNELS[source]),('lastBuildDate',format_datetime(now))]:
        ET.SubElement(channel,tag).text=value
    seen=set()
    for row in rows:
        if row['link'] in seen or not 1<=len(row['title'])<=500 or re.search(r'종료|품절|증정|추첨|일일적립|클릭\s*적립',row['title']):
            continue
        seen.add(row['link']); item=ET.SubElement(channel,'item')
        for tag,value in row.items():
            ET.SubElement(item,tag).text=value
    return ET.tostring(root,encoding='utf-8',xml_declaration=True)

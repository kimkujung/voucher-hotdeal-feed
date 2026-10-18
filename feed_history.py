"""Bounded history of posted metadata; never a statement of current availability."""
from email.utils import format_datetime
import re
import xml.etree.ElementTree as ET
from community_feeds import CHANNELS, post_url, recent

CHANNELS = {**CHANNELS, 'ruliweb': 'https://bbs.ruliweb.com/market/board/1020'}


def document(raw, source):
    if len(raw)>1_500_000 or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise ValueError('unexpected_xml')
    root=ET.fromstring(raw)
    channels=root.findall('channel')
    if root.tag!='rss' or len(channels)!=1 or len(channels[0].findall('link'))!=1 or channels[0].findtext('link')!=CHANNELS[source]:
        raise ValueError('unexpected_channel')
    return channels[0]


def canonical(source, link):
    if source=='ruliweb':
        return link if re.fullmatch(r'https://bbs\.ruliweb\.com/market/board/1020/read/\d{5,12}',link) else None
    return post_url(source,link)


def retain_recent(source, fresh, previous, now):
    current=document(fresh,source)
    dates=current.findall('lastBuildDate')
    updated=recent(dates[0].text or '',now) if len(dates)==1 else None
    if not updated or (now-updated).total_seconds()>7200:
        raise ValueError('invalid_update_time')
    old=None
    if previous:
        try: old=document(previous,source)
        except (ValueError,ET.ParseError): pass
    # Old first, newly observed metadata wins for the same canonical post.
    kept={}
    for channel in [old,current]:
        if channel is None: continue
        for item in channel.findall('item')[:200]:
            if any(len(item.findall(t))!=1 for t in ['title','link','pubDate']): continue
            title=(item.findtext('title') or '').strip()
            link=canonical(source,(item.findtext('link') or '').strip())
            published=recent(item.findtext('pubDate') or '',now)
            if not link or not published or not 1<=len(title)<=500: continue
            fields=dict(title=title,link=link,pubDate=format_datetime(published))
            if source=='arcalive':
                if len(item.findall('price'))!=1 or len(item.findall('shipping'))!=1: continue
                price=(item.findtext('price') or '').strip()
                if not re.fullmatch(r'\d{1,10}',price) or item.findtext('shipping')!='무료': continue
                fields.update(price=price,shipping='무료')
            kept[link]=(published,fields)
    root=ET.Element('rss',version='2.0'); channel=ET.SubElement(root,'channel')
    for tag,value in [('title','상품권핫딜 최근 게시가격'),('link',CHANNELS[source]),('lastBuildDate',dates[0].text)]:
        ET.SubElement(channel,tag).text=value
    for _,fields in sorted(kept.values(),key=lambda x:(x[0],x[1]['link']),reverse=True)[:200]:
        item=ET.SubElement(channel,'item')
        for tag,value in fields.items(): ET.SubElement(item,tag).text=value
    return ET.tostring(root,encoding='utf-8',xml_declaration=True)

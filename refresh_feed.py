"""Publish minimal public voucher RSS metadata. No credentials or AI APIs."""
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime, format_datetime
from pathlib import Path
import re
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from community_feeds import ARCA, PPOMPPU, community_feed

SOURCE = 'https://bbs.ruliweb.com/market/board/1020/rss'
CHANNEL = 'https://bbs.ruliweb.com/market/board/1020'
POST = re.compile(r'https://bbs\.ruliweb\.com/market/board/1020/read/\d{5,12}')


def minimal_feed(raw: bytes, now: datetime) -> bytes:
    if len(raw) > 512_000 or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise ValueError('unexpected_xml')
    root = ET.fromstring(raw)
    channels = root.findall('./channel')
    if root.tag != 'rss' or len(channels) != 1 or channels[0].findtext('link') != CHANNEL:
        raise ValueError('unexpected_channel')
    result = ET.Element('rss', version='2.0')
    channel = ET.SubElement(result, 'channel')
    for tag, value in [('title', '상품권핫딜 공개 게시가격'), ('link', CHANNEL),
                       ('description', '상품권 게시물의 최소 정보와 원문 링크'),
                       ('lastBuildDate', format_datetime(now))]:
        ET.SubElement(channel, tag).text = value
    seen = set()
    for item in channels[0].findall('item')[:200]:
        if any(len(item.findall(tag)) != 1 for tag in ['title','link','pubDate']):
            continue
        title = (item.findtext('title') or '').strip()
        link = (item.findtext('link') or '').strip()
        date = (item.findtext('pubDate') or '').strip()
        if not POST.fullmatch(link) or link in seen or not 1 <= len(title) <= 500:
            continue
        if not re.search(r'상품권|금액권|기프트|기프티콘|교환권|모바일\s*쿠폰', title):
            continue
        if re.search(r'종료|품절|증정|추첨|일일적립|클릭\s*적립', title):
            continue
        try:
            published = parsedate_to_datetime(date)
            if published.tzinfo is None or not now-timedelta(days=7) <= published <= now:
                continue
        except (ValueError, TypeError, OverflowError):
            continue
        seen.add(link)
        dest = ET.SubElement(channel, 'item')
        for tag, value in [('title', title), ('link', link), ('pubDate', date)]:
            ET.SubElement(dest, tag).text = value
    return ET.tostring(result, encoding='utf-8', xml_declaration=True)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch_feed(url, content_types, limit):
    request = urllib.request.Request(url, headers={
        'User-Agent': 'VoucherHotdeal/0.1 (+public deal information; low-frequency)'})
    # One ordinary GET. A failure keeps the previous feed; no fallback IP/cookie/UA.
    with urllib.request.build_opener(NoRedirect).open(request, timeout=15) as response:
        if response.headers.get_content_type() not in content_types:
            raise ValueError('unexpected_content_type')
        raw = response.read(limit+1)
        if len(raw)>limit: raise ValueError('response_too_large')
        return raw


def main():
    successes=0
    for name,url in [('ruliweb',SOURCE),('arcalive',ARCA),('ppomppu',PPOMPPU)]:
        target=Path('data')/(name+'.xml')
        stopped=Path('data')/(name+'.disabled')
        if stopped.exists():
            print('::warning::'+name+' is paused after an HTTP access restriction; review before resuming.')
            continue
        try:
            types=['text/html'] if name=='arcalive' else ['text/xml','application/xml','application/rss+xml']
            raw=fetch_feed(url,types,1_500_000 if name=='arcalive' else 512_000)
            now=datetime.now(timezone.utc)
            data=minimal_feed(raw,now) if name=='ruliweb' else community_feed(name,raw,now)
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(data)
            successes+=1
            print('Updated '+name+' minimal public feed.')
        except Exception as error:
            # Keep the prior file and timestamp for this source. Never print response bodies.
            reason='http_'+str(error.code) if isinstance(error,urllib.error.HTTPError) else type(error).__name__
            if isinstance(error,urllib.error.HTTPError) and error.code in [401,403,429]:
                stopped.parent.mkdir(parents=True,exist_ok=True)
                stopped.write_text(reason+'\n',encoding='utf-8')
            print('::warning::'+name+' refresh failed: '+reason)
    if not successes: raise RuntimeError('all_source_requests_failed')


if __name__ == '__main__':
    main()

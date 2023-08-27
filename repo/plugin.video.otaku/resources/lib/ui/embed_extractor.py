import base64
import binascii
import json
import random
import re
import string
import time
import requests

from resources.lib.ui import client, control, jsunpack
from resources.lib.ui.pyaes import AESModeOfOperationCBC, Decrypter, Encrypter
from urllib import error, parse


_EMBED_EXTRACTORS = {}
_EDGE_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.102 Safari/537.36 Edge/18.18363'

def load_video_from_url(in_url):
    found_extractor = None

    for extractor in list(_EMBED_EXTRACTORS.keys()):
        if in_url.startswith(extractor):
            found_extractor = _EMBED_EXTRACTORS[extractor]
            break

    if found_extractor is None:
        return None

    try:
        if found_extractor['preloader'] is not None:
            in_url = found_extractor['preloader'](in_url)

        data = found_extractor['data']
        if data is not None:
            return found_extractor['parser'](in_url,
                                             data)

        control.log("Probing source: %s" % in_url)
        res = requests.get(in_url)

        return found_extractor['parser'](res.url, res.text, res.headers.get('Referer'))
    except error.URLError:
        pass  # Dead link, Skip result


def __get_packed_data(html):
    packed_data = ''
    for match in re.finditer(r'(eval\s*\(function\(p,a,c,k,e.+?\)\)[;\n<])', html, re.DOTALL | re.I):
        packed_data += jsunpack.unpack(match.group(1))

    return packed_data


def __append_headers(headers):
    return '|%s' % '&'.join(['%s=%s' % (key, parse.quote_plus(headers[key])) for key in headers])


def __extract_mp4upload(url, page_content, referer=None):
    page_content += __get_packed_data(page_content)
    r = re.search(r'src\("([^"]+)', page_content) or re.search(r'src:\s*"([^"]+)', page_content)
    headers = {
        'User-Agent': _EDGE_UA,
        'Referer': url,
        'verifypeer': 'false'
    }
    if r:
        return r.group(1) + __append_headers(headers)


def __extract_kwik(url, page_content, referer=None):
    page_content += __get_packed_data(page_content)
    r = re.search(r"const\s*source\s*=\s*'([^']+)", page_content)
    if r:
        headers = {
            'User-Agent': _EDGE_UA,
            'Referer': url
        }
        return r.group(1) + __append_headers(headers)


def __extract_okru(url, page_content, referer=None):
    pattern = r'(?://|\.)(ok\.ru|odnoklassniki\.ru)/(?:videoembed|video|live)/(\d+)'
    host, media_id = re.findall(pattern, url)[0]
    aurl = "http://www.ok.ru/dk"
    data = {
        'cmd': 'videoPlayerMetadata',
        'mid': media_id
    }
    data = parse.urlencode(data)
    r = requests.post(aurl, data=data)
    if r.ok:
        json_data = r.json()
        strurl = json_data.get('hlsManifestUrl')
        return strurl


def __extract_mixdrop(url, page_content, referer=None):
    r = re.search(r'(?:vsr|wurl|surl)[^=]*=\s*"([^"]+)', __get_packed_data(page_content))
    if r:
        surl = r.group(1)
        if surl.startswith('//'):
            surl = 'https:' + surl
        headers = {
            'User-Agent': _EDGE_UA,
            'Referer': url
        }
        return surl + __append_headers(headers)

def __extract_dood(url, page_content, referer=None):
    def dood_decode(pdata):
        t = string.ascii_letters + string.digits
        return pdata + ''.join([random.choice(t) for _ in range(10)])

    pattern = r'(?://|\.)(dood(?:stream)?\.(?:com?|watch|to|s[ho]|cx|la|w[sf]|pm))/(?:d|e)/([0-9a-zA-Z]+)'
    match = re.search(r'''dsplayer\.hotkeys[^']+'([^']+).+?function\s*makePlay.+?return[^?]+([^"]+)''', page_content, re.DOTALL)
    if match:
        host, media_id = re.findall(pattern, url)[0]
        token = match.group(2)
        nurl = 'https://{0}{1}'.format(host, match.group(1))
        html = client.request(nurl, referer=url)
        headers = {
            'User-Agent': _EDGE_UA,
            'Referer': url
        }
        return dood_decode(html) + token + str(int(time.time() * 1000)) + __append_headers(headers)


def __extract_streamlare(url, page_content, referer=None):
    pattern = r'(?://|\.)((?:streamlare|sl(?:maxed|tube|watch))\.(?:com?|org))/(?:e|v)/([0-9A-Za-z]+)'
    host, media_id = re.findall(pattern, url)[0]
    headers = {
        'User-Agent': _EDGE_UA,
        'Referer': url
    }
    api_durl = 'https://{0}/api/video/download/get'.format(host)
    api_surl = 'https://{0}/api/video/stream/get'.format(host)
    data = {
        'id': media_id
    }
    r = requests.post(api_surl, headers=headers, json=data)
    r = r.json()
    result = r.get('result', {})
    source = result.get('file') or result.get('Original', {}).get('file') or result.get(list(result.keys())[0], {}).get('file')
    if not source:
        r = requests.post(api_durl, headers=headers, json=data)
        source = r.json().get('result', {}).get('Original', {}).get('url')

    if source:
        if '?token=' in source:
            r = requests.get(source, allow_redirects=False, headers=headers)
            if r.ok:
                source = r.headers.get('Location')
        return source + __append_headers(headers)


def __extract_streamtape(url, page_content, referer=None):
    groups = re.search(r"document\.getElementById\(.*?\)\.innerHTML = [\"'](.*?)[\"'] \+ [\"'](.*?)[\"']", page_content)
    stream_link = f'https:{groups.group(1)}{groups.group(2)}'
    return stream_link


def __extract_streamsb(url, page_content, referer=None):
    def get_embedurl(host_, media_id_):
        def makeid(length):
            t = string.ascii_letters + string.digits
            return ''.join([random.choice(t) for _ in range(length)])

        x = '{0}||{1}||{2}||streamsb'.format(makeid(12), media_id_, makeid(12))
        c1 = binascii.hexlify(x.encode('utf8')).decode('utf8')
        x = '7Vd5jIEF2lKy||nuewwgxb1qs'
        c2 = binascii.hexlify(x.encode('utf8')).decode('utf8')
        return 'https://{0}/{1}7/{2}'.format(host_, c2, c1)

    pattern = r'(?://|\.)((?:streamsb|streamsss|sb(?:lanh|ani|rapic))\.(?:net|com|pro))/e/([0-9a-zA-Z]+)'
    host, media_id = re.findall(pattern, url)[0]
    eurl = get_embedurl(host, media_id)
    headers = {
        'User-Agent': _EDGE_UA,
        'Referer': 'https://{0}/'.format(host),
        'watchsb': 'sbstream'
    }
    r = requests.get(eurl, headers=headers, cookies={'lang': '1'})
    data = r.json().get("stream_data", {})
    strurl = data.get('file') or data.get('backup')
    if strurl:
        headers.pop('watchsb')
        headers.update({'Origin': 'https://{0}'.format(host)})
        return strurl + __append_headers(headers)


def __extract_xstreamcdn(url, data):
    r = requests.post(url, data=data)
    if r.ok:
        res = r.json()['data']
        if res == 'Video not found or has been removed':
            return
        stream_file = res[-1]['file']
        r = requests.get(stream_file, allow_redirects=False)
        stream_link = (r.headers['Location']).replace('https', 'http')
        return stream_link


def __extract_goload(url, page_content, referer=None):
    def _encrypt(msg, key, iv_):
        key = key.encode()
        encrypter = Encrypter(AESModeOfOperationCBC(key, iv_))
        ciphertext = encrypter.feed(msg)
        ciphertext += encrypter.feed()
        ciphertext = base64.b64encode(ciphertext)
        return ciphertext.decode()

    def _decrypt(msg, key, iv_):
        ct = base64.b64decode(msg)
        key = key.encode()
        decrypter = Decrypter(AESModeOfOperationCBC(key, iv_))
        decrypted = decrypter.feed(ct)
        decrypted += decrypter.feed()
        return decrypted.decode()

    pattern = r'(?://|\.)((?:gogo-(?:play|stream)|streamani|goload|gogohd|vidstreaming|gembedhd|playgo1|anihdplay|playtaku|gotaku1)\.' \
              r'(?:io|pro|net|com|cc|online))/(?:streaming|embed(?:plus)?|ajax|load)(?:\.php)?\?id=([a-zA-Z0-9-]+)'
    r = re.search(r'crypto-js\.js.+?data-value="([^"]+)', page_content)
    if r:
        host, media_id = re.findall(pattern, url)[0]
        keys = ['37911490979715163134003223491201', '54674138327930866480207815084989']
        iv = '3134003223491201'.encode()
        params = _decrypt(r.group(1), keys[0], iv)
        eurl = 'https://{0}/encrypt-ajax.php?id={1}&alias={2}'.format(
            host, _encrypt(media_id, keys[0], iv), params)
        r = requests.get(eurl)
        if r.ok:
            response = r.json().get('data')
            if response:
                result = _decrypt(response, keys[1], iv)
                result = json.loads(result)
                str_url = ''
                if len(result.get('source')) > 0:
                    str_url = result.get('source')[0].get('file')
                if not str_url and len(result.get('source_bk')) > 0:
                    str_url = result.get('source_bk')[0].get('file')
                if str_url:
                    headers = {'User-Agent': _EDGE_UA,
                               'Referer': 'https://{0}/'.format(host),
                               'Origin': 'https://{0}'.format(host)}
                    return str_url + __append_headers(headers)


def __register_extractor(urls, function, url_preloader=None, datas=[]):
    if not isinstance(urls, list):
        urls = [urls]

    if not datas:
        datas = [None] * len(urls)

    for url, data in zip(urls, datas):
        _EMBED_EXTRACTORS[url] = {
            "preloader": url_preloader,
            "parser": function,
            "data": data
        }


__register_extractor(["https://www.mp4upload.com/",
                      "https://mp4upload.com/"],
                     __extract_mp4upload)

__register_extractor(["https://kwik.cx/"],
                     __extract_kwik)

__register_extractor(["https://mixdrop.co/",
                      "https://mixdrop.to/",
                      "https://mixdrop.sx/",
                      "https://mixdrop.bz/",
                      "https://mixdrop.ch/",
                      "https://mixdrp.co/"],
                     __extract_mixdrop)

__register_extractor(["https://ok.ru/",
                      "odnoklassniki.ru"],
                     __extract_okru)

__register_extractor(["https://dood.wf/",
                      "https://dood.pm/"],
                     __extract_dood)

__register_extractor(["https://gogo-stream.com",
                      "https://gogo-play.net",
                      "https://streamani.net",
                      "https://goload.one"
                      "https://goload.io/",
                      "https://goload.pro/",
                      "https://gogohd.net/",
                      "https://gogohd.pro/",
                      "https://gembedhd.com/",
                      "https://playgo1.cc/",
                      "https://anihdplay.com/",
                      "https://playtaku.net/",
                      "https://playtaku.online/",
                      "https://gotaku1.com/"],
                     __extract_goload)

__register_extractor(["https://streamlare.com/",
                      "https://slmaxed.com/",
                      "https://sltube.org/",
                      "https://slwatch.co/"],
                     __extract_streamlare)

__register_extractor(["https://www.xstreamcdn.com/v/",
                      "https://gcloud.live/v/",
                      "https://www.fembed.com/v/",
                      "https://www.novelplanet.me/v/",
                      "https://fcdn.stream/v/",
                      "https://embedsito.com",
                      "https://fplayer.info",
                      "https://fembed-hd.com",
                      "https://fembed9hd.com"],
                     __extract_xstreamcdn,
                     lambda x: x.replace('/v/', '/api/source/'),
                     [{'d': 'www.xstreamcdn.com'},
                      {'d': 'gcloud.live'},
                      {'d': 'www.fembed.com'},
                      {'d': 'www.novelplanet.me'},
                      {'d': 'fcdn.stream'},
                      {'d': 'embedsito.com'},
                      {'d': 'fplayer.info'},
                      {'d': 'fembed-hd.com'},
                      {'d': 'fembed9hd.com'}])

__register_extractor(["https://streamtape.com/e/"],
                     __extract_streamtape)

__register_extractor(["https://sbembed.com/e/",
                      "https://sbembed1.com/e/",
                      "https://sbplay.org/e/",
                      "https://sbvideo.net/e/",
                      "https://streamsb.net/e/",
                      "https://sbplay.one/e/",
                      "https://cloudemb.com/e/",
                      "https://playersb.com/e/",
                      "https://tubesb.com/e/",
                      "https://sbplay1.com/e/",
                      "https://embedsb.com/e/",
                      "https://watchsb.com/e/",
                      "https://sbplay2.com/e/",
                      "https://japopav.tv/e/",
                      "https://viewsb.com/e/",
                      "https://sbplay2.xyz/e/",
                      "https://sbfast.com/e/",
                      "https://sbfull.com/e/",
                      "https://javplaya.com/e/",
                      "https://ssbstream.net/e/",
                      "https://p1ayerjavseen.com/e/",
                      "https://sbthe.com/e/",
                      "https://vidmovie.xyz/e/",
                      "https://sbspeed.com/e/",
                      "https://streamsss.net/e/",
                      "https://sblanh.com/e/",
                      "https://sbani.pro/e/",
                      "https://sbrapid.com/e/"],
                     __extract_streamsb)
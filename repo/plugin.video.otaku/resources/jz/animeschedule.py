import requests
import datetime
import re

from bs4 import BeautifulSoup
from resources.lib.ui import database

from resources.lib.ui import control

base_url = "https://animeschedule.net/api/v3"
dub_list = []


def get_route(anilist_id):
    params = {
        "anilist-ids": anilist_id
    }
    r = requests.get(f'{base_url}/anime', params=params)
    return r.json()['anime'][0]['route']


def get_dub_time(anilist_id):
    show = database.get_show(anilist_id)
    route = show['anime_schedule_route']
    if not route:
        route = get_route(anilist_id)
        database.update_show(anilist_id, show['mal_id'], show['kodi_meta'], show['last_updated'], route)
    r = requests.get(f'https://animeschedule.net/anime/{route}')
    soup = BeautifulSoup(r.text, 'html.parser')
    soup_all = soup.find_all('div', class_='release-time-wrapper')
    for soup in soup_all:
        if 'dub:' in soup.text.lower():
            dub_soup = soup
            dub_text = dub_soup.span.text
            date_time = dub_soup.time.get('datetime')

            if '-' in dub_text:
                match = re.match(r'Episodes (\d+)-(\d+)', dub_text)
                ep_begin = int(match.group(1))
                ep_end = int(match.group(2))
                for ep_number in range(ep_begin, ep_end):
                    add_to_list(ep_number, date_time)
            else:
                match = re.match(r'Episode (\d+)', dub_text)
                ep_number = int(match.group(1))
                add_to_list(ep_number, date_time)
            return dub_list


def add_to_list(ep_number, date_time):
    try:
        dub_time = str(datetime.datetime.strptime(date_time[:16], "%Y-%m-%dT%H:%M") - datetime.timedelta(hours=5))[:16]
    except TypeError:
        import time
        date_time = re.sub('T', '', date_time)
        date_time = re.sub(':', '', date_time)
        dub_time = str(datetime.datetime(*(time.strptime(date_time[:14], "%Y-%m-%d%H%M")[0:7])) - datetime.timedelta(hours=5))[:16]
    dub_list.append({"season": 0, "episode": ep_number, "release_time": dub_time})

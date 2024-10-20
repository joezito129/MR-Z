import pickle
import requests

from resources.lib import pages
from resources.lib import indexers
from resources.lib.indexers import simkl, anizip, jikanmoe
from resources.lib.ui import control, database, utils

if control.settingids.browser_api == 'mal':
    from resources.lib.MalBrowser import MalBrowser
    BROWSER = MalBrowser()
else:
    from resources.lib.AniListBrowser import AniListBrowser
    BROWSER = AniListBrowser()

def parse_history_view(res):
    return utils.allocate_item(res, f'search/{res}/1', True, False)


def search_history(search_array):
    result = [utils.allocate_item("New Search", "search//1", True, False, 'new_search.png')]
    result += list(map(parse_history_view, search_array))
    result.append(utils.allocate_item("Clear Search History...", "clear_search_history", False, False, 'clear_search_history.png'))
    return result


def get_episodeList(mal_id, pass_idx):
    show = database.get_show(mal_id)
    kodi_meta = pickle.loads(show['kodi_meta'])
    if kodi_meta['format'] in ['MOVIE', 'ONA', 'SPECIAL', 'Movie', 'Special'] and kodi_meta['episodes'] == 1:
        title = kodi_meta['title_userPreferred'] or kodi_meta['name']
        info = {
            "title": title,
            "mediatype": 'movie',
            'plot': kodi_meta['plot'],
            'rating': kodi_meta['rating'],
            'premiered': str(kodi_meta['start_date']),
            'year': int(str(kodi_meta['start_date'])[:4])
        }
        items = [utils.allocate_item(title, 'null', False, True, info=info, poster=kodi_meta['poster'])]

    else:
        episodes = database.get_episode_list(mal_id)
        items = indexers.process_episodes(episodes, '') if episodes else []
        playlist = control.bulk_player_list(items)[pass_idx:]
        for i in playlist:
            control.playList.add(url=i[0], listitem=i[1])
    return items


def get_backup(mal_id, source):
    params = {
        "type": "myanimelist",
        "id": mal_id
    }
    r = requests.get("https://arm2.vercel.app/api/kaito-b", params=params)
    return r.json().get('Pages', {}).get(source, {}) if r.ok else {}


def get_anime_init(mal_id):
    show_meta = database.get_show_meta(mal_id)
    if not show_meta:
        BROWSER.get_anime(mal_id)
        show_meta = database.get_show_meta(mal_id)
        if not show_meta:
            return [], 'episodes'

    if control.getBool('override.meta.api'):
        meta_api = control.getSetting('meta.api')
        if meta_api == 'simkl':
            data = simkl.SIMKLAPI().get_episodes(mal_id, show_meta)
        elif meta_api == 'anizip':
            data = anizip.ANIZIPAPI().get_episodes(mal_id, show_meta)
        else:    # elif meta_api == 'jikanmoa':
            data = jikanmoe.JikanAPI().get_episodes(mal_id, show_meta)

    else:
        data = simkl.SIMKLAPI().get_episodes(mal_id, show_meta)
        if not data[0]:
            data = anizip.ANIZIPAPI().get_episodes(mal_id, show_meta)
        if not data[0]:
            data = jikanmoe.JikanAPI().get_episodes(mal_id, show_meta)
        if not data[0]:
            data = [], 'episodes'
    return data


def get_sources(mal_id, episode, media_type, rescrape=False, source_select=False, silent=False):
    if not (show := database.get_show(mal_id)):
        show = BROWSER.get_anime(mal_id)
    kodi_meta = pickle.loads(show['kodi_meta'])
    actionArgs = {
        'query': kodi_meta['query'],
        'mal_id': mal_id,
        'episode': episode,
        'status': kodi_meta['status'],
        'media_type': media_type,
        'rescrape': rescrape,
        'get_backup': get_backup,
        'source_select': source_select,
        'silent': silent
    }
    sources = pages.getSourcesHelper(actionArgs)
    return sources

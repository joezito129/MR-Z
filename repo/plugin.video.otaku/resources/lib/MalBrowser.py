import time
import requests
import json
import random
import pickle
import re

from functools import partial
from resources.lib.ui import database, control, utils, get_meta
from resources.lib.ui.divide_flavors import div_flavor


class MalBrowser:
    _URL = "https://api.jikan.moe/v4"

    def __init__(self):
        self._TITLE_LANG = ['title', 'title_english'][control.getInt("titlelanguage")]
        self.perpage = control.getInt('interface.perpage.general.mal')
        self.format_in_type = ['tv', 'movie', 'tv_special', 'special', 'ova', 'ona', 'music'][
            control.getInt('contentformat.menu')] if control.getBool('contentformat.bool') else ''
        self.adult = 'true' if control.getSetting('search.adult') == "false" else 'false'

    @staticmethod
    def open_completed():
        try:
            with open(control.completed_json) as file:
                completed = json.load(file)
        except FileNotFoundError:
            completed = {}
        return completed

    @staticmethod
    def handle_paging(hasnextpage, base_url, page):
        if not hasnextpage or not control.is_addon_visible() and control.getBool('widget.hide.nextpage'):
            return []
        next_page = page + 1
        name = "Next Page (%d)" % next_page
        return [utils.allocate_item(name, base_url % next_page, True, False, 'next.png', {'plot': name}, 'next.png')]

    def process_mal_view(self, res, base_plugin_url, page):
        get_meta.collect_meta(res['data'])
        mapfunc = partial(self.base_mal_view, completed=self.open_completed())
        all_results = list(map(mapfunc, res['data']))
        hasNextPage = res['pagination']['has_next_page']
        all_results += self.handle_paging(hasNextPage, base_plugin_url, page)
        return all_results

    def process_res(self, res):
        self.database_update_show(res)
        get_meta.collect_meta([res])
        return database.get_show(res['mal_id'])

    @staticmethod
    def get_season_year(period='current'):
        import datetime
        date = datetime.datetime.today()
        year = date.year
        month = date.month
        seasons = ['WINTER', 'SPRING', 'SUMMER', 'FALL']
        if period == "next":
            season = seasons[int((month - 1) / 3 + 1) % 4]
            if season == 'WINTER':
                year += 1
        else:
            season = seasons[int((month - 1) / 3)]
        return season, year

    def get_anime(self, mal_id):
        res = database.get_(self.get_base_res, 24, f"{self._URL}/anime/{mal_id}")
        return self.process_res(res['data'])

    def get_recommendations(self, mal_id, page):
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult
        }
        recommendations = database.get_(self.get_base_res, 24, f'{self._URL}/anime/{mal_id}/recommendations', params)
        mapfunc = partial(self.recommendation_relation_view, completed=self.open_completed())
        all_results = list(map(mapfunc, recommendations['data']))
        return all_results

    def get_relations(self, mal_id):
        relations = database.get_(self.get_base_res, 24, f'{self._URL}/anime/{mal_id}/relations')

        relation_res = []
        count = 0
        for relation in relations['data']:
            for entry in relation['entry']:
                if entry['type'] == 'anime':
                    res_data = database.get_(self.get_base_res, 24, f"{self._URL}/anime/{mal_id}")['data']
                    res_data['relation'] = relation['relation']
                    res_data['relation'] = relation['relation']
                    relation_res.append(res_data)
                    if count % 3 == 0:
                        time.sleep(2)
                    count += 1
        mapfunc = partial(self.base_mal_view, completed=self.open_completed())
        all_results = list(map(mapfunc, relation_res))
        return all_results

    def get_search(self, query, page=1):
        params = {
            "q": query,
            "page": page,
            "limit": self.perpage,
            'sfw': self.adult
        }

        if self.format_in_type:
            params['type'] = self.format_in_type

        search = database.get_(self.get_base_res, 24, f"{self._URL}/anime", params)
        return self.process_mal_view(search, f"search/{query}?page=%d", page)

    def get_airing_anime(self, page):
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult
        }
        if self.format_in_type:
            params['filter'] = self.format_in_type

        airing = database.get_(self.get_base_res, 24, f"{self._URL}/seasons/now", params)
        return self.process_mal_view(airing, "airing_anime?page=%d", page)

    def get_upcoming_next_season(self, page):
        season, year = self.get_season_year('next')
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult
        }
        if self.format_in_type:
            params['filter'] = self.format_in_type

        upcoming = database.get_(self.get_base_res, 24, f"{self._URL}/seasons/{year}/{season}", params)
        return self.process_mal_view(upcoming, "upcoming_next_season?page=%d", page)

    def get_top_100_anime(self, page):
        params = {
            'page': page,
            'limit': self.perpage,
            'sfw': self.adult
        }
        if self.format_in_type:
            params['type'] = self.format_in_type

        top_100_anime = database.get_(self.get_base_res, 24, f"{self._URL}/top/anime", params)
        return self.process_mal_view(top_100_anime, "top_100_anime?page=%d", page)

    @staticmethod
    def get_base_res(url, params=None):
        r = requests.get(url, params=params)
        return r.json()

    @div_flavor
    def recommendation_relation_view(self, res, completed=None, mal_dub=None):
        if res.get('entry'):
            res = res['entry']
        if not completed:
            completed = {}

        mal_id = res['mal_id']
        title = res['title']
        if res.get('relation'):
            title += ' [I]%s[/I]' % control.colorstr(res['relation'], 'limegreen')

        info = {
            'UniqueIDs': {'mal_id': str(mal_id)},
            'title': title,
            'mediatype': 'tvshow'
        }

        if completed.get(str(mal_id)):
            info['playcount'] = 1

        dub = True if mal_dub and mal_dub.get(str(res.get('idMal'))) else False

        image = res['images']['webp']['large_image_url'] if res.get('images') else None

        base = {
            "name": title,
            "url": f'animes/{mal_id}/',
            "image": image,
            "poster": image,
            'fanart': image,
            "banner": image,
            "info": info
        }

        return utils.parse_view(base, True, False, dub)

    def get_genres(self):
        res = database.get_(self.get_base_res, 24, f'{self._URL}/genres/anime')

        genre = res['data']
        genres_list = []
        for x in genre:
            genres_list.append(x['name'])
        multiselect = control.multiselect_dialog(control.lang(30004), genres_list)
        if not multiselect:
            return []
        genre_display_list = []
        for selection in multiselect:
            if selection < len(genres_list):
                genre_display_list.append(str(genre[selection]['mal_id']))
        return self.genres_payload(genre_display_list, [], 1)

    def genres_payload(self, genre_list, tag_list, page):
        import ast
        if not isinstance(genre_list, list):
            genre_list = ast.literal_eval(genre_list)

        genre = ','.join(genre_list)
        params = {
            'page': page,
            'limit': self.perpage,
            'genres': genre,
            'sfw': self.adult,
            'order_by': 'popularity'
        }

        if self.format_in_type:
            params['type'] = self.format_in_type

        genres = database.get_(self.get_base_res, 24, f'{self._URL}/anime', params)
        return self.process_mal_view(genres, f"genres/{genre_list}/{tag_list}?page=%d", page)

    @div_flavor
    def base_mal_view(self, res, completed=None, mal_dub=None):
        if not completed:
            completed = {}

        mal_id = res['mal_id']

        if not database.get_show(mal_id):
            self.database_update_show(res)

        show_meta = database.get_show_meta(mal_id)
        kodi_meta = pickle.loads(show_meta.get('art')) if show_meta else {}

        title = res[self._TITLE_LANG] or res['title']
        rating = res.get('rating')
        if rating == 'Rx - Hentai':
            title += ' - ' + control.colorstr("Adult", 'red')
        if res.get('relation'):
            title += ' [I]%s[/I]' % control.colorstr(res['relation'], 'limegreen')

        info = {
            'UniqueIDs': {'mal_id': str(mal_id)},
            'title': title,
            'plot': res.get('synopsis'),
            'mpaa': rating,
            'duration': self.duration_to_seconds(res.get('duration')),
            'genre': [x['name'] for x in res.get('genres', [])],
            'studio': [x['name'] for x in res.get('studios', [])],
            'status': res.get('status'),
            'mediatype': 'tvshow'
        }

        if completed.get(str(mal_id)):
            info['playcount'] = 1

        try:
            start_date = res['aired']['from']
            info['premiered'] = start_date[:10]
            info['year'] = res.get('year', int(start_date[:3]))
        except TypeError:
            pass

        if isinstance(res.get('score'), float):
            info['rating'] = {'score': res['score']}
            if isinstance(res.get('scored_by'), int):
                info['rating']['votes'] = res['scored_by']

        if res.get('trailer'):
            info['trailer'] = f"plugin://plugin.video.youtube/play/?video_id={res['trailer']['youtube_id']}"

        dub = True if mal_dub and mal_dub.get(str(mal_id)) else False

        image = res['images']['webp']['large_image_url']
        base = {
            "name": title,
            "url": f'animes/{mal_id}/',
            "image": image,
            "poster": image,
            'fanart': kodi_meta['fanart'] if kodi_meta.get('fanart') else image,
            "banner": image,
            "info": info
        }

        if kodi_meta.get('thumb'):
            base['landscape'] = random.choice(kodi_meta['thumb'])
        if kodi_meta.get('clearart'):
            base['clearart'] = random.choice(kodi_meta['clearart'])
        if kodi_meta.get('clearlogo'):
            base['clearlogo'] = random.choice(kodi_meta['clearlogo'])

        if res.get('type') in ['Movie', 'ONA', 'Special', 'TV Special'] and res['episodes'] == 1:
            base['url'] = f'play_movie/{mal_id}/'
            base['info']['mediatype'] = 'movie'
            return utils.parse_view(base, False, True, dub)
        return utils.parse_view(base, True, False, dub)

    def database_update_show(self, res):
        mal_id = res['mal_id']

        try:
            start_date = res['aired']['from']
        except TypeError:
            start_date = None

        title_userPreferred = res[self._TITLE_LANG] or res['title']

        name = res['title']
        ename = res['title_english']
        titles = f"({name})|({ename})"

        kodi_meta = {
            'name': name,
            'ename': ename,
            'title_userPreferred': title_userPreferred,
            'start_date': start_date,
            'query': titles,
            'episodes': res['episodes'],
            'poster': res['images']['webp']['large_image_url'],
            'status': res.get('status'),
            'format': res.get('type'),
            'plot': res.get('synopsis')
        }

        if isinstance(res.get('score'), float):
            kodi_meta['rating'] = {'score': res['score']}
            if isinstance(res.get('scored_by'), int):
                kodi_meta['rating']['votes'] = res['scored_by']

        database.update_show(mal_id, pickle.dumps(kodi_meta))

    @staticmethod
    def duration_to_seconds(duration_str):
        # Regular expressions to match hours, minutes, and seconds
        hours_pattern = re.compile(r'(\d+)\s*hr')
        minutes_pattern = re.compile(r'(\d+)\s*min')
        seconds_pattern = re.compile(r'(\d+)\s*sec')

        # Extract hours, minutes, and seconds
        hours_match = hours_pattern.search(duration_str)
        minutes_match = minutes_pattern.search(duration_str)
        seconds_match = seconds_pattern.search(duration_str)

        # Convert to integers, default to 0 if not found
        hours = int(hours_match.group(1)) if hours_match else 0
        minutes = int(minutes_match.group(1)) if minutes_match else 0
        seconds = int(seconds_match.group(1)) if seconds_match else 0

        # Calculate total duration in seconds
        total_seconds = hours * 3600 + minutes * 60 + seconds

        return total_seconds
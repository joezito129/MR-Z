import itertools
import time
import requests

from resources.lib.ui import control
from resources.lib.WatchlistFlavor.WatchlistFlavorBase import WatchlistFlavorBase
from urllib import parse


class KitsuWLF(WatchlistFlavorBase):
    _URL = "https://kitsu.io/api"
    _TITLE = "Kitsu"
    _NAME = "kitsu"
    _IMAGE = "kitsu.png"
    _mapping = None

    def login(self):
        params = {
            "grant_type": "password",
            "username": self._auth_var,
            "password": self._password
        }
        resp = requests.post(f'{self._URL}/oauth/token', params=params)

        if not resp:
            return

        data = resp.json()
        self._token = data['access_token']
        resp2 = requests.get(f'{self._URL}/edge/users', headers=self.__headers(), params={'filter[self]': True})
        data2 = resp2.json()["data"][0]

        login_data = {
            'username': data2["attributes"]["name"],
            'userid': data2['id'],
            'token': data['access_token'],
            'refresh': data['refresh_token'],
            'expiry': str(int(time.time()) + int(data['expires_in']))
        }
        return login_data

    def refresh_token(self):
        params = {
            "grant_type": "refresh_token",
            "refresh_token": control.getSetting('kitsu.refresh')
        }
        resp = requests.post(f'{self._URL}/oauth/token', params=params)

        if not resp:
            return

        data = resp.json()
        control.setSetting('kitsu.token', data['access_token'])
        control.setSetting('kitsu.refresh', data['refresh_token'])
        control.setSetting('kitsu.expiry', str(int(time.time()) + int(data['expires_in'])))

    def __headers(self):
        headers = {
            'Content-Type': 'application/vnd.api+json',
            'Accept': 'application/vnd.api+json',
            'Authorization': "Bearer {}".format(self._token)
        }
        return headers

    def _handle_paging(self, hasNextPage, base_url, page):
        if not hasNextPage:
            return []
        next_page = page + 1
        name = "Next Page (%d)" % next_page
        parsed = parse.urlparse(hasNextPage)
        offset = parse.parse_qs(parsed.query)['page[offset]'][0]
        return self._parse_view({'name': name, 'url': base_url % (offset, next_page), 'image': 'next.png', 'info': None, 'fanart': 'next.png'})


    def watchlist(self):
        params = {"filter[user_id]": self._user_id}
        url = f'{self._URL}/edge/library-entries'
        return self._process_watchlist_status_view(url, params, "watchlist/%d", page=1)


    def _base_watchlist_status_view(self, res):
        base = {
            "name": res[0],
            "url": 'watchlist_status_type/%s/%s' % (self._NAME, res[1]),
            "image": f'{res[0].lower()}.png',
            'info': {}
        }
        return self._parse_view(base)

    def _process_watchlist_status_view(self, url, params, base_plugin_url, page):
        all_results = map(self._base_watchlist_status_view, self.__kitsu_statuses())
        all_results = list(itertools.chain(*all_results))
        return all_results

    @staticmethod
    def __kitsu_statuses():
        statuses = [
            ("Next Up", "current?next_up=true"),
            ("Current", "current"),
            ("Want to Watch", "planned"),
            ("Completed", "completed"),
            ("On Hold", "on_hold"),
            ("Dropped", "dropped"),
        ]
        return statuses

    def get_watchlist_status(self, status, next_up, offset=0, page=1):
        url = f'{self._URL}/edge/library-entries'
        params = {
            "fields[anime]": "titles,canonicalTitle,posterImage,episodeCount,synopsis,episodeLength,subtype,averageRating,ageRating,youtubeVideoId",
            "filter[user_id]": self._user_id,
            "filter[kind]": "anime",
            "filter[status]": status,
            "include": "anime,anime.mappings,anime.mappings.item",
            "page[limit]": "50",
            "page[offset]": offset,
            "sort": self.__get_sort(),
        }
        return self._process_watchlist_view(url, params, next_up, f'watchlist_status_type_pages/kitsu/{status}/%s/%d', page)

    def _process_watchlist_view(self, url, params, next_up, base_plugin_url, page):
        result = requests.get(url, headers=self.__headers(), params=params)
        result = result.json()
        _list = result["data"]

        if not result.get('included'):
            result['included'] = []

        el = result["included"][:len(_list)]
        self._mapping = [x for x in result['included'] if x['type'] == 'mappings']

        if next_up:
            all_results = map(self._base_next_up_view, _list, el)
        else:
            all_results = map(self._base_watchlist_view, _list, el)

        all_results = list(itertools.chain(*all_results))

        all_results += self._handle_paging(result['links'].get('next'), base_plugin_url, page)
        return all_results

    def _base_watchlist_view(self, res, eres):
        kitsu_id = eres['id']
        anilist_id = ''
        mal_id = self._mapping_mal(kitsu_id)

        info = {
            'plot': eres['attributes'].get('synopsis'),
            'title': eres["attributes"]["titles"].get(self.__get_title_lang(), eres["attributes"]['canonicalTitle']),
            'rating': float(eres['attributes']['averageRating']) / 10, 'mpaa': eres['attributes']['ageRating'],
            'trailer': 'plugin://plugin.video.youtube/play/?video_id={0}'.format(eres['attributes']['youtubeVideoId']),
            'mediatype': 'tvshow'
        }

        try:
            info['duration'] = eres['attributes']['episodeLength'] * 60
        except TypeError:
            pass

        # 'rating': float(eres['attributes']['averageRating']) / 10, 'mpaa': eres['attributes']['ageRating'],

        base = {
            "name": '%s - %d/%d' % (eres["attributes"]["titles"].get(self.__get_title_lang(), eres["attributes"]['canonicalTitle']),
                                    res["attributes"]['progress'],
                                    eres["attributes"].get('episodeCount', 0) if eres["attributes"]['episodeCount'] else 0),
            "url": f'watchlist_to_ep//{mal_id}/{kitsu_id}/{res["attributes"]["progress"]}',
            "image": eres["attributes"]['posterImage']['large'],
            "info": info
        }

        if eres['attributes']['subtype'] == 'movie' and eres['attributes']['episodeCount'] == 1:
            base['url'] = f'watchlist_to_movie/{anilist_id}/{mal_id}/{kitsu_id}'
            base['info']['mediatype'] = 'movie'
            return self._parse_view(base, False)

        return self._parse_view(base)

    def _base_next_up_view(self, res, eres):
        kitsu_id = eres['id']
        mal_id = self._mapping_mal(kitsu_id)

        progress = res["attributes"]['progress']
        next_up = progress + 1
        anime_title = eres["attributes"]["titles"].get(self.__get_title_lang(), eres["attributes"]['canonicalTitle'])
        episode_count = eres["attributes"]['episodeCount'] if eres["attributes"]['episodeCount'] else 0
        title = '%s - %d/%d' % (anime_title, next_up, episode_count)
        poster = image = eres["attributes"]['posterImage']['large']
        plot = aired = None

        anilist_id, next_up_meta, show = self._get_next_up_meta(mal_id, int(progress))
        if next_up_meta:
            url = 'play/%d/%d/' % (anilist_id, next_up)
            if next_up_meta.get('title'):
                title = '%s - %s' % (title, next_up_meta['title'])
            if next_up_meta.get('image'):
                image = next_up_meta['image']
            plot = next_up_meta.get('plot')
            aired = next_up_meta.get('aired')

        info = {
            'episode': next_up,
            'title': title,
            'tvshowtitle': anime_title,
            'plot': plot,
            'mediatype': 'episode',
            'aired': aired
        }

        base = {
            "name": title,
            "url": f'watchlist_to_ep/{anilist_id}/{mal_id}/{kitsu_id}/{res["attributes"]["progress"]}',
            "image": image,
            "info": info,
            "fanart": image,
            "poster": poster
        }

        if next_up_meta:
            base['url'] = url
            return self._parse_view(base, False)

        if eres['attributes']['subtype'] == 'movie' and eres['attributes']['episodeCount'] == 1:
            base['url'] = f"play_movie/{anilist_id}/{mal_id}/{kitsu_id}"
            base['info']['mediatype'] = 'movie'
            return self._parse_view(base, False)

        return self._parse_view(base)

    def _mapping_mal(self, kitsu_id):
        mal_id = ''
        for i in self._mapping:
            if i['attributes']['externalSite'] == 'myanimelist/anime':
                if i['relationships']['item']['data']['id'] == kitsu_id:
                    mal_id = i['attributes']['externalId']
                    break
        return mal_id

    def get_watchlist_anime_entry(self, anilist_id):
        kitsu_id = self._get_mapping_id(anilist_id, 'kitsu_id')
        if not kitsu_id:
            return False

        url = f'{self._URL}/edge/library-entries'
        params = {
            "filter[user_id]": self._user_id,
            "filter[anime_id]": kitsu_id
        }
        result = requests.get(url, headers=self.__headers(), params=params)
        result = result.json()
        item_dict = result['data'][0]['attributes']

        anime_entry = {
            'eps_watched': item_dict['progress'],
            'status': item_dict['status'],
            'score': item_dict['ratingTwenty']
        }

        return anime_entry

    def update_num_episodes(self, anilist_id, episode):
        kitsu_id = self._get_mapping_id(anilist_id, 'kitsu_id')
        if not kitsu_id:
            return False

        url = f'{self._URL}/edge/library-entries'
        params = {
            "filter[user_id]": self._user_id,
            "filter[anime_id]": kitsu_id
        }
        r = requests.get(url, headers=self.__headers(), params=params)
        r = r.json()
        if len(r['data']) == 0:
            data = {
                "data": {
                    "type": "libraryEntries",
                    "attributes": {
                        'status': 'current',
                        'progress': int(episode)
                    },
                    "relationships": {
                        "user": {
                            "data": {
                                "id": self._user_id,
                                "type": "users"
                            }
                        },
                        "anime": {
                            "data": {
                                "id": int(kitsu_id),
                                "type": "anime"
                            }
                        }
                    }
                }
            }
            r = requests.post(url, headers=self.__headers(), json=data)
            return r.ok

        animeid = r['data'][0]['id']

        data = {
            'data': {
                'id': int(animeid),
                'type': 'libraryEntries',
                'attributes': {
                    'progress': int(episode)}
            }
        }
        r = requests.patch("%s/%s" % (url, animeid), headers=self.__headers(), json=data)
        return r.ok

    def update_list_status(self, anilist_id, status):
        kitsu_id = self._get_mapping_id(anilist_id, 'kitsu_id')
        if not kitsu_id:
            return False

        url = f'{self._URL}/edge/library-entries'
        params = {
            "filter[user_id]": self._user_id,
            "filter[anime_id]": kitsu_id
        }
        r = requests.get(url, headers=self.__headers(), params=params)
        r = r.json()
        if len(r['data']) == 0:
            data = {
                "data": {
                    "type": "libraryEntries",
                    "attributes": {
                        'status': status
                    },
                    "relationships": {
                        "user": {
                            "data": {
                                "id": self._user_id,
                                "type": "users"
                            }
                        },
                        "anime": {
                            "data": {
                                "id": int(kitsu_id),
                                "type": "anime"
                            }
                        }
                    }
                }
            }
            r = requests.post(url, headers=self.__headers(), json=data)
            return r.ok

        animeid = r['data'][0]['id']

        data = {
            'data': {
                'id': int(animeid),
                'type': 'libraryEntries',
                'attributes': {
                    'status': status
                }
            }
        }
        r = requests.patch("%s/%s" % (url, animeid), headers=self.__headers(), json=data)
        return r.json() if r.ok else False


    def update_score(self, anilist_id, score):
        kitsu_id = self._get_mapping_id(anilist_id, 'kitsu_id')
        if not kitsu_id:
            return False

    def __get_sort(self):
        sort_types = {
            "Date Updated": "-progressed_at",
            "Progress": "-progress",
            "Title": "anime.titles." + self.__get_title_lang(),
        }

        return sort_types[self._sort]

    def __get_title_lang(self):
        title_langs = {
            "Canonical": "canonical",
            "English": "en",
            "Romanized": "en_jp",
        }

        return title_langs[self._title_lang]
    
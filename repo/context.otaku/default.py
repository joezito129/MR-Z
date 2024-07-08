import sys

from xbmc import executebuiltin


def main():
    arg = sys.argv[1]
    item = sys.listitem
    path = item.getPath()
    plugin = 'plugin://plugin.video.otaku'

    if arg == 'findrecommendations':
        path = path.split(plugin, 1)[1]
        executebuiltin(f"ActivateWindow(Videos,{plugin}/find_recommendations{path})")
    elif arg == 'findrelations':
        path = path.split(plugin, 1)[1]
        executebuiltin(f"ActivateWindow(Videos,{plugin}/find_relations{path})")
    elif arg == 'rescrape':
        resume_time = item.getVideoInfoTag().getResumeTime()
        path += "?rescrape=true"
        if resume_time > 0:
            path += f"&resume={resume_time}"
        executebuiltin(f"PlayMedia({path})")
    elif arg == 'sourceselect':
        resume_time = item.getVideoInfoTag().getResumeTime()
        path += '?source_select=true'
        if resume_time > 0:
            path += f'&resume={resume_time}'
        executebuiltin(f"PlayMedia({path})")
    elif arg == 'logout':
        path = path.split(f'{plugin}/watchlist', 1)[1]
        executebuiltin(f"RunPlugin({plugin}/watchlist_logout{path})")
    elif arg == 'deletefromdatabase':
        path = path.split(plugin, 1)[1]
        executebuiltin(f"RunPlugin({plugin}/delete_anime_database{path})")
    elif arg == 'watchlist':
        path = path.split(plugin, 1)[1]
        executebuiltin(f"RunPlugin({plugin}/watchlist_manager{path})")
    elif arg == 'markedaswatched':
        path = path.split(f'{plugin}/play', 1)[1]
        executebuiltin(f"RunPlugin({plugin}/marked_as_watched{path})")
    elif arg == 'fanartselect':
        path = path.split(plugin, 1)[1]
        executebuiltin(f"ActivateWindow(Videos,{plugin}/fanart_select{path})")
    else:
        raise KeyError("Could Not find %s in Context Menu Action" % arg)


if __name__ == "__main__":
    main()

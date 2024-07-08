import xbmcaddon

from xbmc import executebuiltin

properties = [
    "context.otaku.findrecommendations",
    "context.otaku.findrelations",
    "context.otaku.rescrape",
    "context.otaku.sourceselect",
    "context.otaku.logout",
    'context.otaku.deletefromdatabase',
    'context.otaku.watchlist',
    'context.otaku.markedaswatched',
    'context.otaku.fanartselect'
]

ADDON = xbmcaddon.Addon('plugin.video.otaku')

for prop in properties:
    executebuiltin(f"SetProperty({prop},{ADDON.getSetting(prop)},home)")

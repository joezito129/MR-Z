from resources.lib.ui import control
from resources.lib.windows.base_window import BaseWindow


class WatchlistFlavorAuth(BaseWindow):

    def __init__(self, xml_file, location, flavor=None, **kwargs):
        super().__init__(xml_file, location)
        self.flavor = flavor
        self.authorized = False
        control.closeBusyDialog()

    def onInit(self):
        self.setFocusId(1000)

    def doModal(self):
        super(WatchlistFlavorAuth, self).doModal()
        return self.authorized

    def onClick(self, controlId):
        if controlId == 1000:
            self.handle_action(7)

    def handle_action(self, actionID):
        if actionID == 7 and self.getFocusId() == 1002:
            self.set_settings()

        if actionID == 7 and self.getFocusId() == 1003:
            self.close()

    def onAction(self, action):
        actionID = action.getId()
        if actionID in [92, 10]:
            self.close()

        if actionID in [7, 100, 401]:
            self.handle_action(7)


    def set_settings(self):
        res = {}
        if self.flavor == 'anilist':
            res['username'] = self.getControl(1000).getText()
            res['token'] = self.getControl(1001).getText()
        else:
            res['authvar'] = self.getControl(1000).getText()

        for _id, value in list(res.items()):
            control.setSetting('%s.%s' % (self.flavor, _id), value)

        self.authorized = True
        self.close()


class AltWatchlistFlavorAuth:
    def __init__(self, flavor=None):
        self.flavor = flavor
        self.authorized = False

    def set_settings(self):
        res = {}
        dialog = control.showDialog
        if self.flavor == 'anilist':
            control.textviewer_dialog(f'{control.ADDON_NAME} : AniList',
                              '{}\n{}\n{}'.format(control.lang(40105),
                                                  control.lang(40106).replace('below', 'in the input dialog that will popup once you close this'),
                                                  control.lang(40110)))

            res['username'] = dialog.input('Enter AniList username', type=control.INPUT_ALPHANUM)
            res['token'] = dialog.input('Enter AniList token', type=control.INPUT_ALPHANUM)
        else:
            control.textviewer_dialog(f'{control.ADDON_NAME} : MyAnimeList',
                              '{}\n{}\n{}'.format(control.lang(40100),
                                                  control.lang(40101).replace('below', 'in the input dialog that will popup once you close this'),
                                                  control.lang(40110)))

            res['authvar'] = dialog.input('Enter MAL auth url', type=control.INPUT_ALPHANUM)
        for _id, value in list(res.items()):
            control.setSetting('%s.%s' % (self.flavor, _id), value)
            self.authorized = True

        return self.authorized

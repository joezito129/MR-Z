import xbmc

from resources.lib.windows.base_window import BaseWindow


class PlayingNext(BaseWindow):
    def __init__(self, xml_file, xml_location, *, actionArgs=None):
        super().__init__(xml_file, xml_location, actionArgs=actionArgs)
        self.player = xbmc.Player()
        self.playing_file = self.player.getPlayingFile()
        self.closed = False
        self.actioned = False
        self.total_time = int(self.player.getTotalTime())
        self.duration = int(self.total_time - self.player.getTime())
        self.skipoutro_end = actionArgs['skipoutro_end']

    def onInit(self):
        self.background_tasks()

    def background_tasks(self):
        progress_bar = self.getControl(3014)
        while not self.closed and self.playing_file == self.player.getPlayingFile():
            xbmc.sleep(1000)
            if progress_bar:
                percent = ((self.total_time - int(self.player.getTime())) / self.duration) * 100
                if percent < 2:
                    break
                progress_bar.setPercent(percent)
        self.close()

    def doModal(self):
        super(PlayingNext, self).doModal()

    def close(self):
        self.closed = True
        super(PlayingNext, self).close()

    def onClick(self, controlID):
        self.handle_action(controlID)

    def handle_action(self, controlID):
        if controlID == 3001:   # playnext
            self.actioned = True
            self.player.playnext()
            self.close()
        elif controlID == 3002:   # close
            self.actioned = True
            self.close()
        elif controlID == 3003:   # skipoutro
            self.actioned = True
            skipoutro_end_skip_time = self.skipoutro_end
            if skipoutro_end_skip_time != 0:
                self.player.seekTime(skipoutro_end_skip_time)
            self.close()

    def onAction(self, action):
        actionID = action.getId()
        if actionID in [92, 10]:
            # BACKSPACE / ESCAPE
            self.close()

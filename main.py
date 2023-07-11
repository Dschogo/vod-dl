# ///////////////////////////////////////////////////////////////
#
# BY: WANDERSON M.PIMENTA
# PROJECT MADE WITH: Qt Designer and PySide6
# V: 1.0.0
#
# This project can be used freely for all uses, as long as they maintain the
# respective credits only in the Python scripts, any information in the visual
# interface (GUI) can be modified without any implication.
#
# There are limitations on Qt licenses if you want to use your products
# commercially, I recommend reading them on the official website:
# https://doc.qt.io/qtforpython/licenses.html
#
# ///////////////////////////////////////////////////////////////

import sys
import os
import platform
import httpx
import m3u8
import re
import asyncio
from typing import List, Optional, OrderedDict

# IMPORT / GUI AND MODULES AND WIDGETS
# ///////////////////////////////////////////////////////////////
from modules import *
from widgets import *

os.environ["QT_FONT_DPI"] = "96"  # FIX Problem for High DPI and Scale above 100%

# SET AS GLOBAL WIDGETS
# ///////////////////////////////////////////////////////////////
widgets = None
from http.server import BaseHTTPRequestHandler, HTTPServer

import extensions.twitch as twitch
import extensions.http as thttp

CLIENT_ID = "kd1unb4b3q4t58fwlpcbzcbnm76a8fp"


twitch_token = None


class MainWindow(QMainWindow):
    class Server(BaseHTTPRequestHandler):
        def do_GET(self):
            global twitch_token, widgets
            print(self.path)

            # set twitch token
            if self.path.startswith("/?code="):
                twitch_token = self.path.split("=")[1].split("&")[0]
                print(twitch_token)

            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(bytes("<html><body><h1>You can close this window now</h1></   body></html>", "utf8"))
            return

    def __init__(self):
        QMainWindow.__init__(self)
        global twitch_token
        # SET AS GLOBAL WIDGETS
        # ///////////////////////////////////////////////////////////////
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        global widgets
        widgets = self.ui
        self.videolist = []

        # USE CUSTOM TITLE BAR | USE AS "False" FOR MAC OR LINUX
        # ///////////////////////////////////////////////////////////////
        Settings.ENABLE_CUSTOM_TITLE_BAR = True

        # APP NAME
        # ///////////////////////////////////////////////////////////////
        title = "Vod-dl"
        description = "Vod-dl Alpha 0.1"
        # APPLY TEXTS
        self.setWindowTitle(title)
        widgets.titleRightInfo.setText(description)

        # TOGGLE MENU
        # ///////////////////////////////////////////////////////////////
        widgets.toggleButton.clicked.connect(lambda: UIFunctions.toggleMenu(self, True))

        # SET UI DEFINITIONS
        # ///////////////////////////////////////////////////////////////
        UIFunctions.uiDefinitions(self)

        # QTableWidget PARAMETERS
        # ///////////////////////////////////////////////////////////////
        widgets.tableWidget.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        # BUTTONS CLICK
        # ///////////////////////////////////////////////////////////////

        # LEFT MENUS
        widgets.btn_home.clicked.connect(self.buttonClick)
        widgets.btn_widgets.clicked.connect(self.buttonClick)
        widgets.btn_new.clicked.connect(self.buttonClick)
        widgets.btn_save.clicked.connect(self.buttonClick)
        widgets.pushButton_5.clicked.connect(self.donwload_video)

        widgets.pushButton_2.clicked.connect(self.fetch_videos)

        # EXTRA LEFT BOX
        def openCloseLeftBox():
            UIFunctions.toggleLeftBox(self, True)

        widgets.toggleLeftBox.clicked.connect(openCloseLeftBox)
        widgets.extraCloseColumnBtn.clicked.connect(openCloseLeftBox)

        # EXTRA RIGHT BOX
        def openCloseRightBox():
            UIFunctions.toggleRightBox(self, True)

        widgets.settingsTopBtn.clicked.connect(openCloseRightBox)
        widgets.btn_login.clicked.connect(self.login)
        widgets.btn_logout.clicked.connect(self.logout)
        widgets.btn_logout.hide()
        widgets.btn_message.hide()

        widgets.tableWidget_4.cellClicked.connect(self.video_selected)
        # SHOW APP
        # ///////////////////////////////////////////////////////////////
        self.show()

        # SET CUSTOM THEME
        # ///////////////////////////////////////////////////////////////
        useCustomTheme = False
        themeFile = "themes\py_dracula_light.qss"

        # SET THEME AND HACKS
        if useCustomTheme:
            # LOAD AND APPLY STYLE
            UIFunctions.theme(self, themeFile, True)

            # SET HACKS
            AppFunctions.setThemeHack(self)

        # SET HOME PAGE AND SELECT MENU
        # ///////////////////////////////////////////////////////////////
        widgets.stackedWidget.setCurrentWidget(widgets.home)
        widgets.btn_home.setStyleSheet(UIFunctions.selectMenu(widgets.btn_home.styleSheet()))

    def video_selected(self, row, col):
        # update timedit
        widgets.timeEdit_2.setTime(QTime(0, 0, 0))
        length_in_s = widgets.tableWidget_4.item(row, 1).text()
        hours = int(length_in_s) // 3600
        minutes = (int(length_in_s) - hours * 3600) // 60
        seconds = int(length_in_s) - hours * 3600 - minutes * 60
        widgets.timeEdit.setTime(QTime(hours, minutes, seconds))

    def fetch_videos(self):
        # demo fill table
        channel = widgets.lineEdit_2.text()
        vids = twitch.get_channel_videos(channel, limit=100, sort="time")["edges"]
        widgets.tableWidget_4.clearContents()
        for i in range(len(vids)):
            vid = vids[i]["node"]
            self.videolist.append(vid)
            widgets.tableWidget_4.setItem(i, 0, QTableWidgetItem(vid["createdAt"]))
            widgets.tableWidget_4.setItem(i, 1, QTableWidgetItem(str(vid["lengthSeconds"])))
            widgets.tableWidget_4.setItem(i, 2, QTableWidgetItem(vid["title"]))

    def donwload_video(self):
        # get selected video
        row = widgets.tableWidget_4.currentRow()
        channel = widgets.lineEdit_2.text()
        print(f"download video {row} from {widgets.timeEdit_2.text()} to {widgets.timeEdit.text()}")
        start_sec = widgets.timeEdit_2.time().hour() * 3600 + widgets.timeEdit_2.time().minute() * 60 + widgets.timeEdit_2.time().second()
        end_sec = widgets.timeEdit.time().hour() * 3600 + widgets.timeEdit.time().minute() * 60 + widgets.timeEdit.time().second()

        video = self.videolist[row]
        print(video)
        access_token = twitch.get_access_token(video["id"], twitch_token)
        args = {"output": "{date}_{id}_{channel_login}_{title_slug}.{format}", "format": "mp4"}
        target = twitch._video_target_filename(
            video, args
        )

        print("<dim>Fetching playlists...</dim>")
        playlists_m3u8 = twitch.get_playlists(video["id"], access_token)
        playlists = list(twitch._parse_playlists(playlists_m3u8))
        playlist_uri = twitch._get_playlist_by_name(playlists, "source")

        print("<dim>Fetching playlist...</dim>")
        response = httpx.get(playlist_uri)
        response.raise_for_status()
        playlist = m3u8.loads(response.text)

        base_uri = re.sub("/[^/]+$", "/", playlist_uri)
        target_dir = twitch._crete_temp_dir(base_uri)
        vod_paths = twitch._get_vod_paths(playlist, start_sec, end_sec)

        # Save playlists for debugging purposes
        with open(os.path.join(target_dir, "playlists.m3u8"), "w") as f:
            f.write(playlists_m3u8)
        with open(os.path.join(target_dir, "playlist.m3u8"), "w") as f:
            f.write(response.text)

        def set_progresstxt(text):
            widgets.labelprogress.setText(text)

        print("\nDownloading {} VODs using {} workers to {}".format(len(vod_paths), 20, target_dir))
        sources = [base_uri + path for path in vod_paths]
        targets = [os.path.join(target_dir, "{:05d}.ts".format(k)) for k, _ in enumerate(vod_paths)]
        # run in background
        asyncio.run(thttp.download_all(set_progresstxt, sources, targets, 20, rate_limit=None))

        # Make a modified playlist which references downloaded VODs
        # Keep only the downloaded segments and skip the rest
        org_segments = playlist.segments.copy()

        path_map = OrderedDict(zip(vod_paths, targets))
        playlist.segments.clear()
        for segment in org_segments:
            if segment.uri in path_map:
                segment.uri = path_map[segment.uri]
                playlist.segments.append(segment)

        playlist_path = os.path.join(target_dir, "playlist_downloaded.m3u8")
        playlist.dump(playlist_path)

        print("\n\nJoining files...")
        twitch._join_vods(playlist_path, target, True, video)

    def logout(self):
        global twitch_token
        twitch_token = None
        widgets.btn_login.show()
        widgets.btn_logout.hide()

    def login(self):
        global twitch_token

        serv = HTTPServer(("localhost", 4973), self.Server)
        import threading

        login_thread = threading.Thread(target=serv.serve_forever)
        login_thread.start()
        import webbrowser

        webbrowser.open("https://id.twitch.tv/oauth2/authorize?client_id=" + CLIENT_ID + "&redirect_uri=http://localhost:4973&response_type=code&scope=channel:read:subscriptions")
        # wait for twitch login
        import time

        while twitch_token is None:
            print("waiting for twitch login")
            time.sleep(1)
        widgets.btn_login.hide()
        widgets.btn_logout.show()
        print("closing server")
        serv.shutdown()

    # BUTTONS CLICK
    # Post here your functions for clicked buttons
    # ///////////////////////////////////////////////////////////////
    def buttonClick(self):
        # GET BUTTON CLICKED
        btn = self.sender()
        btnName = btn.objectName()

        # SHOW HOME PAGE
        if btnName == "btn_home":
            widgets.stackedWidget.setCurrentWidget(widgets.home)
            UIFunctions.resetStyle(self, btnName)
            btn.setStyleSheet(UIFunctions.selectMenu(btn.styleSheet()))

        # SHOW WIDGETS PAGE
        if btnName == "btn_widgets":
            widgets.stackedWidget.setCurrentWidget(widgets.widgets)
            UIFunctions.resetStyle(self, btnName)
            btn.setStyleSheet(UIFunctions.selectMenu(btn.styleSheet()))

        # SHOW NEW PAGE
        if btnName == "btn_new":
            widgets.stackedWidget.setCurrentWidget(widgets.new_page)  # SET PAGE
            UIFunctions.resetStyle(self, btnName)  # RESET ANOTHERS BUTTONS SELECTED
            btn.setStyleSheet(UIFunctions.selectMenu(btn.styleSheet()))  # SELECT MENU

        if btnName == "btn_save":
            print("Save BTN clicked!")

        # PRINT BTN NAME
        print(f'Button "{btnName}" pressed!')

    # RESIZE EVENTS
    # ///////////////////////////////////////////////////////////////
    def resizeEvent(self, event):
        # Update Size Grips
        UIFunctions.resize_grips(self)

    # MOUSE CLICK EVENTS
    # ///////////////////////////////////////////////////////////////
    def mousePressEvent(self, event):
        # SET DRAG POS WINDOW
        self.dragPos = event.globalPos()

        # PRINT MOUSE EVENTS
        if event.buttons() == Qt.LeftButton:
            print("Mouse click: LEFT CLICK")
        if event.buttons() == Qt.RightButton:
            print("Mouse click: RIGHT CLICK")

    # on exit
    # ///////////////////////////////////////////////////////////////
    def closeEvent(self, event):
        print("Closing")
        # close localhost thread<


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon("icon.ico"))
    window = MainWindow()
    sys.exit(app.exec_())

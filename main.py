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
import httpx
import m3u8
import re
import asyncio
from typing import List, Optional, OrderedDict
import threading
import webbrowser
import time
import shutil
import json
import webbrowser

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

CLIENT_ID = "um6i0x3u4m9j42plwlh0zck9kk0wzq"


twitch_token = None

port = 4974


class MainWindow(QMainWindow):
    class Server(BaseHTTPRequestHandler):
        def do_GET(self):
            global twitch_token, widgets
            # set twitch token
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            if self.path.startswith("/?access_token="):
                print("got token")
                twitch_token = self.path.split("=")[1].split("&")[0]
                self.wfile.write(
                    bytes(
                        "<html><body><h1>You can close this window now</h1></   body></html><script>window.location.href = 'http://localhost:" + str(port) + "'</script>",
                        "utf-8",
                    )
                )

            else:
                # const urlParams = new URLSearchParams(window.location.hash.substr(1));
                # const accessToken = urlParams.get('access_token');
                # console.log(accessToken);

                self.wfile.write(
                    bytes(
                        "<html><body><h1>You can close this window now</h1></   body></html><script>const urlParams = new URLSearchParams(window.location.hash.substr(1));const accessToken = urlParams.get('access_token');if (accessToken != null) {const redirectUri = window.location.href = 'http://localhost:" + str(port) + "?access_token=' + accessToken} else {window.close()};;</script>",
                        "utf-8",
                    )
                )
            return

        def log_message(self, format, *args):
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

        self.settings = QSettings("settings.ini", QSettings.IniFormat)
        self.folder = self.settings.value("folder", os.getcwd())

        # USE CUSTOM TITLE BAR | USE AS "False" FOR MAC OR LINUX
        # ///////////////////////////////////////////////////////////////
        Settings.ENABLE_CUSTOM_TITLE_BAR = True

        # APP NAME
        # ///////////////////////////////////////////////////////////////
        title = "Vod-dl"
        description = "Vod-dl Alpha"
        version = "0.1.4"
        # APPLY TEXTS
        self.setWindowTitle(title)
        widgets.titleRightInfo.setText(description)
        widgets.version.setText(version)

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
        widgets.pushButton_5.clicked.connect(self.donwload_video_proxy)

        widgets.pushButton_2.clicked.connect(self.fetch_videos)
        widgets.pushButton_3.clicked.connect(self.fetch_clips)

        widgets.pushButton_2.setDisabled(True)
        widgets.pushButton_3.setDisabled(True)


        widgets.dateEdit.setDateTime(QDateTime.currentDateTime())
        widgets.dateEdit_2.setDateTime(QDateTime.currentDateTime())
        widgets.toggleLeftBox.hide()

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
        widgets.btn_message.clicked.connect(self.set_output)

        # widgets.btn_home.hide()
        widgets.btn_save.hide()
        widgets.btn_exit.hide()

        widgets.tableWidget_4.itemSelectionChanged.connect(self.video_selected)
        widgets.pushButton_7.clicked.connect(self.preview_video)

        widgets.tableWidget_5.cellClicked.connect(self.clip_selected)
        widgets.lineEdit_4.textChanged.connect(self.clip_filter)

        # set table column widths
        widgets.tableWidget_5.setColumnWidth(2, 50)
        widgets.tableWidget_5.setColumnWidth(3, 50)

        widgets.pushButton_6.clicked.connect(self.download_clip_proxy)

        widgets.download_link.clicked.connect(self.download_clip_link_proxy)
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

    def set_output(self):
        # filpicker for folder
        self.folder = QFileDialog.getExistingDirectory(self, "Select Directory")

        # save to settings file
        self.settings.setValue("folder", self.folder)

    def video_selected(self):
        # get selected video
        row = widgets.tableWidget_4.currentRow()

        # update timedit
        widgets.timeEdit_2.setTime(QTime(0, 0, 0))
        hours, minutes, seconds = widgets.tableWidget_4.item(row, 1).text().split(":")
        widgets.timeEdit.setTime(QTime(int(hours), int(minutes), int(seconds)))

    def preview_video(self):
        # get selected video
        row = widgets.tableWidget_4.currentRow()
        vid = self.videolist[row]
        # get start time
        hours, minutes, seconds = widgets.timeEdit_2.time().toString().split(":")

        # open video in browser
        webbrowser.open(f"https://www.twitch.tv/videos/{vid['id']}?t={hours}h{minutes}m{seconds}s")

    def fetch_videos(self):
        # demo fill table
        channel = widgets.lineEdit_2.text()
        vids = twitch.get_channel_videos(channel, limit=100, sort="time")["edges"]
        widgets.tableWidget_4.clearContents()
        widgets.tableWidget_4.setRowCount(len(vids))
        for i in range(len(vids)):
            vid = vids[i]["node"]
            self.videolist.append(vid)
            h = int(vid["lengthSeconds"]) // 3600
            m = (int(vid["lengthSeconds"]) - h * 3600) // 60
            s = int(vid["lengthSeconds"]) - h * 3600 - m * 60
            widgets.tableWidget_4.setItem(i, 0, QTableWidgetItem(vid["createdAt"]))
            widgets.tableWidget_4.setItem(i, 1, QTableWidgetItem(f"{h}:{m}:{s}"))
            widgets.tableWidget_4.setItem(i, 2, QTableWidgetItem(vid["title"]))

    def donwload_video_proxy(self):
        import threading

        c = threading.Thread(target=self.donwload_video)
        c.start()

    def download_clip_link_proxy(self):

        import threading

        c = threading.Thread(target=self.download_clip_link)
        c.start()

    def download_clip_link(self):
        url_slug = widgets.lineEdit_5.text()
        self.download_internal_clip(url_slug, label=widgets.donwload_stat_link)


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
        target = twitch._video_target_filename(video, args)

        print("<dim>Fetching playlists...</dim>")
        playlists_m3u8 = twitch.get_playlists(video["id"], access_token)
        playlists = list(twitch._parse_playlists(playlists_m3u8))
        playlist_uri = twitch._get_playlist_by_name(playlists, "source")

        print("<dim>Fetching playlist...</dim>")
        response = httpx.get(playlist_uri)
        response.raise_for_status()
        playlist = m3u8.loads(response.text)

        base_uri = re.sub("/[^/]+$", "/", playlist_uri)
        target_dir = twitch._crete_temp_dir(base_uri, self.folder)
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
        set_progresstxt("Creating Video File...")
        print(target)
        print(target_dir)
        twitch._join_vods(playlist_path, os.path.join(self.folder, target), True, video)
        # delete temp folder - target_dir two levels up
        shutil.rmtree(os.path.dirname(os.path.dirname(target_dir)))
        set_progresstxt("Done")

    def logout(self):
        global twitch_token
        twitch_token = None
        widgets.btn_login.show()
        widgets.btn_logout.hide()

    def login(self):
        global twitch_token

        serv = HTTPServer(("localhost", port), self.Server)

        login_thread = threading.Thread(target=serv.serve_forever)

        login_thread.start()

        webbrowser.open(
            "https://id.twitch.tv/oauth2/authorize?client_id="
            + CLIENT_ID
            + "&redirect_uri=http://localhost:" + str(port) + "&response_type=token&scope=channel:read:subscriptions" # &force_verify=true
        )
        # wait for twitch login

        while twitch_token is None:
            print("waiting for twitch login")
            time.sleep(1)
        widgets.btn_login.hide()
        widgets.btn_logout.show()

        widgets.pushButton_2.setEnabled(True)
        widgets.pushButton_3.setEnabled(True)

        print("closing server")
        time.sleep(1)
        serv.shutdown()

    def download_clip(self):
        
        # download all selected clips
        to_download = []
        for i in widgets.tableWidget_5.selectionModel().selectedRows():
            # url from column 5
            # if row hidden dont
            if not widgets.tableWidget_5.isRowHidden(i.row()):
                to_download.append(json.loads(widgets.tableWidget_5.item(i.row(), 5).text()))

        for i in range(len(to_download)):
            widgets.labelprogress_2.setText(f"Downloading clip {i+1}/{len(to_download)}")
            self.download_internal_clip(to_download[i]["url"], widgets.labelprogress_2)

    def download_internal_clip(self, clip_url, label):
        args = {"output": "{date}_{id}_{channel_login}_{title_slug}.{format}", "format": "mp4"}
        slug = clip_url.replace("https://clips.twitch.tv/", "")

        clip = twitch.get_clip(slug)

        target = twitch._clip_target_filename(clip, args)
        target = os.path.join(self.folder, target)
        print("Target: <blue>{}</blue>".format(target))

        url = twitch.get_clip_authenticated_url(slug, "source")
        print("<dim>Selected URL: {}</dim>".format(url))

        print("<dim>Downloading clip...</dim>")
        twitch.download_file(url, target)

        print("Downloaded: <blue>{}</blue>".format(target))

        label.setText("Done")

    def download_clip_proxy(self):
        import threading

        c = threading.Thread(target=self.download_clip)
        c.start()

    def clip_filter(self):
        # if line is empty, show all rows
        if widgets.lineEdit_4.text() == "":
            for i in range(widgets.tableWidget_5.rowCount()):
                widgets.tableWidget_5.showRow(i)
            return

        for i in range(widgets.tableWidget_5.rowCount()):
            widgets.tableWidget_5.hideRow(i)
            for j in range(widgets.tableWidget_5.columnCount()):
                if widgets.lineEdit_4.text() in widgets.tableWidget_5.item(i, j).text():
                    widgets.tableWidget_5.showRow(i)
                    break

    def clip_selected(self):
        # if selected column is 4, then find url from clip_list and open in browser
        row = widgets.tableWidget_5.currentRow()
        col = widgets.tableWidget_5.currentColumn()
        if col == 4:
            # get url from column 5
            print(widgets.tableWidget_5.item(row, 5).text())
            clip_url = json.loads(widgets.tableWidget_5.item(row, 5).text())["url"]

            webbrowser.open(clip_url)

    def fetch_clips(self):
        channel = widgets.lineEdit_3.text()
        print(f"fetching clips from {channel}")

        clips = twitch.get_clips_filtered(channel_id=channel, after=widgets.dateEdit.date(), before=widgets.dateEdit_2.date(), access_token=twitch_token, client_id=CLIENT_ID)

        widgets.tableWidget_5.clearContents()
        widgets.tableWidget_5.setRowCount(len(clips))
        # set column names
        widgets.tableWidget_5.setHorizontalHeaderLabels(["Created", "Creator", "Views", "Duration", "Title"])
        # show header
        widgets.tableWidget_5.horizontalHeader().show()
        for i in range(len(clips)):
            # self.clip_list.append(clips[i])
            widgets.tableWidget_5.setItem(i, 0, QTableWidgetItem(clips[i]["created_at"]))
            widgets.tableWidget_5.setItem(i, 1, QTableWidgetItem(clips[i]["creator_name"]))
            widgets.tableWidget_5.setItem(i, 2, QTableWidgetItem(str(clips[i]["view_count"])))
            widgets.tableWidget_5.setItem(i, 3, QTableWidgetItem(str(clips[i]["duration"]) + "s"))
            widgets.tableWidget_5.setItem(i, 4, QTableWidgetItem(clips[i]["title"]))
            widgets.tableWidget_5.setItem(i, 5, QTableWidgetItem(json.dumps(clips[i])))

        # hide url column
        widgets.tableWidget_5.setColumnHidden(5, True)
        # resize columns
        widgets.tableWidget_5.resizeColumnsToContents()

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
            widgets.stackedWidget.setCurrentWidget(widgets.clips)
            UIFunctions.resetStyle(self, btnName)
            btn.setStyleSheet(UIFunctions.selectMenu(btn.styleSheet()))

        # SHOW NEW PAGE
        if btnName == "btn_new":
            widgets.stackedWidget.setCurrentWidget(widgets.vods)  # SET PAGE
            UIFunctions.resetStyle(self, btnName)  # RESET ANOTHERS BUTTONS SELECTED
            btn.setStyleSheet(UIFunctions.selectMenu(btn.styleSheet()))  # SELECT MENU

        # if btnName == "btn_save":
        #     widgets.stackedWidget.setCurrentWidget(widgets.widgets)
        #     UIFunctions.resetStyle(self, btnName)  # RESET ANOTHERS BUTTONS SELECTED
        #     btn.setStyleSheet(UIFunctions.selectMenu(btn.styleSheet()))  # SELECT MENU

        # if btnName == "btn_save":
        #     print("Save BTN clicked!")

        # # PRINT BTN NAME
        # print(f'Button "{btnName}" pressed!')
        pass

    # RESIZE EVENTS
    # ///////////////////////////////////////////////////////////////
    def resizeEvent(self, event):
        # Update Size Grips
        UIFunctions.resize_grips(self)

    # MOUSE CLICK EVENTS
    # ///////////////////////////////////////////////////////////////
    def mousePressEvent(self, event):
        # SET DRAG POS WINDOW
        self.dragPos = event.globalPosition().toPoint()

        # PRINT MOUSE EVENTS
        # if event.buttons() == Qt.LeftButton:
        #     print("Mouse click: LEFT CLICK")
        # if event.buttons() == Qt.RightButton:
        #     print("Mouse click: RIGHT CLICK")

    # on exit
    # ///////////////////////////////////////////////////////////////
    def closeEvent(self, event):
        print("Closing")
        # close localhost thread<


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon("icon.ico"))
    window = MainWindow()
    sys.exit(app.exec())

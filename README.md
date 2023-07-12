# Vod-Dl for twitch

very alpha - kinda ready for use

![image](https://github.com/Dschogo/vod-dl/assets/36862419/81a90ab5-e58b-45a2-84a5-3272fd42ade9)


made with PyDracula - Modern GUI PySide6 / PyQt6
Heavily based on twitch-dl (see twitch.py)

# quirks and hidden features
- to use the clips tab you have to be logged in
- dont forget to set the output folder
- clicking on the clip name opens it in a browser


# TODO
- tidy up code - name buttons in qt
- fancy up and polish the ui (picker css)
- create installer and make proper versioning
- qol improvements
- fix the hard 100 clip cap per day (only teh first 100 clips per day are fetched - needs smart way to check that and fetch rest)

it *should* work with sub only vods, didn't test 

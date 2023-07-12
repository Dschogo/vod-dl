import requests
import datetime
import httpx
from typing import Dict
import m3u8
from pathlib import Path
from urllib.parse import urlparse, urlencode
import os
from typing import List, Optional, OrderedDict
from extensions.progess import Progress
import subprocess
import re
import unicodedata
from datetime import date, timedelta

CLIENT_ID = "kd1unb4b3q4t58fwlpcbzcbnm76a8fp"

VIDEO_FIELDS = """
    id
    title
    createdAt
    broadcastType
    lengthSeconds
    game {
        name
    }
    creator {
        login
        displayName
    }
"""


def slugify(value):
    value = unicodedata.normalize("NFKC", str(value))
    value = re.sub(r"[^\w\s_-]", "", value)
    value = re.sub(r"[\s_-]+", "_", value)
    return value.strip("_").lower()


def titlify(value):
    value = unicodedata.normalize("NFKC", str(value))
    value = re.sub(r"[^\w\s\[\]().-]", "", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _video_target_filename(video, args):
    date, time = video["createdAt"].split("T")
    game = video["game"]["name"] if video["game"] else "Unknown"

    subs = {
        "channel": video["creator"]["displayName"],
        "channel_login": video["creator"]["login"],
        "date": date,
        "datetime": video["createdAt"],
        "format": args["format"],
        "game": game,
        "game_slug": slugify(game),
        "id": video["id"],
        "time": time,
        "title": titlify(video["title"]),
        "title_slug": slugify(video["title"]),
    }

    try:
        return args["output"].format(**subs)
    except KeyError as e:
        supported = ", ".join(subs.keys())
        raise ConsoleError("Invalid key {} used in --output. Supported keys are: {}".format(e, supported))


def _clip_target_filename(clip, args):
    date, time = clip["createdAt"].split("T")
    game = clip["game"]["name"] if clip["game"] else "Unknown"

    url = clip["videoQualities"][0]["sourceURL"]
    _, ext = os.path.splitext(url)
    ext = ext.lstrip(".")

    subs = {
        "channel": clip["broadcaster"]["displayName"],
        "channel_login": clip["broadcaster"]["login"],
        "date": date,
        "datetime": clip["createdAt"],
        "format": ext,
        "game": game,
        "game_slug": slugify(game),
        "id": clip["id"],
        "slug": clip["slug"],
        "time": time,
        "title": titlify(clip["title"]),
        "title_slug": slugify(clip["title"]),
    }

    try:
        return args["output"].format(**subs)
    except KeyError as e:
        supported = ", ".join(subs.keys())
        raise ConsoleError("Invalid key {} used in --output. Supported keys are: {}".format(e, supported))


def get_clip_access_token(slug):
    query = """
    {{
        "operationName": "VideoAccessToken_Clip",
        "variables": {{
            "slug": "{slug}"
        }},
        "extensions": {{
            "persistedQuery": {{
                "version": 1,
                "sha256Hash": "36b89d2507fce29e5ca551df756d27c1cfe079e2609642b4390aa4c35796eb11"
            }}
        }}
    }}
    """

    response = gql_post(query.format(slug=slug).strip())
    return response["data"]["clip"]


def authenticated_post(url, data=None, json=None, headers={}):
    headers["Client-ID"] = CLIENT_ID

    response = httpx.post(url, data=data, json=json, headers=headers)
    if response.status_code == 400:
        data = response.json()
        raise ConsoleError(data["message"])

    response.raise_for_status()

    return response


CLIP_FIELDS = """
    id
    slug
    title
    createdAt
    viewCount
    durationSeconds
    url
    videoQualities {
        frameRate
        quality
        sourceURL
    }
    game {
        id
        name
    }
    broadcaster {
        displayName
        login
    }
"""


def get_clip(slug):
    query = """
    {{
        clip(slug: "{}") {{
            {fields}
        }}
    }}
    """

    response = gql_query(query.format(slug, fields=CLIP_FIELDS))
    return response["data"]["clip"]


def gql_post(query):
    url = "https://gql.twitch.tv/gql"
    response = authenticated_post(url, data=query).json()

    if "errors" in response:
        raise GQLError(response["errors"])

    return response


CHUNK_SIZE = 1024
CONNECT_TIMEOUT = 5
RETRY_COUNT = 5


class DownloadFailed(Exception):
    pass


def _download(url: str, path: str):
    tmp_path = path + ".tmp"
    size = 0
    with httpx.stream("GET", url, timeout=CONNECT_TIMEOUT) as response:
        with open(tmp_path, "wb") as target:
            for chunk in response.iter_bytes(chunk_size=CHUNK_SIZE):
                target.write(chunk)
                size += len(chunk)

    os.rename(tmp_path, path)
    return size


def download_file(url: str, path_o: str, retries: int = RETRY_COUNT):
    if os.path.exists(path_o):
        from_disk = True
        return (os.path.getsize(path_o), from_disk)

    from_disk = False
    for _ in range(retries):
        try:
            return (_download(url, path_o), from_disk)
        except httpx.RequestError:
            pass

    raise DownloadFailed(":(")


def _get_clip_url(clip, quality):
    qualities = clip["videoQualities"]

    # Quality given as an argument
    if quality:
        if quality == "source":
            return qualities[0]["sourceURL"]

        selected_quality = quality.rstrip("p")  # allow 720p as well as 720
        for q in qualities:
            if q["quality"] == selected_quality:
                return q["sourceURL"]

        available = ", ".join([str(q["quality"]) for q in qualities])
        msg = "Quality '{}' not found. Available qualities are: {}".format(quality, available)
        raise ConsoleError(msg)


def get_clip_authenticated_url(slug, quality):
    print("<dim>Fetching access token...</dim>")
    access_token = get_clip_access_token(slug)

    if not access_token:
        raise ConsoleError("Access token not found for slug '{}'".format(slug))

    url = _get_clip_url(access_token, quality)

    query = urlencode(
        {
            "sig": access_token["playbackAccessToken"]["signature"],
            "token": access_token["playbackAccessToken"]["value"],
        }
    )

    return "{}?{}".format(url, query)


def _join_vods(playlist_path, target, overwrite, video):
    command = [
        "ffmpeg",
        "-i",
        playlist_path,
        "-c",
        "copy",
        "-metadata",
        "artist={}".format(video["creator"]["displayName"]),
        "-metadata",
        "title={}".format(video["title"]),
        "-metadata",
        "encoded_by=twitch-dl",
        "-stats",
        "-loglevel",
        "warning",
        "file:{}".format(target),
    ]

    if overwrite:
        command.append("-y")

    print("<dim>{}</dim>".format(" ".join(command)))
    result = subprocess.run(command)
    if result.returncode != 0:
        raise ConsoleError("Joining files failed")


def _get_vod_paths(playlist, start: Optional[int], end: Optional[int]) -> List[str]:
    """Extract unique VOD paths for download from playlist."""
    files = []
    vod_start = 0
    for segment in playlist.segments:
        vod_end = vod_start + segment.duration

        # `vod_end > start` is used here becuase it's better to download a bit
        # more than a bit less, similar for the end condition
        start_condition = not start or vod_end > start
        end_condition = not end or vod_start < end

        if start_condition and end_condition and segment.uri not in files:
            files.append(segment.uri)

        vod_start = vod_end

    return files


def _crete_temp_dir(base_uri: str, root_output) -> str:
    """Create a temp dir to store downloads if it doesn't exist."""
    path = urlparse(base_uri).path.lstrip("/")
    temp_dir = Path(root_output, "twitch-dl", path)
    temp_dir.mkdir(parents=True, exist_ok=True)
    return str(temp_dir)


def get_access_token(video_id, auth_token=None):
    query = """
    {{
        videoPlaybackAccessToken(
            id: {video_id},
            params: {{
                platform: "web",
                playerBackend: "mediaplayer",
                playerType: "site"
            }}
        ) {{
            signature
            value
        }}
    }}
    """

    query = query.format(video_id=video_id)

    headers = {}
    if auth_token is not None:
        headers["authorization"] = f"Bearer {auth_token}"

    try:
        response = gql_query(query, headers=headers)
        return response["data"]["videoPlaybackAccessToken"]
    except httpx.HTTPStatusError as error:
        # Provide a more useful error message when server returns HTTP 401
        # Unauthorized while using a user-provided auth token.
        if error.response.status_code == 401:
            if auth_token:
                raise ConsoleError("Unauthorized. The provided auth token is not valid.")
            else:
                raise ConsoleError("Unauthorized. This video may be subscriber-only.\n" "Login in settings to use your Twitch account to access subscriber-only videos.")

        raise


def _get_playlist_by_name(playlists, quality):
    if quality == "source":
        _, _, uri = playlists[0]
        return uri

    for name, _, uri in playlists:
        if name == quality:
            return uri

    available = ", ".join([name for (name, _, _) in playlists])
    msg = "Quality '{}' not found. Available qualities are: {}".format(quality, available)
    raise ConsoleError(msg)


def _parse_playlists(playlists_m3u8):
    playlists = m3u8.loads(playlists_m3u8)

    for p in sorted(playlists.playlists, key=lambda p: p.stream_info.resolution is None):
        if p.stream_info.resolution:
            name = p.media[0].name
            description = "x".join(str(r) for r in p.stream_info.resolution)
        else:
            name = p.media[0].group_id
            description = None

        yield name, description, p.uri


def get_playlists(video_id, access_token):
    """
    For a given video return a playlist which contains possible video qualities.
    """
    url = "http://usher.ttvnw.net/vod/{}".format(video_id)

    response = httpx.get(
        url,
        params={
            "nauth": access_token["value"],
            "nauthsig": access_token["signature"],
            "allow_audio_only": "true",
            "allow_source": "true",
            "player": "twitchweb",
        },
    )
    response.raise_for_status()
    return response.content.decode("utf-8")


def get_channel_videos(channel_id, limit, sort, type="archive", game_ids=[], after=None):
    query = """
    {{
        user(login: "{channel_id}") {{
            videos(
                first: {limit},
                type: {type},
                sort: {sort},
                after: "{after}",
                options: {{
                    gameIDs: {game_ids}
                }}
            ) {{
                totalCount
                pageInfo {{
                    hasNextPage
                }}
                edges {{
                    cursor
                    node {{
                        {fields}
                    }}
                }}
            }}
        }}
    }}
    """

    query = query.format(channel_id=channel_id, game_ids=game_ids, after=after if after else "", limit=limit, sort=sort.upper(), type=type.upper(), fields=VIDEO_FIELDS)

    response = gql_query(query)

    if not response["data"]["user"]:
        raise ConsoleError("Channel {} not found".format(channel_id))

    return response["data"]["user"]["videos"]


class ConsoleError(Exception):
    """Raised when an error occurs and script exectuion should halt."""

    pass


def gql_query(query: str, headers: Dict[str, str] = {}):
    url = "https://gql.twitch.tv/gql"
    response = authenticated_post(url, json={"query": query}, headers=headers).json()

    if "errors" in response:
        raise GQLError(response["errors"])

    return response


def authenticated_post(url, data=None, json=None, headers={}):
    headers["Client-ID"] = CLIENT_ID

    response = httpx.post(url, data=data, json=json, headers=headers)
    if response.status_code == 400:
        data = response.json()
        raise ConsoleError(data["message"])

    response.raise_for_status()

    return response


def get_clips_filtered(channel_id, limit, after, before, client_id, access_token):
    user = requests.get("https://api.twitch.tv/helix/users?login=" + channel_id, headers={"Client-ID": client_id, "authorization": "Bearer " + access_token}).json()

    # iter over all days

    d0 = date(after.year(), after.month(), after.day())
    d1 = date(before.year(), before.month(), before.day())

    delta = d1 - d0

    clips = []

    for i in range(delta.days + 1):
        day = d0 + timedelta(days=i)
        c = requests.get(
            "https://api.twitch.tv/helix/clips?broadcaster_id="
            + user["data"][0]["id"]
            + "&first="
            + str(limit)
            + "&started_at="
            + str(day)
            + "T00:00:00Z"
            + "&ended_at="
            + str(day)
            + "T23:59:59Z",
            headers={"Client-ID": client_id, "Authorization": "Bearer " + access_token},
        ).json()
        for x in c["data"]:
            clips.append(x)
    return clips


class GQLError(Exception):
    def __init__(self, errors):
        super().__init__("GraphQL query failed")
        self.errors = errors

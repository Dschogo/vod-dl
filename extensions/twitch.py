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
    value = unicodedata.normalize('NFKC', str(value))
    value = re.sub(r'[^\w\s_-]', '', value)
    value = re.sub(r'[\s_-]+', '_', value)
    return value.strip("_").lower()


def titlify(value):
    value = unicodedata.normalize('NFKC', str(value))
    value = re.sub(r'[^\w\s\[\]().-]', '', value)
    value = re.sub(r'\s+', ' ', value)
    return value.strip()


def _video_target_filename(video, args):
    date, time = video['createdAt'].split("T")
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

def _join_vods(playlist_path, target, overwrite, video):
    command = [
        "ffmpeg",
        "-i", playlist_path,
        "-c", "copy",
        "-metadata", "artist={}".format(video["creator"]["displayName"]),
        "-metadata", "title={}".format(video["title"]),
        "-metadata", "encoded_by=twitch-dl",
        "-stats",
        "-loglevel", "warning",
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

def _crete_temp_dir(base_uri: str) -> str:
    """Create a temp dir to store downloads if it doesn't exist."""
    path = urlparse(base_uri).path.lstrip("/")
    temp_dir = Path(os.getcwd(), "twitch-dl", path)
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
        headers['authorization'] = f'OAuth {auth_token}'

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
                raise ConsoleError(
                    "Unauthorized. This video may be subscriber-only.\n"
                    "Login in settings to use your Twitch account to access subscriber-only videos."
                )

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

    response = httpx.get(url, params={
        "nauth": access_token['value'],
        "nauthsig": access_token['signature'],
        "allow_audio_only": "true",
        "allow_source": "true",
        "player": "twitchweb",
    })
    response.raise_for_status()
    return response.content.decode('utf-8')

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

    query = query.format(
        channel_id=channel_id,
        game_ids=game_ids,
        after=after if after else "",
        limit=limit,
        sort=sort.upper(),
        type=type.upper(),
        fields=VIDEO_FIELDS
    )

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
    headers['Client-ID'] = CLIENT_ID

    response = httpx.post(url, data=data, json=json, headers=headers)
    if response.status_code == 400:
        data = response.json()
        raise ConsoleError(data["message"])

    response.raise_for_status()

    return response

class GQLError(Exception):
    def __init__(self, errors):
        super().__init__("GraphQL query failed")
        self.errors = errors
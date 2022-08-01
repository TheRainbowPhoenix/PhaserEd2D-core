"""
Phaser Ed 2D core server ptyhon single-file !
Trying to be as compatible as possible ...

How cool is that ?
Need Pyton 3.10+, fastapi, jinja2 & uvicorn
"""
import argparse
import glob
import re
import shutil
import sys
import time
import json
from asyncio import Task
from collections import defaultdict
from typing import Union, Dict, List, Optional
import os
import pathlib
import hashlib
import asyncio
import webbrowser

import typing
from fastapi import FastAPI, Request, UploadFile, Form
from fastapi.middleware.gzip import GZipMiddleware
from starlette.responses import HTMLResponse, RedirectResponse
from starlette.staticfiles import StaticFiles, PathLike

from pydantic import BaseModel, BaseSettings
from pydantic.typing import Literal
from starlette.types import Scope, Receive, Send
from watchfiles import awatch


class Settings(BaseSettings):
    project: pathlib.Path | None = None
    hash: str = ''
    max_number_files: int = 1000
    port: int = 3355
    disable_colors: bool = False
    disable_gzip: bool = False
    dev: bool = False
    pub: bool = False
    editor: pathlib.Path | None = None
    extra_plugins: List[str] = []
    extra_plugins_dir: List[str] = []
    skip_dir: List[str] = []
    filter_rules: List[str] = []
    plugins_order: Dict[int, List[str]] = {}
    plugins_map: Dict[str, Dict[str, List[str]]] = {}


# Simple setting base, used for shared config and hash passing
settings = Settings()


# API models here - Recreated from AJAX calls

class APIRequest(BaseModel):
    __track__ = defaultdict(list)


class GetServerMode(APIRequest):
    method: Literal['GetServerMode']


class GetNewVersionAvailable(APIRequest):
    method: Literal['GetNewVersionAvailable']


class GetProjectFiles(APIRequest):
    method: Literal['GetProjectFiles']
    body: dict


class GetProjectFilesHash(APIRequest):
    method: Literal['GetProjectFilesHash']
    body: dict


class OpenFileManagerBody(BaseModel):
    file: str


class OpenFileManager(APIRequest):
    method: Literal['OpenFileManager']
    body: OpenFileManagerBody


class OpenVSCodeBody(BaseModel):
    location: str


class OpenVSCode(APIRequest):
    method: Literal['OpenVSCode']
    body: OpenVSCodeBody


class SetFileStringBody(BaseModel):
    path: str
    content: str


class SetFileString(APIRequest):
    method: Literal['SetFileString']
    body: SetFileStringBody


class RenameFileBody(BaseModel):
    oldPath: str
    newPath: str


class RenameFile(APIRequest):
    method: Literal['RenameFile']
    body: RenameFileBody


class CreateFolderBody(BaseModel):
    path: str


class CreateFolder(APIRequest):
    method: Literal['CreateFolder']
    body: CreateFolderBody


class DeleteFilesBody(BaseModel):
    paths: List[str]


class DeleteFiles(APIRequest):
    method: Literal['DeleteFiles']
    body: DeleteFilesBody


class CopyFileBody(BaseModel):
    fromPath: str
    toPath: str


class CopyFile(APIRequest):
    method: Literal['CopyFile']
    body: CopyFileBody


class MoveFilesBody(BaseModel):
    movingPaths: List[str]
    movingToPath: str


class MoveFiles(APIRequest):
    method: Literal['MoveFiles']
    body: MoveFilesBody


# File helpers


def get_mod_time(path) -> int:
    """
    Get the time of modification
    :param path: path string
    :return: time in nanoseconds
    """
    return int(os.path.getmtime(path) * 1000000000)


def file_filtered(file, rules=[]) -> bool:
    """
    CHeck if file or folder is ignored
    :param file: file string name
    :return: boolean
    """

    return (
        any([pathlib.PurePath(file).match(i) for i in rules]) or
        os.path.join(settings.project, file) in settings.skip_dir
    )


def _list_files(start_path, counters: Dict[str, int], filter_rules=[]):
    """
    List all file to the JSON format expected
    :param start_path: string path
    :param counters: file and dir counters
    :return:
    """

    items = []
    rules = filter_rules
    if os.path.isfile(os.path.join(start_path, '.skip')):
        try:
            with open(os.path.join(start_path, '.skip')) as f:
                skip_rules = read_skip_file(f)

            if skip_rules is []:
                # If the .skip file is empty, then the editor assumes it has a * pattern.
                # It means, it will exclude all the folder’s content. We did it that way for backward compatibility
                # with previous versions of the editor.
                return
        except:
            skip_rules = []

        rules = list(set(rules + skip_rules))

    for element in sorted(os.listdir(start_path)):

        if file_filtered(os.path.join(start_path, element), rules=rules):
            continue

        path = os.path.join(start_path, element)

        item = {
            "name": os.path.basename(path),
            "modTime": get_mod_time(path),
            "size": os.path.getsize(path)
        }
        if os.path.isfile(path):
            item["isFile"] = True
            counters['file'] += 1
        if os.path.isdir(path):
            counters['dir'] += 1
            item["children"] = _list_files(path, counters, filter_rules)

        items.append(item)

    return items


def get_files_list(d):
    """
    Get all files in project and return them as JSON
    :param d: directory path
    :return: json object
    """
    base = {
        "rootFile": {
            "name": os.path.basename(d),
            "modTime": get_mod_time(d),
            "size": 4096,
            "children": []
        }, "maxNumberOfFiles": 0, "projectNumberOfFiles": 0, "hash": settings.hash}

    counter = {'file': 0, 'dir': 0}
    base["rootFile"]["children"] = _list_files(d, counter, settings.filter_rules)
    base["projectNumberOfFiles"] = counter['file']
    # Weird file based limit. Ignore it.
    base["maxNumberOfFiles"] = settings.max_number_files

    return base


# API responses
# ============
# Basically function name are really important because I'm reflecting the ModelsClass to their models_class methods
# automatically. See the "resp_map" lower for how it's done :D


async def get_server_mode(body: GetServerMode):
    # No idea if I have to change anything here
    return {
        'desktop': True,
        'externalEditorName': "Visual Studio Code",
        'unlocked': True
    }


async def get_project_files_hash(body: GetProjectFilesHash):
    """
    Poll for file changes. WatchFiles carry us with lightning fast async watch so I didn't experienced any de-sync while testing ...

    Refence use go Hash function backed by sha1 and crc32. Since it's not really useful here, simply hash the timestamp
    :param body:
    :return:
    """
    if settings.hash == '':
        data = get_mod_time(settings.project)
        settings.hash = hashlib.sha256(data.to_bytes(16, sys.byteorder)).hexdigest()[:32]

    return {
        'hash': settings.hash
    }


async def get_project_files(body: GetProjectFilesHash):
    """
    Get a list of all files
    :param body:
    :return:
    """

    return get_files_list(settings.project)


async def get_new_version_available(body: GetNewVersionAvailable):
    """
    Checks for new release, ignore it for now !
    :param body:
    :return:
    """
    # TODO: implement some real updating
    return {'available': False}


async def open_file_manager(body: OpenFileManager):
    """
    Open file or folder in explorer
    :param body: OpenFileManager body request
    :return:
    """
    if settings.pub:
        error = "You're running public mode (\"-public\" flag). That feature have been disabled."
        print_info(error)
        return {
            'error': error
        }

    import subprocess

    path = os.path.normpath(os.path.join(os.path.dirname(settings.project), body.body.file))
    if os.path.isfile(path):
        subprocess.Popen(f'explorer /select,"{path}"')
    else:
        if not os.path.isdir(path):
            path = settings.project
        subprocess.Popen(f'explorer "{path}"')

    return {}


async def open_vscode(body: OpenVSCode):
    """
    Open the project in VSCode
    :param body: OpenVSCode request
    :return:
    """
    if settings.pub:
        error = "You're running public mode (\"-public\" flag). That feature have been disabled."
        print_info(error)
        return {
            'error': error
        }

    import subprocess

    path = os.path.normpath(os.path.join(os.path.dirname(settings.project), body.body.location))
    if os.path.isfile(path):
        subprocess.Popen(f'code "{settings.project}"', shell=True)
    else:
        if not os.path.isdir(path):
            path = settings.project
        subprocess.Popen(f'code "{path}"', shell=True)

    return {}


async def set_file_string(body: SetFileString):
    """
    Main method used to write into file
    :param body: SetFileString model
    :return: file modTime and size
    """
    path = os.path.normpath(os.path.join(os.path.dirname(settings.project), body.body.path))

    # Looks like starlette serve files with carriage return conversion, so undo it here :D
    content = body.body.content.replace('\r\r', '\r').replace('\r\n', '\n')
    if os.path.isfile(path):
        with open(path, 'w+', encoding='utf-8') as f:
            f.write(content)
    elif not os.path.isdir(path):
        with open(path, 'w+', encoding='utf-8') as f:
            f.write(content)

    if os.path.exists(path):
        # os.utime(path, (time.time(), time.time()))
        return {
            "modTime": time.time(),
            "size": os.path.getsize(path)
        }
    else:
        return {
            "modTime": time.time(),
            "size": 0
        }


async def rename_file(body: RenameFile):
    oldPath = os.path.normpath(os.path.join(os.path.dirname(settings.project), body.body.oldPath))
    newPath = os.path.normpath(os.path.join(os.path.dirname(settings.project), body.body.newPath))
    if os.path.exists(oldPath):
        if not os.path.exists(newPath):
            os.rename(oldPath, newPath)
            return {}
        error = "Destination exists"
    else:
        error = "File does not exist"

    return {
        'error': error
    }


async def create_folder(body: CreateFolder):
    path = os.path.normpath(os.path.join(os.path.dirname(settings.project), body.body.path))
    if not os.path.exists(path):
        os.makedirs(path)
        return {
            "modTime": get_mod_time(path)
        }
    else:
        return {
            'error': "Folder already exists"
        }


async def delete_files(body: DeleteFiles):
    for file in body.body.paths:
        path = os.path.normpath(os.path.join(os.path.dirname(settings.project), file))
        if os.path.exists(path):
            os.remove(path)
    return {}


async def copy_file(body: CopyFile):
    fromPath = os.path.normpath(os.path.join(os.path.dirname(settings.project), body.body.fromPath))
    toPath = os.path.normpath(os.path.join(os.path.dirname(settings.project), body.body.toPath))
    if os.path.exists(fromPath):
        if not os.path.exists(toPath):
            shutil.copyfile(fromPath, toPath)

            return {
                "file": {
                    "name": os.path.basename(toPath),
                    "modTime": get_mod_time(toPath),
                    "size": os.path.getsize(toPath),
                    "isFile": os.path.isdir(toPath)
                }
            }

        error = "Destination exists"
    else:
        error = "File does not exist"

    if error:
        return {
            'error': error
        }


async def move_files(body: MoveFiles):
    dest = os.path.normpath(os.path.join(os.path.dirname(settings.project), body.body.movingToPath))

    for file in body.body.movingPaths:
        path = os.path.normpath(os.path.join(os.path.dirname(settings.project), file))
        toFile = os.path.normpath(os.path.join(dest, os.path.basename(file)))
        if not os.path.exists(toFile):
            shutil.move(path, toFile)
    return {}


# Map response to method

def snekify(name: str) -> str:
    """
    Convert CamelCase to python_case strings
    :param name:
    :return:
    """
    return re.sub('(?!^)([A-Z]+)', r'_\1', name).lower()


# Auto mapping MethodsName to methods_name functions.
# Trick is to use globals() to get all functions and since they all extends APIRequest, use "_subclasses__()" to get
# all and "snek_case_ify" them !
resp_map = {
    i.__name__: globals()[snekify(i.__name__)] for i in APIRequest.__subclasses__() if snekify(i.__name__) in globals()
}


def discover_plugins(plugin_dir: str = "editor/plugins") -> (Dict[int, List[str]], Dict[str, Dict[str, List[str]]]):
    """
    Attempt to discover all plugins files
    :param plugin_dir: default plugins directory
    :return: (plugins_order, plugins_map)
    """
    plugins_order = {}
    plugins_map = {}

    all_dirs = settings.extra_plugins_dir
    if not os.path.normpath(plugin_dir) in all_dirs:
        all_dirs.append(os.path.normpath(plugin_dir))

    for plugin in sum(
            [glob.glob(os.path.join(i, 'plugin.json')) for i in settings.extra_plugins if os.path.isdir(i)] +
            [glob.glob(os.path.join(d, '*/plugin.json')) for d in all_dirs if os.path.isdir(d)]
            , []):
        path = os.path.normpath(plugin)
        try:
            with open(path, encoding='utf-8') as f:
                data = json.load(f)
                id = data["id"]
                priority: int = data.get("priority", 0)
                styles: list = data.get("styles", [])
                scripts: list = data.get("scripts", [])

                styles_dev: list = data.get("styles-dev", None)
                scripts_dev: list = data.get("scripts-dev", None)

                if id in plugins_map:
                    print(f"[i] Plugin already loaded : {id}")
                    continue

                # Creating plugin struct
                plugins_map[id] = {
                    'styles': styles,
                    'scripts': scripts
                }

                if styles_dev:
                    plugins_map[id]['styles-dev'] = styles_dev

                if scripts_dev:
                    plugins_map[id]['scripts-dev'] = scripts_dev

                # Adding plugin to priority queue
                if not priority in plugins_order:
                    plugins_order[priority] = []

                plugins_order[priority].append(id)

        except Exception as e:
            print_error(f"Bad plugin : {path}")
            print(e)

    return plugins_order, plugins_map


def custom_exception_handler(loop, context):
    """
    Custom handler used for async errors.
    :param loop:
    :param context:
    :return:
    """
    loop.default_exception_handler(context)

    exception = context.get('exception')
    if isinstance(exception, ZeroDivisionError):
        print(context)
        loop.stop()


async def watch_changes(settings: Settings):
    """
    Change last update hash on file change in directory
    :param settings:
    :return:
    """
    try:
        async for changes in awatch(settings.project):
            data = int(time.time() * 1_000_000)
            settings.hash = hashlib.sha256(data.to_bytes(16, sys.byteorder)).hexdigest()[:32]

            for change in changes:
                change_type, filename = change
                if filename == os.path.abspath(os.path.join(settings.project, 'phasereditor2d.config.json')):
                    print_info("Reloading \"phasereditor2d.config.json\" ...")
                    load_project_config(settings)
                    reload_plugins()

    except Exception as e:
        # print(e)
        # Hack: Error from https://github.com/PyO3/pyo3/issues/2525
        pass
        # print(changes)


# Dumb but works !
ALLOWED_IP = ['::1', 'localhost', '127.0.0.1']

# simple wait to avoid XSS and XML injection
_ALLOWED_ID_CHARS = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ!#$%()*+-.:/;=@[]^_{|}~'


def safe(val: str) -> str:
    return "".join(i for i in val if i in _ALLOWED_ID_CHARS)


class MagicPluginsRoute:
    def __init__(
            self,
            directory: typing.Optional[PathLike] = None,
    ) -> None:
        self.static = StaticFiles(directory=directory, html=True)

        for directory in settings.extra_plugins_dir + [os.path.dirname(i) for i in settings.extra_plugins]:
            plugin_directory = os.path.normpath(directory)
            assert os.path.isdir(
                plugin_directory
            ), f"Directory '{directory!r}' could not be found."
            if plugin_directory not in self.static.all_directories:
                self.static.all_directories.append(plugin_directory)

        self.config_checked = False

    # Every calls to URL hit here ...
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self.static(scope, receive, send)


def create_app(conf: Settings) -> FastAPI:
    """
    Like Flask's create_app, but async and cooler !
    :param conf: global conf of the app, also used for hash passing
    :return: app instance
    """
    app = FastAPI()

    global settings

    settings = conf

    if not settings.disable_gzip:
        app.add_middleware(GZipMiddleware, minimum_size=1000)

    if settings.editor:
        if os.path.isdir(settings.editor):
            plugin_dir = os.path.normpath(settings.editor)
        else:
            print_error(f"Invalid folder provided to \"-editor\" argument : \"{settings.editor}\" does not exists.")
            sys.exit(1)
    else:
        plugin_dir = "editor/plugins"
        if not os.path.isdir(plugin_dir):
            print_error(
                "Can't locate \"editor\" folder or its \"plugins\" subdirectory. Please refer to https://github.com/TheRainbowPhoenix/PhaserEd2D-core/wiki/Using-the-bundle")
            sys.exit(1)
        settings.editor = "editor/plugins"

    settings.plugins_order, settings.plugins_map = discover_plugins(plugin_dir)

    # TODO: support for multiple sources plugins
    try:
        app.mount("/editor/app/plugins", MagicPluginsRoute(directory=plugin_dir), name="plugins")
    except:
        print_error(
            "Can't locate \"editor\" folder or its \"plugins\" subdirectory. Please refer to https://github.com/TheRainbowPhoenix/PhaserEd2D-core/wiki/Using-the-bundle")
        sys.exit(1)

    @app.get("/editor/", response_class=HTMLResponse)
    def get_editor(request: Request):

        body = f"""<!DOCTYPE html>\n<html lang="en">\n<head>\n
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="X-UA-Compatible" content="ie=edge">
    <title>Phaser Editor 2D</title>
"""
        styles = ""
        scripts = ""

        for _, ids in sorted(settings.plugins_order.items()):
            for id in ids:
                if id in settings.plugins_map:
                    styles += f"""\n	<!-- plugin:{safe(id)} -->\n"""
                    plugin = settings.plugins_map[id]

                    key = "styles-dev" if settings.dev and "styles-dev" in plugin else "styles"
                    for style in plugin.get(key, []):
                        styles += f'	<link href="app/plugins/{safe(id)}/{safe(style)}?v={int(time.time())}" rel="stylesheet">\n'

                    scripts += f"""\n	<!-- plugin:{safe(id)} -->\n"""

                    key = "scripts-dev" if settings.dev and "scripts-dev" in plugin else "scripts"
                    for style in plugin.get(key, []):
                        scripts += f'	<script src="app/plugins/{safe(id)}/{safe(style)}?v={int(time.time())}"></script>\n'

        body += styles

        body += "</head>\n<body>"

        if len(scripts) < 1:
            # failsafe message
            scripts += "<h1>Nothing's loading ?</h1>\n" \
                       "<p>Looks like no plugins are loaded. Please <a href=\"https://github.com/TheRainbowPhoenix/PhaserEd2D-core/wiki/FAQ\">refer to help pages</a></p>"

        body += scripts

        body += f"""<!--
      ┌───────╖ 
      │  ╓─_  ╟─╮
      │  ╠════╝ │
      ╘╤═╝ ┌────╯
       ╰───╯
        
    Phaser Editor {"dev" if settings.dev else ''}
-->\n"""

        body += "</body>\n</html>"

        return body

    @app.get("/")
    def read_root():
        return RedirectResponse(url='/editor', status_code=303)

    # Actual API route here

    @app.post("/editor/api")
    async def post_api(request: Request, body: Union[
        tuple(APIRequest.__subclasses__())
    ]):
        """
        Post JSON Payload

        method : GetServerMode
        :param body: JSON payload
        :param request:
        :return: JSON response
        """
        client_host = request.client.host

        if settings.pub and client_host not in ALLOWED_IP:
            return {
                'error': 'Public ip not allowed'
            }

        method = body.method
        if method in resp_map:
            return await resp_map[method](body)
        else:
            return {
                'error': 'Invalid method'
            }

    app.mount("/editor/project/", StaticFiles(directory=settings.project, html=True), name="project files")

    @app.post("/editor/upload")
    async def create_upload_file(uploadTo: str = Form(), file: UploadFile | None = None):
        if not file:
            return {"message": "No upload file sent"}
        else:

            path = os.path.normpath(os.path.join(os.path.dirname(settings.project), uploadTo))
            filename = os.path.normpath(os.path.join(path, file.filename))
            if os.path.exists(path) and not os.path.exists(filename):
                content = await file.read()

                with open(filename, 'wb+') as f:
                    size = f.write(content)

                    return {
                        "file": {
                            "name": file.filename,
                            "modTime": time.time(),
                            "size": size,
                            "isFile": True
                        }
                    }
        return {
            "error": "invalid payload"
        }

    app.mount("/editor/external/", StaticFiles(directory=settings.project, html=True), name="project external files")

    return app


def read_skip_file(f) -> list:
    return [l.strip() for l in f.readlines() if (not l.strip().startswith('#') and len(l.strip()) > 0)]


def print_error(message: str):
    """
    Prints an "error" on the console

    :param message: error message
    :return:
    """
    if os.name == 'nt' and not settings.disable_colors:
        from ctypes import windll
        STD_OUTPUT_HANDLE = -11
        stdout_handle = windll.kernel32.GetStdHandle(STD_OUTPUT_HANDLE)

        print("")
        windll.kernel32.SetConsoleTextAttribute(stdout_handle, 4)
        print(f" ▲ {message}")
        windll.kernel32.SetConsoleTextAttribute(stdout_handle, 15)
        print("")
    else:
        print(f"\n [!] {message} \n")


def print_info(message: str):
    """
    Prints an "info" on the console

    :param message: info message
    :return:
    """
    if os.name == 'nt' and not settings.disable_colors:
        from ctypes import windll
        STD_OUTPUT_HANDLE = -11
        stdout_handle = windll.kernel32.GetStdHandle(STD_OUTPUT_HANDLE)

        windll.kernel32.SetConsoleTextAttribute(stdout_handle, 11)
        print(f" · {message}")
        windll.kernel32.SetConsoleTextAttribute(stdout_handle, 15)
    else:
        print(f"\n [i] {message} \n")


def print_welcome(conf: Settings, port: int):
    """
    Print "welcome" console message + user friendliness
    :param args:
    :return:
    """
    host = 'localhost'
    if conf.pub:
        host = "0.0.0.0"
        import socket
        try:
            host = socket.gethostbyname(socket.gethostname())
        except:
            pass

    print("")
    print(f"PhaserEditor2D {'public ' if settings.pub else ''}{'dev ' if settings.dev else ''}server running from:")
    print("")

    if os.name == 'nt' and not conf.disable_colors:
        from ctypes import windll
        STD_OUTPUT_HANDLE = -11
        stdout_handle = windll.kernel32.GetStdHandle(STD_OUTPUT_HANDLE)

        windll.kernel32.SetConsoleTextAttribute(stdout_handle, 9)
        print(f" ● Project : {conf.project}")
        print(f" ■ Local   : http://localhost:{port}/editor")
        if settings.pub:
            print(f" ▶ PlayLan : http://{host}:{port}/editor/external")
        windll.kernel32.SetConsoleTextAttribute(stdout_handle, 15)

    else:
        print(f"""
  > Project : {conf.project}
  > Local   : http://localhost:{port}/editor""")
        if settings.pub:
            print(f"  > PlayLan : http://{host}:{port}/editor/external")

    print("")


# File loading
def load_default_skip() -> list:
    if os.path.isfile("default-skip"):
        with open("default-skip", "r") as f:
            default_skip = read_skip_file(f)
    else:
        default_skip = []
    return default_skip


def load_project_config(conf: Settings):
    project_file = os.path.join(args.project, "phasereditor2d.config.json")
    if os.path.isfile(project_file):
        with open(project_file, encoding="utf-8") as f:
            data = json.load(f)

            # Ignore directories
            if 'skip' in data:
                conf.skip_dir = []

                project_skips = data.get('skip', [])
                for skip in project_skips:
                    path = os.path.normpath(os.path.join(args.project, skip))
                    if os.path.isdir(path):
                        conf.skip_dir.append(path)

            # Extra plugins to load
            if 'plugins' in data:
                conf.extra_plugins = []

                project_plugins = data.get('plugins', [])
                for plugin_rel in project_plugins:
                    plugin_path = os.path.normpath(os.path.join(args.project, plugin_rel))
                    if os.path.isdir(plugin_path):
                        if not plugin_path in conf.extra_plugins:
                            conf.extra_plugins.append(plugin_path)

                            print_info(f"Loading editor plugin : \"{os.path.basename(plugin_rel)}\"")

            # Launch flags
            if 'flags' in data:
                flags = data.get('flags', [])

                if len(flags) > 0:
                    print_info(f"Using custom flags : {repr(flags)[:60]}")

                if '-port' in flags:
                    # Note: won't change in prod ...
                    port_pos = flags.index('-port')
                    if len(flags) > port_pos + 1:
                        try:
                            _port = int(flags[port_pos + 1])
                            if 1024 < _port < 65535:
                                conf.port = _port
                        except:
                            print_error(f"Invalid port number supplied : \"{flags[port_pos + 1]}\"")

                conf.disable_gzip = '-disable-gzip' in flags
                conf.dev = '-dev' in flags
                conf.pub = '-public' in flags

            if 'playUrl' in data:
                pass


def reload_plugins():
    settings.plugins_order = {}
    settings.plugins_map = {}
    settings.plugins_order, settings.plugins_map = discover_plugins(settings.editor)

if __name__ == '__main__':
    import uvicorn

    # TODO: Scanning user home flags "~/.phasereditor2d/flags.txt"

    default_skip = load_default_skip()

    # Don't: Reading license file at resources\app\server\PhaserEditor2D.lic and ~\.phasereditor2d\PhaserEditor2D.lic
    # TODO: User plugins: ~/.phasereditor2d/plugins
    # Plugins are loaded by their "plugin.json" file
    # Read package.json
    # Read default-skip for file scanning
    # Read each folder for ".skip" file

    # TODO: Plugin: scanning and watch

    # args : -disable-open-browser -port 3354 -project C:/Users/Me/Documents/test_phaser_sunny_land

    parent_parser = argparse.ArgumentParser(add_help=True)
    parent_parser.add_argument('-port', type=int, default=3355, help='Server port (default 3355)')
    parent_parser.add_argument('-project', type=str, metavar='path', required=True,
                               help='Path to the project directory')
    parent_parser.add_argument('-public', action='store_true', help='Allows remote connections')
    parent_parser.add_argument('-max-number-files', type=int, default=1000,
                               help='Maximum number files per project (default 1000)')
    parent_parser.add_argument('-dev', action='store_true', help='Enables developer features, with source map loading')
    parent_parser.add_argument('-disable-open-browser', action='store_true', help='Don\'t launch the browser')
    parent_parser.add_argument('-disable-colors', action='store_true', help='Don\'t print cool colors on console')
    parent_parser.add_argument('-disable-gzip', action='store_true',
                               help='Disable Gzip compression of large HTTP responses')
    parent_parser.add_argument('-editor', type=str, metavar='path', default='editor/plugins',
                               help='Path to the \'editor\' directory (default to current directory)')

    args = parent_parser.parse_args()

    extra_plugins_dir = []

    disable_gzip = args.disable_gzip
    dev = args.dev
    public = args.public or False

    port = args.port or 3355

    # load_project_config()

    # Reading project config  ==> phasereditor2d.config.json

    global_plugins_dir = os.path.join(pathlib.Path.home(), ".phasereditor2d", 'plugins')
    if os.path.isdir(global_plugins_dir):
        extra_plugins_dir.append(global_plugins_dir)

    conf = Settings(
        project=pathlib.Path(args.project),
        max_number_files=args.max_number_files,
        disable_colors=args.disable_colors,
        editor=args.editor,
        extra_plugins_dir=extra_plugins_dir,
        extra_plugins=[],
        skip_dir=[],
        disable_gzip=disable_gzip,
        dev=dev,
        pub=public,
        filter_rules=default_skip,
    )

    load_project_config(conf)

    app = create_app(conf)

    watch_task: Optional[Task] = None


    @app.on_event('startup')
    def init_watch():
        global watch_task

        loop = asyncio.get_event_loop()
        loop.set_exception_handler(custom_exception_handler)
        watch_task = loop.create_task(watch_changes(settings))

        print_welcome(conf, port)

        if not args.disable_open_browser:
            webbrowser.open_new_tab(f'http://localhost:{port}/editor')


    @app.on_event('shutdown')
    def exit_watch():
        global watch_task

        print("exiting...")
        if watch_task:
            watch_task.cancel()


    # asyncio.create_task(watch_changes(settings.project))

    uvicorn.run(
        app,
        port=port,
        host='0.0.0.0' if public else 'localhost',
        log_config=None
    )

    # uvicorn.run('main:create_app', port=3355, reload=True)

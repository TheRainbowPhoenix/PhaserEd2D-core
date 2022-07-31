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
from typing import Union, Dict, List, Awaitable, Optional
import os
import pathlib
import hashlib
import asyncio
import webbrowser

import typing
from fastapi import FastAPI, Request, UploadFile, Form
# from fastapi.templating import Jinja2Templates
from starlette.datastructures import Headers
from starlette.responses import HTMLResponse, RedirectResponse, Response
from starlette.staticfiles import StaticFiles, PathLike

from pydantic import BaseModel, BaseSettings
from pydantic.typing import Literal
from starlette.types import Scope, Receive, Send
from watchfiles import awatch


class Settings(BaseSettings):
    project: pathlib.Path | None = None
    hash: str = ''
    max_number_files: int = 1000
    disable_colors: bool = False
    editor: pathlib.Path | None = None
    extra_plugins_dir: List[str] = []


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


def file_filtered(file) -> bool:
    """
    CHeck if file or folder is ignored
    :param file: file string name
    :return: boolean
    """
    # TODO: use gitignore and better patterns !
    return file.startswith('.')


def _list_files(start_path, counters: Dict[str, int]):
    """
    List all file to the JSON format expected
    :param start_path: string path
    :param counters: file and dir counters
    :return:
    """

    items = []
    for element in sorted(os.listdir(start_path)):
        if file_filtered(element):
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
            item["children"] = _list_files(path, counters)

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
    base["rootFile"]["children"] = _list_files(d, counter)
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

    if os.path.isfile(path):
        with open(path, 'w+', encoding='utf-8') as f:
            f.write(body.body.content)
    elif not os.path.isdir(path):
        with open(path, 'w+', encoding='utf-8') as f:
            f.write(body.body.content)

    if os.path.exists(path):
        return {
            "modTime": get_mod_time(path),
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
    all_dirs.append(plugin_dir)

    for directory in all_dirs:
        if os.path.isdir(directory):
            for plugin in glob.glob(os.path.join(directory, '*/plugin.json')):
                path = os.path.normpath(plugin)
                try:
                    with open(path, encoding='utf-8') as f:
                        data = json.load(f)
                        id = data["id"]
                        priority: int = data.get("priority", 0)
                        styles: list = data.get("styles", [])
                        scripts: list = data.get("scripts", [])

                        if id in plugins_map:
                            print(f"[i] Plugin already loaded : {id}")
                            continue

                        # Creating plugin struct
                        plugins_map[id] = {
                            'styles': styles,
                            'scripts': scripts
                        }

                        # Adding plugin to priority queue
                        if not priority in plugins_order:
                            plugins_order[priority] = []

                        plugins_order[priority].append(id)

                except Exception as e:
                    print(f"[!] Bad plugin : {path}")
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

    except Exception as e:
        # print(e)
        # Hack: Error from https://github.com/PyO3/pyo3/issues/2525
        pass
        # print(changes)


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

        for directory in settings.extra_plugins_dir:
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

    settings.project = conf.project
    settings.editor = conf.editor
    settings.disable_colors = conf.disable_colors
    settings.max_number_files = conf.max_number_files
    settings.extra_plugins_dir = conf.extra_plugins_dir

    if settings.editor != None:
        if os.path.isdir(settings.editor):
            plugin_dir = os.path.normpath(settings.editor)
        else:
            print(f"[!] Invalid folder provided to \"-editor\" argument : \"{settings.editor}\" does not exists.")
            sys.exit(1)
    else:
        plugin_dir = "editor/plugins"
        if not os.path.isdir(plugin_dir):
            print(
                "Can't locate \"editor\" folder or its \"plugins\" subdirectory. Please refer to https://github.com/TheRainbowPhoenix/PhaserEd2D-core/wiki/Using-the-bundle")
            sys.exit(1)

    plugins_order, plugins_map = discover_plugins(plugin_dir)

    # TODO: support for multiple sources plugins
    try:
        app.mount("/editor/app/plugins", MagicPluginsRoute(directory=plugin_dir), name="plugins")
    except:
        print(
            "Can't locate \"editor\" folder or its \"plugins\" subdirectory. Please refer to https://github.com/TheRainbowPhoenix/PhaserEd2D-core/wiki/Using-the-bundle")
        sys.exit(1)

    @app.get("/editor/", response_class=HTMLResponse)
    def get_editor(request: Request, plugins_order=plugins_order, plugins_map=plugins_map):

        body = f"""<!DOCTYPE html>\n<html lang="en">\n<head>\n
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="X-UA-Compatible" content="ie=edge">
    <title>Phaser Editor 2D</title>
"""
        styles = ""
        scripts = ""

        for _, ids in sorted(plugins_order.items()):
            for id in ids:
                if id in plugins_map:
                    styles += f"""\n	<!-- plugin:{safe(id)} -->\n"""
                    plugin = plugins_map[id]

                    for style in plugin.get("styles", []):
                        styles += f'	<link href="app/plugins/{safe(id)}/{safe(style)}?v={int(time.time())}" rel="stylesheet">\n'

                    scripts += f"""\n	<!-- plugin:{safe(id)} -->\n"""
                    for style in plugin.get("scripts", []):
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
        
    Phaser Editor  
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

    return app


def print_welcome(args):
    """
    Print "welcome" console message + user friendliness
    :param args:
    :return:
    """
    host = 'localhost'
    if args.public:
        host = "0.0.0.0"
        import socket
        try:
            host = socket.gethostbyname(socket.gethostname())
        except:
            pass

    if os.name == 'nt' and not args.disable_colors:
        from ctypes import windll
        STD_OUTPUT_HANDLE = -11
        stdout_handle = windll.kernel32.GetStdHandle(STD_OUTPUT_HANDLE)

        print("")
        print("PhaserEditor2D v0.0.1 server running from:")
        print("")
        windll.kernel32.SetConsoleTextAttribute(stdout_handle, 9)
        print(f" ▲ Project : {args.project}")
        print(f" ▲ Local   : http://{host}:{args.port}/editor")
        windll.kernel32.SetConsoleTextAttribute(stdout_handle, 15)
        print("")

    else:
        print(f"""
  PhaserEditor2D v0.0.1 server running from:

  > Project : {args.project}
  > Local   : http://{host}:{args.port}/editor
""")


if __name__ == '__main__':
    import uvicorn

    # TODO: Scanning user home flags "~/.phasereditor2d/flags.txt"
    # TODO: Reading project config  ==> phasereditor2d.config.json
    # Don't: Reading license file at resources\app\server\PhaserEditor2D.lic and ~\.phasereditor2d\PhaserEditor2D.lic
    # TODO: Program flags: [-port, 3355, -project, C:/Users/Phoebe/Downloads/test_phaser_sunny_land]
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
    parent_parser.add_argument('-editor', type=str, metavar='path', default='editor/plugins',
                               help='Path to the \'editor\' directory (default to current directory)')

    args = parent_parser.parse_args()

    extra_plugins_dir = []
    global_plugins_dir = os.path.join(pathlib.Path.home(), ".phasereditor2d", 'plugins')
    if os.path.isdir(global_plugins_dir):
        extra_plugins_dir.append(global_plugins_dir)

    conf = Settings(
        project=pathlib.Path(args.project),
        max_number_files=args.max_number_files,
        disable_colors=args.disable_colors,
        editor=args.editor,
        extra_plugins_dir=extra_plugins_dir
    )

    app = create_app(conf)

    watch_task: Optional[Task] = None


    @app.on_event('startup')
    def init_watch():
        global watch_task

        loop = asyncio.get_event_loop()
        loop.set_exception_handler(custom_exception_handler)
        watch_task = loop.create_task(watch_changes(settings))
        # print("hooked :D")

        print_welcome(args)

        if not args.disable_open_browser:
            webbrowser.open_new_tab(f'http://localhost:{args.port}/editor')


    @app.on_event('shutdown')
    def exit_watch():
        global watch_task

        print("exiting...")
        if watch_task:
            watch_task.cancel()


    # asyncio.create_task(watch_changes(settings.project))

    uvicorn.run(
        app,
        port=args.port or 3355,
        host='0.0.0.0' if args.public else 'localhost',
        log_config=None
    )

    # uvicorn.run('main:create_app', port=3355, reload=True)

"""
Phaser Ed 2D core server ptyhon single-file !

How cool is that ?
Need Pyton 3.10+, fastapi, jinja2 & uvicorn
"""
import argparse
import json
import re
import shutil
import sys
import time
import types
from collections import defaultdict
from typing import Union, Dict, List
import os
import pathlib
import hashlib
import asyncio

from fastapi import FastAPI, Request, UploadFile, Form
from fastapi.templating import Jinja2Templates
from starlette.background import BackgroundTasks
from starlette.responses import HTMLResponse
from starlette.staticfiles import StaticFiles

from pydantic import BaseModel, BaseSettings
from pydantic.typing import Literal
from watchfiles import awatch


class Settings(BaseSettings):
    project: pathlib.Path | None = None
    hash: str = ''


settings = Settings()


# API models here

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

# {"method":"MoveFiles","body":{"movingPaths":["test_phaser_sunny_land/test_folder/hello.txt"],"movingToPath":"test_phaser_sunny_land"}}
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
    base = {
        "rootFile": {
            "name": os.path.basename(d),
            "modTime": get_mod_time(d),
            "size": 4096,
            "children": []
        }, "maxNumberOfFiles": 0, "projectNumberOfFiles": 0, "hash": settings.hash }

    counter = {'file': 0, 'dir': 0}
    base["rootFile"]["children"] = _list_files(d, counter)
    base["projectNumberOfFiles"] = counter['file']
    base["maxNumberOfFiles"] = counter['file'] + counter['dir']

    return base


def get_file_content(path):
    if os.path.exists(path) and os.path.isfile(path):
        return "ok"
    else:
        return ""

# API responses

async def get_server_mode(body: GetServerMode):
    return {
        'desktop': True,
        'externalEditorName': "Visual Studio Code",
        'unlocked': True
    }


async def get_project_files_hash(body: GetProjectFilesHash):
    if settings.hash == '':
        data = get_mod_time(settings.project)
        settings.hash = hashlib.sha256(data.to_bytes(16, sys.byteorder)).hexdigest()[:32]

    return {
        'hash': settings.hash  # TODO: find this ??
    }


async def get_project_files(body: GetProjectFilesHash):
    # with open("sample_projectfiles.json") as f:
    #     obj = json.load(f)

    return get_files_list(settings.project)


async def get_new_version_available(body: GetNewVersionAvailable):
    return {'available': False}


async def open_file_manager(body: OpenFileManager):
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
    return re.sub('(?!^)([A-Z]+)', r'_\1', name).lower()

resp_map = {
    i.__name__: globals()[snekify(i.__name__)] for i in APIRequest.__subclasses__() if snekify(i.__name__) in globals()
}

async def watch_changes(settings: Settings):
    async for changes in awatch(settings.project):

        data = int(time.time() * 1_000_000)
        settings.hash = hashlib.sha256(data.to_bytes(16, sys.byteorder)).hexdigest()[:32]

        # print(changes)


def create_app(conf: Settings) -> FastAPI:
    app = FastAPI()

    settings.project = conf.project

    # Editor static files
    app.mount("/editor/app/plugins", StaticFiles(directory="editor/plugins", html=True), name="editor/plugins")

    # Editor HTML template
    templates = Jinja2Templates(directory="editor/static")

    @app.get("/editor/", response_class=HTMLResponse)
    def get_editor(request: Request):
        return templates.TemplateResponse("index.html", {"request": request})
        # return {"Hello": "World"}

    @app.get("/")
    def read_root():
        return "Just an api ! Go to /editor"

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
    # @app.api_route("/editor/project/{path_name:path}", methods=["GET"])
    # async def catch_all(request: Request, path_name: str):
    #     print(path_name)
    #     a = get_file_content(os.path.join(settings.project, path_name))
    #     return {"request_method": request.method, "path_name": path_name}

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


if __name__ == '__main__':
    import uvicorn

    # args : -disable-open-browser -port 3354 -project C:/Users/Me/Documents/test_phaser_sunny_land

    parent_parser = argparse.ArgumentParser(add_help=True)
    parent_parser.add_argument('-port', type=int, default=3355)
    parent_parser.add_argument('-project', type=str, metavar='path', required=True)

    args = parent_parser.parse_args()

    conf = Settings(
        project=pathlib.Path(args.project)
    )

    app = create_app(conf)


    @app.on_event('startup')
    def init_watch():
        loop = asyncio.get_event_loop()
        loop.create_task(watch_changes(settings))
        # print("hooked :D")

    # asyncio.create_task(watch_changes(settings.project))

    uvicorn.run(
        app,
        port=args.port or 3355
    )
    # uvicorn.run('main:create_app', port=3355, reload=True)

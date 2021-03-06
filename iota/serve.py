#
# (C) Copyright 2020 Tillmann Heidsieck
#
# SPDX-License-Identifier: MIT
#
# original source from
#  https://flask.palletsprojects.com/en/1.1.x/tutorial/
#
from flask import (
    Blueprint,
    current_app,
    json,
    request,
)
from flask_api import status

import base64
import nacl.secret
import nacl.utils
import os

from .deploy import vercmp

bp = Blueprint('serve', __name__, url_prefix='/api/v1')


@bp.route('/global_config')
def gconfig():
    version = request.headers.get("X-global-config-version")
    if not version:
        return {'global_config': 'no version given'}, \
            status.HTTP_404_NOT_FOUND

    key = request.headers.get("X-global-config-key")
    if not key:
        return {'global_config': 'no key supplied'}, \
            status.HTTP_403_FORBIDDEN

    key = base64.b64decode(key)
    if len(key) != 32:
        return {'global_config': 'invalid key'}, status.HTTP_403_FORBIDDEN

    ctext = None
    config_file = os.path.join(current_app.instance_path, "global_config.enc")
    try:
        with open(config_file, "rb") as f:
            ctext = f.read()
    except OSError:
        return {'global_config': 'invalid key'}, \
            status.HTTP_503_SERVICE_UNAVAILABLE

    box = nacl.secret.SecretBox(key)
    plaintext = box.decrypt(ctext)

    j = None
    try:
        j = json.loads(plaintext.decode("utf-8"))
    except json.JSONDecodeError:
        return {'global_config': 'failed to load'}, \
            status.HTTP_403_FORBIDDEN

    if int(version) >= int(j["global_config_version"]):
        return {'global_config': 'no version new version'}, \
            status.HTTP_404_NOT_FOUND

    return plaintext, status.HTTP_200_OK


@bp.route('/local_config')
def lconfig():
    version = request.headers.get("X-config-version")
    if not version:
        return {'local_config': 'no version given'}, \
            status.HTTP_404_NOT_FOUND

    chip_id = request.headers.get("X-chip-id")
    if not chip_id:
        return {'local_config': 'no CHIP ID given'}, \
            status.HTTP_404_NOT_FOUND

    local_conf = None
    config_file = os.path.join(current_app.instance_path,
                               "config.json.%s" % (chip_id))
    try:
        with open(config_file, "rb") as f:
            local_conf = f.read()
    except OSError:
        return {'local_config': 'config for chip id not found'},\
            status.HTTP_404_NOT_FOUND

    j = None
    try:
        j = json.loads(local_conf)
    except json.JSONDecodeError:
        return {'local_config': 'failed to load'},\
            status.HTTP_500_INTERNAL_SERVER_ERROR
    if int(version) >= int(j["config_version"]):
        return {'local_config': 'no version new version'},\
            status.HTTP_404_NOT_FOUND

    return local_conf, status.HTTP_200_OK


@bp.route('/firmware')
def firmware():
    version = request.headers.get("X-ESP8266-version")
    if not version:
        return {'firmware': 'no version given'}, status.HTTP_404_NOT_FOUND

    firmware_json = os.path.join(current_app.instance_path, "firmware.json")
    try:
        with open(firmware_json, "rb") as f:
            j = json.load(f)
    except OSError:
        return {}, status.HTTP_404_NOT_FOUND
    except json.JSONDecodeError:
        return {}, status.HTTP_404_NOT_FOUND

    if "version" in j.keys():
        server_version = j["version"]
    else:
        server_version = "0.0"

    if vercmp(version, server_version) <= 0:
        return {}, status.HTTP_304_NOT_MODIFIED

    try:
        ffile = j["file"]
    except ValueError:
        return {}, status.HTTP_404_NOT_FOUND

    if ffile[0] != "/":
        if not os.path.exists(os.path.join(current_app.instance_path, ffile)):
            return {'firmware': "not found"}, status.HTTP_404_NOT_FOUND
        else:
            ffile = os.path.join(current_app.instance_path, ffile)

    if ffile[0] == "/" and not os.path.exists(ffile):
        return {'firmware': "not found"}, status.HTTP_404_NOT_FOUND

    with open(ffile, "rb") as f:
        fw = f.read()

    return fw, status.HTTP_200_OK

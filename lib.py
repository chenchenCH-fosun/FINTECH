# -*- coding: utf-8 -*-

import os
import logging
import subprocess


def init_log(f):
    log = None

    def init():
        nonlocal log
        if log is not None:
            return log
        log = logging.getLogger(__file__)
        log.setLevel(logging.DEBUG)
        handler = logging.FileHandler(filename=f)
        handler.setFormatter(logging.Formatter('%(name)s - %(levelname)s - %(asctime)s - %(message)s'))
        log.addHandler(handler)
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(name)s - %(levelname)s - %(asctime)s - %(message)s'))
        log.addHandler(handler)
        return log

    return init()


def handle_headers(headers: str):
    if isinstance(headers, dict):
        return headers
    h = filter(None, headers.split("\n"))
    h = [i.split(":", maxsplit=1) for i in h]
    return dict((k, v.strip()) for k, v in h)


def get_duration(file):
    """Get the duration of a video using ffprobe."""
    import sys
    # sys.path.append("C:\\Program Files\\ffmpeg\\bin")
    cmd = 'ffprobe -i {} -show_entries format=duration -v quiet -of csv="p=0"'.format(file)
    output = subprocess.check_output(
        cmd,
        shell=True,
        stderr=subprocess.STDOUT
    )
    output = float(output or 0)
    return round(output)


class FatalBox(Exception):
    pass


def shutdown_computer():
    import os
    os.system("shutdown -s")


def goto(f):
    return os.path.join(os.path.abspath(os.path.dirname(__file__)), f)


def in_ide():
    try:
        from ctypes import windll
        hwnd = windll.user32.GetForegroundWindow()
        out = windll.kernel32.GetStdHandle(-0xb)  # stdin: 0xa, stdout: 0xb, stderr: 0xc
        rtn = windll.kernel32.SetConsoleTextAttribute(out, 0x7)
        return not rtn
    except Exception:
        return False

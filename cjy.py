# -*- coding: utf-8 -*-

import os
import logging
import requests
import time
import datetime

from hashlib import md5
from PIL import Image
from io import BytesIO


class Chaojiying_Client(object):

    def __init__(self, username, password, soft_id):
        self.username = username
        password = password.encode('utf8')
        self.password = md5(password).hexdigest()
        self.soft_id = soft_id
        self.base_params = {
            'user': self.username,
            'pass2': self.password,
            'softid': self.soft_id,
        }
        self.headers = {
            'Connection': 'Keep-Alive',
            'User-Agent': 'Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 5.1; Trident/4.0)',
        }

    def PostPic(self, im, codetype):
        """
        im: 图片字节
        codetype: 题目类型 参考 http://www.chaojiying.com/price.html
        """
        params = {
            'codetype': codetype,
        }
        params.update(self.base_params)
        files = {'userfile': ('ccc.jpg', im)}
        r = requests.post('http://upload.chaojiying.net/Upload/Processing.php', data=params, files=files,
                          headers=self.headers)
        return r.json()

    def ReportError(self, im_id):
        """
        im_id:报错题目的图片ID
        """
        params = {
            'id': im_id,
        }
        params.update(self.base_params)
        r = requests.post('http://upload.chaojiying.net/Upload/ReportError.php', data=params, headers=self.headers)
        return r.json()


def get_v(f, save=False):
    n = "qwe0000"
    p = "a8948258"
    chaojiying = Chaojiying_Client(n, p, '893202')
    if isinstance(f, str) and os.path.isfile(f):
        im = open(f, 'rb').read()
    else:
        im = f
    v = chaojiying.PostPic(im, 1902)
    print(v)
    # {'err_no': 0,
    #  'err_str': 'OK',
    #  'pic_id': '9115617470784500001',
    #  'pic_str': 'dzl7',
    #  'md5': '23a0f6293ec811451601702d81508e16'}
    s = v.get("pic_str")
    if v.get("err_no") or not s:
        logging.info(v)
        if save:
            try:
                Image.open(BytesIO(im)).save(f"{save}/yzm/%s.jpg" % datetime.datetime.now().strftime("%Y%m%d%H%M%S"))
            except:
                logging.info("保存失败")
                pass
        raise Exception("识别失败1")
    if save:
        try:
            Image.open(BytesIO(im)).save(f"{save}/yzm/%s_%s.jpg" % (datetime.datetime.now().strftime("%Y%m%d%H%M%S"), s))
        except:
            logging.info("保存失败2")
            pass
    return s

# -*- coding: utf-8 -*-

import os
import re
import ast
import time
import random
import urllib.request
import requests

from lib import init_log, handle_headers, FatalBox, goto

# 设置日志文件为同目录的dl.log
log = init_log(goto("dl.log"))
here = goto("")
# 设置工作目录
os.chdir(here)

# 发送请求时，headers假装自己是浏览器
headers = """
User-Agent: Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.108 Safari/537.36"""

# 不下载含有以下字眼的文件
exclude_words = (
    "行驶",
    ".+?险",
    "钥匙",
    "保单",
    "交强",
    "商业",
    "受益人",

    "车证",
    "交保",
    "批单",
    "身份",
    "保交",
    "保商",
    "运输",
    "营运"    
)
# 如果“附件查看”按钮显示的所有文件中都不包含该字眼，则去发票附件处寻找
# 如果某个文件含有该字眼，则认为发票一定被下载了，不再去发票附件处寻找批单
bill_word = "发票"


class ContractDownloader():

    def __init__(self, cookie, headers, interval_each_c=(2, 3), interval_each_dl=(0.5, 1)):
        # 浏览器cookie, header， 每个合同处理间隔时间， 同一个合同的每个文件下载间隔, 合同储存方法
        self.headers = handle_headers(headers)
        self.headers.update({"cookie": cookie})
        self.interval_each_c = interval_each_c
        self.interval_each_dl = interval_each_dl
        self.downloaded = []

    def search_contract(self, contract_no):
        """ 根据合同号查询 """

        if not contract_no:
            raise FatalBox

        self.save_contract_attachment(contract_no, None, None)

        # 发起请求，根据合同号查询合同的item_detail_id
        url = "https://ls.cf-finance.com/hlsprod/autocrud/ast.AST301.con_contract_item_v/query?pagesize=10&pagenum=1&_fetchall=false&_autocount=true"
        headers = self.headers
        r = requests.post(url, headers=headers,
                          data={'_request_data': '{"parameter":{"contract_number":"%s"}}' % contract_no})
        res = r.json()

        # 判断查询结果是否正常
        if res["success"] is not True:
            log.warning("查询订单号出错： %s" % contract_no)
            raise FatalBox
        if not isinstance(res["result"]["record"], dict):
            log.warning("查询订单号出错： %s" % contract_no)
            raise FatalBox

        c = res["result"]["record"]
        if c.get("contract_number") == contract_no:
            if not c.get("item_detail_id"):
                log.warning("合同缺少item_detail_id")
                return

            # 查询成功， 返回该合同数据， 是个dict
            return c

        # 程序如果走到这里说明没查到
        log.warning("没查询到相关合同： %s, res: %s" % (contract_no, res))

    def download_contract_attachments(self, contract_no, contract):
        """ 根据item_detail_id下载对应文件 """

        # 从合同数据中取出item_detail_id
        item_detail_id = contract.get("item_detail_id")

        # 发起请求，根据item_detail_id查询合同的所有文件，相当于“附件查看”按钮功能
        url = "https://ls.cf-finance.com/hlsprod/downloadFile.screen"
        r = requests.get(url, params={"table_name": "CON_CONTRACT_ITEM_DETAIL",
                                      "header_id": item_detail_id,
                                      "_dc": int(time.time() * 1000)}, headers=self.headers)
        # todo: 确认只有一个附件时的正则格式
        res = re.search("datas[\"']:.*?(\[\[.+?\]\]),", r.text, re.DOTALL)
        bill_done = False
        if res is None:
            log.warning("合同无相关文件： %s" % contract_no)
        else:
            attachments = res.group(1)
            attachments = ast.literal_eval(attachments)
            # 循环下载符合条件的所有文件
            for att in attachments:
                _, att_id, _, _, _, _, _, _, name, _ = att

                # 文件名包含排除词则不下载该文件
                skip = False
                for word in exclude_words:
                    if word in name or re.search(word, name):
                        skip = True
                if skip:
                    continue

                # 加入包含bill_word或者有叫合同号的文件，就认为发票文件有了
                if bill_word in name or ("%s." % contract_no) in name:
                    bill_done = True
                log.info("下载：%s" % name)
                dl_url = "https://ls.cf-finance.com/hlsprod/atm_download.svc?attachment_id={}&table_name=CON_CONTRACT_ITEM_DETAIL&table_pk_value={}".format(
                    att_id, item_detail_id)

                self.save_contract_attachment(contract_no, dl_url, filename=name)
                self.downloaded.append(name)

                # 随机等待xx秒下载同一个合同的不同文件， 通过interval_each_dl，调整等待时间
                time.sleep(random.uniform(*self.interval_each_dl))

        # 发票文件好像没有，再去发票附件处下载
        if not bill_done:
            car_license = None
            try:
                car_license = self.search_car_license(contract_no, item_detail_id)
            except Exception:
                log.exception("发票下载异常")
            if not car_license:
                log.warning("发票好像下载失败")
            else:
                self.download_bill(contract_no, car_license["ast_car_license_id"])
        return

    def search_car_license(self, contract_no, item_detail_id):
        """ 查询车辆牌照信息数据 ，因为下载发票附件处要用到"""

        if not item_detail_id:
            raise FatalBox

        # 同上，又是请求
        url = "https://ls.cf-finance.com/hlsprod/autocrud/ast.AST301.ast_car_license/query?pagesize=10&pagenum=1&_fetchall=false&_autocount=true"
        headers = self.headers
        r = requests.post(url, headers=headers,
                          data={'_request_data': '{"parameter":{"item_detail_id":"%s"}}' % item_detail_id})
        res = r.json()

        # 判断请求结果是否正常
        if res["success"] is not True:
            log.warning("查询牌照出错： %s" % contract_no)
            raise FatalBox
        if "record" not in res["result"] or not isinstance(res["result"]["record"], dict):
            log.warning("查询牌照出错： %s" % contract_no)
            raise FatalBox
        c = res["result"]["record"]
        if str(c.get("item_detail_id")) == str(item_detail_id):
            if not c.get("ast_car_license_id"):
                log.warning("缺少ast_car_license_id")
                return
            # 走到这里说明数据正确， 直接返回数据
            return c

        # 程序如果走到这里说明没查到
        log.warning("没查询到相关牌照： %s, res: %s" % (contract_no, res))

    def download_bill(self, contract_no, ast_car_license_id):
        """ 尝试下载发票，相当于 发票附件-附件 """

        # 发请求，相当于点击附件按钮，看看里面有没有发票文件
        bill_url = "https://ls.cf-finance.com/hlsprod/uploadFile.screen"
        r = requests.get(bill_url, params={"table_name": "AST_CAR_LICENSE",
                                           "header_id": ast_car_license_id,
                                           "_dc": int(time.time() * 1000)}, headers=self.headers)
        # todo: 确认只有一个附件时的正则格式
        res = re.search("datas[\"']:.*?(\[\[.+?\]\]),", r.text, re.DOTALL)
        if res is None:
            log.warning("发票按钮处无相关文件： %s" % contract_no)
            return
        attachments = res.group(1)
        attachments = ast.literal_eval(attachments)

        # 下载第1个文件
        for att in attachments[:1]:
            _, att_id, _, _, _, _, _, _, name, _ = att
            log.info("下载：%s" % name)
            dl_url = "https://ls.cf-finance.com/hlsprod/atm_download.svc?attachment_id={}&table_name=AST_CAR_LICENSE&table_pk_value={}".format(
                att_id, ast_car_license_id)
            self.save_contract_attachment(contract_no, dl_url, filename=name)
            self.downloaded.append(name)

    def get_contract_nos(self):
        # 打开contracts.txt文件，读取所有合同号
        with open("./contracts.txt", "r") as f:
            return map(lambda x: x.strip(), filter(None, f.read().split("\n")))

    def run(self):
        # 入口方法

        # get_contract_nos方法从contracts.txt中得到所有的合同号
        # for循环处理每一个合同
        for i, contract_no in enumerate(self.get_contract_nos()):
            log.info("处理合同： %s" % contract_no)
            # 初始化
            self.downloaded = []
            contract = None
            try:
                # 尝试查询合同号
                contract = self.search_contract(contract_no)
                if contract is None:
                    raise FatalBox
            except FatalBox:
                log.warning("查询出错：%s" % contract_no)
            except Exception as ex:
                log.warning("新的致命错误，请处理：%s" % contract_no)
                raise ex

            # 没查到该合同号
            if contract is None:
                log.warning("查询出错2：%s" % contract_no)
            else:
                try:
                    self.download_contract_attachments(contract_no, contract)
                except FatalBox:
                    log.exception("下载出错：%s" % contract_no)
                except Exception as ex:
                    log.warning("新的致命错误2，请处理：%s" % contract_no)
                    raise ex
            log.info("处理结束\n")

            # 记录该合同文件下载情况
            self.stat("\n%s: %s, %s" % (contract_no, len(self.downloaded), ", ".join(sorted(self.downloaded))), i==0)

            # 随机等待xx秒下载下一个合同的相关文件， 通过interval_each_c，调整等待时间
            time.sleep(random.uniform(*self.interval_each_c))

    def stat(self, line, tag=False):
        """往stat里面写数据"""

        with open("./stat.txt", "a+",encoding='gbk') as f:
            if tag:
                f.write("\n" * 3 + "又一次运行的起点".center(100, "-"))
            f.write(line)

    def save_contract_attachment(self, contract_no, url, filename, contracts_dir=here + "/contracts"):
        """ 保存文件到电脑 """

        if not contract_no:
            log.warning("合同号为空，无法保存")
            raise FatalBox
        dirname = contract_no
        dirpath = contracts_dir.rstrip("/") + "/" + dirname
        if not os.path.isdir(dirpath):
            os.mkdir(dirpath)
        if url and filename:
            urllib.request.urlretrieve(url, "%s/%s" % (dirpath, filename))


if __name__ == "__main__":
    with open(here + "/cookies", "rb") as f:
        cookies = f.read()
        ContractDownloader(cookies,
                           headers=headers,
                           interval_each_c=(0.3, 0.5),  # 随机等待0.3~0.5秒下载下一个合同的相关文件
                           interval_each_dl=(0.1, 0.3),  # 随机等待0.2~0.4秒下载同一个合同的不同文件
                           ).run()

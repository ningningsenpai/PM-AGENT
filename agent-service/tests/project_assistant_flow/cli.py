"""调试脚本的中文命令行帮助与参数错误。"""

import argparse


class ChineseArgumentParser(argparse.ArgumentParser):
    def __init__(self, **kwargs):
        super().__init__(add_help=False, **kwargs)
        self._positionals.title = "位置参数"
        self._optionals.title = "可选参数"
        self.add_argument("-h", "--help", action="help", help="显示帮助并退出")

    def format_help(self):
        return super().format_help().replace("usage:", "用法:", 1)

    def error(self, _message):
        raise ValueError("命令行参数无效，请使用 --help 查看帮助")

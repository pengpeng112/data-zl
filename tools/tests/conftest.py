# no-op conftest（185 号 R1）。
#
# 本目录是 tools/ 下四个检查器的纯逻辑单测目录，不属于 backend/tests 子树，
# backend/tests/conftest.py 的数据库门禁与 autouse 清库 fixture 天然不适用。
# 此文件按 185 §3 R1 要求留档：显式声明纯逻辑目录语义，防止后续有人把根级
# pytest 配置挪到仓库根时 autouse 清库误伤本目录。

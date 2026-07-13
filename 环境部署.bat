chcp 65001
@echo off
cd /d "%~dp0"
echo "安装python库"
d:\Uniqlo\python\python.exe -m pip install -r d:/Uniqlo/requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
@REM echo "安装浏览器驱动"
@REM d:\Uniqlo\python\python.exe -m playwright install
pause
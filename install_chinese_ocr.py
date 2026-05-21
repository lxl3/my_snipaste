#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
自动安装 Tesseract 中文语言包
"""

import os
import sys
import urllib.request
import shutil
import pytesseract

def find_tessdata_dir():
    """查找 Tesseract tessdata 目录"""
    try:
        # 方法1: 使用 where/which 命令查找
        import subprocess
        try:
            if os.name == 'nt':  # Windows
                result = subprocess.run(['where', 'tesseract'], capture_output=True, text=True)
            else:
                result = subprocess.run(['which', 'tesseract'], capture_output=True, text=True)

            if result.returncode == 0:
                tesseract_path = result.stdout.strip().split('\n')[0]
                tesseract_dir = os.path.dirname(tesseract_path)
                tessdata_dir = os.path.join(tesseract_dir, 'tessdata')
                if os.path.exists(tessdata_dir):
                    return tessdata_dir
        except:
            pass

        # 方法2: 从配置获取
        tesseract_cmd = pytesseract.pytesseract.tesseract_cmd
        if isinstance(tesseract_cmd, str) and tesseract_cmd != 'tesseract':
            tesseract_dir = os.path.dirname(tesseract_cmd)
            tessdata_dir = os.path.join(tesseract_dir, 'tessdata')
            if os.path.exists(tessdata_dir):
                return tessdata_dir

        # 方法3: 尝试常见路径
        common_paths = [
            r"C:\Program Files\Tesseract-OCR\tessdata",
            r"C:\Program Files (x86)\Tesseract-OCR\tessdata",
            r"D:\tool\ocr_tool\tessdata",
            os.path.expanduser("~/AppData/Local/Tesseract-OCR/tessdata"),
        ]

        for path in common_paths:
            if os.path.exists(path):
                return path

        return None
    except:
        return None

def download_language_pack(lang_code, output_path):
    """下载语言包"""
    url = f"https://github.com/tesseract-ocr/tessdata/raw/main/{lang_code}.traineddata"

    print(f"正在下载 {lang_code} 语言包...")
    print(f"URL: {url}")

    try:
        # 下载文件
        with urllib.request.urlopen(url) as response:
            total_size = int(response.headers.get('content-length', 0))
            print(f"文件大小: {total_size / 1024 / 1024:.2f} MB")

            with open(output_path, 'wb') as out_file:
                downloaded = 0
                chunk_size = 8192
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    out_file.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        print(f"\r下载进度: {percent:.1f}%", end='', flush=True)

        print("\n下载完成!")
        return True
    except Exception as e:
        print(f"\n下载失败: {e}")
        return False

def main():
    print("=" * 60)
    print("Tesseract 中文语言包自动安装")
    print("=" * 60)

    # 1. 检查 Tesseract 是否已安装
    try:
        version = pytesseract.get_tesseract_version()
        print(f"\n[OK] Tesseract v{version} 已安装")
    except:
        print("\n[ERROR] Tesseract 未安装或未添加到 PATH")
        print("请先安装 Tesseract: https://github.com/UB-Mannheim/tesseract/wiki")
        return 1

    # 2. 检查是否已有中文语言包
    try:
        langs = pytesseract.get_languages()
        if 'chi_sim' in langs:
            print("[OK] 中文语言包已安装，无需重复安装")
            return 0
    except:
        pass

    # 3. 查找 tessdata 目录
    tessdata_dir = find_tessdata_dir()
    if not tessdata_dir:
        print("\n[ERROR] 未找到 tessdata 目录")
        print("请手动指定 Tesseract 安装路径")
        return 1

    print(f"\n找到 tessdata 目录: {tessdata_dir}")

    # 4. 检查写入权限
    test_file = os.path.join(tessdata_dir, '.test_write')
    try:
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
    except:
        print("\n[WARNING] 没有写入权限，需要管理员权限")
        print("请以管理员身份运行此脚本:")
        print("  右键 -> 以管理员身份运行")
        return 1

    # 5. 下载中文语言包到临时目录
    temp_file = os.path.join(os.path.dirname(__file__), 'chi_sim.traineddata')
    target_file = os.path.join(tessdata_dir, 'chi_sim.traineddata')

    if os.path.exists(target_file):
        print(f"\n[OK] 语言包已存在: {target_file}")
        return 0

    print(f"\n开始下载...")
    if not download_language_pack('chi_sim', temp_file):
        return 1

    # 6. 移动到 tessdata 目录
    print(f"\n正在安装到: {target_file}")
    try:
        shutil.move(temp_file, target_file)
        print("[OK] 安装成功!")
    except Exception as e:
        print(f"[ERROR] 安装失败: {e}")
        if os.path.exists(temp_file):
            print(f"\n语言包已下载到: {temp_file}")
            print(f"请手动复制到: {target_file}")
        return 1

    # 7. 验证安装
    try:
        langs = pytesseract.get_languages()
        if 'chi_sim' in langs:
            print("\n[OK] 中文语言包安装成功!")
            print("现在可以使用中文 OCR 功能了")
            return 0
        else:
            print("\n[WARNING] 安装后未检测到语言包，请重启程序")
            return 0
    except Exception as e:
        print(f"\n[WARNING] 验证时出错: {e}")
        print("请重启程序后再试")
        return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n用户取消")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] 未预期的错误: {e}")
        sys.exit(1)

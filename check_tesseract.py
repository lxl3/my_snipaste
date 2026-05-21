#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Tesseract OCR 语言包检查工具
"""

import sys
import pytesseract

def main():
    print("=" * 60)
    print("Tesseract OCR 语言包检查")
    print("=" * 60)

    try:
        # 检查 Tesseract 版本
        version = pytesseract.get_tesseract_version()
        print(f"\n[OK] Tesseract 已安装: v{version}")
    except Exception as e:
        print(f"\n[ERROR] Tesseract 未安装或未添加到 PATH")
        print(f"  错误: {e}")
        print("\n请安装 Tesseract:")
        print("  Windows: https://github.com/UB-Mannheim/tesseract/wiki")
        print("  安装时请勾选 'Additional Language Data' 选项")
        return 1

    try:
        # 检查可用语言
        langs = pytesseract.get_languages()
        print(f"\n可用语言包 ({len(langs)} 个):")
        print(f"  {', '.join(langs)}")

        # 检查关键语言
        required_langs = ['eng', 'chi_sim']
        missing_langs = []

        print("\n关键语言包检查:")
        for lang in required_langs:
            if lang in langs:
                print(f"  [OK] {lang}")
            else:
                print(f"  [X] {lang} (缺失)")
                missing_langs.append(lang)

        if missing_langs:
            print("\n需要安装的语言包:")
            for lang in missing_langs:
                if lang == 'chi_sim':
                    print(f"\n  {lang} (简体中文):")
                    print(f"    下载: https://github.com/tesseract-ocr/tessdata/raw/main/chi_sim.traineddata")
                    print(f"    放到: <Tesseract安装目录>\\tessdata\\")
                    print(f"    例如: C:\\Program Files\\Tesseract-OCR\\tessdata\\chi_sim.traineddata")
                elif lang == 'eng':
                    print(f"\n  {lang} (英文):")
                    print(f"    下载: https://github.com/tesseract-ocr/tessdata/raw/main/eng.traineddata")

            print("\n安装完成后，重启程序即可使用中文 OCR。")
            return 1
        else:
            print("\n[OK] 所有必需的语言包都已安装")
            print("  可以正常使用中英文 OCR 功能")
            return 0

    except Exception as e:
        print(f"\n[X] 检查语言包时出错: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

import sys
import os
import shutil
from cx_Freeze import setup, Executable

def build_main_program():
	base = None
	if sys.platform == 'win32':
		base = "Win32GUI"

	build_exe_options = dict(
		build_exe="server",
		optimize=1,
		excludes = ["tkinter", "_distutils_hack", "Cryptodome", "curses", "lib2to3", "msilib", "PIL", "pydoc_data", "xmlrpc", "test"],
		includes=[],
		include_files = [
			"auto",
			"logs",
			"models"
		],
		include_msvcr=True,
		zip_include_packages=["*"],
		zip_exclude_packages = ["sacremoses"], # Asegúrate de que esta opción esté presente y esté con las librerías que deseas no incluir en el zip
	)

	executables = [
		Executable('TranslateOfflineSRV.py', base=base, target_name="TranslateOfflineSRV")
	]

	setup(
		name="TranslateOfflineSRV",
		version="1.0.0.0",
		description="",
		options = {"build_exe": build_exe_options},
		executables=executables
	)

if __name__ == "__main__":
	build_main_program()


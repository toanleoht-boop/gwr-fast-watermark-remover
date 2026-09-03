# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files
import imageio_ffmpeg
import os

ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
datas = collect_data_files('qdarktheme')
binaries = [(ffmpeg_path, 'imageio_ffmpeg/binaries')]

a = Analysis(
    ['main.py'], pathex=[], binaries=binaries, datas=datas,
    hiddenimports=['imageio_ffmpeg'], hookspath=[], hooksconfig={},
    runtime_hooks=[], excludes=['torch', 'simple_lama_inpainting', 'PIL'],
    noarchive=False, optimize=1,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name='GWR Fast Watermark Remover',
    debug=False, bootloader_ignore_signals=False, strip=False, upx=True,
    console=False, disable_windowed_traceback=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=True,
               upx_exclude=[], name='GWR-Fast-Watermark-Remover')

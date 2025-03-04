# -*- coding: utf-8 -*-
"""
py2app/py2exe build script for Crystal Web Archiver.

Usage (All Platforms):
    python setup.py

Usage (Mac OS X):
    python setup.py py2app
Usage (Windows):
    python setup.py py2exe

Windows users may need to copy 'MSVCP90.dll' to C:\WINDOWS\system32 if the
following error is encountered:
    error: MSVCP90.dll: No such file or directory
See the tutorial for py2exe for more information about this DLL.
"""

from setuptools import setup
import sys

with open('./setup_settings.py', 'r') as f:
    exec(f.read())

if sys.platform == 'darwin':
    # If run without args, build application
    if len(sys.argv) == 1:
        sys.argv.append("py2app")
        
    # Ensure 'py2app' package installed
    try:
        import py2app
    except ImportError:
        exit(
            'This script requires py2app to be installed. ' + 
            'Download it from http://undefined.org/python/py2app.html')
    
    PLIST = {
        'CFBundleDocumentTypes': [
            # Associate application with .crystalproj files
            {
                'CFBundleTypeExtensions': ['crystalproj'],
                'CFBundleTypeIconFile': 'DocIconMac.icns',
                'CFBundleTypeName': 'Crystal Project',
                'CFBundleTypeRole': 'Editor',
                'LSTypeIsPackage': True,
            },
        ],
        'CFBundleIdentifier': 'net.dafoster.crystal',
        'CFBundleShortVersionString': VERSION_STRING,
        'CFBundleSignature': 'CrWA',
        'CFBundleVersion': VERSION_STRING,
        'NSHumanReadableCopyright': COPYRIGHT_STRING,
    }

    extra_setup_options = dict(
        setup_requires=['py2app'],
        app=['../src/main.py'],
        data_files=['media/DocIconMac.icns'],
        options={'py2app': {
            # Cannot use argv_emulation=True in latest version of py2app
            # because of: https://github.com/ronaldoussoren/py2app/issues/340
            'argv_emulation': False,
            'iconfile': 'media/AppIconMac.icns',
            'plist': PLIST,
        }},
    )
elif sys.platform == 'win32':
    # If run without args, build executables in quiet mode
    if len(sys.argv) == 1:
        sys.argv.append("py2app")
        sys.argv.append("-q")
    
    # Ensure 'py2exe' package installed
    try:
        import py2exe
    except ImportError:
        exit(
            'This script requires py2exe to be installed. ' + 
            'Download it from http://www.py2exe.org/')
    
    # py2exe doesn't look for modules in the directory of the main
    # source file by default, so we must add it to the system path explicitly.
    sys.path.append('..\src')
    
    extra_setup_options = dict(
        setup_requires=['py2exe'],
        windows=[{
            'script': '..\src\main.py',
            'icon_resources': [(0, 'media/AppIconWin.ico')],
            # Executable name
            'dest_base': APP_NAME,
        }],
        # Combine 'library.zip' into the generated exe
        zipfile=None,
        options={'py2exe': {
            'ignores': [
                # Mac junk
                'Carbon', 'Carbon.Files',
                # Windows junk
                'win32api', 'win32con', 'win32pipe',
                # Other junk
                '_scproxy', 'chardet', 'cjkcodecs.aliases', 'iconv_codec',
            ],
            # Would love to use mode '1' to put everything into a single exe,
            # but it breaks wxPython's default tree node icons. Don't know why.
            'bundle_files': 3,
            # Enable compression.
            # Most effective when all files bundled in a single exe (18 MB -> 8 MB).
            'compressed': True,
        }},
    )
else:
    exit('This build script can only run on Mac OS X and Windows.')

setup(
    name=APP_NAME,
    **extra_setup_options
)

# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

BASE_DIR = Path.cwd()

datas = [
    (str(BASE_DIR / 'templates'), 'templates'),
    (str(BASE_DIR / 'static'), 'static'),
    (str(BASE_DIR / 'db.sqlite3'), '.'),
]

# Explicit hidden imports for all local app modules and migrations
hiddenimports = [
    # Accounts
    'accounts',
    'accounts.admin',
    'accounts.apps',
    'accounts.middleware',
    'accounts.models',
    'accounts.views',
    'accounts.migrations',
    'accounts.migrations.0001_initial',

    # Records
    'records',
    'records.admin',
    'records.apps',
    'records.models',
    'records.services',
    'records.views',
    'records.management',
    'records.management.commands',
    'records.management.commands.seed_data',
    'records.migrations',
    'records.migrations.0001_initial',
    'records.migrations.0002_encryptedpackage_original_filename',

    # Consent
    'consent',
    'consent.admin',
    'consent.apps',
    'consent.models',
    'consent.views',
    'consent.migrations',
    'consent.migrations.0001_initial',

    # Audit
    'audit',
    'audit.admin',
    'audit.apps',
    'audit.models',
    'audit.views',
    'audit.migrations',
    'audit.migrations.0001_initial',

    # Blockchain
    'blockchain',
    'blockchain.admin',
    'blockchain.apps',
    'blockchain.models',
    'blockchain.services',
    'blockchain.views',
    'blockchain.migrations',

    # Core project
    'ehr_portal',
    'ehr_portal.settings',
    'ehr_portal.urls',
    'ehr_portal.wsgi',

    # Django internal dependencies
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sessions.middleware',
    'django.contrib.messages',
    'django.contrib.messages.middleware',
    'django.contrib.staticfiles',
    'django.contrib.staticfiles.handlers',
    'django.middleware.security',
    'django.middleware.common',
    'django.middleware.csrf',
    'django.contrib.auth.middleware',
    'django.db.backends.sqlite3',
    'django.db.backends.sqlite3.base',
    'django.db.backends.sqlite3.client',
    'django.db.backends.sqlite3.creation',
    'django.db.backends.sqlite3.features',
    'django.db.backends.sqlite3.introspection',
    'django.db.backends.sqlite3.operations',
    'django.db.backends.sqlite3.schema',

    # Cryptography & Algorand
    'cryptography',
    'cryptography.hazmat.primitives.ciphers.aead',
    'cryptography.hazmat.primitives.ciphers.aead.AESGCM',
    'algosdk',
    'algosdk.v2client',
    'algosdk.v2client.algod',
    'algosdk.v2client.indexer',
    'algosdk.account',
    'algosdk.mnemonic',
    'algosdk.encoding',
    'algosdk.transaction',

    # PyWebView & GUI
    'webview',
    'webview.platforms.winforms',
    'webview.platforms.edgechromium',
    'clr',
    'clr_loader',
    'pythonnet',

    # WSGI Server
    'wsgiref',
    'wsgiref.simple_server',
    'socketserver',
]

hiddenimports += collect_submodules('algosdk')
hiddenimports += collect_submodules('webview')

a = Analysis(
    ['desktop_app.py'],
    pathex=[str(BASE_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'scipy', 'pandas'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AegisEHR',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AegisEHR',
)

# PyInstaller spec for the knowledge-base backend API server.
# Build from project root: pyinstaller backend/backend.spec
# Output: dist/backend.exe (Windows) or dist/backend (Unix). Place next to the EXE:
#   backend/pdffigures2/pdffigures2.jar
#   backend/jdk-17.0.18+8-jre/
# Bundles numpy/faiss DLLs (and Anaconda MKL when present) so the EXE runs on machines without Anaconda.

import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_dynamic_libs, collect_data_files

block_cipher = None

backend_dir = os.path.join(os.getcwd(), 'backend')

# Collect numpy and faiss shared libs so the EXE runs without Anaconda.
binaries = list(collect_dynamic_libs('numpy'))
try:
    binaries += collect_dynamic_libs('faiss')
except Exception:
    pass

# When building under Anaconda on Windows, MKL DLLs are in Library/bin; bundle them so users don't need Anaconda.
if sys.platform.startswith('win'):
    conda_lib_bin = Path(sys.prefix) / 'Library' / 'bin'
    if conda_lib_bin.exists():
        for pattern in ('mkl_*.dll', 'libiomp*.dll'):
            for p in conda_lib_bin.glob(pattern):
                binaries.append((str(p), '.'))

# Bundle tiktoken's model/encoding data so DEFAULT_ENCODING = "cl100k_base"
# works correctly in frozen mode.
tiktoken_datas = collect_data_files('tiktoken')

a = Analysis(
    [os.path.join(backend_dir, 'run_backend_frozen.py')],
    pathex=[backend_dir],
    binaries=binaries,
    datas=[
        (os.path.join(backend_dir, 'step1_grobid', 'config.json'), 'step1_grobid'),
        (os.path.join(backend_dir, 'step4_embeddings', 'config.json'), 'step4_embeddings'),
        (os.path.join(backend_dir, 'step8_llm', 'config.json'), 'step8_llm'),
    ] + tiktoken_datas,
    hiddenimports=[
        'api_server',
        'pipeline_runner',
        'grobid_docker',
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'fastapi',
        'starlette',
        'pydantic',
        'numpy',
        'faiss',
        'step1_grobid.process_pdfs',
        'step1_grobid.postprocess_grobid_json',
        'step1_grobid.add_token_counts',
        'step1_grobid.add_paragraph_figure_refs',
        'step1_grobid.chunk_papers',
        'step2_figures.extract_figures',
        'step2_figures.crop_figures',
        'step3_link_figures.link_figures_to_chunks',
        'step4_embeddings.embedding_interface',
        'step4_embeddings.embed_chunks',
        'step4_embeddings.backends',
        'step4_embeddings.backends.zhipu_embedding3',
        'step5_faiss.faiss_storage',
        'step5_faiss.incremental_add',
        'step6_sqlite.sqlite_storage',
        'step7_query.query_pipeline',
        'step8_llm.llm_answer',
        'step8_llm.llm_interface',
        'step8_llm.backends',
        'step8_llm.backends.zhipu_llm',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

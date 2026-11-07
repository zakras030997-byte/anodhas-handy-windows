#!/usr/bin/env python3
"""Restore only pinned, public upstream assets; verify exact Git blob hashes."""
import argparse,hashlib,json,os,tempfile,urllib.request
from pathlib import Path,PurePosixPath

def git_sha(data):
    return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true',help='Verify local files without network or writes')
    args=parser.parse_args();root=Path(__file__).resolve().parent
    manifest=json.loads((root/'upstream-assets.json').read_text())
    commit='14f6f0d31cb22a4268acfbddba3052820fd0a06e'
    assert manifest['upstream_commit']==commit
    missing=[];restored=0
    for asset in manifest['assets']:
        rel=PurePosixPath(asset['path'])
        assert not rel.is_absolute() and '..' not in rel.parts
        p=root.joinpath(*rel.parts)
        assert p.resolve().is_relative_to(root) and not p.is_symlink()
        if p.is_file() and git_sha(p.read_bytes())==asset['git_blob_sha']:
            continue
        if args.check:
            missing.append(str(rel));continue
        url=f'https://raw.githubusercontent.com/cjpais/Handy/{commit}/{rel}'
        assert asset['url']==url
        with urllib.request.urlopen(url,timeout=60) as response:
            data=response.read(16*1024*1024+1)
        if len(data)>16*1024*1024 or git_sha(data)!=asset['git_blob_sha']:
            raise ValueError(f'Asset integrity mismatch: {rel}')
        p.parent.mkdir(parents=True,exist_ok=True)
        fd,temporary=tempfile.mkstemp(prefix='.upstream-',dir=p.parent)
        try:
            with os.fdopen(fd,'wb') as f:f.write(data)
            os.replace(temporary,p)
        finally:
            Path(temporary).unlink(missing_ok=True)
        restored+=1
    if missing:
        print('Missing or different assets:',*missing,sep='\n');return 1
    print(f'All {len(manifest["assets"])} pinned public assets verified; restored {restored}.')
    return 0

if __name__=='__main__':
    raise SystemExit(main())

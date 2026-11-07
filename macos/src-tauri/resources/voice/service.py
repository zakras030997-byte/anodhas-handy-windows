"""Local voice library. Requests on stdin; no audio/text telemetry or network."""
import contextlib, hashlib, json, os, re, shutil, sqlite3, sys, tempfile, uuid, wave
from pathlib import Path
sys.dont_write_bytecode = True
os.umask(0o077)
os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1')

def checked_id(value):
    if not isinstance(value,str) or len(value)!=32 or any(c not in '0123456789abcdef' for c in value): raise ValueError('Invalid identifier')
    return value

def atomic_json(path,data):
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix='.pending-')
    try:
        with os.fdopen(fd,'w') as f: json.dump(data,f,ensure_ascii=False)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def execute(root,action,payload,runtime):
    root=Path(root);root.mkdir(parents=True,exist_ok=True,mode=0o700)
    library=root/'library.json'
    state=json.loads(library.read_text()) if library.exists() else {'primary':None,'profiles':[]}
    def profile(ident):
        ident=checked_id(ident)
        return next(p for p in state['profiles'] if p['id']==ident)
    def history():
        # Explicit read-only access; never change the working Handy's retention or DB.
        return Path.home()/'Library/Application Support/ai.anodhas.handy'
    if action=='list':
        return {**state,'profiles':[{**p,'audio':str(root/'profiles'/checked_id(p['id'])/'reference.wav')} for p in state['profiles']]}
    if action=='storage':
        runtime=Path(runtime)
        return {'root':str(root),'references':str(root/'profiles'),'outputs':str(root/'outputs'),
                'dictionary':str(root/'pronunciation.json'),'runtimeReady':(runtime/'venv/bin/python').is_file() or (runtime/'python/bin/python3').is_file(),
                'modelReady':(runtime/'model/model.safetensors').is_file()}
    if action=='import_file':
        if payload.get('confirmed') is not True:raise ValueError('Confirm ownership and transcript')
        src=Path(str(payload['path'])).expanduser()
        if src.is_symlink() or not src.is_file() or src.suffix.lower()!='.wav' or src.stat().st_size>20*1024*1024:raise ValueError('Choose a local WAV file')
        text=str(payload['text']).strip();name=str(payload['name']).strip()
        if not text or len(text)>3000 or not name or len(name)>80:raise ValueError('Check name and transcript')
        with wave.open(str(src),'rb') as f:
            duration=f.getnframes()/f.getframerate()
            if f.getnchannels() not in (1,2) or f.getsampwidth()!=2:raise ValueError('Use 16-bit PCM WAV')
        if not 3<=duration<=30:raise ValueError('Choose 3 to 30 seconds')
        ident=uuid.uuid4().hex;folder=root/'profiles'/ident;folder.mkdir(parents=True)
        shutil.copyfile(src,folder/'reference.wav')
        entry={'id':ident,'name':name,'text':text,'status':'candidate','seconds':duration}
        state['profiles'].append(entry);atomic_json(library,state);return entry
    if action=='history':
        db=history()/'history.db'
        if not db.is_file():return []
        with contextlib.closing(sqlite3.connect(db.as_uri()+'?mode=ro',uri=True)) as c:
            return [{'id':r[0],'timestamp':r[1]} for r in c.execute('SELECT id,timestamp FROM transcription_history ORDER BY id DESC LIMIT 50')]
    if action=='history_detail':
        with contextlib.closing(sqlite3.connect((history()/'history.db').as_uri()+'?mode=ro',uri=True)) as c:
            row=c.execute('SELECT file_name,transcription_text FROM transcription_history WHERE id=?',(int(payload['id']),)).fetchone()
        if not row:raise ValueError('Recording is no longer available')
        src=(history()/'recordings'/row[0]).resolve()
        if src.parent!=(history()/'recordings').resolve() or not src.is_file():raise ValueError('Recording is no longer available')
        return {'audio':str(src),'text':row[1]}
    if action=='import':
        if payload.get('confirmed') is not True:raise ValueError('Confirm voice ownership and transcript first')
        detail=execute(root,'history_detail',payload,runtime)
        text=str(payload['text']).strip();name=str(payload['name']).strip()
        if not text or len(text)>3000 or not name or len(name)>80:raise ValueError('Check name and transcript')
        with wave.open(detail['audio'],'rb') as f:
            duration=f.getnframes()/f.getframerate()
        if not 3<=duration<=30:raise ValueError('Choose a recording between 3 and 30 seconds')
        ident=uuid.uuid4().hex;folder=root/'profiles'/ident;folder.mkdir(parents=True)
        shutil.copyfile(detail['audio'],folder/'reference.wav')
        entry={'id':ident,'name':name,'text':text,'status':'candidate','seconds':duration}
        state['profiles'].append(entry);atomic_json(library,state);return entry
    if action=='approve':
        if payload.get('listened') is not True:raise ValueError('Listen to the comparison before approving')
        p=profile(payload['profile']);p['status']='approved';state['primary']=p['id'];atomic_json(library,state);return state
    if action=='generate':
        import time
        import numpy as np
        import mlx.core as mx
        from mlx_audio.tts.utils import load_model
        text=str(payload['text']).strip()
        from pronunciation import prepare_text
        original_text=text
        text=prepare_text(text,root/'pronunciation.json')
        if not text or len(text)>4000:raise ValueError('Text must contain 1 to 4000 characters')
        p=profile(payload.get('profile') or state['primary'])
        model_dir=Path(runtime)/'model'
        if not (model_dir/'model.safetensors').is_file():raise ValueError('Local model is not installed')
        atomic_json(root/'phase.json',{'phase':'loading'})
        start=time.monotonic()
        with contextlib.redirect_stdout(sys.stderr):
            model=load_model(model_dir)
            atomic_json(root/'phase.json',{'phase':'generating'})
            from pronunciation import speech_segments
            segments=speech_segments(text)
            chunks=[]
            for segment in segments:
                chunks.extend(np.array(r.audio) for r in model.generate(text=segment,ref_audio=str(root/'profiles'/p['id']/'reference.wav'),ref_text=p['text'],lang_code='ru',split_pattern='',max_tokens=2048))
        if not chunks:raise ValueError('No audio was produced')
        a=np.concatenate(chunks)
        if not np.isfinite(a).all():raise ValueError('Invalid audio produced')
        ident=uuid.uuid4().hex;folder=root/'outputs';folder.mkdir(exist_ok=True)
        dest=folder/(ident+'.wav');partial=folder/(ident+'.partial')
        with partial.open('xb') as raw,wave.open(raw,'wb') as f:
            f.setnchannels(1);f.setsampwidth(2);f.setframerate(model.sample_rate);f.writeframes((np.clip(a,-1,1)*32767).astype(np.int16).tobytes())
        partial.rename(dest)
        return {'id':ident,'audio':str(dest),'seconds':len(a)/model.sample_rate,'elapsed':time.monotonic()-start,'peak_gib':mx.get_peak_memory()/1024**3,'pronunciation_rules_applied':text!=original_text}
    if action=='output':
        ident=checked_id(payload['id']);p=root/'outputs'/(ident+'.wav')
        if not p.is_file():raise ValueError('Audio does not exist')
        return {'audio':str(p)}
    raise ValueError('Unknown action')

if __name__=='__main__':
    try:
        req=json.loads(sys.stdin.read(65536))
        result=execute(sys.argv[1],req['action'],req.get('payload',{}),sys.argv[2])
        print(json.dumps({'ok':True,'result':result},ensure_ascii=False))
    except Exception:
        # No exception text: libraries may embed transcripts/paths in errors.
        print(json.dumps({'ok':False,'error':'Voice operation failed. Check the local model, selected recording and input.'}))
        sys.exit(1)

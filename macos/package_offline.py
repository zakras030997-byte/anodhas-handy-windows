"""Package public offline runtimes only. Never copies voice profiles or settings."""
import argparse,hashlib,json,shutil,subprocess,os
from pathlib import Path
ASR_HASH='b68557be1e3c40207fd7c4bd9d63f1d3316b963f15325bfb0cc16a8bb0ffd181'
ASR_NAME='parakeet-tdt-0.6b-v3-Q4_K_M.gguf'
def digest(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def package(app,runtime,parakeet,out,entitlements):
 app,runtime,parakeet,out=map(Path,(app,runtime,parakeet,out))
 if out.exists():raise ValueError('Choose a fresh output path')
 if digest(parakeet)!=ASR_HASH:raise ValueError('Parakeet integrity mismatch')
 q=json.loads((runtime/'model/config.json').read_text());assert q['quantization']['bits']==4 and q['model_type']=='qwen3_tts'
 ignore=shutil.ignore_patterns('__pycache__','*.pyc','.DS_Store','.cache','direct_url.json')
 shutil.copytree(app,out,symlinks=True,ignore=ignore)
 res=out/'Contents/Resources';dest=res/'voice-runtime';dest.mkdir()
 for source,name in [(runtime/'python','python'),((runtime/'site-packages') if (runtime/'site-packages').is_dir() else runtime/'venv/lib/python3.12/site-packages','site-packages'),(runtime/'model','model')]:
  shutil.copytree(source,dest/name,symlinks=True,ignore=ignore)
 for p in (dest/'site-packages').glob('*.pth'):
  if '/Users/' in p.read_text(errors='ignore'):raise ValueError('Nonportable Python path in package')
 for p in dest.rglob('*'):
  if p.is_symlink() and p.readlink().is_absolute():
   sibling=p.parent/p.readlink().name
   if not sibling.exists():raise ValueError('Nonportable symlink')
   target=sibling.name;p.unlink();p.symlink_to(target)
 target=res/'resources/models'/ASR_NAME;shutil.copy2(parakeet,target)
 manifest={'application':'ANODHAS Handy','version':'0.9.9','platform':'macOS Apple Silicon','transcription':{'repo':'handy-computer/parakeet-tdt-0.6b-v3-gguf','revision':'85ac09ea12fc4b1112fa76810059364bc6adc9de','file':ASR_NAME,'sha256':ASR_HASH,'license':'CC-BY-4.0'},'voice':{'repo':'mlx-community/Qwen3-TTS-12Hz-1.7B-Base-4bit','revision':'37e955a1deb861c088ae5f3a67043185f3d1a60c','weights_sha256':digest(dest/'model/model.safetensors'),'speech_tokenizer_sha256':digest(dest/'model/speech_tokenizer/model.safetensors'),'license':'Apache-2.0'},'personal_voice_data_included':False}
 (res/'model-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 (res/'MODEL-NOTICES.txt').write_text('ANODHAS Handy 0.9.9 · offline model attribution\n\nParakeet TDT 0.6B v3 Q4_K_M: NVIDIA base model; GGUF conversion by handy-computer. CC-BY-4.0.\nhttps://huggingface.co/handy-computer/parakeet-tdt-0.6b-v3-gguf\n\nQwen3-TTS 12Hz 1.7B Base: Qwen team, converted to MLX 4-bit by mlx-community. Apache-2.0.\nhttps://huggingface.co/mlx-community/Qwen3-TTS-12Hz-1.7B-Base-4bit\n\nPython and dependencies retain their included license notices. Voice cloning requires authorized reference audio. No personal profiles or recordings are distributed.\n')
 subprocess.run(['codesign','--force','--deep','--options','runtime','--entitlements',str(entitlements),'--sign','-',str(out)],check=True)
 subprocess.run(['codesign','--verify','--deep','--strict',str(out)],check=True)
 return manifest
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--app',required=True);p.add_argument('--runtime',required=True);p.add_argument('--parakeet',required=True);p.add_argument('--out',required=True);p.add_argument('--entitlements',required=True);a=p.parse_args()
 print(json.dumps(package(a.app,a.runtime,a.parakeet,a.out,a.entitlements),indent=2))

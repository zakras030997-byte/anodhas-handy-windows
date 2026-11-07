import contextlib,importlib.util,json,sqlite3,tempfile,unittest,wave
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('voice',Path(__file__).parents[2]/'src-tauri/resources/voice/service.py')
voice=importlib.util.module_from_spec(spec);spec.loader.exec_module(voice)
class LibraryTest(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name);self.root=self.base/'voice';self.home=self.base/'home'
  self.history=self.home/'Library/Application Support/ai.anodhas.handy';(self.history/'recordings').mkdir(parents=True)
  with contextlib.closing(sqlite3.connect(self.history/'history.db')) as db, db:
   db.execute('create table transcription_history(id integer,timestamp integer,file_name text,transcription_text text)')
   db.execute('insert into transcription_history values(1,123,?,?)',('sample.wav','Synthetic test only'))
  with wave.open(str(self.history/'recordings/sample.wav'),'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes(b'\0\0'*64000)
  self.home_patch=patch('pathlib.Path.home',return_value=self.home);self.home_patch.start()
 def tearDown(self):self.home_patch.stop();self.temp.cleanup()
 def call(self,a,p=None):return voice.execute(self.root,a,p or {},self.base/'runtime')
 def add(self):return self.call('import',{'id':1,'name':'Test','text':'Synthetic test only','confirmed':True})
 def test_empty_library(self):self.assertIsNone(self.call('list')['primary'])
 def test_readonly_history(self):
  before=(self.history/'history.db').read_bytes();self.call('history');self.call('history_detail',{'id':1});self.assertEqual(before,(self.history/'history.db').read_bytes())
 def test_import_requires_confirmation(self):
  with self.assertRaises(ValueError):self.call('import',{'id':1})
 def test_candidate_never_becomes_primary(self):
  self.add();s=self.call('list');self.assertIsNone(s['primary']);self.assertEqual(s['profiles'][0]['status'],'candidate')
 def test_copy_survives_history_removal(self):
  p=self.add();(self.history/'recordings/sample.wav').unlink();self.assertTrue((self.root/'profiles'/p['id']/'reference.wav').is_file())
 def test_approval_requires_listening(self):
  p=self.add()
  with self.assertRaises(ValueError):self.call('approve',{'profile':p['id']})
 def test_switch_keeps_old_reference(self):
  a=self.add();b=self.add();self.call('approve',{'profile':a['id'],'listened':True});s=self.call('approve',{'profile':b['id'],'listened':True});self.assertEqual(s['primary'],b['id']);self.assertEqual(len(s['profiles']),2)
 def test_traversal_rejected(self):
  with self.assertRaises(ValueError):self.call('output',{'id':'../escape'})
 def test_history_path_escape_rejected(self):
  with contextlib.closing(sqlite3.connect(self.history/'history.db')) as db, db:db.execute("update transcription_history set file_name='../history.db'")
  with self.assertRaises(ValueError):self.call('history_detail',{'id':1})
 def test_original_preserved(self):
  before=(self.history/'recordings/sample.wav').read_bytes();self.add();self.assertEqual(before,(self.history/'recordings/sample.wav').read_bytes())
 def test_storage_reports_real_paths_and_missing_model(self):
  s=self.call('storage');self.assertEqual(s['references'],str(self.root/'profiles'));self.assertFalse(s['modelReady'])
 def test_external_wav_requires_confirmation(self):
  with self.assertRaises(ValueError):self.call('import_file',{'path':str(self.history/'recordings/sample.wav')})
 def test_external_import_preserves_original_and_primary(self):
  src=self.history/'recordings/sample.wav';before=src.read_bytes()
  p=self.call('import_file',{'path':str(src),'text':'Synthetic sample','name':'External','confirmed':True})
  self.assertEqual(before,src.read_bytes());self.assertIsNone(self.call('list')['primary']);self.assertTrue(Path(self.call('list')['profiles'][0]['audio']).is_file())
 def test_external_symlink_is_rejected(self):
  src=self.base/'link.wav';src.symlink_to(self.history/'recordings/sample.wav')
  with self.assertRaises(ValueError):self.call('import_file',{'path':str(src),'text':'Test','name':'Test','confirmed':True})
 def test_external_short_file_is_rejected(self):
  src=self.base/'short.wav'
  with wave.open(str(src),'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes(b'\0\0'*8000)
  with self.assertRaises(ValueError):self.call('import_file',{'path':str(src),'text':'Test','name':'Test','confirmed':True})
if __name__=='__main__':unittest.main()

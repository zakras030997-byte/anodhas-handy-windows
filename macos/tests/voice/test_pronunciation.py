import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[2]/'src-tauri/resources/voice'))
from pronunciation import apply_rules,speech_segments
RULES=[{'kind':'token','source':'API','spoken':'апи','status':'user_confirmed'},{'kind':'phrase','source':'Зачем это интересно?','spoken':'Зачем это, интересно?','status':'user_confirmed'}]
class PronunciationTests(unittest.TestCase):
 def test_requested_word_and_pause(self):self.assertEqual(apply_rules('Есть API. Зачем это интересно?',RULES),'Есть апи. Зачем это, интересно?')
 def test_word_boundaries(self):self.assertEqual(apply_rules('API-интерфейс API_KEY RapidAPI',RULES),'апи-интерфейс API_KEY RapidAPI')
 def test_protected_content(self):
  text='https://example.com/API me@api.com `API` ```API```'
  self.assertEqual(apply_rules(text,RULES),text)
 def test_unconfirmed_rule_not_applied(self):self.assertEqual(apply_rules('Голосовой',[{'kind':'token','source':'Голосовой','spoken':'other','status':'pending_listening'}]),'Голосовой')
 def test_phrase_case_and_boundary(self):
  self.assertEqual(apply_rules('зачем это интересно?',RULES),'Зачем это, интересно?')
  self.assertEqual(apply_rules('Незачем это интересно?',RULES),'Незачем это интересно?')
 def test_repeat_is_stable(self):
  once=apply_rules('API. Зачем это интересно?',RULES);self.assertEqual(apply_rules(once,RULES),once)
class SegmentationTests(unittest.TestCase):
 def test_short_paragraphs_not_separate_takes(self):
  text='Первое предложение.\n\nЗачем это интересно?\n\nСледующее предложение.'
  self.assertEqual(speech_segments(text),[text])
 def test_long_text_preserved_and_bounded(self):
  text=('Сохраняем весь текст, включая слова и знаки. '*100)
  segments=speech_segments(text)
  self.assertTrue(all(len(s)<=1200 for s in segments))
  self.assertEqual(' '.join(' '.join(segments).split()),' '.join(text.split()))
 def test_single_long_token_bounded(self):
  parts=speech_segments('x'*2500)
  self.assertEqual(''.join(parts),'x'*2500)
  self.assertTrue(all(len(s)<=1200 for s in parts))
if __name__=='__main__':unittest.main()


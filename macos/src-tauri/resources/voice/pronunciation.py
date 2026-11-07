"""Owner-approved spoken-form rules. Original scripts and recordings stay unchanged."""
import json,re
from pathlib import Path
PROTECTED=re.compile(r'```[\s\S]*?```|`[^`\n]*`|https?://[^\s]+|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}')

def apply_rules(text,rules):
    approved=[r for r in rules if r.get('status')=='user_confirmed']
    def transform(part):
        for rule in approved:
            source=rule.get('source');spoken=rule.get('spoken');kind=rule.get('kind')
            if not isinstance(source,str) or not source or not isinstance(spoken,str):raise ValueError('Invalid pronunciation rule')
            if kind=='token':part=re.sub(r'(?<!\w)'+re.escape(source)+r'(?!\w)',lambda _:spoken,part,flags=re.I)
            elif kind=='phrase':part=re.sub(r'(?<!\w)'+re.escape(source)+r'(?!\w)',lambda _:spoken,part,flags=re.I)
            else:raise ValueError('Unsupported pronunciation rule')
        return part
    result=[];start=0
    for match in PROTECTED.finditer(text):
        result.extend([transform(text[start:match.start()]),match.group()]);start=match.end()
    result.append(transform(text[start:]));return ''.join(result)

def prepare_text(text,path):
    path=Path(path)
    if not path.exists():return text
    data=json.loads(path.read_text())
    if data.get('schema_version')!=1 or not isinstance(data.get('rules'),list):raise ValueError('Invalid pronunciation dictionary')
    return apply_rules(text,data['rules'])

def speech_segments(text,max_chars=1200):
    """Keep short scripts continuous; bound long scripts at a natural boundary."""
    segments=[];remaining=text
    while len(remaining)>max_chars:
        cut=max(remaining.rfind(c,0,max_chars) for c in '.!?;\n')+1
        if cut<200:cut=remaining.rfind(' ',0,max_chars)
        if cut<1:cut=max_chars
        segments.append(remaining[:cut]);remaining=remaining[cut:].lstrip()
    if remaining:segments.append(remaining)
    return segments

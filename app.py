import os, re, json, math, joblib, requests
from flask import Flask, render_template, request, flash, redirect, url_for
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dart-local-development-key")
FIGMA_TOKEN = os.getenv("FIGMA_ACCESS_TOKEN", "").strip()
MODEL_DIR = os.path.join(app.root_path, "models")

AGENTS = {
    "grandparent": {"label":"Grandparents", "tone":"Patient, larger-text preference", "reading_speed_wpm":115,"attention_span_sec":45,"visual_sensitivity":.90,"motor_precision":.55,"comprehension_factor":.65},
    "elder_adult": {"label":"Elder adults", "tone":"Careful, clarity-focused", "reading_speed_wpm":170,"attention_span_sec":70,"visual_sensitivity":.68,"motor_precision":.72,"comprehension_factor":.82},
    "youth": {"label":"Youth", "tone":"Fast, familiar with common patterns", "reading_speed_wpm":260,"attention_span_sec":100,"visual_sensitivity":.35,"motor_precision":.92,"comprehension_factor":.95},
    "children": {"label":"Children", "tone":"Short attention, simpler language", "reading_speed_wpm":150,"attention_span_sec":35,"visual_sensitivity":.52,"motor_precision":.62,"comprehension_factor":.58},
}
FEATURES = ["font_size_px","text_char_count","node_width_px","node_height_px","contrast_ratio","nearest_element_spacing_px","visible_element_count","navigation_depth","label_complexity_score","layout_complexity_score","interactive_element_count","text_node_count","image_count","minimum_target_dimension_px","whitespace_ratio","task_step_count","reading_speed_wpm","attention_span_sec","visual_sensitivity","motor_precision","comprehension_factor"]
TARGETS = ["task_time_seconds","error_probability","completion_probability","difficulty_score"]


def figma_file_key(value):
    match = re.search(r"figma\.com/(?:design|file)/([a-zA-Z0-9]+)", value.strip())
    if not match: raise ValueError("Paste a valid Figma design or file URL.")
    return match.group(1)


def rgb_hex(rgb):
    if not rgb: return None
    try: return '#%02x%02x%02x' % tuple(max(0,min(255,round(float(rgb[k])*255))) for k in ('r','g','b'))
    except Exception: return None


def luminance(hex_color):
    if not hex_color: return None
    vals=[int(hex_color[i:i+2],16)/255 for i in (1,3,5)]
    vals=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in vals]
    return .2126*vals[0]+.7152*vals[1]+.0722*vals[2]


def contrast(fg,bg):
    a,b=luminance(fg),luminance(bg)
    if a is None or b is None:return 4.5
    hi,lo=max(a,b),min(a,b)
    return round((hi+.05)/(lo+.05),2)


def extract_features(document, agent_key, task_steps=3):
    nodes=[]
    def walk(node):
        if not isinstance(node,dict): return
        if node.get('visible',True) and node.get('type') not in ('DOCUMENT','CANVAS'):
            nodes.append(node)
        for child in node.get('children',[]) or []: walk(child)
    walk(document)
    text_nodes=[n for n in nodes if n.get('type')=='TEXT']
    chars=' '.join(str(n.get('characters','')) for n in text_nodes)
    boxes=[n.get('absoluteBoundingBox') or {} for n in nodes]
    valid=[b for b in boxes if b.get('width') and b.get('height')]
    widths=[float(b['width']) for b in valid]; heights=[float(b['height']) for b in valid]
    text_sizes=[float((n.get('style') or {}).get('fontSize',16) or 16) for n in text_nodes]
    fills=[]; text_colors=[]
    for n in nodes:
        for paint in n.get('fills',[]) or []:
            if paint.get('type')=='SOLID' and paint.get('visible',True):
                c=rgb_hex(paint.get('color')); 
                if c: fills.append(c); break
        if n.get('type')=='TEXT':
            for paint in n.get('fills',[]) or []:
                if paint.get('type')=='SOLID' and paint.get('visible',True):
                    c=rgb_hex(paint.get('color'))
                    if c: text_colors.append(c); break
    ratios=[contrast(f,b) for f in text_colors[:80] for b in fills[:80]]
    # Bounding-box gaps are approximated from neighboring nodes on the same row.
    gaps=[]
    sorted_boxes=sorted(valid,key=lambda b:(round(float(b.get('y',0))/40),float(b.get('x',0))))
    for a,b in zip(sorted_boxes,sorted_boxes[1:]):
        gap=float(b.get('x',0))-float(a.get('x',0))-float(a.get('width',0))
        if 0<=gap<=300:gaps.append(gap)
    names=' '.join(str(n.get('name','')) for n in nodes).lower()
    interactive=sum(1 for n in nodes if n.get('type') in ('INSTANCE','COMPONENT','COMPONENT_SET') or any(w in str(n.get('name','')).lower() for w in ['button','btn','input','field','checkbox','toggle','link','select']))
    image_count=sum(1 for n in nodes if n.get('type') in ('IMAGE','RECTANGLE') and any(p.get('type')=='IMAGE' for p in n.get('fills',[]) or []))
    profile=AGENTS[agent_key]
    # A rough structural complexity proxy, not a ground-truth UX score.
    layout_complexity=min(10,1+len(nodes)/35+len(text_nodes)/18+names.count('auto layout')*.2)
    label_complexity=min(10,1+(sum(len(x.split()) for x in [str(n.get('characters','')) for n in text_nodes])/max(1,len(text_nodes)))/3)
    area=sum(float(b.get('width',0))*float(b.get('height',0)) for b in valid)
    canvas_area=max(area,1)
    return {
      'font_size_px':round(sum(text_sizes)/max(1,len(text_sizes)),2),'text_char_count':len(chars),
      'node_width_px':round(sum(widths)/max(1,len(widths)),2),'node_height_px':round(sum(heights)/max(1,len(heights)),2),
      'contrast_ratio':round(sum(ratios)/max(1,len(ratios)),2),'nearest_element_spacing_px':round(sum(gaps)/max(1,len(gaps)),2),
      'visible_element_count':len(nodes),'navigation_depth':max(1,min(8,task_steps)),'label_complexity_score':round(label_complexity,2),
      'layout_complexity_score':round(layout_complexity,2),'interactive_element_count':interactive,'text_node_count':len(text_nodes),
      'image_count':image_count,'minimum_target_dimension_px':round(min([min(float(b['width']),float(b['height'])) for b in valid] or [44]),2),
      'whitespace_ratio':round(max(0,min(1,1-(len(nodes)/max(1,len(valid)))*.12)),2),'task_step_count':max(1,min(8,task_steps)),
      'reading_speed_wpm':profile['reading_speed_wpm'],'attention_span_sec':profile['attention_span_sec'],
      'visual_sensitivity':profile['visual_sensitivity'],'motor_precision':profile['motor_precision'],'comprehension_factor':profile['comprehension_factor']
    }


def load_model(agent_key):
    path=os.path.join(MODEL_DIR,f'{agent_key}_model.pkl')
    if not os.path.exists(path): return None
    bundle=joblib.load(path)
    return bundle.get('model') if isinstance(bundle,dict) else bundle


def run_analysis(figma_url, task_steps, distribution):
    if not FIGMA_TOKEN: raise RuntimeError('Figma access token is missing. Add FIGMA_ACCESS_TOKEN to your .env file.')
    key=figma_file_key(figma_url)
    response=requests.get(f'https://api.figma.com/v1/files/{key}',headers={'X-Figma-Token':FIGMA_TOKEN},timeout=30)
    if response.status_code==403: raise RuntimeError('Figma denied access. Check the token and make sure the file is shared with your account.')
    if response.status_code==404: raise RuntimeError('Figma file not found. Check the link and your file permissions.')
    response.raise_for_status()
    payload=response.json(); document=payload.get('document',{})
    results=[]
    for agent_key,percent in distribution.items():
        if percent<=0:continue
        model=load_model(agent_key)
        if model is None: raise RuntimeError(f'Missing model: models/{agent_key}_model.pkl. Extract your trained model ZIP into the models folder.')
        features=extract_features(document,agent_key,task_steps)
        row=[features.get(col,0) for col in FEATURES]
        prediction=model.predict([row])[0]
        pred=dict(zip(TARGETS,[float(x) for x in prediction]))
        results.append({'key':agent_key,'label':AGENTS[agent_key]['label'],'percent':percent,'features':features,
          'time':max(0,round(pred['task_time_seconds'],1)),'error':round(max(0,min(1,pred['error_probability']))*100,1),
          'completion':round(max(0,min(1,pred['completion_probability']))*100,1),'difficulty':round(max(0,min(10,pred['difficulty_score'])),1)})
    return {'file_name':payload.get('name','Figma design'),'results':results,'node_count':sum(r['features']['visible_element_count'] for r in results[:1]),'distribution':distribution}

@app.route('/',methods=['GET'])
def home():
    return render_template('index.html')

@app.route('/analyze',methods=['POST'])
def analyze():
    link=request.form.get('figma_url','').strip()
    try:
        task_steps=int(request.form.get('task_steps',3))
        task_steps=max(1,min(8,task_steps))
        keys=list(AGENTS)
        values=[max(0,int(request.form.get('share_'+k,0) or 0)) for k in keys]
        if sum(values)!=100: raise ValueError('Agent distribution must add up to 100%.')
        distribution=dict(zip(keys,values))
        result=run_analysis(link,task_steps,distribution)
        return render_template('results.html',result=result)
    except Exception as e:
        flash(str(e),'error')
        return redirect(url_for('home'))

if __name__=='__main__':
    app.run(debug=True)

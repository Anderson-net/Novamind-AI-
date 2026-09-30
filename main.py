import os, base64, uuid, io, math, json, re, tempfile
from fastapi import FastAPI, Header, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from openai import OpenAI
from PIL import Image

BASE=os.path.dirname(os.path.abspath(__file__))
STATIC_DIR=os.path.join(BASE,"static")
# GitHub/Render may receive the web assets in the repository root instead of /static.
# Use /static when present; otherwise serve the root so the service can boot.
if not os.path.isdir(STATIC_DIR):
    STATIC_DIR=BASE
app=FastAPI(title="NovaMind Mobile v5 — Command Engine")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

ALLOWED={"gpt-5.6-luna","gpt-5.6-terra","gpt-5.6-sol"}
DEFAULT_MODEL="gpt-5.6-luna"
SYSTEM="""Eres NovaMind, un asistente orientado a resultados. No te limites a conversar: transforma objetivos en trabajo concreto.
Usa lenguaje claro. Cuando una tarea sea compleja, divídela internamente en pasos, ejecuta lo que las herramientas disponibles permitan y verifica el resultado.
Nunca inventes que ejecutaste una acción externa si no existe una herramienta conectada para hacerlo. Si falta una autorización, archivo, cuenta o servicio, dilo y deja el siguiente paso listo.
Comandos Nova: /hazlo, /resuelve, /investiga, /crea, /anuncio, /video, /imagen, /documento, /datos, /codigo, /automatiza, /aprende, /explica, /compara, /detecta, /plan, /equipo, /verifica, /continua, /pack, /modoexperto, /modoexpress, /cinema, /storyboard, /director, /promptlab, /remix, /memory, /research, /code, /voice.
"""

class ChatRequest(BaseModel):
    message:str=Field(min_length=1,max_length=30000)
    history:list[dict]=Field(default_factory=list)
    model:str=DEFAULT_MODEL
    web_search:bool=False

class ExecuteRequest(ChatRequest):
    auto:bool=True


def key_from(auth):
    if not auth or not auth.lower().startswith("bearer "):
        raise HTTPException(401,"Introduce tu API Key en Ajustes.")
    k=auth.split(" ",1)[1].strip()
    if not k: raise HTTPException(401,"API Key vacía.")
    return k

def client(auth): return OpenAI(api_key=key_from(auth))

def clean_history(history):
    out=[]
    for x in history[-24:]:
        if x.get("role") in ("user","assistant") and isinstance(x.get("content"),str):
            out.append({"role":x["role"],"content":x["content"][:12000]})
    return out

def response_text(c, model, prompt, history=None, web=False):
    p={"model":model,"instructions":SYSTEM,"input":(clean_history(history or [])+[ {"role":"user","content":prompt} ])}
    if web: p["tools"]=[{"type":"web_search"}]
    r=c.responses.create(**p)
    return r.output_text

def safe_model(model):
    return model if model in ALLOWED else DEFAULT_MODEL

@app.get("/")
def home(): return FileResponse(os.path.join(STATIC_DIR,"index.html"))

@app.get("/health")
def health():
    return {"ok":True,"app":"NovaMind Mobile v5","engine":"Command Engine","model":DEFAULT_MODEL}

@app.get("/api/commands")
def commands():
    return {"commands":[
      {"name":"/hazlo","description":"Comando maestro: entiende un objetivo, crea un plan, ejecuta lo posible, verifica y entrega resultado."},
      {"name":"/resuelve","description":"Descompone problemas complejos y construye una solución accionable."},
      {"name":"/investiga","description":"Investigación web con hechos, fuentes, incertidumbres y síntesis."},
      {"name":"/crea","description":"Convierte una idea en un entregable concreto."},
      {"name":"/anuncio","description":"Diseña campaña, guion, piezas, copys y plan de publicación."},
      {"name":"/video","description":"Diseña un proyecto audiovisual y su pipeline de producción."},
      {"name":"/datos","description":"Analiza datos, encuentra anomalías y propone conclusiones."},
      {"name":"/codigo","description":"Diseña, escribe, prueba y corrige software."},
      {"name":"/automatiza","description":"Diseña un flujo repetible con disparadores, pasos y resultados."},
      {"name":"/verifica","description":"Audita una respuesta, cálculo, código, documento o afirmación."},
      {"name":"/equipo","description":"Divide un objetivo entre roles especializados y consolida resultados."},
      {"name":"/pack","description":"Produce un paquete completo de contenidos y entregables."},
      {"name":"/cinema","description":"Imagen a movimiento local con zoom y paneo; no es vídeo generativo."},
      {"name":"/storyboard","description":"Storyboard técnico de una idea."},
      {"name":"/director","description":"Dirección cinematográfica: cámara, luz, acción, ritmo y sonido."},
      {"name":"/promptlab","description":"Tres versiones de un prompt: precisa, creativa y experimental."},
      {"name":"/remix","description":"Variaciones creativas de una idea."},
      {"name":"/memory","description":"Convierte una preferencia en una instrucción de memoria."},
      {"name":"/voice","description":"Guion de voz con pausas, énfasis y dirección interpretativa."}
    ]}

@app.post("/api/chat")
def chat(body:ChatRequest, authorization:str|None=Header(default=None)):
    model=safe_model(body.model); c=client(authorization)
    try: return {"reply":response_text(c,model,body.message,body.history,body.web_search)}
    except Exception as e: raise HTTPException(502,f"Error de OpenAI: {str(e)[:600]}")

@app.post("/api/hazlo")
def hazlo(body:ExecuteRequest, authorization:str|None=Header(default=None)):
    """Command Engine: planner -> execution passes -> verifier -> final response."""
    model=safe_model(body.model); c=client(authorization)
    goal=body.message.strip()
    if goal.startswith("/hazlo"): goal=goal[len("/hazlo"):].strip()
    if not goal: raise HTTPException(400,"Después de /hazlo indica qué quieres conseguir.")
    planner=f"""Analiza este objetivo como arquitecto de ejecución de NovaMind.
OBJETIVO: {goal}
Devuelve SOLO JSON válido con estas claves:
summary (string), missing (array de strings), steps (array de objetos con id, action, purpose, prompt), verification (array de strings).
Máximo 6 steps. Las acciones permitidas son: research, solve, create, code, explain, compare, verify.
No inventes herramientas externas. Si el objetivo requiere una acción que NovaMind no puede ejecutar, conviértela en un entregable preparado para que la persona lo ejecute.
"""
    try:
        raw=response_text(c,model,planner,body.history,body.web_search)
        match=re.search(r'\{.*\}',raw,re.S)
        plan=json.loads(match.group(0) if match else raw)
    except Exception as e:
        raise HTTPException(502,f"No pude planificar la orden: {str(e)[:500]}")
    results=[]
    for step in plan.get("steps",[])[:6]:
        action=step.get("action","solve")
        prompt=step.get("prompt") or step.get("purpose") or goal
        web=body.web_search or action=="research"
        if action=="research": prompt=f"Investiga y sintetiza para resolver este paso. Objetivo original: {goal}\nPaso: {prompt}\nIncluye fuentes y fecha cuando uses información actual."
        elif action=="code": prompt=f"Resuelve este paso como ingeniero senior. Entrega código listo para ejecutar, pruebas y cómo verificarlo. Objetivo: {goal}\nPaso: {prompt}"
        elif action=="verify": prompt=f"Audita este paso y busca errores, supuestos y omisiones. Objetivo: {goal}\nMaterial a verificar: {prompt}"
        else: prompt=f"Trabaja este paso de forma concreta. Objetivo: {goal}\nPaso: {prompt}"
        try:
            txt=response_text(c,model,prompt,results[-3:] if results else body.history,web)
            results.append({"id":step.get("id"),"action":action,"result":txt})
        except Exception as e:
            results.append({"id":step.get("id"),"action":action,"result":f"Paso no completado: {str(e)[:300]}"})
    verifier=f"""Actúa como verificador final. Objetivo: {goal}
PLAN: {json.dumps(plan,ensure_ascii=False)}
RESULTADOS: {json.dumps(results,ensure_ascii=False)}
Determina qué está realmente resuelto, qué queda pendiente y corrige contradicciones. No afirmes acciones externas no realizadas.
Entrega una respuesta final clara, útil y orientada a resultados. Si hay entregables, enuméralos. Si falta algo, da el siguiente paso exacto."""
    try: final=response_text(c,model,verifier,[],False)
    except Exception as e: final="No se pudo hacer la verificación final: "+str(e)[:400]
    return {"reply":final,"plan":plan,"steps":results,"engine":"NovaMind Command Engine"}

@app.post("/api/image")
def image(body:ChatRequest, authorization:str|None=Header(default=None)):
    c=client(authorization)
    try:
        r=c.images.generate(model="gpt-image-2",prompt=body.message,size="1024x1024")
        return {"image":"data:image/png;base64,"+r.data[0].b64_json}
    except Exception as e: raise HTTPException(502,f"No se pudo generar la imagen: {str(e)[:500]}")

def make_motion_video(data,duration=6,zoom=1.10,direction="zoom"):
    try: import imageio.v2 as imageio; import numpy as np
    except Exception: raise RuntimeError("Falta imageio/numpy. Instala requirements.txt.")
    im=Image.open(io.BytesIO(data)).convert("RGB"); W,H=1280,720
    scale=max(W/im.width,H/im.height); base=im.resize((int(im.width*scale),int(im.height*scale)),Image.Resampling.LANCZOS)
    fps=24; frames=max(24,int(duration*fps))
    tmp=tempfile.NamedTemporaryFile(suffix=".mp4",delete=False); tmp.close()
    try:
        writer=imageio.get_writer(tmp.name,fps=fps,codec="libx264",pixelformat="yuv420p",output_params=["-movflags","faststart"])
        for i in range(frames):
            t=i/max(1,frames-1); z=1+(zoom-1)*t; cw,ch=int(W/z),int(H/z)
            maxx=max(0,base.width-cw); maxy=max(0,base.height-ch)
            if direction=="left": x=int(maxx*t); y=maxy//2
            elif direction=="right": x=int(maxx*(1-t)); y=maxy//2
            elif direction=="up": x=maxx//2; y=int(maxy*(1-t))
            elif direction=="down": x=maxx//2; y=int(maxy*t)
            else: x=int(maxx*(0.5+0.25*math.sin(t*math.pi))); y=int(maxy*(0.5-0.18*math.sin(t*math.pi)))
            frame=base.crop((x,y,x+cw,y+ch)).resize((W,H),Image.Resampling.LANCZOS)
            if t<.06: frame=Image.blend(Image.new("RGB",(W,H),(0,0,0)),frame,t/.06)
            if t>.94: frame=Image.blend(frame,Image.new("RGB",(W,H),(0,0,0)),(t-.94)/.06)
            writer.append_data(np.array(frame))
        writer.close()
        with open(tmp.name,"rb") as f: return f.read()
    finally:
        try: os.unlink(tmp.name)
        except OSError: pass

@app.post("/api/cinema")
async def cinema(authorization:str|None=Header(default=None), image:UploadFile=File(...), duration:float=Form(6), zoom:float=Form(1.10), direction:str=Form("zoom")):
    key_from(authorization)
    if not 2<=duration<=15: raise HTTPException(400,"Duración: 2–15 segundos.")
    if not 1.0<=zoom<=1.35: raise HTTPException(400,"Zoom: 1.0–1.35.")
    if direction not in {"zoom","left","right","up","down"}: raise HTTPException(400,"Dirección inválida.")
    try: video=make_motion_video(await image.read(),duration,zoom,direction)
    except Exception as e: raise HTTPException(500,str(e))
    return StreamingResponse(io.BytesIO(video),media_type="video/mp4",headers={"Content-Disposition":'attachment; filename="novamind_cinema.mp4"'})

@app.post("/api/command")
def command(body:ChatRequest, authorization:str|None=Header(default=None)):
    msg=body.message.strip(); cmd=msg.split()[0].lower() if msg.startswith("/") else "/hazlo"
    if cmd=="/hazlo" or not msg.startswith("/"):
        return hazlo(ExecuteRequest(message=msg if msg.startswith("/hazlo") else "/hazlo "+msg,history=body.history,model=body.model,web_search=body.web_search),authorization)
    payload=msg[len(cmd):].strip()
    if cmd=="/cinema": return {"reply":"Comando /cinema listo. Abre Cine, sube una imagen y elige duración, zoom y movimiento. Es movimiento local, no vídeo generativo."}
    templates={
      "/storyboard":f"Crea un storyboard técnico de 6 planos para: {payload}",
      "/director":f"Actúa como director. Define cámara, lente, movimiento, luz, actuación, ritmo y sonido para: {payload}",
      "/promptlab":f"Genera 3 prompts para: {payload}: preciso, creativo y experimental.",
      "/remix":f"Crea 8 remixes distintos de: {payload}, conservando el elemento principal.",
      "/memory":f"Convierte en memoria útil esta preferencia: {payload}",
      "/research":f"Investiga profundamente: {payload}. Separa hechos, datos actuales, fuentes e incertidumbres.",
      "/code":f"Resuelve como ingeniero senior: {payload}. Entrega código, pruebas y ejecución.",
      "/voice":f"Crea un guion natural de voz para: {payload}, con pausas y énfasis."
    }
    if cmd not in templates: raise HTTPException(400,"Comando Nova desconocido. Prueba /hazlo o consulta /api/commands.")
    return chat(ChatRequest(message=templates[cmd],history=body.history,model=body.model,web_search=(body.web_search or cmd=="/research")),authorization)

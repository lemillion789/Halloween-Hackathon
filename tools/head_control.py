#!/usr/bin/env python3
"""Panel web para controlar la cabeza por serie: ESP32 de los ojos y ESP32 del cuello/hoverboard.

    python3 tools/head_control.py [--eyes /dev/ttyUSB0] [--neck /dev/ttyUSB1] [--http 8080]

Abre http://localhost:8080. Protocolo: firmware/eyes/README.md y firmware/neck/neck.ino.
Sin --eyes/--neck los detecta sondeando: la placa que responde 'POS' al comando Q es el cuello, la otra los ojos.
Requiere pyserial.
"""
import argparse
import json
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import serial
import serial.tools.list_ports

MOODS = "neutral angry happy surprised sleepy sad suspicious evil dead possessed dizzy scared".split()

DEVS = ("eyes", "neck")
sers = {d: None for d in DEVS}
lock = threading.Lock()
log = deque(maxlen=200)   # (n, texto)
log_n = 0
imu = ""
ofs = ""   # ultima respuesta "OFS lx ly rx ry" de los ojos


def add_log(text):
    global log_n
    log_n += 1
    log.append((log_n, text))


def reader(dev):
    global imu, ofs
    while True:
        s = sers[dev]
        if s is None or not s.is_open:
            time.sleep(0.2)
            continue
        try:
            line = s.readline().decode("utf-8", "replace").strip()
        except Exception:
            time.sleep(0.2)
            continue
        if line:
            if line.startswith("IMU"):
                imu = line
            elif "OFS " in line:
                ofs = line[line.index("OFS "):]
                add_log(f"< [{dev}] {line}")
            else:
                add_log(f"< [{dev}] {line}")


def usb_ports():
    return [p for p in serial.tools.list_ports.comports()
            if "ttyUSB" in p.device or "ttyACM" in p.device or p.device.startswith("COM")]


def list_ports():
    return sorted(p.device for p in usb_ports())


def connect(dev, port):
    with lock:
        if sers[dev] is not None:
            try:
                sers[dev].close()
            except Exception:
                pass
            sers[dev] = None
        sers[dev] = serial.Serial(port, 115200, timeout=0.5)
    add_log(f"# {dev} conectado a {port}")


def send(dev, line):
    with lock:
        s = sers[dev]
        if s is None or not s.is_open:
            raise RuntimeError(f"{dev}: sin conexion")
        s.write((line.strip() + "\n").encode())
    if not line.startswith(("L ", "P ", "O L ", "O R ")):      # no llenar el log con mirada/giro continuos
        add_log(f"> [{dev}] {line}")


PAGE = """<!doctype html><html lang=es><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Calavera - control</title>
<style>
:root{--bg:#120d0d;--fg:#eee;--card:#1f1717;--acc:#d22;--mut:#977}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px system-ui,sans-serif;padding:16px;max-width:900px;margin:auto}
h1{font-size:20px;margin:0 0 12px}h2{font-size:13px;color:var(--mut);text-transform:uppercase;letter-spacing:.08em;margin:0 0 10px}
.card{background:var(--card);border-radius:10px;padding:14px;margin-bottom:12px}
button,select,input{font:inherit;color:var(--fg);background:#2d2121;border:1px solid #4a3535;border-radius:7px;padding:8px 12px}
button{cursor:pointer}button:hover{border-color:var(--acc)}button.on{background:var(--acc);border-color:var(--acc)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(110px,1fr));gap:8px}
.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
#pad{width:240px;height:240px;background:#0c0808;border:1px solid #4a3535;border-radius:10px;position:relative;touch-action:none;cursor:crosshair}
#dot{width:16px;height:16px;border-radius:50%;background:var(--acc);position:absolute;left:112px;top:112px;pointer-events:none}
#log{background:#0c0808;border-radius:8px;padding:8px;height:140px;overflow:auto;font:12px monospace;white-space:pre-wrap}
#st{font-size:13px;color:var(--mut)}input[type=range]{width:200px;padding:0}
</style>
<h1>Calavera - control de cabeza <span id=st></span></h1>
<div class=card><h2>Conexion</h2><div class=row>
Ojos <select id=p_eyes></select> Cuello <select id=p_neck></select><button onclick=refresh()>Actualizar</button><button onclick=conn()>Conectar</button></div></div>
<div class=card><h2>Expresion</h2><div class=grid id=moods></div></div>
<div class=card><h2>Mirada</h2><div class=row>
<div id=pad><div id=dot></div></div>
<div><button onclick="look(0,0)">Centro</button> <button onclick="cmd('B')">Parpadear</button>
<button id=demo onclick=demo()>Demo</button><p id=lk style=color:var(--mut)></p>
<label><input type=checkbox id=ix> Invertir X</label><br><label><input type=checkbox id=iy> Invertir Y</label></div></div></div>
<div class=card><h2>Centrado de ojos (pixeles)</h2>
<p style="margin:0 0 10px;color:var(--mut);font-size:13px">Mueve cada ojo hasta que quede centrado en su cuenca. Los cambios se ven al instante; "Guardar" los deja en la flash del ESP32 (sobreviven al reinicio).</p>
<div class=row style="align-items:flex-start;gap:24px" id=ofsbox></div>
<div class=row style=margin-top:10px><button id=cal onclick=calib()>Modo calibracion (cruz)</button>
<button onclick="cmd('O S')" style="border-color:var(--acc)">Guardar en ESP32</button><button onclick="cmd('O E')">Recargar guardado</button>
<button onclick="cmd('O 0')">Poner a 0</button><code id=ofs></code></div></div>
<div class=card><h2>Cuello (giro)</h2><div class=row>
<input type=range id=neck min=45 max=135 value=90 style=width:300px oninput="neckGo(this.value)"><span id=nv>90</span>&deg;
<button onclick="neckGo(90,1)">Centro</button><button id=sw onclick=sweep()>Barrido</button></div></div>
<div class=card><h2>LEDs interiores</h2><div class=row>
<input type=range id=led min=0 max=255 value=255 oninput="cmd('G '+this.value,1)"><span id=lv>255</span>
<button onclick="cmd('G P')">Latido suave</button><button onclick="cmd('G H')">Corazon</button><button onclick="cmd('G 0')">Apagar</button></div></div>
<div class=card><h2>IMU</h2><div class=row><button onclick="cmd('I 1')">Stream on</button><button onclick="cmd('I 0')">Stream off</button>
<button onclick="cmd('I C')">Recalibrar</button><code id=imu></code></div></div>
<div class=card><h2>Comando manual</h2><div class=row><input id=raw placeholder="M evil" style=flex:1 onkeydown="if(event.key=='Enter')rawSend()"><button onclick=rawSend()>Enviar</button></div>
<div id=log style=margin-top:10px></div></div>
<script>
const MOODS=__MOODS__;let last=0,demoOn=false;
const $=id=>document.getElementById(id);
async function api(p,b){const r=await fetch(p,b?{method:'POST',body:JSON.stringify(b)}:{});return r.json()}
async function cmd(l,dev){const r=await api('/cmd',{dev:dev||'eyes',line:l});if(r.error)$('st').textContent=' - '+r.error;if(l.startsWith('G ')&&!isNaN(l.slice(2)))$('lv').textContent=l.slice(2)}
function rawSend(){const v=$('raw').value;if(v){cmd(v);$('raw').value=''}}
async function refresh(){const r=await api('/ports');for(const d of ['eyes','neck']){$('p_'+d).innerHTML=r.ports.map(p=>`<option>${p}</option>`).join('');if(r[d])$('p_'+d).value=r[d]}
 $('st').textContent=' - ojos '+(r.eyes?'ok':'sin conexion')+', cuello '+(r.neck?'ok':'sin conexion')}
async function conn(){for(const d of ['eyes','neck']){const r=await api('/connect',{dev:d,port:$('p_'+d).value});if(r.error){$('st').textContent=' - '+r.error;return}}refresh()}
let nlast=0;function neckGo(a,force){a=+a;$('neck').value=a;$('nv').textContent=a;$('sw').classList.remove('on');const n=Date.now();if(!force&&n-nlast<60)return;nlast=n;cmd('P '+a,'neck');swOn=false}
let swOn=false;function sweep(){swOn=!swOn;$('sw').classList.toggle('on',swOn);if(swOn)cmd('S','neck')}
MOODS.forEach(m=>{const b=document.createElement('button');b.textContent=m;b.onclick=()=>{cmd('M '+m);document.querySelectorAll('#moods button').forEach(x=>x.classList.toggle('on',x==b))};$('moods').appendChild(b)});
function look(x,y){$('dot').style.left=(112+x*112)+'px';$('dot').style.top=(112+y*112)+'px';
 const sx=$('ix').checked?-1:1,sy=$('iy').checked?-1:1;$('lk').textContent=`x=${x.toFixed(2)} y=${y.toFixed(2)}`;
 const now=Date.now();if(now-last<50)return;last=now;cmd(`L ${(x*sx).toFixed(2)} ${(y*sy).toFixed(2)}`,1)}
function padEvt(e){const r=$('pad').getBoundingClientRect();look(Math.max(-1,Math.min(1,(e.clientX-r.left)/r.width*2-1)),Math.max(-1,Math.min(1,(e.clientY-r.top)/r.height*2-1)))}
let drag=false;$('pad').onpointerdown=e=>{drag=true;$('pad').setPointerCapture(e.pointerId);padEvt(e)};$('pad').onpointermove=e=>{if(drag)padEvt(e)};$('pad').onpointerup=()=>drag=false;
const OF={L:[0,0],R:[0,0]};let ofT=0,ofSent='';
['L','R'].forEach(e=>{const d=document.createElement('div');d.innerHTML=`<b>Ojo ${e=='L'?'izquierdo':'derecho'}</b><br>
<div style="display:grid;grid-template-columns:repeat(3,44px);gap:4px;margin:6px 0">
<span></span><button onclick="ofsStep('${e}',0,-1)">&uarr;</button><span></span>
<button onclick="ofsStep('${e}',-1,0)">&larr;</button><button onclick="ofsSet('${e}',0,0)">0</button><button onclick="ofsStep('${e}',1,0)">&rarr;</button>
<span></span><button onclick="ofsStep('${e}',0,1)">&darr;</button><span></span></div>
X <input type=range min=-30 max=30 id=o${e}x oninput="ofsSet('${e}',+this.value,OF.${e}[1])"> <span id=o${e}xv>0</span><br>
Y <input type=range min=-30 max=30 id=o${e}y oninput="ofsSet('${e}',OF.${e}[0],+this.value)"> <span id=o${e}yv>0</span>`;$('ofsbox').appendChild(d)});
function ofsShow(e){$('o'+e+'x').value=OF[e][0];$('o'+e+'y').value=OF[e][1];$('o'+e+'xv').textContent=OF[e][0];$('o'+e+'yv').textContent=OF[e][1]}
function ofsSet(e,x,y){x=Math.max(-30,Math.min(30,x));y=Math.max(-30,Math.min(30,y));OF[e]=[x,y];ofsShow(e);
 const n=Date.now();if(n-ofT<60){clearTimeout(ofsSet.t);ofsSet.t=setTimeout(()=>ofsSet(e,x,y),70);return}ofT=n;cmd(`O ${e} ${x} ${y}`)}
function ofsStep(e,dx,dy){ofsSet(e,OF[e][0]+dx,OF[e][1]+dy)}
let calOn=false;function calib(){calOn=!calOn;$('cal').classList.toggle('on',calOn);cmd(calOn?'C 1':'C 0')}
function ofsParse(t){const v=t.trim().split(' ').filter(Boolean).slice(1).map(Number);if(v.length<4||v.some(isNaN))return;
 if(t==ofSent)return;ofSent=t;OF.L=[v[0],v[1]];OF.R=[v[2],v[3]];ofsShow('L');ofsShow('R');$('ofs').textContent=t}
function demo(){demoOn=!demoOn;$('demo').classList.toggle('on',demoOn);cmd(demoOn?'D':'M neutral')}
let ln=0;setInterval(async()=>{const r=await api('/poll?since='+ln);if(r.lines.length){ln=r.lines[r.lines.length-1][0];const l=$('log');l.textContent+=r.lines.map(x=>x[1]).join('\\n')+'\\n';l.scrollTop=l.scrollHeight}
 $('imu').textContent=r.imu;if(r.ofs&&Date.now()-ofT>600)ofsParse(r.ofs)},400);
refresh();setTimeout(()=>cmd('O'),800);
</script></html>
""".replace("__MOODS__", json.dumps(MOODS))


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def reply(self, obj, code=200, ctype="application/json"):
        data = obj.encode() if isinstance(obj, str) else json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def body(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        if self.path == "/":
            self.reply(PAGE, ctype="text/html; charset=utf-8")
        elif self.path == "/ports":
            ports = list_ports()
            cur = {d: (sers[d].port if sers[d] is not None and sers[d].is_open else None) for d in DEVS}
            self.reply({"ports": ports, **cur})
        elif self.path.startswith("/poll"):
            since = int(self.path.split("since=")[-1] or 0)
            self.reply({"lines": [l for l in log if l[0] > since], "imu": imu, "ofs": ofs})
        else:
            self.reply({}, 404)

    def do_POST(self):
        try:
            b = self.body()
            if self.path == "/cmd":
                send(b.get("dev", "eyes"), b["line"])
            elif self.path == "/connect":
                connect(b["dev"], b["port"])
            self.reply({"ok": True})
        except Exception as e:
            self.reply({"error": str(e)})


def is_neck(port):
    """Abre el puerto, espera el reinicio del ESP32 y pregunta Q: el cuello responde POS."""
    try:
        with serial.Serial(port, 115200, timeout=0.5) as sp:
            time.sleep(1.8)
            sp.reset_input_buffer()
            sp.write(b"Q\n")
            end = time.time() + 1.0
            while time.time() < end:
                if sp.readline().decode("utf-8", "replace").startswith("POS"):
                    return True
    except Exception:
        pass
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eyes", help="puerto del ESP32 de los ojos")
    ap.add_argument("--neck", help="puerto del ESP32 del cuello")
    ap.add_argument("--http", type=int, default=8080)
    a = ap.parse_args()
    ports = {"eyes": a.eyes, "neck": a.neck}
    for p in usb_ports():
        if p.device in ports.values():
            continue
        if ports["neck"] and ports["eyes"]:
            break
        if is_neck(p.device) and not ports["neck"]:
            ports["neck"] = p.device
        elif not ports["eyes"]:
            ports["eyes"] = p.device
    for d in DEVS:
        if ports[d]:
            try:
                connect(d, ports[d])
            except Exception as e:
                print("No se pudo abrir", ports[d], e)
        threading.Thread(target=reader, args=(d,), daemon=True).start()
    print(f"Panel en http://localhost:{a.http}")
    ThreadingHTTPServer(("127.0.0.1", a.http), H).serve_forever()


if __name__ == "__main__":
    main()

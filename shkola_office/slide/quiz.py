"""InterSlide: квізи. Слайд-питання будується з даних (Slide.quiz); відповідь — елемент reveal (з'являється за кліком).
Види: choice (вибір, одна чи кілька правильних), truefalse, input (вписати — у HTML плитками), order (впорядкувати),
match (пари). export_html() — один HTML-файл квізу для учнів, працює офлайн."""
from __future__ import annotations

import html
import json
import random

from .model import Element, Presentation, Slide

KINDS = {"choice": "Вибір відповіді", "truefalse": "Правда чи ні", "input": "Вписати слово",
         "order": "Упорядкувати", "match": "Знайти пару"}
LETTERS = "АБВГДЕЄЖ"


def answer_text(q: dict) -> str:
    k, o, a = q["kind"], q.get("options", []), q.get("answer")
    if k in ("choice", "truefalse"):
        return "Відповідь: " + ", ".join(f"{LETTERS[i]}) {o[i]}" if k == "choice" else o[i] for i in a)
    if k == "input":
        return f"Відповідь: {a}"
    if k == "order":
        return "Правильний порядок: " + " → ".join(o)
    return "Пари: " + "; ".join(f"{l} — {r}" for l, r in o)


def make_quiz_slide(pres: Presentation, q: dict, seed: int | None = None) -> Slide:
    """q: kind, question, options, answer (індекси для choice/truefalse, текст для input), points."""
    from .themes import DEFAULT_THEME, THEMES, _paint
    q = {"points": 1, **q}
    if q["kind"] == "truefalse":
        q["options"] = ["Правда", "Неправда"]
    W, H = pres.size
    L, bw = 50, W - 100
    half = (bw - 30) / 2
    rnd = random.Random(seed if seed is not None else q["question"])
    els = [Element("text", L, 26, bw, 40, KINDS[q["kind"]], 18, role="body", italic=True),
           Element("shape", L, 70, bw, 86, q["question"], 26, bold=True, shape="Скруглений прямокутник",
                   role="accent", align="center")]
    k, opts = q["kind"], q.get("options", [])
    top = 176
    if k in ("choice", "truefalse"):
        n = len(opts)
        cols = 1 if k == "truefalse" or n <= 2 else 2
        cols = 2 if k == "truefalse" else cols
        rows = (n + cols - 1) // cols
        h = min(70, (H - top - 80) / max(1, rows) - 14)
        cw = bw if cols == 1 else half
        for i, t in enumerate(opts):
            label = t if k == "truefalse" else f"{LETTERS[i]}) {t}"
            els.append(Element("shape", L + (i % cols) * (half + 30), top + (i // cols) * (h + 14), cw, h, label, 24,
                               shape="Скруглений прямокутник", role=f"opt:{i}", align="center"))
    elif k == "input":
        els.append(Element("shape", L + bw / 4, top + 20, bw / 2, 70, "_______", 30, shape="Скруглений прямокутник",
                           role="opt:0", align="center"))
        if opts:
            els.append(Element("text", L, top + 110, bw, 40, "Слова для вибору: " + " · ".join(opts), 20,
                               role="body", align="center"))
    elif k == "order":
        sh = opts[:]
        while len(sh) > 1 and sh == opts:
            rnd.shuffle(sh)
        q["shown"] = sh
        for i, t in enumerate(sh):
            els.append(Element("shape", L + 120, top + i * 56, bw - 240, 46, t, 22, shape="Скруглений прямокутник",
                               role=f"opt:{i}", align="center"))
    elif k == "match":
        right = [r for _, r in opts]
        while len(right) > 1 and right == [r for _, r in opts]:
            rnd.shuffle(right)
        q["shown"] = right
        for i, (l, _) in enumerate(opts):
            els.append(Element("shape", L, top + i * 56, half - 40, 46, f"{i + 1}. {l}", 22,
                               shape="Скруглений прямокутник", role=f"opt:{i}", align="center"))
            els.append(Element("shape", L + half + 70, top + i * 56, half - 40, 46, f"{LETTERS[i]}) {right[i]}", 22,
                               shape="Скруглений прямокутник", role="card", align="center"))
    els.append(Element("shape", L, H - 70, bw, 50, answer_text(q), 22, bold=True, shape="Скруглений прямокутник",
                       role="accent2", align="center", reveal=True))
    s = Slide(els, layout="Квіз", quiz=q)
    t = THEMES.get(pres.theme or DEFAULT_THEME, THEMES[DEFAULT_THEME])
    s.bg = t.bg
    for e in s.elements:
        _paint(e, t)
    s.elements[:0] = t.decor(W, H, False)
    return s


def check(q: dict, picked: int) -> bool:
    """Показ: клік по варіанту (choice/truefalse) — чи правильний."""
    return picked in (q.get("answer") or [])


# ---------- HTML-квіз ----------
_CSS = """body{font-family:Segoe UI,Arial,sans-serif;background:#eef5f2;margin:0;color:#1f2d2a}
main{max-width:760px;margin:auto;padding:16px}h1{color:#135548;font-size:26px}
.q{background:#fff;border-radius:14px;padding:16px 18px;margin:14px 0;box-shadow:0 1px 4px #0002}
.q h2{font-size:19px;margin:0 0 10px}.k{color:#5b6b67;font-size:13px}
button.o,.tile{display:block;width:100%;text-align:left;margin:6px 0;padding:10px 12px;border:2px solid #cfe3dc;
border-radius:10px;background:#f7fbf9;font-size:16px;cursor:pointer}.tile{display:inline-block;width:auto}
.sel{border-color:#1d7a66!important;background:#e3f1ec!important}.ok{border-color:#2e9d5b!important;background:#dff3e6!important}
.bad{border-color:#d2453a!important;background:#fde2e1!important}.blank{display:inline-block;min-width:140px;
border-bottom:3px solid #135548;padding:4px 8px;font-weight:700}select{font-size:16px;padding:4px;margin:4px}
#go{background:#135548;color:#fff;border:0;border-radius:10px;padding:12px 22px;font-size:17px;cursor:pointer}
#res{font-size:20px;font-weight:700;color:#135548;margin:12px 0}.ans{display:none;color:#135548;margin-top:8px}
.done .ans{display:block}"""

_JS = """const Q=DATA;const st=Q.map(()=>({}));
function el(t,a,c){const e=document.createElement(t);Object.assign(e,a||{});(c||[]).forEach(x=>e.append(x));return e}
const box=document.getElementById('qs');
Q.forEach((q,i)=>{const d=el('div',{className:'q'});d.append(el('div',{className:'k',textContent:q.label}),
 el('h2',{textContent:(i+1)+'. '+q.question}));
 if(q.kind=='choice'||q.kind=='truefalse'){st[i].p=new Set();q.options.forEach((o,j)=>{const b=el('button',
  {className:'o',textContent:(q.kind=='choice'?'АБВГДЕЄЖ'[j]+') ':'')+o});b.onclick=()=>{if(q.answer.length==1)
  {st[i].p.clear();d.querySelectorAll('.o').forEach(x=>x.classList.remove('sel'))}
  st[i].p.has(j)?st[i].p.delete(j):st[i].p.add(j);b.classList.toggle('sel',st[i].p.has(j))};d.append(b)})}
 if(q.kind=='input'){const bl=el('span',{className:'blank',textContent:'…'});d.append(bl,el('br'));
  q.tiles.forEach(o=>{const b=el('button',{className:'tile',textContent:o});b.onclick=()=>{st[i].v=o;bl.textContent=o};d.append(b)})}
 if(q.kind=='order'){st[i].v=q.shown.map(()=>0);q.shown.forEach((o,j)=>{const s=el('select');
  s.append(el('option',{value:0,textContent:'№'}));q.shown.forEach((_,n)=>s.append(el('option',{value:n+1,textContent:n+1})));
  s.onchange=()=>st[i].v[j]=+s.value;d.append(el('div',{},[s,o]))})}
 if(q.kind=='match'){st[i].v=q.left.map(()=>-1);q.left.forEach((o,j)=>{const s=el('select');
  s.append(el('option',{value:-1,textContent:'—'}));q.shown.forEach((r,n)=>s.append(el('option',{value:n,textContent:'АБВГДЕЄЖ'[n]+') '+r})));
  s.onchange=()=>st[i].v[j]=+s.value;d.append(el('div',{},[o+' → ',s]))})}
 d.append(el('div',{className:'ans',textContent:q.reveal}));q.box=d;box.append(d)});
function ok(q,s){if(q.kind=='choice'||q.kind=='truefalse')return [...s.p].sort().join()==[...q.answer].sort().join();
 if(q.kind=='input')return (s.v||'').trim().toLowerCase()==q.answer.trim().toLowerCase();
 if(q.kind=='order')return q.shown.every((o,j)=>q.options[s.v[j]-1]==o);
 return q.left.every((_,j)=>q.shown[s.v[j]]==q.right[j])}
document.getElementById('go').onclick=()=>{let sc=0,mx=0;Q.forEach((q,i)=>{const g=ok(q,st[i]);mx+=q.points;if(g)sc+=q.points;
 q.box.classList.add('done');q.box.classList.remove('ok','bad');q.box.style.borderLeft='6px solid '+(g?'#2e9d5b':'#d2453a')});
 document.getElementById('res').textContent='Результат: '+sc+' з '+mx+' ('+Math.round(sc*100/mx)+' %)'};"""


def export_html(pres: Presentation, path, title: str = "") -> int:
    data = []
    for s in pres.slides:
        q = s.quiz
        if not q:
            continue
        d = {"kind": q["kind"], "label": KINDS[q["kind"]], "question": q["question"], "points": q.get("points", 1),
             "reveal": answer_text(q)}
        if q["kind"] in ("choice", "truefalse"):
            d.update(options=q["options"], answer=q["answer"])
        elif q["kind"] == "input":
            tiles = list(dict.fromkeys([q["answer"], *q.get("options", [])]))
            random.Random(q["question"]).shuffle(tiles)
            d.update(answer=q["answer"], tiles=tiles)
        elif q["kind"] == "order":
            d.update(options=q["options"], shown=q.get("shown") or q["options"])
        else:
            d.update(left=[l for l, _ in q["options"]], right=[r for _, r in q["options"]],
                     shown=q.get("shown") or [r for _, r in q["options"]])
        data.append(d)
    t = html.escape(title or pres.title or "Квіз")
    page = (f'<!doctype html><html lang="uk"><meta charset="utf-8"><meta name="viewport" content="width=device-width,'
            f'initial-scale=1"><title>{t}</title><style>{_CSS}</style><main><h1>{t}</h1><div id="qs"></div>'
            f'<button id="go">Перевірити</button><div id="res"></div><p class="k">Створено в InterSlide · Офіс ШКОЛА</p>'
            f'</main><script>const DATA={json.dumps(data, ensure_ascii=False).replace("</", "<\\\\/")};{_JS}</script></html>')
    from pathlib import Path
    Path(path).write_text(page, encoding="utf-8")
    return len(data)

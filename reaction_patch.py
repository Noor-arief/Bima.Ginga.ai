from pathlib import Path

p = Path(__file__).with_name("index.html")
s = p.read_text(encoding="utf-8")
marker = "/* BIMAGINGA_REACTION_V1 */"

if marker not in s:
    css = r'''
/* BIMAGINGA_REACTION_V1 */
.msg.user .bubble{position:relative}
.msg-reaction{
  align-self:flex-end;
  margin:-8px 10px 0 0;
  min-width:30px;height:24px;padding:1px 7px;
  display:flex;align-items:center;justify-content:center;
  border-radius:999px;
  background:var(--bg-side);
  border:1px solid var(--active-line);
  box-shadow:0 2px 8px rgba(0,0,0,.18);
  font-size:14px;line-height:1;
  position:relative;z-index:2;
}
@media(max-width:820px){.msg-reaction{margin-right:7px}}
'''
    if "</style>" not in s:
        raise SystemExit("index.html missing </style>; refusing unsafe patch")
    s = s.replace("</style>", css + "\n</style>", 1)

    old = """function makeMsg(role,text){
    var m=document.createElement('div');m.className='msg '+role;
    if(role==='ai'){var w=document.createElement('div');w.className='who';w.textContent='BimaGinga';m.appendChild(w);}
    var b=document.createElement('div');b.className='bubble';if(role==='ai')renderMarkdown(b,text);else b.textContent=text;m.appendChild(b);
    return {row:m,bubble:b};
  }"""
    new = """function shouldBimaReact(text){
    var t=String(text||'').trim().toLowerCase();
    if(!t||t.length>42)return false;
    return /^(udah\??|sudah\??|ok(?:ay)?|oke|sip|nice|mantap|lanjut|lanjutkan|gas|beres|done|makasih|terima kasih|thanks|thank you)[!.? ]*$/.test(t);
  }
  function makeMsg(role,text){
    var m=document.createElement('div');m.className='msg '+role;
    if(role==='ai'){var w=document.createElement('div');w.className='who';w.textContent='BimaGinga';m.appendChild(w);}
    var b=document.createElement('div');b.className='bubble';if(role==='ai')renderMarkdown(b,text);else b.textContent=text;m.appendChild(b);
    if(role==='user'&&shouldBimaReact(text)){var r=document.createElement('span');r.className='msg-reaction';r.setAttribute('aria-label','BimaGinga reacted thumbs up');r.textContent='👍';m.appendChild(r);}
    return {row:m,bubble:b};
  }"""
    if old not in s:
        raise SystemExit("makeMsg anchor changed; refusing unsafe patch")
    s = s.replace(old, new, 1)
    p.write_text(s, encoding="utf-8")
    print("BimaGinga reaction patch applied")
else:
    print("BimaGinga reaction patch already applied")

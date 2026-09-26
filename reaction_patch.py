from pathlib import Path

p = Path(__file__).with_name("index.html")
s = p.read_text(encoding="utf-8")
marker = "/* BIMAGINGA_REACTION_V1 */"

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

old_make = """function makeMsg(role,text){
    var m=document.createElement('div');m.className='msg '+role;
    if(role==='ai'){var w=document.createElement('div');w.className='who';w.textContent='BimaGinga';m.appendChild(w);}
    var b=document.createElement('div');b.className='bubble';if(role==='ai')renderMarkdown(b,text);else b.textContent=text;m.appendChild(b);
    return {row:m,bubble:b};
  }"""
new_make = """function shouldBimaReact(text){
    var t=String(text||'').trim().toLowerCase();
    if(!t||t.length>60)return false;
    if(/^(udah|sudah|ok|okay|oke|sip|nice|mantap|lanjut|lanjutkan|gas|beres|done|makasih|terima kasih|thanks|thank you)[!.? ]*$/.test(t))return true;
    if(/^(halo|hai|hi|hey)(\\s+(bima|bimaginga))?[!.? ]*$/.test(t))return true;
    return false;
  }
  function makeMsg(role,text){
    var m=document.createElement('div');m.className='msg '+role;
    if(role==='ai'){var w=document.createElement('div');w.className='who';w.textContent='BimaGinga';m.appendChild(w);}
    var b=document.createElement('div');b.className='bubble';if(role==='ai')renderMarkdown(b,text);else b.textContent=text;m.appendChild(b);
    if(role==='user'&&shouldBimaReact(text)){var r=document.createElement('span');r.className='msg-reaction';r.setAttribute('aria-label','BimaGinga reacted thumbs up');r.textContent='👍';m.appendChild(r);}
    return {row:m,bubble:b};
  }"""

# First deployment may already have mutated index.html in Railway only; repository index remains canonical.
# Apply/reapply deterministically at container startup without touching any other UI/chat behavior.
if marker not in s:
    if "</style>" not in s:
        raise SystemExit("index.html missing </style>; refusing unsafe patch")
    s = s.replace("</style>", css + "\n</style>", 1)
    if old_make not in s:
        raise SystemExit("makeMsg anchor changed; refusing unsafe patch")
    s = s.replace(old_make, new_make, 1)
else:
    # Upgrade an already-patched runtime copy if present.
    start = s.find("function shouldBimaReact(text){")
    end = s.find("\n  function renderThread()", start)
    if start < 0 or end < 0:
        raise SystemExit("existing reaction patch structure changed; refusing unsafe patch")
    s = s[:start] + new_make + s[end:]

# Explicit owner-approved roadmap writes are privileged execution tasks even if the
# user previously selected an advisory skill such as Planner/Researcher. Force only
# this narrow intent back to custom_task; ordinary skill behavior remains unchanged.
roadmap_anchor = """text=(text||'').trim(); if(!text&&!pendingAttachments.length) return;
    if(skill&&SKILLS[skill]) state.activeSkill=skill;"""
roadmap_replacement = """text=(text||'').trim(); if(!text&&!pendingAttachments.length) return;
    if(skill&&SKILLS[skill]) state.activeSkill=skill;
    var roadmapWrite=/\\b(roadmap|issue)\\b/i.test(text)&&/\\b(update|write|tulis|ubah|edit)\\b/i.test(text)&&/\\b(approve|approved|setuju|izinkan|ijin|izin)\\b/i.test(text);
    if(roadmapWrite) state.activeSkill='custom_task';"""
if roadmap_replacement not in s:
    if roadmap_anchor not in s:
        raise SystemExit("send() anchor changed; refusing unsafe roadmap routing patch")
    s = s.replace(roadmap_anchor, roadmap_replacement, 1)

p.write_text(s, encoding="utf-8")
print("BimaGinga reaction patch V3 + roadmap routing applied")

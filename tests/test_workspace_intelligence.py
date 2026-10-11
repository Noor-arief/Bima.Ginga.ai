import base64
import json
import os
from types import SimpleNamespace as NS
from unittest.mock import patch

os.environ.setdefault('BIMAGINGA_DATA_DIR', '/tmp/bimaginga-intelligence-tests')

import app
import executor
import task_store
from file_intelligence import analyze_csv, inspect_python
from workspace_context import context_query, normalized_history, select_memory, timestamp_seconds
from router import route_message
from fastapi import HTTPException
import pytest


def test_continuation_inherits_context_but_new_topic_does_not():
    h = [{'role':'user','content':'Audit Quant'}, {'role':'ai','text':'Periksa momentum'}]
    assert 'momentum' in context_query('lanjut', h)
    assert context_query('halo', h) == 'halo'
    assert context_query('lanjut proyek Jelnusa', h) == 'lanjut proyek Jelnusa'
    assert normalized_history(h)[1]['role'] == 'assistant'


def test_saved_memory_new_correction_first_and_no_unrelated_project():
    old={'title':'Vireqo','updated_at':100,'messages':[{'role':'user','text':'Vireqo warna merah'}]}
    new={'title':'Vireqo','updated_at':200,'messages':[{'role':'user','text':'Koreksi: Vireqo warna teal'}]}
    unrelated={'title':'Quant','updated_at':300,'messages':[{'role':'user','text':'Quant warna biru'}]}
    result=select_memory('ingat warna Vireqo', [], [old, unrelated, new])
    assert result.index('warna teal') < result.index('warna merah')
    assert 'warna biru' not in result
    assert select_memory('ingat Jelnusa', [], [old]) == ''


def test_saved_timestamp_milliseconds_and_seconds():
    assert timestamp_seconds(1791700000000) == 1791700000
    assert timestamp_seconds(1791700000) == 1791700000


def test_csv_numbers_and_python_syntax_are_computed_without_execution():
    r=analyze_csv('name,total\nA,10\nB,20\nC,\n')
    assert r['rows']==3 and r['numeric']['2:total']['sum']==30
    assert r['empty_cells']==1
    r=inspect_python('def hello(:\n pass')
    assert r['valid_syntax'] is False and r['line']==1
    assert inspect_python('raise RuntimeError("must not run")')['executed'] is False


def test_attachment_contains_verified_calculation():
    a=app.Attachment(name='sample.csv',type='text/csv',data=base64.b64encode(b'name,total\nA,10\nB,20').decode())
    result=app.attachment_context([a])
    assert 'SERVER CSV ANALYSIS' in result and '30.0' in result


def test_writing_does_not_require_execution():
    assert route_message('perbaiki kalimat bahasa Inggris ini').kind=='chat'
    assert route_message('perbaiki kode di repo').kind=='execution'


def test_oversized_csv_field_does_not_break_chat():
    a=app.Attachment(name='large.csv',type='text/csv',data=base64.b64encode(('title\n'+'x'*150000).encode()).decode())
    assert 'SERVER CSV ANALYSIS unavailable' in app.attachment_context([a])


def test_auth_boundary_preserved(monkeypatch):
    monkeypatch.setenv('BIMAGINGA_OWNER_KEY','test-key')
    with pytest.raises(HTTPException) as e:
        app.chat(app.ChatRequest(message='perbaiki kode di repo'), x_bima_key=None)
    assert e.value.status_code==401


def test_context_saved_with_task_and_passed_to_worker(tmp_path, monkeypatch):
    monkeypatch.setattr(task_store,'STORE',tmp_path/'tasks.json')
    task=task_store.create_task('audit source','code_debug',context='previous source and constraints')
    seen={}
    def execute(message, skill, context=''):
        seen['context']=context
        return {'answer':'verified', 'evidence':[{'ok':True}], 'terminal_state':'completed'}
    monkeypatch.setattr(app,'execute_task',execute)
    app.run_task(task['id'])
    assert seen['context']=='previous source and constraints'
    assert task_store.get_task(task['id'])['state']=='completed'


def test_personal_memory_not_blocked_by_unavailable_github(monkeypatch):
    monkeypatch.setattr(app,'canonical_project_context',lambda _: '')
    monkeypatch.setattr(app,'load_conversations',lambda: [])
    monkeypatch.setattr(app,'update_project_state_from_turn',lambda *args: None)
    monkeypatch.setattr(app,'model_answer',lambda prompt, **kwargs: ('Answer','mock'))
    assert app.chat(app.ChatRequest(message='ingat nama panggilan tadi?'))['answer']=='Answer'
    with pytest.raises(HTTPException) as e:
        app.chat(app.ChatRequest(message='checkpoint roadmap sekarang?'))
    assert e.value.status_code==503


def test_new_casual_topic_does_not_fetch_old_project(monkeypatch):
    def forbidden(*args): raise AssertionError('unrelated context fetched')
    monkeypatch.setattr(app,'canonical_project_context',forbidden)
    monkeypatch.setattr(app,'persistent_workspace_context',forbidden)
    monkeypatch.setattr(app,'trading_runtime_context',forbidden)
    monkeypatch.setattr(app,'model_answer',lambda prompt, **kwargs: ('Halo','mock'))
    monkeypatch.setattr(app,'update_project_state_from_turn',lambda *args: None)
    assert app.chat(app.ChatRequest(message='halo',history=[{'role':'user','text':'project Quant'}]))['answer']=='Halo'


def fake_client(monkeypatch, replies):
    seen=[]
    def create(**kwargs):
        seen.append(kwargs)
        return NS(choices=[NS(message=replies.pop(0))])
    monkeypatch.setenv('DEEPSEEK_API_KEY','test-placeholder')
    monkeypatch.setattr(executor,'OpenAI',lambda **kwargs: NS(chat=NS(completions=NS(create=create))))
    return seen


def test_worker_no_tools_cannot_claim_completed(monkeypatch):
    fake_client(monkeypatch,[NS(content='Sudah selesai', tool_calls=None)])
    assert executor.execute_task('audit file','inspect')['terminal_state']=='blocked'


def test_worker_uses_reference_context_and_actual_local_tool(monkeypatch):
    call=NS(id='1',function=NS(name='inspect_python',arguments=json.dumps({'source':'def hello():\n return 1'})))
    seen=fake_client(monkeypatch,[NS(content=None,tool_calls=[call]),NS(content='Syntax valid; code not executed',tool_calls=None)])
    result=executor.execute_task('inspect this code','inspect',context='user wants no execution')
    assert result['terminal_state']=='completed'
    assert result['evidence'][0]['summary']['executed'] is False
    assert any('no execution' in m.get('content','') for m in seen[0]['messages'] if isinstance(m,dict))


def test_unconfigured_integrations_are_not_advertised(monkeypatch):
    for key in ['BIMA_GITHUB_TOKEN','BIMA_GITHUB_ALLOWED_REPOS','BIMA_RAILWAY_TOKEN','BIMA_RAILWAY_ALLOWED_PROJECTS']:
        monkeypatch.delenv(key,raising=False)
    assert {x['function']['name'] for x in executor.available_tools()}=={'inspect_python','analyze_csv'}

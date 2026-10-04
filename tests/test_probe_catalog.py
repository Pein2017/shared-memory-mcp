"""Check sanitized catalog collection with a local stub; no native clients run."""
import json
from urllib.error import HTTPError
from urllib.request import Request,urlopen

import pytest
from native_startup_probe import Provider,TOOLS


@pytest.mark.parametrize('namespace',['shared_memory','shared-memory'])
def test_probe_collects_only_the_seven_namespaced_memory_tools(namespace):
    provider = Provider('sentinel','fixture-id')
    names = [f'mcp__{namespace}__{name}' for name in TOOLS]
    tools = [{'name':name,'input_schema':{'type':'object','properties':{'context':{'type':'object'}}}}
             for name in names+['read','mcp__other__delete',f'mcp__{namespace}__memory_read']]
    try:
        request = Request(provider.url,data=json.dumps({'tools':tools}).encode(),headers={'Content-Type':'application/json'})
        with pytest.raises(HTTPError) as error:
            urlopen(request,timeout=3)
        assert error.value.code == 400
        assert provider.requests[0]['memory_tools'] == sorted(names)
        assert provider.requests[0]['memory_schema_tools'] == sorted(names)
    finally:
        provider.close()


def test_probe_does_not_infer_memory_tools_from_untrusted_namespace_or_metadata():
    provider = Provider('sentinel','fixture-id')
    def function(name):
        return {'type':'function','name':name,'parameters':{'type':'object','properties':{'context':{}}}}
    tools = [function('read'),function('search'),
             {'type':'namespace','name':'mcp__other','tools':[function('read'),function('mcp__shared_memory__search')]},
             {'type':'namespace','name':'mcp__shared_memory','tools':[function('memory_read'),
                 {'type':'object','name':'read','parameters':{'type':'object','properties':{'context':{}}}},
                 {'type':'namespace','name':'mcp__nested_other','tools':[function('read')]}]},
             {'type':'object','name':'mcp__shared_memory','tools':[function('read')]}]
    try:
        request = Request(provider.url,data=json.dumps({'tools':tools}).encode(),headers={'Content-Type':'application/json'})
        with pytest.raises(HTTPError) as error:
            urlopen(request,timeout=3)
        assert error.value.code == 400
        assert provider.requests[0]['memory_tools'] == []
        assert provider.requests[0]['memory_schema_tools'] == []
    finally:
        provider.close()


@pytest.mark.parametrize('namespace',['shared_memory','shared-memory'])
@pytest.mark.parametrize('location',['tools','additional_tools'])
def test_probe_collects_simple_functions_inside_exact_memory_namespace(namespace,location):
    provider = Provider('sentinel','fixture-id')
    names = [f'mcp__{namespace}__{name}' for name in TOOLS]
    def function(name):
        return {'type':'function','name':name,'parameters':{'type':'object','properties':{'context':{'type':'object'}}}}
    tools = [{'type':'namespace','name':f'mcp__{namespace}','tools':[function(name) for name in TOOLS+['memory_read']]+[
                 {'type':'object','name':'read','parameters':{'type':'object','properties':{'context':{}}}},
                 {'type':'namespace','name':'mcp__nested_other','tools':[function('read')]}]},
             function('read'),function('search'),
             {'type':'namespace','name':'mcp__other','tools':[function(name) for name in TOOLS]+[function(f'mcp__{namespace}__read')]},
             {'type':'object','name':f'mcp__{namespace}','tools':[function('read')]}]
    body = {'tools':tools} if location == 'tools' else {'input':[{'type':'additional_tools','tools':tools}]}
    try:
        request = Request(provider.url,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
        with pytest.raises(HTTPError) as error:
            urlopen(request,timeout=3)
        assert error.value.code == 400
        assert provider.requests[0]['memory_tools'] == sorted(names)
        assert provider.requests[0]['memory_schema_tools'] == sorted(names)
    finally:
        provider.close()

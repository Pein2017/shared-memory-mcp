"""Portable wheel assets and SDK metadata, without changing the runtime install."""
import base64
import json
import os
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET


def test_wheel_installed_outside_checkout_has_self_contained_icon_metadata(tmp_path):
    source = Path(__file__).parents[1]
    packaged_logo = source/'src/shared_memory_mcp/assets/logo.svg'
    skill_logo = source/'skills/shared-memory/assets/logo.svg'
    assert packaged_logo.read_bytes() == skill_logo.read_bytes()
    tree = ET.fromstring(packaged_logo.read_bytes())
    assert tree.tag == '{http://www.w3.org/2000/svg}svg'
    for element in tree.iter():
        assert element.tag.rsplit('}',1)[-1] not in {'script','image','foreignObject'}
        assert all(not key.endswith('href') for key in element.attrib)
    wheels = tmp_path/'wheels'
    built = subprocess.run(['python','-m','pip','wheel',str(source),'--no-deps','--no-build-isolation',
                            '--wheel-dir',str(wheels)],capture_output=True,text=True)
    assert built.returncode == 0, built.stdout+built.stderr
    wheel, = wheels.glob('shared_memory_mcp-0.2.0-*.whl')
    installed = tmp_path/'installed'
    result = subprocess.run(['python','-m','pip','install','--no-deps','--target',str(installed),str(wheel)],
                            capture_output=True,text=True)
    assert result.returncode == 0, result.stdout+result.stderr
    script = '''import asyncio,base64,json,os,sys
from importlib.metadata import version
from importlib.resources import files
import shared_memory_mcp
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
async def verify():
 params=StdioServerParameters(command=sys.executable,args=['-m','shared_memory_mcp.server','--root',sys.argv[1]],env=dict(os.environ),cwd=os.getcwd())
 async with stdio_client(params) as (read,write):
  async with ClientSession(read,write) as session:
   initialized=await session.initialize()
   tools=await session.list_tools()
   icon=initialized.serverInfo.icons[0]
   logo=files('shared_memory_mcp').joinpath('assets/logo.svg').read_bytes()
   assert base64.b64decode(icon.src.split(',',1)[1])==logo
   assert initialized.serverInfo.websiteUrl=='https://github.com/Pein2017/shared-memory-mcp'
   assert {t.name for t in tools.tools}=={'context','search','read','create','approve','update','delete','capture','curate'}
   assert all(t.title and t.icons==initialized.serverInfo.icons for t in tools.tools)
   print(json.dumps({'module':shared_memory_mcp.__file__,'version':version('shared-memory-mcp'),'logo':base64.b64encode(logo).decode(),'tools':len(tools.tools)}))
asyncio.run(verify())
'''
    outside = tmp_path/'outside';outside.mkdir()
    env = {**os.environ,'PYTHONPATH':str(installed)}
    verified = subprocess.run(['python','-c',script,str(tmp_path/'unused-store')],env=env,cwd=outside,
                              capture_output=True,text=True)
    assert verified.returncode == 0, verified.stdout+verified.stderr
    receipt = json.loads(verified.stdout)
    assert Path(receipt['module']).is_relative_to(installed)
    assert receipt['version'] == '0.2.0' and receipt['tools'] == 9
    assert base64.b64decode(receipt['logo']) == packaged_logo.read_bytes()

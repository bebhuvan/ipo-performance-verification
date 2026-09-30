"""Minimal MCP client for mcp.nseindia.in (streamable HTTP, SSE responses)."""
import json, requests
class MCP:
    def __init__(self, url):
        self.url=url; self.s=requests.Session(); self.sid=None; self.n=0
        self.h={'Content-Type':'application/json','Accept':'application/json, text/event-stream'}
        r=self._rpc('initialize',{'protocolVersion':'2025-06-18','capabilities':{},'clientInfo':{'name':'ipo-verify','version':'0.1'}})
        self.s.post(url,headers={**self.h,'Mcp-Session-Id':self.sid},json={'jsonrpc':'2.0','method':'notifications/initialized'},timeout=30)
    def _rpc(self,method,params):
        self.n+=1; h=dict(self.h)
        if self.sid: h['Mcp-Session-Id']=self.sid
        r=self.s.post(self.url,headers=h,json={'jsonrpc':'2.0','id':self.n,'method':method,'params':params},timeout=60)
        self.sid=self.sid or r.headers.get('Mcp-Session-Id')
        for line in r.text.splitlines():
            if line.startswith('data:'):
                return json.loads(line[5:])
        return r.json()
    def tools(self): return self._rpc('tools/list',{})
    def call(self,name,args): return self._rpc('tools/call',{'name':name,'arguments':args})

"""
Phone-width check for every page. Loads each page in a 390px-wide frame in headless Chrome and reports:
  * pages whose document scrolls sideways
  * elements that stick out past the right or left edge and are not inside their own scroll container
    (this also catches content that is silently clipped because the page hides horizontal overflow)
  * pages with no viewport meta tag
    python tools/phone_check.py [--width 390] [--only substring]
Needs Google Chrome and internet access (fonts). Takes a few minutes for the whole site.
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "Strokes Edge Website HTML")
CHROME = os.environ.get("CHROME_PATH", r"C:\Program Files\Google\Chrome\Application\chrome.exe")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HARNESS = r"""<!doctype html><meta charset="utf-8"><body style="margin:0"><pre id="out"></pre><div id="wrap"></div>
<script>
var pages=__PAGES__,VW=__VW__,res={},n=0,wrap=document.getElementById('wrap');
function measure(f){
  var d=f.contentDocument,w=f.contentWindow,root=d.documentElement;
  var sw=Math.max(root.scrollWidth,d.body?d.body.scrollWidth:0),off=[];
  var all=d.querySelectorAll('body *');
  for(var i=0;i<all.length&&off.length<4;i++){
    var e=all[i],r=e.getBoundingClientRect();
    if(r.width===0||r.height===0)continue;
    if(r.right>VW+1.5||r.left<-1.5){
      var a=e.parentElement,clipped=false;
      while(a&&a!==d.body&&a!==root){
        var cs=w.getComputedStyle(a);
        if(/(auto|scroll|hidden|clip)/.test(cs.overflowX)){var ar=a.getBoundingClientRect();if(ar.right<=VW+1.5&&ar.left>=-1.5){clipped=true;break}}
        a=a.parentElement;
      }
      if(!clipped){
        var cls=(typeof e.className==='string'?e.className:'');
        off.push(e.tagName.toLowerCase()+(cls?'.'+cls.split(' ')[0]:'')+' right='+Math.round(r.right)+' "'+(e.textContent||'').trim().slice(0,28)+'"');
      }
    }
  }
  return {sw:sw,overflow:sw>VW+1,viewport:!!d.querySelector('meta[name=viewport]'),offenders:off};
}
pages.forEach(function(p){
  var f=document.createElement('iframe');
  f.src=p;f.style.cssText='width:'+VW+'px;height:800px;border:0;display:block';
  f.onload=function(){var fr=f.contentWindow.document.fonts;(fr&&fr.ready?fr.ready:Promise.resolve()).then(function(){setTimeout(function(){
    try{res[p]=measure(f)}catch(e){res[p]={error:String(e)}}
    if(++n===pages.length)document.getElementById('out').textContent='RESULT:'+JSON.stringify(res)+':END';
  },900)})};
  wrap.appendChild(f);
});
</script>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--width", type=int, default=390)
    ap.add_argument("--only")
    ap.add_argument("--batch", type=int, default=6)
    a = ap.parse_args()

    pages = sorted(os.path.basename(p) for p in glob.glob(os.path.join(SITE, "*.html")))
    pages = [p for p in pages if p != "favicon-head-snippet.html" and (not a.only or any(x in p for x in a.only.split(",")))]

    class Quiet(SimpleHTTPRequestHandler):
        def log_message(self, *args, **kwargs):
            pass

    handler = partial(Quiet, directory=SITE)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    harness_name = "_phone_harness.html"
    harness_path = os.path.join(SITE, harness_name)

    results = {}
    try:
        for i in range(0, len(pages), a.batch):
            chunk = pages[i:i + a.batch]
            html = HARNESS.replace("__PAGES__", json.dumps(chunk)).replace("__VW__", str(a.width))
            open(harness_path, "w", encoding="utf-8").write(html)
            r = subprocess.run([CHROME, "--headless=new", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
                                "--window-size=%d,900" % (a.width + 40), "--virtual-time-budget=25000", "--dump-dom",
                                "http://127.0.0.1:%d/%s" % (port, harness_name)],
                               capture_output=True, text=True, timeout=240, encoding="utf-8", errors="replace")
            m = re.search(r"RESULT:(.*?):END", r.stdout, re.S)
            if not m:
                for p in chunk:
                    results[p] = {"error": "no result from Chrome"}
                continue
            data = json.loads(re.sub(r"&quot;", '"', m.group(1).replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")))
            results.update(data)
            print("checked %d/%d" % (min(i + a.batch, len(pages)), len(pages)), flush=True)
    finally:
        srv.shutdown()
        if os.path.exists(harness_path):
            os.remove(harness_path)

    bad = {p: r for p, r in results.items() if r.get("error") or r.get("overflow") or r.get("offenders") or not r.get("viewport")}
    print("\nPHONE CHECK at %dpx: %d pages checked, %d with problems" % (a.width, len(results), len(bad)))
    for p, r in sorted(bad.items()):
        if r.get("error"):
            print(" -", p, "ERROR", r["error"])
            continue
        flags = []
        if r.get("overflow"):
            flags.append("scrolls sideways (width %d)" % r["sw"])
        if not r.get("viewport"):
            flags.append("no viewport meta")
        print(" -", p, "|", "; ".join(flags) if flags else "", "|", " ; ".join(r.get("offenders", [])))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

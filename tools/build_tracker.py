"""
Builds picks.html, the Pick Tracker: the whole record is public (summary, chart, by bet type, by tournament,
every settled bet) and only "open bets this week" sits behind the weekly access code.

The access codes are read from the existing picks.html (the line starting `var validCodes=[`) and written
back unchanged, so the weekly step (add the new code to that array, never remove old ones) still works.
Re-running this tool never loses a code. Safe to re-run.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sitepage import render_page, SITE  # noqa: E402

PICKS = os.path.join(SITE, "picks.html")
existing = open(PICKS, encoding="utf-8").read()
m = re.search(r"var validCodes=\[(.*?)\];", existing, re.S)
if not m:
    raise SystemExit("could not find the validCodes array in picks.html, refusing to rebuild")
CODES = m.group(1)

CSS = r"""
.stat-row{grid-template-columns:repeat(4,1fr)}
.stat-row b.pos{color:var(--g)}
.lockbox{background:var(--sur);border:1px solid var(--bdr);border-radius:4px;padding:24px;margin:1rem 0 2rem}
.lockbox p{margin:0 0 12px;color:var(--txt)}
.code-form{display:flex;gap:10px;flex-wrap:wrap;margin:6px 0 10px}
.code-form input{flex:1;min-width:200px;background:var(--bg);color:var(--txt);border:1px solid var(--bdr);border-radius:2px;padding:13px 12px;font:400 16px/1.2 'DM Mono',monospace;letter-spacing:.08em;text-transform:uppercase}
.code-form input:focus{outline:2px solid var(--g);outline-offset:1px}
.code-form button{border:0;cursor:pointer;margin:0}
.lockmsg{color:var(--r)!important;font:400 13px/1.5 'DM Mono',monospace}
.lockmini{font-size:14px;color:var(--txt2)!important}
.ledger-tools{display:flex;gap:10px;flex-wrap:wrap;margin:6px 0 12px}
.ledger-tools input,.ledger-tools select{background:var(--bg);color:var(--txt);border:1px solid var(--bdr);border-radius:2px;padding:11px 12px;font:400 14px/1.2 'DM Mono',monospace}
.ledger-tools input{flex:1;min-width:220px}
.ledgerwrap{max-height:640px;overflow:auto;border:1px solid var(--bdr2);border-radius:3px}
.ledgerwrap table{margin:0;min-width:760px}
.ledgerwrap th{position:sticky;top:0;background:var(--sur);z-index:1}
.pl-pos{color:var(--g)!important}
.pl-neg{color:var(--r)!important}
.tkmeta{font:400 12px/1.6 'DM Mono',monospace;letter-spacing:.04em;color:var(--txt2);margin:10px 0 0}
@media(max-width:860px){.stat-row{grid-template-columns:repeat(2,1fr)}}
"""

BODY = r"""
<div id="trk-stats" aria-live="polite"><div class="stat-row"><div><b>&hellip;</b><span>Net result</span></div><div><b>&hellip;</b><span>ROI on settled bets</span></div><div><b>&hellip;</b><span>Cashed - lost</span></div><div><b>&hellip;</b><span>Tournaments</span></div></div></div>
<noscript><p>The tracker reads the live bet record with JavaScript. Enable it to see the numbers.</p></noscript>

<h2>Cumulative result</h2>
<div class="chart" id="trk-chart"><p>The chart appears once the live record loads.</p></div>
<p class="tkmeta">Every settled bet, oldest to newest, losses included. A few hundred bets at long odds is a small sample, so results swing a lot from week to week.</p>

<h2>Open bets this week</h2>
<div class="lockbox" id="lockbox">
  <p>This week's open bets are for newsletter subscribers. Enter the code from this week's email.</p>
  <form class="code-form" id="code-form" autocomplete="off">
    <input id="code-in" type="text" placeholder="ACCESS CODE" aria-label="Weekly access code" autocomplete="off">
    <button class="btn" type="submit">Unlock</button>
  </form>
  <p class="lockmsg" id="code-err" hidden>Invalid code. Check this week's newsletter.</p>
  <p class="lockmini">No code yet? <a href="https://strokesedge.substack.com" data-signup>Get the free weekly picks</a> and it arrives with the email.</p>
</div>
<div id="open-wrap" hidden></div>

<h2>By bet type</h2>
<div class="tablewrap"><table id="by-type"></table></div>
<p class="tkmeta">Parlays are grouped together, and every bet is in every total. Small samples, such as the handful of top 5 bets, swing a lot.</p>

<h2>By tournament</h2>
<div class="tablewrap"><table id="by-tourn"></table></div>

<h2>Every settled bet</h2>
<div class="ledger-tools">
  <input id="led-q" type="search" placeholder="Search player or tournament" aria-label="Search the ledger">
  <select id="led-res" aria-label="Filter by result"><option value="">All results</option><option value="cashed">Cashed</option><option value="lost">Lost</option></select>
</div>
<div class="ledgerwrap"><table id="ledger"></table></div>
<p class="tkmeta" id="led-count"></p>

<div class="callout"><p>How this is calculated: profit is total payout (stake included) minus total staked, across settled bets only. A bet counts as cashed when it won or placed. Open bets are excluded until they settle. The record comes straight from the sheet behind this page, so nothing is edited or filtered. <span id="dq"></span></p></div>
"""

JS = r"""<script>
(function(){
  var D='https://docs.google.com/spreadsheets/d/e/2PACX-1vRn7eBjHWBs4nag5K5QHxnKiyeC-UEobNINAfjmEKsnBgX6aqm3lEZCY1i4lg5t5Lwy3I2p8ZLrR4Gc/pub?gid=0&single=true&output=csv';
  var NL=String.fromCharCode(10);
  var $=function(id){return document.getElementById(id)};
  function line(l){var r=[],c='',q=false;for(var i=0;i<l.length;i++){var ch=l[i];if(ch==='"'){q=!q}else if(ch===','&&!q){r.push(c);c=''}else{c+=ch}}r.push(c);return r}
  function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}
  function money(n){return (n<0?'-':'+')+'$'+Math.abs(n).toLocaleString('en-US',{maximumFractionDigits:0})}
  function odds(o){return /^-?[0-9]+$/.test(o)&&parseInt(o,10)>0?'+'+o:o}
  /* group the free-text bet types: the sheet has 60 spellings */
  function kind(t){
    var l=String(t).trim().toLowerCase();
    if(l.indexOf('parlay')>-1)return 'Parlays';
    if(l.indexOf('h2h')===0)return 'Head-to-head';
    var m=l.match(/^top (5|10|20|30|40)( |$|[(])/);
    if(m&&l.indexOf('/')===-1)return 'Top '+m[1];
    if(l.indexOf('e/w')>-1||l.indexOf('ew ')===0)return 'Each-way winner';
    if(l.indexOf('winner')>-1&&l.indexOf('group')===-1)return 'Outright winner';
    if(l==='make cut')return 'Make cut';
    return 'Other';
  }
  var dq=0;
  /* cashed = won or placed. Anything that is not open, won, placed or lost is a typo in the sheet:
     count it by its payout (stake back or more = cashed) and say so on the page. */
  function status(r){
    var s=(r.result||'open').toLowerCase().trim();
    if(s==='open')return 'open';
    if(s==='won'||s==='placed')return 'cashed';
    if(s==='lost')return 'lost';
    dq++;return (parseFloat(r.payout)||0)>=(parseFloat(r.wager)||0)&&(parseFloat(r.payout)||0)>0?'cashed':'lost';
  }
  var settled=[],openRows=[];
  function pl(r){return (parseFloat(r.payout)||0)-(parseFloat(r.wager)||0)}
  function plc(n){return n<0?'pl-neg':n>0?'pl-pos':''}

  function paint(csv){
    var L=csv.trim().split(NL),H=line(L[0]).map(function(h){return h.trim().toLowerCase()}),rows=[];
    for(var i=1;i<L.length;i++){if(!L[i].trim())continue;var v=line(L[i]),o={};H.forEach(function(h,k){o[h]=(v[k]||'').trim()});if(o.player)rows.push(o)}
    rows.forEach(function(r){r._s=status(r);if(r._s==='open')openRows.push(r);else settled.push(r)});
    if(!settled.length){$('trk-stats').innerHTML='<p>No settled bets to show yet.</p>';return}
    var wag=0,ret=0,lost=0,cashed=0,tn={};
    settled.forEach(function(r){wag+=parseFloat(r.wager)||0;ret+=parseFloat(r.payout)||0;if(r._s==='lost')lost++;else cashed++;tn[r.tournament]=1});
    var net=ret-wag,roi=wag>0?net/wag*100:0;
    $('trk-stats').innerHTML='<div class="stat-row">'
      +'<div><b class="'+(net<0?'neg':'pos')+'">'+money(net)+'</b><span>Net result</span></div>'
      +'<div><b class="'+(roi<0?'neg':'pos')+'">'+(roi>=0?'+':'')+roi.toFixed(1)+'%</b><span>ROI on settled bets</span></div>'
      +'<div><b>'+cashed+'-'+lost+'</b><span>Cashed - lost</span></div>'
      +'<div><b>'+Object.keys(tn).length+'</b><span>Tournaments</span></div></div>';
    if(dq)$('dq').textContent=dq+' bet'+(dq>1?'s have':' has')+' a result label the page does not recognize and '+(dq>1?'are':'is')+' counted by payout.';

    /* chart: the sheet lists the newest tournament first, so reverse to run oldest to newest */
    var cum=0,pts=[0];settled.slice().reverse().forEach(function(r){cum+=pl(r);pts.push(cum)});
    var W=720,Hh=260,P=34,mn=Math.min.apply(null,pts),mx=Math.max.apply(null,pts);if(mn===mx){mn-=1;mx+=1}
    function X(k){return P+k*(W-2*P)/(pts.length-1)}function Y(v){return Hh-P-(v-mn)*(Hh-2*P)/(mx-mn)}
    var d=pts.map(function(v,k){return (k?'L':'M')+X(k).toFixed(1)+' '+Y(v).toFixed(1)}).join(' ');
    $('trk-chart').innerHTML='<svg viewBox="0 0 '+W+' '+Hh+'" role="img" aria-label="Cumulative net result across '+settled.length+' settled bets, ending at '+money(net)+'">'
      +'<line x1="'+P+'" x2="'+(W-P)+'" y1="'+Y(0).toFixed(1)+'" y2="'+Y(0).toFixed(1)+'" stroke="rgba(255,255,255,.18)" stroke-dasharray="4 4"/>'
      +'<path d="'+d+'" fill="none" stroke="#00e676" stroke-width="2" stroke-linejoin="round"/>'
      +'<text x="'+P+'" y="16" fill="#8da398" font-size="11" font-family="DM Mono,monospace">'+money(mx)+'</text>'
      +'<text x="'+P+'" y="'+(Hh-8)+'" fill="#8da398" font-size="11" font-family="DM Mono,monospace">'+money(mn)+'</text>'
      +'<text x="'+(W-P)+'" y="'+(Hh-8)+'" text-anchor="end" fill="#8da398" font-size="11" font-family="DM Mono,monospace">'+settled.length+' settled bets</text></svg>';

    /* by bet type */
    var ty={},tord=[];
    settled.forEach(function(r){var k=kind(r.type);if(!ty[k]){ty[k]={n:0,c:0,w:0,p:0};tord.push(k)}var o=ty[k];o.n++;if(r._s==='cashed')o.c++;o.w+=parseFloat(r.wager)||0;o.p+=parseFloat(r.payout)||0});
    tord.sort(function(a,b){return ty[b].n-ty[a].n});
    var h='<tr><th>Bet type</th><th>Bets</th><th>Cashed</th><th>Hit rate</th><th>Staked</th><th>Net</th><th>ROI</th></tr>';
    tord.forEach(function(k){var o=ty[k],n=o.p-o.w;h+='<tr><td>'+esc(k)+'</td><td>'+o.n+'</td><td>'+o.c+'</td><td>'+(o.c/o.n*100).toFixed(0)+'%</td><td>$'+o.w.toFixed(0)+'</td><td class="'+plc(n)+'">'+money(n)+'</td><td class="'+plc(n)+'">'+(n/o.w*100>=0?'+':'')+(n/o.w*100).toFixed(1)+'%</td></tr>'});
    h+='<tr><td><b>All bets</b></td><td><b>'+settled.length+'</b></td><td><b>'+cashed+'</b></td><td><b>'+(cashed/settled.length*100).toFixed(0)+'%</b></td><td><b>$'+wag.toFixed(0)+'</b></td><td class="'+plc(net)+'"><b>'+money(net)+'</b></td><td class="'+plc(net)+'"><b>'+(roi>=0?'+':'')+roi.toFixed(1)+'%</b></td></tr>';
    $('by-type').innerHTML=h;

    /* by tournament, newest first (sheet order) */
    var bt={},order=[];
    settled.forEach(function(r){var t=r.tournament;if(!bt[t]){bt[t]={n:0,w:0,p:0};order.push(t)}bt[t].n++;bt[t].w+=parseFloat(r.wager)||0;bt[t].p+=parseFloat(r.payout)||0});
    var h2='<tr><th>Tournament</th><th>Bets</th><th>Staked</th><th>Net</th></tr>';
    order.forEach(function(t){var o=bt[t],n=o.p-o.w;h2+='<tr><td>'+esc(t)+'</td><td>'+o.n+'</td><td>$'+o.w.toFixed(0)+'</td><td class="'+plc(n)+'">'+money(n)+'</td></tr>'});
    $('by-tourn').innerHTML=h2;

    drawLedger();
    if(unlocked())showOpen();
  }

  /* ledger */
  function drawLedger(){
    var q=($('led-q').value||'').toLowerCase().trim(),rs=$('led-res').value;
    var rowsHtml='',shown=0;
    settled.forEach(function(r){
      if(rs&&r._s!==rs)return;
      if(q&&(r.player+' '+r.tournament+' '+r.type).toLowerCase().indexOf(q)===-1)return;
      var n=pl(r);shown++;
      rowsHtml+='<tr><td>'+esc(r.date)+'</td><td>'+esc(r.tournament)+'</td><td>'+esc(r.player)+'</td><td>'+esc(r.type)+'</td><td>'+esc(odds(r.odds))+'</td><td>$'+(parseFloat(r.wager)||0).toFixed(0)+'</td><td class="'+plc(n)+'">'+money(n)+'</td><td>'+(r._s==='cashed'?'Cashed':'Lost')+'</td></tr>';
    });
    $('ledger').innerHTML='<tr><th>Date</th><th>Tournament</th><th>Player</th><th>Type</th><th>Odds</th><th>Stake</th><th>P&amp;L</th><th>Result</th></tr>'+rowsHtml;
    $('led-count').textContent='Showing '+shown+' of '+settled.length+' settled bets, newest first.';
  }
  $('led-q').addEventListener('input',drawLedger);$('led-res').addEventListener('change',drawLedger);

  /* open bets: behind the weekly code (a signup funnel, not security: the sheet itself is public) */
  var validCodes=[__CODES__];
  var KEY='se_picks_unlocked';
  function unlocked(){try{return sessionStorage.getItem(KEY)==='1'}catch(e){return false}}
  function showOpen(){
    $('lockbox').hidden=true;
    var w=$('open-wrap');w.hidden=false;
    if(!openRows.length){w.innerHTML='<p>No open bets right now. New bets are logged before the first round of each event.</p>';return}
    var h='<div class="tablewrap"><table><tr><th>Player</th><th>Tournament</th><th>Type</th><th>Odds</th><th>Stake</th></tr>';
    openRows.forEach(function(r){h+='<tr><td>'+esc(r.player)+'</td><td>'+esc(r.tournament)+'</td><td>'+esc(r.type)+'</td><td>'+esc(odds(r.odds))+'</td><td>$'+(parseFloat(r.wager)||0).toFixed(0)+'</td></tr>'});
    w.innerHTML=h+'</table></div>';
  }
  $('code-form').addEventListener('submit',function(e){
    e.preventDefault();
    var c=$('code-in').value.toUpperCase().trim(),ok=false;
    for(var i=0;i<validCodes.length;i++){if(validCodes[i]===c)ok=true}
    if(ok){try{sessionStorage.setItem(KEY,'1')}catch(x){}$('code-err').hidden=true;showOpen()}
    else{$('code-err').hidden=false;$('code-in').value='';$('code-in').focus()}
  });

  function fail(){$('trk-stats').innerHTML='<p>The live record could not load right now. Please try again shortly.</p>'}
  fetch(D).then(function(r){if(!r.ok)throw 0;return r.text()}).then(paint)
    .catch(function(){fetch('https://corsproxy.io/?'+encodeURIComponent(D)).then(function(r){if(!r.ok)throw 0;return r.text()}).then(paint).catch(fail)});
})();
</script>"""

REL = [("pga-tour-betting-guide.html", "PGA Tour betting guide", "Markets, odds and strategy"),
       ("methodology.html", "Methodology", "How the model works"),
       ("membership.html", "Membership", "The weekly model workbook")]

if __name__ == "__main__":
    render_page("picks.html", "Pick Tracker: Every StrokesEdge Golf Bet, Wins and Losses",
                "The full StrokesEdge pick tracker: every PGA Tour bet with odds, stake and result, wins and losses included, plus this week's open bets for subscribers.",
                "Pick <span>Tracker.</span>",
                "Every bet we have logged, wins and losses, read live from the tracker sheet.",
                BODY, "Public record", related=REL, extra_css=CSS,
                extra_js=JS.replace("__CODES__", CODES), schema="WebPage")
    print("built picks.html with %d codes preserved" % (CODES.count("'") // 2))

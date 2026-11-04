"""
Builds the calculator pages and the cheat-sheet landing page. Safe to re-run.
    golf-odds-calculator.html, each-way-calculator.html, strokes-gained-cheat-sheet.html
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sitepage import render_page  # noqa: E402

CSS = r"""
.calc{background:var(--sur);border:1px solid var(--bdr);border-radius:4px;padding:22px;margin:1.5rem 0 2rem}
.calc-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
.calc label{display:block;font:400 11px/1.3 'DM Mono',monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--txt2)}
.calc input,.calc select{display:block;width:100%;margin-top:7px;background:var(--bg);color:var(--txt);border:1px solid var(--bdr);border-radius:2px;padding:13px 12px;font:400 18px/1.2 'DM Mono',monospace}
.calc input:focus,.calc select:focus{outline:2px solid var(--g);outline-offset:1px}
.calc .bad{border-color:var(--r)}
.outs{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:var(--bdr2);border:1px solid var(--bdr2);border-radius:3px;overflow:hidden;margin-top:18px}
.outs div{background:var(--bg2);padding:16px 12px;text-align:center}
.outs b{display:block;font:800 clamp(22px,3.2vw,32px)/1 'Archivo',sans-serif;font-stretch:108%;color:var(--g);font-variant-numeric:tabular-nums}
.outs b.neg{color:var(--r)}
.outs span{font:400 10px/1.4 'DM Mono',monospace;letter-spacing:.1em;text-transform:uppercase;color:var(--txt2)}
.msg{min-height:1.4em;margin:12px 0 0;font:400 13px/1.5 'DM Mono',monospace;color:var(--r)}
.calc h3{margin:0 0 4px}
.note-s{font-size:14px;color:var(--txt2);margin:8px 0 0}
@media(max-width:860px){.calc-grid{grid-template-columns:repeat(2,1fr)}.outs{grid-template-columns:repeat(2,1fr)}}
@media(max-width:380px){.calc-grid{grid-template-columns:1fr}}
"""

ODDS_JS = r"""<script>
(function(){
  var $=function(id){return document.getElementById(id)};
  var am=$('am'),de=$('de'),fr=$('fr'),st=$('stake'),pw=$('pw'),msg=$('msg');
  function money(n){return '$'+n.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2})}
  function toAm(d){return d>=2?'+'+Math.round((d-1)*100):String(Math.round(-100/(d-1)))}
  function gcd(a,b){return b?gcd(b,a%b):a}
  function toFr(x){
    for(var den=1;den<=40;den++){var num=Math.round(x*den);if(num>=1&&Math.abs(num/den-x)<.0005){var g=gcd(num,den);return (num/g)+'/'+(den/g)}}
    return x.toFixed(2)+'/1'}
  function parseAm(v){var s=String(v).replace(/[ +]/g,'');if(!/^-?[0-9]+$/.test(s))return null;var n=parseInt(s,10);if(Math.abs(n)<100)return null;return n>0?1+n/100:1+100/(-n)}
  function parseDe(v){var n=parseFloat(v);return isFinite(n)&&n>1?n:null}
  function parseFr(v){var m=String(v).replace(/ /g,'').match(/^([0-9.]+)\/([0-9.]+)$/);if(!m)return null;var a=parseFloat(m[1]),b=parseFloat(m[2]);if(!(a>0&&b>0))return null;return 1+a/b}
  var src='am';
  function run(){
    var d=src==='am'?parseAm(am.value):src==='de'?parseDe(de.value):parseFr(fr.value);
    [am,de,fr].forEach(function(e){e.classList.remove('bad')});
    if(d===null){({am:am,de:de,fr:fr})[src].classList.add('bad');msg.textContent='Enter valid odds, for example +1325, 14.25 or 53/4.';return}
    msg.textContent='';
    if(src!=='am')am.value=toAm(d);
    if(src!=='de')de.value=(Math.round(d*1000)/1000).toString();
    if(src!=='fr')fr.value=toFr(d-1);
    var stake=parseFloat(st.value);if(!(stake>=0))stake=0;
    $('o-imp').textContent=(100/d).toFixed(1)+'%';
    $('o-pay').textContent=money(stake*d);
    $('o-pro').textContent=money(stake*(d-1));
    $('o-fair').textContent=(d).toFixed(2);
    var p=parseFloat(pw.value);
    if(isFinite(p)&&p>0&&p<100){
      var edge=p-100/d,ev=100*(p/100*d-1);
      var e=$('e-edge');e.textContent=(edge>=0?'+':'')+edge.toFixed(1)+' pts';e.className=edge<0?'neg':'';
      var v=$('e-ev');v.textContent=(ev>=0?'+':'-')+'$'+Math.abs(ev).toFixed(2);v.className=ev<0?'neg':'';
      $('e-fair').textContent=toAm(100/p);
    }else{$('e-edge').textContent='-';$('e-ev').textContent='-';$('e-fair').textContent='-'}
  }
  am.addEventListener('input',function(){src='am';run()});
  de.addEventListener('input',function(){src='de';run()});
  fr.addEventListener('input',function(){src='fr';run()});
  st.addEventListener('input',run);pw.addEventListener('input',run);
  run();
})();
</script>"""

odds_body = r"""
<div class="calc" id="calc" aria-label="Golf odds calculator">
  <div class="calc-grid">
    <label>American odds<input id="am" inputmode="numeric" value="+1325" autocomplete="off"></label>
    <label>Decimal odds<input id="de" inputmode="decimal" value="14.25" autocomplete="off"></label>
    <label>Fractional odds<input id="fr" value="53/4" autocomplete="off"></label>
    <label>Stake ($)<input id="stake" inputmode="decimal" value="10" autocomplete="off"></label>
  </div>
  <p class="msg" id="msg" role="status"></p>
  <div class="outs">
    <div><b id="o-imp">7.0%</b><span>Implied win probability</span></div>
    <div><b id="o-pay">$142.50</b><span>Total payout</span></div>
    <div><b id="o-pro">$132.50</b><span>Profit if it wins</span></div>
    <div><b id="o-fair">14.25</b><span>Decimal odds</span></div>
  </div>
</div>

<div class="calc">
  <h3>Edge check</h3>
  <p class="note-s">Enter what you think the player's real chance of winning is. The calculator compares it to the price above.</p>
  <div class="calc-grid" style="grid-template-columns:repeat(2,1fr);margin-top:14px">
    <label>Your win probability (%)<input id="pw" inputmode="decimal" value="9" autocomplete="off"></label>
  </div>
  <div class="outs" style="grid-template-columns:repeat(3,1fr)">
    <div><b id="e-edge">+2.0 pts</b><span>Edge vs the price</span></div>
    <div><b id="e-ev">+$28.25</b><span>Expected value per $100</span></div>
    <div><b id="e-fair">+1011</b><span>Fair American price</span></div>
  </div>
  <p class="note-s">A positive edge means your probability is higher than the price implies. It is only as good as your probability estimate.</p>
</div>

<h2>How to convert golf odds</h2>
<p>American odds show the profit on a $100 stake. A positive number such as +1325 means $1,325 profit on $100, so the decimal price is 1 + 1325 / 100 = 14.25. A negative number such as -110 means you stake $110 to win $100, so the decimal price is 1 + 100 / 110 = 1.91. Fractional odds like 53/4 show profit over stake, so the decimal price is 1 + 53 / 4 = 14.25.</p>
<h2>How to find implied probability</h2>
<p>Implied probability is 1 divided by the decimal odds. At 14.25 that is 1 / 14.25 = 7.0 percent. That is the chance the sportsbook needs you to believe, before its margin. In a golf outright market the implied probabilities of every player add up to more than 100 percent, and the extra is the book's margin.</p>
<div class="tablewrap"><table>
<tr><th>American</th><th>Decimal</th><th>Fractional</th><th>Implied probability</th></tr>
<tr><td>+500</td><td>6.00</td><td>5/1</td><td>16.7%</td></tr>
<tr><td>+1200</td><td>13.00</td><td>12/1</td><td>7.7%</td></tr>
<tr><td>+3000</td><td>31.00</td><td>30/1</td><td>3.2%</td></tr>
<tr><td>+10000</td><td>101.00</td><td>100/1</td><td>1.0%</td></tr>
<tr><td>-110</td><td>1.91</td><td>10/11</td><td>52.4%</td></tr>
</table></div>
<h2>What edge means</h2>
<p>Edge is your estimated win probability minus the implied probability. If you think a player wins 9 percent of the time and the price implies 7.0 percent, the edge is 2.0 percentage points. Expected value per $100 is 100 x (your probability x decimal odds - 1). StrokesEdge uses the same idea each week, with a course-specific model supplying the probability. See the <a href="methodology.html">methodology</a> and the <a href="pga-tour-betting-guide.html">PGA Tour betting guide</a>.</p>
"""

odds_faq = [
    ("How do you convert American odds to implied probability?",
     "For positive odds, divide 100 by the odds plus 100. +1325 gives 100 / 1425, or 7.0 percent. For negative odds, divide the odds without the minus sign by that number plus 100. -110 gives 110 / 210, or 52.4 percent."),
    ("What does +1325 mean in golf betting?",
     "It means a winning $100 bet profits $1,325 and returns $1,425 in total. The implied win probability is about 7.0 percent."),
    ("What is a good edge in golf betting?",
     "Any positive edge means your probability is higher than the price implies, but small edges are easily erased by estimation error and the sportsbook margin. Treat the result as a way to check your reasoning, not a guarantee."),
    ("Why do the implied probabilities in a golf market add up to more than 100 percent?",
     "The extra is the sportsbook's margin, sometimes called the vig or overround. It is built into every price in the market."),
]

EW_JS = r"""<script>
(function(){
  var $=function(id){return document.getElementById(id)};
  var odds=$('ew-odds'),fmt=$('ew-fmt'),stake=$('ew-stake'),frac=$('ew-frac'),msg=$('ew-msg');
  function money(n){return (n<0?'-':'')+'$'+Math.abs(n).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2})}
  function parse(v,f){
    v=String(v).replace(/ /g,'');
    if(f==='am'){var s=v.replace('+','');if(!/^-?[0-9]+$/.test(s))return null;var n=parseInt(s,10);if(Math.abs(n)<100)return null;return n>0?1+n/100:1+100/(-n)}
    if(f==='de'){var d=parseFloat(v);return isFinite(d)&&d>1?d:null}
    var m=v.match(/^([0-9.]+)\/([0-9.]+)$/);if(!m)return null;var a=parseFloat(m[1]),b=parseFloat(m[2]);return a>0&&b>0?1+a/b:null}
  function set(id,val,neg){var e=$(id);e.textContent=val;e.className=neg?'neg':''}
  function run(){
    var D=parse(odds.value,fmt.value),u=parseFloat(stake.value),f=parseFloat(frac.value);
    odds.classList.toggle('bad',D===null);
    if(D===null){msg.textContent='Enter valid odds, for example +2000, 21 or 20/1.';return}
    msg.textContent='';
    if(!(u>=0))u=0;
    var winRet=u*D,placeRet=u*(1+(D-1)*f),total=2*u;
    $('t-stake').textContent=money(total);
    set('r-win',money(winRet+placeRet));set('p-win',money(winRet+placeRet-total),winRet+placeRet-total<0);
    set('r-place',money(placeRet));set('p-place',money(placeRet-total),placeRet-total<0);
    set('r-miss',money(0));set('p-miss',money(-total),true);
    $('d-win').textContent=money(winRet);$('d-place').textContent=money(placeRet);
  }
  [odds,fmt,stake,frac].forEach(function(e){e.addEventListener('input',run);e.addEventListener('change',run)});
  run();
})();
</script>"""

ew_body = r"""
<div class="calc" aria-label="Each-way calculator">
  <div class="calc-grid">
    <label>Odds<input id="ew-odds" value="+2000" autocomplete="off"></label>
    <label>Odds format<select id="ew-fmt"><option value="am">American</option><option value="de">Decimal</option><option value="fr">Fractional</option></select></label>
    <label>Stake per part ($)<input id="ew-stake" inputmode="decimal" value="5" autocomplete="off"></label>
    <label>Place terms<select id="ew-frac"><option value="0.5">1/2 odds</option><option value="0.333333">1/3 odds</option><option value="0.25" selected>1/4 odds</option><option value="0.2">1/5 odds</option></select></label>
  </div>
  <p class="msg" id="ew-msg" role="status"></p>
  <p class="note-s">An each-way bet is two equal bets, so your total stake is double the stake per part. The place terms (the fraction of the odds and the number of places) are set by the sportsbook, so check them before you bet.</p>
  <div class="tablewrap"><table>
    <tr><th>Result</th><th>Win part pays</th><th>Place part pays</th><th>Total return</th><th>Profit or loss</th></tr>
    <tr><td>Wins the tournament</td><td id="d-win">$105.00</td><td id="d-place">$30.00</td><td id="r-win">$135.00</td><td><b id="p-win" style="color:var(--g)">$125.00</b></td></tr>
    <tr><td>Places but does not win</td><td>$0.00</td><td>$30.00</td><td id="r-place">$30.00</td><td><b id="p-place" style="color:var(--g)">$20.00</b></td></tr>
    <tr><td>Misses the places</td><td>$0.00</td><td>$0.00</td><td id="r-miss">$0.00</td><td><b id="p-miss" class="neg" style="color:var(--r)">-$10.00</b></td></tr>
  </table></div>
  <div class="outs" style="grid-template-columns:1fr"><div><b id="t-stake">$10.00</b><span>Total stake</span></div></div>
</div>

<h2>How an each-way bet works</h2>
<p>You place two equal bets on the same player: one on the player to win and one on the player to place. If the player wins, both bets pay. If the player places but does not win, only the place bet pays. If the player misses the places, you lose both stakes.</p>
<p>The win part pays the full odds. The place part pays a fraction of the odds, typically 1/4 or 1/5 in golf, and your place stake is returned. With decimal odds D, the win part returns stake x D and the place part returns stake x (1 + (D - 1) x fraction).</p>
<h2>Worked example</h2>
<p>A $5 each-way bet on a player at +2000 (decimal 21) with place terms of 1/4 odds costs $10. If the player wins, the win part returns $105 and the place part returns $30, for $135 total and $125 profit. If the player only places, you get $30 back for $20 profit. If the player misses the places, you lose the $10.</p>
<h2>Each-way betting in the US</h2>
<p>Each-way terms are standard at UK and Irish bookmakers. Most US sportsbooks do not list each-way golf bets the same way. They usually offer separate top 5, top 10 and top 20 markets instead, each priced on its own. This calculator is still useful for comparing an each-way bet with the same stake split across a win market and a finish market. See the <a href="pga-tour-betting-guide.html">PGA Tour betting guide</a> and the <a href="golf-odds-calculator.html">golf odds calculator</a>.</p>
"""

ew_faq = [
    ("What is an each-way bet in golf?",
     "An each-way bet is two equal bets on one player: one to win and one to place. The place part pays a fraction of the odds, commonly 1/4 or 1/5, if the player finishes in the places the sportsbook sets."),
    ("How do you calculate each-way returns?",
     "The win part returns stake times decimal odds. The place part returns stake times one plus the decimal odds minus one, multiplied by the place fraction. Add the two when the player wins."),
    ("Do US sportsbooks offer each-way golf bets?",
     "Most do not offer them in the UK style. They usually list top 5, top 10 and top 20 finish markets as separate bets, each with its own price."),
]

CHEAT_BODY = r"""
<div class="callout"><p>One page, free, delivered to your inbox when you subscribe to the weekly StrokesEdge picks.</p></div>
<p><a class="btn" href="https://strokesedge.substack.com" data-signup>Get the cheat sheet free →</a></p>
<h2>What is on it</h2>
<ul>
<li><strong>The four strokes gained categories</strong> and what each one measures.</li>
<li><strong>The odds math</strong>: how to turn any price into an implied probability, and how to calculate edge.</li>
<li><strong>The weekly process</strong>: course demands, player scores, thresholds and the market price, in order.</li>
<li><strong>Common mistakes</strong> that cost golf bettors money.</li>
<li><strong>How the weights change</strong> from course to course, with two published examples.</li>
</ul>
<h2>A preview</h2>
<div class="tablewrap"><table>
<tr><th>Category</th><th>What it measures</th></tr>
<tr><td>Off the tee</td><td>Driving: distance and accuracy on par 4s and par 5s.</td></tr>
<tr><td>Approach</td><td>Iron and long shots into the green.</td></tr>
<tr><td>Around the green</td><td>Chipping, pitching and bunker play.</td></tr>
<tr><td>Putting</td><td>Everything on the green.</td></tr>
</table></div>
<p>The full sheet adds the weekly checklist, the formulas and the two worked weightings. For the detail behind it, read <a href="strokes-gained-explained.html">Strokes Gained Explained</a>.</p>
"""

cheat_faq = [
    ("How do I get the strokes gained cheat sheet?",
     "Subscribe to the free StrokesEdge newsletter. The welcome email includes a link to the PDF."),
    ("Is the strokes gained cheat sheet free?",
     "Yes. It is free with a newsletter subscription, and you can unsubscribe at any time."),
]

REL = [("pga-tour-betting-guide.html", "PGA Tour Betting Guide", "Markets, odds and strategy"),
       ("strokes-gained-explained.html", "Strokes Gained Explained", "The stat behind the model"),
       ("how-to-bet-on-golf.html", "How to Bet on Golf", "A first-timer's walkthrough")]

if __name__ == "__main__":
    render_page("golf-odds-calculator.html", "Golf Odds Calculator: Implied Probability & Payout",
                "Free golf odds calculator: convert American, decimal and fractional odds, see implied win probability and payout, and check your edge against the price.",
                "Golf Odds <span>Calculator.</span>",
                "Convert American, decimal and fractional odds, see the implied probability and payout, and check your edge against the price.",
                odds_body, "Free tool", faq=odds_faq, related=REL, extra_css=CSS, extra_js=ODDS_JS, schema="WebApplication")
    render_page("each-way-calculator.html", "Golf Each-Way Bet Calculator: Win and Place Returns",
                "Free each-way calculator for golf: enter the odds, stake and place terms to see the win and place returns, total stake and profit for every result.",
                "Each-Way <span>Calculator.</span>",
                "Enter the odds, your stake and the place terms to see what an each-way golf bet returns in every outcome.",
                ew_body, "Free tool", faq=ew_faq, related=REL, extra_css=CSS, extra_js=EW_JS, schema="WebApplication")
    render_page("strokes-gained-cheat-sheet.html", "Free Strokes Gained Cheat Sheet for Golf Bettors",
                "Free one-page strokes gained cheat sheet for golf bettors: the four categories, the odds math, the weekly process and common mistakes. Subscribe to get it.",
                "Strokes Gained <span>Cheat Sheet.</span>",
                "A one-page reference for reading strokes gained and turning it into betting decisions.",
                CHEAT_BODY, "Free download", faq=cheat_faq, related=REL, schema="WebPage")
    print("built 3 pages")

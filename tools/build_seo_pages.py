"""
Builds the evergreen long-tail betting guides (safe to re-run), all through tools/sitepage.render_page:
    golf-betting-odds-explained, outright-vs-top-10-golf-betting, each-way-golf-betting-explained,
    golf-matchup-bets-explained, golf-betting-bankroll-management
Then adds them to the sitemap. Run tools/add_signup.py and tools/audit_site.py afterwards.
Every worked example below is checked by hand, and bookmaker rules that vary are marked "check your book".
"""
import os
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sitepage import render_page  # noqa: E402
from publish_picks import add_to_sitemap  # noqa: E402

CSS = ".art h3{font:700 18px/1.3 'Archivo',sans-serif;font-stretch:104%;margin:1.4rem 0 .35rem;color:var(--txt)}.art table{width:100%}"
NOTE = '<p><em>Educational only, not financial advice. Rules and terms differ by sportsbook, so check yours. Gamble responsibly.</em></p>'


def rel(*items):
    return list(items)


GUIDE = ("pga-tour-betting-guide.html", "PGA Tour betting guide", "Markets, odds and strategy")
HOW = ("how-to-bet-on-golf.html", "How to bet on golf", "Placing your first golf bet")
ODDSCALC = ("golf-odds-calculator.html", "Golf odds calculator", "Implied probability and payout")
EWCALC = ("each-way-calculator.html", "Each-way calculator", "Win and place returns")
SG = ("strokes-gained-explained.html", "Strokes gained explained", "The stats behind the picks")
PICKS = ("weekly-picks.html", "Weekly picks", "Model best bets every event")
TRACK = ("picks.html", "Public pick tracker", "Every settled bet, wins and losses")

PAGES = [
    dict(slug="golf-betting-odds-explained", title="Golf Betting Odds Explained: American, Decimal, Fractional",
         desc="How golf betting odds work: read +1500 and -150, convert American, decimal and fractional odds, find implied probability and see what a winner pays.",
         h1="Golf betting odds <span>explained.</span>", lede="Reading a price is the first skill in golf betting. Here is how American, decimal and fractional odds work, and how to turn any of them into a probability.",
         eyebrow="Betting basics", related=rel(ODDSCALC, HOW, GUIDE),
         body="""<div class="art">
<h2>What +1500 and -150 mean</h2>
<p>American odds show profit on a winning 100 unit stake. A plus number is the profit on 100 staked, so a golfer at <strong>+1500</strong> pays 1500 profit on a 100 bet, a return of 1600 with your stake. A minus number is how much you must stake to win 100, so <strong>-150</strong> means staking 150 to win 100. Almost every golf outright is a plus number, because even the favorite is far less likely to win than not.</p>
<h2>The same price in three formats</h2>
<div class="tablewrap"><table><thead><tr><th>American</th><th>Decimal</th><th>Fractional</th><th>Implied probability</th></tr></thead><tbody>
<tr><td>+300</td><td>4.00</td><td>3/1</td><td>25.0%</td></tr>
<tr><td>+1500</td><td>16.00</td><td>15/1</td><td>6.25%</td></tr>
<tr><td>+4000</td><td>41.00</td><td>40/1</td><td>2.4%</td></tr>
<tr><td>-150</td><td>1.67</td><td>2/3</td><td>60.0%</td></tr>
</tbody></table></div>
<h2>How to find implied probability</h2>
<p>For a plus price, divide 100 by the price plus 100. For +1500 that is 100 / 1600, or 6.25%. For a minus price, divide the price by the price plus 100. For -150 that is 150 / 250, or 60%. Decimal odds are simpler: divide 1 by the decimal price (1 / 16.00 is 6.25%). You can check any price with the <a href="golf-odds-calculator.html">golf odds calculator</a>.</p>
<h2>Why the probabilities add up to more than 100%</h2>
<p>If you convert every golfer's outright price to a probability and add them, the total is well above 100%. The excess is the sportsbook's margin, often called the overround, and it is the price of placing the bet. Longshots tend to carry a lot of it, because a book shades every long price in its own favor. That is why a model needs a real edge, not just a probability that looks about right.</p>
<h2>Where value comes from</h2>
<p>A bet has value when your estimated chance of winning is higher than the implied probability in the price. If a model gives a golfer a 3.0% chance to win and the price is +4000 (2.4% implied), the bet has a positive edge on paper. If the model says 2.0%, the same price is a pass. Value is always relative to the price, never to how good the golfer is. Our weekly <a href="weekly-picks.html">picks</a> show the model's edge next to every price, and the <a href="strokes-gained-explained.html">strokes gained</a> guide covers the stats behind those probabilities.</p>
</div>""",
         faq=[("What does +1500 mean in golf betting?", "A golfer at +1500 pays 1500 profit on a 100 bet, a total return of 1600 including the stake. The implied win probability is about 6.25%."),
              ("How do I convert American odds to decimal?", "For a plus price, divide by 100 and add 1, so +1500 is 16.00. For a minus price, divide 100 by the price and add 1, so -150 is about 1.67."),
              ("Why do golf odds add up to more than 100%?", "The extra is the sportsbook's margin. Every golfer's price is shaded slightly, and long prices carry the most, so the implied probabilities across the field total well above 100%.")]),
    dict(slug="outright-vs-top-10-golf-betting", title="Outright vs Top 10 Golf Bets: Which Market to Bet",
         desc="Golf outright, top 5, top 10, top 20, make the cut and matchup markets compared: what each pays, how often each hits and when to use them.",
         h1="Outright vs top 10 golf bets: <span>which market?</span>", lede="A golf bet can be one player winning or finishing in a range. Each market trades payout against hit rate, and the right one depends on where the price is wrong.",
         eyebrow="Betting strategy", related=rel(("golf-betting-odds-explained.html", "Golf betting odds explained", "Read and convert any price"), GUIDE, PICKS),
         body="""<div class="art">
<h2>The main golf markets</h2>
<div class="tablewrap"><table><thead><tr><th>Market</th><th>What you need</th><th>Typical price</th><th>Hit rate</th></tr></thead><tbody>
<tr><td>Outright winner</td><td>Win the tournament</td><td>+1500 to +20000</td><td>Lowest, one winner in a 150 player field</td></tr>
<tr><td>Top 5</td><td>Finish 5th or better</td><td>Roughly +250 to +10000</td><td>Low</td></tr>
<tr><td>Top 10</td><td>Finish 10th or better</td><td>Roughly +120 to +5000</td><td>Medium</td></tr>
<tr><td>Top 20</td><td>Finish 20th or better</td><td>Roughly -110 to +2000</td><td>Higher</td></tr>
<tr><td>Make the cut</td><td>Play the weekend</td><td>Mostly minus prices</td><td>Highest</td></tr>
<tr><td>Head to head matchup</td><td>Beat one named player</td><td>About -110 each side</td><td>Near 50%</td></tr>
</tbody></table></div>
<p>The price ranges are rough guides that move with field strength and each book. Check live odds before you bet.</p>
<h2>Outrights: big payout, rare hit</h2>
<p>An outright at +4000 implies about a 2.4% chance. Even a golfer with a genuine edge loses the bet roughly 97 times in 100, so outright betting needs patience and small stakes. The upside is that the price can pay for a long run of losses. Our weekly cards usually include one or two longshot outrights where the model sees a bigger gap than the market does.</p>
<h2>Top 10 and top 20: a better hit rate for the same player</h2>
<p>A golfer priced +4000 to win might be +350 for a top 10, an implied 22.2%. The same skill that gives a small chance to win gives a much larger chance to finish in the top 10, so these markets suit a player the model likes but the outright market already prices fairly. Be careful with dead heat rules: when players tie at the cutoff, most books pay a fraction of the winnings, so a tie for 10th pays less than a clean 10th.</p>
<h2>When to fade the outright but keep the finish markets</h2>
<p>A favorite can be too short to win and still be a strong top 10 player. When our model fades someone outright, the note says whether the top 10 and top 20 markets are still viable, because the edge often exists in one market and not the other.</p>
<h2>Matchups and the cut</h2>
<p>Matchups strip out most of the field, so you only need to beat one player. Make the cut markets pay little but hit often, which makes them a poor fit for a single bet and a common leg in a parlay. See the guide to <a href="golf-matchup-bets-explained.html">matchup bets</a> for how those work.</p>
</div>""",
         faq=[("Is it better to bet outright or top 10 in golf?", "Neither is better in general. Outrights pay far more but win rarely, while top 10 bets hit more often at a lower price. Use the market where your estimate differs most from the price."),
              ("What is a dead heat in golf betting?", "A dead heat is a tie at the cutoff of a finish market. Most books pay a fraction of the winnings, so a tie for 10th pays less than a clean 10th place. Check your book's rule."),
              ("How often does a golf outright bet win?", "An outright price of +4000 implies roughly a 2.4% chance, so even a good bet usually loses. Stake small and expect long losing runs.")]),
    dict(slug="each-way-golf-betting-explained", title="Each-Way Golf Betting Explained With Examples",
         desc="How each-way golf bets work: the win and place parts, place terms like 1/5 odds for five places, a worked payout example and when each-way is worth it.",
         h1="Each-way golf betting <span>explained.</span>", lede="An each-way bet is two bets in one: a win bet and a place bet. Here is how the payout works, with a full example you can check yourself.",
         eyebrow="Betting basics", related=rel(EWCALC, ("golf-betting-odds-explained.html", "Golf betting odds explained", "Read and convert any price"), HOW),
         body="""<div class="art">
<h2>How an each-way bet works</h2>
<p>An each-way bet splits your total stake into two equal parts. One part is a <strong>win bet</strong> that pays at the full odds if your golfer wins. The other part is a <strong>place bet</strong> that pays at a fraction of the odds if your golfer finishes inside the places. The terms, such as "1/5 odds, five places", are set by the sportsbook for each tournament. Each-way is more common in the UK than at US books, so check whether your book offers it.</p>
<h2>A worked example</h2>
<p>You bet 10 each way on a golfer at 40/1 (+4000) with terms of 1/5 odds for five places. The total stake is 20.</p>
<div class="tablewrap"><table><thead><tr><th>Result</th><th>Win part</th><th>Place part</th><th>Total return</th><th>Profit</th></tr></thead><tbody>
<tr><td>Wins</td><td>410</td><td>90</td><td>500</td><td>+480</td></tr>
<tr><td>Finishes 2nd to 5th</td><td>0</td><td>90</td><td>90</td><td>+70</td></tr>
<tr><td>Finishes 6th or worse</td><td>0</td><td>0</td><td>0</td><td>-20</td></tr>
</tbody></table></div>
<p>The place part pays at one fifth of the odds: 40/1 becomes 8/1, so a 10 stake returns 90 including the stake. The win part returns 10 x 41 = 410 if he wins. Notice that a place finish only just covers your total stake with a profit of 70, while a win is where the real payout is.</p>
<h2>Is each-way worth it for golf?</h2>
<p>Each-way helps most when the odds are long and the field is big, because the place part gives you something back far more often than the win part does. It is worse value when the place terms are tight or the odds are short. Compare the place part against a plain top 5 or top 10 bet at the same book, since a separate finish market is sometimes priced better. You can test the numbers in the <a href="each-way-calculator.html">each-way calculator</a>.</p>
<h2>Dead heats</h2>
<p>If players tie for the last paying place, books usually reduce the place payout in proportion. Always read your sportsbook's dead heat rule before staking a longshot each way.</p>
</div>""",
         faq=[("What does each way mean in golf betting?", "An each-way bet is two equal bets: one on your golfer to win and one on him to place. The place part pays at a fraction of the odds, such as 1/5 for the first five places."),
              ("How much does an each-way bet cost?", "Twice the unit stake. A 10 each-way bet costs 20, with 10 on the win and 10 on the place."),
              ("Do US sportsbooks offer each-way golf bets?", "Each-way is more common with UK bookmakers. Many US books offer separate top 5, top 10 and top 20 markets instead, so compare those prices.")]),
    dict(slug="golf-matchup-bets-explained", title="Golf Matchup Bets Explained: Head-to-Head Betting",
         desc="How golf head-to-head matchup bets work: tournament and round matchups, ties, missed cuts, what -110 implies and how to find edges with strokes gained.",
         h1="Golf matchup bets <span>explained.</span>", lede="A matchup asks one question: which of two golfers finishes ahead. It is the closest thing golf has to a coin flip, and it is where a model can find small, steady edges.",
         eyebrow="Betting strategy", related=rel(("outright-vs-top-10-golf-betting.html", "Outright vs top 10", "Compare the main markets"), SG, PICKS),
         body="""<div class="art">
<h2>How a golf matchup works</h2>
<p>A head-to-head matchup pairs two golfers and you pick which will finish with the better score. There are two common versions. A <strong>tournament matchup</strong> compares the full event result, and a <strong>round matchup</strong> compares one round's score. Prices usually sit near -110 on each side, which implies about 52.4% for each, so the book keeps a small margin on a near 50/50 bet.</p>
<h2>Rules that change the result</h2>
<ul>
<li><strong>Ties:</strong> many books refund a tied matchup, others use a tie-break. Check which one applies.</li>
<li><strong>Missed cut:</strong> if both players miss, books commonly give the win to the lower 36 hole score. If only one misses, the one who made it wins.</li>
<li><strong>Withdrawals:</strong> a matchup is often void if one player withdraws before it starts and may stand if he withdraws after teeing off. Rules vary.</li>
</ul>
<h2>Why matchups suit a strokes gained model</h2>
<p>An outright needs one golfer to beat 150 others. A matchup needs one to beat one, so a small skill gap in approach, off the tee or putting shows up much more often. The model compares the two golfers on the stats that matter at that course, then checks whether the market price agrees. Our weekly picks list the matchups where the model prefers one player over the other despite the market leaning the other way, as in the <a href="weekly-picks.html">weekly picks archive</a>. The <a href="strokes-gained-explained.html">strokes gained guide</a> explains the numbers involved.</p>
<h2>Staking matchups</h2>
<p>Because the hit rate is near 50%, matchups swing less than outrights, but each bet earns a small edge at best. That favors flat, small stakes and a larger number of bets. See the <a href="golf-betting-bankroll-management.html">bankroll guide</a> for how to size them.</p>
</div>""",
         faq=[("What is a head-to-head bet in golf?", "A bet on which of two named golfers finishes ahead, either over the whole tournament or in a single round. Prices are usually near -110 on each side."),
              ("What happens in a golf matchup if both players miss the cut?", "Many books award the bet to the lower 36 hole score, but rules differ, so check your sportsbook before betting."),
              ("What does -110 imply in a matchup?", "About a 52.4% chance for each side. Both sides summing past 100% is the sportsbook's margin.")]),
    dict(slug="golf-betting-bankroll-management", title="Golf Betting Bankroll Management: Unit Sizing Guide",
         desc="Golf betting bankroll management: how to set a unit size, why longshot outrights need small stakes, and a worked look at how long losing runs really are.",
         h1="Golf betting bankroll <span>management.</span>", lede="Golf outrights lose most of the time even when they are good bets. Staking is how you stay in the game long enough for the edge to show.",
         eyebrow="Betting strategy", related=rel(("outright-vs-top-10-golf-betting.html", "Outright vs top 10", "Compare the main markets"), TRACK, GUIDE),
         body="""<div class="art">
<h2>Set a bankroll and a unit</h2>
<p>Your bankroll is money you can afford to lose entirely, kept separate from everyday funds. A <strong>unit</strong> is a fixed slice of it, commonly 1% for a small outright and up to 2 or 3% for a shorter-priced bet. With a 1,000 bankroll, one unit at 1% is 10. Decide the unit before the tournament and do not chase losses by raising it after a bad week.</p>
<h2>Why golf needs smaller units than most sports</h2>
<p>Take a golfer at +4000, an implied win rate of about 2.4%. The average gap between wins at that price is roughly 1 divided by 0.024, or about 41 bets. At 1% a bet, 40 straight losers cost around 40% of the bankroll before the average winner arrives, and the real run can be longer than average. Longshot outrights are variance heavy by design, so they should be a small part of the card.</p>
<h2>Mix markets to smooth the ride</h2>
<p>Finish markets and matchups hit more often than outrights, so putting part of the card there narrows the swings. Our weekly card follows this idea: a few outrights and longshots, plus top 10 and top 20 plays and a matchup. See <a href="outright-vs-top-10-golf-betting.html">outright vs top 10</a> for the trade-offs.</p>
<h2>Track every bet</h2>
<p>Record the player, market, odds, stake and result for every bet, including the losers. It is the only way to know whether you have an edge or a lucky month. We publish every settled bet on the <a href="picks.html">public pick tracker</a>, wins and losses together, for the same reason.</p>
<h2>What staking cannot do</h2>
<p>No staking plan turns a bet with no edge into a profitable one. It only controls how fast you lose or win. Never stake money you need, and use your sportsbook's deposit limits and cool-off tools if betting stops being fun. If you or someone you know has a gambling problem, call the National Problem Gambling Helpline at 1-800-GAMBLER.</p>
</div>""",
         faq=[("How much should I bet per golf pick?", "Many bettors use a flat unit of about 1% of their bankroll for outrights and somewhat more for shorter prices. Only stake money you can afford to lose."),
              ("Why do golf outrights lose so often?", "A golfer at +4000 wins roughly once in 40 tries at the implied price, so most outright bets lose even when they have value."),
              ("Should I track my golf bets?", "Yes. Log player, market, odds, stake and result for every bet so you can see whether you actually have an edge.")]),
]


def main():
    today = datetime.now().strftime("%Y-%m-%d")
    for p in PAGES:
        render_page(p["slug"] + ".html", p["title"], p["desc"], p["h1"], p["lede"], p["body"] + NOTE, p["eyebrow"],
                    faq=p["faq"], related=p["related"], extra_css=CSS, schema="WebPage")
        add_to_sitemap(p["slug"], today, "0.8", "monthly")
        print("built", p["slug"])


if __name__ == "__main__":
    main()

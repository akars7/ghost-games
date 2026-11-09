# Ghost Games: What Empty Stadiums Reveal About Home Advantage

![CI](https://github.com/akars7/ghost-games/actions/workflows/ci.yml/badge.svg)

## Question
**Do crowds cause home advantage in football? When COVID emptied Europe's stadiums for most of a season, how much of the home edge in goals, points and referee decisions disappeared?**

Nobody can randomly remove crowds from matches, so the pandemic created a rare natural experiment. The same method applies whenever a proper A/B test isn't possible, for example measuring the effect of a price change or a new feature after it has already launched.

## Approach
| Step | Module | Purpose |
|---|---|---|
| 1. Load and validate results from 5 leagues over several seasons | `data.py` | Stop early on duplicates or bad dates |
| 2. Add real attendance from FBref and match team names between the two sources | `attendance.py` | Team names differ between sites, so clubs are matched by their fixture dates |
| 3. Label each match as fans, partial or empty from the real attendance | `treatment.py` | The dates in `config/closed_doors.csv` are only a backup, and are checked against attendance |
| 4. Define outcomes from the home team's view | `outcomes.py` | Goal difference, points difference, card gap, foul gap |
| 5. Compare raw averages with a bootstrap CI and a permutation test | `inference.py` | Is the raw difference real? |
| 6. Regression that controls for team strength | `model.py` | Rules out "stronger teams happened to play at home" |
| 7. Home advantage over time | `model.py` | Does the edge drop in 2020 and come back with the fans? |

### The model
```
outcome = home_adv + effect·treatment + strength[home team] − strength[away team] + noise
```
Team strength enters as +1 for the home team and −1 for the away team, the same idea as RAPM. This keeps the intercept a clean measure of home advantage.

The treatment is either `closed_doors` (fans vs empty) or `crowd_share` (attendance divided by the club's normal crowd). The second version also uses the partial-crowd matches, so it answers a sharper question: **does a bigger crowd create a bigger home edge?**

Every measure, equation and modelling choice is explained step by step in [docs/METHODS.md](docs/METHODS.md).

## Threats to validity
- **Other changes at the same time:** five substitutes, a crowded fixture list and a short pre-season. Separating these from the crowd effect is the hardest part.
- **Attendance quality.** FBref may leave attendance blank for some matches. Those fall back to the dates in `config/closed_doors.csv`, and the notebook reports how many matches that affects.
- **Adaptation:** teams may have adjusted to empty stadiums over the season. The time-series chart shows whether that happened.

## Quickstart
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,analysis]"
pytest -q     # includes a simulation test that recovers a known effect
```

## Roadmap
- [ ] Download 2015-16 to 2022-23 results for E0, D1, SP1, I1 and F1 (second tiers add more data)
- [ ] Download FBref attendance and check the team-name matches
- [ ] Compare the config dates with real attendance and fix any wrong windows
- [ ] Headline results for goal difference, points difference and card gap, for both fans vs empty and crowd size: what share of home advantage disappeared?
- [ ] Time-series chart with a one-sentence takeaway
- [ ] Heterogeneity: did teams with larger stadiums lose more? (needs a capacity dataset)
- [ ] Betting angle: how fast did bookmakers' odds adjust to the missing crowds?
- [ ] Publish a short write-up with three charts

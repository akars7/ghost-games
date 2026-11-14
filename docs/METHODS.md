# Methods

How Ghost Games measures home advantage, and why each choice was made.
All numbers come from the final run: 14,507 matches from 5 leagues,
2015-16 to 2022-23, with fans vs empty taken from real attendance.

---

## 1. Unit of analysis: the match

Each row is one match. Every outcome is written **from the home team's view**,
so a positive value means the home team did better.

Why match level, not season level: one season can mix fan matches and empty
matches, and the mix differs by league. The Bundesliga played its last 82
matches of 2019-20 without fans, while Ligue 1 cancelled the rest of that
season. A season average blends the two situations and hides the timing.

---

## 2. Outcomes

### 2.1 Goal difference
```
goal_diff = home goals − away goals
```
No home edge → average of 0.

Example: 2–0, 1–1, 0–1 → (2 + 0 − 1) / 3 = **+0.33**

### 2.2 Capped goal difference (winsorized)
```
goal_diff_capped = goal_diff limited to the range −3 … +3
```
A 6–0 counts as +3. This keeps the direction of a big win but limits how much
one blowout moves the average. Only 6.5% of matches are decided by 4+ goals,
so it changes little here, but it is a standard check for outliers.

### 2.3 Home points (3 / 1 / 0)
```
home_points = 3 if home win, 1 if draw, 0 if home loss
```
This is how the league table counts, so it is the easiest measure to explain.

**Catch:** with no home advantage, home points are **not** 0. See 2.4.

### 2.4 The "no-edge" level for home points
Assumption: with no home advantage, a home win is as likely as a home loss.

Let `d` = share of matches that end in a draw.
```
P(home win) = P(home loss) = (1 − d) / 2

no-edge home points = 3 × (1 − d)/2  +  1 × d  +  0
                    = 1.5 − 0.5 × d
```
Worked example, matches with fans (`d` = 0.249):
```
3 × 0.3755 = 1.1265
1 × 0.249  = 0.2490
           = 1.3755
```
Sanity checks:
- `d = 0` (no draws) → 1.5 (win half, lose half)
- `d = 1` (all draws) → 1.0

The **home edge in points** is what's left above that level:
```
home points edge = home_points − (1.5 − 0.5 × d)
```

### 2.5 Points difference
```
points_diff = home team points − away team points   →   +3 / 0 / −3
```
This is the **gap** between the two teams, not points given to the home team.
No home edge → average of 0.

**It is the same measure as 2.4 on a different scale:**
```
home points edge = points_diff / 2
```
Proof, with `w`, `l`, `d` = home win, loss, draw shares (`w + l + d = 1`):
```
points_diff      = 3w − 3l = 3(w − l)
home points edge = 3w + d − 1.5 + 0.5d
                 = 3w − 1.5(1 − d)
                 = 3w − 1.5(w + l)
                 = 1.5(w − l)            = points_diff / 2
```
So the write-up can use home points (intuitive), and the model can use
`points_diff` (zero means no edge). Both give the same "share of edge lost".

### 2.6 Win, draw and loss rates
```
home win rate = share of matches the home team won
away win rate = share of matches the away team won
draw rate     = share of draws
```

### 2.7 Card gap and foul gap
```
card_gap = away yellow cards − home yellow cards
foul_gap = away fouls − home fouls
```
Positive = the away team was booked (or penalised) more. These measure how
much of the home edge may come through the referee.

---

## 3. Averages and their uncertainty

### 3.1 Mean
```
mean = (sum of the outcome over all matches) / (number of matches)
```

### 3.2 Margin of error (the ± number)
```
± = 1.96 × (standard deviation of the outcome) / √n
```
`n` = number of matches. 1.96 gives a 95% interval. The margin shrinks with
√n, so small groups are unreliable:

| Group | n | Mean goal diff | ± |
|---|---|---|---|
| Bundesliga 2019-20 after restart (empty) | 82 | −0.24 | 0.48 |
| All leagues, all seasons | 14,507 | +0.32 | 0.03 |

The famous "home teams lose in ghost games" headline came from groups like
the first row. That's why we pool the leagues.

### 3.3 Share of the home edge lost
```
share lost = (edge with fans − edge when empty) / edge with fans
```
Raw averages (11,823 fan matches, 2,022 empty):

| Outcome | Fans | Empty | Share lost |
|---|---|---|---|
| Goal difference | +0.345 | +0.135 | 61% |
| Goal difference, capped | +0.305 | +0.112 | 63% |
| Points difference | +0.459 | +0.142 | 69% |
| Home points edge (2.4) | +0.230 | +0.071 | 69% |

| Rate | Fans | Empty |
|---|---|---|
| Home win | 45.2% | 39.6% |
| Away win | 29.9% | 34.9% |
| Draw | 24.9% | 25.5% |

The model in section 6 controls for team strength and gives almost the same
shares (60%, 63%, 68%), so the raw gap was not caused by which teams happened
to play at home.

The draw rate barely moves: crowds seem to turn some home wins into away
wins, not into draws.

### 3.4 Robustness
Several reasonable measures are reported side by side instead of one combined
score. A weighted mix (say 0.8 × results + 0.2 × goals) would need arbitrary
weights, and could be tuned, even by accident, to give the most exciting
answer. When separate measures agree (60–68% above), the conclusion is robust.

A second check uses a different treatment, `crowd_level` (4.1), instead of
fans vs empty. It gives 54% for goals, 65% for points and 92% for cards: same
direction, similar size.

---

## 4. Treatment: who had fans?

### 4.1 Crowd share
```
normal crowd = the home team's median attendance outside COVID
               (before 1 March 2020 or from 1 August 2021)
crowd_share  = attendance / normal crowd        (capped at 1.5)
```
1.0 = normal crowd, 0.3 = a 30% capacity limit, 0 = empty.

For the model, the crowd is turned into `crowd_level`:
```
outside COVID (before 1 March 2020 or after 30 June 2022):  crowd_level = 1
during COVID:                                               crowd_level = crowd_share, capped at 1
empty matches:                                              crowd_level = 0
```
Why not use `crowd_share` directly: outside COVID, a low crowd usually means
a small or unpopular match, not a capacity limit. That's a different thing,
so those matches count as a full crowd.

### 4.2 Labels
| Rule | Label |
|---|---|
| attendance = 0 | empty |
| crowd_share < 0.6, during COVID only | partial |
| otherwise | fans |
| attendance missing | use the dates in `config/closed_doors.csv` |
| attendance missing and no date window | unknown (left out) |

FBref leaves closed-doors matches **blank**, not 0, so the config dates are
still needed. The notebook compares the two sources to find wrong dates.

Final counts: 11,823 fans, 2,022 empty, 627 partial, 35 unknown. Attendance
labelled 12,341 matches, the config dates 2,131.

An earlier version gave missing matches the label "fans" by default. That
quietly put some empty matches in the fans group and shrank the effect.
"Unknown" is safer: a match we can't label is left out, not guessed.

### 4.3 Season
The season comes from the **file name** (`I1_1920.csv` → 2019-20), not the
date. COVID pushed the end of 2019-20 into August 2020, so a date rule
("August = new season") put 10 Serie A matches in the wrong season.

---

## 5. Statistical tests (no controls)

### 5.1 Bootstrap confidence interval
1. Resample the fan matches with replacement, same size as the original.
2. Do the same for the empty matches.
3. Record `mean(empty) − mean(fans)`.
4. Repeat 5,000 times. The middle 95% of the results is the interval.

No assumption about the shape of the data is needed.

### 5.2 Permutation test
If crowds don't matter, the labels "fans" and "empty" could be swapped
without changing anything.
1. Shuffle the labels across all matches.
2. Compute the gap in means.
3. Repeat 5,000 times.
```
p = (number of shuffled gaps at least as big as the real one + 1) / (5,000 + 1)
```
The +1 keeps p above 0, since only a limited number of shuffles were run.

---

## 6. The model (with controls)

```
outcome = home_adv + effect × treatment
          + strength[home team, season] − strength[away team, season] + noise
```
- `treatment` is `closed_doors` (0 = fans, 1 = empty) or `crowd_level` (4.1).
- Unknown matches are always left out. Partial matches are left out of the
  `closed_doors` model, but kept in the `crowd_level` model.
- `home_adv` (the intercept) = the home edge when treatment = 0.
- `effect` = how much the treatment changes the home edge.

### Why +1 / −1 for team strength
Each team-season gets one column: +1 when it plays at home, −1 away. On every
row the two values cancel out, so strength can never absorb the home edge.
The intercept stays a clean measure of home advantage. This is the same idea
as RAPM in basketball.

### Reference team
Adding the same number to every team's strength gives identical predictions,
so the strengths are not unique. One team per league-season is dropped and
the others are measured relative to it. `home_adv` and `effect` are not
affected.

### Standard errors
Ordinary least squares with HC1 robust standard errors, which stay valid when
the noise is bigger for some matches than others.

### Share of the edge lost
```
closed_doors:  share lost = −effect / home_adv
crowd_level:   share from crowd = effect / (home_adv + effect)
```
With `crowd_level`, the intercept is the edge with **no** crowd, so the full
edge is `home_adv + effect`.

### Confidence interval for the share (delta method)
The share is a ratio of two estimates, and both have uncertainty. The delta
method turns their variances into a variance for the ratio, using the slope
(gradient) of the ratio with respect to each estimate:
```
h = home_adv, e = effect

closed_doors:  gradient = [ e / h²,  −1 / h ]
crowd_level:   gradient = [ −e / (h + e)²,  h / (h + e)² ]

variance(share) = gradient · Cov(h, e) · gradientᵀ
95% CI          = share ± 1.96 × √variance
```
`Cov(h, e)` is the 2×2 covariance of the two estimates from the regression.
The covariance term matters: h and e are estimated from the same matches, so
their errors are linked.

Final results (closed_doors):

| Outcome | Share lost | 95% CI |
|---|---|---|
| Goal difference | 60% | 40–81% |
| Goal difference, capped | 63% | – |
| Points difference | 68% | 45–90% |
| Yellow card gap | 105% | 78–132% |

More than 100% for cards means the edge did not just vanish but slightly
flipped. The CI includes 100%, so "disappeared completely" is the safe reading.

---

## 7. Booking rate

The card gap (2.7) can drop for two reasons: referees became fairer, or
home players fouled less. The booking rate separates the two:
```
booking rate     = yellow cards / fouls
booking rate gap = away booking rate − home booking rate
```
Fouls barely changed (home fouls rose from 12.43 to 12.75 per match), while
the gap fell:

| | Fans | Empty |
|---|---|---|
| Booking rate gap | +0.0166 | +0.0020 |

Change −0.0146, bootstrap CI −0.020 to −0.0085. In words: per 100 fouls, away
teams got 1.7 more yellow cards than home teams with fans, and 0.2 more
without them.

**Limit:** the data has no foul severity. If away players commit harder fouls
when a crowd is watching, that would also raise their booking rate.

---

## 8. Per-referee changes (empirical-Bayes shrinkage)

Premier League only: the other leagues' files have no referee column.
Referees need at least 30 fan matches and 10 empty matches (18 qualify).

For each referee:
```
change = mean card gap (empty) − mean card gap (fans)
se²    = var(fans) / n_fans + var(empty) / n_empty
```
A referee with 10 empty matches gets a noisy `change`. Some will look extreme
by luck alone. Shrinkage pulls each one toward the overall change, more
strongly when it is noisy:
```
overall     = average change, weighted by 1 / se²   (precise referees count more)
true_spread = max( var(change across referees) − mean(se²), 0 )
weight      = true_spread / (true_spread + se²)
shrunk      = overall change + weight × (change − overall change)
```
The first line is the method of moments: the spread we see = the real spread
+ noise, so the real spread = what we see − the average noise.

Result: `true_spread` = 0. All the variation between referees is what noise
alone would give, so every referee shrinks to the overall change (−0.218).
No referee stands out.

---

## 9. Market check

Betting odds give the market's prediction for each match. 1 / odds is a
probability, but the three outcomes add up to about 1.05. The extra 0.05 is
the bookmaker's margin, removed by dividing by the sum:
```
p_home = (1 / odds_home) / (1 / odds_home + 1 / odds_draw + 1 / odds_away)
surprise = home_win − p_home          (home_win is 1 or 0)
```
Average surprise near 0 = the market was right on average. Below 0 = it
overrated home teams. Each period gets a bootstrap CI (5.1) for the mean
surprise.

| Period | Matches | Predicted | Actual | Gap | 95% CI |
|---|---|---|---|---|---|
| Fans | 11,822 | 44.5% | 45.2% | +0.7 | −0.1 to +1.5 |
| Empty, first 60 days | 497 | 42.2% | 39.8% | −2.3 | −6.2 to +1.5 |
| Empty, later | 1,525 | 41.9% | 39.5% | −2.4 | −4.6 to 0.0 |

Empty minus fans: −3.1 points, CI −5.2 to −0.9. The 60-day cutoff is a
choice, counted from each league's first empty match.

---

## 10. Next methods

- **Ordered logistic regression** for win / draw / loss. The outcome is
  ordinal (loss < draw < win), but the gaps between categories aren't fixed
  numbers. This model keeps the order without assuming a spacing, and gives
  probabilities ("away wins went from 30% to 35%").
- **Closing odds** for the market check: they include late news, so they are
  a harder test than the odds used here.

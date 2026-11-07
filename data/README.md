# Data

Not committed to Git (see `.gitignore`). Two sources, both saved under `data/raw/`.

## 1. Match results (football-data.co.uk)
Run this on your own machine. It downloads 40 files: 5 leagues, 2015-16 to 2022-23.
```bash
mkdir -p data/raw
for season in 1516 1617 1718 1819 1920 2021 2122 2223; do
  for league in E0 D1 SP1 I1 F1; do
    curl -sf "https://www.football-data.co.uk/mmz4281/$season/$league.csv" -o "data/raw/${league}_${season}.csv"
  done
done
```
League codes: `E0` Premier League, `D1` Bundesliga, `SP1` La Liga, `I1` Serie A, `F1` Ligue 1.

## 2. Attendance (FBref)
Needs Google Chrome. soccerdata opens a Chrome window to get past FBref's bot check, and it waits between requests, so the full download takes a while.
```bash
pip install -e ".[fbref]"
ghost-games-fetch-attendance                       # all leagues and seasons
ghost-games-fetch-attendance --leagues E0 --seasons 1920 2021   # or a small test first
```
Files go to `data/raw/attendance/E0_1920.csv` and so on. Files that already exist are skipped, so you can stop and restart.

If soccerdata gets blocked: open the season's "Scores & Fixtures" page on fbref.com, use **Share & Export > Get table as CSV**, and save it with the same file name. The loader reads both formats.

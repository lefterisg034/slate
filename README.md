# Slate — daily MLB model

Runs every morning on GitHub's computers, for free, and publishes a web page
you can open from anywhere. You never have to turn anything on.

Setup takes about 20 minutes, once. Everything below happens in a web browser.
No terminal, no installing anything, no git.

---

## Step 1 — Get a free odds key (3 min)

1. Go to **the-odds-api.com**
2. Click **Get API Key**, enter your email
3. Copy the key they email you. It looks like a long string of letters and numbers.
4. Keep that tab open, you'll paste it in Step 4.

The free tier gives 500 credits a month. This project uses about 3 a day, so
roughly 90 a month. You will not run out.

---

## Step 2 — Make a GitHub account and a project (5 min)

1. Go to **github.com** and sign up. Free.
2. Click the **+** in the top right → **New repository**
3. Name it `slate`
4. Choose **Public** *(required — private repos don't get free web hosting)*
5. Tick **Add a README file**
6. Click **Create repository**

---

## Step 3 — Upload the files (5 min)

On your new repository page:

1. Click **Add file** → **Upload files**
2. Drag in these six files:
   - `ingest.py`
   - `mlb_model.py`
   - `render.py`
   - `build.py`
   - `requirements.txt`
   - `README.md`
3. Click **Commit changes**

Now the workflow file, which lives in a folder:

4. Click **Add file** → **Create new file**
5. In the filename box type exactly: `.github/workflows/daily.yml`
   *(typing the slashes creates the folders automatically)*
6. Open `daily.yml` from your download, copy everything in it, paste it in
7. Click **Commit changes**

---

## Step 4 — Add your odds key as a secret (2 min)

This keeps the key private even though the repository is public.

1. Click **Settings** (top of your repository)
2. Left sidebar → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Name: `ODDS_API_KEY`
5. Secret: paste the key from Step 1
6. Click **Add secret**

---

## Step 5 — Turn on the web page (2 min)

1. Still in **Settings**, left sidebar → **Pages**
2. Under **Source**, choose **Deploy from a branch**
3. Branch: **main**, folder: **/ (root)**
4. Click **Save**

Your page will live at:

```
https://YOUR-USERNAME.github.io/slate/
```

It'll 404 until the first build finishes. That's Step 6.

---

## Step 6 — Run it for the first time (2 min)

1. Click the **Actions** tab
2. If it asks, click the green **I understand my workflows, enable them**
3. Click **Build daily slate** in the left sidebar
4. Click **Run workflow** → **Run workflow**
5. Wait about a minute, then refresh

A green tick means it worked. Open your page URL.

**From now on it runs by itself at 9am Eastern, every day.** Bookmark the URL
on your phone.

---

## When something breaks

Click **Actions**, click the failed run (red X), click the step that failed and
read the error. Most likely causes:

| What you see | What it means |
|---|---|
| `401` or `Unauthorized` | Odds key is wrong or wasn't saved as a secret |
| `no games scheduled` | Off day, All-Star break, or the season is over |
| `TBD` starters, thin ratings | Probable pitchers aren't posted yet — run it later in the morning |
| Nothing changed | Games already final; the workflow skipped them |

To change the run time, edit the `cron` line in `daily.yml`. It's in UTC.
`"0 13 * * *"` is 9am Eastern. Subtract 4 in summer, 5 in winter.

---

## What it is, honestly

Runs are projected from regressed team offense and regressed pitcher FIP,
blended 58/42 with the bullpen, adjusted for park and home field, then scored
through a Negative Binomial distribution. Market probabilities are devigged
from the two-way price. What's shown as EV is the gap between the two, minus
the hold.

**None of this has been walk-forward tested yet.** The math is sound but the
model's real-world accuracy is unmeasured. Treat every number as a hypothesis
until there's a backtest behind it.

A quick sanity check you should run often: real MLB edges live at 1–3%. If the
page shows something at +20%, that's a stale line, a devig error, or a bug —
never a genuine edge.

## Data licensing

MLB's Stats API is free for personal, non-commercial use. Commercial or bulk
use needs written permission from MLB Advanced Media. The Odds API free tier is
for development. If this ever becomes a paid product, both need revisiting.

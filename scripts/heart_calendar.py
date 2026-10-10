import os, json, urllib.request

QUERY = """
query($login:String!){
  user(login:$login){
    contributionsCollection{
      contributionCalendar{
        totalContributions
        weeks{ contributionDays{ date contributionCount contributionLevel weekday } }
      }
    }
  }
}"""

LEVELS = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2,
          "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}
COLORS = ["#2a1f4d", "#5b3a9e", "#8b5cf6", "#c084fc", "#f0abfc"]
HEART = "M0,4.6 C-7.4,-1 -4.2,-6.8 0,-2.9 C4.2,-6.8 7.4,-1 0,4.6 Z"


def fetch(user, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": user}}).encode(),
        headers={"Authorization": "bearer " + token,
                 "Content-Type": "application/json",
                 "User-Agent": "heart-calendar"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if data.get("errors"):
        raise SystemExit("GraphQL error: " + json.dumps(data["errors"]))
    cal = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    return cal["weeks"], cal["totalContributions"]


def streaks(days):
    days = sorted(days, key=lambda d: d["date"])
    best = run = 0
    for d in days:
        run = run + 1 if d["contributionCount"] > 0 else 0
        best = max(best, run)
    cur = 0
    for i, d in enumerate(reversed(days)):
        if d["contributionCount"] > 0:
            cur += 1
        elif i == 0:
            continue  # today may still be empty
        else:
            break
    return cur, best


def bow(x, y, rot=0, s=1.0):
    return (
        f'<g transform="translate({x},{y}) rotate({rot}) scale({s})" '
        'fill="#f9a8d4" stroke="#f0abfc" stroke-width="1" stroke-linejoin="round">'
        '<path d="M-1,2 L-7,15 L-2,12 L0,16 Z"/>'
        '<path d="M1,2 L7,15 L2,12 L0,16 Z"/>'
        '<path d="M0,0 C-6,-10 -19,-9 -17,0 C-19,9 -6,10 0,0 Z"/>'
        '<path d="M0,0 C6,-10 19,-9 17,0 C19,9 6,10 0,0 Z"/>'
        '<circle r="3.4" fill="#f0abfc"/></g>'
    )


def build_svg(weeks, total):
    all_days = [d for w in weeks for d in w["contributionDays"]]
    cur, best = streaks(all_days)

    px, ox, oy = 15, 66, 106
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    # snake path: zigzag column by column (down, up, down, ...)
    order = []
    for wi, w in enumerate(weeks):
        ds = sorted(w["contributionDays"], key=lambda d: d["weekday"])
        if wi % 2:
            ds.reverse()
        order += [(wi, d) for d in ds]
    n = max(len(order), 2)
    T = n * 0.1
    idx = {d["date"]: i for i, (_, d) in enumerate(order)}

    hearts, labels, kf = [], [], []
    last_month = None
    for wi, w in enumerate(weeks):
        days = w["contributionDays"]
        if not days:
            continue
        m = int(days[0]["date"][5:7])
        if m != last_month:
            if last_month is not None or wi == 0:
                labels.append(
                    f'<text class="mono" x="{ox + wi * px - 6}" y="98" '
                    f'font-size="10" fill="#a78bfa">{months[m - 1]}</text>')
            last_month = m
        for d in days:
            lvl = LEVELS.get(d["contributionLevel"], 0)
            cx = ox + wi * px
            cy = oy + d["weekday"] * px + 7
            style = ""
            if lvl > 0:
                i = idx[d["date"]]
                p = min(i / (n - 1) * 100, 99.3)
                p2 = p + 0.4
                kf.append(
                    f"@keyframes e{i}{{0%,{p:.2f}%{{opacity:1}}"
                    f"{p2:.2f}%,99.8%{{opacity:0}}100%{{opacity:1}}}}")
                style = f' style="animation:e{i} {T:.1f}s linear infinite"'
            op = ' opacity=".55"' if lvl == 0 else ""
            hearts.append(
                f'<use href="#h" x="{cx}" y="{cy}" fill="{COLORS[lvl]}"{op}{style}/>')

    coords = [(ox + wi * px, oy + d["weekday"] * px + 7) for wi, d in order]
    pts = " ".join(("M" if k == 0 else "L") + f"{x},{y}" for k, (x, y) in enumerate(coords))
    snake = ""
    for k in reversed(range(8)):
        r = 5.6 - k * 0.45
        fill = "#f9a8d4" if k == 0 else "#c084fc"
        begin = "0s" if k == 0 else f"-{T - k * 0.18:.2f}s"
        snake += (
            f'<circle r="{r:.1f}" fill="{fill}" opacity="{1 - k * 0.08:.2f}">'
            f'<animateMotion dur="{T:.1f}s" begin="{begin}" repeatCount="indefinite" path="{pts}"/>'
            '</circle>')

    day_labels = "".join(
        f'<text class="mono" x="26" y="{oy + i * px + 10}" font-size="9" fill="#8b6fd1">{n_}</text>'
        for i, n_ in ((1, "Mon"), (3, "Wed"), (5, "Fri")))

    legend = "".join(
        f'<use href="#h" x="{738 + i * 17}" y="236" fill="{COLORS[i]}"/>' for i in range(5))

    return f'''<svg width="900" height="272" viewBox="0 0 900 272" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <path id="h" d="{HEART}"/>
    <linearGradient id="edge" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#f0abfc"/><stop offset="1" stop-color="#6d28d9"/>
    </linearGradient>
    <pattern id="grid" width="28" height="28" patternUnits="userSpaceOnUse">
      <path d="M28 0H0V28" fill="none" stroke="#a855f7" stroke-opacity="0.08"/>
    </pattern>
    <filter id="blur" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="10"/></filter>
    <clipPath id="card"><rect x="10" y="10" width="880" height="252" rx="14"/></clipPath>
  </defs>
  <style>
    .mono{{font-family:'Fira Code','Consolas','Courier New',monospace}}
    .cur{{animation:bl 1s steps(1) infinite}}
    @keyframes bl{{50%{{opacity:0}}}}
    .pulse{{animation:pu 4s ease-in-out infinite}}
    @keyframes pu{{0%,100%{{opacity:.3}}50%{{opacity:.6}}}}
    {"".join(kf)}
  </style>

  <rect class="pulse" x="10" y="10" width="880" height="252" rx="14" fill="#7c3aed" filter="url(#blur)"/>
  <rect x="10" y="10" width="880" height="252" rx="14" fill="#140d2b"/>
  <g clip-path="url(#card)">
    <rect x="10" y="10" width="880" height="252" fill="url(#grid)"/>
    <rect x="10" y="10" width="880" height="36" fill="#1f1542"/>
    <rect x="10" y="46" width="880" height="1" fill="#7c3aed" opacity=".6"/>
  </g>
  <rect x="10" y="10" width="880" height="252" rx="14" fill="none" stroke="url(#edge)" stroke-width="2"/>

  <circle cx="34" cy="28" r="5" fill="#f0abfc"/>
  <circle cx="54" cy="28" r="5" fill="#c084fc"/>
  <circle cx="74" cy="28" r="5" fill="#7c3aed"/>
  <text class="mono" x="450" y="32" text-anchor="middle" font-size="12" fill="#a78bfa">~/contributions.exe</text>
  <use href="#h" x="536" y="28" fill="#f0abfc"/>

  <text class="mono" x="30" y="72" font-size="13" font-weight="600">
    <tspan fill="#f0abfc">$</tspan><tspan fill="#d8b4fe"> git log --hearts --since="1 year"</tspan>
  </text>
  <rect class="cur" x="306" y="61" width="8" height="14" fill="#f0abfc"/>
  <text class="mono" x="870" y="72" text-anchor="end" font-size="12" fill="#c4b5fd">{total} commits  |  best streak {best}d  |  now {cur}d</text>

  {"".join(labels)}
  {day_labels}
  {"".join(hearts)}
  {snake}

  <text class="mono" x="30" y="240" font-size="11" fill="#8b6fd1">made with</text>
  <use href="#h" x="102" y="236" fill="#f0abfc"/>
  <text class="mono" x="114" y="240" font-size="11" fill="#8b6fd1">and a lot of git push</text>
  <text class="mono" x="700" y="240" text-anchor="end" font-size="10" fill="#8b6fd1">less</text>
  {legend}
  <text class="mono" x="832" y="240" font-size="10" fill="#8b6fd1">more</text>

  {bow(872, 14, 25, 0.9)}
</svg>
'''


def main():
    weeks, total = fetch(os.environ["GH_USER"], os.environ["GH_TOKEN"])
    os.makedirs("assets", exist_ok=True)
    with open("assets/heart-calendar.svg", "w", encoding="utf-8") as f:
        f.write(build_svg(weeks, total))
    print("ok:", total, "contributions")


if __name__ == "__main__":
    main()

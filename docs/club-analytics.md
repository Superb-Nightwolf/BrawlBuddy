# Club Hub analytics

Club Hub uses the returned club profile and member roster without inventing activity, leagues or historical growth
The same summary is returned by `/api/club`, `/api/demo/club` and club results from `/api/lookup`
`/api/club?tag=%23TAG&refresh=true` bypasses the server club cache
Explicit `/club/{tag}` routes load that club and show a retryable error if it cannot be loaded

## Sources and denominators

The hero displays the reported club trophy total
Charts use the sum of returned member trophies, with a visible notice if that sum differs from the reported total
Source and fetch timestamp accompany the dashboard, and demo and cached responses are labeled

| Measure | Calculation |
|---|---|
| Roster trophies | Sum of returned member trophies |
| Mean | Roster trophies divided by returned member count |
| Median | Middle sorted value or mean of the two middle values |
| Lower and upper quartiles | Linear interpolation at positions `(n - 1) × 0.25` and `(n - 1) × 0.75` |
| Range | Highest minus lowest returned member trophies |
| Standard deviation | Population standard deviation across the returned roster |
| Member trophy share | Member trophies divided by roster trophy sum × 100 |
| Trophy rank | One plus the count of members with more trophies, preserving ties |
| Top 5 and top 10 share | Sum of the highest available 5 or 10 members divided by roster trophy sum × 100 |
| Role trophy share | Sum of trophies in that club role divided by roster trophy sum × 100 |
| Role average | Sum of trophies in that club role divided by that role's member count |
| Leadership | Actual president and vice-president counts |
| Capacity | Returned count compared with the maintained 30-member capacity |
| Open places | `max(0, 30 - member count)` |
| Admission comparison | Count below and at or above the current required trophy setting |

Counts and sums remain zero for an empty roster
Means, quartiles, extrema and undefined shares remain unavailable rather than displaying fabricated values
Unknown role strings are counted under Other roles
Trophy share requires a non-zero roster total

## Charts and panels

Six headline statistics precede thirteen panels in four sections

| Section | Presentation |
|---|---|
| Club snapshot | Donuts for occupied/open places, actual club roles and admission-setting comparison |
| Trophy landscape | Member-count histogram and mean-independent quartile/range/deviation statistics |
| Shared progress | Top-member bars, top-5/rest donut, role trophy totals and averages, cumulative contribution curve |
| Club planning | Editable trophy target, connected player's comparison and recruitment scenario |

Histogram bands include their lower bound and exclude their upper bound
Bands are 0–20k, 20–40k, 40–60k, 60–80k, 80–100k and 100k+
The last band has no upper bound
Bars and their labels show exact counts or totals, and donuts show the same values in their legends

The contribution curve orders members by trophies descending and plots cumulative trophy share against member count
Its diagonal is an even-contribution reference, not a forecast or trophy-growth history
Club roles are separate from brawler combat classes and receive interface symbols rather than unrelated game artwork

The member table supports name/tag search, role filtering and trophy/name sorting
It shows rank, trophies, share, difference from the mean and a link to inspect the player's account
Table scrolling stays inside the table on narrow screens

## Planning assumptions

The initial target is the next multiple of 100,000 above the roster trophy sum
The user can edit the target locally without writing to the official API
Gap is `max(0, target - roster sum)`
The per-member amount is `ceil(gap / current count)` and assumes equal contributions
It is unavailable with no current members

Recruitment adds `open places × joining minimum` to the current roster sum
This assumes every open place is filled at the current minimum and no member leaves
The joining minimum is an admission setting and does not establish whether existing members will remain or qualify for a specific event

Personal comparisons require the connected real player tag to be present in the returned roster
Demo players and absent members receive a clear empty state

## Additional data needed

Club activity, Mega Pig participation, member equipment, win rates and historical growth cannot be derived from the club roster alone
Those require other verified inputs or stored observations collected over time

The numerical tests cover denominator differences, empty and zero rosters, quartiles, tied ranks, unknown roles, cohort sums and refresh cache bypass
The browser check covers direct club routes, charts, planning controls, roster filters, failed refresh recovery, demos, empty rosters and desktop/tablet/mobile layouts

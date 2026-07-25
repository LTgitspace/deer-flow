---
name: planting-research
description: Step-by-step research and guide for planting anything — from plant biology and soil chemistry to pot selection, seed sourcing, and local environment adaptation. Triggers on "plant", "grow", "garden", "seed", "soil", "tree planting", "reforest", "crop", "potting", "fertilize", "irrigation", plus /planting-research.
---

# Planting Research — Practical End-to-End Guide

## Purpose

Walk the user through every phase of planting — from selecting what to grow, through biological and chemical requirements, to pots, soil, seeds, watering, local adaptation, and a beginner-friendly tutorial. This skill is specific, actionable, and grounded in real data.

---

## Phase 1: Research Plant Info

**Goal**: Understand the plant at a high level before diving deep.

### What to Search

- General overview: "how to grow {plant} at home"
- Common varieties: "{plant} varieties for home growing"
- Difficulty level: "is {plant} easy to grow for beginners"
- Growth timeline: "{plant} germination to harvest timeline"

### Required Output

```
## {Plant Name} — Quick Profile

- **Species**: {common name} / {scientific name}
- **Type**: Annual / Perennial / Biennial / Tree / Shrub / Vine
- **Difficulty**: Beginner-Friendly / Intermediate / Expert
- **Growth duration**: {X weeks/months from seed to maturity}
- **Mature size**: {height × width}
- **Edible/Ornamental**: {edible parts} / {ornamental value}
- **Native range**: {geographic origin}
```

---

## Phase 2: Confirm User's Locale

**Gate: Must complete BEFORE any detailed research. Different regions = different growing conditions.**

### Ask the User

Ask `ask_clarification` if locale is not specified:

```
"Where are you planning to plant this?

I need to know:
- Country/region (e.g., "Ho Chi Minh City, Vietnam")
- Indoor or outdoor?
- If outdoor: balcony / garden bed / ground / greenhouse / rooftop?
- Climate zone if you know it (tropical / temperate / Mediterranean / arid)"
```

### Why Locale Changes Everything

| Factor | Why It Matters |
|---|---|
| USDA/Climate zone | Determines if the plant survives winter |
| Sunlight hours | Some plants need 12+ hours, some burn |
| Humidity | Tropical plants fail in dry climates |
| Season | You cannot plant tomatoes in December in Hanoi |
| Local pests | Different regions = different threats |

### Required Output After Confirmation

```
## Locale Profile

- **Location**: {city, country}
- **Setting**: Indoor / Outdoor / Balcony / Garden / Greenhouse
- **Climate zone**: {USDA zone or tropical/temperate/etc.}
- **Current season**: {month} — {planting window: yes/no/with protection}
- **Average sunlight**: {hours per day on planting site}
- **Indoor environment** (if applicable): {temperature, humidity, air flow}
```

---

## Phase 2.5: Month-by-Month Calendar

**Goal**: Every plant has a calendar. What you do in January is wrong in July. This phase builds a specific month-by-month action plan for the user's locale.

### Calendar Rules

- All months must be based on the **user's confirmed locale** from Phase 2
- If user is in the **Southern Hemisphere**, flip the seasons (January = summer, July = winter)
- If locale is **tropical** (no distinct seasons), use wet/dry season cycle instead
- Each month must include: temperature range, daylight hours, and specific tasks

### What to Search

- "{plant} monthly care calendar {locale}"
- "{plant} growing season {country} planting calendar"
- "when to plant {plant} in {city}"
- "{plant} seasonal care month by month"
- "average temperature {city} by month"
- "sunrise sunset times {city} monthly"

### Required Output

```
## Monthly Calendar — {Plant} in {Locale}

### Climate Summary — {City, Country}

```
| Month | Avg Temp (°C) | Avg Rainfall (mm) | Daylight (hours) | Season |
|---|---|---|---|---|
| January | {temp} | {rain} | {hours} | {season} |
| February | {temp} | {rain} | {hours} | {season} |
| March | {temp} | {rain} | {hours} | {season} |
| April | {temp} | {rain} | {hours} | {season} |
| May | {temp} | {rain} | {hours} | {season} |
| June | {temp} | {rain} | {hours} | {season} |
| July | {temp} | {rain} | {hours} | {season} |
| August | {temp} | {rain} | {hours} | {season} |
| September | {temp} | {rain} | {hours} | {season} |
| October | {temp} | {rain} | {hours} | {season} |
| November | {temp} | {rain} | {hours} | {season} |
| December | {temp} | {rain} | {hours} | {season} |
```

### Month-by-Month Action Plan

#### January
- **Season**: {Dry season / Peak summer / Mid-winter}
- **Temperature**: {X-Y}°C
- **Daylight**: {X} hours
- **Plant status**: {Dormant / Active growth / Flowering / Fruiting}
- **Watering**: {schedule and amount — specific, not "as needed"}
- **Fertilizing**: {what and how much — or "do NOT fertilize"}
- **Pruning**: {what to cut and why}
- **Pest watch**: {what pests are active this month in this locale}
- **Harvesting**: {what you should be picking}
- **Critical task this month**: {the ONE thing you must not skip}

#### February
{repeat same structure for all 12 months}

...

#### December
{repeat same structure}

### Critical Windows (Do NOT Miss These)

| Window | When | What Happens If You Miss It |
|---|---|---|
| **Planting window opens** | {month} | Too early = frost kills seedlings. Too late = plant doesn't mature before summer heat. |
| **Planting window closes** | {month} | After this date, wait until next season OR start indoors with grow lights. |
| **Last frost date** | {month/day} | Do NOT transplant outdoors before this date. |
| **First frost date** | {month/day} | Harvest everything before this date. Bring perennials indoors. |
| **Peak pest season** | {month-month} | Weekly inspection required. Preventive treatment recommended. |
| **Peak growth spurt** | {month-month} | Increase watering and fertilizing during this window. |
| **Harvest peak** | {month-month} | Daily harvesting required. If you skip days, fruit over-ripens / seeds drop. |
| **Dormancy begins** | {month} | Stop fertilizing. Reduce watering to {frequency}. Do not prune after this. |

### What If You're Starting in {Current Month}?

```
You are reading this in {current month}. Here is your catch-up plan:

IF {current month} is INSIDE the planting window:
  → Start NOW. Follow the calendar from this month forward.
  → Skip phases that already passed (germination, early growth).
  → Buy seedlings instead of seeds to catch up.

IF {current month} is OUTSIDE the planting window:
  → Option A: Wait until {next planting window month} (recommended)
  → Option B: Start indoors with grow lights now, transplant when window opens
  → Option C: Choose a different plant whose window is open now
    - Alternative plants in-season right now: {list 3-5 options}
```

### Weather Disaster Months (If Applicable)

| Month | Threat | Preparation | Recovery |
|---|---|---|---|
| {e.g., August} | Typhoon season | Move pots indoors. Stake tall plants. Harvest early. | After storm: check for root rot, broken stems, wash salt spray off leaves. |
| {e.g., January} | Frost | Cover with frost cloth. Water soil (not leaves) before freeze — wet soil holds heat. | Do NOT prune frost damage until spring — dead leaves protect live tissue. |
| {e.g., April} | Heat wave >{X}°C | Mulch 5cm deep. Shade cloth 50%. Water at dawn only. | Misted leaves at midday = leaf burn. Only water soil. |
```
---

## Phase 3: Research Biology Behavior

**Goal**: Understand how the plant lives, grows, reproduces, and interacts with its environment.

### What to Search

- Growth cycle: "{plant} growth stages life cycle"
- Root system: "{plant} root depth root spread"
- Light needs: "{plant} sunlight requirements hours"
- Pollination: "{plant} pollination self-pollinating or cross"
- Pests and diseases: "{plant} common pests diseases identification"
- Companion planting: "{plant} companion plants what to plant nearby"
- Spacing: "{plant} spacing between plants cm"

### Required Output

```
## Biological Profile — {Plant}

### Growth Cycle
| Stage | Duration | What Happens | Care Needed |
|---|---|---|---|
| Germination | {days} | Seed absorbs water, root emerges | Keep moist, {temp}°C |
| Seedling | {weeks} | First true leaves appear | Bright indirect light |
| Vegetative | {weeks} | Stem and leaves grow rapidly | Regular water + light fertilizer |
| Flowering | {weeks} | Buds form and bloom | Higher phosphorus feed |
| Fruiting/Seed | {weeks} | Fruit develops or seed heads form | Reduce nitrogen, support branches |
| Dormancy | {months} | (Perennials only) Resting phase | Reduce water, stop feeding |

### Root System
- **Type**: Taproot / Fibrous / Tuberous / Rhizome
- **Depth**: {cm} — needs {shallow/deep} pot
- **Spread**: {cm} — minimum spacing between plants

### Light Requirements
- **Minimum**: {hours} direct sunlight/day
- **Optimal**: {hours} direct sunlight/day
- **Tolerates**: Full sun / Partial shade / Full shade

### Pollination
- **Method**: Self-pollinating / Wind / Insects / Hand-pollination
- **If insect-pollinated**: Needs {specific pollinators} nearby

### Common Pests & Diseases
| Problem | Symptoms | Prevention | Treatment |
|---|---|---|---|
| {pest/disease} | {visual signs} | {prevention} | {treatment} |

### Companion Planting
- **Good neighbors**: {companions that help}
- **Bad neighbors**: {companions that harm}
```

---

## Phase 4: Research Chemical Behavior

**Goal**: Soil pH, nutrient needs, water chemistry, fertilizer ratios — the hard numbers.

### What to Search

- Soil pH: "{plant} soil pH range acidic alkaline"
- Nutrient needs: "{plant} NPK ratio nitrogen phosphorus potassium requirements"
- Water quality: "{plant} water quality pH hardness sensitivity"
- Fertilizer schedule: "{plant} fertilizer schedule organic synthetic"
- Deficiencies: "{plant} nutrient deficiency symptoms yellow leaves brown spots"
- Soil type: "{plant} soil type clay loam sand drainage"
- Toxicity: "is {plant} toxic to pets" (if relevant)

### Required Output

```
## Chemical Profile — {Plant}

### Soil Chemistry
| Property | Optimal Range | Tolerable Range | Critical if |
|---|---|---|---|
| Soil pH | {pH range} | {wider range} | Below {X} or above {Y} |
| Soil type | {loam/clay/sand} | {alternatives} | Heavy clay = root rot |
| Drainage | Well-draining | Moderate | Any standing water = fatal |
| Organic matter | {percentage} | {range} | Below {X} = add compost |

### Nutrient Profile (NPK)
| Stage | N (Nitrogen) | P (Phosphorus) | K (Potassium) | Frequency |
|---|---|---|---|---|
| Seedling | Low | Medium | Low | Every 2 weeks |
| Vegetative | **High** | Medium | Medium | Weekly |
| Flowering | Low | **High** | **High** | Weekly |
| Fruiting | Medium | High | **High** | Weekly |

### Fertilizer by Stage
- **Seedling**: {product type, e.g., "fish emulsion 5-1-1 diluted to half strength"}
- **Vegetative**: {product type, e.g., "balanced 10-10-10 or compost tea"}
- **Flowering/Fruiting**: {product type, e.g., "tomato feed 5-10-10"}
- **Organic alternative**: {compost / worm castings / bone meal / kelp}

### Water Chemistry
- **Ideal pH**: {range}
- **Hardness tolerance**: {soft water OK? hard water OK?}
- **Chlorine sensitivity**: Let tap water sit 24h / use filtered / rainwater preferred
- **Watering frequency**: {schedule — varies by season and pot size}

### Deficiency Signs
| Symptom | Likely Deficiency | Fix |
|---|---|---|
| Yellow lower leaves | Nitrogen | Add blood meal or fish emulsion |
| Purple leaves | Phosphorus | Add bone meal |
| Brown leaf edges | Potassium | Add kelp meal or wood ash |
| Yellow between veins | Iron or Magnesium | Add chelated iron or Epsom salts |
| Blossom end rot | Calcium | Add crushed eggshells or lime |

### Toxicity Warning
- **Toxic to pets**: Yes / No
- **Toxic to humans**: {which parts?} — {symptoms if ingested}
```

---

## Phase 5: Process — From Pots to Final Output

**Goal**: Specific, numbered, granular steps. No generalizations.

### What to Search

- Pot selection: "best pot size for {plant} container growing {locale}"
- Soil mix: "{plant} potting mix recipe ratio"
- Seed sourcing: "where to buy {plant} seeds {country} trusted supplier"
- Seed starting: "how to start {plant} seeds indoors germination"
- Transplanting: "when to transplant {plant} seedlings outdoors hardening off"
- Pruning: "how to prune {plant} for yield shape"
- Harvesting: "when to harvest {plant} signs of ripeness"

### Required Output

```
## Step-by-Step Process — {Plant} in {Locale}

### 1. Pot/Container Selection
- **Material**: Terracotta / Plastic / Fabric / Raised bed / Direct ground
- **Minimum size**: {diameter}cm × {depth}cm — {rationale: taproot needs depth / spreading roots need width}
- **Drainage**: Must have {X} drainage holes. Layer {gravel/broken pottery} at bottom.
- **Where to buy in {locale}**: {local store names, garden center chains, online options with prices}
- **Approximate cost**: {price range in local currency}

### 2. Soil Mix Recipe (Specific Ratios)
| Ingredient | Ratio | Purpose | Source in {locale} |
|---|---|---|---|
| Garden soil / topsoil | 40% | Structure, minerals | {local source} |
| Compost / worm castings | 30% | Nutrients, microbes | {local source} |
| Coco coir / peat moss | 20% | Water retention | {local source} |
| Perlite / pumice / sand | 10% | Drainage, aeration | {local source} |
| {Optional: bone meal/lime} | {as needed} | pH adjustment | {local source} |

### 3. Seed/Tuber/Cutting Sourcing
- **Where to buy seeds**: {specific store names, websites, local markets in {locale}}
- **What to look for**: Check date on packet. Heirloom vs hybrid. Organic certification.
- **Price range**: {local currency range per packet}
- **Alternative**: Can you propagate from {cuttings / grocery store produce / neighbor's plant}?

### 4. Germination / Starting
| Action | Detail |
|---|---|
| **Pre-soak seeds?** | Yes, {X} hours in warm water / No |
| **Sowing depth** | {X} cm deep. Rule: sow 2× the seed diameter. |
| **Starting medium** | Seed-starting mix / Paper towel method / Direct sow in final pot |
| **Temperature** | {X}°C — use heat mat / warm windowsill / propagator |
| **Humidity** | Cover with plastic dome or cling film until sprouted |
| **Light** | After sprouting: {X} hours bright indirect light / grow light {X} cm above |
| **Expected germination** | {X} days (range: {Y-Z} days depending on temperature) |
| **Thinning** | Remove weaker seedlings, keep strongest. Final spacing: {X} per pot. |

### 5. Transplanting (If Starting Indoors)
- **When**: After {X} true leaves appear. Approx {Y} weeks after germination.
- **Hardening off**: 1 hour outdoors day 1 → 2 hours day 2 → ... → full day by day 7.
- **Transplant shock prevention**: Water thoroughly before transplant. Don't disturb roots.
- **After transplant**: Water daily for first week. Shield from direct sun for 3 days.

### 6. Daily/Weekly Care Routine
| Frequency | Task | Detail |
|---|---|---|
| Daily | Check soil moisture | Finger test: dry top 2cm = water. Damp = skip. |
| Daily | Inspect leaves | Look for pests, discoloration, curling. |
| Weekly | Water deeply | Water until it drains from bottom. Never let sit in water. |
| Biweekly | Fertilize | {fertilizer type and amount}. Follow Phase 4 schedule. |
| Biweekly | Prune/train | Remove dead leaves. Pinch tips for bushier growth. |
| As growth | Stake/support | Install {bamboo stake / tomato cage / trellis} when {X} cm tall. |
| As needed | Pest treatment | {neem oil spray / insecticidal soap / hand removal} |

### 7. Flowering & Fruiting Stage
- **Signs of flowering**: {visual cues}
- **Hand pollination (if needed)**: {how to hand-pollinate this plant}
- **Fruit development time**: {weeks from flower to ripe fruit}
- **Thinning fruit**: Remove {X} of small fruit so remaining ones grow larger.

### 8. Harvesting
| Indicator | How to Know It's Ready |
|---|---|
| Color | {ripe color vs unripe} |
| Size | {expected size at maturity} |
| Texture | {firm/soft/slightly gives when squeezed} |
| Smell | {aroma when ripe} |
| Time of day | Best harvested {morning / evening} |

### 9. Post-Harvest / End of Season
- **Annuals**: Pull plant, compost, rotate crop next season.
- **Perennials**: Cut back to {X} cm. Mulch heavily for winter protection. Reduce watering.
- **Seed saving**: {how to save seeds from this plant for next season — if applicable}.
```

---

## Phase 6: Online Tips & Tricks

**Goal**: What experienced growers know that guides don't tell you.

### What to Search

- "{plant} tips Reddit gardening forum"
- "{plant} mistakes beginners make"
- "{plant} hacks increase yield"
- "{plant} growing secrets experienced gardeners"
- "{plant} problems solutions troubleshooting"

### Required Output

```
## Tips, Tricks & Common Mistakes — {Plant}

### Common Beginner Mistakes
| Mistake | Why It Happens | How to Avoid |
|---|---|---|
| Overwatering | Most common cause of plant death | Finger test before every watering |
| Too small pot | Roots bind, plant stagnates | Start in 20% larger pot than you think |
| Wrong season planted | Frost kills, or heat stress | Check Phase 2 planting window |
| No drainage holes | Roots drown | Non-negotiable: every pot must drain |
| Using garden soil in pots | Compacts into concrete | Always use potting mix (see Phase 5) |
| Fertilizing too early | Burns seedling roots | Wait until 2+ true leaves |

### Yield-Boosting Hacks
| Hack | How It Works | Credibility Source |
|---|---|---|
| {Eggshell tea for calcium} | Steep crushed shells in water 24h | {link to source} |
| {Epsom salt for magnesium} | 1 tbsp per liter, foliar spray | {link to source} |
| {Companion planting marigolds} | Repels nematodes and aphids | {link to source} |
| {Pinch top growth} | Forces bushier plant = more flowering sites | {link to source} |

### Pest Control — What Actually Works
| Pest | Organic Treatment | Chemical Treatment (last resort) | Prevention |
|---|---|---|---|
| Aphids | Neem oil spray, ladybugs | Pyrethrin | Companion plant marigolds |
| Spider mites | Increase humidity, insecticidal soap | Miticide | Mist leaves regularly |
| {local pest} | {local remedy} | {local product} | {prevention} |

### Reddit & Community Wisdom
- **r/gardening**: "{quote a specific popular tip thread URL or summary}"
- **r/{locale-specific subreddit if exists}**: "{local community advice}"
- **YouTube channels recommended**: {specific channel names for this plant type}
```

---

## Phase 7: Beginner Tutorial

**Goal**: Step-by-step tutorial that assumes zero prior knowledge. If the user is new to this.

### Structure

```
## Tutorial: How to Plant {Plant} — Complete Beginner's Guide

### What You'll Need (Shopping List)
| Item | Quantity | Approx Cost ({currency}) | Where to Buy in {locale} |
|---|---|---|---|
| {Pot/container} | 1 | {cost} | {store} |
| {Soil mix} | {liters} | {cost} | {store} |
| {Seeds/seedlings} | {count} | {cost} | {store} |
| {Fertilizer} | {size} | {cost} | {store} |
| {Watering can/spray} | 1 | {cost} | {store} |
| {Optional: grow light} | 1 | {cost} | {store} |
| **Total estimated cost** | | **{sum}** | |

### Before You Start (5 minutes)
1. Read Phases 1-4 above so you understand your plant's biology and chemistry
2. Read Phase 2 to confirm your season is right for planting
3. Prepare your workspace: {indoor/outdoor, newspaper on table, access to water}

### Day 1: Setting Up (30 minutes)
1. Fill pot with soil mix to 2cm below rim
2. Water soil thoroughly until water drains from bottom
3. Let drain for 10 minutes
4. Make a hole {X}cm deep with your finger
5. Drop in {number} seed(s)
6. Cover lightly with soil — do NOT pack down
7. Label with plant name and date
8. Place in {location with light/temperature specs}
9. Cover with plastic wrap / humidity dome (if Phase 5 says so)

### Days 2-{Germination}: Waiting
1. Check moisture daily — spray with water if surface is dry
2. Do NOT fertilize. Do NOT dig up to check.
3. Keep temperature steady at {X}°C
4. If mold appears on soil surface: remove cover for 1 hour, reduce watering

### Day {Germination}: They Sprouted!
1. Remove plastic cover if used
2. Move to bright indirect light NOW — not tomorrow
3. If using grow lights: place {X}cm above seedlings, 14-16 hours/day
4. Begin weak fertilizer at 1/4 strength (Phase 4 schedule)

### Week {Transplant}: Moving to Final Home
1. Follow hardening-off process from Phase 5
2. Transplant on a cloudy day or late afternoon (reduces shock)
3. Water deeply after transplanting

### Ongoing: Your Routine
{Paste the daily/weekly care table from Phase 5 here}

### Troubleshooting Quick Reference
| You See This | It Means This | Do This |
|---|---|---|
| Yellow leaves, bottom | Overwatering OR nitrogen deficiency | Check soil moisture first. If wet: stop watering. If dry: add nitrogen. |
| Brown crispy leaf edges | Underwatering OR potassium deficiency OR sunburn | Water more. Check for fertilizer need. Move from direct sun. |
| Leggy, stretched, thin | Not enough light | Move closer to window or lower grow light. |
| Gnats flying around soil | Overwatering, fungus gnats | Let soil dry completely. Sticky traps. |
| Holes in leaves | Pest damage | Inspect undersides of leaves. Identify pest → Phase 6 treatment. |
| Leaves curling down | Overwatering | Stop watering until soil dries. |
| No flowers after {X} weeks | Too much nitrogen (all leaves, no flowers) | Switch to flowering fertilizer (high P-K, low N). |
```

---

## Phase 8: Local Details

**Goal**: Ground the guide in the user's actual environment — not generic advice from a California gardening blog applied to a balcony in Hanoi.

### Required Adaptations

```
## Local Adaptation Guide — {Plant} in {Locale}

### Water
- **Tap water in {locale}**: Generally {soft/hard}. {If hard: let sit 24h / use filtered.}
- **Rainwater harvesting**: {feasible? legal? common? how to set up.}
- **Dry season strategy**: {how much water changes. Mulching strategy.}
- **Rainy/monsoon season**: Move under cover OR ensure drainage. {Flood risk?}

### Local Climate Threats
| Threat | When | How to Protect |
|---|---|---|
| {Heat wave >X°C} | {season} | Move to shade, mulch heavily, water at dawn |
| {Frost / cold snap} | {season} | Bring indoors, cover with cloth, don't water frozen soil |
| {Heavy rain / typhoon} | {season} | Move pots under cover, stake tall plants |
| {Drought / dry season} | {season} | Mulch 5cm deep, use ollas or drip irrigation |

### Soil in Your Area
- **Local soil type** (if planting in ground): {clay / sandy / loam / rocky}
- **Local soil pH**: Typically {acidic / neutral / alkaline} in {region}
- **Amendment needed**: {add lime / add sulfur / add compost}
- **Where to get soil tested in {locale}**: {local agricultural extension, university, or service}

### Local Fertilizer & Amendments
| Product | Local Name in {locale} | Where to Buy | Approx Cost |
|---|---|---|---|
| NPK fertilizer | "{local brand name}" | {store} | {price} |
| Compost | "{local source}" | {market / nursery} | {price} |
| Organic option | "{e.g., fish emulsion, rice water, coconut husk}" | {source} | {price} |

### Local Pests Specific to Your Region
| Pest | Local Name | Season Active | Organic Control Available Locally |
|---|---|---|---|
| {regional pest 1} | "{local name}" | {months} | {product and where to buy} |
| {regional pest 2} | "{local name}" | {months} | {product and where to buy} |

### Local Gardening Culture & Community
- **Common planting seasons in {locale}**: {tradition / lunar calendar / local wisdom}
- **Local nurseries worth visiting**: {specific names, addresses, what they specialize in}
- **Local gardening groups**: {Facebook groups, Telegram groups, community gardens in {locale}}
- **Local planting traditions**: {any cultural practices — what locals typically grow, traditional methods, festivals}
- **What grows easily in {locale}**: {list of foolproof plants for your region if this plant fails}

### Local Environmental Considerations
- **Invasive species warning**: Is {plant} invasive in your region? {Check local regulations.}
- **Water restrictions** (if any): {any local water-use laws affecting gardening}
- **Protected areas nearby**: {any restrictions on collecting wild plants, seeds, or soil}
```

---

## Final Synthesis

After all 8 phases are complete, produce a **master document** via `present_file` that compiles:

```
# Complete Planting Guide: {Plant} in {Locale}

## Quick Reference Card (Print This)
{1-page summary of all key facts}

## Full Guide
1. Plant Profile (Phase 1)
2. Locale Profile (Phase 2)
3. Biological Requirements (Phase 3)
4. Chemical Requirements (Phase 4)
5. Step-by-Step Process (Phase 5)
6. Tips & Tricks (Phase 6)
7. Beginner Tutorial (Phase 7)
8. Local Adaptation (Phase 8)
```

### Quality Gate Before Presenting

- [ ] All 8 phases completed
- [ ] Locale-specific details in Phases 2, 5, and 8 (not generic)
- [ ] Real product names and store names from the user's region
- [ ] Prices in local currency
- [ ] All claims cited with source URLs
- [ ] Beginner tutorial is followable by someone who's never touched soil

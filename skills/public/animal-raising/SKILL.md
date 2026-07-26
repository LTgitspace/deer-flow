---
name: animal-raising
description: Guide for raising any animal — from species selection to housing, feeding, health care, breeding, and local adaptation. Use when the user asks about "raise", "keep", "breed", "care for", "husbandry", "livestock", "poultry", "pet", or a specific animal name. Produces species-specific, locale-grounded step-by-step care plans.
---

# Animal Raising Skill

## Purpose

Produce a complete, actionable guide for raising a specific animal — covering species biology, housing, feeding, health care, behavior, breeding, and local adaptation. The output must be specific enough for a beginner to follow without prior experience.

---

## Phase 1: Research Animal Basics

**Goal**: General knowledge about the species.

### What to Search

- "{animal} basic care guide beginner"
- "{animal} breeds comparison"
- "{animal} lifespan size temperament"
- "{animal} legal requirements ownership"

### Required Output

```
## {Animal} — Quick Profile

- **Scientific name**: {name}
- **Type**: Mammal / Bird / Reptile / Amphibian / Fish / Insect
- **Purpose**: Pet / Meat / Eggs / Milk / Fiber / Pest control / Companion
- **Breeds common**: {list 3-5 popular breeds}
- **Adult size**: {weight × height/length}
- **Lifespan**: {years} in captivity
- **Temperament**: {docile/active/aggressive/shy}
- **Legal to own in**: {countries/states — flag restricted areas}
- **Difficulty**: Beginner / Intermediate / Expert
- **Initial cost**: {range}
- **Monthly cost**: {range}
```

---

## Phase 2: Confirm User's Setup

**Gate: Must complete before housing/enclosure design.**

### Ask with `ask_clarification`

```
"Where are you planning to keep this animal?

I need to know:
- Country / region (e.g., "Da Lat, Vietnam")
- Indoor / outdoor / both?
- Available space: {size in m² or ft²}
- Climate: {tropical / temperate / cold / arid}
- Do you have existing animals? (if so, which?)
- How many animals are you planning to keep?
- Beginner or experienced with this type of animal?"
```

### Why Setup Changes Everything

| Factor | Why It Matters |
|---|---|
| Climate | Tropical species need heat in temperate zones; arctic species need cooling in tropics |
| Space | Determines enclosure size, exercise needs, group size |
| Local laws | Some breeds banned in certain countries, permits required |
| Existing animals | Quarantine needed, disease transmission, aggression |
| Experience level | Some species require advanced husbandry skills |

### Required Output

```
## Owner Profile

- **Location**: {city, country}
- **Housing type**: Indoor / Outdoor / Barn / Apartment / Farm / Backyard
- **Available space**: {m² or ft²}
- **Climate**: {type} — {avg temp range}°C, {humidity}
- **Existing animals**: {species and count}
- **Experience level**: Beginner / Intermediate / Experienced
- **Goal**: {companion / breeding / production / rescue}
- **Children in household**: Yes / No (impacts species selection)
```

---

## Phase 3: Housing & Enclosure

**Goal**: Specific enclosure requirements — size, materials, temperature, humidity, lighting, security.

### What to Search

- "{animal} enclosure size requirements minimum"
- "{animal} housing temperature humidity range"
- "{animal} bedding substrate type"
- "{animal} enclosure security predator proof"
- "{animal} outdoor shelter coop hutch design"

### Required Output

```
## Housing Requirements

### Enclosure Size

| Number of Animals | Minimum Area | Recommended Area | Height Required |
|---|---|---|---|
| 1 | {m²} | {m²} | {cm} |
| 2-3 | {m²} | {m²} | {cm} |
| 4-6 | {m²} | {m²} | {cm} |

### Environmental Control

| Parameter | Optimal Range | Critical Else |
|---|---|---|
| Temperature | {X-Y}°C | Below {X} or above {Y} = stress/death |
| Humidity | {X-Y}% | Below {X} = respiratory issues, above {Y} = fungal |
| Ventilation | {description} | Ammonia buildup causes respiratory disease |
| Lighting | {hours/day, type} | Disrupts breeding cycle if wrong |
| Noise level | {quiet / moderate / noisy} | Excessive noise = stress |

### Bedding / Substrate

| Material | Pros | Cons | Best For |
|---|---|---|---|
| {straw} | {warm, cheap} | {dusty, mold-prone} | {outdoor, dry climates} |
| {pine shavings} | {absorbent, smell control} | {can't compost} | {indoor enclosures} |
| {sand} | {easy to clean} | {doesn't hold heat} | {reptiles, arid species} |

### Enclosure Setup

- **Flooring**: {material recommended}
- **Walls**: {material, height, ventilation}
- **Roof**: {weatherproof / insulated / mesh}
- **Security**: {predator proofing needed: wire gauge, buried fence, lock type}
- **Cleaning schedule**: Daily: {tasks}. Weekly: {tasks}. Monthly: {tasks}.
- **Local materials in {locale}**: {what's available locally, local store names, prices}
```

---

## Phase 4: Feeding & Nutrition

**Goal**: Species-specific diet, feeding schedule, supplements, and local sourcing.

### What to Search

- "{animal} diet what to feed"
- "{animal} nutritional requirements protein fat fiber"
- "{animal} food list safe toxic"
- "{animal} feeding schedule amount by age"
- "{animal} supplements vitamins minerals"
- "where to buy {animal} food in {locale}"

### Required Output

```
## Feeding Guide

### Diet Composition

| Age | Food Type | Protein | Fat | Fiber | Frequency | Amount Per Feeding |
|---|---|---|---|---|---|---|
| Baby | {milk / starter feed} | {X}% | {Y}% | {Z}% | {X} times/day | {amount} |
| Juvenile | {grower feed} | {X}% | {Y}% | {Z}% | {X} times/day | {amount} |
| Adult | {maintenance feed} | {X}% | {Y}% | {Z}% | {X} times/day | {amount} |
| Breeding / Lactating | {high-energy feed} | {X}% | {Y}% | {Z}% | {X} times/day | {amount} |

### Safe & Toxic Foods

| Safe (treats) | Toxic (NEVER feed) | Emergency Signs if Ingested |
|---|---|---|
| {food} | {food} | {symptoms} |
| {food} | {food} | {symptoms} |
| {food} | {food} | {symptoms} |

### Fresh Water

- **Type**: Tap (let sit 24h if chlorinated) / Filtered / Rainwater
- **Delivery**: Bowl / Bottle / Nipple / Drip system
- **Frequency**: Check twice daily. Change daily minimum.
- **Winter precaution**: {heated bowl / break ice / insulated container}

### Local Sourcing in {locale}

| Feed Type | Local Brand | Where to Buy | Cost | Alternative |
|---|---|---|---|---|
| Maintenance feed | {brand} | {store} | {price/kg} | {alternative} |
| Treats | {brand} | {store} | {price} | {alternative} |
| Supplements | {brand} | {store} | {price} | {alternative} |
```

---

## Phase 5: Health Care

**Goal**: Common diseases, prevention, vaccination schedule, first aid, and local vet access.

### What to Search

- "{animal} common diseases symptoms treatment"
- "{animal} vaccination schedule"
- "{animal} first aid kit essentials"
- "{animal} parasite prevention internal external"
- "{animal} signs of illness early warning"
- "veterinarian for {animal} in {locale}"

### Required Output

```
## Health Care

### Vaccination / Prevention Schedule

| Age | Vaccine / Treatment | Frequency | Notes |
|---|---|---|---|
| {week} | {vaccine} | One-time | {notes} |
| {month} | {vaccine} | Annual booster | {notes} |
| Monthly | {parasite prevention} | Monthly | {notes} |

### Common Diseases

| Disease | Symptoms | Cause | Treatment | Prevention |
|---|---|---|---|---|
| {disease} | {symptoms} | {cause} | {treatment} | {prevention} |
| {disease} | {symptoms} | {cause} | {treatment} | {prevention} |

### First Aid Kit

| Item | Purpose |
|---|---|
| {antiseptic spray} | Wound cleaning |
| {bandages} | Wound covering |
| {electrolytes} | Dehydration / stress recovery |
| {thermometer} | Check for fever — normal range: {X-Y}°C |
| {syringe} | Oral medication delivery |
| {Emergency contact} | {local vet name, phone} |

### When to Call a Vet

| Symptom | Urgency | Action |
|---|---|---|
| Not eating for {X} hours | High | Call vet same day |
| Labored breathing | Emergency | Vet immediately |
| Bleeding that won't stop | Emergency | Apply pressure, go to vet |
| Lethargy + no droppings | Medium | Observe 24h, call if persists |
| Diarrhea for > {X} hours | Medium | Electrolytes, monitor, call if worsens |

### Local Vet Access in {locale}

- **Exotic/specialist vet**: {name, address, phone}
- **General vet**: {name, address, phone}
- **Emergency clinic (24h)**: {name, address, phone}
- **Pharmacy for animal meds**: {store name}
- **Average consultation cost**: {price}
```

---

## Phase 6: Behavior & Handling

**Goal**: Understanding natural behaviors, handling techniques, socialization, and enrichment.

### What to Search

- "{animal} behavior body language signs"
- "{animal} handling techniques safe"
- "{animal} socialization taming"
- "{animal} enrichment toys activities"
- "{animal} aggression signs prevention"

### Required Output

```
## Behavior & Handling

### Body Language

| Signal | Meaning | What to Do |
|---|---|---|
| {behavior} | {meaning} | {action} |
| {behavior} | {meaning} | {action} |
| {behavior} | {meaning} | {action} |

### Safe Handling

| Situation | Correct Technique | Mistakes to Avoid |
|---|---|---|
| Picking up | {technique} | {mistake} |
| Restraining for exam | {technique} | {mistake} |
| Introducing to new animals | {technique} | {mistake} |

### Enrichment

| Type | Example | Frequency | Benefit |
|---|---|---|---|
| Physical | {activity} | Daily | Exercise, muscle tone |
| Mental | {puzzle/toy} | Rotate weekly | Prevents boredom |
| Social | {interaction} | Daily | Prevents depression |
| Environmental | {hides/perches/structures} | Ongoing | Security, natural behavior |
```

---

## Phase 7: Breeding (If Applicable)

**Gate: Only if user intends to breed.**

### Required Output

```
## Breeding Guide

- **Sexual maturity**: {age}
- **Breeding season**: {months / year-round}
- **Gestation / incubation**: {days}
- **Litter / clutch size**: {range}
- **Breeding ratio**: {male:female}
- **Nesting requirements**: {materials, privacy needed}
- **Birthing signs**: {signs labor is imminent}
- **Newborn care**: {feeding, warmth, hygiene, when to intervene}
- **Weaning**: {age}
- **Genetic concerns**: {inbreeding risks, known hereditary issues}
- **Spay/neuter recommendation**: {recommended age, benefits}
```

---

## Phase 8: Local Adaptation

**Gate: Locale confirmed in Phase 2.**

### Required Output

```
## Local Adaptation Guide — {Animal} in {Locale}

### Climate Challenges

| Season/Event | Threat | Prevention | Emergency Action |
|---|---|---|---|
| {Heat wave} | Heat stress, death | Shade, water misting, ventilation | Ice packs, vet immediately |
| {Cold snap} | Hypothermia, frostbite | Heated enclosure, deep bedding, wind blocks | Warm slowly, vet |
| {Rainy season} | Mud, fungal infections, parasites | Covered area, drainage, daily cleaning | Dry and treat affected areas |
| {Dry season} | Dehydration, dust = respiratory | Extra water sources, wet feed, misting | Electrolytes |

### Local Disease Risks

| Disease | Common in {locale}? | Prevention |
|---|---|---|
| {disease} | Yes / No | {vaccine / management practice} |

### Local Laws & Permits

- **Ownership**: {allowed / restricted / banned}
- **Permit required**: Yes / No — {details, where to apply, cost}
- **Microchipping/registration**: {requirements}
- **Housing regulations**: {min enclosure size mandated by law}
- **Noise complaints**: {what to expect, soundproofing}
- **Waste disposal**: {manure management regulations if applicable}
- **Transport**: {rules for moving animal}
- **Slaughter** (if applicable): {legal requirements / halal / kosher}

### Local Supplies & Services

| Item | Local Source | Cost | Note |
|---|---|---|---|
| Feed | {store/supplier name} | {price} | {if seasonal, note availability} |
| Bedding | {store/supplier name} | {price} | {alternative in off-season} |
| Vet | {clinic name} | {consult price} | {specialist level} |
| Supplies | {store name} | {range} | {recommended brand} |

### Local Community

- {Facebook group name / WhatsApp group / forum}
- {local breeder / rescue / association}
- {seasonal show / competition / fair}
```

---

## Phase 9: Daily Care Schedule

**Goal**: A printable daily, weekly, monthly schedule.

```
## Care Schedule — Quick Reference

### Daily
| Time | Task |
|---|---|
| Morning | Check water, feed, inspect all animals, clean droppings, observe behavior |
| Midday | Check water temp (outdoor), treat any issues spotted |
| Evening | Feed (if 2x/day), secure enclosure, check for illness |

### Weekly
- Deep clean enclosure / change bedding
- Weigh animals (track in log)
- Trim nails / hooves / beaks if needed
- Check for parasites (visible inspection)

### Monthly
- Deep disinfection of enclosure
- Stock up on feed and supplies
- Review health records
- Check enclosure for wear, damage, security gaps

### Seasonal
| Season | Tasks |
|---|---|
| Spring | Breeding prep, vaccinations, parasite prevention start, deep clean after winter |
| Summer | Heat management, extra water, shade, fly control |
| Autumn | Prepare for cold, stock up feed, reinforce shelter, breeding wind-down |
| Winter | Heat lamps, deep bedding, check water heater daily, reduce outdoor time |
```

---

## Bare Minimum

| Phase | Minimum deliverable |
|---|---|
| Basics | Species profile + 3 breed options |
| Setup | Enclosure size + temperature + humidity + lighting |
| Feeding | Diet per age + feeding schedule + 3 toxic foods to avoid |
| Health | 3 common diseases + first aid kit + local vet contact |
| Behavior | 3 body language signals + safe handling technique |
| Daily care | Daily checklist printable |
| Local | Climate adaptation + local laws |
| Beginner tutorial | Shopping list + step-by-step first 7 days |

### Quality Gates

- [ ] Every temperature/humidity/metric is a NUMBER — not "warm" but "24-28°C"
- [ ] Every local section has locale-specific content — not generic copy-paste from a temperate-climate guide
- [ ] Feed types include actual product names available in the user's country
- [ ] Vet contacts are researched and named
- [ ] Legal section addresses the user's specific jurisdiction
- [ ] Beginner can follow the daily schedule without prior experience

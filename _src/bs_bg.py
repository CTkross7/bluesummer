# -*- coding: utf-8 -*-
"""배경 CG 68장. run() / redo(["CAF2R","STA4"])"""
import os, sys, time
sys.path.insert(0, "/kaggle/working/BLUESUMMER")
import bs_config as C, bs_engine as E, bs_state as ST, bs_upload as U, bs_log as L

DEST = os.path.join(ST.DIST, "bg")

BG = {
"BCH1": "wide empty sandy beach at early morning, low sun on the left, very long soft shadows, calm turquoise sea, closed folded parasols in a row, thin sea mist over water, cool pale blue morning light, wet sand reflecting sky",
"BCH2": "crowded summer beach at high noon, dozens of colorful parasols and beach tents, harsh white sunlight from above, short hard shadows, turquoise sea, heat haze over sand, lifeguard watchtower, cloudless deep blue sky",
"BCH3": "beach at golden hour, entire sea and sky washed in deep orange, sun touching the horizon, extremely long shadows across sand, warm rim light on wave crests, wet sand mirroring the sky",
"BCH4": "beach at night, dark indigo sea, distant town lights along the coastline, faint moonlight path on the water, foam glowing pale, starry summer sky, cool blue black tones",
"BCH3R": "beach in rain at dusk, grey overcast sky, choppy grey green sea, rain rings on wet sand, one abandoned tilted parasol, desaturated muted palette, rain streaks",
"PIE1": "concrete breakwater pier with a small red lighthouse at dawn, tetrapods along the side, fishing rods on the railing, pale lavender pink sky, calm dark sea",
"PIE3": "breakwater pier at sunset, red lighthouse silhouetted against burning orange sky, long pier line into the sea, sun glitter path on orange water, dramatic backlight",
"PIE4": "breakwater at night, red lighthouse lamp blinking, black glossy sea, single lamp post glow on wet concrete, clear starry sky, deep navy and red contrast",
"PIE4R": "breakwater in stormy night rain, waves crashing over tetrapods, white spray, red lighthouse light diffused through rain, wind blown rain streaks, cold blue grey palette",
"CMP1": "forest campground in morning mist, dome tents on grass, wet dewy grass, tall pine trees, god rays cutting through mist, small wooden cabin, cool green light",
"CMP3": "campground in late afternoon, warm orange light through trees, tents with tarps, folding chairs, stacked firewood, long tree shadows over grass",
"CMP4": "campground at night, glowing campfire embers, tents lit warm from inside, the milky way filling the sky, silhouetted pine trees, string lights, deep blue with warm orange accents",
"CMP4R": "campsite in night rain, large tarp with water pouring off the edge, one dim lantern, wet muddy ground, rain visible in lantern light",
"MKT3": "korean seaside night market street setting up at dusk, rows of food stalls, bulbs just switched on, purple blue dusk sky, steam rising, hand painted signboards",
"MKT4": "crowded korean night market at night, dense rows of hanging warm bulbs, food stalls with steam and smoke, colorful signs, bokeh light orbs, warm amber glow",
"MKT4R": "night market in rain, clear plastic sheets over stalls, wet ground mirroring bulb lights, dripping awnings, warm lights against cold rain",
"CAF1": "exterior of a two story wooden seaside cafe in the morning, faded blue paint, open sign, potted plants, bicycle on the wall, cool morning shadow",
"CAF2": "cafe interior at noon, huge window with strong sunlight streaming in, wooden tables, espresso machine, hanging plants, dust motes in sunbeams, warm wood tones",
"CAF3": "cafe second floor window seat at sunset, the sea visible through the glass, warm orange light flooding the wooden interior, long window frame shadows",
"CAF2R": "cafe interior during heavy rain, condensation and running droplets on the window, grey rainy street blurred outside, warm yellow lamp light, steam from a cup",
"GST1": "courtyard of an old korean two story wooden guesthouse in the morning, laundry lines with white sheets, outdoor water tap, blue painted metal gate, morning sun on the wall",
"GST2": "guesthouse courtyard at bright noon, harsh sun on concrete, wooden low platform in the shade, coiled hose, worn wooden facade, faded blue gate",
"GST3": "guesthouse courtyard at dusk, warm bulb over the wooden platform, mosquito coil smoking, watermelon rind on a tray, orange sky above the roofline",
"GST4": "old guesthouse exterior at night, one second floor window glowing warm, dark narrow alley, tangled power lines, a single street lamp, sliver of dark sea",
"LGH2": "white lighthouse on a grassy cliff at noon, deep blue sky, wind bending the grass, blue sea far below, winding concrete path, bright clean high contrast",
"LGH3": "lighthouse at sunset, orange and pink gradient sky, tower catching warm light, long shadow across the grass, sea horizon glowing",
"LGH4": "lighthouse at night, rotating beam cutting through the dark, dense stars, black sea below, warm light from a small window, deep navy palette",
"LGH4R": "lighthouse in a storm at night, thick dark clouds, heavy rain, the beam diffused into a glowing cone, waves smashing the rocks, wind bent grass",
"VLY1": "mountain valley stream in early morning, mist hovering above clear water, wet mossy rocks, dense green foliage, cool blue green light",
"VLY2": "valley stream at noon, brilliant dappled sunlight through the canopy, crystal clear shallow water over smooth rocks, light reflections on stones, wooden platforms",
"VLY3": "valley stream in late afternoon, cooler dimmer light in the ravine, empty wooden platforms, a rolled up mat, deep green shade",
"POL2": "rooftop swimming pool at noon, brilliant turquoise water, white loungers and parasols, glass railing, town and sea view, caustic light patterns on the pool floor",
"POL3": "rooftop pool at sunset, water surface reflecting orange and pink, empty loungers, silhouetted railing, sea horizon and rooftops beyond",
"POL4": "rooftop pool at night, underwater lights glowing electric blue, town lights and dark sea behind, ripples, small hanging lanterns, cyan palette",
"PLZ2": "town plaza with a festival stage under construction at noon, scaffolding and trusses, hanging banners, shipping container office, coiled cables",
"PLZ3": "festival plaza at dusk, hundreds of paper lanterns being lit, purple blue sky, warm lantern glow spreading, stage lights warming up, food stalls",
"PLZ4": "festival plaza at night in full swing, dense hanging paper lanterns, stage spotlights, lit fountain, warm amber light, bokeh orbs, distant fireworks",
"PLZ3R": "festival plaza in evening rain, blue tarps over equipment, a few lanterns glowing wetly, puddles reflecting lights, grey wet stage",
"CVS1": "korean convenience store front in the early morning, glass facade, plastic tables and parasols outside, delivery crates, cool blue morning light, empty road",
"CVS3": "convenience store front at dusk, glowing sign against a purple sky, plastic tables outside, warm interior light spilling onto the pavement",
"CVS4": "convenience store at 4AM, the only lit thing on a pitch dark street, cold white fluorescent glow, empty asphalt road, one flickering streetlamp, cinematic",
"CVS3R": "convenience store front in evening rain, wet asphalt mirroring the neon sign, umbrella stand, rain streaming off the awning, strong reflections",
"FOR1": "forest trail in the morning, thick mist between trunks, god rays through the canopy, wet dirt path, dense green undergrowth, ferns",
"FOR2": "forest trail at noon in deep summer, dazzling dappled light through dense leaves, narrow dirt path, a small wooden pavilion, overwhelming green",
"FOR3": "forest trail in late afternoon, low golden light raking horizontally through trunks, long stripes of light and shadow, dust in the light beams",
"FOR2R": "forest trail in rain, everything soaked and glossy, water dripping from leaves, mist rising, dark wet trunks, wooden pavilion, deep saturated green",
"OBS2": "hilltop observation deck at noon, wooden railing and benches, sweeping view of the town and blue sea below, coin telescope, brilliant sunlight",
"OBS3": "hilltop observation deck at golden hour, town and sea drenched in orange, wooden benches backlit, sun on the sea horizon, long shadows across the deck",
"OBS4": "hilltop observation deck at night, town lights spread below like scattered coins, glowing vending machine as the only light source, dense stars",
"OBS3R": "hilltop observation deck in evening rain, thick fog swallowing the view, wet wooden railing, water beading on benches, grey monochrome atmosphere",
"STA2": "abandoned railway station converted into a bookstore, noon light, overgrown platform with knee high weeds, rusted rails in grass, stacked old books, dust motes in sunbeams",
"STA3": "abandoned station at dusk, string lights hung along the platform, books on folding tables, purple orange sky, rusted rails catching the last light",
"STA4": "abandoned station platform at 3AM, one bare bulb swinging, thick fog, tall weeds, rusted rails vanishing into darkness, old water tower silhouette, eerie",
"STA2R": "abandoned station in daytime rain, water dripping through the broken roof, puddles on the concrete platform, rain-darkened weeds, grey diffused light",
"HRB1": "fishing harbor at 4:30AM, fishing boats moored, crates of ice, harsh fluorescent work lamps over the auction floor, dark blue predawn sky, wet concrete quay",
"HRB2": "fishing harbor at noon, boats on bright blue water, nets drying on the quay, orange buoys, white hot sunlight, seagulls on the bollards",
"HRB3": "fishing harbor at sunset, moored boats silhouetted against orange water, long reflections, drying nets glowing warm, stacked blue crates",
"HRB4": "fishing harbor at night, boat cabin lights reflected in black water, a single sodium lamp on the quay, dark hulls, coiled rope, deep navy and amber",
"DIV1": "small diving shop exterior in the morning, wetsuits hanging outside to dry, air tanks against the wall, faded sign, harbor beyond, salt worn paint",
"DIV2": "diving shop interior at noon, racks of wetsuits, air tanks, masks and fins on hooks, workbench with gauges, bright sea light through the open door",
"DIV3": "underwater scene, deep blue water, sun rays piercing down from the surface, streams of bubbles, rocky reef below, small fish schooling, serene and vast",
"TWN2": "small korean rural town main street at noon, old faded shop signs, a bank, a pharmacy, a bus stop, harsh sunlight, worn concrete buildings",
"TWN3": "town main street at dusk, shop signs lighting up one by one, orange sky over low rooftops, a shuttered storefront, provincial evening",
"TWN4": "town main street at night, most shutters closed, one 24-hour sign glowing, empty road, sodium streetlamps, small town emptiness",
"ROM1": "small second floor guesthouse room in the morning, sunlight through a thin curtain onto a folded futon, an electric fan, low wooden desk, suitcase, worn wallpaper",
"ROM3": "small guesthouse room at sunset, orange light flooding through the open window, the curtain lifting in the sea breeze, dust in the light, fan slowly turning",
"ROM4": "small guesthouse room at night, a single warm bulb, open window with dark blue sky and distant town lights, electric fan, folded futon, tropical night heat",
"ROM4R": "small guesthouse room during night rain, rain streaking the dark window, warm dim lamp light inside, a towel hung to dry, cool blue outside versus warm inside",
}


def _seed(code, salt=0):
    import hashlib
    h = hashlib.sha256(("bg|%s|%s|%d" % (C.LORA_VER, code, salt)).encode()).hexdigest()
    return int(h[:8], 16) % 2147483647


def _gen(codes, overwrite=False, budget=None):
    os.makedirs(DEST, exist_ok=True)
    pr = L.Progress(len(codes), "배경")
    fails = []
    for code in codes:
        if code not in BG:
            L.warn("미정의 배경 코드 %s" % code)
            continue
        if budget is not None and not budget.can(ST.timing_avg("bg",
                                                               C.EST_BG_MIN * 60) / 60):
            L.warn("시간 예산 부족 - 배경 중단")
            break
        path = os.path.join(DEST, code + ".webp")
        prompt = "%s, %s, BREAK, %s" % (C.SCENERY_HEAD, BG[code], C.TAIL)
        _, _, note = E.make(prompt, C.NEG_BG, path, seed=_seed(code, ST.retry_of(code)),
                            bg=True, overwrite=overwrite)
        if note == "fail":
            fails.append(code)
            ST.bump_retry(code)
        pr.step("%s.webp %s" % (code, note))
        if pr.n % C.PUSH_EVERY == 0:
            U.push("bg %d" % pr.n, force=True)
    pr.done()
    ST.rescan()
    U.push("bg done", force=True)
    return fails


def run(overwrite=False, budget=None):
    return _gen(list(BG.keys()), overwrite, budget)


def redo(codes, budget=None):
    return _gen(list(codes), True, budget)


if __name__ == "__main__":
    run()

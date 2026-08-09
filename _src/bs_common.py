
# -*- coding: utf-8 -*-
QUALITY = ("masterpiece, best quality, very aesthetic, absurdres, "
           "highly detailed, official art, anime screencap style, "
           "soft summer lighting")
NEG = ("lowres, worst quality, low quality, bad anatomy, bad hands, "
       "missing fingers, extra digits, fewer digits, jpeg artifacts, "
       "signature, watermark, username, text, error, cropped, blurry, "
       "multiple views, multiple girls, 3d, realistic photo, nsfw, nude")

BASE_TAGS = {
 "HRM": "1girl, solo, Yun Haram, tan skin, brown high ponytail, amber eyes, athletic toned body, scar on left knee, sharp gaze",
 "SRA": "1girl, solo, Seo Ria, pale skin, black bob cut, blunt bangs, dark green eyes, silver rimmed glasses, ear cuff on right ear, calm expression",
 "MJO": "1girl, solo, Mun Jio, long ash brown wavy hair, half updo, hazel eyes, mole under left eye, tall slender, camera strap",
 "HTI": "1girl, solo, Ha Taei, short orange red hair, freckles, light green eyes, petite, bandage on right cheek, energetic",
 "KYS": "1girl, solo, Kang Yeseol, very pale skin, long platinum blonde straight hair, grey blue eyes, half-lidded eyes, tall, black nail polish",
 "LCH": "1girl, solo, Im Choha, warm beige skin, chestnut long wavy side ponytail, light brown eyes, whistle necklace, confident",
 "BRW": "1girl, solo, Baek Rowon, pale skin, chin length pale blue hair, asymmetrical bangs, light grey eyes, slim, headphones around neck",
 "CSM": "1girl, solo, Cha Somin, healthy skin, light brown low twin braids, round hazel eyes, flower hairpin, bright smile",
 "JHO": "1girl, solo, Jeong Haeoreum, deep tan skin, black wet undercut bob, dark grey eyes, muscular, shark tooth necklace",
 "YDH": "1girl, solo, Yu Danha, fair skin, orange medium hair, half bun, drooping green eyes, petite, leaf hairpin",
 "PSA": "1girl, solo, Pyo Sea, pale skin, long black hair with purple inner color, dark purple eyes, eyebags, thin, chain choker",
 "OMR": "1girl, solo, O Mireu, porcelain skin, very long white straight hair, heterochromia, blue left eye, golden right eye, red ribbon on wrist",
}

TRIGGER = {c: f"bs{c.lower()}" for c in BASE_TAGS}

OUTFIT_TAGS = {
 "HRM": {"W":"red lifeguard swimsuit, open yellow windbreaker, whistle, rescue tube",
         "C":"white tank top, denim shorts, sandals",
         "B":"red one piece swimsuit, barefoot on sand",
         "N":"oversized grey t-shirt, cotton shorts, indoors",
         "F":"navy summer festival yukata style dress, hair ornament",
         "R":"transparent raincoat, wet hair, wet clothes"},
 "SRA": {"W":"white shirt, dark green cafe apron, name tag",
         "C":"linen blouse, long skirt, tote bag",
         "B":"navy sporty swimsuit, beach cover-up",
         "N":"grey knit cardigan, pajama shorts",
         "F":"mint summer festival dress, small hairpin",
         "R":"beige raincoat, wet bangs, holding umbrella"},
 "MJO": {"W":"loose linen shirt, cargo shorts, camera around neck",
         "C":"black crop top, wide pants, sunglasses on head",
         "B":"black bikini with sheer shirt over",
         "N":"silk camisole, loose pants, indoors",
         "F":"purple yukata style summer dress",
         "R":"khaki poncho, wet camera bag"},
 "HTI": {"W":"food stall apron, bandana, arm sleeves",
         "C":"graphic t-shirt, denim overalls shorts",
         "B":"orange two piece swimsuit, swim ring",
         "N":"loose tank top, shorts, hair down",
         "F":"red festival happi coat style top",
         "R":"yellow raincoat, rubber boots"},
 "KYS": {"W":"oversized black cardigan, white shirt, reading glasses",
         "C":"black long dress, straw hat",
         "B":"black swimsuit, thin shawl",
         "N":"large white shirt only, bare legs, indoors",
         "F":"black yukata style dress, red obi",
         "R":"black umbrella, wet shoulders"},
 "LCH": {"W":"staff t-shirt, cap, clipboard, lanyard",
         "C":"striped shirt, khaki shorts",
         "B":"blue two piece swimsuit, rash guard open",
         "N":"training wear, towel on shoulders",
         "F":"blue festival dress, flower crown",
         "R":"navy rain jacket, wet hair"},
 "BRW": {"W":"grey work jacket, thin sweater, gloves",
         "C":"oversized hoodie, long skirt",
         "B":"white swimsuit, long sleeve rash guard",
         "N":"pale blue pajama set",
         "F":"white yukata style dress, pale blue accents",
         "R":"clear vinyl raincoat, night rain"},
 "CSM": {"W":"guesthouse apron, rolled sleeves shirt",
         "C":"yellow sundress, sandals",
         "B":"polka dot two piece swimsuit",
         "N":"cotton pajamas, hair loose",
         "F":"pink summer festival dress, hair flowers",
         "R":"pink raincoat, holding two umbrellas"},
 "JHO": {"W":"black wetsuit half unzipped, rash guard",
         "C":"open shirt over sports bra, board shorts",
         "B":"black athletic bikini, diving mask on forehead",
         "N":"loose tank top, sweatpants",
         "F":"dark blue yukata style dress",
         "R":"waterproof jacket, dripping wet"},
 "YDH": {"W":"campsite staff vest, checkered shirt, work gloves",
         "C":"beige knit top, long skirt",
         "B":"green one piece swimsuit, sun hat",
         "N":"oversized pajama shirt, thick socks",
         "F":"light green festival dress, leaf motif",
         "R":"olive rain poncho, muddy boots"},
 "PSA": {"W":"convenience store uniform vest, name tag reversed",
         "C":"black band t-shirt, ripped jeans",
         "B":"black bikini with oversized shirt",
         "N":"loose black tank top, shorts, messy hair",
         "F":"black festival outfit, stage lighting",
         "R":"soaked hoodie, wet purple hair"},
 "OMR": {"W":"white travel coat, small suitcase",
         "C":"white blouse, layered skirt, ribbon",
         "B":"white swimsuit, sheer wrap",
         "N":"white slip dress, indoors",
         "F":"white and gold yukata style dress",
         "R":"white umbrella, rain, ethereal"},
}

EMO_TAGS = {
 "01": "neutral expression, looking at viewer",
 "02": "soft smile, gentle eyes",
 "03": "laughing, open mouth, happy, closed eyes",
 "04": "blushing, embarrassed, averted eyes",
 "05": "surprised, wide eyes, open mouth",
 "06": "pouting, annoyed, puffed cheeks",
 "07": "serious expression, narrowed eyes",
 "08": "sad, teary eyes, downcast",
 "09": "sleepy, half-lidded eyes, relaxed",
 "10": "shy happy, slight blush, looking away, heartfelt",
}

CHAR_FRAME = ("upper body, simple soft background, bokeh, "
              "portrait composition, centered")

LOC = {
 "BCH":"wide sandy beach, parasols, blue sea, south korean coastal town",
 "PIE":"red lighthouse breakwater, tetrapods, fishing rods, open sea",
 "CMP":"riverside campground, tents, tarps, pine trees, fire pit",
 "MKT":"night market street, food stalls, hanging lights, crowd",
 "CAF":"two story wooden cafe, large windows, sea view, plants",
 "GST":"old two story wooden guesthouse, blue gate, yard with water tap",
 "LGH":"white lighthouse on grassy hill, winding path, sea horizon",
 "VLY":"mountain valley stream, clear shallow water, rocks, forest",
 "POL":"rooftop swimming pool, sun beds, city and sea view",
 "PLZ":"town culture plaza, fountain, outdoor stage, banners",
 "CVS":"24 hour convenience store, bright interior, parasol tables outside",
 "FOR":"forest trail, tall trees, cicadas, dappled light, small pavilion",
 "OBS":"hilltop sunset observatory deck, benches, vending machine, sea below",
 "STA":"abandoned train station, rusty rails, overgrown platform, bookshop",
 "HRB":"fishing harbor, boats, ice boxes, nets, auction floor",
 "DIV":"diving shop by the sea, tanks, wetsuits hanging, small pier",
 "TWN":"small korean downtown street, low buildings, shops, few people",
 "ROM":"small tatami-less korean room, window, electric fan, single bed",
}

TIME = {
 "1":"early morning, long shadows, cool blue air, few people",
 "2":"midday, harsh white sunlight, heat haze, bright",
 "3":"golden hour sunset, orange light, long shadows",
 "4":"night, streetlights, deep blue sky, warm lamps",
}
RAIN = "heavy summer rain, wet ground reflections, grey sky, puddles"

BG_FRAME = ("scenery, no humans, wide angle, anime background art, "
            "detailed environment, cinematic")

UI = {
 "status":"summer beach banner, blue sea gradient, minimal, no text",
 "album":"polaroid photos scattered on wooden table, summer, no text",
 "talk":"messenger bubble motif, soft blue gradient, minimal, no text",
 "town":"small coastal town skyline silhouette, dusk, minimal, no text",
 "map":"hand drawn coastal town map texture, paper, minimal, no text",
 "card":"row of empty benches at seaside, soft light, minimal, no text",
 "sns":"bulletin board with paper notes, summer light, no text",
 "radio":"old radio on windowsill at dawn, sea outside, no text",
}

def char_prompt(code, outfit, emo, with_lora=True, weight=0.9):
    base = BASE_TAGS[code]
    fit  = OUTFIT_TAGS[code][outfit]
    emo_t = EMO_TAGS[emo]
    lora = f"<lora:bs_{code.lower()}:{weight}> {TRIGGER[code]}, " if with_lora else ""
    return f"{lora}{QUALITY}, {base}, {fit}, {emo_t}, {CHAR_FRAME}"

def src_prompt(code, i):
    """LoRA 학습용 소스 : 의상/표정/각도를 흩어 다양성 확보."""
    outfits = ["W", "C", "N", "B"]
    emos = list(EMO_TAGS)
    views = ["front view", "three quarter view", "from side",
             "looking at viewer", "upper body", "cowboy shot"]
    o = outfits[i % len(outfits)]
    e = emos[(i // 2) % len(emos)]
    v = views[i % len(views)]
    return (f"{QUALITY}, {BASE_TAGS[code]}, {OUTFIT_TAGS[code][o]}, "
            f"{EMO_TAGS[e]}, {v}, simple background, consistent character design")

def bg_prompt(code):
    loc, rest = code[:3], code[3:]
    rain = rest.endswith("R")
    t = rest[0]
    p = f"{QUALITY}, {LOC[loc]}, {TIME[t]}, {BG_FRAME}"
    if rain:
        p += f", {RAIN}"
    return p

def ui_prompt(code):
    return f"{QUALITY}, {UI[code]}, banner composition, wide, {BG_FRAME}"

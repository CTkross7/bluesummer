# -*- coding: utf-8 -*-
"""캐릭터 DB + 프롬프트 조립기 + 결정론적 시드."""
import os, sys, glob, hashlib
sys.path.insert(0, "/kaggle/working/BLUESUMMER")
import bs_config as C

QUALITY = C.QUALITY_HEAD
NEG     = C.NEG_CHAR

EMO = {
 "01": "neutral expression, looking at viewer, calm eyes, relaxed standing pose",
 "02": "soft gentle smile, warm eyes, looking at viewer, slight head tilt",
 "03": "laughing, open mouth, closed eyes, cheerful, lively, head tilt",
 "04": "blush, embarrassed expression, averting eyes, hand near mouth, flustered",
 "05": "surprised, wide open eyes, open mouth, leaning back slightly, raised eyebrows",
 "06": "pouting, annoyed, furrowed brow, arms crossed, looking away, sulking",
 "07": "serious expression, narrowed eyes, straight mouth, determined, direct gaze",
 "08": "sad, teary eyes, downcast gaze, slight frown, hair shadow over eyes, melancholic",
 "09": "sleepy, half-lidded eyes, yawning, relaxed drooping shoulders, tired",
 "10": "light blush, shy smile, glancing at viewer, hand on chest, romantic warm atmosphere",
}

OUTFIT_ORDER = ["W", "C", "B", "N", "F", "R"]
EMO_ORDER    = ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10"]

FRAMING = {
 "W": "upper body, cowboy shot, looking at viewer, dutch angle, dynamic",
 "C": "cowboy shot, standing, looking at viewer, from side, dynamic pose",
 "B": "cowboy shot, dynamic pose, looking at viewer, from below, foreshortening",
 "N": "upper body, close-up, portrait, face focus, soft focus background",
 "F": "cowboy shot, looking at viewer, festival crowd bokeh, dutch angle",
 "R": "upper body, portrait, rain droplets on skin, wet hair strands, looking at viewer",
}

CHARS = {}


def add(code, trigger, anchor, outfits, scenes):
    CHARS[code] = dict(trigger=trigger, anchor=anchor, outfits=outfits, scenes=scenes)


add("HRM", "bsharam",
 "1girl, solo, adult woman, 24 years old, tanned skin, long dark brown hair, high ponytail, "
 "sharp amber eyes, glossy eyes, athletic toned body, medium breasts, red hair tie, "
 "confident expression, mature female",
 {"W": "red lifeguard rash guard, white shorts, whistle around neck, sunglasses on head, orange rescue tube",
  "C": "white tank top, denim shorts, sneakers, sports watch",
  "B": "red one-piece competition swimsuit, wet skin, water droplets, barefoot",
  "N": "oversized grey t-shirt, cotton shorts, hair down, barefoot at home",
  "F": "navy blue summer festival dress, hair ornament, holding a paper lantern",
  "R": "transparent raincoat over rash guard, wet hair, holding an umbrella"},
 {"W": "sunny beach lifeguard tower, bright summer daylight, blue sky, sea behind, lens flare",
  "C": "seaside town street, warm afternoon sunlight, dappled shadow",
  "B": "shoreline shallow water, splashing, strong backlight, sun glare, water spray",
  "N": "dim wooden guesthouse room, warm lamp light, night, tenebrism",
  "F": "summer night festival, paper lanterns, bokeh lights, warm glow",
  "R": "rainy beach entrance, grey sky, wet asphalt reflection"})

add("SRA", "bsseoria",
 "1girl, solo, adult woman, 22 years old, pale skin, black bob cut, blunt bangs, "
 "dark green eyes, glossy eyes, thin silver framed glasses, slender, small breasts, "
 "silver ear cuff, quiet expression, mature female",
 {"W": "white shirt, dark green cafe apron, rolled sleeves, holding a tray",
  "C": "beige linen shirt, long skirt, canvas tote bag, sketchbook under arm",
  "B": "navy blue simple bikini with a white shirt worn open over it, sitting, holding a sketchbook",
  "N": "loose white long sleeve shirt, shorts, no glasses, messy hair",
  "F": "mint green summer dress, small hair clip, holding a festival lantern",
  "R": "beige raincoat, rain droplets on glasses, holding a transparent umbrella"},
 {"W": "wooden cafe interior, large window light, espresso machine, hanging plants, dust in sunbeam",
  "C": "old seaside alley, warm evening light, long shadow",
  "B": "quiet corner of a beach under a parasol, soft daylight",
  "N": "small dim room, desk lamp, scattered drawings, night",
  "F": "festival plaza at night, string lights, crowd bokeh",
  "R": "inside a cafe by the window, heavy rain outside, condensation on glass"})

add("MJO", "bsjio",
 "1girl, solo, adult woman, 27 years old, light olive skin, long wavy ash brown hair, half updo, "
 "hazel eyes, glossy eyes, beauty mark under left eye, tall slender, medium breasts, "
 "relaxed confident expression, mature female",
 {"W": "black photographer vest, grey t-shirt, cargo pants, DSLR camera on a strap, lens pouch",
  "C": "loose white blouse, wide linen pants, straw hat, sandals",
  "B": "black halter bikini with an open shirt, camera in hand, sunglasses",
  "N": "silk camisole, loose pajama pants, hair down, holding a glass",
  "F": "dark red summer dress, gold earrings, camera around neck",
  "R": "olive rain poncho, camera sheltered under it, wet strands of hair"},
 {"W": "hilltop observatory deck, golden hour, sea horizon behind, lens flare",
  "C": "narrow town alley, harsh noon shadows",
  "B": "rocky shore, strong sunlight, sea spray",
  "N": "hotel room balcony at night, town lights below, bokeh",
  "F": "night festival street, distant fireworks in the sky",
  "R": "under a shop awning, curtain of rain, neon reflection"})

add("HTI", "bstaei",
 "1girl, solo, adult woman, 20 years old, fair skin, short messy red orange hair, "
 "freckles across the nose, bright yellow green eyes, glossy eyes, petite, small breasts, "
 "bandaid on right cheek, energetic expression, mature female",
 {"W": "black night market apron, rolled up sleeves, headband, holding grilled skewers",
  "C": "oversized graphic t-shirt, denim shorts, worn sneakers, crossbody bag",
  "B": "orange striped bikini, rash guard tied around the waist, holding shaved ice",
  "N": "tank top, pajama shorts, sitting cross legged, holding instant noodles",
  "F": "yellow summer festival dress, hair pins, holding a goldfish scooping net",
  "R": "cheap yellow vinyl raincoat, soaked sneakers, annoyed expression"},
 {"W": "crowded night market stall, warm bulb lights, steam, food stalls behind, bokeh",
  "C": "small town convenience store front, afternoon",
  "B": "busy summer beach, parasols, bright sun",
  "N": "cramped small room, TV glow, late night",
  "F": "festival street, lanterns, fireworks light on her face",
  "R": "night market in rain, wet ground reflecting lights"})

add("KYS", "bsyeseol",
 "1girl, solo, adult woman, 26 years old, very pale skin, long straight platinum silver hair, "
 "grey blue eyes, glossy eyes, half-lidded tired eyes, tall, large breasts, black nail polish, "
 "apathetic expression, mature female",
 {"W": "oversized black cardigan, white shirt, long skirt, holding an old book",
  "C": "black long dress, sandals, silver rings",
  "B": "black bikini under a sheer black cover-up, wide brim hat, sitting on a rock",
  "N": "black slip dress, bare shoulders, loosely tied hair, reading in bed",
  "F": "deep purple summer dress, minimal accessories, bored expression",
  "R": "black raincoat, wet silver hair sticking to her cheek, closed umbrella"},
 {"W": "abandoned train station bookstore interior, dust in light beams, stacked books, tenebrism",
  "C": "overgrown railway platform, rusty tracks, weeds",
  "B": "empty rocky shore, overcast sky",
  "N": "dim room, a single hanging bulb, piles of books, night",
  "F": "the far edge of a festival, lanterns in the distance",
  "R": "station platform under heavy rain, water dripping from the roof"})

add("LCH", "bschoha",
 "1girl, solo, adult woman, 23 years old, warm beige skin, long chestnut brown wavy hair, "
 "side ponytail, bright brown eyes, glossy eyes, medium breasts, whistle necklace, "
 "confident reliable expression, mature female",
 {"W": "staff t-shirt, cargo shorts, clipboard in hand, radio on belt, cap",
  "C": "white blouse, high waist jeans, tote bag, sunglasses on head",
  "B": "coral pink bikini with a sarong, energetic pose",
  "N": "large hoodie, bare legs, hair down, exhausted, holding a mug",
  "F": "white and blue festival dress, flower hairpiece, holding a lantern",
  "R": "clear plastic poncho over staff shirt, wet clipboard, still working"},
 {"W": "festival plaza with a stage under construction, container office, daylight",
  "C": "town main street, shops, afternoon",
  "B": "beach volleyball area, bright sun",
  "N": "container office at night, desk lamp, papers everywhere",
  "F": "festival main stage, lantern lights, crowd behind, spotlight",
  "R": "plaza in rain, tarps over equipment, grey sky"})

add("BRW", "bsrowon",
 "1girl, solo, adult woman, 25 years old, pale skin, chin length pale blue hair, "
 "asymmetric bangs, pale grey eyes, glossy eyes, thin, small breasts, "
 "large headphones around neck, quiet dreamy expression, mature female",
 {"W": "navy work jacket, grey shirt, holding a flashlight",
  "C": "oversized knit cardigan, long skirt, sneakers, hands in pockets",
  "B": "pale blue simple swimsuit with an oversized shirt, sitting on stone steps",
  "N": "grey pajama set, headphones on, sitting at a broadcast desk with a microphone",
  "F": "pale blue summer dress, star hairpin, looking up",
  "R": "navy raincoat with the hood up, wet face, standing in the rain"},
 {"W": "lighthouse interior, control panel, warm indicator lights, night",
  "C": "hill road to the lighthouse, dusk, sea below",
  "B": "lighthouse stone steps, morning sea, soft light",
  "N": "small radio broadcast booth, 3AM, dark blue tone, rim light",
  "F": "lighthouse hill overlooking distant festival fireworks",
  "R": "lighthouse in a storm, rain, dark clouds"})

add("CSM", "bssomin",
 "1girl, solo, adult woman, 21 years old, healthy skin, light brown low twin braids, "
 "round hazel eyes, glossy eyes, medium breasts, floral hairpin, "
 "cheerful friendly expression, mature female",
 {"W": "light blue apron over a t-shirt, rubber gloves, holding a laundry basket",
  "C": "yellow sundress, straw hat, sandals, small bag",
  "B": "white and pink frilled bikini, holding an inflatable ring, splashing",
  "N": "pink printed pajamas, untied hair, holding a slice of watermelon",
  "F": "pink and white festival dress, hair flowers, holding cotton candy",
  "R": "floral umbrella, light cardigan, rolled up pants, stepping over a puddle"},
 {"W": "guesthouse courtyard, laundry lines, morning sun, water tap, backlight",
  "C": "seaside town street, bright noon",
  "B": "shallow beach water, bright summer, water splash",
  "N": "wooden guesthouse porch at night, mosquito coil, warm light",
  "F": "festival street, lanterns, crowd bokeh",
  "R": "guesthouse gate in rain, wet blue door"})

add("JHO", "bshaeorm",
 "1girl, solo, adult woman, 29 years old, deeply tanned skin, short black undercut bob, "
 "wet look hair, dark grey eyes, glossy eyes, muscular athletic body, large breasts, "
 "shark tooth necklace, calm mature expression, mature female",
 {"W": "black wetsuit unzipped to the waist with a sports top underneath, towel on shoulder",
  "C": "black tank top, olive shorts, flip flops, arms crossed",
  "B": "black high neck sports bikini, wet skin, diving mask on forehead",
  "N": "loose linen shirt open over a sports top, shorts, sitting, holding a can",
  "F": "simple dark blue summer dress, uncomfortable expression, hand on neck",
  "R": "already soaked, no umbrella, wet tank top, indifferent to the rain"},
 {"W": "diving shop interior, tanks and gear, sea visible through the open door",
  "C": "harbor pier, fishing boats, late afternoon",
  "B": "underwater blue light, bubbles, sun rays from the surface, caustics",
  "N": "harbor at night, boat lights on the water, sitting on a bollard",
  "F": "the edge of a festival near the harbor, lanterns",
  "R": "pier in heavy rain, grey sea"})

add("YDH", "bsdanha",
 "1girl, solo, adult woman, 22 years old, fair skin, medium orange hair, half-up bun, "
 "drooping green eyes, glossy eyes, small breasts, leaf hairpin, "
 "gentle quiet expression, mature female",
 {"W": "green camping staff vest, plaid shirt, work gloves, holding firewood",
  "C": "cream knit top, long brown skirt, boots, small backpack",
  "B": "green gingham bikini with shorts, sitting by a stream, feet in the water",
  "N": "beige oversized sweater, shorts, a blanket over her shoulders",
  "F": "soft green summer dress, leaf hairpin, holding a small lantern",
  "R": "khaki poncho, hood up, holding an umbrella"},
 {"W": "campground management office, tents in the background, morning mist, god rays",
  "C": "forest trail, dappled sunlight through leaves",
  "B": "valley stream, clear water, rocks, green shade",
  "N": "campfire at night, tent glow, milky way, warm rim light",
  "F": "standing at the quiet edge of a festival with a lantern",
  "R": "rainy campsite, tarp, water dripping"})

add("PSA", "bsseah",
 "1girl, solo, adult woman, 25 years old, pale skin, long black hair with purple inner streaks, "
 "dark purple eyes, glossy eyes, eye bags, thin, medium breasts, silver chain choker, "
 "tired apathetic expression, mature female",
 {"W": "convenience store uniform vest over a black shirt, leaning on the counter",
  "C": "oversized black band t-shirt, ripped jeans, headphones, boots",
  "B": "black bikini with a black cover-up shirt, sitting in the shade",
  "N": "black tank top, shorts, messy hair, holding an electric guitar, sitting on the floor",
  "F": "black stage outfit, choker, holding a microphone, intense expression",
  "R": "soaked black hoodie, no umbrella, walking in the rain, unbothered"},
 {"W": "convenience store interior at 4AM, cold fluorescent light, dark outside the glass",
  "C": "empty town street at dusk, closed shutters",
  "B": "beach under parasol shade, harsh sunlight outside",
  "N": "small storage room, amplifier, cables, a single bulb, night",
  "F": "festival stage, spotlight, crowd silhouettes, dramatic lighting, lens flare",
  "R": "rain at night, streetlight, wet asphalt reflection"})

add("OMR", "bsmireu",
 "1girl, solo, adult woman, 23 years old, porcelain skin, very long straight white hair, "
 "heterochromia, blue left eye, gold right eye, glossy eyes, medium breasts, "
 "thin red ribbon on wrist, ethereal mysterious smile, mature female",
 {"W": "white blouse, long white skirt, straw hat, small vintage suitcase",
  "C": "white sundress, bare shoulders, sandals, holding a seashell",
  "B": "white bikini with a sheer white wrap, standing in shallow water",
  "N": "white nightgown, hair down, sitting by an open window, moonlight",
  "F": "pure white festival dress, red ribbon, holding a glowing lantern",
  "R": "white dress soaked in rain, no umbrella, smiling, hair stuck to her face"},
 {"W": "an unfamiliar street corner, no other people, soft light",
  "C": "sunset beach, long shadow, empty, backlight",
  "B": "dusk shoreline, purple sky, reflection on wet sand",
  "N": "dark room, moonlight through the window, curtain moving",
  "F": "festival crowd but she stands out, dreamlike bokeh, light particles",
  "R": "empty rainy road, grey, cinematic"})


def lora_file(code):
    return "bs_%s_%s.safetensors" % (code, C.LORA_VER)


def lora_ready(code):
    """LoRA 가 실제로 배치돼 있는지 확인. 없으면 LoRA 없이 생성한다."""
    if not C.ENABLE_LORA:
        return False
    for d in ("/kaggle/temp/models/Lora", "/kaggle/working/BLUESUMMER/lora_out"):
        if os.path.exists(os.path.join(d, lora_file(code))):
            return True
    return False


def seed_of(code, outfit, emo, salt=0):
    """조합마다 고정된(재현 가능한) 시드. 재시도 시 salt 로 흔든다."""
    key = "%s|%s|%s|%s|%d" % (C.LORA_VER, code, outfit, emo, salt)
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return int(h[:8], 16) % 2147483647


def build_prompt(code, outfit, emo, lora_weight=None, use_lora=None, extra=""):
    """QUALITY -> STYLE -> LoRA/트리거 -> 본문 -> BREAK -> 조명"""
    d = CHARS[code]
    if use_lora is None:
        use_lora = lora_ready(code)
    w = C.LORA_WEIGHT if lora_weight is None else lora_weight
    head = "%s, %s" % (C.QUALITY_HEAD, C.STYLE_BA)
    if use_lora:
        head += ", <lora:bs_%s_%s:%s>, %s" % (code, C.LORA_VER, w, d["trigger"])
    else:
        head += ", " + d["trigger"]
    body = "%s, %s, %s, %s, %s, summer atmosphere" % (
        d["anchor"], d["outfits"][outfit], EMO[emo], FRAMING[outfit], d["scenes"][outfit])
    if extra:
        body += ", " + extra
    return "%s, %s, BREAK, %s" % (head, body, C.TAIL)


def all_codes(code=None):
    return [(o, e) for o in OUTFIT_ORDER for e in EMO_ORDER]

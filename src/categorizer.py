"""
categorizer.py  ·  v4
──────────────────────
Keyword-правила (EN + ES + IT + OCR + Бренды) + Zero-shot NLP fallback.
"""

from __future__ import annotations
import re, json
from typing import Optional
from functools import lru_cache
from config import CATEGORIES, LLM_MODEL, PARSED_DIR

KEYWORD_MAP: dict[str, list[str]] = {

    "fruits": [
        r"apple", r"orange", r"banana", r"grape", r"berr(y|ies)",
        r"strawberr", r"blueberr", r"raspberr", r"mango", r"pineapple",
        r"watermelon", r"melon", r"peach", r"pear\b", r"plum\b", r"cherry",
        r"lemon", r"lime\b", r"kiwi", r"avocado", r"apricot", r"coconut",
        r"guava", r"papaya", r"tamarind",
        r"naranja", r"manzana", r"pl[aá]tano", r"fresa", r"aguacate",
        r"pi[ñn]a", r"coco\b", r"lim[oó]n", r"uva\b",
        r"macedonia\b", r"fragola", r"ciliegia", r"pesca\b", r"arancia",
    ],

    "vegetables": [
        r"lettuce", r"salad\b", r"tomato", r"potato", r"onion", r"carrot",
        r"broccoli", r"spinach", r"cabbage", r"cucumber", r"pepper",
        r"celery", r"mushroom", r"corn\b", r"pea\b", r"bean\b", r"beans\b",
        r"zucchini", r"asparagus", r"kale", r"radish", r"beet\b", r"yam\b",
        r"collard", r"yams?\b", r"coll\s*grn",  # OCR "COLL GRN" = collard green
        r"ensalada", r"tomate", r"cebolla", r"zanahoria", r"tostones?",
        r"yuca\b",
        r"insalata\b", r"pomodor", r"spinaci", r"carciofo",
        r"brussels?\s*sprouts?",
        r"brussel\s*s\s*sprout"
    ],

    "dairy": [
        r"milk\b", r"cream\b", r"butter\b", r"yogurt", r"yoghurt",
        r"kefir", r"sour\s+cream", r"ice\s+cream", r"whey\b", r"cheddar",
        r"mozzarella", r"parmesan", r"brie\b", r"cottage",
        r"leche\b", r"mantequilla",
        r"burrata", r"ricotta", r"bufala\b", r"parmigian",
        # "queso" убрано из dairy → в restaurant_food
    ],

    "meat": [
        r"chicken", r"beef", r"pork", r"lamb\b", r"turkey", r"veal",
        r"steak", r"sirloin", r"ribeye", r"filet", r"fillet",
        r"burger", r"hamburger", r"cheeseburger",
        r"sausage", r"hot\s*dog", r"bacon",
        r"ham\b", r"meatball", r"wing\b", r"wings\b", r"wing\s+meal",
        r"drumstick", r"breast\b", r"rib\b", r"ribs\b", r"pulled\s+pork",
        r"ground\s+(beef|meat)", r"chop\b", r"tenderloin", r"parmesan",
        r"chicharr[oó]n", r"chkn\b",
        r"carne\b", r"pollo\b", r"cerdo\b", r"lechon",
        r"bistec", r"albondigas", r"chorizo", r"pernil",
        r"maiale", r"vitello", r"manzo", r"prosciutto", r"pancetta",
        r"cotoletta", r"ossobuco",
        r"tikka", r"murgh", r"palak\b",
        r"hb\b",     # HB = Hamburger (Big Jo's abbreviation)
        r"\bcb\b",   # CB = CheeseB urger
        r"tenders?\b",
        r"duckling\b",
        r"duck\b",
        r"canard\b",
        r"pechuga",
        r"poule\b",
        r"confit\b"
        r"chicken\s+lollipop",
        r"lollipop\s+chicken",
        r"short\s+rib",
        r"pot\s+roast"
    ],

    "fish": [
        r"fish\b", r"salmon\b", r"tuna\b", r"shrimp", r"prawn",
        r"lobster", r"crab\b", r"clam\b", r"oyster", r"scallop",
        r"tilapia", r"cod\b", r"halibut", r"sea\s*food", r"sushi",
        r"calamari", r"squid", r"anchov",
        r"pargo", r"chillo", r"mero\b", r"mariscos",
        r"camar[oó]n", r"langosta", r"pulpo\b",
        r"plancha\b",       # "salmon a la plancha"
        r"frito\b",         # "pargo frito"
        r"branzino", r"spigola", r"orata\b", r"tonno\b", r"salmone",
        r"gamberi", r"scampi\b", r"baccal[aà]",
        r"tartare?\b",
        r"negombo",
        r"mahi\b",          # Mahi-Mahi
        r"taco\s+(fish|baja)",  # fish taco
        r"baja\s+california\s+shrimp",
        r"cocktail\s+shrimp|shrimp\s+cocktail",
        r"escargot",
        r"bourguign\w*"
    ],

    "bakery": [
        r"bread\b", r"roll\b", r"bun\b", r"bagel", r"muffin", r"croissant",
        r"pastry", r"pie\b", r"biscuit", r"toast\b", r"waffle",
        r"pancake", r"donut", r"doughnut", r"scone", r"pretzel",
        r"sourdough", r"tortilla", r"pita\b", r"naan\b",
        r"empanada", r"arepa", r"tostada",
        r"focaccia", r"grissini", r"panino\b", r"cornetto",
        r"calzone\b", r"cornbread",
    ],

    "beverages": [
        r"coffee\b", r"latte\b", r"espresso", r"cappuccin", r"cappucin",
        r"americano", r"tea\b", r"iced\s+tea", r"juice\b",
        r"water\b", r"soda\b", r"cola\b", r"coke\b",
        r"pepsi", r"sprite\b", r"fanta\b", r"lemonade", r"smoothie",
        r"shake\b", r"milk\s+shake", r"hot\s+choco", r"cocoa\b",
        r"energy\s+drink", r"dr\.?\s*pepper",
        r"mountain\s+dew", r"gatorade", r"powerade",
        r"orange\s+crush", r"crsh\s*fz",
        r"perrier", r"sparkling\s+water", r"agua\s*(mineral)?",
        r"\bdrink\b", r"\bbeverage\b",
        r"jugo\b", r"limonada", r"refresco", r"batido", r"caf[eé]\b",
        r"acqua\b", r"succo\b",
        r"sierra\s+(mist|nevada\s+pale|nevada\s+tor)",  # Sierra Mist only
        # r"margarita" убран из beverages — это алкоголь
        r"cappuccin"
        r"lassi\b",
        r"birch\s+beer",
        r"\bbirch\b",
        r"lemonade\b"
    ],

    "snacks": [
        r"chip\b", r"chips\b", r"crisp\b", r"popcorn",
        r"nacho", r"cracker", r"granola\s*bar", r"protein\s*bar", r"snack",
        r"nut\b", r"nuts\b", r"peanut", r"cashew", r"almond",
        r"sunflower\s+seed", r"trail\s+mix", r"jerky",
        r"fries\b", r"truffle\s+fries", r"fri(tes|es)\b",
        r"french\s+fries", r"chill\s+fries", r"chili\s+fries",
        r"spicy\s*fr[iy]|spcy\s*fr",
        r"garlic\s+fries"
        r"garlic\s+fries"
    ],

    "sweets": [
        r"candy", r"chocolate", r"brownie", r"cookie\b", r"dessert",
        r"ice\s*cream", r"gelato", r"sorbet", r"pudding", r"jelly",
        r"gummy", r"fudge\b", r"caramel", r"toffee", r"lollipop",
        r"flan\b", r"tres\s+leches", r"churro",
        r"carrot\s+cake", r"baked\s+cookie",
        r"tiramis[uù]", r"panna\s+cotta", r"cannoli", r"cake\b",
    ],

    "household": [
        r"soap\b", r"detergent", r"cleaner", r"bleach", r"tissue",
        r"napkin", r"paper\s+towel", r"toilet\s+paper", r"trash\s+bag",
        r"garbage\s+bag", r"sponge", r"brush\b", r"mop\b", r"broom",
        r"foil\b", r"zip\s+lock", r"candle", r"lighter",
        r"battery", r"batteries", r"bulb\b",
    ],

    "personal_care": [
        r"shampoo", r"conditioner", r"toothpaste", r"toothbrush",
        r"deodorant", r"razor", r"shave\b", r"lotion", r"sunscreen",
        r"q-tip", r"tampon", r"makeup", r"lipstick", r"mascara",
        r"perfume", r"cologne", r"hairspray", r"nail\s+polish",
    ],

    "restaurant_food": [
        r"lunch\b", r"dinner\b", r"breakfast", r"meal\b", r"combo\b",
        r"plate\b", r"bowl\b", r"wrap\b", r"sandwich", r"sub\s+sandwich",
        r"taco\b", r"burrito", r"quesadilla", r"quesadi\w*",  # OCR variants
        r"enchilada", r"enchi\s*[il]\w*",                      # OCR variants
        r"taquito\w*",
        r"fajita",
        r"pizza\b",
        r"pasta\b", r"noodle", r"ramen\b", r"soup\b", r"salad\b",
        r"fried\s+rice", r"lo\s+mein", r"pad\s+thai", r"curry\b",
        r"gyro\b", r"kebab", r"falafel",
        r"veg\s*bowl", r"power\s*veg",
        r"california\s+(tropic|roll)",
        r"miso\b", r"side\b", r"mac\s*&?\s*c?h(e|z)",
        # ES
        r"arroz\b", r"frijoles", r"guacamole", r"guaca\b",
        r"queso\b",          # queso dip — выше приоритетом чем dairy теперь
        r"salsa\b", r"mole\b",
        r"ropa\s+vieja", r"picadillo",
        # IT
        r"risotto", r"gnocchi", r"lasagna|lasagne",
        r"tagliatelle", r"spaghetti", r"linguine",
        r"penne\b", r"ravioli", r"carbonara",
        r"antipasto", r"bruschetta", r"margherita\b",
        # Индийское
        r"masala\b", r"biryani", r"dal\b", r"bharta\b", r"paneer\b",
        # Прочее
        r"r&b\s+meal", r"wing\s+meal", r"3wing", r"2pc\b", r"3pc\b",
        r"grilled\s+cheese",
        r"linguine?|linguini",
        r"mac\s*&\s*chz"
        r"pho\b",
        r"buffet\b",
        r"pot\s+roast",
        r"fish\s+[&n]\s*chips|fish\s+and\s+chips",
        r"fish\s+an\s+chips"
    ],

    "alcohol": [
        r"beer\b", r"ale\b", r"lager", r"stout\b", r"ipa\b",
        r"wine\b", r"champagne", r"prosecco", r"cider\b",
        r"vodka", r"whiskey", r"whisky", r"bourbon", r"scotch",
        r"rum\b", r"gin\b", r"tequila", r"brandy", r"cognac",
        r"shot\b", r"cocktail", r"mojito", r"martini", r"margarita\b",
        r"sangria",
        r"miller\s*lite", r"bud(weiser|light)?", r"coors\b",
        r"heineken", r"corona\b", r"modelo\b", r"stella\b",
        r"dos\s+equis", r"blue\s+moon",
        r"flying\s+dog",    # Flying Dog Brewery
        r"dogfish",         # Dogfish Head
        r"sierra\s+nevada", # Sierra Nevada Brewing
        r"stone\s+ipa", r"lagunitas", r"new\s+belgium",
        r"goose\s+island", r"bells\s+brew", r"anchor\s+steam",
        r"caldera\b",       # Caldera Brewery (Oregon) — из 1058
        r"oatmeal\s+stout", r"amber\b",  # типы пива
        r"\bBTL\b",         # bottle — указывает на бутылочное пиво/вино
        r"draught\b", r"draft\b",
        # Вина
        r"sangiovese", r"chianti", r"barolo", r"brunello",
        r"pinot\s*(noir|grigio|gris)?",
        r"cabernet", r"sauvignon", r"chardonnay", r"riesling",
        r"merlot\b", r"syrah\b", r"shiraz\b", r"malbec\b",
        r"lambrusco",
        r"avion\b", r"silver\s+rx",
        # ES/IT
        r"cerveza", r"ron\b", r"vino\b", r"sangr[ií]a", r"daiquiri",
        r"honey\s+bee",     # Totem Honey Bee — craft beer
        r"numero\s+uno",    # Flying Dog Numero Uno
        r"house\s+(wine|beer|brew)",
        r"btl\s+beer|beer\s+btl"
        r"dft\b",
        r"draft\b",
        r"draught\b",
        r"shock\s*top",
        r"gu[ie]nn?e?ss",
        r"stout\b"
    ],

    "tobacco": [
        r"cigarette", r"cigar\b", r"tobacco", r"vape\b", r"e-cig",
        r"nicotine", r"marlboro", r"camel\b", r"newport", r"winston",
        r"parliament", r"lucky\s+strike",
    ],
}

_COMPILED: dict[str, re.Pattern] = {
    cat: re.compile("|".join(rf"(?:{p})" for p in patterns), re.IGNORECASE)
    for cat, patterns in KEYWORD_MAP.items()
}

_PRIORITY_ORDER = [
    "fish",   # fish ПЕРЕД alcohol (cocktail shrimp ≠ cocktail drink)
    "alcohol", "tobacco",
    "meat",   # meat ПЕРЕД sweets (Chicken Lollipop → meat, не sweets)
    "sweets",
    "beverages",
    "dairy",
    "snacks",
    "restaurant_food",
    "fruits", "vegetables",
    "bakery",
    "household", "personal_care",
]


def classify_by_keywords(name: str) -> Optional[str]:
    for cat in _PRIORITY_ORDER:
        if cat in _COMPILED and _COMPILED[cat].search(name):
            return cat
    return None


ZS_THRESHOLD = 0.40


@lru_cache(maxsize=1)
def _get_pipeline():
    from transformers import pipeline as hf_pipeline
    return hf_pipeline(
        "zero-shot-classification",
        model=LLM_MODEL, device=-1, batch_size=8,
    )


def classify_by_model(names: list[str]) -> list[tuple[str, float]]:
    if not names:
        return []
    classifier = _get_pipeline()
    labels = [c for c in CATEGORIES if c != "other"]
    results = classifier(names, candidate_labels=labels, multi_label=False)
    return [
        (res["labels"][0], round(res["scores"][0], 4))
        if res["scores"][0] >= ZS_THRESHOLD
        else ("other", round(res["scores"][0], 4))
        for res in results
    ]


def categorize_items(items: list[dict]) -> list[dict]:
    if not items:
        return []
    categorized, fallback_idx, fallback_names = [], [], []
    for idx, item in enumerate(items):
        cat = classify_by_keywords(item["name"])
        if cat:
            categorized.append({**item, "category": cat, "category_score": 1.0})
        else:
            categorized.append({**item, "category": "other", "category_score": 0.0})
            fallback_idx.append(idx)
            fallback_names.append(item["name"])
    if fallback_names:
        for idx, (cat, score) in zip(fallback_idx, classify_by_model(fallback_names)):
            categorized[idx]["category"] = cat
            categorized[idx]["category_score"] = score
    return categorized


def update_json_with_categories(json_path: str, categorized: list):
    import json as _json
    with open(json_path, encoding="utf-8") as f:
        data = _json.load(f)
    data["categorized_items"] = categorized
    with open(json_path, "w", encoding="utf-8") as f:
        _json.dump(data, f, ensure_ascii=False, indent=2)
"""Phone-number and address trivia for the "roast my contact" bonus feature.

Deterministic and entirely local: no geocoding, no network calls, and no
`hash()` — Python salts string hashing per process, so the same phone number
would roast differently every time the server restarts, which would be
confusing at a live demo and would flake any test pinning the output.
`zlib.crc32` is used instead wherever a stable pseudo-random pick is needed.
"""

import math
import zlib

_PI_DIGITS = "31415926535897932384626433832795028841971693993751"
_PHI_DIGITS = "16180339887498948482045868343656381177203091798057"

# Well-known original area codes; kept small and verifiably true rather than
# an exhaustive directory.
_AREA_CODES = {
    "212": "New York City's original area code — all five boroughs once shared it.",
    "213": "Downtown/Central LA's original code, before the 1990s splits.",
    "312": "Chicago's original area code, assigned in 1947.",
    "415": "San Francisco has held this code since the original 1947 numbering plan.",
    "202": "Washington, D.C. — one of the original 86 area codes from 1947.",
    "617": "Boston's original area code, unchanged since 1947.",
    "305": "Miami's original area code, since 1947.",
    "702": "Covered all of Nevada, including Las Vegas, until a 1998 split.",
    "512": "Austin's area code — also covered all of Central Texas until 1990.",
    "206": "Seattle's original area code, once covering the entire state.",
}


def _digits(phone: str) -> str:
    return "".join(char for char in phone if char.isdigit())


def _is_prime(n: int) -> bool:
    if n < 2:
        return False
    if n in (2, 3):
        return True
    if n % 2 == 0:
        return False
    i = 3
    while i * i <= n:
        if n % i == 0:
            return False
        i += 2
    return True


def _is_perfect_square(n: int) -> bool:
    root = math.isqrt(n)
    return root * root == n


def _longest_repdigit_run(digits: str) -> int:
    if not digits:
        return 0
    best = cur = 1
    for i in range(1, len(digits)):
        cur = cur + 1 if digits[i] == digits[i - 1] else 1
        best = max(best, cur)
    return best


def _longest_counting_run(digits: str) -> tuple[int, str]:
    """Longest run where each digit is exactly one more, or one less, than the last."""
    if not digits:
        return 0, ""
    best_len, best_start = 1, 0
    cur_len, cur_start, cur_dir = 1, 0, 0
    for i in range(1, len(digits)):
        step = int(digits[i]) - int(digits[i - 1])
        direction = 1 if step == 1 else -1 if step == -1 else 0
        if direction and direction == cur_dir:
            cur_len += 1
        elif direction:
            cur_len, cur_start, cur_dir = 2, i - 1, direction
        else:
            cur_len, cur_start, cur_dir = 1, i, 0
        if cur_len > best_len:
            best_len, best_start = cur_len, cur_start
    return best_len, digits[best_start : best_start + best_len]


def _grade(matched: int, seed: int) -> str:
    if matched >= 3:
        return "A+"
    if matched == 2:
        return "A-"
    if matched == 1:
        return "B+"
    # No special properties found in the number itself — still deterministic,
    # still a little mean, just not enthusiastic about it.
    return ("B-", "C+", "C", "C-")[seed % 4]


def phone_roast(phone: str | None) -> tuple[list[str], str]:
    """Numeric trivia about a phone number, and a deterministic letter grade.

    Always returns at least one trivia line, even for a blank or short number.
    """
    digits = _digits(phone or "")
    if len(digits) < 4:
        return ["No phone on file to roast — a blank field is its own kind of statement."], "C"

    last_four = digits[-4:]
    n = int(last_four)
    lines: list[str] = []

    if len(digits) in (10, 11):
        area = digits[-10:-7]
        region = _AREA_CODES.get(area)
        if region:
            lines.append(f"Area code {area}: {region}")

    if _is_prime(n):
        lines.append(f"Your last four digits, {last_four}, are prime — untouchable, indivisible, correct.")
    if last_four == last_four[::-1]:
        lines.append(f"{last_four} reads the same backwards. A palindrome — efficient, if uninspired.")
    if len(set(last_four)) == 1:
        lines.append(f"All four digits are {last_four[0]}. Either luck, or someone at the phone company likes you.")
    if n > 0 and _is_perfect_square(n):
        lines.append(f"{last_four} is {math.isqrt(n)}² — a perfect square hiding in your phone number.")
    if last_four in _PI_DIGITS:
        lines.append(f"{last_four} shows up in the digits of π. You're basically irrational.")
    if last_four in _PHI_DIGITS:
        lines.append(f"{last_four} appears in the golden ratio. Aesthetically pleasing, mathematically speaking.")
    if "1337" in digits:
        lines.append("Your number contains 1337. Nice.")
    if "420" in digits:
        lines.append("Your number contains 420. Also nice.")

    run_len, run = _longest_counting_run(digits)
    if run_len >= 4:
        direction = "ascending" if int(run[1]) > int(run[0]) else "descending"
        lines.append(f"Digits {run} form an {direction} run of {run_len} — suspiciously tidy for a phone number.")

    rep_len = _longest_repdigit_run(digits)
    if rep_len >= 3:
        lines.append(f"Your number has a run of {rep_len} identical digits in a row. Bold choice.")

    matched = len(lines)
    if not lines:
        lines.append(
            f"Nothing remarkable jumped out — but your digits sum to {sum(int(d) for d in digits)}, for what it's worth."
        )

    return lines, _grade(matched, zlib.crc32(digits.encode()))


# ~40 real, verifiable facts. Exact (city, state) match wins; falls back to
# city-only, then state, then country, then a generic line — every address
# gets a response.
_CITY_FACTS = {
    ("fullerton", "ca"): "Leo Fender started Fender Musical Instruments here in 1946 — the electric guitar as we know it began in Fullerton.",
    ("cupertino", "ca"): "Apple's headquarters — the spaceship you've seen in every keynote is right here.",
    ("mountain view", "ca"): "Google's home turf since 1999.",
    ("menlo park", "ca"): "Meta's headquarters — though the OTHER Menlo Park, in New Jersey, is where Edison actually invented things.",
    ("palo alto", "ca"): "Hewlett-Packard started in a garage here in 1939 — the original Silicon Valley garage.",
    ("los gatos", "ca"): "Netflix was founded here in 1997, originally mailing DVDs.",
    ("santa clara", "ca"): "Both Intel and Nvidia call this city home.",
    ("san jose", "ca"): "The unofficial capital of Silicon Valley — and briefly California's actual capital, 1850-1851.",
    ("sunnyvale", "ca"): "Yahoo's longtime headquarters.",
    ("san francisco", "ca"): "Cable cars, fog, and more tech unicorns per square mile than almost anywhere else.",
    ("seattle", "wa"): "Starbucks poured its first cup at Pike Place Market in 1971.",
    ("redmond", "wa"): "Microsoft's headquarters since 1986.",
    ("bellevue", "wa"): "T-Mobile USA is headquartered here.",
    ("issaquah", "wa"): "Costco's headquarters, and origin of the bulk-size everything.",
    ("beaverton", "or"): "Nike's world headquarters.",
    ("austin", "tx"): "Michael Dell started what became Dell Technologies from his UT Austin dorm room in 1984.",
    ("round rock", "tx"): "Dell's actual corporate headquarters today.",
    ("armonk", "ny"): "IBM's headquarters since 1964.",
    ("new york", "ny"): "More Fortune 500 headquarters than any other US city.",
    ("cambridge", "ma"): "Home to both MIT and Harvard, a few blocks apart.",
    ("boston", "ma"): "One of the oldest cities in the US, founded in 1630.",
    ("chicago", "il"): "McDonald's has been headquartered here since 2018.",
    ("deerfield", "il"): "Walgreens' corporate headquarters.",
    ("detroit", "mi"): "Motown Records started here in 1959, on an $800 loan.",
    ("minneapolis", "mn"): "Target's headquarters, and namesake of the Twin Cities.",
    ("bloomington", "mn"): "Home to the Mall of America — one of the largest shopping malls in the US.",
    ("bentonville", "ar"): "Walmart's headquarters, in the town where Sam Walton opened his first store.",
    ("omaha", "ne"): "Warren Buffett has run Berkshire Hathaway from here for decades.",
    ("atlanta", "ga"): "Coca-Cola has been headquartered here since 1892.",
    ("nashville", "tn"): "Music City — the heart of the country music industry.",
    ("memphis", "tn"): "Elvis Presley's Graceland, and FedEx's global headquarters.",
    ("louisville", "ky"): "Louisville Slugger has made baseball bats here since 1884.",
    ("cincinnati", "oh"): "Procter & Gamble's headquarters since 1837.",
    ("pittsburgh", "pa"): "Once the steel capital of the world; Mr. Rogers' Neighborhood was filmed here.",
    ("milwaukee", "wi"): "Harley-Davidson has built motorcycles here since 1903.",
    ("denver", "co"): "The Mile High City — its capitol steps mark exactly 5,280 feet above sea level.",
    ("boulder", "co"): "Celestial Seasonings has been blending tea here since 1969.",
    ("provo", "ut"): "Home to Brigham Young University and a fast-growing tech corridor nicknamed 'Silicon Slopes.'",
    ("las vegas", "nv"): "Zappos moved its headquarters downtown in 2013, chasing Tony Hsieh's vision for the city.",
    ("miami", "fl"): "Its Art Deco Historic District has one of the largest collections of Art Deco buildings in the world.",
    ("orlando", "fl"): "Walt Disney World opened here in 1971, on land quietly bought up under shell companies.",
}

_STATE_FACTS = {
    "ca": "California alone would be among the world's five largest economies if it were its own country.",
    "tx": "Texas spent nine years, 1836-1845, as its own internationally recognized independent republic.",
    "ny": "The Erie Canal, completed in 1825, is a big part of why New York became the country's commercial capital.",
    "wa": "Washington grows roughly 70% of the country's apples.",
    "il": "Illinois' Sears (now Willis) Tower was the tallest building in the Western Hemisphere for nearly 40 years.",
    "ma": "Massachusetts has one of the highest concentrations of colleges and universities per capita in the country.",
    "fl": "Florida has the longest coastline in the contiguous US outside of Alaska.",
    "co": "Colorado has the highest average elevation of any US state.",
    "or": "Oregon is one of only five US states with no general sales tax.",
    "nv": "Nevada is the driest state in the country.",
}

_COUNTRY_FACTS = {
    "usa": "Home to more Fortune 500 headquarters than any other country.",
    "united states": "Home to more Fortune 500 headquarters than any other country.",
}


def address_trivia(city: str | None, state: str | None, country: str | None) -> str:
    """One line of trivia for an address, from the most to least specific match."""
    key_city = (city or "").strip().lower()
    key_state = (state or "").strip().lower()

    exact = _CITY_FACTS.get((key_city, key_state))
    if exact:
        return exact
    for (fact_city, _), fact in _CITY_FACTS.items():
        if key_city and fact_city == key_city:
            return fact
    if key_state in _STATE_FACTS:
        return _STATE_FACTS[key_state]

    key_country = (country or "").strip().lower()
    if key_country in _COUNTRY_FACTS:
        return _COUNTRY_FACTS[key_country]

    if city or state or country:
        return "No trivia on file for that one — but it's now immortalized in a QR code, so there's that."
    return "No address on file. Mysterious. We respect it."

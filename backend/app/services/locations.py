import re

BUILDINGS = {
    "Woodward Hall": ("woodward",),
    "Atkins Library": ("atkins", "library", "atkins library (simulated)"),
    "Friday Building": ("Friday",),
    "Science Building": ("Science Hall",),
    "Fretwell Building": ("Fretwell",),
    "EPIC Building": ("EPIC",),
    "Burson Building": ("Burson",),
    "Student Union": ("campus center",),
    "College of Computing and Informatics building": ("college of computing", "cci"),
}


def location_parts(value):
    clean = " ".join((value or "").strip().split())
    clean = re.sub(r" \(Simulated\)$", "", clean, flags=re.I)
    for name, aliases in BUILDINGS.items():
        for alias in sorted((name, *aliases), key=len, reverse=True):
            if clean.casefold() == alias.casefold():
                return name, ""
            if clean.casefold().startswith(alias.casefold()):
                rest = clean[len(alias):]
                if re.fullmatch(r"(?:\s*[,#–-]\s*.+|\s+(?:room\b.*|lab\b.*|\d\w*))", rest, re.I):
                    return name, re.sub(r"^(?:room\s+)?", "", rest.strip(" ,#–-").casefold())
    building, _, room = clean.partition(",")
    return building.strip(), re.sub(r"^room\s+", "", room.strip().casefold())


def same_building(value, building):
    return bool(building) and location_parts(value)[0].casefold() == location_parts(building)[0].casefold()


def test_endpoint(building):
    return bool(re.search(r"\b(?:demo|test)\b", building, re.I))

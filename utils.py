from config import EUR_TO_INR
import re

CITY_TO_IATA = {
    "Kodaikanal": "MAA",
    "Kullu": "KUU",
    "Kumarakom": "COK",
    "Kuta": "DPS",
    "Manali": "KUU",
    "Meghalaya": "SHL",
    "Munnar": "COK",
    "Mysore": "MYQ",
    "Neil Island": "IXZ",
    "Ooty": "CJB",
    "Pahalgam": "SXR",
    "Port Blair": "IXZ",
    "Seminyak": "DPS",
    "Shillong": "SHL",
    "Shimla": "SLV",
    "Sikkim": "PYG",
    "Siliguri": "IXB",
    "Srinagar": "SXR",
    "Ubud": "DPS",
    "Varkala": "TRV",
    "Agra": "AGR",
    "Alleppey": "COK",
    "Andaman": "IXZ",
    "Bali": "DPS",
    "Chandigarh": "IXC",
    "Cherrapunjee": "SHL",
    "Coimbatore": "CJB",
    "Coonoor": "CJB",
    "Coorg": "IXM",
    "Darjeeling": "IXB",
    "Delhi": "DEL",
    "Dwaki": "SHL",
    "Gangtok": "PYG",
    "Goa": "GOX",
    "Havelock": "IXZ",
    "Himachal": "KUU",
    "Kashmir": "SXR",
    "Kasol": "KUU",
    "Kaziranga": "JRH",
    "Kochi": "COK",
    "Wayanad": "CCJ",
    "Kerala": "COK",
    "Bangkok": "BKK",
    "Singapore": "SIN"
}

def eur_to_inr(eur_str):
    try:
        eur = float(eur_str)
        inr = eur * EUR_TO_INR
        return f"{inr:.2f} INR ({{eur:.2f}} EUR)"
    except Exception:
        return f"- INR (- EUR)"

def city_to_iata(city_name: str) -> str:
    return CITY_TO_IATA.get(city_name.strip().title(), "")

def extract_city_from_package_name(package_name: str, package: dict = {}):
    for city in CITY_TO_IATA.keys():
        if city.lower() in package_name.lower():
            return city
    dest_names = package.get("destinationName", "")
    for city in CITY_TO_IATA.keys():
        if city.lower() in dest_names.lower():
            return city
    match = re.search(r'in ([A-Za-z ]+)', package_name)
    if match:
        return match.group(1).strip()
    return "" 
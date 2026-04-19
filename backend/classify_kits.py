import csv
import os
import sqlite3
from collections import Counter


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "ilm1300.db")
REPORT_PATH = os.path.join(BASE_DIR, "..", "export_text", "research", "kit_category_audit.csv")


def ensure_column(conn, table_name, column_name, ddl):
    columns = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    if not any(col[1] == column_name for col in columns):
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}")


def has_any(text, *terms):
    return any(term in text for term in terms)


def classify_kit(name, scale, brand=""):
    n = (name or "").lower()
    s = (scale or "").lower()
    b = (brand or "").lower()

    # Broadly aligned with common Scalemates-style subject families:
    # aircraft, AFV / military ground, cars, trucks / trailers, ships, spacecraft.
    if has_any(n, "apollo", "gemini", "mercury", "vostok", "lunar", "saturn v",
               "spacecraft", "moon ship", "moon rocket", "nasa", "v-2 rocket", "rocket"):
        if has_any(n, "saturn", "v-2", "rocket"):
            return "space", "rocket"
        return "space", "spacecraft"

    if has_any(n, "u-boat", "submarine"):
        return "naval", "submarine"
    if has_any(n, "battleship", "battle ship", "aircraft carrier", "carrier ", "carrier)",
               "destroyer", "cruiser", "yamato", "missouri", "bismarck", "tirpitz", "iowa",
               "essex", "akagi", "haruna", "kongo", "kirishima", "hiei", "north carolina",
               "washington, u.s.navy", "u.s.s.", "h.m.s.", "ijn ", "galeass",
               "patrol gunboat", "battle of midway"):
        if "carrier" in n:
            return "naval", "carrier"
        if has_any(n, "battleship", "battle ship"):
            return "naval", "battleship"
        if "destroyer" in n:
            return "naval", "destroyer"
        if "patrol gunboat" in n:
            return "naval", "small_craft"
        return "naval", "warship"
    if "sealab" in n:
        return "naval", "undersea"

    if "bridge" in n:
        return "industrial", "structure"
    if has_any(n, "railway gun", "railway carrier", "anzio annie", "leopold"):
        return "military_ground", "rail_artillery"
    if has_any(n, "howitzer", "field piece", "m2 gun"):
        return "military_ground", "artillery"
    if has_any(n, "tanker semi", "tanker trailer"):
        return "commercial_vehicle", "trailer"
    if has_any(n, "army military tractor", "tank transporter", "tank transport",
               "scammell tank transporter", "scammel tank transporter",
               "ordnance diamond", "cargo truck"):
        return "military_ground", "support_vehicle"
    if has_any(n, "tank", "panzer", "jagd", "hetzer", "sherman", "matilda", "chieftain",
               "stalin", "m36 jackson", "m8e2", "sdkfz", "sd.kfz", "flakpanzer", "stuart",
               "patton", "churchill", "tiger", "leopard", "elephant", "kampfwagen",
               "armored car", "armoured car", "armored vehicle", "armoured vehicle",
               "assault gun", "hummel", "self-propelled", "mortar carrier", "m60", "centurion"):
        return "military_ground", "afv"
    if has_any(n, "half-track", "hanomag", "kettenkrad"):
        return "military_ground", "support_vehicle"
    if "bmw r75 with sidecar" in n:
        return "military_ground", "motorcycle"

    if has_any(n, "helicopter", "hueycobra", "huey"):
        return "aircraft", "helicopter"
    if has_any(n, "boeing 727", "dc-9", "trident", "clipper", "dc-7", "whisperjet"):
        return "aircraft", "civil_aircraft"
    if has_any(n, "xb-70", "fokker", "se-5", "p-40", "p-51", "spitfire", "harrier",
               "hurricane", "messerschmitt", "bf109", "shiden", "hawker", "harrow",
               "b-52", "beaufighter", "ju 88",
               "mitchell bomber", "torpedo-bomber", "bomber", "fighter", "intruder",
               "whitley", "kate", "dive-bomber", "stratofortress", "scout", "interceptor"):
        return "aircraft", "military_aircraft"
    if s == "1/144" and has_any(n, "boeing", "dc-", "trident", "clipper"):
        return "aircraft", "civil_aircraft"

    if has_any(n, "trailer", "reefer", "moving van", "flatbed", "tanker semi"):
        return "commercial_vehicle", "trailer"
    if has_any(n, "tractor", "truck tractor", "freightliner", "peterbilt", "kenworth",
               "reo", "semi truck", "cabover", "delivery", "stake truck", "dump truck",
               "log hauler", "post van", "ladder truck", "city delivery", "truck", "van"):
        return "commercial_vehicle", "truck"

    if has_any(n, "honda super hawk", "cb750", "motocrosser"):
        return "automotive", "motorcycle"
    if has_any(n, "lotus", "mclaren", "ferrari 312", "tyrrell", "brabham", "matra",
               "porsche 910", "porsche carrera", "corvette ss hatchback", "funny car",
               "dragray", "bobby allison", "racing type", "ford f-1", "j.p.s.", "honda f-1") or (
        "f-1" in n and "ford" in n
    ):
        return "automotive", "race_car"
    if has_any(n, "pickup", "coupe", "phaeton", "sedan", "nomad", "hardtop", "el camino",
               "corvette", "gremlin", "galaxie", "camaro", "mustang", "impala", "victoria",
               "bel air", "roadster", "bentley"):
        return "automotive", "car"

    if has_any(n, "wankel rotary engine", "microchip", "lamp shade", "brick", "koolshade", "engine") or b == "aavid":
        return "industrial", "component"

    # Fallbacks by scale for older ambiguous entries.
    if s in {"1/700", "1/600", "1/500", "1/450", "1/400", "1/568", "1/547", "1/542", "1/1200"}:
        return "naval", "warship"
    if s in {"1/72", "1/48", "1/32", "1/27", "1/19", "1/105", "1/100"}:
        return "aircraft", "military_aircraft"
    if s in {"1/35", "1/76", "1/30", "1/15", "1/21"}:
        return "military_ground", "afv"
    if s in {"1/25", "1/24", "1/43", "1/18"}:
        return "automotive", "car"

    return "other", "unclassified"


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    ensure_column(conn, "kits", "category_family", "TEXT")
    ensure_column(conn, "kits", "category_subject", "TEXT")
    rows = conn.execute(
        "SELECT id, brand, name, scale, serial_number, scalemates_url FROM kits ORDER BY brand, name"
    ).fetchall()

    summary = Counter()
    report_rows = []

    for row in rows:
        family, subject = classify_kit(row["name"], row["scale"], row["brand"])
        conn.execute(
            "UPDATE kits SET category_family=?, category_subject=? WHERE id=?",
            (family, subject, row["id"]),
        )
        summary[(family, subject)] += 1
        report_rows.append({
            "id": row["id"],
            "brand": row["brand"],
            "name": row["name"],
            "scale": row["scale"] or "",
            "serial_number": row["serial_number"] or "",
            "category_family": family,
            "category_subject": subject,
            "scalemates_url": row["scalemates_url"] or "",
        })

    conn.commit()
    conn.close()

    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "id",
                "brand",
                "name",
                "scale",
                "serial_number",
                "category_family",
                "category_subject",
                "scalemates_url",
            ],
        )
        writer.writeheader()
        writer.writerows(report_rows)

    print(f"Updated {len(report_rows)} kits")
    for (family, subject), count in sorted(summary.items(), key=lambda item: (-item[1], item[0])):
        print(f"{family:20} {subject:20} {count}")
    print(f"Report: {os.path.normpath(REPORT_PATH)}")


if __name__ == "__main__":
    main()

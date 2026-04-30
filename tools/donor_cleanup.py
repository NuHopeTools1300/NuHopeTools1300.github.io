"""
Audit and clean the donor-kit backbone against ANH donors.xlsx.

Source-of-truth rule for this cleanup pass:
  - ANH donors.xlsx / SWANH donors is canonical for ANH donor kit identity.
  - ANH donors.xlsx / Discarded is not canonical; hits are reported/reviewed.

The script intentionally avoids third-party dependencies so it can run in the
current lightweight repo environment.

Usage:
  python tools/donor_cleanup.py --audit
  python tools/donor_cleanup.py --apply-clear
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sqlite3
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "backend" / "data" / "ilm1300.db"
ANH_PATH = ROOT / "ANH donors.xlsx"
PARTLIST_PATH = ROOT / "PartList_private.xlsx"

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
NS = {"main": MAIN_NS}


SAFE_URL_FIXES = [
    {
        "kit_id": 222,
        "hint": "AMT|Fruehauf 40ft. Reefer",
        "scalemates_url": "https://www.scalemates.com/de/kits/amt-t507-40ft-reefer--178230",
        "reason": "User-provided correct Scalemates URL; previous URL belonged to AMT T-531 Tanker.",
    },
]


SAFE_MERGES = [
    {
        "source_id": 14,
        "target_id": 197,
        "source_hint": "Airfix|ILYUSHIN",
        "target_hint": "Airfix|ILYUSHIN",
        "reason": "Same Scalemates URL and normalized kit name; target matches ANH donors identity.",
    },
    {
        "source_id": 15,
        "target_id": 199,
        "source_hint": "Airfix|Lockheed Hudson",
        "target_hint": "Airfix|Lockheed Hudson",
        "reason": "Same Scalemates URL and normalized kit name; target matches ANH donors identity.",
    },
    {
        "source_id": 3,
        "target_id": 173,
        "source_hint": "Airfix|Harrier",
        "target_hint": "Airfix|Hawker Harrier",
        "reason": "Same Scalemates URL; target matches ANH donors identity.",
    },
    {
        "source_id": 10,
        "target_id": 174,
        "source_hint": "Airfix|Bismarck",
        "target_hint": "Airfix|Bismarck",
        "reason": "Same Scalemates URL; target matches ANH donors identity.",
    },
    {
        "source_id": 11,
        "target_id": 186,
        "source_hint": "Airfix|O/400",
        "target_hint": "Airfix|O/400",
        "reason": "Same Scalemates URL; target matches ANH donors identity.",
    },
    {
        "source_id": 12,
        "target_id": 189,
        "source_hint": "Airfix|Pontoon Bridge",
        "target_hint": "Airfix|Pontoon Bridge Assault Set",
        "reason": "Same donor identity; target matches ANH donors row 35.",
    },
    {
        "source_id": 16,
        "target_id": 190,
        "source_hint": "Airfix|Wellington",
        "target_hint": "Airfix|Wellington",
        "reason": "Same Scalemates URL; target matches ANH donors identity.",
    },
    {
        "source_id": 17,
        "target_id": 184,
        "source_hint": "Airfix|Hampton",
        "target_hint": "Airfix|Hampden",
        "reason": "Same Scalemates URL and likely typo normalization; target matches ANH donors identity.",
    },
    {
        "source_id": 19,
        "target_id": 192,
        "source_hint": "Airfix|Scammell",
        "target_hint": "Airfix|Scammel",
        "reason": "Same donor identity and serial; target matches ANH donors row 39 spelling/URL.",
    },
    {
        "source_id": 20,
        "target_id": 202,
        "source_hint": "Airfix|Panzer IV",
        "target_hint": "Airfix|Panzer IV",
        "reason": "Same Scalemates URL; target matches ANH donors identity.",
    },
    {
        "source_id": 21,
        "target_id": 183,
        "source_hint": "Airfix|Halifax",
        "target_hint": "Airfix|Halifax",
        "reason": "Same donor identity; target matches ANH donors row 28.",
    },
    {
        "source_id": 23,
        "target_id": 180,
        "source_hint": "Airfix|Black Widow",
        "target_hint": "Airfix|Black Widow",
        "reason": "Same donor identity and serial; target matches ANH donors row 24.",
    },
    {
        "source_id": 24,
        "target_id": 193,
        "source_hint": "Airfix|B-24 Liberator",
        "target_hint": "Airfix|B-24 Liberator",
        "reason": "Same Scalemates URL and normalized kit name; target matches ANH donors identity.",
    },
    {
        "source_id": 26,
        "target_id": 201,
        "source_hint": "Airfix|Buffalo & Jeep",
        "target_hint": "Airfix|Buffalo & Jeep",
        "reason": "Same Scalemates URL and normalized kit name; target matches ANH donors identity.",
    },
    {
        "source_id": 31,
        "target_id": 226,
        "source_hint": "AMT|Kenworth",
        "target_hint": "AMT|Kenworth",
        "reason": "Same Scalemates URL and same W-925 Watkins identity; target matches ANH donors identity.",
    },
    {
        "source_id": 34,
        "target_id": 281,
        "source_hint": "Payhauler 350",
        "target_hint": "Payhauler 350",
        "reason": "Same donor identity; target matches ANH donors row 158.",
    },
    {
        "source_id": 68,
        "target_id": 277,
        "source_hint": "Entex Industries|Wankel Rotary Engine",
        "target_hint": "Entex|Wankel Rotary Engine",
        "reason": "Same Scalemates URL/name/serial; ANH donors row uses Entex identity.",
    },
    {
        "source_id": 44,
        "target_id": 279,
        "source_hint": "Sturmgeschutz IV",
        "target_hint": "Sturmgeschutz IV",
        "reason": "Same Scalemates URL and normalized kit name; target matches ANH donors identity.",
    },
    {
        "source_id": 45,
        "target_id": 269,
        "source_hint": "German Tank",
        "target_hint": "German Tank",
        "reason": "Same Scalemates URL; target matches ANH donors identity.",
    },
    {
        "source_id": 49,
        "target_id": 270,
        "source_hint": "M60",
        "target_hint": "M60",
        "reason": "Same Scalemates URL; target matches ANH donors identity.",
    },
    {
        "source_id": 64,
        "target_id": 272,
        "source_hint": "75mm German Anti Tank Gun",
        "target_hint": "75mm German Anti Tank Gun",
        "reason": "Same Scalemates URL and normalized kit name; target matches ANH donors identity.",
    },
    {
        "source_id": 71,
        "target_id": 282,
        "source_hint": "German Half-Track Hanomag",
        "target_hint": "German Half-Track Hanomag",
        "reason": "Same Scalemates URL and normalized kit name; target matches ANH donors identity.",
    },
    {
        "source_id": 72,
        "target_id": 285,
        "source_hint": "Westland Wyvern",
        "target_hint": "Westland Wyvern",
        "reason": "Same Scalemates URL and normalized kit name; target matches ANH donors identity.",
    },
    {
        "source_id": 73,
        "target_id": 287,
        "source_hint": "Bristol Beaufighter",
        "target_hint": "Bristol Beaufighter",
        "reason": "Same Scalemates URL and normalized kit name; target matches ANH donors identity.",
    },
    {
        "source_id": 86,
        "target_id": 298,
        "source_hint": "Sherman",
        "target_hint": "Sherman",
        "reason": "Same Scalemates URL and normalized kit name; target matches ANH donors identity.",
    },
    {
        "source_id": 85,
        "target_id": 292,
        "source_hint": "Yamato",
        "target_hint": "Yamato",
        "reason": "Same Scalemates URL; target matches ANH donors identity.",
    },
    {
        "source_id": 89,
        "target_id": 295,
        "source_hint": "Anzio Annie",
        "target_hint": "Anzio Annie",
        "reason": "Same Scalemates URL; target matches ANH donors identity.",
    },
    {
        "source_id": 93,
        "target_id": 304,
        "source_hint": "M40-75/18",
        "target_hint": "M40-75/18",
        "reason": "Same Scalemates URL; target matches ANH donors identity.",
    },
    {
        "source_id": 94,
        "target_id": 305,
        "source_hint": "Tiger",
        "target_hint": "Tiger",
        "reason": "Same Scalemates URL and normalized kit name; target matches ANH donors identity.",
    },
    {
        "source_id": 98,
        "target_id": 309,
        "source_hint": "Panzerkampfwagen IV",
        "target_hint": "Panzerkampfwagen IV",
        "reason": "Same Scalemates URL; target matches ANH donors identity.",
    },
    {
        "source_id": 100,
        "target_id": 313,
        "source_hint": "Mack Bulldog",
        "target_hint": "Mack Bulldog",
        "reason": "Same Scalemates URL; target matches ANH donors identity.",
    },
    {
        "source_id": 104,
        "target_id": 318,
        "source_hint": "Elefant",
        "target_hint": "Elefant",
        "reason": "Same Scalemates URL; target matches ANH donors identity.",
    },
    {
        "source_id": 105,
        "target_id": 317,
        "source_hint": "Centurion",
        "target_hint": "Centurion",
        "reason": "Same Scalemates URL; target matches ANH donors identity.",
    },
    {
        "source_id": 109,
        "target_id": 324,
        "source_hint": "Nagato",
        "target_hint": "Nagato",
        "reason": "Same Scalemates URL; target matches ANH donors identity.",
    },
    {
        "source_id": 110,
        "target_id": 332,
        "source_hint": "Yamato",
        "target_hint": "Yamato",
        "reason": "Same Scalemates URL; target matches ANH donors identity.",
    },
    {
        "source_id": 112,
        "target_id": 335,
        "source_hint": "Jagdpanther",
        "target_hint": "Jagdpanther",
        "reason": "Same Scalemates URL and normalized kit name; target matches ANH donors identity.",
    },
    {
        "source_id": 115,
        "target_id": 308,
        "source_hint": "Howitzer",
        "target_hint": "Howitzer",
        "reason": "Same Scalemates URL; target matches ANH donors identity.",
    },
    {
        "source_id": 117,
        "target_id": 340,
        "source_hint": "Defiance",
        "target_hint": "Defiance",
        "reason": "Same Scalemates URL; target matches ANH donors identity.",
    },
    {
        "source_id": 119,
        "target_id": 344,
        "source_hint": "Phantom",
        "target_hint": "Phantom",
        "reason": "Same Scalemates URL; target matches ANH donors identity.",
    },
    {
        "source_id": 120,
        "target_id": 348,
        "source_hint": "Junkers Ju 88",
        "target_hint": "Junkers Ju 88",
        "reason": "Same Scalemates URL; target matches ANH donors identity.",
    },
    {
        "source_id": 102,
        "target_id": 319,
        "source_hint": "Nichimo|Jagdtiger",
        "target_hint": 'Nichimo|Jagdpanzer VI "Jagdtiger"',
        "reason": "Source kit is in Discarded; canonical ANH donors row uses target identity.",
    },
    {
        "source_id": 124,
        "target_id": 353,
        "source_hint": "Tamiya|John Player Special",
        "target_hint": "Tamiya|J.P.S. Lotus 72D",
        "reason": "Same Scalemates URL; target matches ANH donors identity.",
    },
    {
        "source_id": 125,
        "target_id": 356,
        "source_hint": "Tamiya|McLaren M23",
        "target_hint": "Tamiya|McLaren M23",
        "reason": "Same Scalemates URL; target matches ANH donors identity.",
    },
    {
        "source_id": 126,
        "target_id": 351,
        "source_hint": "Tamiya|Ferrari 312",
        "target_hint": "Tamiya|Ferrari 312B",
        "reason": "Same Scalemates URL; target matches ANH donors identity.",
    },
    {
        "source_id": 127,
        "target_id": 357,
        "source_hint": "Tamiya|Tyrrell Ford",
        "target_hint": "Tamiya|Tyrrell Ford",
        "reason": "Same Scalemates URL; target matches ANH donors identity.",
    },
    {
        "source_id": 128,
        "target_id": 352,
        "source_hint": "Tamiya|Honda F-1",
        "target_hint": "Tamiya|Honda F-1",
        "reason": "Same Scalemates URL; target matches ANH donors identity.",
    },
    {
        "source_id": 150,
        "target_id": 366,
        "source_hint": "Tamiya|M36 Jackson",
        "target_hint": "Tamiya|M36 Jackson",
        "reason": "Same kit identity after punctuation normalization; target has ANH placements.",
    },
    {
        "source_id": 151,
        "target_id": 378,
        "source_hint": "Tamiya|M41",
        "target_hint": "Tamiya-MRC|M41",
        "reason": "Same Scalemates URL; target matches ANH donors identity.",
    },
    {
        "source_id": 154,
        "target_id": 365,
        "source_hint": "Tamiya|M577",
        "target_hint": "Tamiya|M577",
        "reason": "Same kit identity after punctuation normalization; target has ANH placements.",
    },
    {
        "source_id": 164,
        "target_id": 373,
        "source_hint": "Tamiya|Shinano",
        "target_hint": "Tamiya|Shinano",
        "reason": "Same Scalemates URL; target matches ANH donors identity.",
    },
    {
        "source_id": 166,
        "target_id": 375,
        "source_hint": "Tamiya|Yamato",
        "target_hint": "Tamiya|Yamato",
        "reason": "Same Scalemates URL; target matches ANH donors identity.",
    },
    {
        "source_id": 39,
        "target_id": 265,
        "source_hint": "Aurora|M4A3E8 Sherman",
        "target_hint": "Aurora|World War II Sherman Tank",
        "reason": "User-confirmed equivalence; target matches ANH donors identity.",
    },
    {
        "source_id": 40,
        "target_id": 262,
        "source_hint": "Aurora|CHURCHILL TANK",
        "target_hint": "Aurora|British Churchill Tank",
        "reason": "User-confirmed equivalence; target matches ANH donors identity.",
    },
    {
        "source_id": 61,
        "target_id": 276,
        "source_hint": "Bandai|Jagd-Panther",
        "target_hint": "Bandai|Tank Destroyer Jagd-Panther",
        "reason": "User-confirmed equivalence; target matches ANH donors identity.",
    },
    {
        "source_id": 74,
        "target_id": 284,
        "source_hint": "Frog|Blackburn Shark",
        "target_hint": "Frog|Blackburn Shark Torpedo-bomber",
        "reason": "User-confirmed equivalence; target matches ANH donors identity.",
    },
    {
        "source_id": 77,
        "target_id": 289,
        "source_hint": "Fujimi|Battleship Missouri",
        "target_hint": "Fujimi|Battleship Iowa / Missouri",
        "reason": "User-confirmed equivalence; target matches ANH donors identity.",
    },
    {
        "source_id": 80,
        "target_id": 330,
        "source_hint": "Fujimi|Panther-G German Medium Tank",
        "target_hint": "Nitto|Panther-G German Medium Tank",
        "reason": "User-confirmed equivalence; source was an unused duplicate of the canonical ANH donor identity.",
    },
    {
        "source_id": 81,
        "target_id": 328,
        "source_hint": "Fujimi|Panzer.IV Ausf.J",
        "target_hint": "Nitto|Panzer.IV Ausf.J",
        "reason": "User-confirmed equivalence; target matches ANH donors identity.",
    },
    {
        "source_id": 82,
        "target_id": 334,
        "source_hint": "Fujimi|M36 Jackson",
        "target_hint": "Nitto|M36 Jackson",
        "reason": "User-confirmed equivalence; target matches ANH donors identity.",
    },
    {
        "source_id": 84,
        "target_id": 329,
        "source_hint": "Fujimi/Nitto|M3A1 Half Track",
        "target_hint": "Nitto|M3A1 Half Track",
        "reason": "User-confirmed equivalence; target matches ANH donors identity.",
    },
    {
        "source_id": 90,
        "target_id": 294,
        "source_hint": "Hasegawa|CCKW-353 Cargo Truck",
        "target_hint": "Hasegawa|CCKW-353 Gasoline Tank Truck",
        "reason": "User-confirmed equivalence; target matches ANH donors identity.",
    },
    {
        "source_id": 103,
        "target_id": 321,
        "source_hint": "Nichimo|Tiger II",
        "target_hint": "Nichimo|Henschel Turret",
        "reason": "User-confirmed equivalence; target matches ANH donors identity.",
    },
    {
        "source_id": 106,
        "target_id": 320,
        "source_hint": "Nichimo|Sherman US Army Medium Tank M4A1",
        "target_hint": "Nichimo|M4A1 Sherman",
        "reason": "User-confirmed equivalence; target matches ANH donors identity.",
    },
    {
        "source_id": 107,
        "target_id": 326,
        "source_hint": "Nichimo|Hyuga",
        "target_hint": "Nichimo|Ise / Hyuga",
        "reason": "User-confirmed equivalence; target matches ANH donors identity.",
    },
    {
        "source_id": 108,
        "target_id": 325,
        "source_hint": "Nichimo|Yamato",
        "target_hint": "Nichimo|Musashi",
        "reason": "User-confirmed source is actually the Musashi; target matches ANH donors identity.",
    },
    {
        "source_id": 129,
        "target_id": 354,
        "source_hint": "Tamiya|Lotus 49",
        "target_hint": "Tamiya|Lotus 49B",
        "reason": "User-confirmed equivalence; target matches ANH donors identity.",
    },
    {
        "source_id": 134,
        "target_id": 359,
        "source_hint": "Tamiya|Jagdpanther",
        "target_hint": "Tamiya|Panther A / Jagdpanther",
        "reason": "User-confirmed equivalence; target matches ANH donors identity.",
    },
    {
        "source_id": 148,
        "target_id": 362,
        "source_hint": "Tamiya|LEOPARD",
        "target_hint": "Tamiya|Leopard",
        "reason": "User-confirmed equivalence; target matches ANH donors identity.",
    },
    {
        "source_id": 162,
        "target_id": 368,
        "source_hint": "Tamiya|Avro Lancaster",
        "target_hint": "Tamiya|Avro Lancaster",
        "reason": "User-confirmed equivalence; target matches ANH donors identity.",
    },
    {
        "source_id": 163,
        "target_id": 377,
        "source_hint": "Tamiya|Enterprise",
        "target_hint": "Tamiya|Hornet / Enterprise",
        "reason": "User-confirmed equivalence; target matches ANH donors identity.",
    },
    {
        "source_id": 165,
        "target_id": 376,
        "source_hint": "Tamiya|Kumano",
        "target_hint": "Tamiya|Suzuya / Mogami / Kumano",
        "reason": "User-confirmed equivalence; target matches ANH donors identity.",
    },
    {
        "source_id": 167,
        "target_id": 363,
        "source_hint": "Tamiya|M60A1",
        "target_hint": "Tamiya|M60A1 / M60A2",
        "reason": "User-confirmed equivalence; target matches ANH donors identity.",
    },
    {
        "source_id": 137,
        "target_id": 378,
        "source_hint": "Tamiya|M3 Lee",
        "target_hint": "Tamiya-MRC|M41 Walker Bulldog",
        "reason": "User-confirmed M3 Lee record should resolve to M41 Walker Bulldog with 4 Army figures.",
    },
]


SAFE_SPLITS = [
    {
        "source_id": 38,
        "source_hint": "Aurora|M8E2 Munitions Carrier and 8\" Howitzer",
        "targets": [
            {
                "target_id": 263,
                "target_hint": "Aurora|Howitzer",
                "part_numbers": ["npn_056"],
                "reason": "Part explicitly marked 'From Howitzer'.",
            },
            {
                "target_id": 264,
                "target_hint": "Aurora|M8E2 Munitions Carrier",
                "part_numbers": ["npn_048", "npn_046", "npn_049", "npn_057", "npn_060", "npn_020"],
                "reason": "Remaining parts from old combined M8E2/Howitzer record assigned to carrier side.",
            },
        ],
        "reference_target_id": 264,
        "reason": "Old combined kit split into the two canonical ANH donor rows 118 and 119.",
    },
]


EXCLUDED_KITS = [
    {
        "id": 1,
        "hint": "Aavid|Aavid 325705B00000G",
        "reason": "User-confirmed discard; Discarded sheet marks it as not a kit.",
        "delete_dependencies": True,
    },
    {
        "id": 92,
        "hint": "Holgate and Reynolds|HO Brick",
        "reason": "User-confirmed discard from active ANH donor truth.",
        "delete_dependencies": True,
    },
    {
        "id": 91,
        "hint": "Heller|Ship",
        "reason": "User-confirmed discard; Discarded sheet says to integrate purpose into Suffren instead.",
    },
    {
        "id": 35,
        "hint": "Aoshima|Jagd Tiger",
        "reason": "User-confirmed replacement for a secret kit, not an active ANH donor identity.",
        "delete_dependencies": True,
    },
    {
        "id": 95,
        "hint": "ITT|Vintage microchip",
        "reason": "User-confirmed discard from active ANH donor kit truth.",
        "delete_dependencies": True,
    },
    {
        "id": 116,
        "hint": "Plastruct|Lamp shade",
        "reason": "User-confirmed discard; component/material not counted as active ANH donor kit.",
        "delete_dependencies": True,
    },
    {
        "id": 122,
        "hint": "Smartlouvre|Koolshade",
        "reason": "User-confirmed discard; component/material not counted as active ANH donor kit.",
        "delete_dependencies": True,
    },
    {
        "id": 87,
        "hint": "Hasegawa|Mörser Karl",
        "reason": "User-confirmed unused for active ANH donor truth.",
        "delete_dependencies": True,
    },
    {
        "id": 88,
        "hint": "Hasegawa|Panzerkampfwagen VI Tiger",
        "reason": "User-confirmed not a donor.",
        "delete_dependencies": True,
    },
    {
        "id": 135,
        "hint": "Tamiya|Royal Army Chieftain Battle Tank",
        "reason": "User-confirmed removal from active ANH donor truth.",
        "delete_dependencies": True,
    },
    {
        "id": 435,
        "hint": "ERTL|International Transtar CO4070A",
        "reason": "User-confirmed removal from active ANH donor truth.",
    },
    {
        "id": 436,
        "hint": "Airfix / MPC|1930 Bentley",
        "reason": "User-confirmed removal from active ANH donor truth.",
    },
    {
        "id": 437,
        "hint": "Airfix / MPC|Spitfire",
        "reason": "User-confirmed removal from active ANH donor truth.",
    },
    {
        "id": 438,
        "hint": "Aurora|German Panther Tank",
        "reason": "User-confirmed removal from active ANH donor truth.",
    },
    {
        "id": 439,
        "hint": "Aurora|Japanese Medium Tank",
        "reason": "User-confirmed removal from active ANH donor truth.",
    },
    {
        "id": 440,
        "hint": "Lindberg|Blue Devil Destroyer",
        "reason": "User-confirmed removal from active ANH donor truth.",
    },
    {
        "id": 441,
        "hint": "Revell|Honda Super Hawk",
        "reason": "User-confirmed removal from active ANH donor truth.",
    },
    {
        "id": 442,
        "hint": "Revell|Praying Mantis",
        "reason": "User-confirmed removal from active ANH donor truth.",
    },
    {
        "id": 443,
        "hint": "Revell|VOSTOK",
        "reason": "User-confirmed removal from active ANH donor truth.",
    },
    {
        "id": 444,
        "hint": "Revell|Bell HueyCobra",
        "reason": "User-confirmed removal from active ANH donor truth.",
    },
    {
        "id": 445,
        "hint": "Revell|Bell UH-1D Huey",
        "reason": "User-confirmed removal from active ANH donor truth.",
    },
    {
        "id": 446,
        "hint": "Revell|Apollo Lunar Spacecraft",
        "reason": "User-confirmed removal from active ANH donor truth.",
    },
    {
        "id": 447,
        "hint": "Revell|Mercury and Gemini",
        "reason": "User-confirmed removal from active ANH donor truth.",
    },
    {
        "id": 448,
        "hint": "Tamiya / Hawk|Great Britain 18ton Light Tank Crusader",
        "reason": "User-confirmed removal from active ANH donor truth.",
    },
]


def clean(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"none", "nan", "-", "—"}:
        return None
    return text


def norm_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def key_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", norm_text(value))).strip()


def col_to_idx(ref: str | None) -> int | None:
    match = re.match(r"([A-Z]+)", ref or "")
    if not match:
        return None
    idx = 0
    for ch in match.group(1):
        idx = idx * 26 + (ord(ch) - 64)
    return idx - 1


def read_xlsx_sheet(path: Path, sheet_name: str) -> list[list[object]]:
    with zipfile.ZipFile(path) as archive:
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root.findall("main:si", NS):
                shared_strings.append(
                    "".join(text.text or "" for text in item.iter(f"{{{MAIN_NS}}}t"))
                )

        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        relmap = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}

        target = None
        for sheet in workbook.find("main:sheets", NS):
            if sheet.attrib["name"] == sheet_name:
                target = relmap[sheet.attrib[REL_NS + "id"]]
                break
        if target is None:
            raise ValueError(f"Sheet not found: {sheet_name}")
        if not target.startswith("xl/"):
            target = "xl/" + target

        root = ET.fromstring(archive.read(target))
        rows: list[list[object]] = []
        for row in root.findall(".//main:sheetData/main:row", NS):
            values: list[object] = []
            for cell in row.findall("main:c", NS):
                idx = col_to_idx(cell.attrib.get("r"))
                if idx is None:
                    idx = len(values)
                while len(values) <= idx:
                    values.append(None)

                value_node = cell.find("main:v", NS)
                if value_node is None:
                    value = None
                elif cell.attrib.get("t") == "s":
                    value = shared_strings[int(value_node.text)]
                else:
                    value = value_node.text
                values[idx] = value

            while values and values[-1] is None:
                values.pop()
            rows.append(values)
        return rows


def donor_rows() -> tuple[list[dict], list[dict]]:
    canonical = []
    discarded = []

    rows = read_xlsx_sheet(ANH_PATH, "SWANH donors")
    for row_number, row in enumerate(rows[2:], start=3):
        brand = clean(row[0] if len(row) > 0 else None)
        name = clean(row[2] if len(row) > 2 else None)
        if not brand or not name:
            continue
        canonical.append(
            {
                "row": row_number,
                "brand": brand,
                "scale": clean(row[1] if len(row) > 1 else None),
                "name": name,
                "serial_number": clean(row[3] if len(row) > 3 else None),
                "scalemates_url": clean(row[4] if len(row) > 4 else None),
            }
        )

    rows = read_xlsx_sheet(ANH_PATH, "Discarded")
    for row_number, row in enumerate(rows[1:], start=2):
        brand = clean(row[0] if len(row) > 0 else None)
        name = clean(row[2] if len(row) > 2 else None)
        if not brand or not name:
            continue
        discarded.append(
            {
                "row": row_number,
                "brand": brand,
                "scale": clean(row[1] if len(row) > 1 else None),
                "name": name,
                "serial_number": clean(row[3] if len(row) > 3 else None),
                "scalemates_url": clean(row[4] if len(row) > 4 else None),
                "comments": clean(row[6] if len(row) > 6 else None),
            }
        )

    return canonical, discarded


def connect() -> sqlite3.Connection:
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def add_source(db: sqlite3.Connection, code: str, title: str, local_path: str, notes: str) -> bool:
    existing = db.execute("SELECT id FROM sources WHERE source_code=?", (code,)).fetchone()
    if existing:
        db.execute(
            """
            UPDATE sources
            SET source_type='spreadsheet', title=?, local_path=?, notes=?
            WHERE id=?
            """,
            (title, local_path, notes, existing["id"]),
        )
        return False
    db.execute(
        """
        INSERT INTO sources (source_code, source_type, title, local_path, notes)
        VALUES (?, 'spreadsheet', ?, ?, ?)
        """,
        (code, title, local_path, notes),
    )
    return True


def fix_date_like_scales(db: sqlite3.Connection) -> int:
    rows = db.execute(
        """
        SELECT id, scale FROM kits
        WHERE scale GLOB '????-??-??*'
        ORDER BY id
        """
    ).fetchall()
    changed = 0
    for row in rows:
        match = re.match(r"^\d{4}-(\d{2})-01", row["scale"])
        if not match:
            continue
        denominator = int(match.group(1))
        if denominator <= 0:
            continue
        db.execute("UPDATE kits SET scale=? WHERE id=?", (f"1/{denominator}", row["id"]))
        changed += 1
    return changed


def kit_signature(row: sqlite3.Row) -> str:
    return f"{row['brand']}|{row['name']}|{row['serial_number'] or ''}"


def append_note(existing: str | None, addition: str) -> str:
    existing = clean(existing)
    if not existing:
        return addition
    if addition in existing:
        return existing
    return existing + "\n" + addition


def apply_url_fix(db: sqlite3.Connection, kit_id: int, hint: str, scalemates_url: str, reason: str) -> str:
    kit = db.execute("SELECT * FROM kits WHERE id=?", (kit_id,)).fetchone()
    if not kit:
        return f"skipped URL fix {kit_id}: kit missing"
    if hint and not all(part.lower() in kit_signature(kit).lower() for part in hint.split("|")):
        raise RuntimeError(f"URL fix hint mismatch for kit {kit_id}: {kit_signature(kit)}")
    current = norm_text(kit["scalemates_url"]).rstrip("/")
    desired = norm_text(scalemates_url).rstrip("/")
    if current == desired:
        return f"skipped URL fix {kit_id}: already correct"
    note = append_note(
        kit["notes"],
        f"[donor cleanup 2026-04-27] Updated Scalemates URL from {kit['scalemates_url']} to {scalemates_url}. {reason}",
    )
    db.execute(
        "UPDATE kits SET scalemates_url=?, notes=? WHERE id=?",
        (scalemates_url, note, kit_id),
    )
    return f"fixed URL for kit {kit_id}: {kit['scalemates_url']} -> {scalemates_url}"


def transfer_kit_reference(db: sqlite3.Connection, source_id: int, target_id: int) -> None:
    refs = db.execute("SELECT * FROM kit_references WHERE kit_id=?", (source_id,)).fetchall()
    for ref in refs:
        existing = db.execute(
            "SELECT id FROM kit_references WHERE kit_id=? AND system=?",
            (target_id, ref["system"]),
        ).fetchone()
        if existing:
            note = append_note(ref["notes"], f"Merged duplicate reference value from kit {source_id}: {ref['value']}")
            db.execute("UPDATE kit_references SET notes=? WHERE id=?", (note, existing["id"]))
            db.execute("DELETE FROM kit_references WHERE id=?", (ref["id"],))
        else:
            db.execute("UPDATE kit_references SET kit_id=? WHERE id=?", (target_id, ref["id"]))


def merge_kit(db: sqlite3.Connection, source_id: int, target_id: int, reason: str, source_hint: str, target_hint: str) -> str:
    source = db.execute("SELECT * FROM kits WHERE id=?", (source_id,)).fetchone()
    target = db.execute("SELECT * FROM kits WHERE id=?", (target_id,)).fetchone()
    if not source and target:
        return f"skipped {source_id} -> {target_id}: already merged"
    if not source or not target:
        raise RuntimeError(f"Cannot merge {source_id}->{target_id}: missing source or target")
    if source_hint and not all(part.lower() in kit_signature(source).lower() for part in source_hint.split("|")):
        raise RuntimeError(f"Source hint mismatch for kit {source_id}: {kit_signature(source)}")
    if target_hint and not all(part.lower() in kit_signature(target).lower() for part in target_hint.split("|")):
        raise RuntimeError(f"Target hint mismatch for kit {target_id}: {kit_signature(target)}")

    source_direct = db.execute("SELECT COUNT(*) c FROM placements WHERE kit_id=?", (source_id,)).fetchone()["c"]
    if source_direct:
        conflicts = db.execute(
            """
            SELECT
                s.id AS source_id,
                t.id AS target_id,
                s.model_id AS source_model_id,
                t.model_id AS target_model_id,
                s.map_id AS source_map_id,
                t.map_id AS target_map_id,
                s.location_label AS source_location_label,
                t.location_label AS target_location_label,
                s.copy_count AS source_copy_count,
                t.copy_count AS target_copy_count,
                s.confidence AS source_confidence,
                t.confidence AS target_confidence,
                s.modification AS source_modification,
                t.modification AS target_modification,
                s.notes AS source_notes,
                t.notes AS target_notes,
                s.source_url AS source_url,
                t.source_url AS target_url
            FROM placements s
            JOIN placements t
              ON t.model_id=s.model_id
             AND t.kit_id=?
             AND t.part_id IS NULL
             AND t.cast_assembly_id IS NULL
            WHERE s.kit_id=?
              AND s.part_id IS NULL
              AND s.cast_assembly_id IS NULL
            """,
            (target_id, source_id),
        ).fetchall()
        if conflicts:
            for conflict in conflicts:
                same = all(
                    conflict[f"source_{field}"] == conflict[f"target_{field}"]
                    for field in (
                        "model_id",
                        "map_id",
                        "location_label",
                        "copy_count",
                        "confidence",
                        "modification",
                        "notes",
                    )
                ) and conflict["source_url"] == conflict["target_url"]
                if not same:
                    raise RuntimeError(
                        f"Cannot auto-merge {source_id}->{target_id}: non-identical duplicate direct placements would be created"
                    )
                db.execute("DELETE FROM placements WHERE id=?", (conflict["source_id"],))

    stamp = dt.date.today().isoformat()
    note = f"[donor cleanup {stamp}] Merged kit {source_id} ({kit_signature(source)}) into this record. {reason}"
    db.execute(
        """
        UPDATE kits
        SET notes=?,
            scans_url=COALESCE(scans_url, ?),
            instructions_url=COALESCE(instructions_url, ?),
            availability=COALESCE(availability, ?)
        WHERE id=?
        """,
        (
            append_note(target["notes"], note),
            source["scans_url"],
            source["instructions_url"],
            source["availability"],
            target_id,
        ),
    )

    db.execute("UPDATE parts SET kit_id=? WHERE kit_id=?", (target_id, source_id))
    db.execute("UPDATE placements SET kit_id=? WHERE kit_id=?", (target_id, source_id))
    db.execute(
        "UPDATE image_regions SET entity_id=? WHERE entity_type='kit' AND entity_id=?",
        (target_id, source_id),
    )
    db.execute(
        "UPDATE image_links SET entity_id=? WHERE entity_type='kit' AND entity_id=?",
        (target_id, source_id),
    )
    db.execute(
        "UPDATE claims SET subject_id=? WHERE subject_type='kit' AND subject_id=?",
        (target_id, source_id),
    )
    db.execute(
        "UPDATE claims SET object_id=? WHERE object_type='kit' AND object_id=?",
        (target_id, source_id),
    )
    db.execute("UPDATE kit_history SET kit_id=? WHERE kit_id=?", (target_id, source_id))
    db.execute("UPDATE placement_history SET prev_kit_id=? WHERE prev_kit_id=?", (target_id, source_id))
    transfer_kit_reference(db, source_id, target_id)
    db.execute("DELETE FROM kits WHERE id=?", (source_id,))
    return f"merged {source_id} -> {target_id}"


def split_combined_kit(
    db: sqlite3.Connection,
    source_id: int,
    source_hint: str,
    targets: list[dict],
    reference_target_id: int | None,
    reason: str,
) -> str:
    source = db.execute("SELECT * FROM kits WHERE id=?", (source_id,)).fetchone()
    if not source:
        return f"skipped split {source_id}: already split"
    if source_hint and not all(part.lower() in kit_signature(source).lower() for part in source_hint.split("|")):
        raise RuntimeError(f"Split source hint mismatch for kit {source_id}: {kit_signature(source)}")

    assigned_part_numbers = []
    for target in targets:
        target_row = db.execute("SELECT * FROM kits WHERE id=?", (target["target_id"],)).fetchone()
        if not target_row:
            raise RuntimeError(f"Split target missing: {target['target_id']}")
        if target["target_hint"] and not all(
            part.lower() in kit_signature(target_row).lower()
            for part in target["target_hint"].split("|")
        ):
            raise RuntimeError(
                f"Split target hint mismatch for kit {target['target_id']}: {kit_signature(target_row)}"
            )
        for part_number in target["part_numbers"]:
            part = db.execute(
                "SELECT id FROM parts WHERE kit_id=? AND part_number=?",
                (source_id, part_number),
            ).fetchone()
            if not part:
                raise RuntimeError(f"Split part not found on kit {source_id}: {part_number}")
            db.execute("UPDATE parts SET kit_id=? WHERE id=?", (target["target_id"], part["id"]))
            assigned_part_numbers.append(part_number)

        stamp = dt.date.today().isoformat()
        note = (
            f"[donor cleanup {stamp}] Split parts {', '.join(target['part_numbers'])} "
            f"from old combined kit {source_id} ({kit_signature(source)}). {target['reason']} {reason}"
        )
        db.execute(
            "UPDATE kits SET notes=? WHERE id=?",
            (append_note(target_row["notes"], note), target["target_id"]),
        )

    leftover_parts = db.execute(
        "SELECT part_number FROM parts WHERE kit_id=? ORDER BY part_number",
        (source_id,),
    ).fetchall()
    if leftover_parts:
        names = ", ".join(row["part_number"] for row in leftover_parts)
        raise RuntimeError(f"Cannot delete split source kit {source_id}; unassigned parts remain: {names}")

    refs = db.execute("SELECT * FROM kit_references WHERE kit_id=?", (source_id,)).fetchall()
    for ref in refs:
        if reference_target_id:
            existing = db.execute(
                "SELECT id, notes FROM kit_references WHERE kit_id=? AND system=?",
                (reference_target_id, ref["system"]),
            ).fetchone()
            if existing:
                note = append_note(
                    existing["notes"],
                    f"Merged split reference from old combined kit {source_id}: {ref['value']}",
                )
                db.execute("UPDATE kit_references SET notes=? WHERE id=?", (note, existing["id"]))
                db.execute("DELETE FROM kit_references WHERE id=?", (ref["id"],))
            else:
                note = append_note(
                    ref["notes"],
                    f"Moved from old combined kit {source_id}; related split target parts also moved to other canonical kit.",
                )
                db.execute(
                    "UPDATE kit_references SET kit_id=?, notes=? WHERE id=?",
                    (reference_target_id, note, ref["id"]),
                )
        else:
            db.execute("DELETE FROM kit_references WHERE id=?", (ref["id"],))

    blockers = {
        "direct_placements": db.execute(
            "SELECT COUNT(*) c FROM placements WHERE kit_id=?", (source_id,)
        ).fetchone()["c"],
        "image_regions": db.execute(
            "SELECT COUNT(*) c FROM image_regions WHERE entity_type='kit' AND entity_id=?",
            (source_id,),
        ).fetchone()["c"],
        "image_links": db.execute(
            "SELECT COUNT(*) c FROM image_links WHERE entity_type='kit' AND entity_id=?",
            (source_id,),
        ).fetchone()["c"],
    }
    blockers = {name: count for name, count in blockers.items() if count}
    if blockers:
        raise RuntimeError(f"Cannot delete split source kit {source_id}; dependencies remain: {blockers}")

    db.execute("DELETE FROM kit_history WHERE kit_id=?", (source_id,))
    db.execute("DELETE FROM kits WHERE id=?", (source_id,))
    return f"split {source_id} -> " + ", ".join(
        f"{target['target_id']}[{', '.join(target['part_numbers'])}]" for target in targets
    )


def delete_excluded_kit(
    db: sqlite3.Connection,
    kit_id: int,
    hint: str,
    reason: str,
    delete_dependencies: bool = False,
) -> str:
    kit = db.execute("SELECT * FROM kits WHERE id=?", (kit_id,)).fetchone()
    if not kit:
        return f"skipped excluded kit {kit_id}: already removed"
    if hint and not all(part.lower() in kit_signature(kit).lower() for part in hint.split("|")):
        raise RuntimeError(f"Excluded kit hint mismatch for kit {kit_id}: {kit_signature(kit)}")

    checks = {
        "placements": "SELECT COUNT(*) c FROM placements WHERE kit_id=?",
        "parts": "SELECT COUNT(*) c FROM parts WHERE kit_id=?",
        "image_regions": "SELECT COUNT(*) c FROM image_regions WHERE entity_type='kit' AND entity_id=?",
        "image_links": "SELECT COUNT(*) c FROM image_links WHERE entity_type='kit' AND entity_id=?",
        "claim_subjects": "SELECT COUNT(*) c FROM claims WHERE subject_type='kit' AND subject_id=?",
        "claim_objects": "SELECT COUNT(*) c FROM claims WHERE object_type='kit' AND object_id=?",
        "kit_references": "SELECT COUNT(*) c FROM kit_references WHERE kit_id=?",
    }
    blockers = {
        name: db.execute(query, (kit_id,)).fetchone()["c"]
        for name, query in checks.items()
    }
    blockers = {name: count for name, count in blockers.items() if count}
    if blockers:
        if delete_dependencies:
            part_ids = [
                row["id"]
                for row in db.execute("SELECT id FROM parts WHERE kit_id=?", (kit_id,))
            ]
            if part_ids:
                part_placeholders = ",".join("?" for _ in part_ids)
                placement_ids = [
                    row["id"]
                    for row in db.execute(
                        f"SELECT id FROM placements WHERE part_id IN ({part_placeholders})",
                        part_ids,
                    )
                ]
                if placement_ids:
                    placement_placeholders = ",".join("?" for _ in placement_ids)
                    db.execute(
                        f"DELETE FROM placement_positions WHERE placement_id IN ({placement_placeholders})",
                        placement_ids,
                    )
                    db.execute(
                        f"DELETE FROM placement_contributors WHERE placement_id IN ({placement_placeholders})",
                        placement_ids,
                    )
                    db.execute(
                        f"DELETE FROM placement_history WHERE placement_id IN ({placement_placeholders})",
                        placement_ids,
                    )
                    db.execute(
                        f"DELETE FROM placements WHERE id IN ({placement_placeholders})",
                        placement_ids,
                    )
                db.execute(
                    f"DELETE FROM part_files WHERE part_id IN ({part_placeholders})",
                    part_ids,
                )
                db.execute(f"DELETE FROM parts WHERE id IN ({part_placeholders})", part_ids)
            db.execute("DELETE FROM kit_references WHERE kit_id=?", (kit_id,))
            blockers = {}
        if blockers:
            raise RuntimeError(f"Cannot delete excluded kit {kit_id}; dependencies remain: {blockers}")

    db.execute("DELETE FROM kit_history WHERE kit_id=?", (kit_id,))
    db.execute("DELETE FROM kits WHERE id=?", (kit_id,))
    return f"deleted excluded kit {kit_id}: {kit['brand']} | {kit['scale']} | {kit['name']} ({reason})"


def duplicate_url_groups(db: sqlite3.Connection) -> list[tuple[str, list[sqlite3.Row]]]:
    groups: dict[str, list[sqlite3.Row]] = {}
    for kit in db.execute("SELECT * FROM kits WHERE scalemates_url IS NOT NULL ORDER BY id"):
        key = norm_text(kit["scalemates_url"]).rstrip("/")
        groups.setdefault(key, []).append(kit)
    return [(url, kits) for url, kits in groups.items() if len(kits) > 1]


def discarded_hits(db: sqlite3.Connection, discarded: list[dict]) -> list[tuple[sqlite3.Row, dict]]:
    urls = {
        norm_text(row["scalemates_url"]).rstrip("/"): row
        for row in discarded
        if row.get("scalemates_url")
    }
    names = {(key_text(row["brand"]), key_text(row["name"])): row for row in discarded}
    hits = []
    for kit in db.execute("SELECT * FROM kits ORDER BY id"):
        url = norm_text(kit["scalemates_url"]).rstrip("/") if kit["scalemates_url"] else ""
        hit = urls.get(url) or names.get((key_text(kit["brand"]), key_text(kit["name"])))
        if hit:
            hits.append((kit, hit))
    return hits


def audit(db: sqlite3.Connection, canonical: list[dict], discarded: list[dict]) -> None:
    canonical_urls = {
        norm_text(row["scalemates_url"]).rstrip("/")
        for row in canonical
        if row.get("scalemates_url")
    }
    canonical_names = {(key_text(row["brand"]), key_text(row["name"])) for row in canonical}
    kits = db.execute("SELECT * FROM kits ORDER BY id").fetchall()
    unmatched = [
        kit
        for kit in kits
        if not (
            (kit["scalemates_url"] and norm_text(kit["scalemates_url"]).rstrip("/") in canonical_urls)
            or (key_text(kit["brand"]), key_text(kit["name"])) in canonical_names
        )
    ]
    date_scales = db.execute(
        "SELECT COUNT(*) c FROM kits WHERE scale GLOB '????-??-??*'"
    ).fetchone()["c"]
    duplicate_urls = duplicate_url_groups(db)
    discarded = discarded_hits(db, discarded)

    print("Donor DB audit")
    print(f"  canonical SWANH donor rows: {len(canonical)}")
    print(f"  DB kits: {len(kits)}")
    print(f"  kits not matched to SWANH by URL or normalized brand/name: {len(unmatched)}")
    print(f"  date-like scale values: {date_scales}")
    print(f"  duplicate Scalemates URL groups: {len(duplicate_urls)}")
    print(f"  active DB kits matching Discarded sheet: {len(discarded)}")

    if duplicate_urls:
        print("\nRemaining duplicate URL groups:")
        for url, group in duplicate_urls[:50]:
            print(f"  {url}")
            for kit in group:
                direct = db.execute(
                    "SELECT COUNT(*) c FROM placements WHERE kit_id=?", (kit["id"],)
                ).fetchone()["c"]
                parts = db.execute("SELECT COUNT(*) c FROM parts WHERE kit_id=?", (kit["id"],)).fetchone()["c"]
                print(
                    f"    {kit['id']}: {kit['brand']} | {kit['scale']} | {kit['name']} | "
                    f"{kit['serial_number'] or ''} | placements={direct} parts={parts}"
                )

    if discarded:
        print("\nDiscarded-sheet hits still active:")
        for kit, hit in discarded:
            direct = db.execute(
                "SELECT COUNT(*) c FROM placements WHERE kit_id=?", (kit["id"],)
            ).fetchone()["c"]
            part_placements = db.execute(
                """
                SELECT COUNT(*) c
                FROM placements p
                JOIN parts pa ON pa.id=p.part_id
                WHERE pa.kit_id=?
                """,
                (kit["id"],),
            ).fetchone()["c"]
            print(
                f"  kit {kit['id']}: {kit['brand']} | {kit['scale']} | {kit['name']} | "
                f"discarded row {hit['row']} | direct={direct} part_placements={part_placements} | "
                f"{hit.get('comments') or ''}"
            )


def apply_clear(db: sqlite3.Connection) -> None:
    add_source(
        db,
        "SPREADSHEET-ANH-DONORS",
        "ANH donors.xlsx / SWANH donors",
        "ANH donors.xlsx",
        "Canonical donor-kit matrix for the current cleanup pass. The Discarded sheet is non-authoritative.",
    )
    add_source(
        db,
        "SPREADSHEET-PARTLIST-PRIVATE",
        "PartList_private.xlsx",
        "PartList_private.xlsx",
        "Falcon part/map spreadsheet. Used for part-level and map detail; ANH donors governs cross-model donor identity.",
    )
    scale_count = fix_date_like_scales(db)
    print(f"fixed date-like scales: {scale_count}")

    for url_fix in SAFE_URL_FIXES:
        result = apply_url_fix(db, **url_fix)
        print(result)

    for merge in SAFE_MERGES:
        result = merge_kit(db, **merge)
        print(result)

    for split in SAFE_SPLITS:
        result = split_combined_kit(db, **split)
        print(result)

    for excluded in EXCLUDED_KITS:
        result = delete_excluded_kit(
            db,
            kit_id=excluded["id"],
            hint=excluded["hint"],
            reason=excluded["reason"],
            delete_dependencies=excluded.get("delete_dependencies", False),
        )
        print(result)

    fk_errors = db.execute("PRAGMA foreign_key_check").fetchall()
    if fk_errors:
        raise RuntimeError(f"foreign key errors after cleanup: {fk_errors}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", action="store_true", help="Print donor/DB health report")
    parser.add_argument("--apply-clear", action="store_true", help="Apply conservative, predefined cleanup fixes")
    args = parser.parse_args(argv)

    if not ANH_PATH.exists():
        raise SystemExit(f"Missing {ANH_PATH}")
    if not DB_PATH.exists():
        raise SystemExit(f"Missing {DB_PATH}")

    canonical, discarded = donor_rows()
    with connect() as db:
        if args.apply_clear:
            apply_clear(db)
            db.commit()
        if args.audit or not args.apply_clear:
            audit(db, canonical, discarded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

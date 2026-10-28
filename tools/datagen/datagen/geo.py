"""Fixed geography from ARCHITECTURE.md section 8: regions, states, universities."""

from __future__ import annotations

from .config import load_data

REGIONS: list[dict[str, str]] = [
    {"code": "NORTH", "name": "Northern", "hq_city": "Kanpur"},
    {"code": "NORTH_WEST", "name": "North-Western", "hq_city": "Chandigarh"},
    {"code": "CENTRAL", "name": "Central", "hq_city": "Bhopal"},
    {"code": "WEST", "name": "Western", "hq_city": "Mumbai"},
    {"code": "WEST_CENTRAL", "name": "West-Central", "hq_city": "Vadodara"},
    {"code": "SOUTH_WEST", "name": "South-Western", "hq_city": "Bengaluru"},
    {"code": "SOUTH", "name": "Southern", "hq_city": "Chennai"},
    {"code": "SOUTH_CENTRAL", "name": "South-Central", "hq_city": "Hyderabad"},
    {"code": "EAST", "name": "Eastern", "hq_city": "Kolkata"},
    {"code": "NORTH_EAST", "name": "North-Eastern", "hq_city": "Guwahati"},
]

STATES: list[dict[str, str]] = [
    {"code": "UP", "name": "Uttar Pradesh", "region": "NORTH"},
    {"code": "UK", "name": "Uttarakhand", "region": "NORTH"},
    {"code": "PB", "name": "Punjab", "region": "NORTH_WEST"},
    {"code": "HR", "name": "Haryana", "region": "NORTH_WEST"},
    {"code": "HP", "name": "Himachal Pradesh", "region": "NORTH_WEST"},
    {"code": "JK", "name": "Jammu & Kashmir", "region": "NORTH_WEST"},
    {"code": "LA", "name": "Ladakh", "region": "NORTH_WEST"},
    {"code": "CH", "name": "Chandigarh", "region": "NORTH_WEST"},
    {"code": "DL", "name": "Delhi", "region": "NORTH_WEST"},
    {"code": "MP", "name": "Madhya Pradesh", "region": "CENTRAL"},
    {"code": "CG", "name": "Chhattisgarh", "region": "CENTRAL"},
    {"code": "MH", "name": "Maharashtra", "region": "WEST"},
    {"code": "GA", "name": "Goa", "region": "WEST"},
    {"code": "DH", "name": "Dadra & Nagar Haveli and Daman & Diu", "region": "WEST"},
    {"code": "GJ", "name": "Gujarat", "region": "WEST_CENTRAL"},
    {"code": "RJ", "name": "Rajasthan", "region": "WEST_CENTRAL"},
    {"code": "KA", "name": "Karnataka", "region": "SOUTH_WEST"},
    {"code": "KL", "name": "Kerala", "region": "SOUTH_WEST"},
    {"code": "LD", "name": "Lakshadweep", "region": "SOUTH_WEST"},
    {"code": "TN", "name": "Tamil Nadu", "region": "SOUTH"},
    {"code": "PY", "name": "Puducherry", "region": "SOUTH"},
    {"code": "AN", "name": "Andaman & Nicobar", "region": "SOUTH"},
    {"code": "TS", "name": "Telangana", "region": "SOUTH_CENTRAL"},
    {"code": "AP", "name": "Andhra Pradesh", "region": "SOUTH_CENTRAL"},
    {"code": "WB", "name": "West Bengal", "region": "EAST"},
    {"code": "OD", "name": "Odisha", "region": "EAST"},
    {"code": "BR", "name": "Bihar", "region": "EAST"},
    {"code": "JH", "name": "Jharkhand", "region": "EAST"},
    {"code": "AS", "name": "Assam", "region": "NORTH_EAST"},
    {"code": "AR", "name": "Arunachal Pradesh", "region": "NORTH_EAST"},
    {"code": "MN", "name": "Manipur", "region": "NORTH_EAST"},
    {"code": "ML", "name": "Meghalaya", "region": "NORTH_EAST"},
    {"code": "MZ", "name": "Mizoram", "region": "NORTH_EAST"},
    {"code": "NL", "name": "Nagaland", "region": "NORTH_EAST"},
    {"code": "SK", "name": "Sikkim", "region": "NORTH_EAST"},
    {"code": "TR", "name": "Tripura", "region": "NORTH_EAST"},
]

STATE_BY_CODE = {s["code"]: s for s in STATES}
REGION_OF_STATE = {s["code"]: s["region"] for s in STATES}

# The demo university (ARCHITECTURE section 7) and one state technical university per state.
# Big states get a second, city-named university so affiliation is not one-to-one with state.
PRIMARY_UNIVERSITY: dict[str, tuple[str, str]] = {
    "MH": ("MSTU", "Maharashtra State Technical University"),
    "TN": ("TNTU", "Tamil Nadu Technological University"),
    "KA": ("KSTU", "Karnataka State Technological University"),
    "AP": ("APTU", "Andhra Pradesh Technological University"),
    "TS": ("TSTU", "Telangana State Technological University"),
    "UP": ("UPTU", "Uttar Pradesh Technical University"),
    "GJ": ("GJTU", "Gujarat Technological University"),
    "WB": ("WBUT", "West Bengal University of Technology"),
    "RJ": ("RJTU", "Rajasthan Technical University"),
    "MP": ("MPTU", "Madhya Pradesh Technical University"),
    "KL": ("KLTU", "Kerala Technological University"),
    "PB": ("PBTU", "Punjab Technical University"),
    "HR": ("HRTU", "Haryana State Technical University"),
    "OD": ("ODTU", "Odisha Technical University"),
}

SECONDARY_UNIVERSITY: dict[str, tuple[str, str]] = {
    "MH": ("NGPU", "Nagpur University of Technology"),
    "TN": ("CBEU", "Coimbatore University of Engineering"),
    "KA": ("MYSU", "Mysuru University of Technology"),
    "AP": ("VSPU", "Visakhapatnam University of Technology"),
    "TS": ("WGLU", "Warangal University of Technology"),
    "UP": ("LKOU", "Lucknow Technical University"),
    "GJ": ("SRTU", "Surat Technological University"),
    "WB": ("DGPU", "Durgapur University of Technology"),
}


def universities() -> list[dict[str, str]]:
    """Every state has one technical university; large states have two."""
    out: list[dict[str, str]] = []
    for state in STATES:
        code = state["code"]
        if code in PRIMARY_UNIVERSITY:
            ucode, uname = PRIMARY_UNIVERSITY[code]
        else:
            ucode, uname = f"{code}TU", f"{state['name']} Technical University"
        out.append({"code": ucode, "name": uname, "state_code": code})
        if code in SECONDARY_UNIVERSITY:
            ucode, uname = SECONDARY_UNIVERSITY[code]
            out.append({"code": ucode, "name": uname, "state_code": code})
    return out


def state_profile(code: str) -> dict:
    """Cities, PIN prefix, institution weight and naming-group weights for a state."""
    return load_data("geo.json")["states"][code]


def exam_for_state(code: str) -> str:
    geo = load_data("geo.json")
    return geo["exams"].get(code, geo["default_exam"])


def state_weights() -> list[tuple[str, float]]:
    geo = load_data("geo.json")["states"]
    return [(s["code"], float(geo[s["code"]]["weight"])) for s in STATES]

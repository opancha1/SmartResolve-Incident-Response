import math
import re
from collections import Counter

RULES = {
    "Security": r"phish(?:ing)?|suspicious (?:email|login|activity|mfa)|malware|ransomware|unauthori[sz]ed access|compromised|credential theft",
    "Printing and Scanning": r"print(?:er|ing)?|scan(?:ner|ning)?|print queue|paper jam|toner",
    "Classroom Technology": r"document camera|doc cam|projector|lecture capture|smart ?board|classroom display|classroom av|podium|av system",
    "Software": r"lockdown browser|respondus|software|applications?|install(?:ation)?|crash(?:ed|es|ing)?|canvas|license|update loop",
    "Network": r"wi[ -]?fi|wireless|internet|network|ethernet|vpn|latency|packet loss|dns",
    "Account": r"accounts?|password|log[ -]?in|sign[ -]?in|locked out|authentication|mfa|duo|permissions?|single sign.on|sso",
    "Email and Collaboration": r"email|outlook|mailbox|teams|sharepoint|zoom|calendar|onedrive",
    "Hardware": r"docking station|dock|laptop|monitor|keyboard|webcam|battery|mouse|charger|usb|computer",
}

def classification_details(title: str, description: str) -> dict:
    if re.search(r"\b(?:classroom|lecture hall|podium)\b", f"{title} {description}", re.I):
        if re.search(r"\b(?:webcam|microphone|display|camera)\b", f"{title} {description}", re.I):
            return {"category": "Classroom Technology", "reason": "AV device and classroom context", "confidence": "Strong rule match"}
    for category, pattern in RULES.items():
        hit = re.search(r"\b(?:" + pattern + r")\b", f"{title} {description}", re.I)
        if hit:
            return {"category": category, "reason": f"Matched “{hit.group()}” in the report", "confidence": "Rule match"}
    return {"category": "Other", "reason": "No support category rule matched", "confidence": "Unclassified"}

def classify_ticket(title: str, description: str) -> str:
    return classification_details(title, description)["category"]

def priority_factors(affected_users, severity="Medium", location="", security=False, evidence=False):
    factors = {
        "Reported impact": min(40, affected_users * 4),
        "Reported severity": {"Low": 5, "Medium": 15, "High": 28, "Critical": 40}.get(severity.title(), 15),
    }
    if "woodward" in location.lower() or "library" in location.lower():
        factors["Location policy"] = 5
    if security:
        factors["Security issue type"] = 15
    if evidence:
        factors["Correlated incident evidence"] = 15
    return factors

def calculate_priority(affected_users: int, severity: str = "Medium", location: str = "", security: bool = False, evidence: bool = False) -> int:
    return min(100, sum(priority_factors(affected_users, severity, location, security, evidence).values()))

def priority_label(score: int) -> str:
    return "Critical" if score > 75 else "High" if score > 50 else "Medium" if score > 25 else "Low"

def network_severity(latency: float, packet_loss: float, availability: bool) -> str:
    if not availability: return "Critical"
    if latency > 150 or packet_loss > 10: return "High"
    return "Normal"

def network_reason(event) -> str:
    if not event.availability: return "Service is unavailable"
    reasons=[]
    if event.latency > 150: reasons.append(f"latency {event.latency:g} ms exceeds 150 ms")
    if event.packet_loss > 10: reasons.append(f"packet loss {event.packet_loss:g}% exceeds 10%")
    return "; ".join(reasons) or "Within demo thresholds"

def security_risk(failed_attempts: int, event_type: str) -> int:
    return min(100, sum(security_factors(failed_attempts, event_type).values()))

def security_factors(failed_attempts: int, event_type: str) -> dict:
    event = event_type.casefold()
    weight = next((points for term, points in (("endpoint protection disabled", 55), ("privileged access", 45), ("password reset", 20), ("unauthorized", 45), ("phishing", 55), ("suspicious", 30), ("unusual", 30), ("lockout", 20)) if term in event), 0)
    return {"Failed authentication attempts": min(65, failed_attempts * 10), "Event type": weight}

def security_severity(score: int) -> str:
    return "Critical" if score >= 80 else "High" if score >= 55 else "Medium" if score >= 25 else "Low"

def cosine_similarity(first: str, second: str) -> float:
    tokens = lambda text: re.findall(r"[a-z]{2,}", text.lower())
    a, b = Counter(tokens(first)), Counter(tokens(second))
    if not a or not b: return 0.0
    # TF-IDF-like normalized term frequency is sufficient for the small local corpus.
    dot = sum(a[word] * b[word] for word in a)
    return dot / math.sqrt(sum(v*v for v in a.values()) * sum(v*v for v in b.values()))

def recommend_technician(technicians, category: str, location: str):
    matches = [t for t in technicians if t.availability]
    if not matches: return None, "No technician is currently available."
    specialization = {"Printing and Scanning": "Hardware", "Email and Collaboration": "Software"}.get(category, category)
    def score(technician):
        return (50 if technician.specialization.casefold() == specialization.casefold() else 0) + (
            20 if technician.location.casefold() == location.casefold() else 0
        ) - technician.current_workload * 5
    winner = min(matches, key=lambda technician: (-score(technician), technician.name))
    reasons = [f"{winner.current_workload} unresolved assigned tickets"]
    if winner.specialization.casefold() == specialization.casefold():
        reasons.append("matching specialization")
    if winner.location.casefold() == location.casefold():
        reasons.append("matching location")
    return winner, f"{winner.name}: {', '.join(reasons)}."

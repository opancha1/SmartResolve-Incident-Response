import math
import re
from collections import Counter

def classify_ticket(title: str, description: str) -> str:
    text = f"{title} {description}".lower()
    rules = {"Security": ["phish", "password", "login", "malware", "suspicious", "hack"], "Network": ["wi-fi", "wifi", "internet", "network", "connect", "latency", "disconnect"], "Hardware": ["printer", "laptop", "monitor", "keyboard", "computer"], "Software": ["software", "app", "application", "install", "crash"], "Classroom Technology": ["projector", "classroom", "smart board", "microphone", "camera"], "Account": ["account", "access", "username", "permission"]}
    return next((category for category, words in rules.items() if any(word in text for word in words)), "Other")

def calculate_priority(affected_users: int, severity: str = "Medium", location: str = "", security: bool = False, evidence: bool = False) -> int:
    score = min(40, affected_users * 4)
    score += {"Low": 5, "Medium": 15, "High": 28, "Critical": 40}.get(severity.title(), 15)
    if "woodward" in location.lower() or "library" in location.lower(): score += 5
    if security: score += 15
    if evidence: score += 15
    return min(100, score)

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
    score = min(65, failed_attempts * 10)
    if "suspicious" in event_type.lower(): score += 30
    return min(100, score)

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
    def score(t): return (50 if t.specialization.lower() == category.lower() else 0) + (20 if t.location.lower() == location.lower() else 0) - t.current_workload * 5
    winner = max(matches, key=score)
    return winner, f"{winner.name} matches {category}, is {'at' if winner.location.lower() == location.lower() else 'near'} {location}, and has workload {winner.current_workload}."

from app.services.intelligence import classify_ticket, calculate_priority, cosine_similarity, network_severity, security_risk, recommend_technician
class Tech:
    def __init__(self,name,specialization,location,current_workload,availability=True):self.name=name;self.specialization=specialization;self.location=location;self.current_workload=current_workload;self.availability=availability
def test_classification(): assert classify_ticket("Wifi issue","Cannot connect to internet") == "Network"
def test_priority(): assert calculate_priority(20,"High","Woodward",evidence=True) >= 75
def test_network_anomaly(): assert network_severity(240,21,True) == "High"
def test_similarity(): assert cosine_similarity("wifi disconnecting woodward","wifi disconnecting in woodward") > .7
def test_security_risk(): assert security_risk(7,"Suspicious activity") == 95
def test_technician_recommendation(): assert recommend_technician([Tech("A","Network","Woodward",1)],"Network","Woodward")[0].name=="A"

import pytest


@pytest.mark.parametrize(("title", "description", "expected"), [
    ("Webcam not working", "USB webcam on my laptop", "Hardware"),
    ("Webcam not working", "The webcam in the classroom cannot be selected", "Classroom Technology"),
    ("Doc cam not working", "No image for the instructor", "Classroom Technology"),
    ("Projector flickering", "Display flickers during class", "Classroom Technology"),
    ("Docking station not working", "My monitor is blank", "Hardware"),
    ("LockDown Browser not working", "Cannot connect to the exam", "Software"),
    ("Wi-Fi not connecting", "Campus wireless dropped", "Network"),
    ("Account locked", "I cannot sign in", "Account"),
    ("Suspicious email", "Unknown sender requested credentials", "Security"),
    ("Paper jam", "Also affects the printer", "Printing and Scanning"),
    ("Outlook missing mail", "Shared mailbox stopped receiving messages", "Email and Collaboration"),
    ("Help needed", "Please contact me with details", "Other"),
])
def test_support_classification_examples(title, description, expected):
    assert classify_ticket(title, description) == expected

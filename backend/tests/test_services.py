from app.services.intelligence import classify_ticket, calculate_priority, cosine_similarity, network_severity, security_risk, recommend_technician
class Tech:
    def __init__(self,name,specialization,location,current_workload,availability=True):self.name=name;self.specialization=specialization;self.location=location;self.current_workload=current_workload;self.availability=availability
def test_classification(): assert classify_ticket("Wifi issue","Cannot connect to internet") == "Network"
def test_priority(): assert calculate_priority(20,"High","Woodward",evidence=True) >= 75
def test_network_anomaly(): assert network_severity(240,21,True) == "High"
def test_similarity(): assert cosine_similarity("wifi disconnecting woodward","wifi disconnecting in woodward") > .7
def test_security_risk(): assert security_risk(7,"Suspicious activity") == 95
def test_technician_recommendation(): assert recommend_technician([Tech("A","Network","Woodward",1)],"Network","Woodward")[0].name=="A"

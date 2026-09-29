from fastapi import APIRouter

router=APIRouter(prefix="/api/locations",tags=["Locations"])
LOCATIONS=["Woodward","Atkins","Mebane","Grainger","Friday","Science Hall","Campus Center","Library"]

@router.get("")
def list_locations():
    return LOCATIONS

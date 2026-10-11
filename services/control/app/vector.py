"""Validation helpers shared by the control plane and vector builder."""
import math

def vector_id(area_id):
    if not isinstance(area_id,str):raise ValueError("Invalid area ID")
    clean="".join(c for c in area_id.lower() if c.isalnum() or c in "-_")
    if not clean or len(clean)>80:raise ValueError("Invalid area ID")
    return "area-"+clean

def bbox_text(bbox):
    if not isinstance(bbox,(list,tuple)) or len(bbox)!=4:raise ValueError("Invalid build bbox")
    if not all(isinstance(v,(int,float)) and math.isfinite(v) for v in bbox):raise ValueError("Invalid build bbox")
    west,south,east,north=map(float,bbox)
    if not (-180<=west<east<=180 and -85.05112878<=south<north<=85.05112878):raise ValueError("Invalid build bbox")
    return ",".join(str(v) for v in (west,south,east,north))

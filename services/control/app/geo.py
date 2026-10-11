"""Geometry validation and bounded Web Mercator tile enumeration."""
import math

def geometry(value):
    if value.get("type") == "Feature":
        value = value.get("geometry") or {}
    kind = value.get("type")
    coords = value.get("coordinates")
    if kind not in ("Polygon", "MultiPolygon") or not isinstance(coords, list):
        raise ValueError("Polygon or MultiPolygon required")
    polygons = [coords] if kind == "Polygon" else coords
    if not polygons or len(polygons) > 100:
        raise ValueError("Invalid polygon count")
    vertices = 0
    bounds = [180., 90., -180., -90.]
    for poly in polygons:
        if not poly or len(poly) > 100:
            raise ValueError("Invalid rings")
        for ring in poly:
            if len(ring) < 4 or ring[0] != ring[-1]:
                raise ValueError("Rings must be closed and have at least four vertices")
            vertices += len(ring)
            for pair in ring:
                if not isinstance(pair, (list, tuple)) or len(pair) < 2:
                    raise ValueError("Invalid coordinate")
                lon, lat = pair[:2]
                if not all(isinstance(n, (int, float)) and math.isfinite(n) for n in (lon, lat)):
                    raise ValueError("Invalid coordinate")
                if not (-180 <= lon <= 180 and -85.05112878 <= lat <= 85.05112878):
                    raise ValueError("Coordinates outside supported Mercator range")
                bounds = [min(bounds[0], lon), min(bounds[1], lat),
                          max(bounds[2], lon), max(bounds[3], lat)]
    if vertices > 20000:
        raise ValueError("Too many vertices")
    return value, bounds

def point_in_ring(x, y, ring):
    inside = False
    for i in range(len(ring)-1):
        x1,y1 = ring[i][:2]
        x2,y2 = ring[i+1][:2]
        if (y1 > y) != (y2 > y) and x < (x2-x1)*(y-y1)/(y2-y1)+x1:
            inside = not inside
    return inside

def contains(lon, lat, geom):
    polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
    return any(point_in_ring(lon,lat,p[0]) and not any(point_in_ring(lon,lat,hole) for hole in p[1:]) for p in polys)

def tile_bounds(z,x,y):
    n=2**z
    def lon(a): return a/n*360-180
    def lat(a): return math.degrees(math.atan(math.sinh(math.pi*(1-2*a/n))))
    return lon(x),lat(y+1),lon(x+1),lat(y)

def tile_range(bounds,z):
    n=2**z
    def xx(lon): return max(0,min(n-1,int((lon+180)/360*n)))
    def yy(lat): return max(0,min(n-1,int((1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*n)))
    return xx(bounds[0]),xx(bounds[2]),yy(bounds[3]),yy(bounds[1])

def tiles(geom, min_zoom, max_zoom, limit=30000):
    _, bounds=geometry(geom)
    if not 0 <= min_zoom <= max_zoom <= 18:
        raise ValueError("Zoom range must be between 0 and 18")
    count=0
    for z in range(min_zoom,max_zoom+1):
        x0,x1,y0,y1=tile_range(bounds,z)
        for x in range(x0,x1+1):
            for y in range(y0,y1+1):
                west,south,east,north=tile_bounds(z,x,y)
                center=((west+east)/2,(south+north)/2)
                corners=((west,south),(west,north),(east,south),(east,north))
                # Conservative intersection: cache any tile whose center/corner lies in area.
                # Edge-only intersections may be omitted; full polygon intersection is future work.
                if contains(*center,geom) or any(contains(*p,geom) for p in corners):
                    count+=1
                    if count>limit: raise ValueError("Tile limit exceeded")
                    yield z,x,y

"""Small safe OGC GetCapabilities probe (no XML entity expansion)."""
from urllib.parse import urlencode,urlparse
import httpx
from defusedxml import ElementTree
from .network import validate_url

def request_url(url,kind):
    if kind not in ("wms","wmts","wfs"):raise ValueError("Not an OGC service")
    parsed=urlparse(url)
    if kind=="wmts" and parsed.path.lower().endswith(".xml"):return url
    params=urlencode({"SERVICE":kind.upper(),"REQUEST":"GetCapabilities"})
    return url+("&" if "?" in url else "?")+params

def capabilities(url,kind):
    validate_url(url);target=request_url(url,kind)
    with httpx.Client(timeout=15,follow_redirects=False,trust_env=False) as client:
        response=client.get(target);response.raise_for_status()
        if len(response.content)>2_000_000:raise ValueError("Capabilities too large")
    root=ElementTree.fromstring(response.content);title=None;layers=[]
    for node in root.iter():
        tag=node.tag.rsplit("}",1)[-1]
        if tag=="Title" and title is None and node.text:title=node.text.strip()
        if tag in ("Layer","FeatureType"):
            name=next((c.text.strip() for c in node if c.tag.rsplit("}",1)[-1] in ("Name","Identifier") and c.text),None)
            if name and len(layers)<100:layers.append(name)
    return {"title":title,"layers":layers,"service":kind}

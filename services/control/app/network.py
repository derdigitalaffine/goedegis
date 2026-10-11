"""Restricted external HTTP fetching for administrator-configured sources."""
import ipaddress,socket
from pathlib import Path
from urllib.parse import urlparse
import httpx

def validate_url(url):
    parsed=urlparse(url)
    if parsed.scheme not in ("https","http") or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Only plain HTTP(S) source URLs are supported")
    for item in socket.getaddrinfo(parsed.hostname,parsed.port or (443 if parsed.scheme=="https" else 80),type=socket.SOCK_STREAM):
        if not ipaddress.ip_address(item[4][0]).is_global:
            raise ValueError("Source resolves to a non-public address")
    return url

def get(url,params=None,max_bytes=10_000_000,timeout=30):
    validate_url(url)
    with httpx.Client(timeout=timeout,follow_redirects=False,trust_env=False) as client:
        with client.stream("GET",url,params=params) as r:
            r.raise_for_status()
            if r.is_redirect:raise ValueError("Redirects are not permitted")
            result=bytearray()
            for chunk in r.iter_bytes():
                result.extend(chunk)
                if len(result)>max_bytes:raise ValueError("Response too large")
            return bytes(result),r.headers.get("content-type","")

def download_to(url,target,max_bytes=8_000_000_000,timeout=1800,progress=lambda current,total:None,cancelled=lambda:False):
    """Stream an external file to a temporary sibling and atomically replace target."""
    validate_url(url);target=Path(target);target.parent.mkdir(parents=True,exist_ok=True);tmp=target.with_suffix(target.suffix+".partial")
    written=0
    try:
        with httpx.Client(timeout=timeout,follow_redirects=False,trust_env=False) as client:
            with client.stream("GET",url) as r:
                r.raise_for_status()
                if r.is_redirect:raise ValueError("Redirects are not permitted")
                declared=int(r.headers.get("content-length") or 0)
                if declared and declared>max_bytes:raise ValueError("Response too large")
                with tmp.open("wb") as out:
                    for chunk in r.iter_bytes(1024*1024):
                        if cancelled():raise InterruptedError("Download cancelled")
                        written+=len(chunk)
                        if written>max_bytes:raise ValueError("Response too large")
                        out.write(chunk);progress(written,declared)
        if written==0:raise ValueError("Empty download")
        tmp.replace(target);return written
    except Exception:
        tmp.unlink(missing_ok=True);raise

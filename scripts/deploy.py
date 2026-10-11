#!/usr/bin/env python3
"""Goedegis ncurses deployment and maintenance console."""
import curses, os, shutil, socket, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILES = ["core", "database", "jobs", "tiles", "geocoding", "routing", "ogc", "monitoring"]

def run(*args):
    return subprocess.run(args, cwd=ROOT, text=True, capture_output=True)

def ensure_env():
    env = ROOT / ".env"
    if not env.exists():
        import secrets
        text = (ROOT / ".env.example").read_text()
        for key in ("POSTGRES_PASSWORD", "NOMINATIM_PASSWORD", "GEOSERVER_ADMIN_PASSWORD"):
            import re
            text = re.sub(r"(?m)^" + key + r"=.*$", key + "=" + secrets.token_urlsafe(32), text)
        env.write_text(text)
        env.chmod(0o600)
    return env

def read_profiles():
    env = ensure_env()
    for line in env.read_text().splitlines():
        if line.startswith("COMPOSE_PROFILES="):
            return [x for x in line.split("=", 1)[1].split(",") if x]
    return ["core"]

def write_profiles(profiles):
    env = ensure_env()
    lines = [x for x in env.read_text().splitlines() if not x.startswith("COMPOSE_PROFILES=")]
    lines.append("COMPOSE_PROFILES=" + ",".join(profiles))
    env.write_text("\n".join(lines) + "\n")
    env.chmod(0o600)

def menu(stdscr, heading, items):
    cursor = 0
    while True:
        stdscr.erase()
        h,w = stdscr.getmaxyx()
        stdscr.addnstr(1,2,heading,max(1,w-4),curses.A_BOLD)
        stdscr.addnstr(3,2,"Pfeiltasten: Auswahl   Enter: Bestätigen   q: Zurück",max(1,w-4))
        for i,item in enumerate(items):
            if 5+i >= h-1: break
            stdscr.addnstr(5+i,2,("▶ " if i==cursor else "  ")+item,max(1,w-4),curses.A_REVERSE if i==cursor else 0)
        stdscr.refresh()
        key=stdscr.getch()
        if key in (ord("q"),27): return None
        if key in (curses.KEY_UP,ord("k")):cursor=(cursor-1)%len(items)
        if key in (curses.KEY_DOWN,ord("j")):cursor=(cursor+1)%len(items)
        if key in (10,13,curses.KEY_ENTER):return cursor

def output(stdscr, title, content):
    stdscr.erase()
    h,w=stdscr.getmaxyx()
    stdscr.addnstr(0,0,title,max(1,w-1),curses.A_BOLD)
    for i,line in enumerate(content.splitlines()[:max(0,h-3)]):
        stdscr.addnstr(i+2,0,line,max(1,w-1))
    stdscr.addnstr(h-1,0,"Beliebige Taste drücken",max(1,w-1))
    stdscr.refresh()
    stdscr.getch()

def app(stdscr):
    curses.curs_set(0)
    ensure_env()
    while True:
        selected=read_profiles()
        options=["Module auswählen","Installation / Start","Stoppen","Status","Logs (letzte 100 Zeilen)","Docker-Diagnose","Beenden"]
        choice=menu(stdscr,"GOEDEGIS · LAN GIS Control Center",options)
        if choice is None or choice==6:break
        if choice==0:
            while True:
                items=[("[x] " if p in selected else "[ ] ")+p for p in PROFILES]+["Fertig"]
                x=menu(stdscr,"Module umschalten",items)
                if x is None or x==len(PROFILES):break
                p=PROFILES[x]
                if p in selected:selected.remove(p)
                else:selected.append(p)
                if "jobs" in selected and "database" not in selected:selected.append("database")
                if "core" not in selected:selected.append("core")
                write_profiles(selected)
        elif choice==5:
            d=run("docker","compose","version")
            output(stdscr,"Diagnose","Docker: "+str(shutil.which("docker"))+"\nCompose: "+d.stdout+d.stderr+"\nIP: "+socket.gethostname()+"\nFreier Speicher: "+str(shutil.disk_usage(ROOT).free//(1024**3))+" GiB")
        else:
            if not shutil.which("docker"):
                output(stdscr,"Fehler","Docker nicht gefunden. Bitte Docker Engine + Compose Plugin installieren.")
                continue
            cmd={1:["up","-d","--build"],2:["down"],3:["ps"],4:["logs","--tail","100"]}[choice]
            result=run("docker","compose",*cmd)
            output(stdscr,"Docker Compose: "+" ".join(cmd),result.stdout+"\n"+result.stderr+"\nExit-Code: "+str(result.returncode))

if __name__=="__main__":
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        sys.exit("Interaktives Terminal erforderlich")
    curses.wrapper(app)

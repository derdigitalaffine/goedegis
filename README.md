# Goedegis

Modulare offlinefähige GIS-Plattform für das LAN. **Status: frühes Grundgerüst, keine vollständige GIS-Implementierung.**

## Start

```bash
cp .env.example .env
# Starkes POSTGRES_PASSWORD in .env setzen
docker compose --profile core --profile database up -d
```

Web: http://<LAN-IP>:8080. Derzeit nur responsive Platzhalteroberfläche.

## Verbindlicher Umfang (19 Entscheidungen)

Offline-LAN; mehrere Gebiete; grafischer Gebietseditor; inkrementelle OSM-Updates; Multi-Level-Cache/Prewarming; Mehrprofil-Routing; WMS/WMTS/WFS-Manager; Nominatim und POI-Suche; visueller Stil-/Layereditor; grafischer Quellen-/Sync-Manager; Ressourcen-Dashboard; ncurses-Control-Center; responsives HTTP-Frontend; native GIS-APIs; zentraler Job-Manager; modulare Compose-Profile.

Nicht gewünscht: Benutzerverwaltung, automatische Backups, PWA, zusätzliche REST-Gateway-API oder eigener Geodatenimport.

## Implementiert

Compose-Grundgerüst mit HTTP-Webserver (Profil core), persistentem PostGIS (Profil database), .env-Vorlage und responsiver Platzhalteroberfläche.

## Noch nicht implementiert

MapLibre-Karte, OSM-Kartenserver, Nominatim, Routing, OGC-Cache, Sync, Queue, Monitoring und ncurses.

## Sicherheit

Ohne Authentifizierung muss der administrative Webzugriff auf ein vertrauenswürdiges LAN begrenzt werden. HTTP ist unverschlüsselt. PostgreSQL veröffentlicht keinen Host-Port. Externe Datenquellen können Caching- und Nutzungsbeschränkungen haben.

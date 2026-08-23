from __future__ import annotations

from html import escape

from fastapi import Depends, Header, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from . import main


ROUTINEHUB_PAGE = "https://routinehub.co/shortcut/21697/"
ROUTINEHUB_DOWNLOAD = "https://routinehub.co/download/59565/?t=eyJ2Ijo1OTU2NX0:1wy3IN:uAgosFteGGum_57LQ3Io47B7f9unHbYNOx73Etz23pQ"

_original_layout = main._layout


def _layout_with_guides(title: str, body: str, user: main.User | None = None) -> str:
    html = _original_layout(title, body, user)
    if user and "href='/guides'" not in html:
        html = html.replace(
            "<a href='/devices'>Geräte / API</a>",
            "<a href='/devices'>Geräte / API</a><a href='/guides'>Anleitungen</a>",
        )
    return html


main._layout = _layout_with_guides


def _endpoint(request: Request) -> str:
    return f"{str(request.base_url).rstrip('/')}/api/v1/me/next"


@main.app.get("/guides", response_class=HTMLResponse)
def guides_page(
    request: Request,
    user: main.User = Depends(main.current_user),
):
    endpoint = escape(_endpoint(request))
    body = f"""
<section>
  <h2>Smartphone-Wecker – ausführliche Anleitung für Anfänger</h2>
  <p>Alarm-HUB verwaltet deine Weckzeiten auf dem Server. Damit dein Smartphone wirklich klingelt, muss dein iPhone oder Android-Gerät den nächsten Wecker von Alarm-HUB abrufen und anschließend einen lokalen Wecker in der Uhr-App anlegen.</p>

  <div class='card'>
    <h3>Bevor du beginnst</h3>
    <ol>
      <li>Erstelle in Alarm-HUB mindestens einen manuellen Wecker oder stelle sicher, dass über WebComm bereits kommende Wecker vorhanden sind.</li>
      <li>Öffne <a href='/devices'>Geräte / API</a>.</li>
      <li>Gib als Gerätenamen z. B. <b>Mein iPhone</b> oder <b>Mein Android</b> ein.</li>
      <li>Klicke auf <b>Token erzeugen</b>.</li>
      <li>Kopiere das angezeigte Token sofort. Es wird nur einmal vollständig angezeigt.</li>
      <li>Behandle das Token wie ein Passwort und teile es nicht öffentlich.</li>
    </ol>
  </div>

  <div class='card'>
    <h3>Alarm-HUB API</h3>
    <p><code>{endpoint}</code></p>
    <p>Für die Abfrage wird zusätzlich folgender HTTP-Header benötigt:</p>
    <p><code>Authorization: Bearer DEIN_TOKEN</code></p>
    <p class='muted'>Zwischen <code>Bearer</code> und dem Token steht genau ein Leerzeichen.</p>
  </div>

  <div class='card'>
    <h3>Beispielantwort</h3>
    <pre><code>{{
  "ok": true,
  "timezone": "Europe/Berlin",
  "alarm": {{
    "name": "Frühschicht",
    "date": "24.08.2026",
    "time": "04:34",
    "source": "webcomm"
  }}
}}</code></pre>
    <p>Für den Smartphone-Wecker sind vor allem <code>alarm.time</code> und <code>alarm.name</code> wichtig.</p>
  </div>

  <p><b>Netzwerk-Hinweis:</b> Wenn Alarm-HUB nur im Heimnetz erreichbar ist, funktioniert die Synchronisation unterwegs nur über VPN. Für direkten Internetzugriff sollte Alarm-HUB ausschließlich über HTTPS hinter einem korrekt konfigurierten Reverse Proxy bereitgestellt werden.</p>
</section>

<section id='ios'>
  <h2>iOS / iPhone</h2>

  <div class='card'>
    <h3>Empfohlen – fertigen Alarm-HUB-Kurzbefehl installieren</h3>
    <p>Für iPhone-Nutzer steht ein fertiger Alarm-HUB-Kurzbefehl über RoutineHub bereit. Damit musst du die komplette Kurzbefehle-Logik nicht selbst nachbauen.</p>
    <p class='row'>
      <a href='{ROUTINEHUB_DOWNLOAD}' target='_blank' rel='noopener noreferrer'><button type='button'>📲 Kurzbefehl direkt installieren</button></a>
      <a href='{ROUTINEHUB_PAGE}' target='_blank' rel='noopener noreferrer'><button type='button'>🔗 RoutineHub-Seite öffnen</button></a>
    </p>
    <p class='muted'>Falls der Direktdownload später nicht mehr funktioniert, öffne die RoutineHub-Seite und installiere dort die aktuelle Version.</p>
  </div>

  <div class='card'>
    <h3>Nach der Installation – Schritt für Schritt</h3>
    <ol>
      <li>Tippe oben auf <b>Kurzbefehl direkt installieren</b> oder öffne die RoutineHub-Seite.</li>
      <li>Bestätige auf dem iPhone, dass der Kurzbefehl in der App <b>Kurzbefehle</b> geöffnet bzw. hinzugefügt werden soll.</li>
      <li>Öffne anschließend den importierten Alarm-HUB-Kurzbefehl in <b>Kurzbefehle</b>.</li>
      <li>Öffne in Alarm-HUB <a href='/devices'>Geräte / API</a> und erzeuge ein Geräte-Token, falls noch keines für dein iPhone vorhanden ist.</li>
      <li>Trage im Kurzbefehl die Adresse deiner eigenen Alarm-HUB-Installation ein. Für diese Installation lautet der API-Endpunkt:<br><code>{endpoint}</code></li>
      <li>Trage dein persönliches Geräte-Token an der dafür vorgesehenen Stelle ein. Das Token darf nicht öffentlich geteilt werden.</li>
      <li>Starte den Kurzbefehl zunächst <b>einmal manuell</b>.</li>
      <li>Erlaube erforderliche Berechtigungen für Netzwerkzugriff und die Uhr-/Wecker-Funktionen, falls iOS danach fragt.</li>
      <li>Öffne danach die App <b>Uhr</b> → <b>Wecker</b> und prüfe, ob der Alarm-HUB-Wecker mit der erwarteten Uhrzeit angelegt wurde.</li>
      <li>Öffne anschließend in Alarm-HUB <a href='/devices'>Geräte / API</a>. Beim iPhone-Token sollte unter <b>zuletzt benutzt</b> eine aktuelle Zeit stehen.</li>
    </ol>
  </div>

  <div class='card'>
    <h3>Automatische Ausführung auf dem iPhone</h3>
    <ol>
      <li>Öffne die App <b>Kurzbefehle</b>.</li>
      <li>Wechsle unten zu <b>Automation</b>.</li>
      <li>Tippe auf <b>+</b> bzw. <b>Neue Automation</b>.</li>
      <li>Wähle <b>Tageszeit</b>.</li>
      <li>Lege eine Uhrzeit fest, zu der Alarm-HUB regelmäßig abgefragt werden soll.</li>
      <li>Wähle <b>Täglich</b>.</li>
      <li>Aktiviere, sofern deine iOS-Version diese Auswahl anbietet, <b>Sofort ausführen</b>.</li>
      <li>Wähle als Aktion <b>Kurzbefehl ausführen</b>.</li>
      <li>Wähle den installierten Alarm-HUB-Kurzbefehl.</li>
      <li>Speichere die Automation und führe danach einmal einen manuellen Test durch.</li>
    </ol>
  </div>

  <details>
    <summary><b>Manuelle Einrichtung – falls du den Kurzbefehl selbst bauen möchtest</b></summary>

    <div class='card'>
      <h3>Teil 1 – Neuen Kurzbefehl anlegen</h3>
      <ol>
        <li>Öffne auf dem iPhone die App <b>Kurzbefehle</b>.</li>
        <li>Tippe oben rechts auf <b>+</b>.</li>
        <li>Benenne den neuen Kurzbefehl in <b>Alarm-HUB Sync</b> um.</li>
        <li>Tippe auf <b>Aktion hinzufügen</b>.</li>
      </ol>
    </div>

    <div class='card'>
      <h3>Teil 2 – Alarm-HUB abfragen</h3>
      <ol>
        <li>Füge die Aktion <b>URL</b> hinzu.</li>
        <li>Trage <code>{endpoint}</code> ein.</li>
        <li>Füge darunter <b>Inhalte von URL abrufen</b> hinzu.</li>
        <li>Stelle die Methode auf <b>GET</b>.</li>
        <li>Füge den Header <code>Authorization</code> hinzu.</li>
        <li>Als Wert verwendest du <code>Bearer DEIN_TOKEN</code> und ersetzt <code>DEIN_TOKEN</code> durch dein Geräte-Token.</li>
      </ol>
    </div>

    <div class='card'>
      <h3>Teil 3 – Verbindung testen</h3>
      <ol>
        <li>Führe den Kurzbefehl einmal aus.</li>
        <li>Erlaube den Netzwerkzugriff, falls iOS danach fragt.</li>
        <li>Prüfe in Alarm-HUB unter <a href='/devices'>Geräte / API</a>, ob das Token nun als zuletzt benutzt angezeigt wird.</li>
        <li>Falls nicht, prüfe URL, WLAN/VPN, Token und Authorization-Header.</li>
      </ol>
    </div>

    <div class='card'>
      <h3>Teil 4 – Weckerdaten auslesen</h3>
      <ol>
        <li>Füge nach <b>Inhalte von URL abrufen</b> die Aktion <b>Wörterbuchwert abrufen</b> hinzu.</li>
        <li>Verwende als Schlüssel <code>alarm</code>.</li>
        <li>Aus diesem Wörterbuch liest du anschließend den Schlüssel <code>time</code>.</li>
        <li>Der Wert hat das Format <code>HH:MM</code>, z. B. <code>04:34</code>.</li>
        <li>Lies zusätzlich aus <code>alarm</code> den Schlüssel <code>name</code> aus.</li>
      </ol>
    </div>

    <div class='card'>
      <h3>Teil 5 – Uhrzeit zerlegen und Wecker erstellen</h3>
      <ol>
        <li>Teile den Wert aus <code>time</code> mit <b>Text teilen</b> am Doppelpunkt <code>:</code>.</li>
        <li>Element 1 ist die Stunde, Element 2 die Minute.</li>
        <li>Füge die Uhr-/Wecker-Aktion zum Erstellen eines neuen Weckers hinzu.</li>
        <li>Verwende Stunde und Minute aus den zuvor gelesenen Werten.</li>
        <li>Als Bezeichnung kannst du <b>Alarm-HUB –</b> gefolgt von <code>name</code> verwenden.</li>
        <li>Führe den Kurzbefehl erneut aus und kontrolliere den Wecker in der Apple-Uhr-App.</li>
      </ol>
    </div>
  </details>

  <div class='card'>
    <h3>Doppelte iPhone-Wecker vermeiden</h3>
    <p>Wenn eine selbst erstellte Automation den Wecker bei jedem Lauf neu anlegt, können Duplikate entstehen. Der bereitgestellte RoutineHub-Kurzbefehl ist deshalb die empfohlene Variante. Bei eigenen Kurzbefehlen solltest du vorhandene Alarm-HUB-Wecker vor dem erneuten Anlegen suchen, vergleichen oder entfernen.</p>
  </div>
</section>

<section id='android'>
  <h2>Android – Schritt für Schritt mit MacroDroid</h2>
  <p>Da Android keine einheitliche vorinstallierte Automations-App besitzt, verwendet diese Anleitung <b>MacroDroid</b>. Je nach Gerätehersteller und MacroDroid-Version können Menünamen etwas anders aussehen.</p>

  <div class='card'>
    <h3>Teil 1 – MacroDroid vorbereiten</h3>
    <ol>
      <li>Installiere MacroDroid aus dem offiziellen App-Store deines Geräts.</li>
      <li>Öffne MacroDroid.</li>
      <li>Erlaube die grundlegenden Berechtigungen, die MacroDroid für Automationen benötigt.</li>
      <li>Erstelle ein neues Makro und nenne es <b>Alarm-HUB Sync</b>.</li>
    </ol>
  </div>

  <div class='card'>
    <h3>Teil 2 – Auslöser festlegen</h3>
    <ol>
      <li>Öffne im neuen Makro den Bereich <b>Trigger / Auslöser</b>.</li>
      <li>Wähle einen zeitgesteuerten Trigger, z. B. <b>Tag/Uhrzeit</b>.</li>
      <li>Stelle eine Uhrzeit ein, zu der dein Smartphone Alarm-HUB abfragen soll.</li>
      <li>Für den Anfang reicht einmal täglich. Bei häufigen Änderungen kann später eine zweite Ausführung ergänzt werden.</li>
    </ol>
  </div>

  <div class='card'>
    <h3>Teil 3 – HTTP-Abfrage erstellen</h3>
    <ol>
      <li>Öffne den Bereich <b>Aktionen</b>.</li>
      <li>Füge eine <b>HTTP Request</b>- bzw. <b>HTTP-Anfrage</b>-Aktion hinzu.</li>
      <li>Stelle die Methode auf <b>GET</b>.</li>
      <li>Als URL verwendest du <code>{endpoint}</code>.</li>
      <li>Füge den Header <code>Authorization</code> hinzu.</li>
      <li>Als Wert verwendest du <code>Bearer DEIN_TOKEN</code>.</li>
      <li>Ersetze <code>DEIN_TOKEN</code> durch dein zuvor erzeugtes Android-Geräte-Token.</li>
      <li>Speichere die HTTP-Antwort in einer Textvariable, z. B. <code>alarmhub_response</code>.</li>
    </ol>
  </div>

  <div class='card'>
    <h3>Teil 4 – Verbindung testen</h3>
    <ol>
      <li>Starte das Makro einmal manuell.</li>
      <li>Öffne anschließend Alarm-HUB → <a href='/devices'>Geräte / API</a>.</li>
      <li>Beim Android-Token sollte <b>zuletzt benutzt</b> eine aktuelle Zeit anzeigen.</li>
      <li>Wenn MacroDroid einen HTTP-Status anzeigt, sollte Alarm-HUB mit <b>200</b> antworten.</li>
      <li>Ein Fehler <b>401</b> weist normalerweise auf ein falsches Token oder einen falschen Authorization-Header hin.</li>
    </ol>
  </div>

  <div class='card'>
    <h3>Teil 5 – JSON-Daten lesen</h3>
    <ol>
      <li>Die HTTP-Antwort enthält JSON.</li>
      <li>Lies <code>alarm.time</code> aus und speichere den Wert z. B. in <code>alarm_time</code>.</li>
      <li>Lies <code>alarm.name</code> aus und speichere den Wert z. B. in <code>alarm_name</code>.</li>
      <li>Wenn <code>alarm</code> den Wert <code>null</code> hat, gibt es aktuell keinen kommenden Wecker. Beende das Makro dann ohne neuen Wecker.</li>
    </ol>
  </div>

  <div class='card'>
    <h3>Teil 6 – Stunde und Minute trennen</h3>
    <ol>
      <li><code>alarm_time</code> hat das Format <code>HH:MM</code>.</li>
      <li>Teile den Text am Doppelpunkt <code>:</code>.</li>
      <li>Der erste Teil ist die Stunde, der zweite die Minute.</li>
      <li>Speichere beide Werte z. B. als <code>alarm_hour</code> und <code>alarm_minute</code>.</li>
    </ol>
  </div>

  <div class='card'>
    <h3>Teil 7 – Android-Wecker anlegen</h3>
    <ol>
      <li>Füge eine Aktion zum <b>Wecker setzen</b> bzw. eine passende Alarm-Clock-Aktion hinzu.</li>
      <li>Verwende <code>alarm_hour</code> als Stunde und <code>alarm_minute</code> als Minute.</li>
      <li>Als Beschriftung verwendest du <b>Alarm-HUB –</b> gefolgt von <code>alarm_name</code>.</li>
      <li>Falls keine direkte Wecker-Aktion verfügbar ist, verwende die Android-Intent-/Alarm-Clock-Funktion.</li>
      <li>Speichere das Makro.</li>
    </ol>
  </div>

  <div class='card'>
    <h3>Teil 8 – Berechtigungen</h3>
    <ol>
      <li>Führe das Makro manuell aus.</li>
      <li>Erlaube die Berechtigung zum Setzen von Weckern, falls Android danach fragt.</li>
      <li>Bei eingeschränkter Hintergrundausführung öffne Android-Einstellungen → Apps → MacroDroid → Akku.</li>
      <li>Setze MacroDroid bei Bedarf auf <b>Nicht eingeschränkt</b> bzw. deaktiviere die Akku-Optimierung.</li>
      <li>Einige Hersteller benötigen zusätzlich eine Autostart-/Hintergrundberechtigung.</li>
    </ol>
  </div>

  <div class='card'>
    <h3>Teil 9 – Funktion prüfen</h3>
    <ol>
      <li>Starte <b>Alarm-HUB Sync</b> manuell.</li>
      <li>Öffne danach deine Android-Uhr-App.</li>
      <li>Prüfe Uhrzeit und Beschriftung des Weckers.</li>
      <li>Kontrolliere in Alarm-HUB unter <a href='/devices'>Geräte / API</a>, ob das Token zuletzt benutzt wurde.</li>
      <li>Wenn diese Punkte stimmen, ist die Einrichtung erfolgreich.</li>
    </ol>
  </div>

  <div class='card'>
    <h3>Doppelte Android-Wecker vermeiden</h3>
    <p>Je nach Uhr-App kann jedes Ausführen des Makros einen weiteren Wecker anlegen. Für Anfänger empfiehlt sich zunächst eine feste Synchronisation pro Tag. Später kann das Makro vorhandene Alarm-HUB-Wecker vor dem Anlegen entfernen oder vergleichen.</p>
  </div>
</section>

<section>
  <h2>Fehlersuche</h2>
  <div class='card'>
    <h3>Das Token zeigt „noch nie benutzt“</h3>
    <p>Dann erreicht das Smartphone Alarm-HUB nicht erfolgreich. Prüfe URL, WLAN/VPN, HTTPS bzw. Reverse Proxy und den Header <code>Authorization: Bearer ...</code>.</p>
  </div>
  <div class='card'>
    <h3>HTTP 401 / Ungültiges Token</h3>
    <p>Erzeuge unter <a href='/devices'>Geräte / API</a> bei Bedarf ein neues Token und trage es erneut ein. Achte auf das Leerzeichen nach <code>Bearer</code>.</p>
  </div>
  <div class='card'>
    <h3>Die API funktioniert, aber kein Wecker wird erstellt</h3>
    <p>Prüfe, ob <code>alarm.time</code> korrekt gelesen wird und ob Kurzbefehle bzw. MacroDroid die nötige Berechtigung zum Erstellen von Weckern besitzen.</p>
  </div>
  <div class='card'>
    <h3>Es gibt keinen kommenden Wecker</h3>
    <p>Öffne in Alarm-HUB das Dashboard oder <a href='/alarms'>Meine Wecker</a>. Wenn kein zukünftiger Wecker vorhanden ist, liefert die API <code>alarm: null</code>. Das ist kein Fehler.</p>
  </div>
  <p class='muted'>Die Smartphone-Automation verwendet immer den aktuell nächsten bekannten Wecker. Änderungen an manuellen Weckern oder WebComm-Schichten werden beim nächsten erfolgreichen Sync berücksichtigt.</p>
</section>
"""
    return HTMLResponse(main._layout("Anleitungen", body, user))


@main.app.get("/api/v1/me/next")
def next_alarm_api(
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(main.db_session),
):
    if authorization:
        user = main._token_user(authorization, db, main.DeviceToken)
    else:
        user = main.current_user(request, db)
    alarms = main._upcoming(user, db, 1)
    return {
        "ok": True,
        "timezone": user.timezone,
        "alarm": alarms[0] if alarms else None,
    }

from __future__ import annotations

from html import escape

from fastapi import Depends, Header, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from . import main


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
      <li>Gib als Namen z. B. <b>Mein iPhone</b> oder <b>Mein Android</b> ein.</li>
      <li>Klicke auf <b>Token erzeugen</b>.</li>
      <li>Kopiere das angezeigte Token sofort und speichere es vorübergehend sicher. Es wird nur ein einziges Mal vollständig angezeigt.</li>
      <li>Behandle dieses Token wie ein Passwort. Wer das Token kennt, kann deine kommenden Wecker über die API abrufen.</li>
    </ol>
  </div>
  <div class='card'>
    <h3>Diese Adresse brauchst du später</h3>
    <p><code>{endpoint}</code></p>
    <p>Alarm-HUB erwartet zusätzlich den HTTP-Header:</p>
    <p><code>Authorization: Bearer DEIN_TOKEN</code></p>
    <p class='muted'>Das Wort <code>Bearer</code>, danach genau ein Leerzeichen und anschließend dein Token.</p>
  </div>
  <div class='card'>
    <h3>Was die API zurückgibt</h3>
    <p>Wenn ein Wecker vorhanden ist, sieht die Antwort sinngemäß so aus:</p>
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
    <p>Für die Smartphone-Einrichtung benötigen wir hauptsächlich <code>alarm.time</code> und <code>alarm.name</code>.</p>
  </div>
  <p><b>Netzwerk-Hinweis:</b> Wenn Alarm-HUB nur im Heimnetz erreichbar ist, funktioniert die Synchronisation unterwegs nur über VPN. Für direkten Internetzugriff solltest du Alarm-HUB ausschließlich über HTTPS hinter einem korrekt konfigurierten Reverse Proxy bereitstellen.</p>
</section>

<section id='ios'>
  <h2>iOS / iPhone – Schritt für Schritt mit Kurzbefehle</h2>
  <p>Diese Variante verwendet ausschließlich die Apple-App <b>Kurzbefehle</b>. Je nach iOS-Version können einzelne Aktionsnamen geringfügig anders heißen.</p>

  <div class='card'>
    <h3>Teil 1 – Neuen Kurzbefehl anlegen</h3>
    <ol>
      <li>Öffne auf deinem iPhone die App <b>Kurzbefehle</b>.</li>
      <li>Tippe oben rechts auf das <b>+</b>.</li>
      <li>Tippe oben auf <b>Neuer Kurzbefehl</b> und anschließend auf <b>Umbenennen</b>.</li>
      <li>Nenne den Kurzbefehl <b>Alarm-HUB Sync</b>.</li>
      <li>Tippe auf <b>Aktion hinzufügen</b>.</li>
    </ol>
  </div>

  <div class='card'>
    <h3>Teil 2 – Alarm-HUB-Adresse eintragen</h3>
    <ol>
      <li>Suche nach der Aktion <b>URL</b> und füge sie hinzu.</li>
      <li>Tippe in das URL-Feld.</li>
      <li>Trage exakt diese Adresse ein:<br><code>{endpoint}</code></li>
      <li>Füge darunter die Aktion <b>Inhalte von URL abrufen</b> hinzu.</li>
      <li>Öffne in dieser Aktion die erweiterten Optionen bzw. <b>Mehr anzeigen</b>.</li>
      <li>Stelle die Methode auf <b>GET</b>.</li>
    </ol>
  </div>

  <div class='card'>
    <h3>Teil 3 – Geräte-Token als Header eintragen</h3>
    <ol>
      <li>Suche innerhalb der Aktion <b>Inhalte von URL abrufen</b> den Bereich <b>Header</b>.</li>
      <li>Füge einen neuen Header hinzu.</li>
      <li>Als Schlüssel bzw. Name trägst du ein:<br><code>Authorization</code></li>
      <li>Als Wert trägst du ein:<br><code>Bearer DEIN_TOKEN</code></li>
      <li>Ersetze <code>DEIN_TOKEN</code> vollständig durch das Token aus Alarm-HUB.</li>
      <li>Achte darauf, dass zwischen <code>Bearer</code> und deinem Token genau ein Leerzeichen steht.</li>
    </ol>
    <p class='muted'>Das Token niemals in die URL schreiben und niemals öffentlich teilen.</p>
  </div>

  <div class='card'>
    <h3>Teil 4 – Verbindung testen</h3>
    <ol>
      <li>Tippe unten oder oben im Kurzbefehleditor auf die <b>Play-/Ausführen-Taste</b>.</li>
      <li>Beim ersten Zugriff kann iOS nach einer Berechtigung für den Netzwerkzugriff fragen. Erlaube den Zugriff.</li>
      <li>Wenn keine Fehlermeldung erscheint, öffne in Alarm-HUB <a href='/devices'>Geräte / API</a>.</li>
      <li>Bei deinem iPhone-Token sollte bei <b>zuletzt benutzt</b> nun eine aktuelle Uhrzeit stehen.</li>
      <li>Falls dort weiterhin <b>noch nie benutzt</b> steht, prüfe zuerst URL, Token, WLAN/VPN und den Header.</li>
    </ol>
  </div>

  <div class='card'>
    <h3>Teil 5 – Den Bereich <code>alarm</code> aus der Antwort lesen</h3>
    <ol>
      <li>Füge direkt nach <b>Inhalte von URL abrufen</b> die Aktion <b>Wörterbuchwert abrufen</b> / <b>Get Dictionary Value</b> hinzu.</li>
      <li>Als Schlüssel trägst du <code>alarm</code> ein.</li>
      <li>Diese Aktion enthält danach nur noch die Daten des nächsten Weckers.</li>
      <li>Optional kannst du zum Testen kurz die Aktion <b>Schnellvorschau</b> oder <b>Ergebnis anzeigen</b> hinzufügen. Dort sollten Name, Datum und Uhrzeit des nächsten Weckers erscheinen.</li>
      <li>Entferne die Testanzeige anschließend wieder, wenn alles funktioniert.</li>
    </ol>
  </div>

  <div class='card'>
    <h3>Teil 6 – Uhrzeit auslesen</h3>
    <ol>
      <li>Füge eine weitere Aktion <b>Wörterbuchwert abrufen</b> hinzu.</li>
      <li>Verwende als Eingabe den zuvor gelesenen Wert <code>alarm</code>.</li>
      <li>Als Schlüssel trägst du <code>time</code> ein.</li>
      <li>Das Ergebnis sieht z. B. so aus: <code>04:34</code>.</li>
      <li>Füge anschließend die Aktion <b>Text teilen</b> / <b>Split Text</b> hinzu.</li>
      <li>Als Trennzeichen verwendest du einen Doppelpunkt <code>:</code>.</li>
      <li>Du erhältst damit zwei Teile: der erste ist die Stunde, der zweite die Minute.</li>
      <li>Mit <b>Element aus Liste abrufen</b> liest du Element 1 als Stunde und Element 2 als Minute aus.</li>
    </ol>
  </div>

  <div class='card'>
    <h3>Teil 7 – Namen des Weckers auslesen</h3>
    <ol>
      <li>Füge noch einmal <b>Wörterbuchwert abrufen</b> hinzu.</li>
      <li>Verwende wieder das Wörterbuch <code>alarm</code> als Eingabe.</li>
      <li>Als Schlüssel verwendest du <code>name</code>.</li>
      <li>Das Ergebnis ist z. B. <code>Frühschicht</code>.</li>
      <li>Diesen Wert verwenden wir gleich als Beschriftung des iPhone-Weckers.</li>
    </ol>
  </div>

  <div class='card'>
    <h3>Teil 8 – Lokalen iPhone-Wecker erstellen</h3>
    <ol>
      <li>Suche nach einer Uhr-/Wecker-Aktion wie <b>Wecker erstellen</b> bzw. <b>Create Alarm</b>.</li>
      <li>Setze die Weckzeit aus der zuvor ausgelesenen Stunde und Minute zusammen.</li>
      <li>Als Bezeichnung verwendest du z. B. <b>Alarm-HUB –</b> gefolgt vom Wert <code>name</code>.</li>
      <li>Lass die Wiederholung des lokalen Weckers deaktiviert. Alarm-HUB liefert beim nächsten Sync wieder den aktuell nächsten Wecker.</li>
      <li>Führe den Kurzbefehl erneut manuell aus.</li>
      <li>Öffne danach die Apple-App <b>Uhr</b> → <b>Wecker</b>.</li>
      <li>Kontrolliere, ob Uhrzeit und Beschriftung stimmen.</li>
    </ol>
  </div>

  <div class='card'>
    <h3>Teil 9 – Automatisch ausführen lassen</h3>
    <ol>
      <li>Öffne in der App <b>Kurzbefehle</b> unten den Bereich <b>Automation</b>.</li>
      <li>Tippe auf <b>+</b> bzw. <b>Neue Automation</b>.</li>
      <li>Wähle als Auslöser <b>Tageszeit</b>.</li>
      <li>Lege eine Uhrzeit fest, zu der Alarm-HUB regelmäßig abgefragt werden soll, z. B. nachts oder früh morgens.</li>
      <li>Wähle <b>Täglich</b>.</li>
      <li>Wähle, sofern deine iOS-Version dies anbietet, <b>Sofort ausführen</b> und deaktiviere eine unnötige Bestätigungsabfrage.</li>
      <li>Als auszuführende Aktion wählst du <b>Kurzbefehl ausführen</b>.</li>
      <li>Wähle dort <b>Alarm-HUB Sync</b>.</li>
      <li>Speichere die Automation.</li>
      <li>Wenn sich deine Schichten im Tagesverlauf ändern können, kannst du eine zweite Automation zu einer weiteren Tageszeit anlegen.</li>
    </ol>
  </div>

  <div class='card'>
    <h3>Doppelte iPhone-Wecker vermeiden</h3>
    <p>Wenn dieselbe Automation mehrfach läuft, kann iOS denselben Wecker mehrmals anlegen. Für den Einstieg empfiehlt es sich daher, nur ein- oder zweimal täglich zu synchronisieren. Eine spätere erweiterte Variante kann vor dem Erstellen vorhandene Wecker mit der Bezeichnung <b>Alarm-HUB</b> suchen und löschen bzw. abgleichen.</p>
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
      <li>Erstelle ein neues Makro.</li>
      <li>Nenne es <b>Alarm-HUB Sync</b>.</li>
    </ol>
  </div>

  <div class='card'>
    <h3>Teil 2 – Auslöser festlegen</h3>
    <ol>
      <li>Öffne im neuen Makro den Bereich <b>Trigger / Auslöser</b>.</li>
      <li>Wähle einen zeitgesteuerten Trigger, z. B. <b>Tag/Uhrzeit</b> oder eine vergleichbare Zeitplan-Funktion.</li>
      <li>Stelle eine Uhrzeit ein, zu der dein Smartphone Alarm-HUB abfragen soll.</li>
      <li>Für den Anfang reicht einmal täglich.</li>
      <li>Wenn sich deine WebComm-Schichten häufiger ändern, kannst du später eine zweite Ausführung am Tag ergänzen.</li>
    </ol>
  </div>

  <div class='card'>
    <h3>Teil 3 – HTTP-Abfrage an Alarm-HUB erstellen</h3>
    <ol>
      <li>Öffne im Makro den Bereich <b>Aktionen</b>.</li>
      <li>Suche nach einer Aktion wie <b>HTTP Request</b>, <b>HTTP-Anfrage</b> oder <b>Web Request</b>.</li>
      <li>Stelle die Methode auf <b>GET</b>.</li>
      <li>Als URL trägst du exakt ein:<br><code>{endpoint}</code></li>
      <li>Öffne in der HTTP-Aktion den Bereich für zusätzliche <b>Header</b>.</li>
      <li>Füge einen Header mit dem Namen <code>Authorization</code> hinzu.</li>
      <li>Als Wert verwendest du <code>Bearer DEIN_TOKEN</code>.</li>
      <li>Ersetze <code>DEIN_TOKEN</code> mit dem zuvor in Alarm-HUB erzeugten Android-Token.</li>
      <li>Speichere die HTTP-Antwort in einer String-/Textvariable, z. B. <code>alarmhub_response</code>.</li>
    </ol>
  </div>

  <div class='card'>
    <h3>Teil 4 – Verbindung testen</h3>
    <ol>
      <li>Starte das Makro einmal manuell.</li>
      <li>Öffne anschließend Alarm-HUB → <a href='/devices'>Geräte / API</a>.</li>
      <li>Bei deinem Android-Token sollte <b>zuletzt benutzt</b> nun eine aktuelle Zeit anzeigen.</li>
      <li>Falls nicht, prüfe zuerst WLAN/VPN, URL und den Authorization-Header.</li>
      <li>Wenn MacroDroid einen HTTP-Status anzeigt, sollte Alarm-HUB mit <b>200</b> antworten.</li>
      <li>Ein Fehler <b>401</b> bedeutet normalerweise, dass Token oder Authorization-Header nicht stimmen.</li>
    </ol>
  </div>

  <div class='card'>
    <h3>Teil 5 – JSON-Daten aus der Antwort lesen</h3>
    <ol>
      <li>Die HTTP-Antwort enthält JSON.</li>
      <li>Verwende in MacroDroid eine JSON-/Textverarbeitungsaktion oder die verfügbaren JSON-Ausgabevariablen der HTTP-Aktion.</li>
      <li>Lies zuerst <code>alarm.time</code> aus und speichere den Wert z. B. in <code>alarm_time</code>.</li>
      <li>Lies anschließend <code>alarm.name</code> aus und speichere den Wert z. B. in <code>alarm_name</code>.</li>
      <li>Wenn <code>alarm</code> den Wert <code>null</code> hat, gibt es aktuell keinen kommenden Wecker. In diesem Fall soll das Makro beendet werden, ohne einen Wecker anzulegen.</li>
    </ol>
  </div>

  <div class='card'>
    <h3>Teil 6 – Stunde und Minute trennen</h3>
    <ol>
      <li><code>alarm_time</code> hat das Format <code>HH:MM</code>, z. B. <code>04:34</code>.</li>
      <li>Teile den Text am Doppelpunkt <code>:</code>.</li>
      <li>Der erste Teil ist die Stunde.</li>
      <li>Der zweite Teil ist die Minute.</li>
      <li>Speichere beide Werte in Variablen, z. B. <code>alarm_hour</code> und <code>alarm_minute</code>.</li>
    </ol>
  </div>

  <div class='card'>
    <h3>Teil 7 – Android-Wecker anlegen</h3>
    <ol>
      <li>Füge eine Aktion zum <b>Wecker setzen</b>, <b>Alarm setzen</b> oder eine entsprechende Alarm-Clock-Aktion hinzu.</li>
      <li>Verwende <code>alarm_hour</code> als Stunde.</li>
      <li>Verwende <code>alarm_minute</code> als Minute.</li>
      <li>Als Beschriftung verwendest du <b>Alarm-HUB –</b> gefolgt von <code>alarm_name</code>.</li>
      <li>Wenn MacroDroid keine direkte Wecker-Aktion anbietet, verwende die Aktion für einen Android-Intent bzw. die Alarm-Clock-Funktion.</li>
      <li>Speichere das Makro.</li>
    </ol>
  </div>

  <div class='card'>
    <h3>Teil 8 – Android-Berechtigungen richtig setzen</h3>
    <ol>
      <li>Führe das Makro manuell aus.</li>
      <li>Wenn Android nach der Berechtigung zum Setzen von Weckern fragt, erlaube sie.</li>
      <li>Wenn dein Hersteller Hintergrundaktivitäten einschränkt, öffne die Android-Einstellungen → Apps → MacroDroid → Akku.</li>
      <li>Setze MacroDroid dort, falls nötig, auf <b>Nicht eingeschränkt</b> bzw. deaktiviere die Akku-Optimierung.</li>
      <li>Bei Samsung, Xiaomi, Huawei und ähnlichen Geräten kann zusätzlich eine Autostart-/Hintergrundberechtigung erforderlich sein.</li>
    </ol>
  </div>

  <div class='card'>
    <h3>Teil 9 – Funktion prüfen</h3>
    <ol>
      <li>Starte <b>Alarm-HUB Sync</b> einmal manuell.</li>
      <li>Öffne danach deine Android-Uhr-App.</li>
      <li>Prüfe, ob ein neuer Wecker mit der richtigen Uhrzeit vorhanden ist.</li>
      <li>Prüfe außerdem, ob die Beschriftung <b>Alarm-HUB – ...</b> stimmt.</li>
      <li>Kontrolliere in Alarm-HUB unter <a href='/devices'>Geräte / API</a>, ob das Token zuletzt benutzt wurde.</li>
      <li>Wenn alle drei Punkte stimmen, ist die Einrichtung erfolgreich.</li>
    </ol>
  </div>

  <div class='card'>
    <h3>Doppelte Android-Wecker vermeiden</h3>
    <p>Je nach Uhr-App kann jedes Ausführen des Makros einen weiteren Wecker anlegen. Für Anfänger empfiehlt sich daher zunächst nur eine feste Synchronisation pro Tag. Später kann das Makro vor dem Anlegen vorhandene Alarm-HUB-Wecker entfernen oder vergleichen.</p>
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
    <p>Erzeuge unter <a href='/devices'>Geräte / API</a> ein neues Token und trage es erneut ein. Achte auf das Leerzeichen nach <code>Bearer</code>.</p>
  </div>
  <div class='card'>
    <h3>Die API funktioniert, aber kein Wecker wird erstellt</h3>
    <p>Dann liegt das Problem meistens in der Smartphone-Automation. Prüfe, ob <code>alarm.time</code> korrekt gelesen wird, ob Stunde und Minute richtig getrennt werden und ob Kurzbefehle bzw. MacroDroid die Berechtigung zum Erstellen von Weckern besitzen.</p>
  </div>
  <div class='card'>
    <h3>Es gibt keinen kommenden Wecker</h3>
    <p>Öffne in Alarm-HUB das Dashboard oder <a href='/alarms'>Meine Wecker</a>. Wenn dort kein zukünftiger Wecker vorhanden ist, liefert die API <code>alarm: null</code>. Das ist kein Fehler.</p>
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

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


# Existing pages resolve main._layout at request time. Replacing it here adds the
# guide link without duplicating the application's shared layout implementation.
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
  <h2>Smartphone-Wecker für Anfänger</h2>
  <p>Alarm-HUB klingelt nicht selbst auf deinem Smartphone. Dein iPhone oder Android-Gerät fragt Alarm-HUB nach dem nächsten Wecker und legt diesen anschließend in der lokalen Uhr-App an.</p>
  <p><b>Du brauchst zuerst ein Geräte-Token.</b> Öffne <a href='/devices'>Geräte / API</a>, erstelle z. B. ein Token mit dem Namen <i>iPhone</i> oder <i>Android</i> und kopiere es sofort. Das Token wird nur einmal vollständig angezeigt.</p>
  <div class='card'>
    <h3>Verwendete Adresse</h3>
    <p><code>{endpoint}</code></p>
    <p class='muted'>Das Token gehört niemals in die URL. Es wird als HTTP-Header <code>Authorization: Bearer DEIN_TOKEN</code> übertragen.</p>
  </div>
  <p><b>Wichtig:</b> Wenn du Alarm-HUB nur im Heimnetz erreichst, funktioniert die Synchronisation unterwegs nur über dein VPN. Für direkten Zugriff aus dem Internet solltest du ausschließlich HTTPS über einen sauber konfigurierten Reverse Proxy verwenden.</p>
</section>

<section id='ios'>
  <h2>iOS · iPhone mit Kurzbefehle</h2>
  <p>Für iPhones kannst du die bereits installierte Apple-App <b>Kurzbefehle</b> verwenden. Die Bezeichnungen einzelner Aktionen können je nach iOS-Version leicht abweichen.</p>
  <ol>
    <li><b>Token erstellen:</b> In Alarm-HUB unter <a href='/devices'>Geräte / API</a> ein neues Geräte-Token namens z. B. <i>iPhone</i> erzeugen und kopieren.</li>
    <li><b>Kurzbefehle öffnen:</b> Auf dem iPhone die App <i>Kurzbefehle</i> öffnen, oben rechts auf <b>+</b> tippen und den Kurzbefehl <i>Alarm-HUB Sync</i> nennen.</li>
    <li><b>URL hinzufügen:</b> Die Aktion <i>URL</i> hinzufügen und <code>{endpoint}</code> eintragen.</li>
    <li><b>Alarm-HUB abfragen:</b> Danach die Aktion <i>Inhalte von URL abrufen</i> hinzufügen. Methode <b>GET</b> verwenden. Unter Header einen neuen Eintrag anlegen: Name <code>Authorization</code>, Wert <code>Bearer DEIN_TOKEN</code>.</li>
    <li><b>Antwort auslesen:</b> Aus dem zurückgegebenen Wörterbuch zuerst den Schlüssel <code>alarm</code> lesen. Ist der Wert leer, gibt es aktuell keinen kommenden Wecker und der Kurzbefehl kann beendet werden.</li>
    <li><b>Uhrzeit lesen:</b> Aus <code>alarm</code> die Werte <code>time</code> und <code>name</code> holen. <code>time</code> kommt im Format <code>HH:MM</code>, z. B. <code>04:34</code>.</li>
    <li><b>Wecker erstellen:</b> Die Kurzbefehle-Aktion zum Erstellen/Hinzufügen eines Weckers wählen, die gelesene Uhrzeit einsetzen und als Bezeichnung z. B. <i>Alarm-HUB – [name]</i> verwenden.</li>
    <li><b>Testen:</b> Den Kurzbefehl einmal manuell starten. Danach in der Apple-Uhr-App prüfen, ob der Wecker mit der richtigen Uhrzeit angelegt wurde.</li>
    <li><b>Automatisieren:</b> In Kurzbefehle auf <i>Automation</i> wechseln und eine persönliche Automation erstellen, die <i>Alarm-HUB Sync</i> täglich ausführt, z. B. nachts oder früh morgens. Wenn deine Schichten tagsüber geändert werden, kannst du zusätzlich eine zweite tägliche Ausführung einrichten.</li>
  </ol>
  <div class='card'>
    <h3>Doppelte Wecker vermeiden</h3>
    <p>Wenn du den Kurzbefehl mehrmals täglich laufen lässt, kann iOS denselben Wecker mehrfach anlegen. Für den Einstieg empfiehlt sich deshalb nur eine oder zwei feste Synchronisationen pro Tag. Später kannst du vor dem Erstellen vorhandene Wecker mit der Bezeichnung <i>Alarm-HUB</i> suchen und entfernen.</p>
  </div>
</section>

<section id='android'>
  <h2>Android · mit MacroDroid</h2>
  <p>Android hat keine einheitliche eingebaute Automations-App. Für Anfänger ist <b>MacroDroid</b> eine einfache Möglichkeit. Alternativ funktioniert dasselbe Prinzip auch mit Tasker. Die Namen einzelner Aktionen können je nach Android-/MacroDroid-Version leicht abweichen.</p>
  <ol>
    <li><b>Token erstellen:</b> In Alarm-HUB unter <a href='/devices'>Geräte / API</a> ein Geräte-Token namens z. B. <i>Android</i> erzeugen und kopieren.</li>
    <li><b>MacroDroid installieren und öffnen.</b> Ein neues Makro mit dem Namen <i>Alarm-HUB Sync</i> anlegen.</li>
    <li><b>Auslöser wählen:</b> Als Trigger eine feste Tageszeit oder einen regelmäßigen Zeitplan verwenden, z. B. täglich früh morgens.</li>
    <li><b>HTTP-Abfrage hinzufügen:</b> Eine HTTP-/Web-Request-Aktion mit Methode <b>GET</b> anlegen und <code>{endpoint}</code> als Adresse verwenden.</li>
    <li><b>Header setzen:</b> Den HTTP-Header <code>Authorization</code> mit dem Wert <code>Bearer DEIN_TOKEN</code> hinzufügen.</li>
    <li><b>JSON auslesen:</b> Aus der Antwort <code>alarm.time</code> und <code>alarm.name</code> in Variablen übernehmen. Wenn <code>alarm</code> leer ist, soll das Makro ohne Änderung beendet werden.</li>
    <li><b>Wecker setzen:</b> Danach die Aktion zum Setzen/Erstellen eines Weckers bzw. Alarm-Clock-Aktion auswählen. Die Stunde und Minute aus <code>alarm.time</code> verwenden und als Beschriftung <i>Alarm-HUB – alarm.name</i> eintragen.</li>
    <li><b>Berechtigungen erlauben:</b> Falls Android danach fragt, MacroDroid die benötigten Berechtigungen für Alarme/Uhr und Hintergrundausführung geben. Bei einigen Herstellern muss zusätzlich die Akku-Optimierung für MacroDroid deaktiviert werden.</li>
    <li><b>Testen:</b> Das Makro manuell ausführen und anschließend in deiner Uhr-App prüfen, ob der Wecker korrekt gesetzt wurde.</li>
  </ol>
  <div class='card'>
    <h3>Wenn deine Android-Uhr keinen Wecker zulässt</h3>
    <p>Manche Hersteller blockieren das direkte Erstellen von Weckern durch Automations-Apps. In diesem Fall kannst du in MacroDroid die Aktion <i>Intent senden</i> bzw. die Alarm-Clock-Funktion verwenden oder als fortgeschrittene Alternative Tasker einsetzen.</p>
  </div>
</section>

<section>
  <h2>So prüfst du, ob die Verbindung funktioniert</h2>
  <p>Nach einer erfolgreichen Abfrage wird das Geräte-Token unter <a href='/devices'>Geräte / API</a> bei <b>zuletzt benutzt</b> mit einer aktuellen Zeit angezeigt. Damit kannst du schnell erkennen, ob dein Smartphone Alarm-HUB erreicht.</p>
  <p class='muted'>Die Smartphone-Automation erstellt immer nur den nächsten aktuell bekannten Wecker. Änderungen an manuellen Weckern oder WebComm-Schichten werden bei der nächsten Synchronisation berücksichtigt.</p>
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

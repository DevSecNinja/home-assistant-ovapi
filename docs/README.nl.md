# OVAPI voor Home Assistant

Vertrekborden voor favoriete haltes met gedeelde, voorzichtige API-aanvragen.
Gebruik de [bijbehorende kaarten](https://github.com/DevSecNinja/lovelace-ovapi)
voor vertrektijden, bekende vertragingen/uitval en een lokale "vertrek over"-teller.

**Aangepaste integratie, geen officieel Gold/Platinum-keurmerk.**
Home Assistant 2026.10 of nieuwer is vereist. Releasepublicatie is nog niet
geautomatiseerd.

## Installeren en instellen

[![OVAPI openen in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=DevSecNinja&repository=home-assistant-ovapi&category=integration)

Als HACS al is geïnstalleerd, opent de knop deze repository in jouw Home Assistant.
Bevestig het toevoegen als daarom wordt gevraagd, download OVAPI en herstart
Home Assistant. Werkt de koppeling niet, volg dan deze handmatige stappen.

Voeg
`https://github.com/DevSecNinja/home-assistant-ovapi` in HACS toe als aangepaste
repository, categorie **Integratie**. Download OVAPI, herstart Home Assistant en
voeg OVAPI toe via **Instellingen > Apparaten & diensten**.

Handmatig: kopieer alleen `custom_components/ovapi` uit de gewenste branch naar
de configuratiemap van Home Assistant en herstart.
Eigen lichte/donkere pictogrammen en logo's worden meegeleverd en lokaal door
Home Assistant getoond; een aparte brands-aanmelding is niet nodig.

Kies **Halte zoeken op naam**, voer een plaats en een deel van de haltenaam in en
kies de passende **plaats - haltenaam**. Kies daarna je haltebord of richting met
de namen, lijnen en bestemmingen die OVAPI levert. Je hoeft geen code op te zoeken.
Hoofdletters en accenten maken niet uit; verfijn een zoekopdracht met meer dan
50 resultaten.

**Normaal instellen heeft geen verplichte wachttijd van twee minuten.** De
namenlijst en gekozen haltegegevens mogen direct worden opgevraagd, ook vlak na
een bordverversing. De duur hangt af van de verbinding en je keuze.
Alle instelvensters delen maximaal twee zoekaanvragen per voortschrijdende
120 seconden. Een derde ongecachete aanvraag wacht; opnieuw openen of herladen
reset dit budget niet. Zoeken in de cache is lokaal, zonder aanvraag per toetsaanslag.

Het voortgangsscherm gaat automatisch verder; sluit het om te annuleren.
Serverpauzes gelden ook tijdens instellen en kunnen na fouten langer duren.
Zoekaanvragen stellen de volgende gewone bordverversing uit om dubbele aanvragen
te vermijden. Alleen extra zoekaanvragen na een paar kunnen op een verversbeurt
wachten, zodat bestaande borden niet worden verdrongen.

Per favoriet stel je een eigen naam, optionele lijnnummers/bestemming en looptijd
(0-120 minuten) in. **Haltecode invoeren (geavanceerd)** blijft beschikbaar voor
bekende codes van 1-10 cijfers, inclusief voorloopnullen. Maximaal tien
verschillende haltecodes delen het budget.

**Vervoermiddelen tonen** selecteert standaard bus, tram en metro. Kies minstens
een vervoermiddel; alles uitvinken geeft een duidelijke fout, niet opnieuw alles.
Alleen metro blijft ook nieuwe metrolijnen tonen. De genoemde bronwaarnemingen
zijn actuele voorbeelden, geen garantie dat elk vervoermiddel hier rijdt.
Oude favorieten zonder deze instelling blijven alle ondersteunde soorten tonen.
Laat **lijnnummers** leeg voor alle lijnen, of gebruik exacte openbare nummers met
komma's, bijvoorbeeld `50, 51`; voeg geen `M` toe als OVAPI die niet vermeldt.
**Bestemming bevat** is één tekstfragment, geen lijst met komma's; leeg is alles.

Ook handmatige code-invoer en herconfiguratie wachten automatisch op hetzelfde
zoekbudget. Een derde ongecachete controle kan wachten; dit is geen limiet van
twee favorieten. Invoer blijft bewaard en de voortgang toont de echte deadline,
met onderscheid tussen lokaal budget en een serverpauze. Gecachete haltes gaan
direct door. Sluiten annuleert onnodig werk. Mislukt de aanvraag zelf, dan blijft
het formulier met foutmelding staan: verstuur opnieuw om automatisch tot de
volgende toegestane poging te wachten. Er is geen automatische herhaallus bij fouten.

De namenlijst wordt alleen op verzoek opgehaald; vertrekgegevens uitsluitend voor
het gekozen haltegebied. Voorbeelden van lijnen/richtingen zijn geen volledige
dekking. Haltes zonder actuele vertrekinformatie blijven kiesbaar, maar richting
en vervoermiddel kunnen dan onbekend zijn. Een leeg resultaat bewijst niet dat er
niets rijdt. Bekende uitsluitend niet-ondersteunde vervoermiddelen worden weggelaten.

Op **2026-10-12** zijn twee afzonderlijke haltecodes met een kleine gecombineerde
aanvraag gecontroleerd: **Amsterdam Centraal `30009501`** en
**Amsterdam Amstel `30009514`**. De locatienamen klopten en ondersteunde
vervoersgegevens waren aanwezig. Dit zijn geen garanties voor alle perrons,
richtingen of bus-, tram- en metrolijnen. Controleer je eigen richting.
Echte vertrekgegevens zijn niet opgeslagen; testlijnen X1/X2 blijven fictief.

NS en andere treinen worden niet getoond. Gebruik daarnaast de ingebouwde
[Nederlandse Spoorwegen-integratie](https://www.home-assistant.io/integrations/nederlandse_spoorwegen/);
deze is geen afhankelijkheid.

Via **Configureren** wijzigen filters en looptijd lokaal, zonder extra aanvraag.
Via **Opnieuw configureren** wijzig je halte of naam. Een nieuwe halte of herladen
kan op het gedeelde budget wachten; probeer niet herhaaldelijk te verversen.
Dezelfde namenzoeker is beschikbaar en bestaande favoriet-/entiteit-ID's en
voorkeuren blijven behouden. Keuzes verlopen binnen 29 minuten; daarna laad je
nieuwe gegevens. Alleen je gekozen naam, code en voorkeuren worden opgeslagen.
De gekozen halte hergebruikt de opgehaalde gegevens zonder derde controleaanvraag.

**Hele stations automatisch toevoegen is nog niet beschikbaar.** Een favoriet
blijft één haltecode. Bij Diemen Zuid bevat het OVAPI-haltegebied alleen bussen,
terwijl werkende metrohaltes apart beschikbaar zijn. Deze update doet niet alsof
dat busgebied het volledige station is. Automatische stationsgroepering staat in
[#5](https://github.com/DevSecNinja/home-assistant-ovapi/issues/5), in afwachting van
een gecontroleerde actuele bron die stations aan haltecodes koppelt. Er worden
geen codes geraden en geen extra metadatabronnen geïnstalleerd.

## Actueel, verouderd en niet beschikbaar

Het apparaat toont de gekozen haltecode en **Status vertrekgegevens**.
**Gegevensbron actueel** is de toestand van de bron, niet een vertrektijd.
Bestaande entiteit-ID's en het achtervoegsel `departure_board` blijven behouden.
[Open de OVAPI-kaarten in HACS](https://my.home-assistant.io/redirect/hacs_repository/?owner=DevSecNinja&repository=lovelace-ovapi&category=plugin),
installeer ze, voeg een OVAPI-kaart aan je dashboard toe en kies de entiteit van
je favoriet. Ook het scherm na instellen verwijst hiernaar. Een gewone
entiteitenkaart toont alleen de status.

- **Gegevensbron actueel**: de laatste aanvraag lukte. Een geldig leeg bord is ook actueel.
- **Gegevensbron verouderd**: de aanvraag mislukte, maar vorige gegevens zijn nog niet verlopen.
- **Niet beschikbaar**: er zijn geen bruikbare gegevens of de bewaartermijn is voorbij.

Onbekende voorspellingen/uitval blijven onbekend. Geannuleerde ritten geven geen
actiegerichte vertrekteller. Onvolledige records zonder bruikbare dienstregeling,
lijn of bestemming worden weggelaten. Een leeg bord bewijst niet dat er geen OV rijdt.

Gewone bordaanvragen liggen minimaal twee minuten uit elkaar. Instellen heeft
het gedeelde budget van twee zoekaanvragen per 120 seconden. Dit zijn onze
keuzes, **geen officieel gepubliceerde toegestane limieten**.
Bij fouten wacht de integratie langer. Kaarten doen geen eigen OVAPI-aanvragen.

OVAPI gebruikt onversleuteld HTTP; HTTPS had bij controle een ongeldig certificaat.
Er worden geen inloggegevens naar OVAPI gestuurd.

Vertrekgegevens verdwijnen binnen 29 minuten uit het actieve geheugen, ook tijdens
storingen. Ze komen niet in Recorder, geschiedenis, herstelstatus of diagnostiek.
De sensor geeft alleen de toestand van het bord; gewone sensorkaarten en historische
vertrekautomatiseringen zijn daarom niet ondersteund. De gekoppelde GOVI-licentie
was niet beschikbaar bij controle. Lees de volledige [beleidsnotitie](policy.md).

## Problemen oplossen en verwijderen

Controleer bij verbindingsfouten HTTP-toegang en wacht de automatische pauze af.
Controleer bij een onbekende halte de code en voorloopnullen. Verwijder filters
tijdelijk bij een leeg bord en controleer de dekking van de vervoerder.
Diagnostiek bevat alleen veilige operationele informatie.

Verwijder favorieten in **Instellingen > Apparaten & diensten**, verwijder de
bijbehorende kaarten en verwijder eventueel de integratie uit HACS. Herstart na
het verwijderen van de code. Er is geen vertrekgeschiedenisbestand om op te ruimen.

Zie [de Engelse handleiding](../README.md) voor alle opties en voorbeelden en
[ontwikkeling](development.md) voor reproduceerbare offline tests.

# OVAPI voor Home Assistant

Vertrekborden voor favoriete haltes met gedeelde, voorzichtige API-aanvragen.
Gebruik de [bijbehorende kaarten](https://github.com/DevSecNinja/lovelace-ovapi)
voor vertrektijden, bekende vertragingen/uitval en een lokale "vertrek over"-teller.

**Aangepaste integratie, geen officieel Gold/Platinum-keurmerk.**
Home Assistant 2026.10 of nieuwer is vereist. De eerste implementatie staat op
een reviewbranch; er is nog geen release gepubliceerd.

## Installeren en instellen

Zodra de implementatie op de standaardbranch staat: voeg
`https://github.com/DevSecNinja/home-assistant-ovapi` in HACS toe als aangepaste
repository, categorie **Integratie**. Download OVAPI, herstart Home Assistant en
voeg OVAPI toe via **Instellingen > Apparaten & diensten**.

Handmatig: kopieer alleen `custom_components/ovapi` uit de gewenste branch naar
de configuratiemap van Home Assistant en herstart.

Per favoriet stel je een eigen naam, haltecode (1-10 cijfers, inclusief eventuele
voorloopnullen), optionele lijnnummers/bestemming en looptijd (0-120 minuten) in.
Gebruik de haltecode van de juiste haltepaal/richting, niet zomaar een stationsnaam.
Er wordt geen volledige haltelijst opgehaald. Maximaal tien verschillende
haltecodes delen hetzelfde aanvraagbudget.

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

## Actueel, verouderd en niet beschikbaar

- **Actueel**: de laatste aanvraag lukte. Een geldig leeg bord is ook actueel.
- **Verouderd**: de aanvraag mislukte, maar vorige gegevens zijn nog niet verlopen.
- **Niet beschikbaar**: er zijn geen bruikbare gegevens of de bewaartermijn is voorbij.

Onbekende voorspellingen/uitval blijven onbekend. Geannuleerde ritten geven geen
actiegerichte vertrekteller. Onvolledige records zonder bruikbare dienstregeling,
lijn of bestemming worden weggelaten. Een leeg bord bewijst niet dat er geen OV rijdt.

Alle aanvragen delen minimaal twee minuten tussen verzoeken. Dit is onze
voorzichtige keuze, **geen officieel gepubliceerde toegestane limiet**.
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

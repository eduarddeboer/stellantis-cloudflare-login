# Stellantis Cloudflare Login — experimentele releasecandidate

> **LET OP: dit is een openbare testrelease, niet voor productiegebruik.** Uitsluitend installeren op een afzonderlijke, herstelbare Home Assistant-testinstallatie.

De installatie wordt getest met Home Assistant Marketplace 2026.11+. De Cloudflare Worker zelf is **niet** inbegrepen in deze repository; de publieke licentie en distributie daarvan worden apart beoordeeld.

Deze community-fork is **niet officieel** van Stellantis, Peugeot, de oorspronkelijke auteur of Home Assistant.

<!-- ha-marketplace:exclude-start -->
## Preview-installatie

Voeg deze repository toe via Instellingen → Marketplace → Add from link. Schakel prereleases in en installeer uitsluitend op de geïsoleerde test-VM. Maak vooraf een snapshot. Voer geen MyPeugeot-credentials in.

<!-- ha-marketplace:exclude-end -->
## Technische basis

# Stellantis Vehicles – Cloudflare Login (EXPERIMENTAL BETA)

Niet officieel van Stellantis, Peugeot, Home Assistant of de oorspronkelijke ontwikkelaar.

Bevat een fork van `stellantis_vehicles` versie **2026.10.3** (MIT), als **2026.10.3-beta.3**.
Deze fork gebruikt **hetzelfde integratiedomein** als upstream en mag niet naast de bestaande Stellantis-integratie worden geïnstalleerd.
Updates van de originele integratie kunnen deze patch overschrijven.

De gebruikersinterface ondersteunt zowel de standaardlogin als een expliciet bevestigde `https://NAME.ACCOUNT.workers.dev/` met eigen geheime sleutel.
De OAuth-code wordt door deze Worker opgehaald; tokenuitwisseling en voertuiggegevens blijven bij Stellantis Vehicles.

Maak vooraf een volledige Home Assistant-back-up (inclusief config entries).
Installeer nooit op een draaiende installatie zonder terugvalplan.
Dit pakket is niet getest op meerdere voertuigen of accounts.

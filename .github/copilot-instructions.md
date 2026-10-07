# PeekPerformance – Copilot Instructions

## Język
Zawsze odpowiadaj po polsku.

## Projekt
PeekPerformance to lokalna aplikacja do analizy plików demo Counter-Strike 2 (`.dem` i `.dem.gz`).
Główny przepływ: wgranie demo, analiza statystyk i zdarzeń oraz eksport wyników do Excela lub CSV.
Istniejąca integracja z Leetify jest starszą funkcją planowaną do usunięcia. Nie rozbudowuj jej bez wyraźnego polecenia.

## Stack technologiczny
- **Język**: Python 3.10+
- **Interfejs**: `Streamlit`
- **Parsowanie demek**: `demoparser2`
- **Dane i wykresy**: `pandas`, `Plotly`
- **Lokalne przechowywanie**: SQLite
- **Eksport Excel**: `openpyxl`
- **Modele danych**: `dataclasses`
- **Typowanie**: zawsze dodawaj type hints

## Styl kodu
- PEP 8
- Type hints wszędzie
- f-stringi zamiast `.format()`
- Unikaj zbędnych abstrakcji – prostota > nadmierna inżynieria

## Bezpieczeństwo
- Analiza demek nie wymaga konta ani klucza API.
- Nie zapisuj danych uwierzytelniających w kodzie.

## Zachowanie Copilota
- Implementuj zmiany od razu, nie tylko sugeruj
- Krótkie, konkretne odpowiedzi
- Nie dodawaj docstringów ani komentarzy do kodu, którego nie zmieniasz

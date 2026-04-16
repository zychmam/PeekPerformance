# PeekPerformance – Copilot Instructions

## Język
Zawsze odpowiadaj po polsku.

## Projekt
PeekPerformance to Python scraper / klient API dla platformy Leetify (statystyki CS2).  
Zbiera dane o meczach, graczach i statystykach z API lub stron Leetify.

## Stack technologiczny
- **Język**: Python 3.11+
- **HTTP**: `httpx` (preferowany) lub `requests`
- **Parsowanie HTML** (jeśli potrzebne): `BeautifulSoup4`
- **Modele danych**: `dataclasses` lub `pydantic`
- **Async**: używaj `asyncio` + `async/await` gdy to sensowne
- **Typowanie**: zawsze dodawaj type hints

## Styl kodu
- PEP 8
- Type hints wszędzie
- f-stringi zamiast `.format()`
- Unikaj zbędnych abstrakcji – prostota > nadmierna inżynieria

## Bezpieczeństwo
- Dane uwierzytelniające (tokeny, klucze API) czytaj ze zmiennych środowiskowych lub pliku `.env` (python-dotenv)
- Nigdy nie hardkoduj credentials w kodzie

## Zachowanie Copilota
- Implementuj zmiany od razu, nie tylko sugeruj
- Krótkie, konkretne odpowiedzi
- Nie dodawaj docstringów ani komentarzy do kodu, którego nie zmieniasz

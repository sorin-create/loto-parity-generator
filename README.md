# loto-parity-generator
null-drift-loto-generator
# Loto Parity Generator

Script Python pentru analiza arhivei Loto 6/49, generarea și sortarea variantelor pe baza unui scor compus și a unui strat experimental de paritate (`a + b = 1`, prag critic `0.29213`), precum și rularea unui *walk-forward backtest*.

## Ce face `generator.py`

* **Încarcă și curăță arhiva CSV:** citește fișierul local (`arhiva.loto.2014-noi.2026.csv`) sau îl descarcă automat de la `GITHUB_CSV_RAW_URL` dacă lipsește, normalizând coloanele și validând extragerile.
* **Afișează numerele fierbinți și reci:** calculează topul numerelor fierbinți pe două ferestre consecutive (**20** și **50** de trageri) și topul numerelor reci (după numărul de extrageri absente).
* **Calculează intervalul dinamic de sumă și scorurile:** estimează limitele sumei pe o fereastră mobilă și clasează numerele (`1–49`) combinând fereastra recentă, frecvența globală și recența exponențială (`decay`).
* **Generează și sortează variante:** filtrează combinațiile de 6 numere (paritate, interval sumă, suprapunere și frecvență maximă) și le sortează (`sort_by="score_parity"` implicit) ținând cont de indicele local `a(t)` față de pragul `0.29213` (`NULL_DRIFT` vs. `PANIC_JAMMING`).
* **Rulează walk-forward backtest:** compară performanța `Top_K` (`6, 9, 12, 15`) cu selecția aleatorie și salvează `backtest_rezumat.csv` și `backtest_detalii.csv`.

## Utilizare rapidă

```bash
python generator.py

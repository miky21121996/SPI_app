# ⚡ Confronto run di produzione elettrica combinata (eolico + FV)

Questo script permette di confrontare **due run di previsioni di produzione elettrica combinata (eolico + fotovoltaico)** per un paese selezionato.  
I dati di input devono essere scaricati come **serie temporali aggregate giornaliere di combinato (wind + solar)**.

---

## 📂 Input richiesto
- File CSV esportato con il formato simile a: Power (Single) Germany - Combined (MW) 10-09-2025 10 (2).csv

⚠️ Il file deve contenere la **serie temporale combinata** (eolico + FV) per il paese selezionato.  

---

## 🛠️ Funzionalità
Lo script esegue i seguenti passaggi:
1. Caricamento e pulizia del file CSV.
2. Selezione di due run di previsione (es. `00Z GFS Mean` vs `06Z GFS Mean`).
3. Calcolo della differenza giornaliera:
 - Assoluta in **MW**
 - Percentuale in **%**
4. Filtro dei dati sul periodo definito dall’utente.
5. Aggregazione della differenza settimanale.
6. Creazione di un grafico con:
 - Barre verdi (aumento produzione)
 - Barre rosse (diminuzione produzione)
 - Annotazioni con le differenze percentuali
 - Delta settimanale mostrato nel grafico
7. Stampa in console del delta settimanale aggregato.

---

## 📊 Esempio di output
- **Grafico** con differenze giornaliere (positive/negative).
- **Console** con messaggio simile a: 
--- Delta Settimanale Aggregato (dal 15 Sep 2025 al 21 Sep 2025) ---
2025-09-21 1234.56


---

## ⚙️ Requisiti
Lo script utilizza le seguenti librerie Python:
- [pandas](https://pandas.pydata.org/)
- [numpy](https://numpy.org/)
- [matplotlib](https://matplotlib.org/)

Installa i pacchetti richiesti con:
```bash
pip install pandas numpy matplotlib

## 📊 Esempio di grafico

![Esempio Grafico](example_graph.png)

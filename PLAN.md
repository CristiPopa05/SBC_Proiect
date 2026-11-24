# Detecția indicatoarelor rutiere și dashboard

## Obiectiv

Camera MacBook-ului simulează o cameră orientată spre drum. Modelul analizează cadrul întreg, localizează unul sau mai multe indicatoare vizibile oriunde în imagine și afișează un chenar, tipul și scorul de încredere pentru fiecare detecție. Dashboard-ul Streamlit afișează fluxul video și istoricul salvat în SQLite.

## Date

Descarcă arhivele de pe Kaggle și extrage-le în subfolderele de mai jos. Păstrează structura internă, fișierele de adnotări și împărțirile incluse în arhive. Git ignoră `raw_data/` și `dataset/`.

| Sursă | Folder local | Rol |
| --- | --- | --- |
| [Traffic Signs Detection](https://www.kaggle.com/datasets/pkdarabi/cardetection) | `raw_data/cardetection/` | Sursa de pornire pentru detectorul YOLO. Verificăm clasele și adnotările din arhiva locală. |
| [German Traffic Sign Dataset](https://www.kaggle.com/datasets/harbhajansingh21/german-traffic-sign-dataset) | `raw_data/german-traffic-sign-dataset/` | Imagini cu indicatoare individuale pentru recunoașterea tipului de semn. Verificăm clasele și împărțirea înainte de a antrena clasificatorul. |
| [Road Segmentation Dataset](https://www.kaggle.com/datasets/trainingdatapro/roads-segmentation-dataset) | `raw_data/roads-segmentation-dataset/` | Cadre rutiere suplimentare. Poligoanele etichetate `road_sign` pot fi convertite în chenare pentru a evalua localizarea indicatoarelor. |

## Ordinea de lucru

1. Pe branch-ul `feature/ai-training`, inventariem fișierele din `raw_data/cardetection/`. Confirmăm ce tipuri de indicatoare sunt etichetate și verificăm vizual adnotările pe câteva imagini.
2. `scripts/prepare_data.py` pregătește structura YOLO Detection sub `dataset/detection/`, cu `images/`, `labels/` și `data.yaml`. Păstrăm împărțirile de antrenare, validare și test furnizate de sursă, dacă există. [Formatul Ultralytics YOLO Detection](https://docs.ultralytics.com/datasets/detect/)
3. `scripts/train_model.py` pornește de la `yolov8n.pt`, folosește MPS dacă este disponibil și salvează detectorul în `models/best.pt`. Validăm localizarea și clasele pe imagini din setul de test și rulăm predicția pe un clip de drum, inclusiv pe cadre cu semne la margini și mai multe semne în același cadru.
4. Verificăm acoperirea claselor. Pentru tipurile care lipsesc, avem nevoie de cadre în care acele semne sunt adnotate. Dacă folosim un detector generic pentru localizare, putem antrena separat un clasificator pe setul german și îl rulăm pe decupajele generate automat de detector. Folosim adnotările `road_sign` din setul de segmentare pentru a evalua localizarea separat de identificarea tipului.
5. După ce detectorul funcționează pe video, continuăm pe `feature/live-dashboard` cu fluxul OpenCV și afișarea detecțiilor în `app.py`, apoi cu istoricul din `database/db_manager.py` în `traffic_logs.db`.

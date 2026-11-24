# Detecția indicatoarelor rutiere și dashboard

## Obiectiv

Camera MacBook-ului simulează o cameră orientată spre drum. YOLO analizează cadrul întreg. Bordul Sign Assist afișează în timp real pictograma și numele semnului cu scorul cel mai mare și păstrează ultimele patru semne în sesiunea curentă.

## Date

Descarcă arhivele ZIP de pe Kaggle în subfolderele de mai jos. Scriptul de pregătire citește direct `raw_data/cardetection/cardetection.zip` și folosește împărțirile furnizate în arhivă. Pentru imagini identice prezente în mai multe seturi, păstrează prioritar testul, apoi validarea. Git ignoră `raw_data/` și `dataset/`.

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
5. Interfața Lovable din `frontend/` preia camera prin browser și trimite cadre către `detection_api.py`. Detectorul local folosește `models/best.pt`, iar interfața afișează rezultatul prin `setDetectedSign`.
6. Salvarea persistentă a istoricului în SQLite este o etapă planificată.

## Rulare locală

Din rădăcina proiectului, pregătește mediul și datele, apoi pornește antrenarea.

```sh
python3 -m venv venv
venv/bin/python -m pip install -r requirements.txt
venv/bin/python scripts/prepare_data.py
venv/bin/python scripts/train_model.py --epochs 5 --imgsz 416 --batch 16
```

Setul pregătit are 3.439 de imagini pentru antrenare, 791 pentru validare și 638 pentru test. Arhiva are 4.969 de imagini, iar pregătirea exclude 101 fișiere identice cu imagini din alte seturi. După pregătirea datelor, poți rula din nou direct `train_model.py`. Scriptul salvează cel mai bun model al rulării în `models/best.pt`, iar Ultralytics păstrează rezultatele fiecărei rulări în `runs/detect/`.

### Bordul din Lovable

Instalează dependențele Python și pregătește `models/best.pt` folosind pașii de mai sus. Modelul de bază acoperă indicatoarele STOP, limitele de viteză de la 10 la 120 km/h și semafoarele roșii și verzi. Butoanele demo afișează și alte categorii.

Pornește detectorul din rădăcina proiectului.

```sh
venv/bin/python detection_api.py
```

În alt terminal, instalează dependențele conform lockfile-ului și pornește interfața.

```sh
cd frontend
npx --yes --package=bun bun install --frozen-lockfile
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Deschide [Sign Assist](http://127.0.0.1:5173) și apasă **Pornește camera**.

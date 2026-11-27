# Detecția indicatoarelor rutiere și dashboard

## Obiectiv

Camera MacBook-ului simulează o cameră orientată spre drum. YOLO analizează cadrul întreg. Bordul Sign Assist afișează semnul cu scorul cel mai mare după ce îl vede în două cadre consecutive și păstrează ultimele patru semne din sesiune. Salvarea persistentă a istoricului în SQLite este o etapă planificată.

## Rulare locală

Ai nevoie de Python 3 cu `venv` și de Node.js 20.19+ sau 22.12+. Dacă `venv/` și `frontend/node_modules/` sunt deja instalate, mergi direct la pornire. [Cerințele Vite](https://vite.dev/guide/)

Din rădăcina proiectului, instalează dependențele o singură dată.

```sh
python3 -m venv venv
venv/bin/python -m pip install -r requirements.txt
(cd frontend && npx --yes --package=bun bun install --frozen-lockfile)
```

Cu checkpoint-ul `models/best.pt` disponibil, pornește API-ul în primul terminal. Dacă ai clonat proiectul, copiază checkpoint-ul și clasificatorul auxiliar `models/oncoming_classifier.pt` din instalarea care le are sau urmează pașii de antrenare de mai jos. Git ignoră fișierele `.pt` din `models/`.

```sh
venv/bin/python detection_api.py
```

Din rădăcina proiectului, pornește interfața în al doilea terminal.

```sh
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Deschide [Sign Assist](http://127.0.0.1:5173), apasă **Pornește camera** și permite accesul la cameră. Lasă ambele terminale deschise. Dacă vezi „Detector indisponibil”, verifică dacă API-ul ascultă pe portul `8510` și dacă terminalul Python afișează o eroare.

Poți încerca un alt checkpoint cu `venv/bin/python detection_api.py --weights models/candidate.pt`. Oprește instanța anterioară cu `Ctrl+C` înainte de a o reporni. Rezoluția implicită este 640 și poate fi ajustată cu `--imgsz`. `--conf` ajustează scorul minim, implicit `0.40`. `--device cpu` selectează CPU-ul dacă întâmpini o eroare cu GPU-ul.

## Date

Scriptul de pregătire citește direct `raw_data/cardetection/cardetection.zip`. Când găsește aceeași imagine, același nume de origine sau cadre din aceeași secvență GTSRB în mai multe seturi, păstrează prioritar testul, apoi validarea. Git ignoră `raw_data/` și `dataset/`. [Descrierea setului GTSRB](https://sid.erda.dk/public/archives/daaeac0d7ce1152aea9b61d9f1e19370/published-archive.html)

| Sursă | Folder local | Rol |
| --- | --- | --- |
| [Traffic Signs Detection](https://www.kaggle.com/datasets/pkdarabi/cardetection) | `raw_data/cardetection/` | Sursa de pornire pentru detectorul YOLO. Verificăm clasele și adnotările din arhiva locală. |
| [German Traffic Sign Dataset](https://www.kaggle.com/datasets/harbhajansingh21/german-traffic-sign-dataset) | `raw_data/german-traffic-sign-dataset/` | Decupaje pentru cele 43 de clase GTSRB și imagini de referință pentru bord. |
| [German Traffic Sign Detection Benchmark](https://sid.erda.dk/public/archives/ff17dc924eba88d5d01a807357d6614c/published-archive.html) | `raw_data/gtsdb/` | Cadre de drum cu chenare pentru clasele germane. |
| [BelgiumTS](https://btsd.ethz.ch/shareddata/) | `raw_data/belgiumts/` | Cadre de drum și decupaje pentru indicatoarele suplimentare din demo. |
| [Road Segmentation Dataset](https://www.kaggle.com/datasets/trainingdatapro/roads-segmentation-dataset) | `raw_data/roads-segmentation-dataset/` | Cadre rutiere suplimentare. Poligoanele etichetate `road_sign` pot fi convertite în chenare pentru a evalua localizarea indicatoarelor. |

## Pregătirea și antrenarea primului model

Pentru detector ai nevoie de arhiva **Traffic Signs Detection** din tabel. Descarc-o în `raw_data/cardetection/cardetection.zip`, apoi rulează din rădăcina proiectului.

```sh
venv/bin/python scripts/prepare_data.py
venv/bin/python scripts/train_model.py --epochs 25 --imgsz 416 --batch 16
```

Antrenarea pornește de la greutățile preantrenate `yolov8n.pt`, descărcate la prima rulare. Scriptul alege MPS pe Apple Silicon sau CUDA când este disponibil și folosește CPU în rest. Dacă ai nevoie de mai puțină memorie, folosește `--batch 8`. Modelul cu cel mai bun rezultat pe validare este copiat în `models/best.pt`. În `runs/detect/` găsești metricile pe epoci și matricea de confuzie.

Setul pregătit din arhiva actuală are 2.320 de imagini pentru antrenare, 576 pentru validare și 638 pentru test. Dacă ai deja un `dataset/detection/` pregătit cu vechiul script și vrei să evaluezi un model cu noua împărțire, pregătește un folder separat și pornește de la `yolov8n.pt`. Dacă `dataset/detection_grouped/data.yaml` există deja, rulează a doua comandă direct.

```sh
venv/bin/python scripts/prepare_data.py --output dataset/detection_grouped
venv/bin/python scripts/train_model.py --data dataset/detection_grouped/data.yaml \
  --epochs 25 --imgsz 416 --batch 16 --output models/grouped.pt
```

## Continuarea antrenării

Pentru încă 20 de epoci pornind de la modelul cu 54 de clase, folosește setul din `dataset/detection_oncoming/data.yaml`.

```sh
venv/bin/python scripts/train_model.py --weights models/best.pt \
  --data dataset/detection_oncoming/data.yaml \
  --epochs 20 --imgsz 416 --batch 16 --output models/candidate.pt
```

Compară checkpoint-urile pe același set de test și la aceeași rezoluție. Uită-te la mAP50–95 și la rândurile pentru clasele care contează în demo. Pentru cadre noi, verifică și ce detectează în clipuri în care semnele apar mici, la margine sau alături de alte semne. [Evaluarea modelelor YOLO](https://docs.ultralytics.com/modes/val/)

```sh
for model in best candidate; do
  venv/bin/yolo detect val model="models/$model.pt" data=dataset/detection_oncoming/data.yaml \
    split=test imgsz=640 project=runs/detect name="${model}_test"
done
```

Pentru un câștig pe camera ta, adaugă cadre rutiere adnotate cu semafoare, limitele rare, semne văzute de la distanță și cadre fără semne. Înregistrează clipuri diferite pentru antrenare, validare și test și păstrează toate cadrele unui clip în aceeași împărțire. Pentru poze fără semne, folosește etichete YOLO goale. [Formatul Ultralytics YOLO Detection](https://docs.ultralytics.com/datasets/detect/)

Pentru o nouă clasă, cum ar fi limita de 130 km/h din demo, adaugă clasa în `data.yaml` și adnotează semnul în cadre întregi. API-ul acceptă eticheta `Speed Limit 130`. Pozele decupate din GTSRB pot servi la antrenarea unui clasificator separat, iar poligoanele `road_sign` din setul de segmentare pot servi la evaluarea localizării.

## Cedează trecerea și Drum cu prioritate

Pentru a reface setul de 17 clase, descarcă `FullIJCNN2013.zip` și extrage dosarul `FullIJCNN2013`. `--gtsdb` trebuie să indice dosarul cu `gt.txt` și imaginile `.ppm` sau `.jpg`. În acest workspace, subsetul necesar este deja în `raw_data/gtsdb/`. Scriptul extinde `dataset/detection_grouped/` cu cadre întregi, decupaje mai apropiate și compoziții de antrenare. Dacă `dataset/detection_priority/data.yaml` există deja, poți trece direct la antrenare. `data_gtsdb_test.yaml` evaluează separat cadrele rutiere din împărțirea oficială de test. [Arhiva GTSDB](https://sid.erda.dk/public/archives/ff17dc924eba88d5d01a807357d6614c/published-archive.html)

```sh
venv/bin/python scripts/prepare_priority_data.py --gtsdb raw_data/gtsdb
venv/bin/python scripts/train_model.py --weights models/best.pt \
  --data dataset/detection_priority/data.yaml --epochs 7 --imgsz 416 --batch 16 \
  --output models/priority.pt
venv/bin/yolo detect val model=models/priority.pt \
  data=dataset/detection_priority/data_gtsdb_test.yaml split=test imgsz=640
```

## Parcare și celelalte indicatoare din BelgiumTS

Setul cu 24 de clase adaugă Parcare, Parcarea interzisă, Accesul interzis, Depășirea interzisă, Trecere pietoni, Sens giratoriu și Atenție. Pregătirea păstrează împărțirea oficială de test și folosește identificatorul stâlpului pentru a grupa cadrele aceluiași indicator de antrenare sau validare. `data_belgium_test.yaml` conține cadrele rutiere de test din cele două camere. [Sursa BelgiumTS](https://btsd.ethz.ch/shareddata/)

Pentru a reface setul, pornește cu `dataset/detection_priority/` pregătit. Salvează `BelgiumTSD_annotations.zip` ca `annotations.zip`, `BelgiumTSC_Training.zip` ca `crops_train.zip`, `BelgiumTSC_Testing.zip` ca `crops_test.zip` și păstrează numele `camera00.tar` și `camera01.tar`. Pune fișierele în `raw_data/belgiumts/`. Dacă `dataset/detection_belgium/data.yaml` există deja, poți rula direct antrenarea.

```sh
venv/bin/python scripts/prepare_belgium_data.py
venv/bin/python scripts/train_model.py --weights models/priority.pt \
  --data dataset/detection_belgium/data.yaml --epochs 6 --imgsz 416 --batch 16 \
  --output models/expanded.pt
venv/bin/yolo detect val model=models/expanded.pt \
  data=dataset/detection_belgium/data_belgium_test.yaml split=test imgsz=640
```

## Cele 43 de clase din setul german

Setul GTSRB oferă decupaje din 43 de clase. În datele YOLO extinse, 15 clase păstrează etichetele modelului existent și 28 primesc etichete noi. În total sunt 52 de clase împreună cu celelalte indicatoare și semafoare din model. YOLO localizează semnele, iar clasificatorul GTSRB verifică tipul pe decupaj când `models/gtsrb_classifier.pt` e disponibil. Bordul afișează denumirea în română și o poză de referință pentru clasele noi. [GTSRB și GTSDB](https://github.com/houbensebastian/GermanTrafficSignBenchmarks)

Păstrează `dataset/detection_belgium/` pregătit și arhiva GTSRB la calea din tabel. Pune `gt.txt` și imaginile adnotate din `FullIJCNN2013.zip` în `raw_data/gtsdb/`. Scriptul folosește cadrele rutiere și compune imagini din decupajele GTSRB cu împărțiri distincte pentru antrenare, validare și test. Poți omite pregătirea dacă `dataset/detection_gtsrb/data.yaml` există deja.

```sh
venv/bin/python -m scripts.prepare_gtsrb_data
venv/bin/python scripts/train_model.py --weights models/expanded.pt \
  --data dataset/detection_gtsrb/data.yaml --epochs 6 --imgsz 416 --batch 16 \
  --output models/gtsrb.pt
venv/bin/python -m scripts.train_gtsrb_classifier
for source in gtsdb gtsrb; do
  venv/bin/yolo detect val model=models/gtsrb.pt \
    data="dataset/detection_gtsrb/data_${source}_test.yaml" split=test imgsz=640
done
```

## Indicatoarele de prioritate din sens invers

Modelul cu 54 de clase adaugă „Prioritate pentru circulația din sens invers” (B19) și „Prioritate față de circulația din sens invers” (B21). Pentru pregătire, păstrează setul `dataset/detection_gtsrb/` și fișierele BelgiumTS de mai sus. Adaugă `camera05.tar` în `raw_data/belgiumts/`. [Sursa BelgiumTS](https://btsd.ethz.ch/shareddata/)

```sh
venv/bin/python -m scripts.prepare_oncoming_data
venv/bin/python scripts/train_model.py --weights models/gtsrb.pt \
  --data dataset/detection_oncoming/data.yaml --epochs 4 --warmup-epochs 0.5 \
  --imgsz 416 --batch 16 --output models/oncoming.pt
venv/bin/python -m scripts.train_oncoming_classifier
venv/bin/python detection_api.py --weights models/oncoming.pt
```

Clasificatorul auxiliar verifică aceleași chenare cu trei margini diferite. Pentru a schimba eticheta YOLO pe baza decupajului, cel puțin două variante trebuie să indice aceeași clasă cu un scor ridicat. Setul oficial de test are doar trei cadre pentru fiecare indicator nou, provenite de la un singur stâlp pe clasă. Verifică recunoașterea la distanță pe cadre suplimentare.

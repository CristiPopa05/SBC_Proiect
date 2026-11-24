# Traffic Sign Classification & Dashboard (GTSRB)

## Obiectiv
Antrenarea unui model YOLOv8 Classification (`yolov8n-cls.pt`) pe dataset-ul GTSRB (43 clase) și afișarea semnului arătat de pe telefon în pătratul central (ROI) al camerei MacBook-ului într-un dashboard Streamlit cu salvare istoric în SQLite.

## Arhitectură
- `raw_data/`: Arhiva/folderele brute GTSRB (ignorate de Git)
- `dataset/train/<class_id>/` și `dataset/val/<class_id>/`: Structură standard YOLO Classification
- `scripts/prepare_data.py`: Organizează imaginile din `raw_data/` în `dataset/train` și `dataset/val` pe cele 43 de clase
- `scripts/train_model.py`: Antrenează `YOLO("yolov8n-cls.pt")` cu `device="mps"` și salvează `models/best.pt`
- `database/db_manager.py`: Stochează istoricul detecțiilor în SQLite (`traffic_logs.db`)
- `app.py`: Dashboard Streamlit + OpenCV cu chenar central (ROI) pentru scanarea semnului de pe telefon

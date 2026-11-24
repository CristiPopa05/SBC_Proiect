"""Show full-frame traffic sign detections from the browser camera."""

import os
from pathlib import Path
from threading import Lock

import av
import streamlit as st
from streamlit_webrtc import WebRtcMode, webrtc_streamer


ROOT = Path(__file__).resolve().parent
CHECKPOINT = ROOT / "models" / "best.pt"


@st.cache_resource
def load_detector(checkpoint):
    os.environ.setdefault("YOLO_CONFIG_DIR", str(ROOT / "runs" / ".ultralytics"))
    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
    import torch
    from ultralytics import YOLO

    if torch.backends.mps.is_available():
        device = "mps"
    elif torch.cuda.is_available():
        device = "0"
    else:
        device = "cpu"
    return YOLO(str(checkpoint), task="detect"), device, Lock()


def main():
    st.set_page_config(page_title="Detecție live a indicatoarelor")
    st.title("Detecție live a indicatoarelor")
    if not CHECKPOINT.is_file():
        st.error("Lipsește models/best.pt. Rulează mai întâi scripts/train_model.py.")
        st.stop()

    confidence = st.slider("Prag de încredere", 0.10, 0.90, 0.25, step=0.05)
    model, device, lock = load_detector(CHECKPOINT)

    def detect_frame(frame):
        image = frame.to_ndarray(format="bgr24")
        with lock:
            result = model.predict(image, device=device, imgsz=640, conf=confidence, verbose=False)[0]
            annotated = result.plot(line_width=2)
        return av.VideoFrame.from_ndarray(annotated, format="bgr24")

    webrtc_streamer(
        key="traffic-sign-camera",
        mode=WebRtcMode.SENDRECV,
        rtc_configuration={"iceServers": []},
        media_stream_constraints={
            "video": {
                "width": {"ideal": 960},
                "height": {"ideal": 540},
                "frameRate": {"ideal": 15, "max": 20},
            },
            "audio": False,
        },
        video_frame_callback=detect_frame,
        video_html_attrs={"autoPlay": True, "playsInline": True, "muted": True, "style": {"width": "100%"}},
        translations={
            "start": "Pornește camera",
            "stop": "Oprește camera",
            "select_device": "Alege camera",
            "device_access_denied": "Permite accesul la cameră în setările browserului.",
            "device_not_available": "Camera este momentan indisponibilă.",
        },
    )
    st.caption("Modelul caută indicatoare STOP, limite de viteză și semafoare.")


if __name__ == "__main__":
    main()

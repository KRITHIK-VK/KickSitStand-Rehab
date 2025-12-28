# KickSitStand-Rehab

KickSitStand-Rehab is a computer-vision–based rehabilitation game designed to help patients practice controlled lower-limb movements in **sitting** or **standing** posture using a webcam.

The application uses human pose estimation to track movement and provides real-time visual feedback in a simple, patient-friendly interface.

---

## 🎮 Features

- Webcam-based motion tracking
- Sitting and Standing exercise modes
- Adjustable difficulty levels
- Timed exercise sessions
- Real-time HUD (time, repetitions, hits)
- Scorecard summary after each session
- Designed for rehab / physiotherapy use

---

## 🖥️ Download (Windows)

> **No Python installation required**

1. Go to the **Releases** section of this repository
2. Download the latest Windows release
3. Extract the archive (if split, extract from `.001`)
4. Run the `.exe` file

⚠️ Windows may show a SmartScreen warning because the app is unsigned.  
Click **More info → Run anyway**.

---

## 📦 Extraction Instructions (If Download Is Split)

If the release contains files like:
KickSitStand.zip.001
KickSitStand.zip.002


Steps:
1. Download **all parts**
2. Place them in the **same folder**
3. Right-click the `.zip.001` file
4. Extract using **7-Zip**
5. Run the extracted `.exe`

---

## Running From Source (Optional)

### Requirements
- Python 3.9+
- Webcam
- Recommended: NVIDIA GPU (CPU fallback supported)

### Install dependencies
```bash
pip install -r requirements.txt
```
### Run the application
```bash
python main.py
```
## Notes
The camera is activated only during gameplay
Camera resources are released automatically when exiting or returning to the menu
GPU is used automatically if available, otherwise CPU is used




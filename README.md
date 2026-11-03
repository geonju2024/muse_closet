# MUSE Closet Vision — 1-day starter

이 저장소는 Seeed Studio XIAO ESP32S3 Sense(OV3660) 기반으로 의류 사진을 ESP32 내부 AI 모델로 분류하고, 추론 로그를 Windows 노트북 SQLite DB에 남기는 하루짜리 MVP용 **시작 코드**입니다.

> **중요:** 의류 AI 모델 가중치는 포함되어 있지 않습니다. Edge Impulse 또는 SenseCraft AI에서 본인의 의류 데이터로 학습·배포해야 합니다. Camera test와 backend/CI는 별도로 실행 가능합니다. 완성된 온디바이스 AI 제품이라고 주장해서는 안 됩니다.

## 1. 오늘의 작업 순서

1. Arduino IDE에서 `esp32 by Espressif Systems` 보드 패키지 2.0.17 사용(Seeed Edge Impulse 예제 호환 목적)
2. Board에서 `XIAO_ESP32S3` 선택, PSRAM `OPI PSRAM` 활성화, USB CDC On Boot 설정 확인
3. `firmware/camera_test/camera_test.ino` 업로드 → `Camera initialized`, `Captured... bytes` 확인
4. Edge Impulse에서 `tops`, `bottoms`, `outerwear` 의류 사진을 각 30~50장 이상 수집하여 이미지 분류 모델 학습
5. Arduino library INT8 ZIP 배포 후 `esp32_camera` 예제를 **XIAO 핀맵**(본 프로젝트 camera_test 참조)으로 수정, ESP32에서 실제 모델 추론 확인
6. `backend` 서버와 DB 실행, `firmware/wifi_logger_example.h`를 추론 스케치에 통합
7. GitHub Actions `backend-tests`와 `camera-smoke-build` 통과 확인

## 2. 서버 실행 (Windows CMD / PowerShell)

```powershell
cd backend
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

브라우저에서 `http://127.0.0.1:8000/` 열면 DB 대시보드가 나타납니다.

다른 터미널에서 `cd backend` 후:
```powershell
.venv\Scripts\python send_demo.py
.venv\Scripts\python -m pytest -q
```

`send_demo.py`는 **가짜 테스트 데이터**를 1건 보내므로 성공해도 보드-서버 연결이 증명된 것은 아닙니다.

ESP32에서 접속할 때는 `http://127.0.0.1:8000`이 아니라 `ipconfig`로 확인한 **Windows 노트북의 같은 LAN IPv4 주소**를 사용합니다. 노트북과 ESP32는 같은 네트워크에 연결합니다. Windows 방화벽의 8000 포트 접근이 필요한 경우 로컬 네트워크에 한정하여 허용하세요.

## 3. ESP32에 DB 전송 붙이기

1. 학습된 모델 ZIP을 Arduino IDE에 `스케치 > 라이브러리 포함하기 > .ZIP 라이브러리 추가`로 추가
2. Export된 라이브러리에서 `esp32_camera` 예제를 열고 Seeed Studio XIAO 핀맵으로 수정
3. 실제 추론 성공을 시리얼에서 먼저 확인
4. `firmware/secrets.example.h`을 스케치 폴더에 `secrets.h`로 복사해 Wi-Fi/API 주소 수정
5. `firmware/wifi_logger_example.h` 내용을 스케치에 포함시키거나 같은 스케치 폴더에 복사하여 include
6. `setup()`에 `closetConnectWifi()`를 추가
7. 성공한 `run_classifier()` 직후 `closetSendPrediction(label, confidence, inferenceMs)` 호출
8. `DB upload status: 201`이면 DB 저장에 성공. `/api/predictions` 조회하여 실제 로그 확인

**주의:** 이 예제는 모델 자체를 포함하지 않습니다. 모델 라이브러리 이름과 `esp32_camera` 스케치는 배포한 Edge Impulse 프로젝트마다 다릅니다. `wifi_logger_example.h`의 `#include "secrets.h"`가 실제 스케치 폴더의 secrets.h를 찾도록 파일을 배치하세요.

## 4. CI 검증 범위

GitHub Actions는 (A) FastAPI/SQLite 단위 테스트, (B) **카메라 테스트 스케치의 컴파일**을 자동 검증합니다. Edge Impulse 모델을 포함하는 최종 추론 펌웨어는 학습 라이브러리를 연결하기 전까지 CI에서 컴파일하지 않습니다. 최종 펌웨어 검증은 Arduino IDE에서 실기기 업로드로 수행합니다.

## 5. 공식 자료

- 카메라 및 Arduino 가이드: https://wiki.seeedstudio.com/xiao_esp32s3_camera_usage/
- 이미지 분류·Edge Impulse 예제: https://wiki.seeedstudio.com/tinyml_course_Image_classification_project/
- Seeed Studio Getting Started: https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/
- Edge Impulse Studio: https://studio.edgeimpulse.com/

## 6. 성공 기준

- ESP32에서 카메라 이미지 취득 가능
- ESP32에서 직접 의류 분류 결과 출력 (서버 추론 X)
- Wi-Fi API로 전달한 **실제 ESP32의 추론 결과**가 SQLite에 저장
- GitHub Actions 성공
- 다른 의류 최소 9~15회 실제 평가 및 결과 기록

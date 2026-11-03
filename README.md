# MUSE Closet Vision

Seeed Studio **XIAO ESP32S3 Sense (OV3660)** 가 카메라로 의류 사진을 촬영하고, **ESP32-S3 안에서 직접** 경량 CNN(MobileNetV2, INT8)을 실행해
**상의(tops) / 하의(bottoms) / 아우터(outerwear)** 로 분류한 뒤, 추론 결과를 Wi-Fi로 노트북의 **FastAPI + SQLite** 에 로그로 저장하는 1일 MVP입니다.

> 이 저장소는 하루 동안 만든 MVP이며 완성된 제품이 아닙니다. 평가는 실제 옷이 아니라 **학습에 쓰지 않은 데이터셋 이미지를 노트북 화면에 띄워 OV3660으로 촬영**하는 방식으로 설계했습니다(아래 [한계](#9-한계와-개선-방향) 참고).

> **실기기 평가 결과 요약**: ESP32-S3에서 추론 **176 ms**, 모든 결과 DB 저장 성공. 화면 촬영 이미지 15장 분류 정확도는 **40% (6/15)** 로 낮으며, 특히 **아우터를 한 번도 맞히지 못했습니다(0/5).** 원인 분석과 개선 방향은 [§7 평가](#7-평가)에 정리했습니다.

## 1. 필수 조건 충족 현황

| 조건 | 구현 | 근거 |
|---|---|---|
| **① ESP32에 모델을 넣어 사용** | Edge Impulse로 학습한 MobileNetV2 INT8 모델을 Arduino 라이브러리로 펌웨어에 포함, `run_classifier()`를 ESP32-S3에서 실행(서버 추론 없음) | `firmware/closet_inference/`, `firmware/libraries/MUSE_Closet_Vision_inferencing/` |
| **② 로그를 DB에 저장** | 추론 직후 `POST /api/predictions` → SQLite `prediction_logs` 테이블, 대시보드(`/`)에서 5초마다 갱신 | `backend/main.py`, `closet_logger.h` |
| **③ CI 구현** | GitHub Actions 3개 job: 백엔드 테스트, 카메라 스케치 빌드, **모델 포함 최종 펌웨어 빌드** | `.github/workflows/ci.yml` |

**검증 상태**: ① **실기기 확인** — ESP32-S3에서 모델 실행 성공(DSP 4 ms + NN 172 ms = 176 ms). ② **실기기 확인** — ESP32가 보낸 추론 결과가 SQLite에 저장됨(`DB upload status: 201`, `id=1`). ③ **완료** — 3개 job 모두 통과. 15회 실기기 평가 완료(정확도 40%, [§7](#7-평가)).

## 2. 시스템 구조

```
 [노트북 화면: 평가 이미지]                         [Windows 노트북]
            │ 촬영                                ┌──────────────────────────┐
            ▼                                     │ FastAPI (uvicorn :8000)  │
 ┌────────────────────────────────┐   Wi-Fi       │  POST /api/predictions   │
 │ XIAO ESP32S3 Sense             │  HTTP JSON    │  GET  /api/predictions   │
 │  OV3660 → JPEG 320x240         │ ────────────▶ │  GET  /  (대시보드)       │
 │  → RGB888 → 중앙 crop 96x96    │               │        │                 │
 │  → MobileNetV2 INT8 (ESP-NN)   │               │        ▼                 │
 │  → label, confidence, ms       │               │  SQLite closet.db        │
 └────────────────────────────────┘               └──────────────────────────┘
        ▲ 시리얼 'c' = 추론+저장 / 't' = 추론만
```

DB 스키마 `prediction_logs`: `id, created_at(UTC), device_id, category, confidence, inference_ms, model_version`

## 3. 저장소 구성

| 경로 | 내용 |
|---|---|
| `firmware/closet_inference/` | **최종 펌웨어**: XIAO 핀맵, 시리얼 키 입력 1회 촬영·추론, Wi-Fi DB 전송(`closet_logger.h`) |
| `firmware/libraries/MUSE_Closet_Vision_inferencing/` | Edge Impulse 배포 라이브러리(v1.0.1, INT8, EON). ESP32-S3 크래시 수정 포함([§8](#8-문제-해결-기록)) |
| `firmware/camera_test/` | 카메라·PSRAM 동작 확인용 최소 스케치 |
| `firmware/camera_webserver/` | XIAO용 CameraWebServer(스트리밍으로 화각·방향 확인) |
| `backend/` | FastAPI + SQLite API, 대시보드, pytest |
| `tools/prepare_ei_dataset.py` | 원본 데이터셋 → 3클래스 균형 데이터(Edge Impulse 업로드용) |
| `tools/contact_sheet.py` | 육안 검수용 번호 붙은 썸네일 시트 |
| `tools/make_eval_viewer.py` | 학습 미사용 평가 이미지 15장 + 전체화면 뷰어 + 평가표 |
| `tools/fill_eval_sheet.py` | DB 로그와 평가표를 대조해 정확도·혼동행렬 계산 |

## 4. 데이터와 모델

**데이터**: [alexeygrigorev/clothing-dataset-small](https://github.com/alexeygrigorev/clothing-dataset-small) (자유 이용 가능 데이터셋, 10개 클래스)

| 우리 클래스 | 원본 클래스 | 학습 | 테스트 |
|---|---|---|---|
| tops | t-shirt, shirt, longsleeve (균등 샘플) | 121 | 32 |
| bottoms | pants, shorts, skirt (균등 샘플) | 128 | 32 |
| outerwear | outwear | 123 | 31 |
| (제외) | dress, hat, shoes | | |

- 클래스당 160장(총 480장)을 목표로 샘플링하고, 테스트는 원본 test 분할에서만 뽑아 학습과 겹치지 않게 했습니다.
- 썸네일 시트로 **육안 검수**하여 라벨이 모호한 13장을 제외했습니다(아우터 라벨인데 셔츠·니트·아기 우주복인 사진, 상의 라벨인데 원피스·바디수트·재킷인 사진, 노출 불량 사진).
- 재현: `py tools/prepare_ei_dataset.py <clothing-dataset-small 경로> data/ei_upload` (seed 고정)

**모델 (Edge Impulse)**: 입력 96×96 RGB(Fit shortest axis) → Transfer Learning **MobileNetV2 0.35** → 3클래스, **INT8 양자화**, EON Compiler, Arduino library 배포

| 항목 | 값 |
|---|---|
| Edge Impulse 검증 정확도 | 미기록 (Edge Impulse 프로젝트 학습 결과에서 확인 가능) |
| Edge Impulse 테스트(95장) 정확도 | 미기록 (Edge Impulse 프로젝트 Model testing에서 확인 가능) |
| 펌웨어 크기 (CI 빌드 기준) | 플래시 1,505,753 B (45%) / 전역 RAM 63,036 B (19%) |
| 실기기 추론 시간 (XIAO ESP32-S3) | DSP 4 ms + NN 172 ms = **176 ms** / 1회 |

## 5. 실행 방법

### 5-1. 서버 (Windows PowerShell)
```powershell
cd backend
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m uvicorn main:app --host 0.0.0.0 --port 8000
```
- 대시보드: `http://127.0.0.1:8000/`, 테스트: `.venv\Scripts\python -m pytest -q`
- ESP32에서 접속하려면 `--host 0.0.0.0`과 방화벽 허용이 필요합니다(로컬 서브넷·개인 네트워크로 한정):
  ```powershell
  New-NetFirewallRule -DisplayName "MUSE Closet API 8000" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow -Profile Private -RemoteAddress LocalSubnet
  ```
- `send_demo.py`는 **가짜 데이터**(`model_version=demo`)를 보내는 서버 확인용이며, 평가 집계에서는 제외됩니다.

### 5-2. 펌웨어 (Arduino IDE)
1. 보드 패키지 `esp32 by Espressif Systems` **2.0.17**, Board `XIAO_ESP32S3`, **PSRAM `OPI PSRAM`**, USB CDC On Boot `Enabled`
2. `firmware/libraries/MUSE_Closet_Vision_inferencing` 폴더를 ZIP으로 묶어 *스케치 > 라이브러리 포함하기 > .ZIP 라이브러리 추가*
3. `firmware/secrets.example.h`를 `firmware/closet_inference/secrets.h`로 복사하고 **2.4GHz** Wi-Fi와 `API_URL`(노트북 LAN IPv4, `ipconfig`로 확인) 입력. `secrets.h`는 `.gitignore` 대상입니다.
4. `firmware/closet_inference/closet_inference.ino` 업로드(첫 빌드는 10분 이상 소요)
5. 시리얼 모니터 115200: `t` = 추론만, `c` = 추론 + DB 저장 → `DB upload status: 201`, `DB saved: id=N`

## 6. CI (GitHub Actions)

| Job | 검증 내용 |
|---|---|
| `backend-tests` | Python 3.11, pytest 3개: 저장·조회, 잘못된 클래스 거부(422), health |
| `camera-smoke-build` | arduino-cli + esp32 core 2.0.17로 `camera_test`, `camera_webserver` 컴파일 |
| `inference-firmware-build` | **Edge Impulse 모델 + 카메라 + Wi-Fi/DB 로그가 포함된 최종 펌웨어** 컴파일 |

- `secrets.h`가 없는 CI 환경에서는 `__has_include`로 자리표시 값을 사용해 컴파일만 검증합니다.
- 실행 기록: https://github.com/geonju2024/muse_closet/actions

## 7. 평가

**방법**: 학습·테스트·제외 어디에도 쓰지 않은 원본 이미지에서 클래스당 5장(하위 클래스를 고르게: 셔츠/티/긴팔, 바지/반바지/치마) 총 **15장**을 골라(`tools/make_eval_viewer.py`, seed 고정), 노트북 화면에 전체화면으로 띄우고 OV3660으로 촬영 → ESP32에서 추론 → DB 저장. 1회 시도 = 시리얼 `c` 1번 = DB 1행이므로 평가표의 trial과 DB id가 1:1로 대응합니다.

```powershell
py tools/fill_eval_sheet.py               # 최근 ei-1.0.1 로그 15건을 trial 1..15에 매칭
py tools/fill_eval_sheet.py --first-id N  # 시험 기록이 섞였으면 trial 1의 DB id 지정
```

**결과** (DB id 3–17, `py tools/fill_eval_sheet.py --first-id 3`)

| # | 정답 | 예측 | 신뢰도 | 추론(ms) | DB id | 결과 |
|---|---|---|---|---|---|---|
| 1 | 상의 | 하의 | 0.90 | 176 | 3 | X |
| 2 | 아우터 | 하의 | 0.81 | 176 | 4 | X |
| 3 | 하의 | 하의 | 0.96 | 176 | 5 | O |
| 4 | 하의 | 하의 | 0.65 | 176 | 6 | O |
| 5 | 상의 | 상의 | 0.64 | 176 | 7 | O |
| 6 | 아우터 | 상의 | 0.73 | 176 | 8 | X |
| 7 | 아우터 | 상의 | 0.68 | 176 | 9 | X |
| 8 | 하의 | 상의 | 0.70 | 176 | 10 | X |
| 9 | 상의 | 하의 | 0.77 | 176 | 11 | X |
| 10 | 하의 | 하의 | 0.78 | 176 | 12 | O |
| 11 | 아우터 | 상의 | 0.92 | 176 | 13 | X |
| 12 | 상의 | 하의 | 0.57 | 177 | 14 | X |
| 13 | 하의 | 하의 | 0.60 | 176 | 15 | O |
| 14 | 상의 | 상의 | 0.64 | 176 | 16 | O |
| 15 | 아우터 | 하의 | 0.86 | 176 | 17 | X |

| 클래스 | 정답/시도 | 정확도 |
|---|---|---|
| 상의 (tops) | 2/5 | 40% |
| 하의 (bottoms) | 4/5 | 80% |
| 아우터 (outerwear) | 0/5 | 0% |
| **전체** | **6/15** | **40%** |

평균 추론 시간(DSP+NN, ESP32-S3): **176 ms** (최소 176 / 최대 177)

혼동 행렬 (행=정답, 열=예측)

| | 상의 | 하의 | 아우터 |
|---|---|---|---|
| 상의 | 2 | 3 | 0 |
| 하의 | 1 | 4 | 0 |
| 아우터 | 3 | 2 | 0 |

**분석**
- 전체 40%는 3클래스 무작위 추측(33%)과 큰 차이가 없습니다. 실사용 수준의 분류 성능은 **달성하지 못했습니다.**
- 모델이 **아우터를 한 번도 예측하지 않았습니다**(15회 중 하의 9회, 상의 6회). 아우터 5장은 모두 상의(3) 또는 하의(2)로 분류됐습니다.
- 틀린 예측도 신뢰도가 0.73~0.92로 높아, 모델의 신뢰도를 정답 여부의 근거로 쓸 수 없습니다.
- 추정 원인: ① 학습은 스마트폰 원본 사진, 평가는 **노트북 화면을 OV3660으로 재촬영**한 이미지라 모아레·반사·색 변화로 입력 분포가 크게 다름(OV3660 촬영 이미지는 학습에 포함하지 않음), ② 96×96 저해상도에서 아우터와 긴팔 상의는 형태가 비슷함, ③ 클래스당 약 120장의 작은 학습 데이터. Edge Impulse 테스트 정확도를 기록하지 못해 ①의 영향(데이터셋 이미지에서는 잘 맞는데 화면 촬영에서만 떨어지는지)은 분리해 확인하지 못했습니다.

**평가 기록**: DB id 1–2는 평가 전 동작 확인용 시도, id 18은 15회 이후 추가 입력으로 집계에서 제외했습니다. 1회 시도 = `c` 1회 = DB 1행이며 재촬영은 하지 않았습니다.

**동작 검증**

| 항목 | 상태 | 근거 |
|---|---|---|
| 모델 포함 최종 펌웨어 빌드 | ✅ 확인 | CI `inference-firmware-build` 통과 |
| 실기기 부팅: PSRAM 8MB 인식, OV3660(PID 0x3660) 초기화, Wi-Fi 연결 | ✅ 확인 | 시리얼 출력 |
| 실기기 추론 (`run_classifier`, ESP32-S3) | ✅ 확인 | 2회 실행, 매회 **DSP 4 ms + NN 172 ms = 176 ms** |
| ESP32 → DB 저장 | ✅ 확인 | `DB upload status: 201`, `DB saved: id=1` / `GET /api/predictions`에 `device_id=xiao-esp32s3-01, model_version=ei-1.0.1` 행 존재 |
| 15회 평가: 전체·클래스별 정확도 | ✅ 수행 | 위 결과표 (정확도 40%) |

실기기 시리얼 출력(발췌):
```
Camera PID: 0x3660
WiFi connected, IP: 192.168.0.132
[trial 2] DSP 4 ms, NN 172 ms
  bottoms    0.7109
  outerwear  0.0391
  tops       0.2500
RESULT trial=2 label=bottoms confidence=0.7109 inference_ms=176
DB upload status: 201
DB saved: id=1
```
위 출력은 평가 전 동작 확인용 시험이며 정확도 집계에 포함하지 않았습니다. 첫 시도는 `bottoms`와 `tops`가 0.4961로 동점이었습니다(INT8 출력은 1/256 단위로 양자화됨).

## 8. 문제 해결 기록

| 증상 | 원인 | 조치 |
|---|---|---|
| 첫 추론 시 `ERR: Failed to allocate persistent buffer of size 128, does not fit in tensor arena and reached EI_MAX_OVERFLOW_BUFFER_COUNT` 후 `Guru Meditation Error (StoreProhibited)`로 재부팅 | EON 모델의 tensor arena 크기 계산에 ESP-NN 커널의 계층별 persistent buffer가 포함되지 않음. 초과분 별도 할당 상한(10/30개)을 MobileNetV2가 넘고, 실패 시 NULL을 역참조 | `EI_MAX_OVERFLOW_BUFFER_COUNT`를 256으로 상향(`ei_classifier_porting.h`, `tflite_learn_*_compiled.cpp`). 추가 메모리 약 1KB. **실기기에서 해결 확인**(추론 정상 완료) |
| `secrets.h`가 하위 폴더에서 Git 추적 대상이 됨 | `.gitignore`가 `firmware/secrets.h` 한 경로만 지정 | 모든 폴더의 `secrets.h` 무시로 변경. 실제 Wi-Fi 정보는 커밋된 적 없음 |
| ESP32→서버 요청 차단 가능성 | 기존 python 허용 규칙이 Public 프로필 전용, 실제 네트워크는 Private | 8000/TCP, Private, LocalSubnet 한정 인바운드 규칙 추가 |

## 9. 한계와 개선 방향

- **화면 촬영 평가**: 실제 옷이 아닌 데이터셋 이미지를 화면에 띄워 촬영했습니다. 모아레·반사·색 왜곡이 있고, 실제 옷 촬영 정확도와 다를 수 있습니다.
- **낮은 분류 정확도(40%)와 도메인 차이**: 학습 데이터는 스마트폰 사진이며 OV3660 촬영 이미지를 학습에 넣지 않았습니다. 다음 단계 우선순위: ① 평가에 쓰지 않은 학습 이미지를 같은 환경(화면+OV3660)에서 클래스당 20~30장 촬영해 학습에 추가, ② Edge Impulse 테스트 정확도와 실기기 정확도를 함께 기록해 도메인 차이의 영향 분리, ③ 입력 해상도(96→160)·모델 폭(0.35→1.0) 상향을 메모리·추론 시간과 함께 비교.
- **작은 데이터와 평가 규모**: 학습 372장, 실기기 평가 15회로 통계적 신뢰도가 낮습니다.
- **분류 범위**: 3클래스만 지원하며 '옷 아님/배경' 클래스가 없어, 어떤 입력이든 셋 중 하나로 분류합니다.
- **보안**: API에 인증이 없고 HTTP 평문입니다. 같은 LAN 내 데모 용도로만 사용합니다.

## 10. 참고 자료

- XIAO ESP32S3 카메라: https://wiki.seeedstudio.com/xiao_esp32s3_camera_usage/
- XIAO + Edge Impulse 이미지 분류: https://wiki.seeedstudio.com/tinyml_course_Image_classification_project/
- Edge Impulse Studio: https://studio.edgeimpulse.com/
- 데이터셋: https://github.com/alexeygrigorev/clothing-dataset-small

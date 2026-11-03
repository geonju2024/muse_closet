/* MUSE Closet Vision - XIAO ESP32S3 Sense(OV3660) 온디바이스 의류 분류 + DB 로그
 * 기반: Edge Impulse esp32_camera 예제 (MIT, Copyright (c) 2022 EdgeImpulse Inc.)
 * 변경: XIAO 핀맵, 시리얼 키 입력으로 1회 촬영·추론, Wi-Fi로 결과를 FastAPI/SQLite에 저장
 *
 * 보드 설정: XIAO_ESP32S3 / PSRAM: OPI PSRAM / USB CDC On Boot: Enabled
 * 시리얼 모니터(115200, 줄 끝 아무거나)에서:
 *   c : 촬영 → ESP32에서 추론 → 결과 출력 → DB 저장   (평가·시연용, 1회 = DB 1행)
 *   t : 촬영 → 추론 → 결과 출력만 (DB 저장 안 함, 카메라 위치 맞출 때)
 */
#include <MUSE_Closet_Vision_inferencing.h>
#include "edge-impulse-sdk/dsp/image/image.hpp"
#include "esp_camera.h"
#include "closet_logger.h"

// ---- 영상 방향: CameraWebServer에서 옷이 똑바로 보였던 설정과 같게 맞추세요 ----
#define CAM_VFLIP   1
#define CAM_HMIRROR 0

// ---- XIAO ESP32S3 Sense 카메라 핀 (camera_test / CameraWebServer와 동일) ----
#define PWDN_GPIO_NUM  -1
#define RESET_GPIO_NUM -1
#define XCLK_GPIO_NUM  10
#define SIOD_GPIO_NUM  40
#define SIOC_GPIO_NUM  39
#define Y9_GPIO_NUM    48
#define Y8_GPIO_NUM    11
#define Y7_GPIO_NUM    12
#define Y6_GPIO_NUM    14
#define Y5_GPIO_NUM    16
#define Y4_GPIO_NUM    18
#define Y3_GPIO_NUM    17
#define Y2_GPIO_NUM    15
#define VSYNC_GPIO_NUM 38
#define HREF_GPIO_NUM  47
#define PCLK_GPIO_NUM  13

#define EI_CAMERA_RAW_FRAME_BUFFER_COLS 320
#define EI_CAMERA_RAW_FRAME_BUFFER_ROWS 240
#define EI_CAMERA_FRAME_BYTE_SIZE       3

static bool is_initialised = false;
static uint8_t *snapshot_buf = nullptr;
static uint32_t trial = 0;

static camera_config_t camera_config = {
    .pin_pwdn = PWDN_GPIO_NUM,
    .pin_reset = RESET_GPIO_NUM,
    .pin_xclk = XCLK_GPIO_NUM,
    .pin_sscb_sda = SIOD_GPIO_NUM,
    .pin_sscb_scl = SIOC_GPIO_NUM,
    .pin_d7 = Y9_GPIO_NUM,
    .pin_d6 = Y8_GPIO_NUM,
    .pin_d5 = Y7_GPIO_NUM,
    .pin_d4 = Y6_GPIO_NUM,
    .pin_d3 = Y5_GPIO_NUM,
    .pin_d2 = Y4_GPIO_NUM,
    .pin_d1 = Y3_GPIO_NUM,
    .pin_d0 = Y2_GPIO_NUM,
    .pin_vsync = VSYNC_GPIO_NUM,
    .pin_href = HREF_GPIO_NUM,
    .pin_pclk = PCLK_GPIO_NUM,
    .xclk_freq_hz = 20000000,
    .ledc_timer = LEDC_TIMER_0,
    .ledc_channel = LEDC_CHANNEL_0,
    .pixel_format = PIXFORMAT_JPEG,
    .frame_size = FRAMESIZE_QVGA,  // 320x240
    .jpeg_quality = 12,
    .fb_count = 1,
    .fb_location = CAMERA_FB_IN_PSRAM,
    .grab_mode = CAMERA_GRAB_LATEST,  // 키 입력 시점의 최신 프레임 사용
};

static bool ei_camera_init();
static bool ei_camera_capture(uint32_t img_width, uint32_t img_height, uint8_t *out_buf);
static int ei_camera_get_data(size_t offset, size_t length, float *out_ptr);
static void classify_once(bool upload);

void setup() {
  Serial.begin(115200);
  unsigned long t0 = millis();
  while (!Serial && millis() - t0 < 5000) delay(10);  // 시리얼 미연결이어도 5초 후 진행
  Serial.println("\nMUSE Closet Vision - on-device inference");
  Serial.printf("PSRAM found: %s, size: %u bytes\n", psramFound() ? "YES" : "NO", ESP.getPsramSize());
  if (!psramFound()) {
    Serial.println("ERROR: Tools > PSRAM > OPI PSRAM 으로 설정 후 다시 업로드하세요.");
    return;
  }
  Serial.printf("Model: %d labels, input %dx%d\n", EI_CLASSIFIER_LABEL_COUNT,
                EI_CLASSIFIER_INPUT_WIDTH, EI_CLASSIFIER_INPUT_HEIGHT);

  snapshot_buf = (uint8_t *)ps_malloc(EI_CAMERA_RAW_FRAME_BUFFER_COLS * EI_CAMERA_RAW_FRAME_BUFFER_ROWS *
                                      EI_CAMERA_FRAME_BYTE_SIZE);
  if (!snapshot_buf) {
    Serial.println("ERR: snapshot buffer 할당 실패");
    return;
  }
  if (!ei_camera_init()) {
    Serial.println("Failed to initialize Camera!");
    return;
  }
  Serial.println("Camera initialized");
  closetConnectWifi();
  Serial.println("Ready. 'c' = 추론+DB저장, 't' = 추론만");
}

void loop() {
  if (!Serial.available()) {
    delay(10);
    return;
  }
  char ch = Serial.read();
  if (ch == 'c' || ch == 'C') classify_once(true);
  else if (ch == 't' || ch == 'T') classify_once(false);
}

static void classify_once(bool upload) {
  if (!is_initialised || !snapshot_buf) {
    Serial.println("ERR: camera/buffer not ready");
    return;
  }
  // 이전 프레임이 남아 있을 수 있으므로 1장 버리고 새로 촬영
  camera_fb_t *stale = esp_camera_fb_get();
  if (stale) esp_camera_fb_return(stale);

  if (!ei_camera_capture(EI_CLASSIFIER_INPUT_WIDTH, EI_CLASSIFIER_INPUT_HEIGHT, snapshot_buf)) {
    Serial.println("Failed to capture image");
    return;
  }

  ei::signal_t signal;
  signal.total_length = EI_CLASSIFIER_INPUT_WIDTH * EI_CLASSIFIER_INPUT_HEIGHT;
  signal.get_data = &ei_camera_get_data;

  ei_impulse_result_t result = {0};
  EI_IMPULSE_ERROR err = run_classifier(&signal, &result, false);
  if (err != EI_IMPULSE_OK) {
    Serial.printf("ERR: Failed to run classifier (%d)\n", err);
    return;
  }

  size_t best = 0;
  for (size_t i = 1; i < EI_CLASSIFIER_LABEL_COUNT; i++) {
    if (result.classification[i].value > result.classification[best].value) best = i;
  }
  const char *label = result.classification[best].label;
  float conf = result.classification[best].value;
  uint32_t ms = result.timing.dsp + result.timing.classification;

  trial++;
  Serial.printf("\n[trial %u] DSP %d ms, NN %d ms\n", trial, result.timing.dsp, result.timing.classification);
  for (size_t i = 0; i < EI_CLASSIFIER_LABEL_COUNT; i++) {
    Serial.printf("  %-10s %.4f\n", result.classification[i].label, result.classification[i].value);
  }
  Serial.printf("RESULT trial=%u label=%s confidence=%.4f inference_ms=%u\n", trial, label, conf, ms);

  if (upload) {
    int r = closetSendPrediction(label, conf, ms);
    if (r > 0) Serial.printf("DB saved: id=%d\n", r);
  }
}

static bool ei_camera_init() {
  if (is_initialised) return true;
  esp_err_t err = esp_camera_init(&camera_config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed with error 0x%x\n", err);
    return false;
  }
  sensor_t *s = esp_camera_sensor_get();
  Serial.printf("Camera PID: 0x%04x\n", s->id.PID);
  if (s->id.PID == OV3660_PID) {
    s->set_brightness(s, 1);
    s->set_saturation(s, 0);
  }
  s->set_vflip(s, CAM_VFLIP);
  s->set_hmirror(s, CAM_HMIRROR);
  is_initialised = true;
  return true;
}

static bool ei_camera_capture(uint32_t img_width, uint32_t img_height, uint8_t *out_buf) {
  camera_fb_t *fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("Camera capture failed");
    return false;
  }
  bool converted = fmt2rgb888(fb->buf, fb->len, PIXFORMAT_JPEG, snapshot_buf);
  esp_camera_fb_return(fb);
  if (!converted) {
    Serial.println("Conversion failed");
    return false;
  }
  if (img_width != EI_CAMERA_RAW_FRAME_BUFFER_COLS || img_height != EI_CAMERA_RAW_FRAME_BUFFER_ROWS) {
    // 가운데를 정사각형으로 잘라 96x96으로 축소 (학습 시 Fit shortest axis와 같은 방식)
    ei::image::processing::crop_and_interpolate_rgb888(out_buf, EI_CAMERA_RAW_FRAME_BUFFER_COLS,
                                                       EI_CAMERA_RAW_FRAME_BUFFER_ROWS, out_buf,
                                                       img_width, img_height);
  }
  return true;
}

static int ei_camera_get_data(size_t offset, size_t length, float *out_ptr) {
  size_t pixel_ix = offset * 3;
  for (size_t i = 0; i < length; i++) {
    // esp32-camera fmt2rgb888는 BGR 순서 → RGB로 변환 (espressif/esp32-camera#379)
    out_ptr[i] = (snapshot_buf[pixel_ix + 2] << 16) + (snapshot_buf[pixel_ix + 1] << 8) + snapshot_buf[pixel_ix];
    pixel_ix += 3;
  }
  return 0;
}

#if !defined(EI_CLASSIFIER_SENSOR) || EI_CLASSIFIER_SENSOR != EI_CLASSIFIER_SENSOR_CAMERA
#error "Invalid model for current sensor"
#endif
